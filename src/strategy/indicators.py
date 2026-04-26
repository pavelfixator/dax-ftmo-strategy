"""Technical indicators — EMA, SMA, ATR, RSI, ADX, VWAP, Keltner.

Pure functions na pandas DataFrames / Series. Žádný state, žádné side-effects.
Používá se v setupech (`src/strategy/setups/`) a v daily-bias filtrech
(`src/risk/rules_engine.py`).

Konvence:
  - Vstupní DataFrame má sloupce: open, high, low, close, volume (lower-case).
  - Index je tz-aware DatetimeIndex (UTC). Pro daily-reset indikátory (VWAP)
    používáme UTC midnight jako default rollover.
  - Wilder's smoothing (alpha = 1/period) pro RSI / ATR / ADX, jak je standard
    v MT5 / TradingView default.

Spec: Strategy v3.2 (Filtry F1-F4 napříč ORB / VWAP / US-Momentum setupy).
"""
from __future__ import annotations

import pandas as pd

OHLC_COLS = ("open", "high", "low", "close")


def sma(s: pd.Series, period: int) -> pd.Series:
    return s.rolling(window=period, min_periods=period).mean()


def ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False, min_periods=period).mean()


def _rma(s: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed moving average (RMA): alpha = 1/period."""
    return s.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def true_range(df: pd.DataFrame) -> pd.Series:
    h, l, pc = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([(h - l), (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _rma(true_range(df), period)


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = _rma(gain, period)
    avg_loss = _rma(loss, period)
    rs = avg_gain / avg_loss.replace(0.0, pd.NA)
    return 100.0 - (100.0 / (1.0 + rs))


def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Returns DataFrame with columns: plus_di, minus_di, adx."""
    h, l = df["high"], df["low"]
    up = h.diff()
    down = -l.diff()
    plus_dm = ((up > down) & (up > 0)).astype(float) * up
    minus_dm = ((down > up) & (down > 0)).astype(float) * down
    tr = true_range(df)
    atr_w = _rma(tr, period)
    plus_di = 100.0 * _rma(plus_dm, period) / atr_w
    minus_di = 100.0 * _rma(minus_dm, period) / atr_w
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, pd.NA)
    return pd.DataFrame({
        "plus_di": plus_di,
        "minus_di": minus_di,
        "adx": _rma(dx, period),
    })


def vwap(df: pd.DataFrame, reset: str = "D") -> pd.Series:
    """Volume-weighted average price with periodic reset.

    `reset='D'` = UTC daily reset (default). `reset=None` = cumulative from
    first bar (no reset). Typical price = (H+L+C)/3.
    """
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = typical * df["volume"]
    if reset is None:
        return pv.cumsum() / df["volume"].cumsum()
    grp = df.index.floor(reset)
    return (pv.groupby(grp).cumsum() / df["volume"].groupby(grp).cumsum())


def keltner(df: pd.DataFrame, ema_period: int = 20, atr_period: int = 14,
            mult: float = 2.5) -> pd.DataFrame:
    """Keltner Channel: middle = EMA(close), bands = middle ± mult × ATR.

    Default mult=2.5 odpovídá Strategy v3.2 vítězné variantě (Experiment #4).
    """
    mid = ema(df["close"], ema_period)
    a = atr(df, atr_period)
    return pd.DataFrame({
        "kc_mid": mid,
        "kc_upper": mid + mult * a,
        "kc_lower": mid - mult * a,
        "kc_atr": a,
    })


def relative_volume(volume: pd.Series, lookback: int = 20) -> pd.Series:
    """vol[t] / SMA(vol, lookback)[t-1]. Filtr F3 ORB-DAX (>1.5)."""
    avg = sma(volume, lookback).shift(1)
    return volume / avg
