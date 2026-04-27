# DEPRECATED v3.3.1, see orb_dax_v331.py
"""ORB-DAX Setup — Trend Open Range Breakout (v3.2 — DEPRECATED).

Po v3.3.1 redesign nahrazeno regime-aware variantou v `orb_dax_v331.py`.
Tento modul zůstává pro backward-compat a benchmark Iter2/Iter2b reportů,
ale není používán novým engine post-Sekce 3 integration.

Spec: Strategy v3.2 §Setup 1 + Pavel's hybrid plan 2026-04-26.

Mechanika:
  ORB15 = high/low prvních 3 × 5m barů od 09:00 CET (= 08:00 UTC zimní /
  07:00 UTC letní). Time window pro entry: 09:15-10:00 CET (8 × 5m barů).

Filtry A (4):
  F1 Daily Bias (3 booleans, all-true pro daný směr):
      yest_close > EMA20(D1)        (long) / <  (short)
      yest_close > yest_open        (bullish day) / < (bearish)
      yest_close > day_before_close (consecutive trend)
  F2 ORB15 valid: high > low strict, range >= 10 points (sanity)
  F3 Volume na breakout baru > 1.5× avg volume prvních 3 ORB barů
  F4 ATR(14) 5m at 09:00-09:15 > 0.7× rolling 20-day median ATR

Filtry B (3): F1 + F2 + F3 (chybí F4) — pro lower-confidence regimy.

Entry: 5m close baru breakout → market entry next bar 1 tick nad/pod ORB.
SL_raw = max(35 points, 1.5 × ATR(14) 5m at entry)
SL_eff = SL_raw + 1.5 (spread) + 2.0 (slippage) = SL_raw + 3.5
TP1   = 2 × ORB15 height (RRR 1:2), scale-out 50 %
TP2   = trailing po TP1 (BE+5, trail 5m swing low/high) — řeší engine
Invalidace: 5m close zpět uvnitř ORB15 → immediate close.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from src.strategy.indicators import ema, atr
from .base_setup import BaseSetup, Signal

CET = dt.timezone(dt.timedelta(hours=1))  # session-local; DST handled by zoneinfo elsewhere
ORB_BARS = 3  # 3 × 5m = 15min
ORB_RANGE_MIN_POINTS = 10.0
ENTRY_WINDOW_START = dt.time(9, 15)
ENTRY_WINDOW_END = dt.time(10, 0)
ORB_WINDOW_START = dt.time(9, 0)
ORB_WINDOW_END = dt.time(9, 15)
SL_MIN_POINTS = 35.0
SL_ATR_MULT = 1.5
SLIPPAGE_AND_SPREAD_POINTS = 3.5  # 1.5 spread + 2.0 slippage
RRR_TARGET = 2.0
VOLUME_THRESHOLD = 1.5
F4_ATR_THRESHOLD_RATIO = 0.7
F4_MEDIAN_LOOKBACK_DAYS = 20


@dataclass(frozen=True)
class OrbContext:
    orb_high: float
    orb_low: float
    orb_range: float
    orb_avg_volume: float
    daily_bias_long: bool
    daily_bias_short: bool
    atr5_at_entry: Optional[float]


def _to_cet_time(ts: pd.Timestamp) -> dt.time:
    """Convert UTC timestamp to CET wall-clock time (DST via zoneinfo)."""
    from zoneinfo import ZoneInfo
    return ts.tz_convert(ZoneInfo("Europe/Berlin")).time()


def _to_cet_date(ts: pd.Timestamp) -> dt.date:
    from zoneinfo import ZoneInfo
    return ts.tz_convert(ZoneInfo("Europe/Berlin")).date()


def compute_orb(session_5m: pd.DataFrame) -> Optional[OrbContext]:
    """ORB high/low + avg volume z 3 prvních 5m barů 09:00-09:15 CET.

    Vrací None pokud session nemá 3 ORB bary nebo range < 10 points.
    """
    if len(session_5m) == 0:
        return None
    cet_times = [_to_cet_time(t) for t in session_5m.index]
    in_orb = [(ORB_WINDOW_START <= t < ORB_WINDOW_END) for t in cet_times]
    orb_bars = session_5m[in_orb]
    if len(orb_bars) < ORB_BARS:
        return None
    orb_bars = orb_bars.iloc[:ORB_BARS]
    high = float(orb_bars["high"].max())
    low = float(orb_bars["low"].min())
    rng = high - low
    if rng < ORB_RANGE_MIN_POINTS:
        return None
    return OrbContext(
        orb_high=high,
        orb_low=low,
        orb_range=rng,
        orb_avg_volume=float(orb_bars["volume"].mean()),
        daily_bias_long=False,  # filled by daily_bias()
        daily_bias_short=False,
        atr5_at_entry=None,
    )


def daily_bias(daily_df: pd.DataFrame, today_cet_date: dt.date,
               ema_period: int = 20) -> tuple[bool, bool]:
    """Return (bull_bias, bear_bias). Both False = mixed/insufficient data."""
    if daily_df.empty:
        return False, False
    prior = daily_df[daily_df.index.date < today_cet_date]
    if len(prior) < ema_period + 2:
        return False, False
    ema_d1 = ema(prior["close"], ema_period)
    yest = prior.iloc[-1]
    day_before = prior.iloc[-2]
    yest_close = float(yest["close"])
    yest_open = float(yest["open"])
    db_close = float(day_before["close"])
    ema_yest = float(ema_d1.iloc[-1])
    bull = (yest_close > ema_yest) and (yest_close > yest_open) and (yest_close > db_close)
    bear = (yest_close < ema_yest) and (yest_close < yest_open) and (yest_close < db_close)
    return bull, bear


def aggregate_daily(df_5m: pd.DataFrame) -> pd.DataFrame:
    """5m → D1 OHLC aggregation by CET trading date (no overnight session).

    Returns tz-aware UTC index (CET midnight localized to UTC). This keeps
    daily_df comparable to tz-aware timestamps in classifier/persistence.
    """
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")
    df = df_5m.copy()
    df["_cet_date"] = [t.tz_convert(cet).date() for t in df.index]
    grp = df.groupby("_cet_date")
    daily = pd.DataFrame({
        "open": grp["open"].first(),
        "high": grp["high"].max(),
        "low": grp["low"].min(),
        "close": grp["close"].last(),
        "volume": grp["volume"].sum(),
    })
    daily.index = pd.to_datetime(daily.index).tz_localize("UTC")
    return daily


def f4_atr_relative(df_5m: pd.DataFrame, today_cet_date: dt.date,
                    atr_period: int = 14,
                    median_lookback_days: int = F4_MEDIAN_LOOKBACK_DAYS,
                    threshold_ratio: float = F4_ATR_THRESHOLD_RATIO) -> Optional[bool]:
    """F4: ATR(14) at 09:00-09:15 today > 0.7 × rolling 20-day median.

    Return None if insufficient history.
    """
    a = atr(df_5m, atr_period)
    if a.dropna().empty:
        return None
    cet_dates = pd.Series([_to_cet_date(t) for t in df_5m.index], index=df_5m.index)
    cet_times = pd.Series([_to_cet_time(t) for t in df_5m.index], index=df_5m.index)
    in_orb_window = (cet_times >= ORB_WINDOW_START) & (cet_times < ORB_WINDOW_END)

    today_mask = (cet_dates == today_cet_date) & in_orb_window
    today_atr = a[today_mask]
    if today_atr.dropna().empty:
        return None
    today_value = float(today_atr.dropna().iloc[-1])

    # 20 prior trading days at the same window
    prior_mask = (cet_dates < today_cet_date) & in_orb_window
    prior_atr = a[prior_mask].dropna()
    # Take last value per day across last N days
    if prior_atr.empty:
        return None
    prior_per_day = prior_atr.groupby(cet_dates[prior_mask]).last().tail(median_lookback_days)
    if len(prior_per_day) < median_lookback_days // 2:
        return None
    median = float(prior_per_day.median())
    if median <= 0:
        return None
    return today_value > threshold_ratio * median


class OrbDaxSetup(BaseSetup):
    """ORB-DAX setup — call check_entry(session_5m, daily_df, current_bar_ts)."""

    name = "orb_dax"
    setup_type = "A"

    def __init__(self, filters: Literal["A", "B"] = "A"):
        if filters not in ("A", "B"):
            raise ValueError(f"filters must be 'A' or 'B', got {filters}")
        self.filters = filters
        self.setup_type = filters

    def check_entry(self, market_data) -> Optional[Signal]:  # noqa: D401
        raise NotImplementedError("Use check_entry_at(session_5m, daily_df, ts)")

    def get_sl(self, entry: float, direction: str, market_data) -> float:
        a5 = market_data.get("atr5_at_entry") if isinstance(market_data, dict) else None
        sl_raw = max(SL_MIN_POINTS, SL_ATR_MULT * (a5 or 0))
        offset = sl_raw + SLIPPAGE_AND_SPREAD_POINTS
        return entry - offset if direction == "LONG" else entry + offset

    def get_tp(self, entry: float, sl: float, direction: str) -> float:
        risk = abs(entry - sl)
        return entry + RRR_TARGET * risk if direction == "LONG" else entry - RRR_TARGET * risk

    def check_entry_at(self, session_5m: pd.DataFrame, daily_df: pd.DataFrame,
                       ts: pd.Timestamp,
                       *, history_5m: Optional[pd.DataFrame] = None,
                       skip_filters: Optional[set] = None) -> Optional[Signal]:
        """Vyhodnocení 1 baru.

        session_5m: bary aktuálního CET dne až po `ts` včetně.
        daily_df:   D1 OHLC starší než dnešek (pro daily bias EMA20).
        ts:         timestamp aktuálně uzavřeného 5m baru (UTC).
        history_5m: širší 5m history pro F4 ATR baseline (≥20 dní). Pokud None,
                    F4 fallback = pass (raw spec: missing data ≠ block).
        skip_filters: set z {"F1","F2","F3","F4"} — filtrů k vynechání pro
                    ablation diagnostiku. Vynechaný filtr neblockuje entry,
                    ale negarantuje směrový bias (pak používáme breakout side).
        """
        skip = skip_filters or set()
        if ts not in session_5m.index:
            return None
        bar_cet_time = _to_cet_time(ts)
        if not (ENTRY_WINDOW_START <= bar_cet_time < ENTRY_WINDOW_END):
            return None
        bars_up_to = session_5m.loc[:ts]
        orb = compute_orb(bars_up_to)
        if "F2" not in skip and orb is None:
            return None  # F2 fail
        if orb is None:
            # F2 skipped but no ORB context → can't compute breakout direction
            return None
        today_date = _to_cet_date(ts)
        if "F1" in skip:
            bull = bear = False  # direction will come purely from breakout side
            bias_known = False
        else:
            bull, bear = daily_bias(daily_df, today_date)
            bias_known = True
            if not (bull or bear):
                return None  # F1 fail
        bar = bars_up_to.iloc[-1]
        close = float(bar["close"])
        # Direction
        if bias_known:
            if bull and close > orb.orb_high:
                direction = "LONG"
            elif bear and close < orb.orb_low:
                direction = "SHORT"
            else:
                return None
        else:
            if close > orb.orb_high:
                direction = "LONG"
            elif close < orb.orb_low:
                direction = "SHORT"
            else:
                return None
        # F3 Volume confirm
        if "F3" not in skip:
            if float(bar["volume"]) < VOLUME_THRESHOLD * orb.orb_avg_volume:
                return None
        filters_total = 4 if self.filters == "A" else 3
        filters_met = 3  # F1 + F2 + F3 confirmed (subject to skips)
        # F4 only for filters="A"
        if self.filters == "A" and "F4" not in skip:
            f4_pass = f4_atr_relative(history_5m, today_date) if history_5m is not None else None
            if f4_pass is False:
                return None
            if f4_pass is True:
                filters_met = 4
        # Sizing-relevant ATR for SL
        a5_series = atr(bars_up_to, 14).dropna()
        a5 = float(a5_series.iloc[-1]) if not a5_series.empty else None
        entry = close
        sl = self.get_sl(entry, direction, {"atr5_at_entry": a5})
        tp = self.get_tp(entry, sl, direction)
        return Signal(
            setup_name=self.name,
            direction=direction,
            entry=entry,
            sl=sl,
            tp=tp,
            lots=0.0,  # filled by risk_manager downstream
            risk_usd=0.0,
            confidence=filters_met / filters_total,
            filters_met=filters_met,
            filters_total=filters_total,
        )
