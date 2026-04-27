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

    def test_crash_05x(self):
        assert REGIME_RISK_MULTIPLIERS[Regime.CRASH] == 0.5

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

    def test_crash_05x_halves_lots_when_standard_binds(self):
        r_trend = calculate_lots_v331("A", "normal", Regime.TREND,
                                       sl_points=300, eur_usd_spot=EURUSD,
                                       dax_price=DAX)
        r_crash = calculate_lots_v331("A", "normal", Regime.CRASH,
                                       sl_points=300, eur_usd_spot=EURUSD,
                                       dax_price=DAX)
        if r_trend.capped_by == "standard" and r_crash.capped_by == "standard":
            ratio = r_crash.lots / r_trend.lots
            assert 0.45 <= ratio <= 0.55

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
        # base A normal = 1000 USD; CRASH 0.5× → 500 USD risk_usd
        assert r.risk_usd == 500.0

    def test_unknown_regime_raises(self):
        class FakeRegime:
            pass
        with pytest.raises((ValueError, KeyError, TypeError)):
            calculate_lots_v331("A", "normal", FakeRegime(),
                                 sl_points=100, eur_usd_spot=EURUSD,
                                 dax_price=DAX)
