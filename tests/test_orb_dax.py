"""Tests pro src.strategy.setups.orb_dax."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.setups.orb_dax import (
    OrbDaxSetup, compute_orb, daily_bias, aggregate_daily,
    SL_MIN_POINTS, SLIPPAGE_AND_SPREAD_POINTS, RRR_TARGET,
)


def _bar(ts_cet_str: str, o, h, l, c, v):
    """Helper to build a single bar with CET-aware index."""
    ts = pd.Timestamp(ts_cet_str, tz="Europe/Berlin").tz_convert("UTC")
    return ts, dict(open=o, high=h, low=l, close=c, volume=v)


def _build_session(rows):
    idx = []
    data = []
    for ts_str, o, h, l, c, v in rows:
        ts, b = _bar(ts_str, o, h, l, c, v)
        idx.append(ts)
        data.append(b)
    return pd.DataFrame(data, index=pd.DatetimeIndex(idx, tz="UTC"))


def _build_daily_history(n_days: int = 25, base: float = 13000.0,
                        bull: bool = True) -> pd.DataFrame:
    """Synthesize n_days × D1 OHLC ending the day before 2020-01-13."""
    end = dt.date(2020, 1, 12)
    idx = [end - dt.timedelta(days=i) for i in range(n_days)][::-1]
    rng = np.random.default_rng(0)
    closes = base + np.arange(n_days) * (5.0 if bull else -5.0) + rng.standard_normal(n_days) * 2
    # Bull: open below close (green candle); bear: open above close (red candle)
    opens = closes + (-5.0 if bull else 5.0)
    df = pd.DataFrame({
        "open": opens,
        "high": np.maximum(opens, closes) + 3,
        "low": np.minimum(opens, closes) - 3,
        "close": closes,
        "volume": rng.uniform(1000, 2000, n_days),
    }, index=pd.to_datetime(idx))
    return df


class TestOrb:
    def test_orb_three_bars_5min(self):
        rows = [
            ("2020-01-13 09:00", 13000, 13010, 12995, 13005, 100),
            ("2020-01-13 09:05", 13005, 13020, 13000, 13015, 120),
            ("2020-01-13 09:10", 13015, 13025, 13010, 13020, 110),
        ]
        df = _build_session(rows)
        orb = compute_orb(df)
        assert orb is not None
        assert orb.orb_high == 13025
        assert orb.orb_low == 12995
        assert orb.orb_range == 30
        assert orb.orb_avg_volume == 110

    def test_orb_below_min_range_rejected(self):
        # 5-point range < 10 min
        rows = [
            ("2020-01-13 09:00", 13000, 13002, 12999, 13001, 100),
            ("2020-01-13 09:05", 13001, 13003, 12998, 13002, 100),
            ("2020-01-13 09:10", 13002, 13004, 12997, 13003, 100),
        ]
        df = _build_session(rows)
        assert compute_orb(df) is None

    def test_orb_insufficient_bars(self):
        rows = [("2020-01-13 09:00", 13000, 13010, 12995, 13005, 100)]
        df = _build_session(rows)
        assert compute_orb(df) is None


class TestDailyBias:
    def test_bull_bias_all_three(self):
        d = _build_daily_history(25, bull=True)
        bull, bear = daily_bias(d, dt.date(2020, 1, 13))
        assert bull and not bear

    def test_bear_bias(self):
        d = _build_daily_history(25, bull=False)
        bull, bear = daily_bias(d, dt.date(2020, 1, 13))
        assert bear and not bull

    def test_insufficient_history(self):
        d = _build_daily_history(5)
        bull, bear = daily_bias(d, dt.date(2020, 1, 13))
        assert not bull and not bear


class TestSLTPLogic:
    def test_sl_uses_min_when_atr_low(self):
        s = OrbDaxSetup(filters="A")
        sl = s.get_sl(13000, "LONG", {"atr5_at_entry": 5.0})
        # 1.5 × 5 = 7.5 < 35 → use 35 + 3.5 = 38.5
        assert sl == 13000 - (SL_MIN_POINTS + SLIPPAGE_AND_SPREAD_POINTS)

    def test_sl_uses_atr_when_high(self):
        s = OrbDaxSetup(filters="A")
        sl = s.get_sl(13000, "LONG", {"atr5_at_entry": 50.0})
        # 1.5 × 50 = 75 > 35 → 75 + 3.5 = 78.5
        assert sl == 13000 - (75 + SLIPPAGE_AND_SPREAD_POINTS)

    def test_sl_short_above_entry(self):
        s = OrbDaxSetup(filters="A")
        sl = s.get_sl(13000, "SHORT", {"atr5_at_entry": 10.0})
        assert sl > 13000

    def test_tp_yields_rrr_2(self):
        s = OrbDaxSetup(filters="A")
        sl = 13000 - 38.5
        tp = s.get_tp(13000, sl, "LONG")
        assert tp - 13000 == pytest.approx(RRR_TARGET * 38.5)


class TestEntryDecision:
    def _full_session(self, breakout: bool, volume_high: bool):
        bars = []
        # ORB 09:00-09:15 (3 bars)
        bars += [
            ("2020-01-13 09:00", 13000, 13010, 12995, 13005, 100),
            ("2020-01-13 09:05", 13005, 13020, 13000, 13015, 100),
            ("2020-01-13 09:10", 13015, 13025, 13010, 13020, 100),
        ]
        # Entry window 09:15+
        c = 13030 if breakout else 13020  # break above ORB high (13025) only if breakout
        v = 200 if volume_high else 80    # need >1.5× avg of 100 = 150
        bars.append(("2020-01-13 09:15", 13020, 13035, 13015, c, v))
        return _build_session(bars)

    def test_long_entry_with_bull_bias_and_breakout(self):
        s = OrbDaxSetup(filters="B")  # use B to skip F4
        df = self._full_session(breakout=True, volume_high=True)
        daily = _build_daily_history(25, bull=True)
        ts = df.index[-1]  # 09:15 bar
        sig = s.check_entry_at(df, daily, ts)
        assert sig is not None
        assert sig.direction == "LONG"
        assert sig.filters_met == 3
        assert sig.filters_total == 3

    def test_no_entry_without_breakout(self):
        s = OrbDaxSetup(filters="B")
        df = self._full_session(breakout=False, volume_high=True)
        daily = _build_daily_history(25, bull=True)
        ts = df.index[-1]
        assert s.check_entry_at(df, daily, ts) is None

    def test_no_entry_without_volume(self):
        s = OrbDaxSetup(filters="B")
        df = self._full_session(breakout=True, volume_high=False)
        daily = _build_daily_history(25, bull=True)
        ts = df.index[-1]
        assert s.check_entry_at(df, daily, ts) is None

    def test_no_entry_outside_window(self):
        s = OrbDaxSetup(filters="B")
        df = self._full_session(breakout=True, volume_high=True)
        # Inject a bar at 10:30 CET (after window) with same close
        ts2 = pd.Timestamp("2020-01-13 10:30", tz="Europe/Berlin").tz_convert("UTC")
        df.loc[ts2] = df.iloc[-1]
        df = df.sort_index()
        daily = _build_daily_history(25, bull=True)
        assert s.check_entry_at(df, daily, ts2) is None

    def test_filters_a_vs_b(self):
        sa = OrbDaxSetup(filters="A")
        sb = OrbDaxSetup(filters="B")
        df = self._full_session(breakout=True, volume_high=True)
        daily = _build_daily_history(25, bull=True)
        ts = df.index[-1]
        sig_a = sa.check_entry_at(df, daily, ts, history_5m=None)
        sig_b = sb.check_entry_at(df, daily, ts)
        # Without history_5m, F4 falls back to pass-but-not-counted; A produces 3/4 confidence
        assert sig_a is not None and sig_a.filters_total == 4 and sig_a.filters_met == 3
        assert sig_b is not None and sig_b.filters_total == 3 and sig_b.filters_met == 3


def test_aggregate_daily_basic():
    rows = [
        ("2020-01-13 09:00", 13000, 13010, 12995, 13005, 100),
        ("2020-01-13 14:00", 13005, 13050, 12990, 13030, 200),
        ("2020-01-14 09:00", 13030, 13045, 13020, 13040, 150),
    ]
    df = _build_session(rows)
    daily = aggregate_daily(df)
    assert len(daily) == 2
    assert daily.loc["2020-01-13", "high"] == 13050
    assert daily.loc["2020-01-13", "low"] == 12990
    assert daily.loc["2020-01-13", "volume"] == 300
