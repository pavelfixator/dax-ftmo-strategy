"""Tests for v3.3.5 STEP 3 1/3 consensus classifier.

Validates classify_regime_consensus_v331_step3 (single-signal regime mapping).
2/3 baseline classify_regime_raw remains unchanged — kept as reference.
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.strategy.regime.classifier import (
    Regime, RegimeSignals,
    classify_regime_consensus_v331_step3,
    classify_regime_step3,
    classify_regime_raw,
)


def _signals(vol="NORMAL", vol_v=1.0, adx_l="MODERATE", adx_v=25.0,
             slope="FLAT", slope_v=0.0):
    return RegimeSignals(
        ts=dt.datetime(2026, 4, 27, 8, 0, tzinfo=dt.timezone.utc),
        atr_pct_label=vol, atr_pct_value=vol_v,
        adx_h4_label=adx_l, adx_h4_value=adx_v,
        ema_slope_label=slope, ema_slope_value=slope_v,
    )


class TestStep3InstantCrash:
    """CRASH panic protection MUST be preserved (same as 2/3 baseline)."""

    def test_high_vol_down_returns_crash(self):
        assert classify_regime_consensus_v331_step3("HIGH", "WEAK", "DOWN") == Regime.CRASH

    def test_high_vol_down_with_strong_adx_still_crash(self):
        # CRASH priority over TREND — even if ADX STRONG
        assert classify_regime_consensus_v331_step3("HIGH", "STRONG", "DOWN") == Regime.CRASH

    def test_high_vol_up_NOT_crash(self):
        # HIGH vol but UP direction → not CRASH (rally, not panic)
        result = classify_regime_consensus_v331_step3("HIGH", "MODERATE", "UP")
        assert result != Regime.CRASH


class TestStep3SingleSignalTrend:
    """STRONG trend signal alone → TREND (1/3 consensus)."""

    def test_strong_adx_alone_returns_trend(self):
        # No vol/direction alignment, just STRONG ADX → TREND under 1/3 rule
        # (under 2/3 baseline this would also be TREND, but only when vol != HIGH)
        assert classify_regime_consensus_v331_step3("NORMAL", "STRONG", "FLAT") == Regime.TREND

    def test_strong_adx_with_low_vol_returns_trend(self):
        # STRONG takes priority over LOW vol → CALM check
        assert classify_regime_consensus_v331_step3("LOW", "STRONG", "FLAT") == Regime.TREND

    def test_strong_adx_with_high_vol_no_down_returns_trend(self):
        # HIGH+UP doesn't trigger CRASH; STRONG ADX → TREND
        assert classify_regime_consensus_v331_step3("HIGH", "STRONG", "UP") == Regime.TREND


class TestStep3SingleSignalCalm:
    """LOW vol alone (without STRONG trend) → CALM (1/3 consensus)."""

    def test_low_vol_alone_returns_calm(self):
        # LOW vol, MODERATE trend, FLAT direction → CALM under 1/3
        assert classify_regime_consensus_v331_step3("LOW", "MODERATE", "FLAT") == Regime.CALM

    def test_low_vol_weak_trend_returns_calm(self):
        # 2/3 baseline also returns CALM here
        assert classify_regime_consensus_v331_step3("LOW", "WEAK", "FLAT") == Regime.CALM

    def test_low_vol_with_strong_trend_returns_trend_not_calm(self):
        # STRONG takes priority over LOW vol
        assert classify_regime_consensus_v331_step3("LOW", "STRONG", "FLAT") == Regime.TREND


class TestStep3DirectionAlignment:
    """UP/DOWN + MODERATE trend → TREND/CALM by direction (4th rule)."""

    def test_up_direction_moderate_returns_trend(self):
        assert classify_regime_consensus_v331_step3("NORMAL", "MODERATE", "UP") == Regime.TREND

    def test_down_direction_moderate_returns_calm(self):
        # DOWN+MODERATE+NORMAL vol → CALM (NOT crash; only HIGH vol triggers CRASH)
        assert classify_regime_consensus_v331_step3("NORMAL", "MODERATE", "DOWN") == Regime.CALM

    def test_flat_direction_moderate_returns_undefined(self):
        # FLAT direction does not trigger directional rule
        assert classify_regime_consensus_v331_step3("NORMAL", "MODERATE", "FLAT") == Regime.UNDEFINED

    def test_up_direction_weak_trend_returns_undefined(self):
        # WEAK trend disqualifies the direction rule (only MODERATE qualifies)
        assert classify_regime_consensus_v331_step3("NORMAL", "WEAK", "UP") == Regime.UNDEFINED


class TestStep3UndefinedFallback:
    """No single signal aligned → UNDEFINED."""

    def test_all_neutral_returns_undefined(self):
        # NORMAL vol + WEAK trend + FLAT dir → no rule matches → UNDEFINED
        assert classify_regime_consensus_v331_step3("NORMAL", "WEAK", "FLAT") == Regime.UNDEFINED


class TestStep3FrequencyVsBaseline:
    """1/3 consensus must produce more decisive (non-UNDEFINED) classifications
    than 2/3 baseline on average."""

    def test_more_trades_eligible_under_1_of_3(self):
        # Cases where 2/3 returns UNDEFINED but 1/3 returns a trading regime
        cases = [
            # (vol, adx, slope) — combinations 2/3 marks UNDEFINED but 1/3 should classify
            ("LOW", "MODERATE", "FLAT"),  # 2/3: UNDEFINED (need WEAK adx); 1/3: CALM
            ("NORMAL", "STRONG", "FLAT"),  # 2/3: TREND; 1/3: TREND (same)
            ("NORMAL", "MODERATE", "UP"),  # 2/3: UNDEFINED; 1/3: TREND
            ("NORMAL", "MODERATE", "DOWN"),  # 2/3: UNDEFINED; 1/3: CALM
        ]
        n_eligible_baseline = 0
        n_eligible_step3 = 0
        for vol, adx_l, slope in cases:
            sig = _signals(vol=vol, adx_l=adx_l, slope=slope)
            if classify_regime_raw(sig) != Regime.UNDEFINED:
                n_eligible_baseline += 1
            if classify_regime_consensus_v331_step3(vol, adx_l, slope) != Regime.UNDEFINED:
                n_eligible_step3 += 1
        # 1/3 must be at least as decisive as 2/3 (and on these cases strictly more)
        assert n_eligible_step3 >= n_eligible_baseline
        assert n_eligible_step3 > n_eligible_baseline  # strictly more on this set

    def test_crash_unchanged_between_2_of_3_and_1_of_3(self):
        # CRASH instant rule is identical in both classifiers
        sig = _signals(vol="HIGH", slope="DOWN", adx_l="WEAK")
        assert classify_regime_raw(sig) == Regime.CRASH
        assert classify_regime_step3(sig) == Regime.CRASH


class TestStep3WrapperConsistency:
    """classify_regime_step3(signals) wrapper must equal direct call."""

    def test_wrapper_matches_direct_call(self):
        for vol in ("HIGH", "NORMAL", "LOW"):
            for adx_l in ("STRONG", "MODERATE", "WEAK"):
                for slope in ("UP", "FLAT", "DOWN"):
                    sig = _signals(vol=vol, adx_l=adx_l, slope=slope)
                    direct = classify_regime_consensus_v331_step3(vol, adx_l, slope)
                    via_wrapper = classify_regime_step3(sig)
                    assert direct == via_wrapper, f"mismatch at ({vol}, {adx_l}, {slope})"


class TestStep3EnumerationCoverage:
    """All 27 (vol × adx × slope) combinations produce a valid Regime."""

    def test_all_combinations_return_valid_regime(self):
        valid = {Regime.TREND, Regime.CALM, Regime.CRASH, Regime.UNDEFINED}
        count_undefined = 0
        count_total = 0
        for vol in ("HIGH", "NORMAL", "LOW"):
            for adx_l in ("STRONG", "MODERATE", "WEAK"):
                for slope in ("UP", "FLAT", "DOWN"):
                    r = classify_regime_consensus_v331_step3(vol, adx_l, slope)
                    assert r in valid
                    count_total += 1
                    if r == Regime.UNDEFINED:
                        count_undefined += 1
        # Sanity: 1/3 consensus produces fewer UNDEFINED than 2/3 baseline.
        # 2/3 baseline produces UNDEFINED for ~22/27 combinations; 1/3 should
        # produce noticeably fewer (Princip #8 magnitude check at boundary).
        assert count_undefined < 22, (
            f"1/3 consensus too restrictive: {count_undefined}/27 UNDEFINED "
            "(expected < 22 from 2/3 baseline)"
        )
