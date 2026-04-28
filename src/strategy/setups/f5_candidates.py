# DEPRECATED v3.3.2.1 — F5 framework dropped after extended ablation (0/8 candidates passed FDR + OOS + sample size). Filter Budget exception accepted (3-4 filters per regime). Module retained for backward-compat with ablation outputs and re-runs against historical specs.
"""F5 filter candidates pro extended ablation (Exp #12) — DEPRECATED v3.3.2.1.

Pro ORB-DAX CRASH regime (4 candidates):
  F5a range_exp     — 5m bar |H-L| > 2× ATR(14) 5m  (Connors-Raschke)
  F5b brooks_break  — current 5m close above prior swing high (LONG) / below low (SHORT)
  F5c rsi_extreme   — RSI(14) > 80 (LONG opportunity post-extreme) or < 20 (SHORT)
  F5d nr4           — current bar range == min(last 4 bar ranges)  (volatility compression)

Pro US-Momentum CALM regime (4 candidates):
  F5a macd_3_10     — MACD(3,10,3) histogram aligned with direction
  F5b dual_ema      — EMA9 > EMA21 (LONG) / EMA9 < EMA21 (SHORT)
  F5c volume_profile— current bar volume in top quartile of session
  F5d atr_norm_mom  — (close - close[N]) / ATR(N) > threshold (normalized momentum)

Each candidate returns bool — True = filter passes (allow signal).
Direction parameter required pro all (different polarity per LONG/SHORT).

Spec: Strategy v3.3.1 §2.4 + Pavel hybrid plan 2026-04-27 (Exp #12 candidates).
"""
from __future__ import annotations

import pandas as pd

from src.strategy.indicators import atr, ema, rsi
from src.strategy.setups.us_momentum_v331 import (
    macd_3_10_histogram, f5_calm_macd_aligned,
)
from src.strategy.setups.orb_dax_v331 import f5_crash_range_expansion


# ===========================================================================
# ORB-DAX CRASH F5 candidates
# ===========================================================================

def f5a_range_exp_orb(bar: pd.Series, history_5m: pd.DataFrame,
                      direction: str = "LONG") -> bool:
    """F5a: range expansion (existing default in orb_dax_v331)."""
    a5_series = atr(history_5m, 14).dropna()
    if a5_series.empty:
        return False
    return f5_crash_range_expansion(bar, float(a5_series.iloc[-1]))


def f5b_brooks_break_orb(bar: pd.Series, history_5m: pd.DataFrame,
                          direction: str, lookback: int = 10) -> bool:
    """F5b Brooks break: close above prior 10-bar swing high (LONG) / below low (SHORT)."""
    if len(history_5m) < lookback + 1:
        return False
    prior = history_5m.iloc[-(lookback + 1):-1]
    close = float(bar["close"])
    if direction == "LONG":
        return close > float(prior["high"].max())
    return close < float(prior["low"].min())


def f5c_rsi_extreme_orb(bar: pd.Series, history_5m: pd.DataFrame,
                         direction: str, period: int = 14) -> bool:
    """F5c RSI extreme: RSI(14) > 80 LONG (momentum continuation in crash relief)
    or < 20 SHORT (oversold continuation)."""
    if len(history_5m) < period + 5:
        return False
    r = rsi(history_5m["close"], period).dropna()
    if r.empty:
        return False
    last = float(r.iloc[-1])
    if direction == "LONG":
        return last > 80.0
    return last < 20.0


def f5d_nr4_orb(bar: pd.Series, history_5m: pd.DataFrame,
                 direction: str = "LONG") -> bool:
    """F5d NR4: current bar range == min of last 4 bar ranges (volatility compression)."""
    if len(history_5m) < 4:
        return False
    last_4 = history_5m.iloc[-4:]
    ranges = last_4["high"] - last_4["low"]
    cur_range = float(bar["high"] - bar["low"])
    return cur_range <= float(ranges.min())  # tightest in window


ORB_CRASH_F5_CANDIDATES = {
    "F5a_range_exp": f5a_range_exp_orb,
    "F5b_brooks_break": f5b_brooks_break_orb,
    "F5c_rsi_extreme": f5c_rsi_extreme_orb,
    "F5d_nr4": f5d_nr4_orb,
}


# ===========================================================================
# US-Momentum CALM F5 candidates
# ===========================================================================

def f5a_macd_us(history_5m: pd.DataFrame, direction: str) -> bool:
    """F5a MACD 3-10 histogram alignment (existing default)."""
    return f5_calm_macd_aligned(history_5m["close"], direction)


def f5b_dual_ema_us(history_5m: pd.DataFrame, direction: str) -> bool:
    """F5b Dual EMA: EMA9 > EMA21 (LONG) / EMA9 < EMA21 (SHORT)."""
    if len(history_5m) < 22:
        return False
    e9 = ema(history_5m["close"], 9).dropna()
    e21 = ema(history_5m["close"], 21).dropna()
    if e9.empty or e21.empty:
        return False
    if direction == "LONG":
        return float(e9.iloc[-1]) > float(e21.iloc[-1])
    return float(e9.iloc[-1]) < float(e21.iloc[-1])


def f5c_volume_profile_us(history_5m: pd.DataFrame, direction: str = "LONG",
                           lookback: int = 50) -> bool:
    """F5c Volume profile: current bar volume in top quartile of last N bars."""
    if len(history_5m) < lookback + 1:
        return False
    window = history_5m["volume"].iloc[-(lookback + 1):-1]
    cur = float(history_5m["volume"].iloc[-1])
    q75 = float(window.quantile(0.75))
    return cur >= q75


def f5d_atr_norm_momentum_us(history_5m: pd.DataFrame, direction: str,
                              period: int = 20, threshold: float = 1.0) -> bool:
    """F5d ATR-normalized momentum: |(close - close[N]) / ATR(N)| > threshold,
    sign matching direction."""
    if len(history_5m) < period + 14:
        return False
    a = atr(history_5m, 14).dropna()
    if a.empty:
        return False
    atr_val = float(a.iloc[-1])
    if atr_val <= 0:
        return False
    close_now = float(history_5m["close"].iloc[-1])
    close_then = float(history_5m["close"].iloc[-1 - period])
    norm = (close_now - close_then) / atr_val
    if direction == "LONG":
        return norm > threshold
    return norm < -threshold


US_CALM_F5_CANDIDATES = {
    "F5a_macd_3_10": f5a_macd_us,
    "F5b_dual_ema": f5b_dual_ema_us,
    "F5c_volume_profile": f5c_volume_profile_us,
    "F5d_atr_norm_momentum": f5d_atr_norm_momentum_us,
}
