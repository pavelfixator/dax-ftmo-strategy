"""Tests pro backtest.engine."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.data_feed import BarFeed
from src.strategy.setups.base_setup import Signal
from src.strategy.setups.orb_dax import OrbDaxSetup
from backtest.engine import (
    run_backtest, _pnl_usd, BacktestResult, OpenPosition, _exit_check,
    _force_close_due,
)


def _empty_feed() -> BarFeed:
    idx = pd.date_range("2020-01-13 00:00", "2020-01-13 23:55", freq="5min", tz="UTC")
    rng = np.random.default_rng(0)
    n = len(idx)
    close = 13000 + rng.standard_normal(n).cumsum() * 1.0
    df = pd.DataFrame({
        "open": close - 0.5, "high": close + 1, "low": close - 1,
        "close": close, "volume": rng.uniform(50, 100, n),
    }, index=idx)
    return BarFeed(df)


def test_pnl_long_positive():
    assert _pnl_usd("LONG", 13000, 13050, 1.0, 1.08) == pytest.approx(54.0)


def test_pnl_short_positive():
    assert _pnl_usd("SHORT", 13050, 13000, 0.5, 1.08) == pytest.approx(27.0)


def test_pnl_long_negative():
    assert _pnl_usd("LONG", 13050, 13000, 1.0, 1.08) == pytest.approx(-54.0)


def test_exit_check_long_sl_hit():
    pos = OpenPosition(setup="x", direction="LONG", entry_ts=pd.Timestamp.now(tz="UTC"),
                        entry=13000, sl=12990, tp=13020, lots=1.0, risk_usd=100,
                        filters_met=3, filters_total=3)
    bar = pd.Series({"open": 12995, "high": 13000, "low": 12985, "close": 12992})
    ex = _exit_check(pos, bar, pd.Timestamp.now(tz="UTC"), 1.08)
    assert ex == (12990, "sl")


def test_exit_check_long_tp1_hit():
    pos = OpenPosition(setup="x", direction="LONG", entry_ts=pd.Timestamp.now(tz="UTC"),
                        entry=13000, sl=12990, tp=13020, lots=1.0, risk_usd=100,
                        filters_met=3, filters_total=3)
    bar = pd.Series({"open": 13005, "high": 13025, "low": 13003, "close": 13020})
    ex = _exit_check(pos, bar, pd.Timestamp.now(tz="UTC"), 1.08)
    assert ex == (13020, "tp1")


def test_exit_check_short_sl_hit():
    pos = OpenPosition(setup="x", direction="SHORT", entry_ts=pd.Timestamp.now(tz="UTC"),
                        entry=13000, sl=13010, tp=12980, lots=1.0, risk_usd=100,
                        filters_met=3, filters_total=3)
    bar = pd.Series({"open": 13005, "high": 13015, "low": 13003, "close": 13008})
    ex = _exit_check(pos, bar, pd.Timestamp.now(tz="UTC"), 1.08)
    assert ex == (13010, "sl")


def test_force_close_after_2055_mon_thu():
    ts_cet = pd.Timestamp("2020-01-13 21:00", tz="Europe/Berlin")
    pos = OpenPosition(setup="x", direction="LONG", entry_ts=pd.Timestamp.now(tz="UTC"),
                        entry=13000, sl=12990, tp=13020, lots=1.0, risk_usd=100,
                        filters_met=3, filters_total=3)
    assert _force_close_due(pos, ts_cet)


def test_force_close_before_2055_no():
    ts_cet = pd.Timestamp("2020-01-13 20:30", tz="Europe/Berlin")
    pos = OpenPosition(setup="x", direction="LONG", entry_ts=pd.Timestamp.now(tz="UTC"),
                        entry=13000, sl=12990, tp=13020, lots=1.0, risk_usd=100,
                        filters_met=3, filters_total=3)
    assert not _force_close_due(pos, ts_cet)


def test_run_backtest_no_trades_on_random_data():
    """Random small-amplitude noise should not trigger any setup signals."""
    feed = _empty_feed()
    res = run_backtest(feed)
    # Setups need: ORB > 10pt range, volume spike, daily bias from history (we have only 1 day) → no entries.
    assert res.n_trades == 0


def test_backtest_result_stats_on_empty():
    res = BacktestResult()
    assert res.stats() == {"n": 0}


def test_run_backtest_no_invariant_violations_random():
    feed = _empty_feed()
    res = run_backtest(feed)
    assert res.invariant_violations == []
