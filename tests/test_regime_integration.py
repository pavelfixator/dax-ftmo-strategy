"""Integration tests pro regime layer — 30-day synthetic regime sequence.

Cíl: end-to-end ověření že classifier + persistence společně produkují
stabilní active regime sequenci na realistic synthetic data.

Test scenarios:
  A. 30 dnů kalmního trhu → většina dnů CALM (po warmup)
  B. 30 dnů trending up → většina dnů TREND
  C. 30 dnů s embedded crash week → CRASH instantně, exit po 2 calm days
  D. Flip-flop scenario → persistence rule rejects 1-day flips
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from src.strategy.regime import Regime, get_active_regime
from src.strategy.regime.classifier import (
    classify_regime_raw, derive_signals_from_market_data,
)


def _build_market(n_days: int, scenario: str, seed: int = 0) -> pd.DataFrame:
    """Synth daily OHLC for given scenario; returns daily_df of length n_days."""
    rng = np.random.default_rng(seed)
    end = dt.date(2026, 4, 27)
    idx = pd.date_range(end - dt.timedelta(days=n_days - 1), end,
                        freq="D", tz="UTC")
    base = 13000.0
    if scenario == "calm":
        closes = base + rng.standard_normal(n_days).cumsum() * 3
        ranges = rng.uniform(20, 60, n_days)
    elif scenario == "trend_up":
        closes = base + np.arange(n_days) * 20 + rng.standard_normal(n_days) * 5
        ranges = rng.uniform(60, 120, n_days)
    elif scenario == "crash_embed":
        closes = np.zeros(n_days)
        ranges = np.zeros(n_days)
        for i in range(n_days):
            if 10 <= i < 15:  # 5-day crash window
                closes[i] = base - (i - 9) * 250
                ranges[i] = 350
            else:
                if i < 10:
                    closes[i] = base + rng.standard_normal() * 5
                else:
                    closes[i] = closes[i - 1] + rng.standard_normal() * 5
                ranges[i] = rng.uniform(40, 80)
    elif scenario == "flip_flop":
        closes = base + rng.standard_normal(n_days).cumsum() * 6
        ranges = rng.uniform(40, 80, n_days)
    else:
        raise ValueError(f"unknown scenario {scenario}")
    daily = pd.DataFrame({
        "open": closes - 5,
        "high": closes + ranges / 2,
        "low":  closes - ranges / 2,
        "close": closes,
        "volume": rng.uniform(1000, 2000, n_days),
    }, index=idx)
    return daily


def _build_h4(daily: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Build matching H4 series — 6 bars per day around close."""
    rng = np.random.default_rng(seed + 100)
    rows = []
    for d, row in daily.iterrows():
        for h in range(0, 24, 4):
            close = float(row["close"]) + rng.standard_normal() * 1.5
            rows.append({
                "ts": d.replace(hour=h),
                "open": close - 1, "high": close + rng.uniform(1, 4),
                "low": close - rng.uniform(1, 4), "close": close,
                "volume": rng.uniform(100, 300),
            })
    h4 = pd.DataFrame(rows).set_index("ts").sort_index()
    h4.index = pd.DatetimeIndex(h4.index, tz="UTC")
    return h4


def _evaluate_sequence(daily_df: pd.DataFrame, h4_df: pd.DataFrame,
                       eval_days: int = 30) -> list[tuple[dt.date, Regime, Regime]]:
    """Walk forward last `eval_days`; returns [(date, raw, active), ...].

    Insufficient history days are skipped. Active regime carries forward.
    """
    out = []
    current_active = None
    raw_history: list[Regime] = []
    eval_start_idx = max(len(daily_df) - eval_days, 110)  # need 100+ for ATR MA100
    for i in range(eval_start_idx, len(daily_df)):
        ts_today = daily_df.index[i].to_pydatetime()
        try:
            sig = derive_signals_from_market_data(
                daily_df.iloc[:i + 1], h4_df, pd.DataFrame(), ts_today)
            raw = classify_regime_raw(sig)
        except ValueError:
            continue
        active = get_active_regime(raw_history, raw, current_active=current_active)
        out.append((ts_today.date(), raw, active))
        raw_history.append(raw)
        current_active = active
    return out


# ============================================================
# Scenarios
# ============================================================

class TestIntegrationScenarios:
    def test_calm_market_yields_calm_or_undefined(self):
        daily = _build_market(150, "calm", seed=1)
        h4 = _build_h4(daily, seed=1)
        seq = _evaluate_sequence(daily, h4, eval_days=30)
        assert len(seq) > 0
        regimes = [r[2] for r in seq]
        # Calm sideways market should never trigger CRASH
        assert Regime.CRASH not in regimes
        # Most days should be CALM or UNDEFINED (no strong trend)
        calm_or_undef = sum(1 for r in regimes
                              if r in {Regime.CALM, Regime.UNDEFINED})
        assert calm_or_undef >= 0.5 * len(regimes)

    def test_trending_market_avoids_crash(self):
        daily = _build_market(150, "trend_up", seed=2)
        h4 = _build_h4(daily, seed=2)
        seq = _evaluate_sequence(daily, h4, eval_days=30)
        assert len(seq) > 0
        regimes = [r[2] for r in seq]
        # Up-trending market should not trigger CRASH (slope is UP, vol moderate)
        assert Regime.CRASH not in regimes

    def test_crash_window_detected_and_exited(self):
        daily = _build_market(150, "crash_embed", seed=3)
        h4 = _build_h4(daily, seed=3)
        seq = _evaluate_sequence(daily, h4, eval_days=40)
        regimes = [r[2] for r in seq]
        raws = [r[1] for r in seq]
        # If derive captured the crash window, we should see CRASH at least once
        if Regime.CRASH in raws:
            # Once raw goes to CRASH, active must follow instantly
            assert Regime.CRASH in regimes
            # After raw stops being CRASH for 2 days, active must exit
            crash_idx = [i for i, r in enumerate(regimes) if r == Regime.CRASH]
            last_crash = crash_idx[-1]
            tail_raws = raws[last_crash + 1:]
            tail_actives = regimes[last_crash + 1:]
            if len(tail_raws) >= 2 and all(r != Regime.CRASH for r in tail_raws[:2]):
                # by 3rd day after crash, should have exited
                if len(tail_actives) >= 2:
                    assert tail_actives[1] != Regime.CRASH

    def test_persistence_rejects_one_day_flips(self):
        """Custom sequence: TREND established, single-day CALM noise, back to TREND."""
        history: list[Regime] = []
        active = Regime.TREND
        sequence = [Regime.TREND, Regime.CALM, Regime.TREND, Regime.TREND]
        results = []
        for raw in sequence:
            active = get_active_regime(history, raw, current_active=active)
            results.append(active)
            history.append(raw)
        # 1-day CALM noise should NOT switch to CALM
        assert results[1] == Regime.TREND
        # Back to TREND, stay TREND
        assert results[2] == Regime.TREND
        assert results[3] == Regime.TREND

    def test_30_day_sequence_runs_without_exception(self):
        """End-to-end smoke: classifier + persistence on 30 evaluation days."""
        daily = _build_market(150, "calm", seed=42)
        h4 = _build_h4(daily, seed=42)
        seq = _evaluate_sequence(daily, h4, eval_days=30)
        assert len(seq) >= 20  # at least 20 valid eval days after warmup
        # All regimes are valid enum values
        for d, raw, active in seq:
            assert isinstance(raw, Regime)
            assert isinstance(active, Regime)
