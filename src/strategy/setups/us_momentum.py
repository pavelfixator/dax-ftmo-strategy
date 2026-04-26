"""US-Momentum Setup — NY Open Continuation.

Spec: Strategy v3.2 §Setup 3 + Pavel's hybrid plan 2026-04-26.

Mechanika:
  Trend continuation na US open (15:30 CET standard / 14:30 CET v gap oknech).
  HTF=D1 bias, MTF=15m pre-US, LTF=5m breakout potvrzení.
  DST handling kritický — entry window se posune během 2 přechodových oken.

Filtry A (4):
  F1 Daily Bias = ORB-DAX daily_bias() (yest_close vs EMA20D1, vs yest_open, vs day_before)
  F2 Pre-US trend na 15m (HH/LL serie v 14:00-15:25 CET DST-adjusted)
  F3 US500.cash korelace (15:15-15:20 CET) — Dukascopy USA500IDXUSD proxy.
     Pokud feed missing → F3 fallback "pass" + log; v Iter1/2 acceptable.
  F4 Podklad nepřekročil Yesterday H (long) / Yesterday L (short) — runway

Filtry B (3): F1 + F2 + F3 (chybí F4)

Entry:    market na 5m close potvrzující breakout 15:30 5m high/low (DST-adj).
SL_raw:   max(40 points, 1.5 × ATR(14) 15m at entry)
SL_eff:   SL_raw + 3.5 (1.5 spread + 2.0 slippage)
TP:       Brooks measured move (proxy: 2 × pre-US 14:00-15:25 swing high-low,
          min RRR 1:2). Trailing handled by engine.
Invalidace: 5m close opačným směrem
Time window entry: get_entry_window(date) — DST-aware
"""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

import pandas as pd

from src.strategy.indicators import atr
from src.risk.rules_engine import get_nyse_open_cet
from .base_setup import BaseSetup, Signal
from .orb_dax import daily_bias

PRE_US_WINDOW_END_OFFSET = dt.timedelta(minutes=5)  # 5 min before NYSE open
PRE_US_WINDOW_DURATION_HOURS = 1
ENTRY_WINDOW_AFTER_OPEN = dt.timedelta(minutes=60)  # 60 min after NYSE open
SL_MIN_POINTS = 40.0
SL_ATR_MULT = 1.5
SLIPPAGE_AND_SPREAD = 3.5
RRR_MIN = 2.0
F3_MISSING_FALLBACK = True  # Iter1/2: pass with note if SP500 feed unavailable


def _to_cet(ts: pd.Timestamp) -> pd.Timestamp:
    from zoneinfo import ZoneInfo
    return ts.tz_convert(ZoneInfo("Europe/Berlin"))


def get_entry_window(d: dt.date) -> tuple[dt.time, dt.time]:
    """Returns (start_cet, end_cet) for the US-Momentum entry window.

    Standard: 15:20-16:30 CET. In US-EU DST gap windows: 14:20-15:30 CET.
    Source of truth for NYSE open: rules_engine.get_nyse_open_cet(date).
    """
    nyse_open = get_nyse_open_cet(d)
    # Window starts 10 min before NYSE open, ends 60 min after.
    start_h = nyse_open.hour
    start_m = nyse_open.minute - 10
    if start_m < 0:
        start_h -= 1
        start_m += 60
    start = dt.time(start_h, start_m)
    end_dt = (dt.datetime.combine(d, nyse_open) + dt.timedelta(minutes=60)).time()
    return start, end_dt


def _aggregate_15m(df_5m: pd.DataFrame) -> pd.DataFrame:
    if df_5m.empty:
        return df_5m
    return df_5m.resample("15min", label="right", closed="right").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["close"])


