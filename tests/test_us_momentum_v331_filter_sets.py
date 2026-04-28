"""Tests pro v3.3.2.1 US-Momentum filter sets per regime."""
from __future__ import annotations

from src.strategy.regime import Regime
from src.strategy.setups.us_momentum_v331 import REGIME_FILTERS


class TestV3321FilterSets:
    def test_trend_unchanged_f1234(self):
        assert REGIME_FILTERS[Regime.TREND] == {"F1", "F2", "F3", "F4"}

    def test_calm_drops_f2_no_f5(self):
        # v3.3.2.1: CALM = F1+F3+F4 (drop F2 paralyzes calm, F5_CALM dropped)
        s = REGIME_FILTERS[Regime.CALM]
        assert s == {"F1", "F3", "F4"}
        assert "F2" not in s
        assert "F5_CALM" not in s

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

    def test_no_f5_anywhere(self):
        for r, filters in REGIME_FILTERS.items():
            for f in filters:
                assert not f.startswith("F5"), f"{r} still has {f}"
