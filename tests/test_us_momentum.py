"""Tests pro src.strategy.setups.us_momentum — DST handling kritický."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.setups.us_momentum import (
    UsMomentumSetup, get_entry_window, pre_us_trend,
    yesterday_extremes, measured_move_target, correlation_proxy_pass,
    SL_MIN_POINTS, SLIPPAGE_AND_SPREAD,
)


class TestEntryWindowDST:
    def test_winter_default_window(self):
        s, e = get_entry_window(dt.date(2026, 1, 15))
        assert s == dt.time(15, 20)
        assert e == dt.time(16, 30)

    def test_us_spring_gap_window(self):
        # 8.-28. 3. 2026 — US in DST, EU not → NYSE 14:30 CET
        s, e = get_entry_window(dt.date(2026, 3, 15))
        assert s == dt.time(14, 20)
        assert e == dt.time(15, 30)

    def test_summer_default_window(self):
        # 29. 3. - 24. 10. 2026 — both DST
        s, e = get_entry_window(dt.date(2026, 6, 15))
        assert s == dt.time(15, 20)
        assert e == dt.time(16, 30)

    def test_us_autumn_gap_window(self):
        s, e = get_entry_window(dt.date(2026, 10, 27))
        assert s == dt.time(14, 20)
        assert e == dt.time(15, 30)


class TestPreUsTrend:
    def _build_5m(self, today: dt.date, slope: float, n: int = 30):
        """Build 5m bars from 14:00 CET to 15:30 CET with linear slope."""
        from zoneinfo import ZoneInfo
        cet = ZoneInfo("Europe/Berlin")
        start_cet = pd.Timestamp(dt.datetime.combine(today, dt.time(14, 0)), tz=cet)
        idx = pd.DatetimeIndex([(start_cet + pd.Timedelta(minutes=5 * i)).tz_convert("UTC")
                                  for i in range(n)])
        base = 13000.0
        close = base + np.arange(n) * slope
        return pd.DataFrame({
            "open": close - 1, "high": close + 2, "low": close - 2,
            "close": close, "volume": 100.0,
        }, index=idx)

    def test_uptrend_detected(self):
        d = dt.date(2026, 1, 13)  # winter, NYSE 15:30 CET
        df = self._build_5m(d, slope=2.0, n=30)
        assert pre_us_trend(df, d) == "UP"

    def test_downtrend_detected(self):
        d = dt.date(2026, 1, 13)
        df = self._build_5m(d, slope=-2.0, n=30)
        assert pre_us_trend(df, d) == "DOWN"

    def test_sideways_returns_none(self):
        d = dt.date(2026, 1, 13)
        df = self._build_5m(d, slope=0.0, n=30)
        assert pre_us_trend(df, d) is None


class TestSLTPLogic:
    def test_sl_uses_min_when_atr_low(self):
        s = UsMomentumSetup(filters="B")
        sl = s.get_sl(13000, "LONG", {"atr15_at_entry": 10.0})
        # max(40, 15) = 40 + 3.5 = 43.5
        assert sl == 13000 - (SL_MIN_POINTS + SLIPPAGE_AND_SPREAD)

    def test_sl_uses_atr_when_high(self):
        s = UsMomentumSetup(filters="B")
        sl = s.get_sl(13000, "LONG", {"atr15_at_entry": 50.0})
        # max(40, 75) = 75 → 78.5
        assert sl == 13000 - (75 + SLIPPAGE_AND_SPREAD)

    def test_tp_min_rrr_2(self):
        s = UsMomentumSetup(filters="B")
        sl = 13000 - 43.5
        tp = s.get_tp(13000, sl, "LONG", measured_move_pts=10)  # mm too small
        assert tp - 13000 == pytest.approx(2 * 43.5)

    def test_tp_uses_measured_move_when_larger(self):
        s = UsMomentumSetup(filters="B")
        sl = 13000 - 43.5
        tp = s.get_tp(13000, sl, "LONG", measured_move_pts=120)
        assert tp - 13000 == pytest.approx(120)


class TestCorrelationProxy:
    def test_missing_returns_none(self):
        ts = pd.Timestamp("2026-04-15 13:30", tz="Europe/Berlin").tz_convert("UTC")
        assert correlation_proxy_pass(None, ts, "LONG") is None

    def test_aligned_long(self):
        from zoneinfo import ZoneInfo
        cet = ZoneInfo("Europe/Berlin")
        idx = pd.DatetimeIndex([
            pd.Timestamp(f"2026-04-15 15:{m}", tz=cet).tz_convert("UTC")
            for m in [15, 20]
        ])
        df = pd.DataFrame({"open": [4500.0, 4502.0], "high": [4503.0, 4506.0],
                           "low": [4499.0, 4501.0], "close": [4502.0, 4505.0],
                           "volume": [10.0, 12.0]}, index=idx)
        ts = pd.Timestamp("2026-04-15 15:30", tz="Europe/Berlin").tz_convert("UTC")
        assert correlation_proxy_pass(df, ts, "LONG") is True
        assert correlation_proxy_pass(df, ts, "SHORT") is False


def test_yesterday_extremes_from_daily():
    daily = pd.DataFrame({
        "open": [13000, 13050],
        "high": [13100, 13150],
        "low": [12950, 13000],
        "close": [13050, 13120],
        "volume": [1000, 1100],
    }, index=pd.to_datetime(["2026-01-12", "2026-01-13"]))
    yh = yesterday_extremes(daily, dt.date(2026, 1, 14))
    assert yh == (13150.0, 13000.0)


def test_measured_move_returns_swing_x2():
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")
    d = dt.date(2026, 1, 13)
    times = [dt.time(14, 0), dt.time(14, 30), dt.time(14, 55),
             dt.time(15, 0), dt.time(15, 5), dt.time(15, 10),
             dt.time(15, 15), dt.time(15, 25)]
    idx = pd.DatetimeIndex([
        pd.Timestamp(dt.datetime.combine(d, t), tz=cet).tz_convert("UTC")
        for t in times
    ])
    df = pd.DataFrame({
        "open":   [13000, 13010, 13050, 13060, 13070, 13080, 13085, 13090],
        "high":   [13020, 13040, 13070, 13080, 13090, 13100, 13110, 13105],
        "low":    [12990, 13000, 13030, 13050, 13060, 13070, 13080, 13085],
        "close":  [13010, 13030, 13060, 13070, 13080, 13095, 13100, 13095],
        "volume": [100] * 8,
    }, index=idx)
    mm = measured_move_target(df, d, "LONG")
    # 14:00 bar is OUTSIDE pre-US window [14:05, 15:25] → its low=12990 excluded.
    # In-window high=13110, low=13000 → range 110 → ×2 = 220.
    assert mm == pytest.approx(220.0)