def pre_us_trend(df_5m: pd.DataFrame, today_cet_date: dt.date) -> Optional[str]:
    """Returns 'UP' / 'DOWN' / None based on 15m HH/LL series in pre-US window."""
    nyse_open = get_nyse_open_cet(today_cet_date)
    end = (dt.datetime.combine(today_cet_date, nyse_open)
           - PRE_US_WINDOW_END_OFFSET)
    start = end - dt.timedelta(hours=PRE_US_WINDOW_DURATION_HOURS,
                                minutes=20)  # 14:00-15:25 standard
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")
    start_utc = pd.Timestamp(dt.datetime.combine(today_cet_date, start.time()),
                              tz=cet).tz_convert("UTC")
    end_utc = pd.Timestamp(dt.datetime.combine(today_cet_date, end.time()),
                            tz=cet).tz_convert("UTC")
    window_5m = df_5m[(df_5m.index >= start_utc) & (df_5m.index <= end_utc)]
    if len(window_5m) < 6:
        return None
    bars_15m = _aggregate_15m(window_5m)
    if len(bars_15m) < 3:
        return None
    highs = bars_15m["high"].values
    lows = bars_15m["low"].values
    higher_highs = sum(highs[i] > highs[i - 1] for i in range(1, len(highs)))
    higher_lows = sum(lows[i] > lows[i - 1] for i in range(1, len(lows)))
    lower_highs = sum(highs[i] < highs[i - 1] for i in range(1, len(highs)))
    lower_lows = sum(lows[i] < lows[i - 1] for i in range(1, len(lows)))
    n = len(bars_15m) - 1
    if higher_highs >= 2 * n // 3 and higher_lows >= 2 * n // 3:
        return "UP"
    if lower_highs >= 2 * n // 3 and lower_lows >= 2 * n // 3:
        return "DOWN"
    return None


def yesterday_extremes(daily_df: pd.DataFrame, today_cet_date: dt.date
                       ) -> Optional[tuple[float, float]]:
    prior = daily_df[daily_df.index.date < today_cet_date]
    if prior.empty:
        return None
    yest = prior.iloc[-1]
    return float(yest["high"]), float(yest["low"])


def measured_move_target(df_5m: pd.DataFrame, today_cet_date: dt.date,
                         direction: str) -> Optional[float]:
    """Brooks measured move proxy: 2 × pre-US swing range projected from breakout."""
    nyse_open = get_nyse_open_cet(today_cet_date)
    end = (dt.datetime.combine(today_cet_date, nyse_open)
           - PRE_US_WINDOW_END_OFFSET)
    start = end - dt.timedelta(hours=PRE_US_WINDOW_DURATION_HOURS,
                                minutes=20)
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")
    start_utc = pd.Timestamp(dt.datetime.combine(today_cet_date, start.time()),
                              tz=cet).tz_convert("UTC")
    end_utc = pd.Timestamp(dt.datetime.combine(today_cet_date, end.time()),
                            tz=cet).tz_convert("UTC")
    win = df_5m[(df_5m.index >= start_utc) & (df_5m.index <= end_utc)]
    if win.empty:
        return None
    swing = float(win["high"].max() - win["low"].min())
    return swing * 2.0  # projected magnitude in points


def correlation_proxy_pass(sp500_5m: Optional[pd.DataFrame], ts: pd.Timestamp,
                            direction: str) -> Optional[bool]:
    """F3: SP500 in same direction in window 15:15-15:20 CET (pre-NYSE open).

    Returns True/False if SP500 data available; None if missing (caller decides).
    """
    if sp500_5m is None or sp500_5m.empty:
        return None
    cet_ts = _to_cet(ts)
    window_start = cet_ts.replace(hour=15, minute=15)
    window_end = cet_ts.replace(hour=15, minute=20)
    win = sp500_5m[(sp500_5m.index >= window_start.tz_convert("UTC"))
                   & (sp500_5m.index <= window_end.tz_convert("UTC"))]
    if win.empty:
        return None
    move = float(win["close"].iloc[-1]) - float(win["open"].iloc[0])
    return (direction == "LONG" and move > 0) or (direction == "SHORT" and move < 0)


