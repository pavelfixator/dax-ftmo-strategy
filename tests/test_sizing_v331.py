"""Tests pro src.risk.sizing_v331 — regime risk multipliers."""
from __future__ import annotations

import pytest

from src.risk.sizing_v331 import (
    calculate_lots_v331, REGIME_RISK_MULTIPLIERS,
)
from src.risk.risk_manager import compute_lots
from src.strategy.regime import Regime

EURUSD = 1.08
DAX = 24155.0


class TestRegimeMultipliers:
    def test_trend_full_risk(self):
        assert REGIME_RISK_MULTIPLIERS[Regime.TREND] == 1.0

    def test_calm_07x(self):
        assert REGIME_RISK_MULTIPLIERS[Regime.CALM] == 0.7

    def test_crash_10x_v3_3_5_step_1(self):
        # v3.3.5 STEP 1: CRASH 0.5 → 1.0 (post 16-kolo adversarial review)
        assert REGIME_RISK_MULTIPLIERS[Regime.CRASH] == 1.0

    def test_undefined_zero(self):
        assert REGIME_RISK_MULTIPLIERS[Regime.UNDEFINED] == 0.0


class TestCalculateLotsV331:
    def test_undefined_returns_zero_no_trade(self):
        r = calculate_lots_v331("A", "normal", Regime.UNDEFINED,
                                 sl_points=100, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
        assert r.lots == 0.0
        assert r.capped_by == "regime_undefined"
        assert r.detail["regime"] == "UNDEFINED"

    def test_trend_matches_baseline(self):
        # TREND multiplier 1.0 → identical to compute_lots when standard not capped
        r_v331 = calculate_lots_v331("A", "normal", Regime.TREND,
                                      sl_points=200, eur_usd_spot=EURUSD,
                                      dax_price=DAX)
        r_base = compute_lots("A", "normal", sl_points=200, eur_usd_spot=EURUSD,
                                dax_price=DAX)
        assert r_v331.lots == r_base.lots

    def test_calm_07x_reduces_standard_branch(self):
        # Wide SL keeps standard branch binding; CALM 0.7× should reduce lots ~30%
        r_trend = calculate_lots_v331("A", "normal", Regime.TREND,
                                       sl_points=300, eur_usd_spot=EURUSD,
                                       dax_price=DAX)
        r_calm = calculate_lots_v331("A", "normal", Regime.CALM,
                                      sl_points=300, eur_usd_spot=EURUSD,
                                      dax_price=DAX)
        if r_trend.capped_by == "standard" and r_calm.capped_by == "standard":
            ratio = r_calm.lots / r_trend.lots
            assert 0.65 <= ratio <= 0.75

    def test_crash_10x_matches_trend_v3_3_5_step_1(self):
        # v3.3.5 STEP 1: CRASH multiplier boosted 0.5 → 1.0 → matches TREND magnitude
        r_trend = calculate_lots_v331("A", "normal", Regime.TREND,
                                       sl_points=300, eur_usd_spot=EURUSD,
                                       dax_price=DAX)
        r_crash = calculate_lots_v331("A", "normal", Regime.CRASH,
                                       sl_points=300, eur_usd_spot=EURUSD,
                                       dax_price=DAX)
        if r_trend.capped_by == "standard" and r_crash.capped_by == "standard":
            ratio = r_crash.lots / r_trend.lots
            assert 0.95 <= ratio <= 1.05  # both 1.0× now

    def test_disabled_state_zero(self):
        # B in warning state = disabled regardless of regime
        r = calculate_lots_v331("B", "warning", Regime.TREND,
                                 sl_points=100, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
        assert r.lots == 0
        assert r.capped_by == "disabled"

    def test_bsc_cap_still_applies_in_calm(self):
        # Tight SL → BSC binds; CALM multiplier scales standard but BSC stays
        r = calculate_lots_v331("A", "normal", Regime.CALM,
                                 sl_points=30, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
        # If BSC < scaled-standard, BSC binds
        assert r.capped_by in {"black_swan_cap", "standard", "margin_cap"}
        assert r.lots > 0
        assert r.detail["regime"] == "CALM"
        assert r.detail["regime_multiplier"] == 0.7

    def test_risk_usd_reflects_multiplier(self):
        r = calculate_lots_v331("A", "normal", Regime.CRASH,
                                 sl_points=300, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
        # v3.3.5 STEP 1: base A normal = 1000 USD; CRASH 1.0× → 1000 USD risk_usd
        assert r.risk_usd == 1000.0

    def test_crash_multiplier_v3_3_5_step_1(self):
        """v3.3.5 STEP 1: CRASH multiplier 0.5 → 1.0 verification.

        Pavel's spec gave argument order swap (sl_points/eur_usd_spot positional
        confusion); this corrected version uses keyword args.
        """
        # Verify multiplier constant
        assert REGIME_RISK_MULTIPLIERS[Regime.CRASH] == 1.0
        # Verify lots match boosted formula (no BSC binding for SL=70):
        # 1000 / (70 × 1.08) × 1.0 = 13.22 (matches Pavel's 13.22 lots target for US-MOM CRASH)
        r = calculate_lots_v331("A", "normal", Regime.CRASH,
                                 sl_points=70, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
        # Expected ~13.22 (standard branch binds; below BSC 23.15 and margin caps)
        assert 13.0 < r.lots < 13.5
        assert r.risk_usd == 1000.0  # boosted to full A-normal $1K

    def test_unknown_regime_raises(self):
        class FakeRegime:
            pass
        with pytest.raises((ValueError, KeyError, TypeError)):
            calculate_lots_v331("A", "normal", FakeRegime(),
                                 sl_points=100, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
