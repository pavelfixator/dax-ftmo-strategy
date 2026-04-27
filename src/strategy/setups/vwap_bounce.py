# DEPRECATED v3.3.1 — VWAP DROPPED (RRR 1:2 violation)
"""VWAP-Bounce Setup — DEPRECATED v3.3.1.

Důvod: post-9-kol adversarial design analýza Iter2 ukázala 120 sig → 0 trades
v calm regime, RRR 1:2 hard rule violation (TP1 = Keltner mid často <1× SL).
v3.3.1 redukuje na 2 setupy: ORB-DAX + US-Momentum (oba regime-aware).

Modul zůstává pro Iter2/Iter2b benchmark, ale není používán post-Sekce 3.

Spec: Strategy v3.2 §Setup 2 + Pavel's hybrid plan 2026-04-26.

Mechanika:
  Range / rotation regime, evropský lunch (11:30-13:30 CET).
  ADX(14) na 30m TF musí být < 20 (no-trend).
  Cena se dotkne Keltner pásma (EMA20 + 2.5×ATR14), na otočení reverz candle.

Filtry A (4):
  F1 ADX(14) 30m < 20
  F2 Keltner touch (low ≤ kc_lower → long; high ≥ kc_upper → short)
  F3 Brooks reversal candle: bullish/bearish engulfing baru na hranici
  F4 Volume confirm > 1.2× avg posledních 20 5m barů

Filtry B (3): F1 + F2 + F3 (chybí F4).

Entry:    market na close reversal baru (LONG na bull eng., SHORT na bear)
SL_raw:   35 bodů FIXED (structure-based: za reversal bar low/high + 3 buffer)
SL_eff:   38.5 bodů (35 + 1.5 spread + 2.0 slippage)
TP1:      Keltner middle (kc_mid)            ← Signal.tp
TP2:      opposite Keltner band              ← engine reads via setup attrs
Invalidace: 5m close mimo Keltner band (proti směru entry).
"""
from __future__ import annotations

import datetime as dt
from typing import Literal, Optional

import pandas as pd

from src.strategy.indicators import adx, keltner
from .base_setup import BaseSetup, Signal

ENTRY_WINDOW_START = dt.time(11, 30)
ENTRY_WINDOW_END = dt.time(13, 30)
ADX_NO_TREND_THRESHOLD = 20.0
KC_EMA_PERIOD = 20
KC_ATR_PERIOD = 14
KC_MULT = 2.5
SL_RAW_POINTS = 35.0
SLIPPAGE_AND_SPREAD = 3.5
SL_EFF_POINTS = SL_RAW_POINTS + SLIPPAGE_AND_SPREAD  # 38.5
VOLUME_THRESHOLD = 1.2
VOLUME_LOOKBACK = 20


def _to_cet_time(ts: pd.Timestamp) -> dt.time:
    from zoneinfo import ZoneInfo
    return ts.tz_convert(ZoneInfo("Europe/Berlin")).time()


def is_engulfing(prev: pd.Series, cur: pd.Series) -> Optional[str]:
    """Brooks-style engulfing detection.

    Bullish engulfing (LONG signal): prev red (close<open) + cur green
    closing above prev open AND opening below prev close.
    Bearish: mirror.
    """
    p_open, p_close = float(prev["open"]), float(prev["close"])
    c_open, c_close = float(cur["open"]), float(cur["close"])
    if c_close > c_open and p_close < p_open and c_close > p_open and c_open < p_close:
        return "BULL"
    if c_close < c_open and p_close > p_open and c_close < p_open and c_open > p_close:
        return "BEAR"
    return None


def adx_on_30m(df_5m: pd.DataFrame, period: int = 14) -> pd.Series:
    """Resample 5m → 30m (right-closed) and compute ADX(period)."""
    if df_5m.empty:
        return pd.Series(dtype=float)
    rs = df_5m.resample("30min", label="right", closed="right").agg({
        "open": "first", "high": "max", "low": "min",
        "close": "last", "volume": "sum",
    }).dropna(subset=["close"])
    return adx(rs, period)["adx"]


def keltner_state(df_5m: pd.DataFrame) -> pd.DataFrame:
    return keltner(df_5m, ema_period=KC_EMA_PERIOD,
                   atr_period=KC_ATR_PERIOD, mult=KC_MULT)


def volume_confirm(df_5m: pd.DataFrame, ts: pd.Timestamp,
                   lookback: int = VOLUME_LOOKBACK,
                   threshold: float = VOLUME_THRESHOLD) -> bool:
    if ts not in df_5m.index:
        return False
    bar_vol = float(df_5m.loc[ts, "volume"])
    prior = df_5m.loc[df_5m.index < ts, "volume"].tail(lookback)
    if len(prior) < lookback // 2:
        return False
    return bar_vol > threshold * float(prior.mean())


