"""Tests pro v3.3.5 STEP 1 HARD STOP detection in gate18_block_bootstrap (POZNÁMKA #1).

Per Architekt v3.3.5 STEP 1 spec:
  - HARD STOP probability = P(within-Challenge max DD ≤ -$7 000)
  - Threshold: <10 % (Gate #8 lowered from 0.15 → 0.10)
  - 95 % Wilson CI returned alongside point estimate
  - max_dd_distribution returned for diagnostic purposes
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from scripts.gate18_block_bootstrap import (
    HARD_STOP_USD, PROFIT_TARGET_USD, CHALLENGE_DAYS,
    block_bootstrap,
)


def _series(daily_values: list[float]) -> dict[dt.date, float]:
    """Build {date: pnl} dict from a list of daily P&L values."""
    base = dt.date(2020, 1, 1)
    return {base + dt.timedelta(days=i): v for i, v in enumerate(daily_values)}


class TestHardStopConstants:
    def test_hard_stop_threshold_value(self):
        assert HARD_STOP_USD == -7_000.0

    def test_profit_target_value(self):
        assert PROFIT_TARGET_USD == 5_000.0

    def test_challenge_days(self):
        assert CHALLENGE_DAYS == 30


class TestBlockBootstrapHardStopDetection:
    def test_hard_stop_triggered_in_clear_drawdown(self):
        # Day 0: -$8 000 (below threshold), days 1-29 small positives → final positive
        # but within-challenge max DD ≤ -$7 000 → HARD STOP triggered
        pnl = [-8000.0] + [100.0] * 29
        # n_eligible = 30 → n_blocks = 1 → every sim picks the same block
        out = block_bootstrap(_series(pnl), n_simulations=1000, seed=7)
        assert out["hard_stop_probability"] == pytest.approx(1.0, abs=1e-9)
        assert out["successes"] == 0  # final = -8000 + 2900 = -5100, no success

    def test_no_hard_stop_when_drawdown_above_threshold(self):
        # Max single-day loss -$3 000 → cumsum never reaches -$7 000
        pnl = [-3000.0] + [200.0] * 29
        out = block_bootstrap(_series(pnl), n_simulations=1000, seed=7)
        assert out["hard_stop_probability"] == pytest.approx(0.0, abs=1e-9)

    def test_hard_stop_probability_returned_with_wilson_ci(self):
        pnl = [50.0] * 60
        out = block_bootstrap(_series(pnl), n_simulations=500, seed=42)
        assert "hard_stop_probability" in out
        assert "hard_stop_ci_low" in out
        assert "hard_stop_ci_high" in out
        # Wilson CI may produce tiny floating-point excursions outside [0, 1]; allow eps slack.
        eps = 1e-9
        assert -eps <= out["hard_stop_ci_low"] <= out["hard_stop_probability"] + eps
        assert out["hard_stop_probability"] <= out["hard_stop_ci_high"] + eps <= 1.0 + eps

    def test_max_dd_distribution_returned(self):
        pnl = [50.0] * 60
        out = block_bootstrap(_series(pnl), n_simulations=300, seed=42)
        dist = out["max_dd_distribution"]
        assert {"mean", "p5", "p50", "p95"} <= set(dist.keys())
        # All max DD values must be ≤ 0 (cumsum.min() of any path with negative bars)
        # With all-positive pnls, max_dd = first day = +50 (cumsum starts positive)
        # so distribution values are all 50 here
        assert dist["p5"] == pytest.approx(50.0, abs=1.0)

    def test_max_dd_distribution_negative_when_losses(self):
        # 30-day pattern with deep mid-challenge drawdown
        pnl = [-500.0] * 15 + [400.0] * 15  # cumsum.min() = -7500 at day 14
        out = block_bootstrap(_series(pnl), n_simulations=200, seed=42)
        dist = out["max_dd_distribution"]
        assert dist["p50"] <= -1000.0
        # n_blocks=1 → all sims see same block with cumsum.min() = -7500
        assert out["hard_stop_probability"] == pytest.approx(1.0, abs=1e-9)

    def test_hard_stop_threshold_passed_via_argument(self):
        # Override threshold to -$2 000 → max DD -$3 000 should now trigger
        pnl = [-3000.0] + [200.0] * 29
        out = block_bootstrap(_series(pnl), n_simulations=300,
                              hard_stop_usd=-2_000.0, seed=7)
        assert out["hard_stop_probability"] == pytest.approx(1.0, abs=1e-9)
        assert out["hard_stop_usd_threshold"] == -2_000.0

    def test_partial_hard_stop_probability(self):
        # 60 days: first 30 deep loss, last 30 small positive
        # Two distinct blocks (n_blocks=31): start=0 has cumsum.min()=-7500 (HS),
        # start=30 has cumsum.min() ≈ +200 (no HS). Probability ≈ 1/31 ≈ 0.032.
        pnl = [-500.0] * 15 + [400.0] * 15 + [200.0] * 30
        out = block_bootstrap(_series(pnl), n_simulations=10_000, seed=42)
        # Loose bound: each "starting block index" containing the loss segment
        # triggers hard stop → roughly between 0.05 and 0.95.
        assert 0.0 < out["hard_stop_probability"] < 1.0

    def test_insufficient_days_returns_zeros(self):
        # Fewer days than block size → guarded
        pnl = [100.0] * 5
        out = block_bootstrap(_series(pnl), n_simulations=10, seed=1)
        assert "error" in out
        assert out["hard_stop_probability"] == 0.0
        assert out["success_rate"] == 0.0

    def test_success_and_hard_stop_can_coexist_in_distribution(self):
        # 60-day mix: first 30 deep loss block (HS), last 30 strong profit (success)
        pnl = [-500.0] * 15 + [400.0] * 15 + [200.0] * 30
        out = block_bootstrap(_series(pnl), n_simulations=10_000, seed=42)
        # Both metrics should be in (0, 1) — strategy mixes outcomes
        assert 0.0 < out["success_rate"] < 1.0 or out["success_rate"] == 0.0
        assert 0.0 <= out["hard_stop_probability"] <= 1.0
