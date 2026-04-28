"""Tests pro scripts.gate18_block_bootstrap."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from scripts.gate18_block_bootstrap import (
    block_bootstrap, classify, CHALLENGE_DAYS, PROFIT_TARGET_USD,
)


def _synthetic_pnl(n_days=200, mean=50.0, std=200.0, seed=42):
    rng = np.random.default_rng(seed)
    base = dt.date(2020, 1, 1)
    return {
        base + dt.timedelta(days=i): float(rng.normal(mean, std))
        for i in range(n_days)
    }


class TestBlockBootstrap:
    def test_returns_required_keys(self):
        d = _synthetic_pnl(200)
        s = block_bootstrap(d, n_simulations=500, block_size=30, seed=1)
        assert "success_rate" in s
        assert "successes" in s
        assert "n_blocks" in s
        assert s["n_eligible_days"] == 200

    def test_insufficient_days_returns_error(self):
        d = _synthetic_pnl(20)  # < block_size=30
        s = block_bootstrap(d, n_simulations=100, block_size=30, seed=1)
        assert "error" in s
        assert s["success_rate"] == 0.0

    def test_high_mean_yields_high_success(self):
        # +500/day for 30 days = +15K, well above 5K target
        d = _synthetic_pnl(200, mean=500.0, std=50.0)
        s = block_bootstrap(d, n_simulations=500, block_size=30, seed=2)
        assert s["success_rate"] > 0.99

    def test_low_mean_yields_low_success(self):
        # -10/day = expected -300/30day
        d = _synthetic_pnl(200, mean=-10.0, std=50.0)
        s = block_bootstrap(d, n_simulations=500, block_size=30, seed=3)
        assert s["success_rate"] < 0.05

    def test_block_size_param(self):
        d = _synthetic_pnl(200)
        s = block_bootstrap(d, n_simulations=300, block_size=50, seed=4)
        assert s["block_size"] == 50
        assert s["n_blocks"] == 200 - 50 + 1

    def test_distribution_keys(self):
        d = _synthetic_pnl(200, mean=20.0)
        s = block_bootstrap(d, n_simulations=500, block_size=30, seed=5)
        dist = s["final_pnl_distribution"]
        for k in ("mean", "median", "p5", "p25", "p75", "p95"):
            assert k in dist


class TestClassify:
    def test_pass_at_70(self):
        assert classify(0.71) == "PASS"
        assert classify(0.70) == "PASS"

    def test_warning_60_to_70(self):
        assert classify(0.65) == "WARNING"
        assert classify(0.60) == "WARNING"

    def test_fail_below_60(self):
        assert classify(0.59) == "FAIL"
        assert classify(0.30) == "FAIL"


def test_constants():
    assert CHALLENGE_DAYS == 30
    assert PROFIT_TARGET_USD == 5000.0
