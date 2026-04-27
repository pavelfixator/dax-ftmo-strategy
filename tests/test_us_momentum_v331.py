"""Tests pro src.strategy.setups.us_momentum_v331 — regime-aware + DST."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.regime import Regime
from src.strategy.setups.us_momentum_v331 import (
    UsMomentumSetupV331, REGIME_FILTERS,
    macd_3_10_histogram, f5_calm_macd_aligned,
)


# ============================================================
# Filter sets
# ============================================================

class TestFilterSets:
    def test_trend_uses_f1234(self):
        assert REGIME_FILTERS[Regime.TREND] == {"F1", "F2", "F3", "F4"}

    def test_calm_swaps_f2_for_f5(self):
        assert REGIME_FILTERS[Regime.CALM] == {"F1", "F3", "F4", "F5_CALM"}

    def test_crash_uses_f1_f2_mandatory_plus_f3_f4(self):
        assert REGIME_FILTERS[Regime.CRASH] == {"F1", "F2", "F3", "F4"}

    def test_undefined_empty(self):
        assert REGIME_FILTERS[Regime.UNDEFINED] == set()


# ============================================================
# MACD 3-10 (F5_CALM)
# ============================================================

class TestMacd:
    def test_uptrend_yields_positive_histogram(self):
        s = pd.Series(np.linspace(13000, 13200, 50))
        h = macd_3_10_histogram(s).dropna()
        # In a clean uptrend, MACD line > signal eventually → positive hist
        assert h.iloc[-5:].mean() > 0

    def test_downtrend_yields_negative_histogram(self):
        s = pd.Series(np.linspace(13200, 13000, 50))
        h = macd_3_10_histogram(s).dropna()
        assert h.iloc[-5:].mean() < 0

    def test_f5_calm_aligned_long_in_uptrend(self):
        s = pd.Series(np.linspace(13000, 13150, 30))
        assert f5_calm_macd_aligned(s, "LONG") is True
        assert f5_calm_macd_aligned(s, "SHORT") is False

    def test_f5_calm_aligned_short_in_downtrend(self):
        s = pd.Series(np.linspace(13150, 13000, 30))
        assert f5_calm_macd_aligned(s, "SHORT") is True
        assert f5_calm_macd_aligned(s, "LONG") is False

    def test_f5_calm_empty_returns_false(self):
        assert f5_calm_macd_aligned(pd.Series([], dtype=float), "LONG") is False


# ============================================================
# Setup behavior
# ============================================================

class TestSetupV331:
    def test_undefined_never_signals(self):
        s = UsMomentumSetupV331()
        ts = pd.Timestamp("2020-01-13 15:30", tz="Europe/Berlin").tz_convert("UTC")
        sig = s.check_entry_at(pd.DataFrame({"close": [13000]}, index=[ts]),
                                pd.DataFrame(), ts, Regime.UNDEFINED)
        assert sig is None

    def test_no_signal_outside_window(self):
        s = UsMomentumSetupV331()
        ts = pd.Timestamp("2020-01-13 11:00", tz="Europe/Berlin").tz_convert("UTC")
        df = pd.DataFrame({"open": 1, "high": 1, "low": 1, "close": 1,
                           "volume": 1}, index=[ts])
        sig = s.check_entry_at(df, pd.DataFrame(), ts, Regime.TREND)
        assert sig is None

    def test_sl_short(self):
        s = UsMomentumSetupV331()
        sl = s.get_sl(13000, "SHORT", {"atr15_at_entry": 50})
        # max(40, 75) = 75 + 3.5 = 78.5; SHORT → entry+78.5
        assert sl == 13000 + 78.5

    def test_sl_long(self):
        s = UsMomentumSetupV331()
        sl = s.get_sl(13000, "LONG", {"atr15_at_entry": 10})
        # max(40, 15) = 40 + 3.5 = 43.5
        assert sl == 13000 - 43.5

    def test_tp_min_rrr_2(self):
        s = UsMomentumSetupV331()
        sl = 13000 - 43.5
        tp = s.get_tp(13000, sl, "LONG")
        assert tp - 13000 == pytest.approx(2 * 43.5)

    def test_tp_uses_measured_move_when_larger(self):
        s = UsMomentumSetupV331()
        sl = 13000 - 43.5
        tp = s.get_tp(13000, sl, "LONG", measured_move_pts=120)
        assert tp - 13000 == pytest.approx(120)


# ============================================================
# DST entry window (delegated to get_entry_window)
# ============================================================

class TestDSTWindow:
    def test_winter_window(self):
        from src.strategy.setups.us_momentum_v331 import get_entry_window
        s, e = get_entry_window(dt.date(2026, 1, 15))
        assert (s, e) == (dt.time(15, 20), dt.time(16, 30))

    def test_us_spring_gap(self):
        from src.strategy.setups.us_momentum_v331 import get_entry_window
        s, e = get_entry_window(dt.date(2026, 3, 15))
        assert (s, e) == (dt.time(14, 20), dt.time(15, 30))

    def test_us_autumn_gap(self):
        from src.strategy.setups.us_momentum_v331 import get_entry_window
        s, e = get_entry_window(dt.date(2026, 10, 27))
        assert (s, e) == (dt.time(14, 20), dt.time(15, 30))

    def test_summer_default(self):
        from src.strategy.setups.us_momentum_v331 import get_entry_window
        s, e = get_entry_window(dt.date(2026, 6, 15))
        assert (s, e) == (dt.time(15, 20), dt.time(16, 30))
