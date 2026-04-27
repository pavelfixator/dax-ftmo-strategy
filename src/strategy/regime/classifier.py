"""Regime classifier — multi-signal consensus pro Strategy v3.3.1.

Vyhodnocení v 08:00 CET, cached pro celý den (cache layer řeší persistence.py).

Konsenzus rule (2/3 musí souhlasit, jinak UNDEFINED):
  Signál 1: ATR% (HIGH > 1.5×MA100, NORMAL, LOW < 0.8×MA100)
  Signál 2: ADX(14) H4 (STRONG > 30, MODERATE 20-30, WEAK < 20) — Linda Raschke
  Signál 3: EMA50 D1 slope 10-day (UP > 0.05%/day, FLAT, DOWN < -0.05%/day)

Composite mapping:
  HIGH vol + DOWN direction → CRASH
  STRONG trend + non-HIGH vol → TREND
  WEAK trend + LOW vol → CALM
  jinak → UNDEFINED (no trade, risk multiplier 0×)

Implementace stub. Plná logika v Sekci 2.

Spec: Strategy v3.3.1 §2.1.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Regime(Enum):
    """4 tržní režimy podle multi-signal konsensu."""
    TREND = "TREND"
    CALM = "CALM"
    CRASH = "CRASH"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class RegimeSignals:
    """Raw signály vstupující do classifier konsensu.

    Atributy:
      ts: 08:00 CET timestamp (tz-aware) kdy byl klasifikátor vyhodnocen
      atr_pct_label: "HIGH" | "NORMAL" | "LOW"
      atr_pct_value: aktuální ATR% (rolling 20-day) / MA100 ratio
      adx_h4_label: "STRONG" | "MODERATE" | "WEAK"
      adx_h4_value: aktuální ADX(14) na H4 timeframe
      ema_slope_label: "UP" | "FLAT" | "DOWN"
      ema_slope_value: 10-day percent change EMA50 D1 (např. 0.0008 = 0.08%/day)
    """
    ts: dt.datetime
    atr_pct_label: str
    atr_pct_value: float
    adx_h4_label: str
    adx_h4_value: float
    ema_slope_label: str
    ema_slope_value: float


def classify_regime_raw(signals: RegimeSignals) -> Regime:
    """Mapuje 3 raw signály na Regime přes 2/3 consensus.

    Stub. Plná implementace v Sekci 2 — bude obsahovat:
      1. HIGH+DOWN → CRASH (panic protection priority)
      2. STRONG+(NORMAL|LOW) → TREND
      3. WEAK+LOW → CALM
      4. else → UNDEFINED

    Args:
        signals: RegimeSignals s pre-classified labels (HIGH/NORMAL/LOW etc.)

    Returns:
        Regime enum value.

    Raises:
        NotImplementedError: dokud Sekce 2 nedokončí.
    """
    raise NotImplementedError(
        "classify_regime_raw: full implementation deferred to Sekce 2"
    )


def derive_signals_from_market_data(daily_df, h4_df, m5_df,
                                     ts_cet: dt.datetime) -> RegimeSignals:
    """Build RegimeSignals from raw market data at given 08:00 CET timestamp.

    Stub. Sekce 2 provede:
      - ATR% rolling 20-day vs MA100 → label HIGH/NORMAL/LOW
      - ADX(14) na H4 → label STRONG/MODERATE/WEAK (Linda Raschke thresholds)
      - EMA50 D1 slope 10-day → label UP/FLAT/DOWN

    Args:
        daily_df: D1 OHLCV pro EMA50 slope
        h4_df: H4 OHLCV pro ADX(14)
        m5_df: 5m OHLCV pro ATR% rolling
        ts_cet: 08:00 CET tz-aware timestamp

    Returns:
        RegimeSignals.

    Raises:
        NotImplementedError: dokud Sekce 2 nedokončí.
    """
    raise NotImplementedError(
        "derive_signals_from_market_data: deferred to Sekce 2"
    )
