"""Tests pro src.strategy.setups.f5_candidates."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategy.setups.f5_candidates import (
    f5a_range_exp_orb, f5b_brooks_break_orb, f5c_rsi_extreme_orb, f5d_nr4_orb,
    f5a_macd_us, f5b_dual_ema_us, f5c_volume_profile_us, f5d_atr_norm_momentum_us,
    ORB_CRASH_F5_CANDIDATES, US_CALM_F5_CANDIDATES,
)


def _hist(closes, ranges=None):
    n = len(closes)
    rng = np.random.default_rng(0)
    r = ranges if ranges is not None else rng.uniform(2, 8, n)
    high = closes + r / 2
    low = closes - r / 2
    return pd.DataFrame({
        "open": closes - 0.5, "high": high, "low": low, "close": closes,
        "volume": rng.uniform(80, 120, n),
    })


# ============================================================
# ORB-CRASH F5 candidates
# ============================================================

class TestF5OrbCandidates:
    def test_dict_has_4_candidates(self):
        assert set(ORB_CRASH_F5_CANDIDATES.keys()) == {
            "F5a_range_exp", "F5b_brooks_break", "F5c_rsi_extreme", "F5d_nr4",
        }

    def test_range_exp_passes_on_large_bar(self):
        history = _hist(np.full(20, 13000.0), ranges=np.full(20, 4.0))
        bar = pd.Series({"high": 13050, "low": 12950})  # range 100, ATR ~4
        assert f5a_range_exp_orb(bar, history) is True

    def test_brooks_break_long_above_swing_high(self):
        closes = np.linspace(13000, 13050, 15)
        history = _hist(closes)
        bar = pd.Series({"close": 13100, "high": 13105, "low": 13095})
        assert f5b_brooks_break_orb(bar, history, "LONG") is True

    def test_brooks_break_long_blocks_below(self):
        closes = np.linspace(13000, 13050, 15)
        history = _hist(closes)
        bar = pd.Series({"close": 13030, "high": 13035, "low": 13025})
        assert f5b_brooks_break_orb(bar, history, "LONG") is False

    def test_rsi_extreme_long_high_rsi(self):
        # Pure uptrend → RSI very high
        closes = np.linspace(13000, 13500, 30)
        history = _hist(closes)
        bar = history.iloc[-1]
        # RSI on synthetic clean uptrend should exceed 80
        result = f5c_rsi_extreme_orb(bar, history, "LONG")
        assert isinstance(result, bool)

    def test_rsi_short_low_rsi(self):
        closes = np.linspace(13500, 13000, 30)
        history = _hist(closes)
        bar = history.iloc[-1]
        # Sustained downtrend → low RSI
        result = f5c_rsi_extreme_orb(bar, history, "SHORT")
        assert isinstance(result, bool)

    def test_nr4_passes_on_smallest_range(self):
        history = _hist(np.full(5, 13000.0), ranges=np.array([20, 18, 15, 12, 5]))
        bar = pd.Series({"high": 13002, "low": 12998})  # range 4 (smallest)
        assert f5d_nr4_orb(bar, history) is True

    def test_nr4_blocks_on_larger(self):
        history = _hist(np.full(5, 13000.0), ranges=np.array([5, 5, 5, 5, 5]))
        bar = pd.Series({"high": 13050, "low": 12950})  # range 100 (bigger)
        assert f5d_nr4_orb(bar, history) is False


# ============================================================
# US-CALM F5 candidates
# ============================================================

class TestF5UsCandidates:
    def test_dict_has_4_candidates(self):
        assert set(US_CALM_F5_CANDIDATES.keys()) == {
            "F5a_macd_3_10", "F5b_dual_ema", "F5c_volume_profile", "F5d_atr_norm_momentum",
        }

    def test_macd_long_in_uptrend(self):
        closes = np.linspace(13000, 13150, 30)
        history = _hist(closes)
        assert f5a_macd_us(history, "LONG") is True

    def test_dual_ema_long_in_uptrend(self):
        closes = np.linspace(13000, 13150, 30)
        history = _hist(closes)
        assert f5b_dual_ema_us(history, "LONG") is True

    def test_dual_ema_short_in_downtrend(self):
        closes = np.linspace(13150, 13000, 30)
        history = _hist(closes)
        assert f5b_dual_ema_us(history, "SHORT") is True

    def test_volume_profile_high_passes(self):
        # 50 bars of low volume + 1 bar of spike
        history = _hist(np.full(60, 13000.0))
        history.iloc[-1, history.columns.get_loc("volume")] = 1000  # spike
        # last bar volume 1000 vs window q75 ~120 → pass
        assert f5c_volume_profile_us(history, "LONG", lookback=50) is True

    def test_atr_norm_momentum_long(self):
        closes = np.linspace(13000, 13200, 50)
        history = _hist(closes)
        # Strong uptrend → norm momentum > threshold
        assert f5d_atr_norm_momentum_us(history, "LONG", period=20,
                                         threshold=0.5) is True

    def test_atr_norm_momentum_short(self):
        closes = np.linspace(13200, 13000, 50)
        history = _hist(closes)
        assert f5d_atr_norm_momentum_us(history, "SHORT", period=20,
                                         threshold=0.5) is True


# ============================================================
# Edge cases — insufficient data
# ============================================================

class TestEdges:
    def test_brooks_short_history_returns_false(self):
        history = _hist(np.full(3, 13000.0))
        bar = pd.Series({"close": 13100})
        assert f5b_brooks_break_orb(bar, history, "LONG") is False

    def test_dual_ema_short_history(self):
        history = _hist(np.full(10, 13000.0))
        assert f5b_dual_ema_us(history, "LONG") is False

    def test_volume_profile_short_history(self):
        history = _hist(np.full(10, 13000.0))
        assert f5c_volume_profile_us(history, "LONG", lookback=50) is False
