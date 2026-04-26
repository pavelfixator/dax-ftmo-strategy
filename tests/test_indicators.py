"""Smoke tests pro src.strategy.indicators.

Cíl: ověřit že funkce vrací smysluplné hodnoty na syntetických datech, NE
matematickou přesnost vůči TradingView (ten cross-check je out-of-scope —
udělá se proti reálným MT5 hodnotám až bude indikátor zapnut na live grafu).

Run: pytest tests/test_indicators.py -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategy import indicators as ind


@pytest.fixture
def synth_ohlc() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 200
    idx = pd.date_range("2024-01-02 09:00", periods=n, freq="5min", tz="UTC")
    close = 24000 + rng.standard_normal(n).cumsum() * 5
    high = close + rng.uniform(0, 8, n)
    low = close - rng.uniform(0, 8, n)
    open_ = close + rng.uniform(-3, 3, n)
    vol = rng.uniform(50, 200, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low,
                         "close": close, "volume": vol}, index=idx)


def test_sma_ema_match_after_warmup(synth_ohlc):
    s = synth_ohlc["close"]
    assert ind.sma(s, 14).iloc[:13].isna().all()
    assert ind.sma(s, 14).iloc[13:].notna().all()
    assert ind.ema(s, 14).iloc[:13].isna().all()
    assert ind.ema(s, 14).iloc[13:].notna().all()
    # On constant series both should equal the constant
    const = pd.Series([100.0] * 50, index=pd.date_range("2024", periods=50, freq="5min"))
    assert ind.sma(const, 10).iloc[-1] == pytest.approx(100.0)
    assert ind.ema(const, 10).iloc[-1] == pytest.approx(100.0)


def test_atr_positive_and_bounded(synth_ohlc):
    a = ind.atr(synth_ohlc, 14)
    valid = a.dropna()
    assert (valid > 0).all()
    # ATR should be at most max bar range
    bar_range = (synth_ohlc["high"] - synth_ohlc["low"]).max()
    assert valid.max() <= bar_range * 3  # generous upper bound


def test_rsi_in_range(synth_ohlc):
    r = ind.rsi(synth_ohlc["close"], 14).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_adx_columns_and_range(synth_ohlc):
    a = ind.adx(synth_ohlc, 14).dropna()
    assert set(a.columns) == {"plus_di", "minus_di", "adx"}
    assert ((a["adx"] >= 0) & (a["adx"] <= 100)).all()
    assert ((a["plus_di"] >= 0) & (a["plus_di"] <= 100)).all()
    assert ((a["minus_di"] >= 0) & (a["minus_di"] <= 100)).all()


def test_vwap_daily_reset(synth_ohlc):
    v = ind.vwap(synth_ohlc, reset="D")
    # First bar of any day should equal that bar's typical price
    grp = synth_ohlc.index.floor("D")
    first_per_day = synth_ohlc.groupby(grp).head(1)
    typical = (first_per_day["high"] + first_per_day["low"] + first_per_day["close"]) / 3
    assert v.loc[first_per_day.index].equals(typical.rename(None)) or \
        np.allclose(v.loc[first_per_day.index].values, typical.values)


def test_keltner_band_ordering(synth_ohlc):
    k = ind.keltner(synth_ohlc, ema_period=20, atr_period=14, mult=2.5).dropna()
    assert (k["kc_upper"] > k["kc_mid"]).all()
    assert (k["kc_mid"] > k["kc_lower"]).all()
    assert (k["kc_atr"] > 0).all()


def test_relative_volume_uses_prior_window(synth_ohlc):
    rv = ind.relative_volume(synth_ohlc["volume"], lookback=20).dropna()
    assert (rv > 0).all()
    # On constant volume series → relvol should equal 1
    const_vol = pd.Series([100.0] * 50,
                          index=pd.date_range("2024", periods=50, freq="5min"))
    rv_const = ind.relative_volume(const_vol, 20).dropna()
    assert np.allclose(rv_const.values, 1.0)
