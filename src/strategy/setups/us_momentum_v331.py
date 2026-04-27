"""US-Momentum v3.3.1 — regime-aware NY Open Continuation.

Spec: Strategy v3.3.1 §2.4 + Pavel hybrid plan + adversarial 9-kol design.

Filter sets per regime (defaults pre-ablation):
  TREND: F1 + F2 + F3 + F4
  CALM:  F1 + F3 + F4 + F5_CALM    (F2 pre-US trend skipped — calm = no clear pre-trend)
  CRASH: F1 MANDATORY + F2 MANDATORY + F3 + F4

Filtry:
  F1 Daily Bias  — same as ORB-DAX (3 booleans all-aligned)
  F2 Pre-US trend — HH/LL series on 15m, 14:00-15:25 CET (DST-aware)
  F3 SP500 corr   — Dukascopy USA500IDXUSD proxy in 15:15-15:20 CET window
  F4 Yest H/L     — current close not breached yesterday's high (LONG) / low (SHORT)
  F5_CALM (a)     — MACD 3-10 histogram (Raschke 3/10): MACD line > signal line (UP)
                    confirms momentum without strong trend; default candidate
                    pre-Exp #12 winner.

Time window entry (DST-aware via rules_engine.get_nyse_open_cet):
  Standard: 15:20-16:30 CET (10 min before NYSE open + 60 min after)
  US-EU DST gap: 14:20-15:30 CET

Spec §2.4.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import pandas as pd

from src.strategy.indicators import atr, ema
from src.strategy.regime import Regime
from src.risk.rules_engine import get_nyse_open_cet
from .base_setup import BaseSetup, Signal
from .us_momentum import (
    pre_us_trend, yesterday_extremes, measured_move_target,
    correlation_proxy_pass, get_entry_window, _to_cet, _aggregate_15m,
    SL_MIN_POINTS, SL_ATR_MULT, SLIPPAGE_AND_SPREAD, RRR_MIN,
)
from .orb_dax import daily_bias

# F5_CALM default — MACD 3-10 (Raschke 3/10)
MACD_FAST = 3
MACD_SLOW = 10
MACD_SIGNAL = 3  # short signal smoothing for fast histogram


def macd_3_10_histogram(close: pd.Series) -> pd.Series:
    """MACD(3, 10, 3) histogram = (MACD line − Signal line). Raschke 3/10."""
    fast = ema(close, MACD_FAST)
    slow = ema(close, MACD_SLOW)
    macd_line = fast - slow
    signal = ema(macd_line.dropna(), MACD_SIGNAL).reindex(close.index)
    return macd_line - signal


def f5_calm_macd_aligned(close: pd.Series, direction: str) -> bool:
    """F5a CALM: MACD 3-10 histogram positive for LONG / negative for SHORT.

    Raschke logic — fast momentum agreement during ranging regime.
    """
    hist = macd_3_10_histogram(close).dropna()
    if hist.empty:
        return False
    last = float(hist.iloc[-1])
    if direction == "LONG":
        return last > 0
    return last < 0


REGIME_FILTERS: dict[Regime, set] = {
    Regime.TREND:     {"F1", "F2", "F3", "F4"},
    Regime.CALM:      {"F1", "F3", "F4", "F5_CALM"},  # F2 skipped, F5_CALM placeholder
    Regime.CRASH:     {"F1", "F2", "F3", "F4"},        # F1+F2 both mandatory
    Regime.UNDEFINED: set(),
}


class UsMomentumSetupV331(BaseSetup):
    name = "us_momentum_v331"
    setup_type = "A"

    def __init__(self):
        pass

    def check_entry(self, market_data) -> Optional[Signal]:
        raise NotImplementedError("Use check_entry_at(...)")

    def get_sl(self, entry: float, direction: str, market_data=None) -> float:
        a15 = (market_data or {}).get("atr15_at_entry") if isinstance(market_data, dict) else None
        sl_raw = max(SL_MIN_POINTS, SL_ATR_MULT * (a15 or 0))
        offset = sl_raw + SLIPPAGE_AND_SPREAD
        return entry - offset if direction == "LONG" else entry + offset

    def get_tp(self, entry: float, sl: float, direction: str,
               measured_move_pts: Optional[float] = None) -> float:
        risk = abs(entry - sl)
        rrr_target_pts = max(RRR_MIN * risk, measured_move_pts or 0)
        return entry + rrr_target_pts if direction == "LONG" else entry - rrr_target_pts

    def check_entry_at(self, df_5m: pd.DataFrame, daily_df: pd.DataFrame,
                       ts: pd.Timestamp, regime: Regime, *,
                       sp500_5m: Optional[pd.DataFrame] = None,
                       skip_filters: Optional[set] = None,
                       f5_override=None) -> Optional[Signal]:
        skip = skip_filters or set()
        if regime == Regime.UNDEFINED:
            return None
        active_filters = REGIME_FILTERS[regime]
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

        # F2 Pre-US trend (only in active set + not skipped)
        trend = None
        if "F2" in active_filters and "F2" not in skip:
            trend = pre_us_trend(df_5m, today)
            if trend is None:
                return None
            if bias_known and bull and trend != "UP":
                return None
            if bias_known and bear and trend != "DOWN":
                return None

        if bias_known:
            direction = "LONG" if bull else "SHORT"
        elif trend is not None:
            direction = "LONG" if trend == "UP" else "SHORT"
        else:
            direction = None  # decided by breakout bar below

        # Breakout bar at NYSE open (5m bar closing at NYSE open)
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

        filters_met = 1 if bias_known else 0
        filters_total = len(active_filters)
        if "F2" in active_filters and "F2" not in skip:
            filters_met += 1

        # F3 SP500 correlation
        if "F3" in active_filters and "F3" not in skip:
            f3 = correlation_proxy_pass(sp500_5m, ts, direction)
            if f3 is False:
                return None
            if f3 is True:
                filters_met += 1
            # f3 is None → fallback pass (don't count toward met)

        # F4 Yesterday H/L runway
        if "F4" in active_filters and "F4" not in skip:
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

        # F5_CALM — default MACD 3-10 alignment, or override
        if "F5_CALM" in active_filters and "F5_CALM" not in skip:
            history_5m_close = df_5m.loc[:ts, "close"]
            if len(history_5m_close) < MACD_SLOW + MACD_SIGNAL + 5:
                return None
            if f5_override is not None:
                ok = f5_override(df_5m.loc[:ts], direction)
            else:
                ok = f5_calm_macd_aligned(history_5m_close, direction)
            if not ok:
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
            setup_name=f"{self.name}_{regime.value.lower()}",
            direction=direction,
            entry=entry, sl=sl, tp=tp,
            lots=0.0, risk_usd=0.0,
            confidence=filters_met / max(filters_total, 1),
            filters_met=filters_met,
            filters_total=filters_total,
        )
