"""Tests pro v3.3.2.1 US-Momentum filter sets per regime."""
from __future__ import annotations

from src.strategy.regime import Regime
from src.strategy.setups.us_momentum_v331 import REGIME_FILTERS


class TestV3321FilterSets:
    def test_trend_unchanged_f1234(self):
        assert REGIME_FILTERS[Regime.TREND] == {"F1", "F2", "F3", "F4"}

    def test_calm_drops_f2_includes_f5(self):
        # v3.3.4: CALM = F1+F3+F4+F5_CALM (drop F2, RESTORED F5_CALM=MACD)
        s = REGIME_FILTERS[Regime.CALM]
        assert s == {"F1", "F3", "F4", "F5_CALM"}
        assert "F2" not in s
        assert "F5_CALM" in s

    def test_crash_drops_f1(self):
        # v3.3.2.1: CRASH = F2+F3+F4 (drop F1 — top winner, gap-fill mechanistic)
        s = REGIME_FILTERS[Regime.CRASH]
        assert s == {"F2", "F3", "F4"}
        assert "F1" not in s

    def test_undefined_blocks_all(self):
        assert REGIME_FILTERS[Regime.UNDEFINED] == set()


class TestFilterCount:
    """Filter Budget Rule: max 4 filters per cell, F5 framework dropped."""

    def test_no_regime_uses_more_than_4(self):
        for r, filters in REGIME_FILTERS.items():
            assert len(filters) <= 4, f"{r} has {len(filters)} filters (> 4)"

    def test_f5_calm_only_in_calm(self):
        # v3.3.4: F5_CALM restored to CALM regime only
        for r, filters in REGIME_FILTERS.items():
            f5_filters = [f for f in filters if f.startswith("F5")]
            if r == Regime.CALM:
                assert f5_filters == ["F5_CALM"], f"{r} should have F5_CALM"
            else:
                assert not f5_filters, f"{r} should NOT have F5 filter, got {f5_filters}"
