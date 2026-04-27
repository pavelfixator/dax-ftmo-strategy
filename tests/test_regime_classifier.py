"""Tests pro src.strategy.regime.classifier — composite mapping + signal derivation."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.regime.classifier import (
    Regime, RegimeSignals,
    classify_regime_raw, derive_signals_from_market_data,
    _label_atr_pct, _label_adx, _label_ema_slope,
)


def _signals(vol="NORMAL", vol_v=1.0, adx_l="MODERATE", adx_v=25.0,
             slope="FLAT", slope_v=0.0):
    return RegimeSignals(
        ts=dt.datetime(2026, 4, 27, 8, 0, tzinfo=dt.timezone.utc),
        atr_pct_label=vol, atr_pct_value=vol_v,
        adx_h4_label=adx_l, adx_h4_value=adx_v,
        ema_slope_label=slope, ema_slope_value=slope_v,
    )


# ============================================================
# Label boundary tests
# ============================================================

class TestLabels:
    def test_atr_high_at_threshold(self):
        assert _label_atr_pct(1.5) == "HIGH"
        assert _label_atr_pct(1.49) == "NORMAL"
        assert _label_atr_pct(2.0) == "HIGH"

    def test_atr_low_below_0p8(self):
        assert _label_atr_pct(0.79) == "LOW"
        assert _label_atr_pct(0.8) == "NORMAL"
        assert _label_atr_pct(0.5) == "LOW"

    def test_atr_normal_band(self):
        assert _label_atr_pct(1.0) == "NORMAL"
        assert _label_atr_pct(1.49) == "NORMAL"

    def test_adx_strong_above_30(self):
        assert _label_adx(31) == "STRONG"
        assert _label_adx(30) == "MODERATE"
        assert _label_adx(45) == "STRONG"

    def test_adx_weak_below_20(self):
        assert _label_adx(19.9) == "WEAK"
        assert _label_adx(20) == "MODERATE"
        assert _label_adx(10) == "WEAK"

    def test_adx_moderate_band(self):
        assert _label_adx(25) == "MODERATE"
        assert _label_adx(20) == "MODERATE"
        assert _label_adx(30) == "MODERATE"

    def test_ema_slope_up_above_005pct(self):
        assert _label_ema_slope(0.0006) == "UP"
        assert _label_ema_slope(0.001) == "UP"
        assert _label_ema_slope(0.0005) == "FLAT"

    def test_ema_slope_down_below_minus005pct(self):
        assert _label_ema_slope(-0.0006) == "DOWN"
        assert _label_ema_slope(-0.001) == "DOWN"
        assert _label_ema_slope(-0.0005) == "FLAT"

    def test_ema_slope_flat_band(self):
        assert _label_ema_slope(0.0) == "FLAT"
        assert _label_ema_slope(0.0003) == "FLAT"
        assert _label_ema_slope(-0.0004) == "FLAT"


# ============================================================
# Composite mapping tests
# ============================================================

class TestClassifyRegimeRaw:
    def test_high_vol_down_is_crash(self):
        # Even with strong ADX, HIGH+DOWN forces CRASH (panic priority)
        s = _signals(vol="HIGH", vol_v=1.8, adx_l="STRONG", adx_v=35,
                     slope="DOWN", slope_v=-0.001)
        assert classify_regime_raw(s) == Regime.CRASH

    def test_high_vol_up_not_crash_falls_to_trend_or_undefined(self):
        # HIGH vol + UP not CRASH; STRONG ADX + HIGH vol → vol blocks TREND, undefined
        s = _signals(vol="HIGH", vol_v=2.0, adx_l="STRONG", adx_v=35,
                     slope="UP", slope_v=0.001)
        assert classify_regime_raw(s) == Regime.UNDEFINED

    def test_strong_trend_normal_vol_is_trend(self):
        s = _signals(vol="NORMAL", vol_v=1.0, adx_l="STRONG", adx_v=35,
                     slope="UP", slope_v=0.0008)
        assert classify_regime_raw(s) == Regime.TREND

    def test_strong_trend_low_vol_is_trend(self):
        s = _signals(vol="LOW", vol_v=0.6, adx_l="STRONG", adx_v=35,
                     slope="UP", slope_v=0.0008)
        assert classify_regime_raw(s) == Regime.TREND

    def test_strong_trend_high_vol_is_undefined(self):
        # STRONG ADX but HIGH vol blocks TREND; not DOWN slope → not CRASH
        s = _signals(vol="HIGH", vol_v=2.0, adx_l="STRONG", adx_v=35,
                     slope="FLAT", slope_v=0.0)
        assert classify_regime_raw(s) == Regime.UNDEFINED

    def test_weak_trend_low_vol_is_calm(self):
        s = _signals(vol="LOW", vol_v=0.6, adx_l="WEAK", adx_v=15,
                     slope="FLAT", slope_v=0.0)
        assert classify_regime_raw(s) == Regime.CALM

    def test_weak_trend_normal_vol_is_undefined(self):
        s = _signals(vol="NORMAL", vol_v=1.0, adx_l="WEAK", adx_v=15,
                     slope="FLAT", slope_v=0.0)
        assert classify_regime_raw(s) == Regime.UNDEFINED

    def test_moderate_everything_is_undefined(self):
        s = _signals(vol="NORMAL", vol_v=1.0, adx_l="MODERATE", adx_v=25,
                     slope="FLAT", slope_v=0.0)
        assert classify_regime_raw(s) == Regime.UNDEFINED

    def test_moderate_adx_low_vol_undefined(self):
        s = _signals(vol="LOW", vol_v=0.7, adx_l="MODERATE", adx_v=25,
                     slope="UP", slope_v=0.0008)
        assert classify_regime_raw(s) == Regime.UNDEFINED

    def test_low_vol_strong_down_trend(self):
        # STRONG + LOW vol + DOWN → TREND (downtrend, not crash)
        s = _signals(vol="LOW", vol_v=0.7, adx_l="STRONG", adx_v=35,
                     slope="DOWN", slope_v=-0.001)
        assert classify_regime_raw(s) == Regime.TREND


# ============================================================
# derive_signals_from_market_data — synthesize realistic input
# ============================================================

def _build_synth_history(n_days: int = 130, calm: bool = True) -> tuple:
    """Returns (daily_df, h4_df, m5_df, ts) — synth indexed UTC."""
    rng = np.random.default_rng(42)
    end_date = dt.date(2026, 4, 27)
    start_date = end_date - dt.timedelta(days=n_days)
    daily_idx = pd.date_range(start_date, end_date - dt.timedelta(days=1),
                              freq="D", tz="UTC")
    base = 13000.0
    if calm:
        # Low vol, sideways
        closes = base + rng.standard_normal(len(daily_idx)).cumsum() * 5
        ranges = rng.uniform(20, 60, len(daily_idx))
    else:
        # Trending up
        closes = base + np.arange(len(daily_idx)) * 15 + rng.standard_normal(len(daily_idx)) * 8
        ranges = rng.uniform(80, 200, len(daily_idx))
    daily_df = pd.DataFrame({
        "open": closes - 5,
        "high": closes + ranges / 2,
        "low":  closes - ranges / 2,
        "close": closes,
        "volume": rng.uniform(1000, 2000, len(daily_idx)),
    }, index=daily_idx)
    # H4 — 6 bars per day; for ADX we need ~28+ bars
    h4_n = n_days * 6
    h4_idx = pd.date_range(start_date, periods=h4_n, freq="4h", tz="UTC")
    h4_close = base + rng.standard_normal(h4_n).cumsum() * 2
    h4_df = pd.DataFrame({
        "open": h4_close - 2,
        "high": h4_close + rng.uniform(2, 8, h4_n),
        "low":  h4_close - rng.uniform(2, 8, h4_n),
        "close": h4_close,
        "volume": rng.uniform(100, 500, h4_n),
    }, index=h4_idx)
    m5_df = pd.DataFrame()  # not used in current derivation; placeholder
    ts = pd.Timestamp(end_date, tz="UTC").to_pydatetime()
    return daily_df, h4_df, m5_df, ts


class TestDeriveSignals:
    def test_calm_history_produces_valid_signals(self):
        daily, h4, m5, ts = _build_synth_history(n_days=130, calm=True)
        sig = derive_signals_from_market_data(daily, h4, m5, ts)
        assert sig.atr_pct_label in {"HIGH", "NORMAL", "LOW"}
        assert sig.adx_h4_label in {"STRONG", "MODERATE", "WEAK"}
        assert sig.ema_slope_label in {"UP", "FLAT", "DOWN"}
        assert sig.ts == ts
        assert isinstance(sig.atr_pct_value, float)

    def test_trending_history_yields_up_slope(self):
        daily, h4, m5, ts = _build_synth_history(n_days=130, calm=False)
        sig = derive_signals_from_market_data(daily, h4, m5, ts)
        # Strongly trending up by construction
        assert sig.ema_slope_value > 0
        assert sig.ema_slope_label in {"UP", "FLAT"}

    def test_short_history_raises(self):
        daily, h4, m5, ts = _build_synth_history(n_days=20)
        with pytest.raises(ValueError, match="insufficient"):
            derive_signals_from_market_data(daily, h4, m5, ts)

    def test_naive_ts_raises(self):
        daily, h4, m5, _ = _build_synth_history(n_days=130)
        with pytest.raises(ValueError, match="tz-aware"):
            derive_signals_from_market_data(daily, h4, m5, dt.datetime(2026, 4, 27))
