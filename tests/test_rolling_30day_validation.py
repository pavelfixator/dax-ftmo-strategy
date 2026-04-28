"""Tests pro scripts.rolling_30day_validation."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from scripts.rolling_30day_validation import (
    rolling_eligible_counts, decision, DEFAULT_THRESHOLD_DAYS,
)
from src.strategy.regime import Regime


def _build(seq):
    """seq = list of regimes for consecutive days starting 2020-01-01."""
    return {
        dt.date(2020, 1, 1) + dt.timedelta(days=i): r
        for i, r in enumerate(seq)
    }


class TestRollingCounts:
    def test_all_undefined_zero_eligible(self):
        m = _build([Regime.UNDEFINED] * 60)
        rolling = rolling_eligible_counts(m, window_days=30)
        assert (rolling["eligible_days"] == 0).all()

    def test_all_trend_full_window(self):
        m = _build([Regime.TREND] * 60)
        rolling = rolling_eligible_counts(m, window_days=30)
        # First windows have 30 days available, last few less
        assert rolling["eligible_days"].iloc[0] == 30
        assert rolling["eligible_days"].iloc[-1] >= 1

    def test_mixed(self):
        # 30 TREND + 30 UNDEFINED
        m = _build([Regime.TREND] * 30 + [Regime.UNDEFINED] * 30)
        rolling = rolling_eligible_counts(m, window_days=30)
        # Day 0 window covers 30 TREND days
        assert rolling.loc[rolling["window_start"] == dt.date(2020, 1, 1),
                           "eligible_days"].iloc[0] == 30
        # Day 30 window covers 30 UNDEFINED days
        assert rolling.loc[rolling["window_start"] == dt.date(2020, 1, 31),
                           "eligible_days"].iloc[0] == 0


class TestDecision:
    def test_pass_threshold_below_5pct(self):
        # 100 windows, 4 fails = 4 % → PASS
        df = pd.DataFrame({"eligible_days": [10] * 96 + [3] * 4,
                            "window_start": [dt.date(2020, 1, 1)] * 100})
        d = decision(df, threshold_days=DEFAULT_THRESHOLD_DAYS)
        assert d["verdict"] == "PASS"
        assert d["fail_pct"] == 4.0

    def test_warning_band_5_to_15(self):
        df = pd.DataFrame({"eligible_days": [10] * 90 + [3] * 10,
                            "window_start": [dt.date(2020, 1, 1)] * 100})
        d = decision(df, threshold_days=DEFAULT_THRESHOLD_DAYS)
        assert d["verdict"] == "WARNING"
        assert d["fail_pct"] == 10.0

    def test_requires_adjustment_above_15(self):
        df = pd.DataFrame({"eligible_days": [10] * 70 + [3] * 30,
                            "window_start": [dt.date(2020, 1, 1)] * 100})
        d = decision(df, threshold_days=DEFAULT_THRESHOLD_DAYS)
        assert d["verdict"] == "REQUIRES ADJUSTMENT"
        assert d["fail_pct"] == 30.0

    def test_empty_returns_empty_verdict(self):
        d = decision(pd.DataFrame())
        assert d["verdict"] == "EMPTY"
