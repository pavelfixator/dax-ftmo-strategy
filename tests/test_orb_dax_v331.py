"""Tests pro src.strategy.setups.orb_dax_v331 — regime-aware filtering."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.regime import Regime
from src.strategy.setups.orb_dax_v331 import (
    OrbDaxSetupV331, REGIME_FILTERS,
    f5_crash_range_expansion, F5A_RANGE_EXPANSION_MULT,
)


def _bar(ts_cet_str: str, o, h, l, c, v):
    ts = pd.Timestamp(ts_cet_str, tz="Europe/Berlin").tz_convert("UTC")
    return ts, dict(open=o, high=h, low=l, close=c, volume=v)


def _build(rows):
    idx, data = [], []
    for ts_str, o, h, l, c, v in rows:
        ts, b = _bar(ts_str, o, h, l, c, v)
        idx.append(ts); data.append(b)
    return pd.DataFrame(data, index=pd.DatetimeIndex(idx, tz="UTC"))


def _daily(n_days=25, base=13000.0, bull=True):
    rng = np.random.default_rng(0)
    end = dt.date(2020, 1, 12)
    idx = [end - dt.timedelta(days=i) for i in range(n_days)][::-1]
    closes = base + np.arange(n_days) * (5 if bull else -5) + rng.standard_normal(n_days) * 2
    opens = closes + (-5 if bull else 5)
    return pd.DataFrame({
        "open": opens,
        "high": np.maximum(opens, closes) + 3,
        "low":  np.minimum(opens, closes) - 3,
        "close": closes,
        "volume": rng.uniform(1000, 2000, n_days),
    }, index=pd.to_datetime(idx))


def _full_session(volume_high=True, range_expansion=False):
    # Warmup 14 bars pre-ORB so ATR(14) is computable at 09:15
    rng = np.random.default_rng(7)
    bars = []
    for i in range(14):
        h = 7 + i // 12
        m = (i % 12) * 5
        ts_str = f"2020-01-13 {h:02d}:{m:02d}"
        c = 13000 + rng.standard_normal() * 2
        bars.append((ts_str, c - 1, c + 3, c - 3, c, 100))
    # ORB 09:00-09:15
    bars += [
        ("2020-01-13 09:00", 13000, 13010, 12995, 13005, 100),
        ("2020-01-13 09:05", 13005, 13020, 13000, 13015, 100),
        ("2020-01-13 09:10", 13015, 13025, 13010, 13020, 100),
    ]
    # 09:15 entry candidate
    if range_expansion:
        bars.append(("2020-01-13 09:15", 13020, 13150, 12950, 13030,
                     200 if volume_high else 80))
    else:
        # Tight range bar — must be < 2× ATR (warmup ATR ~6, so range ≤ 11 to block F5)
        bars.append(("2020-01-13 09:15", 13020, 13027, 13018,
                     13030, 200 if volume_high else 80))
    return _build(bars)


# ============================================================
# Regime filter sets per spec
# ============================================================

class TestFilterSets:
    """v3.3.2.1: ORB-DAX active ONLY in CALM with drop_F3 (F1+F2+F4)."""

    def test_trend_disabled(self):
        assert REGIME_FILTERS[Regime.TREND] == set()

    def test_calm_drop_f3(self):
        assert REGIME_FILTERS[Regime.CALM] == {"F1", "F2", "F4"}

    def test_crash_disabled(self):
        assert REGIME_FILTERS[Regime.CRASH] == set()

    def test_undefined_empty(self):
        assert REGIME_FILTERS[Regime.UNDEFINED] == set()


# ============================================================
# F5_CRASH range expansion
# ============================================================

class TestF5RangeExpansion:
    def test_large_range_passes(self):
        bar = pd.Series({"high": 13150, "low": 12950})
        assert f5_crash_range_expansion(bar, atr5=50) is True
        # |H-L| = 200 > 2 × 50 = 100

    def test_small_range_blocks(self):
        bar = pd.Series({"high": 13020, "low": 12990})
        assert f5_crash_range_expansion(bar, atr5=50) is False
        # |H-L| = 30 < 100

    def test_zero_atr_blocks(self):
        bar = pd.Series({"high": 13050, "low": 12950})
        assert f5_crash_range_expansion(bar, atr5=0) is False

    def test_none_atr_blocks(self):
        bar = pd.Series({"high": 13050, "low": 12950})
        assert f5_crash_range_expansion(bar, atr5=None) is False


# ============================================================
# Entry decisions per regime
# ============================================================

class TestEntryByRegime:
    def test_undefined_never_signals(self):
        s = OrbDaxSetupV331()
        df = _full_session(volume_high=True)
        daily = _daily(bull=True)
        ts = df.index[-1]
        assert s.check_entry_at(df, daily, ts, Regime.UNDEFINED) is None

    def test_trend_returns_none_disabled(self):
        s = OrbDaxSetupV331()
        df = _full_session(volume_high=True)
        daily = _daily(bull=True)
        ts = df.index[-1]
        # v3.3.2.1: TREND disabled regardless of bar quality
        assert s.check_entry_at(df, daily, ts, Regime.TREND) is None

    def test_crash_returns_none_disabled(self):
        s = OrbDaxSetupV331()
        df = _full_session(range_expansion=True)
        daily = _daily(bull=True)
        ts = df.index[-1]
        # v3.3.2.1: CRASH disabled
        assert s.check_entry_at(df, daily, ts, Regime.CRASH) is None

    def test_calm_drop_f3_passes_without_volume_check(self):
        s = OrbDaxSetupV331()
        # Volume LOW — old F3 would block, v3.3.2.1 doesn't check
        df = _full_session(volume_high=False)
        daily = _daily(bull=True)
        ts = df.index[-1]
        sig = s.check_entry_at(df, daily, ts, Regime.CALM)
        assert sig is not None
        assert sig.direction == "LONG"
        assert sig.filters_total == 3  # F1+F2+F4
        assert "calm" in sig.setup_name

    def test_calm_full_filters_pass(self):
        s = OrbDaxSetupV331()
        df = _full_session(volume_high=True)
        daily = _daily(bull=True)
        ts = df.index[-1]
        sig = s.check_entry_at(df, daily, ts, Regime.CALM)
        assert sig is not None
        assert "calm" in sig.setup_name


class TestSLTPLogic:
    def test_sl_min_when_atr_low(self):
        s = OrbDaxSetupV331()
        sl = s.get_sl(13000, "LONG", {"atr5_at_entry": 5.0})
        # max(35, 7.5) = 35 + 3.5 = 38.5
        assert sl == 13000 - 38.5

    def test_tp_uses_orb_range(self):
        s = OrbDaxSetupV331()
        tp = s.get_tp(13030, 13000, "LONG", orb_range=30)
        # 2 × 30 = 60 → 13090
        assert tp == 13030 + 60

    def test_tp_fallback_rrr(self):
        s = OrbDaxSetupV331()
        tp = s.get_tp(13030, 13000, "LONG")
        # risk 30 → tp 30 + 60 = 13090
        assert tp == 13090
