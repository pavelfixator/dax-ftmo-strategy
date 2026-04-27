"""Regime classifier — multi-signal consensus pro Strategy v3.3.1.

Vyhodnocení v 08:00 CET, cached pro celý den (cache layer řeší persistence.py).

Konsenzus rule (3 raw signály → composite mapping):
  Signál 1 (volatility): ATR% rolling 20-day vs MA100 → HIGH > 1.5×, LOW < 0.8×, jinak NORMAL
  Signál 2 (trend strength): ADX(14) na H4 — Linda Raschke threshold
                              STRONG > 30, MODERATE 20-30, WEAK < 20
  Signál 3 (direction): EMA50 D1 slope 10-day  →  UP > 0.05%/day, DOWN < -0.05%/day, FLAT

Composite mapping (priority order):
  HIGH vol + DOWN dir         → CRASH        (panic protection)
  STRONG trend + non-HIGH vol → TREND        (clean directional)
  WEAK trend + LOW vol        → CALM         (range/rotation)
  jinak                       → UNDEFINED    (no trade, multiplier 0×)

Spec: Strategy v3.3.1 §2.1.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

from src.strategy.indicators import atr, adx, ema

ATR_PCT_ROLLING_DAYS = 20
ATR_PCT_MA_DAYS = 100
ATR_PCT_HIGH_THRESHOLD = 1.5  # rolling20 / MA100
ATR_PCT_LOW_THRESHOLD = 0.8

ADX_STRONG_THRESHOLD = 30.0
ADX_WEAK_THRESHOLD = 20.0
ADX_PERIOD = 14

EMA_SLOPE_PERIOD = 50
EMA_SLOPE_LOOKBACK_DAYS = 10
EMA_SLOPE_UP_THRESHOLD = 0.0005   # 0.05% / day
EMA_SLOPE_DOWN_THRESHOLD = -0.0005


class Regime(Enum):
    """4 tržní režimy."""
    TREND = "TREND"
    CALM = "CALM"
    CRASH = "CRASH"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class RegimeSignals:
    """Raw signály vstupující do classifier konsensu.

    Atributy:
      ts: 08:00 CET timestamp (tz-aware)
      atr_pct_label: "HIGH" | "NORMAL" | "LOW"
      atr_pct_value: rolling20-day ATR% / MA100 ATR% ratio
      adx_h4_label: "STRONG" | "MODERATE" | "WEAK"
      adx_h4_value: aktuální ADX(14) na H4
      ema_slope_label: "UP" | "FLAT" | "DOWN"
      ema_slope_value: 10-day percent change EMA50 D1 (např. 0.0008 = 0.08 %/day)
    """
    ts: dt.datetime
    atr_pct_label: str
    atr_pct_value: float
    adx_h4_label: str
    adx_h4_value: float
    ema_slope_label: str
    ema_slope_value: float


def _label_atr_pct(ratio: float) -> str:
    if ratio >= ATR_PCT_HIGH_THRESHOLD:
        return "HIGH"
    if ratio < ATR_PCT_LOW_THRESHOLD:
        return "LOW"
    return "NORMAL"


def _label_adx(adx_value: float) -> str:
    if adx_value > ADX_STRONG_THRESHOLD:
        return "STRONG"
    if adx_value < ADX_WEAK_THRESHOLD:
        return "WEAK"
    return "MODERATE"


def _label_ema_slope(slope: float) -> str:
    if slope > EMA_SLOPE_UP_THRESHOLD:
        return "UP"
    if slope < EMA_SLOPE_DOWN_THRESHOLD:
        return "DOWN"
    return "FLAT"


def classify_regime_raw(signals: RegimeSignals) -> Regime:
    """Composite mapping 3 labels → Regime.

    Priority:
      1. HIGH vol + DOWN dir → CRASH (panic, even moderate ADX)
      2. STRONG ADX + non-HIGH vol → TREND
      3. WEAK ADX + LOW vol → CALM
      4. else → UNDEFINED
    """
    vol = signals.atr_pct_label
    adx_l = signals.adx_h4_label
    slope = signals.ema_slope_label
    if vol == "HIGH" and slope == "DOWN":
        return Regime.CRASH
    if adx_l == "STRONG" and vol != "HIGH":
        return Regime.TREND
    if adx_l == "WEAK" and vol == "LOW":
        return Regime.CALM
    return Regime.UNDEFINED


def derive_signals_from_market_data(daily_df: pd.DataFrame,
                                     h4_df: pd.DataFrame,
                                     m5_df: pd.DataFrame,
                                     ts: dt.datetime) -> RegimeSignals:
    """Build RegimeSignals from market data at given 08:00 CET timestamp.

    Vstupní DataFrames:
      daily_df: D1 OHLCV pro EMA50 slope
      h4_df:    H4 OHLCV pro ADX(14)
      m5_df:    5m OHLCV (nepoužívá se v této verzi — kept for forward compat)

    DataFrames jsou tz-aware UTC indexed. Funkce použije pouze řádky před `ts`.

    Raises ValueError pokud insufficient history.
    """
    if ts.tzinfo is None:
        raise ValueError("ts must be tz-aware")
    ts_utc = ts.astimezone(dt.timezone.utc) if ts.tzinfo else ts.replace(tzinfo=dt.timezone.utc)

    # 1) ATR% — daily ATR(14) jako baseline; rolling 20-day vs MA100
    daily_prior = daily_df[daily_df.index < ts_utc]
    if len(daily_prior) < ATR_PCT_MA_DAYS + 5:
        raise ValueError(f"insufficient daily history: {len(daily_prior)} < {ATR_PCT_MA_DAYS + 5}")
    atr_d = atr(daily_prior, 14).dropna()
    atr_pct = atr_d / daily_prior["close"].loc[atr_d.index]
    rolling_20 = atr_pct.rolling(ATR_PCT_ROLLING_DAYS, min_periods=ATR_PCT_ROLLING_DAYS).mean()
    ma_100 = atr_pct.rolling(ATR_PCT_MA_DAYS, min_periods=ATR_PCT_MA_DAYS).mean()
    if rolling_20.dropna().empty or ma_100.dropna().empty:
        raise ValueError("ATR% rolling/MA100 insufficient warmup")
    last_ma100 = float(ma_100.dropna().iloc[-1])
    if last_ma100 <= 0:
        raise ValueError("ATR% MA100 zero/negative")
    atr_ratio = float(rolling_20.dropna().iloc[-1]) / last_ma100

    # 2) ADX(14) na H4 — value at most-recent H4 bar before ts
    h4_prior = h4_df[h4_df.index < ts_utc]
    if len(h4_prior) < ADX_PERIOD + 14:
        raise ValueError(f"insufficient H4 history for ADX: {len(h4_prior)}")
    adx_series = adx(h4_prior, ADX_PERIOD)["adx"].dropna()
    if adx_series.empty:
        raise ValueError("ADX series empty after warmup")
    adx_val = float(adx_series.iloc[-1])

    # 3) EMA50 D1 slope 10-day percent change
    if len(daily_prior) < EMA_SLOPE_PERIOD + EMA_SLOPE_LOOKBACK_DAYS + 2:
        raise ValueError("insufficient daily history for EMA50 slope")
    ema50 = ema(daily_prior["close"], EMA_SLOPE_PERIOD).dropna()
    if len(ema50) < EMA_SLOPE_LOOKBACK_DAYS + 1:
        raise ValueError("EMA50 series too short")
    ema_now = float(ema50.iloc[-1])
    ema_then = float(ema50.iloc[-1 - EMA_SLOPE_LOOKBACK_DAYS])
    if ema_then == 0:
        raise ValueError("EMA50 reference value zero")
    slope_per_day = (ema_now - ema_then) / ema_then / EMA_SLOPE_LOOKBACK_DAYS

    return RegimeSignals(
        ts=ts,
        atr_pct_label=_label_atr_pct(atr_ratio),
        atr_pct_value=atr_ratio,
        adx_h4_label=_label_adx(adx_val),
        adx_h4_value=adx_val,
        ema_slope_label=_label_ema_slope(slope_per_day),
        ema_slope_value=slope_per_day,
    )