class UsMomentumSetup(BaseSetup):
    name = "us_momentum"
    setup_type = "A"

    def __init__(self, filters: Literal["A", "B"] = "A"):
        if filters not in ("A", "B"):
            raise ValueError(f"filters must be 'A' or 'B', got {filters}")
        self.filters = filters
        self.setup_type = filters

    def check_entry(self, market_data) -> Optional[Signal]:
        raise NotImplementedError("Use check_entry_at(...)")

    def get_sl(self, entry: float, direction: str, market_data=None) -> float:
        a15 = (market_data or {}).get("atr15_at_entry")
        sl_raw = max(SL_MIN_POINTS, SL_ATR_MULT * (a15 or 0))
        offset = sl_raw + SLIPPAGE_AND_SPREAD
        return entry - offset if direction == "LONG" else entry + offset

    def get_tp(self, entry: float, sl: float, direction: str,
               measured_move_pts: Optional[float] = None) -> float:
        risk = abs(entry - sl)
        rrr_target_pts = max(RRR_MIN * risk, measured_move_pts or 0)
        return entry + rrr_target_pts if direction == "LONG" else entry - rrr_target_pts

    def check_entry_at(self, df_5m: pd.DataFrame, daily_df: pd.DataFrame,
                       ts: pd.Timestamp, *,
                       sp500_5m: Optional[pd.DataFrame] = None,
                       skip_filters: Optional[set] = None) -> Optional[Signal]:
        skip = skip_filters or set()
        if ts not in df_5m.index:
            return None
        cet_ts = _to_cet(ts)
        today = cet_ts.date()
        win_start, win_end = get_entry_window(today)
        if not (win_start <= cet_ts.time() < win_end):
            return None
        # F1 Daily Bias
        if "F1" in skip:
            bull = bear = False
            bias_known = False
        else:
            bull, bear = daily_bias(daily_df, today)
            bias_known = True
            if not (bull or bear):
                return None
        # F2 Pre-US trend (15m HH/LL)
        if "F2" in skip:
            trend = None
        else:
            trend = pre_us_trend(df_5m, today)
            if trend is None:
                return None
            if bias_known and bull and trend != "UP":
                return None
            if bias_known and bear and trend != "DOWN":
                return None
        # Direction
        if bias_known:
            direction = "LONG" if bull else "SHORT"
        elif trend is not None:
            direction = "LONG" if trend == "UP" else "SHORT"
        else:
            # F1+F2 both skipped → use breakout bar direction below
            direction = None
        # 15:30 5m breakout direction (or 14:30 in gap windows)
        nyse_open_t = get_nyse_open_cet(today)
        from zoneinfo import ZoneInfo
        cet = ZoneInfo("Europe/Berlin")
        breakout_ts = pd.Timestamp(dt.datetime.combine(today, nyse_open_t),
                                    tz=cet).tz_convert("UTC")
        if breakout_ts not in df_5m.index:
            return None
        br_bar = df_5m.loc[breakout_ts]
        breakout_long = float(br_bar["close"]) > float(br_bar["open"])
        breakout_short = float(br_bar["close"]) < float(br_bar["open"])
        if direction is None:
            if breakout_long:
                direction = "LONG"
            elif breakout_short:
                direction = "SHORT"
            else:
                return None
        else:
            if direction == "LONG" and not breakout_long:
                return None
            if direction == "SHORT" and not breakout_short:
                return None
        # F3 SP500 correlation
        f3_count = 0
        if "F3" not in skip:
            f3 = correlation_proxy_pass(sp500_5m, ts, direction)
            if f3 is False:
                return None
            if f3 is True:
                f3_count = 1
            # f3 is None → fallback pass (logged)
        # F4 yesterday extremes (only filters="A")
        filters_total = 4 if self.filters == "A" else 3
        filters_met = 2 + f3_count  # F1 + F2 + (F3 if known)
        if self.filters == "A" and "F4" not in skip:
            yh = yesterday_extremes(daily_df, today)
            if yh is None:
                return None
            yest_high, yest_low = yh
            cur_close = float(df_5m.loc[ts, "close"])
            if direction == "LONG" and cur_close >= yest_high:
                return None
            if direction == "SHORT" and cur_close <= yest_low:
                return None
            filters_met += 1
        # ATR(14) on 15m for SL
        bars_15m = _aggregate_15m(df_5m.loc[:ts])
        a15_series = atr(bars_15m, 14).dropna()
        a15 = float(a15_series.iloc[-1]) if not a15_series.empty else None
        entry = float(df_5m.loc[ts, "close"])
        sl = self.get_sl(entry, direction, {"atr15_at_entry": a15})
        mm = measured_move_target(df_5m, today, direction)
        tp = self.get_tp(entry, sl, direction, measured_move_pts=mm)
        return Signal(
            setup_name=self.name, direction=direction,
            entry=entry, sl=sl, tp=tp,
            lots=0.0, risk_usd=0.0,
            confidence=filters_met / filters_total,
            filters_met=filters_met, filters_total=filters_total,
        )
