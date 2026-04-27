"""Integration test pro v3.3.1 — engine + classifier + setupy v331 na 1 týdnu real data."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARQUET = ROOT / "data" / "historical" / "GER40_5m_2019-2023.parquet"


@pytest.mark.skipif(not PARQUET.exists(), reason="parquet not yet built")
def test_v331_engine_runs_on_2020_01_week_no_crash():
    """End-to-end: load 2019-2023 parquet, slice 2020-01-13..17, run engine v331.

    Smoke goal: engine doesn't crash, no V7 invariant violations.
    Trade count is regime-dependent — may be 0 if regime UNDEFINED most days
    (insufficient warmup for ATR MA100 in early week).
    """
    from src.strategy.data_feed import BarFeed
    from backtest.engine import run_backtest
    feed = BarFeed.from_parquet(PARQUET)
    week = feed.range("2020-01-13", "2020-01-18")
    res = run_backtest(week, use_v331=True)
    # No invariant violations
    assert res.invariant_violations == [], \
        f"V7 violations: {res.invariant_violations}"
    # Engine produced a valid BacktestResult
    assert hasattr(res, "trades")
    assert hasattr(res, "stats")
    stats = res.stats()
    assert isinstance(stats, dict)


@pytest.mark.skipif(not PARQUET.exists(), reason="parquet not yet built")
def test_v331_with_full_history_warmup():
    """Same week but feed includes all prior history → regime can warmup."""
    from src.strategy.data_feed import BarFeed
    from backtest.engine import run_backtest
    feed = BarFeed.from_parquet(PARQUET)
    # Feed entire 2019-2020 range to engine; will only trade 1 day from internal
    # session windows but regime classifier has 100+ days of warmup
    sub = feed.range("2019-01-01", "2020-01-18")
    res = run_backtest(sub, use_v331=True)
    assert res.invariant_violations == []