class VwapBounceSetup(BaseSetup):
    name = "vwap_bounce"
    setup_type = "B"  # default secondary; A when F4 also passes

    def __init__(self, filters: Literal["A", "B"] = "A"):
        if filters not in ("A", "B"):
            raise ValueError(f"filters must be 'A' or 'B', got {filters}")
        self.filters = filters
        self.setup_type = filters

    def check_entry(self, market_data) -> Optional[Signal]:
        raise NotImplementedError("Use check_entry_at(df_5m, ts)")

    def get_sl(self, entry: float, direction: str, market_data=None) -> float:
        return entry - SL_EFF_POINTS if direction == "LONG" else entry + SL_EFF_POINTS

    def get_tp(self, entry: float, sl: float, direction: str,
               kc_mid: Optional[float] = None) -> float:
        """Default TP = Keltner middle if known; fallback RRR 1:2 vs SL."""
        if kc_mid is not None:
            return kc_mid
        risk = abs(entry - sl)
        return entry + 2 * risk if direction == "LONG" else entry - 2 * risk

    def check_entry_at(self, df_5m: pd.DataFrame, ts: pd.Timestamp,
                       *, history_5m: Optional[pd.DataFrame] = None,
                       skip_filters: Optional[set] = None) -> Optional[Signal]:
        """Vyhodnocení 1 baru.

        df_5m:      bary aktuálního dne až po `ts` včetně.
        history_5m: ≥ KC_EMA_PERIOD+ATR_PERIOD bars before today, pro warmup
                    Keltneru a 30m ADX. Pokud None, použije se df_5m sám.
        skip_filters: set z {"F1","F2","F3","F4"} pro ablation. F3 (engulfing)
                    je entry-defining; když skipnuto, používá se touch-only jako
                    direction proxy.
        """
        skip = skip_filters or set()
        if ts not in df_5m.index:
            return None
        if not (ENTRY_WINDOW_START <= _to_cet_time(ts) < ENTRY_WINDOW_END):
            return None
        ctx = history_5m if history_5m is not None else df_5m
        ctx_up_to = ctx.loc[:ts]
        if len(ctx_up_to) < KC_EMA_PERIOD + KC_ATR_PERIOD:
            return None
        # F1 ADX 30m < 20
        if "F1" not in skip:
            adx30 = adx_on_30m(ctx_up_to)
            if adx30.dropna().empty:
                return None
            last_adx = float(adx30.dropna().iloc[-1])
            if last_adx >= ADX_NO_TREND_THRESHOLD:
                return None
        # F2 Keltner touch
        kc = keltner_state(ctx_up_to).iloc[-1]
        if pd.isna(kc["kc_upper"]):
            return None
        cur = ctx_up_to.iloc[-1]
        touch_lower = float(cur["low"]) <= float(kc["kc_lower"])
        touch_upper = float(cur["high"]) >= float(kc["kc_upper"])
        if "F2" not in skip and not (touch_lower or touch_upper):
            return None
        # F3 Brooks engulfing on (prev, cur)
        if len(ctx_up_to) < 2:
            return None
        if "F3" not in skip:
            eng = is_engulfing(ctx_up_to.iloc[-2], cur)
            if eng is None:
                return None
            if eng == "BULL" and not touch_lower and "F2" not in skip:
                return None
            if eng == "BEAR" and not touch_upper and "F2" not in skip:
                return None
            direction = "LONG" if eng == "BULL" else "SHORT"
        else:
            # F3 skipped: derive direction from touch side (or fallback to bar direction)
            if touch_lower:
                direction = "LONG"
            elif touch_upper:
                direction = "SHORT"
            else:
                # F2 also skipped → use bar color
                direction = "LONG" if float(cur["close"]) > float(cur["open"]) else "SHORT"
        # F4 Volume confirm (only Filter A)
        filters_total = 4 if self.filters == "A" else 3
        filters_met = 3
        if self.filters == "A" and "F4" not in skip:
            if not volume_confirm(ctx_up_to, ts):
                return None
            filters_met = 4
        entry = float(cur["close"])
        sl = self.get_sl(entry, direction)
        tp = self.get_tp(entry, sl, direction, kc_mid=float(kc["kc_mid"]))
        return Signal(
            setup_name=self.name,
            direction=direction,
            entry=entry,
            sl=sl,
            tp=tp,
            lots=0.0,
            risk_usd=0.0,
            confidence=filters_met / filters_total,
            filters_met=filters_met,
            filters_total=filters_total,
        )
