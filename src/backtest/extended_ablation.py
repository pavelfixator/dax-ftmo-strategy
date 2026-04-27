"""Extended ablation statistical helpers — bootstrap CI, Wilson CI, FDR, OOS.

Used by `scripts/run_extended_ablation.py` (Sekce 4 runtime).

Spec: Strategy v3.3.1 §Extended Ablation + Red Team Dodatek 1 (multiple
comparisons correction).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import numpy as np

# scipy.stats is already in deps; statsmodels for FDR
try:
    from scipy.stats import norm
except ImportError:  # pragma: no cover
    norm = None

try:
    from statsmodels.stats.multitest import multipletests
except ImportError:  # pragma: no cover
    multipletests = None


# ============================================================
# Wilson 95% CI for binomial proportion (WR)
# ============================================================

def wilson_ci(successes: int, n: int, ci: float = 0.95) -> tuple[float, float]:
    """Wilson score interval. Returns (lower, upper)."""
    if n <= 0:
        return (0.0, 1.0)
    if norm is None:
        raise RuntimeError("scipy.stats.norm not available")
    z = float(norm.ppf((1 + ci) / 2))
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


# ============================================================
# Bootstrap percentile CI
# ============================================================

def bootstrap_ci(data: Sequence[float], n_iter: int = 1000, ci: float = 0.95,
                 statistic: Callable[[np.ndarray], float] = np.mean,
                 seed: Optional[int] = None) -> tuple[float, float]:
    """Bootstrap percentile CI for a statistic over `data`.

    Returns (lower, upper). Returns (statistic(data), statistic(data)) if data
    has fewer than 2 elements.
    """
    arr = np.asarray(data, dtype=float)
    if len(arr) < 2:
        v = float(statistic(arr)) if len(arr) else 0.0
        return (v, v)
    rng = np.random.default_rng(seed)
    boots = np.empty(n_iter, dtype=float)
    for i in range(n_iter):
        sample = rng.choice(arr, size=len(arr), replace=True)
        boots[i] = float(statistic(sample))
    lower = float(np.percentile(boots, 100 * (1 - ci) / 2))
    upper = float(np.percentile(boots, 100 * (1 + ci) / 2))
    return (lower, upper)


# ============================================================
# FDR (Benjamini-Hochberg)
# ============================================================

def fdr_bh(pvalues: Sequence[float], alpha: float = 0.05) -> np.ndarray:
    """Benjamini-Hochberg FDR.

    Returns boolean array (rejected = True). Uses statsmodels if available,
    fallback to manual implementation.
    """
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    if n == 0:
        return np.zeros(0, dtype=bool)
    if multipletests is not None:
        rejected, _, _, _ = multipletests(p, alpha=alpha, method="fdr_bh")
        return rejected
    # Fallback manual
    order = np.argsort(p)
    sorted_p = p[order]
    threshold = alpha * np.arange(1, n + 1) / n
    significant_sorted = sorted_p <= threshold
    if not significant_sorted.any():
        return np.zeros(n, dtype=bool)
    last_sig = int(np.where(significant_sorted)[0].max())
    rejected_sorted = np.zeros(n, dtype=bool)
    rejected_sorted[: last_sig + 1] = True
    rejected = np.zeros(n, dtype=bool)
    rejected[order] = rejected_sorted
    return rejected


def bonferroni(pvalues: Sequence[float], alpha: float = 0.05) -> np.ndarray:
    """Bonferroni — alpha / n threshold. Secondary check per Pavel spec."""
    p = np.asarray(pvalues, dtype=float)
    n = len(p)
    if n == 0:
        return np.zeros(0, dtype=bool)
    return p <= (alpha / n)


# ============================================================
# Cell sample size flag
# ============================================================

def sample_size_flag(n: int) -> str:
    """PRIMARY ≥100 / WARNING 50-99 / REJECT <50 per Pavel spec."""
    if n >= 100:
        return "PRIMARY"
    if n >= 50:
        return "WARNING"
    return "REJECT"


# ============================================================
# Out-of-sample validation
# ============================================================

@dataclass(frozen=True)
class OOSResult:
    train_expectancy: float
    test_expectancy: float
    threshold: float  # min ratio test/train
    pass_: bool       # True if test ≥ threshold × train
    reason: str


def oos_validate(train_expectancy: float, test_expectancy: float,
                  threshold_ratio: float = 0.7) -> OOSResult:
    """OOS validation per spec: test ≥ 0.7 × train expectancy.

    Edge cases:
      - train_expectancy ≤ 0 → fail (no edge in train set, can't validate)
      - test_expectancy < 0 → fail (negative OOS = no edge)
    """
    if train_expectancy <= 0:
        return OOSResult(
            train_expectancy=train_expectancy,
            test_expectancy=test_expectancy,
            threshold=threshold_ratio,
            pass_=False,
            reason=f"train expectancy {train_expectancy:.4f} ≤ 0 (no in-sample edge)",
        )
    if test_expectancy <= 0:
        return OOSResult(
            train_expectancy=train_expectancy,
            test_expectancy=test_expectancy,
            threshold=threshold_ratio,
            pass_=False,
            reason=f"test expectancy {test_expectancy:.4f} ≤ 0 (negative OOS)",
        )
    ratio = test_expectancy / train_expectancy
    if ratio >= threshold_ratio:
        return OOSResult(
            train_expectancy=train_expectancy,
            test_expectancy=test_expectancy,
            threshold=threshold_ratio,
            pass_=True,
            reason=f"OOS ratio {ratio:.2%} ≥ {threshold_ratio:.0%}",
        )
    return OOSResult(
        train_expectancy=train_expectancy,
        test_expectancy=test_expectancy,
        threshold=threshold_ratio,
        pass_=False,
        reason=f"OOS ratio {ratio:.2%} < {threshold_ratio:.0%}",
    )


# ============================================================
# Per-cell distribution metrics (median, P25, P75, std, max DD)
# ============================================================

@dataclass
class CellDistribution:
    n: int
    mean: float
    median: float
    p25: float
    p75: float
    std: float
    max_dd: float


def cell_distribution(pnls: Sequence[float]) -> CellDistribution:
    arr = np.asarray(pnls, dtype=float)
    if len(arr) == 0:
        return CellDistribution(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    return CellDistribution(
        n=len(arr),
        mean=float(arr.mean()),
        median=float(np.median(arr)),
        p25=float(np.percentile(arr, 25)),
        p75=float(np.percentile(arr, 75)),
        std=float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
        max_dd=float(dd.min()),
    )


# ============================================================
# Sharpe / Profit Factor / Expectancy
# ============================================================

def sharpe_ratio(pnls: Sequence[float], periods_per_year: int = 252) -> float:
    arr = np.asarray(pnls, dtype=float)
    if len(arr) < 2 or arr.std(ddof=1) == 0:
        return 0.0
    return float(arr.mean() / arr.std(ddof=1) * math.sqrt(periods_per_year))


def profit_factor(pnls: Sequence[float]) -> float:
    arr = np.asarray(pnls, dtype=float)
    wins = arr[arr > 0].sum()
    losses = -arr[arr < 0].sum()
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


def expectancy(pnls: Sequence[float]) -> float:
    arr = np.asarray(pnls, dtype=float)
    if len(arr) == 0:
        return 0.0
    return float(arr.mean())


def expectancy_pvalue(pnls: Sequence[float]) -> float:
    """One-sided t-test: H0 mean=0. Returns p-value for mean > 0."""
    from scipy.stats import ttest_1samp
    arr = np.asarray(pnls, dtype=float)
    if len(arr) < 2 or arr.std(ddof=1) == 0:
        return 1.0
    t, p_two = ttest_1samp(arr, 0.0)
    if t > 0:
        return float(p_two / 2)
    return float(1 - p_two / 2)
