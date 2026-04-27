"""Tests pro src.backtest.extended_ablation helpers."""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.backtest.extended_ablation import (
    wilson_ci, bootstrap_ci, fdr_bh, bonferroni,
    sample_size_flag, oos_validate, cell_distribution,
    sharpe_ratio, profit_factor, expectancy, expectancy_pvalue,
)


# ============================================================
# Wilson CI
# ============================================================

class TestWilsonCI:
    def test_zero_n_returns_full_range(self):
        assert wilson_ci(0, 0) == (0.0, 1.0)

    def test_50_50_centered_around_p(self):
        lo, hi = wilson_ci(50, 100)
        assert 0.4 < lo < 0.5
        assert 0.5 < hi < 0.6
        # Center close to 0.5
        assert abs(((lo + hi) / 2) - 0.5) < 0.01

    def test_zero_successes(self):
        lo, hi = wilson_ci(0, 100)
        assert lo == pytest.approx(0.0, abs=1e-10)
        assert hi < 0.1  # tight upper bound

    def test_full_successes(self):
        lo, hi = wilson_ci(100, 100)
        assert hi == 1.0
        assert lo > 0.95


# ============================================================
# Bootstrap CI
# ============================================================

class TestBootstrapCI:
    def test_constant_data_zero_width(self):
        lo, hi = bootstrap_ci([5.0] * 50, n_iter=200, seed=0)
        assert lo == 5.0 and hi == 5.0

    def test_normal_data_brackets_mean(self):
        rng = np.random.default_rng(0)
        data = rng.normal(loc=10, scale=2, size=200).tolist()
        lo, hi = bootstrap_ci(data, n_iter=500, seed=1)
        # 95% CI for mean should bracket the true mean (10) with high prob
        assert lo < 10 < hi
        # CI width ~ 2 × 1.96 × σ/√n = ~0.55
        assert 0.3 < hi - lo < 1.2

    def test_short_data_collapses(self):
        lo, hi = bootstrap_ci([1.0], n_iter=100, seed=0)
        assert lo == hi == 1.0

    def test_empty_data(self):
        lo, hi = bootstrap_ci([], n_iter=100, seed=0)
        assert lo == hi == 0.0

    def test_custom_statistic_median(self):
        data = list(range(100))
        lo, hi = bootstrap_ci(data, n_iter=300, statistic=np.median, seed=2)
        # True median is 49.5; bootstrap should bracket it
        assert lo < 50 < hi


# ============================================================
# FDR (Benjamini-Hochberg)
# ============================================================

class TestFDR:
    def test_all_significant_pvalues(self):
        p = [0.001, 0.002, 0.003, 0.004]
        rej = fdr_bh(p, alpha=0.05)
        assert rej.all()

    def test_none_significant(self):
        p = [0.5, 0.6, 0.7, 0.8]
        rej = fdr_bh(p, alpha=0.05)
        assert not rej.any()

    def test_partial_significance(self):
        # 3 small p-values + 7 large
        p = [0.001, 0.005, 0.01] + [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99]
        rej = fdr_bh(p, alpha=0.05)
        # First 3 should be rejected; rest not
        assert rej[:3].all()
        assert not rej[3:].any()

    def test_empty(self):
        rej = fdr_bh([], alpha=0.05)
        assert len(rej) == 0


class TestBonferroni:
    def test_strict_threshold(self):
        # n=10, alpha 0.05 / 10 = 0.005 threshold
        p = [0.001, 0.004, 0.006, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        rej = bonferroni(p, alpha=0.05)
        # Only first 2 (p ≤ 0.005) should pass
        assert rej[0] and rej[1]
        assert not rej[2:].any()

    def test_empty(self):
        rej = bonferroni([], alpha=0.05)
        assert len(rej) == 0


# ============================================================
# Sample size flag
# ============================================================

class TestSampleFlag:
    def test_primary(self):
        assert sample_size_flag(100) == "PRIMARY"
        assert sample_size_flag(500) == "PRIMARY"

    def test_warning(self):
        assert sample_size_flag(50) == "WARNING"
        assert sample_size_flag(99) == "WARNING"

    def test_reject(self):
        assert sample_size_flag(0) == "REJECT"
        assert sample_size_flag(49) == "REJECT"


# ============================================================
# OOS validation
# ============================================================

class TestOOS:
    def test_pass_above_threshold(self):
        r = oos_validate(train_expectancy=10.0, test_expectancy=8.0,
                          threshold_ratio=0.7)
        assert r.pass_
        assert "≥" in r.reason

    def test_fail_below_threshold(self):
        r = oos_validate(train_expectancy=10.0, test_expectancy=5.0,
                          threshold_ratio=0.7)
        assert not r.pass_

    def test_train_zero_or_negative_fails(self):
        r = oos_validate(0.0, 5.0)
        assert not r.pass_
        assert "no in-sample edge" in r.reason

    def test_test_negative_fails(self):
        r = oos_validate(10.0, -2.0)
        assert not r.pass_
        assert "negative OOS" in r.reason


# ============================================================
# Cell distribution
# ============================================================

def test_cell_distribution_simple():
    pnls = [10, 20, -5, 30, -10, 15]
    d = cell_distribution(pnls)
    assert d.n == 6
    assert d.mean == pytest.approx(60 / 6)
    assert d.max_dd <= 0


def test_cell_distribution_empty():
    d = cell_distribution([])
    assert d.n == 0
    assert d.max_dd == 0


# ============================================================
# Sharpe / PF / Expectancy
# ============================================================

def test_sharpe_constant_zero_std():
    assert sharpe_ratio([5.0] * 10) == 0.0


def test_profit_factor_basic():
    assert profit_factor([10, -5]) == 2.0


def test_profit_factor_no_losses():
    assert math.isinf(profit_factor([10, 5]))


def test_expectancy_zero():
    assert expectancy([]) == 0


def test_expectancy_pvalue_positive_mean():
    p = expectancy_pvalue([1, 2, 3, 4, 5])
    assert p < 0.05


def test_expectancy_pvalue_zero_centered():
    # Use exactly zero-centered data (no random) → p ≈ 0.5
    p = expectancy_pvalue([1.0, -1.0] * 50)  # mean exactly 0
    assert 0.4 < p < 0.6


def test_expectancy_pvalue_negative_mean_high():
    # Strong negative trend → one-sided p (mean > 0) should be very high
    p = expectancy_pvalue([-5, -3, -7, -2, -4, -6])
    assert p > 0.9
