"""Tests pro src.strategy.data_feed."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.data_feed import BarFeed, load, CET, UTC


@pytest.fixture
def synth_parquet(tmp_path):
    rng = np.random.default_rng(7)
    # 3 trading days × 24h × 12 bars/h = 864 bars (5m freq)
    idx = pd.date_range("2020-01-13 00:00", "2020-01-15 23:55", freq="5min", tz="UTC")
    n = len(idx)
    close = 13000 + rng.standard_normal(n).cumsum() * 3
    df = pd.DataFrame({
        "open": close + rng.uniform(-2, 2, n),
        "high": close + rng.uniform(0, 5, n),
        "low": close - rng.uniform(0, 5, n),
        "close": close,
        "volume": rng.uniform(50, 200, n),
    }, index=idx)
    df.index.name = "ts_utc"
    p = tmp_path / "synth.parquet"
    df.to_parquet(p)
    return p


def test_load_returns_utc_index(synth_parquet):
    df = load(synth_parquet)
    assert str(df.index.tz) == "UTC"
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_barfeed_length_and_iter(synth_parquet):
    feed = BarFeed.from_parquet(synth_parquet)
    assert len(feed) == 864
    bars = list(feed.iter_bars())
    assert len(bars) == 864
    assert bars[0].ts_utc.hour == 0
    assert hasattr(bars[0], "ts_cet")
    # CET in Jan 2020 = UTC+1
    assert bars[0].ts_cet.hour == 1


def test_barfeed_range_naive_assumed_cet(synth_parquet):
    feed = BarFeed.from_parquet(synth_parquet)
    # 2020-01-13 09:00 CET = 08:00 UTC
    sub = feed.range("2020-01-13 09:00", "2020-01-13 10:00")
    assert sub.first == pd.Timestamp("2020-01-13 08:00", tz="UTC")
    assert sub.last < pd.Timestamp("2020-01-13 09:00", tz="UTC")
    assert len(sub) == 12  # 12 × 5m = 1h


def test_barfeed_range_tz_aware_passthrough(synth_parquet):
    feed = BarFeed.from_parquet(synth_parquet)
    s = pd.Timestamp("2020-01-14 14:00", tz="UTC")
    e = pd.Timestamp("2020-01-14 15:00", tz="UTC")
    sub = feed.range(s, e)
    assert sub.first == s
    assert len(sub) == 12


def test_trading_session_window(synth_parquet):
    feed = BarFeed.from_parquet(synth_parquet)
    sess = feed.trading_session("2020-01-13",
                                 open_time=dt.time(9, 0),
                                 close_time=dt.time(17, 30))
    # 8.5 h × 12 bars/h = 102 bars
    assert len(sess) == 102
    cet_first = sess.first.tz_convert(CET)
    assert cet_first.hour == 9 and cet_first.minute == 0


def test_load_rejects_missing_columns(tmp_path):
    bad = pd.DataFrame({"x": [1, 2, 3]},
                       index=pd.date_range("2020", periods=3, freq="5min", tz="UTC"))
    p = tmp_path / "bad.parquet"
    bad.to_parquet(p)
    with pytest.raises(ValueError, match="missing columns"):
        load(p)


def test_load_rejects_empty(tmp_path):
    empty = pd.DataFrame(columns=["open", "high", "low", "close", "volume"],
                         index=pd.DatetimeIndex([], tz="UTC"))
    p = tmp_path / "empty.parquet"
    empty.to_parquet(p)
    with pytest.raises(ValueError, match="empty parquet"):
        load(p)


def test_dst_spring_forward_handled():
    # 2020-03-29 is EU DST switch (CET → CEST). 02:00 CET → 03:00 CEST = 01:00 UTC.
    # We synthesize 5-min bars across this boundary in UTC index.
    idx = pd.date_range("2020-03-29 00:00", "2020-03-29 04:00", freq="5min", tz="UTC")
    df = pd.DataFrame({
        "open": [100.0] * len(idx), "high": [101.0] * len(idx),
        "low": [99.0] * len(idx), "close": [100.0] * len(idx),
        "volume": [10.0] * len(idx),
    }, index=idx)
    feed = BarFeed(df)
    # Naive 2020-03-29 02:30 CET — pre-DST clock didn't exist; pandas localize
    # would normally raise, but our coerce uses tz_localize(CET) which falls back
    # to nonexistent="raise" by default. Ensure we still iterate and don't crash
    # on the boundary in UTC space:
    bars = list(feed.iter_bars())
    assert len(bars) > 0
    cet_hours = [b.ts_cet.hour for b in bars]
    assert 1 in cet_hours  # pre-DST 01:xx CET
    assert 3 in cet_hours  # post-DST 03:xx CEST (skipped 02:xx)
