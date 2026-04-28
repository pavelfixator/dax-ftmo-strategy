"""F5_CALM=MACD OOS validation pre v3.3.4 conditional restore.

Train: 2015-01-01 → 2022-12-31 (in-sample, ~70% of window)
Test:  2023-01-01 → 2026-04-01 (OOS,        ~30% of window)

Compute US-MOM CALM expectancy with F5_CALM=MACD active in both periods.
Decision tree (per Pavel v3.3.4):
  test_exp ≥ 0.7 × train_exp → PASS (revert MACD)
  0.5 ≤ ratio < 0.7         → MARGINAL (revert s WARNING)
  ratio < 0.5               → FAIL (drop US-MOM CALM cell)

Output: experiments/exp_macd_oos.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.data_feed import BarFeed
from src.strategy.regime import Regime
from src.strategy.setups.orb_dax import aggregate_daily
from backtest.engine import _aggregate_h4
from scripts.run_extended_ablation import (
    build_regime_cache, evaluate_cell, cell_metrics,
)
from src.backtest.extended_ablation import expectancy

OUT = ROOT / "experiments" / "exp_macd_oos.md"
EXTENDED_PARQUET = ROOT / "data" / "historical" / "GER40_5m_2015-2026.parquet"

TRAIN_START = "2015-01-01"
TRAIN_END = "2023-01-01"        # exclusive (= 2022-12-31 inclusive)
TEST_START = "2023-01-01"
TEST_END = "2026-04-01"

PASS_RATIO = 0.7
MARGINAL_RATIO = 0.5


def evaluate_period(feed: BarFeed, daily_history, regime_cache, start: str, end: str):
    sub = feed.range(start, end)
    df = sub.to_dataframe()
    cet_dates = pd.Series([t.tz_convert("Europe/Berlin").date() for t in df.index],
                           index=df.index)
    raw = evaluate_cell("us_momentum", Regime.CALM, set(),
                         df, daily_history, regime_cache, cet_dates)
    pnls = raw["pnls_pts"]
    exp = expectancy(pnls)
    return {
        "n_trades": len(pnls),
        "expectancy": exp,
        "wr": (sum(1 for p in pnls if p > 0) / len(pnls)) if pnls else 0.0,
        "total_pts": sum(pnls),
    }


def classify(train: dict, test: dict) -> dict:
    if train["expectancy"] <= 0:
        return {"verdict": "FAIL", "reason": "train expectancy <= 0",
                "ratio": None}
    if test["expectancy"] <= 0:
        return {"verdict": "FAIL", "reason": "test expectancy <= 0 (OOS negative)",
                "ratio": test["expectancy"] / train["expectancy"]}
    ratio = test["expectancy"] / train["expectancy"]
    if ratio >= PASS_RATIO:
        return {"verdict": "PASS",
                "reason": f"ratio {ratio:.2%} >= {int(PASS_RATIO*100)}%", "ratio": ratio}
    if ratio >= MARGINAL_RATIO:
        return {"verdict": "MARGINAL",
                "reason": f"ratio {ratio:.2%} in [{int(MARGINAL_RATIO*100)}%, {int(PASS_RATIO*100)}%)",
                "ratio": ratio}
    return {"verdict": "FAIL",
            "reason": f"ratio {ratio:.2%} < {int(MARGINAL_RATIO*100)}%", "ratio": ratio}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", type=Path, default=EXTENDED_PARQUET)
    a = p.parse_args()
    if not a.parquet.exists():
        print(f"parquet not found: {a.parquet}", file=sys.stderr)
        return 1
    print(f"[macd_oos] loading {a.parquet}")
    feed = BarFeed.from_parquet(a.parquet)
    df = feed.to_dataframe()
    print(f"[macd_oos] full range: {feed.first} .. {feed.last}, {len(df)} bars")
    daily = aggregate_daily(df)
    h4 = _aggregate_h4(df)
    print("[macd_oos] building regime cache")
    regime_cache = build_regime_cache(df, daily, h4)

    print(f"[macd_oos] eval TRAIN ({TRAIN_START}..{TRAIN_END})")
    train = evaluate_period(feed, daily, regime_cache, TRAIN_START, TRAIN_END)
    print(f"  train: n={train['n_trades']} WR={train['wr']:.2%} "
          f"exp={train['expectancy']:+.2f} pts total={train['total_pts']:+.0f}")

    print(f"[macd_oos] eval TEST  ({TEST_START}..{TEST_END})")
    test = evaluate_period(feed, daily, regime_cache, TEST_START, TEST_END)
    print(f"  test:  n={test['n_trades']} WR={test['wr']:.2%} "
          f"exp={test['expectancy']:+.2f} pts total={test['total_pts']:+.0f}")

    verdict = classify(train, test)
    print(f"\n[macd_oos] VERDICT: {verdict['verdict']} ({verdict['reason']})")

    lines = [
        "# F5_CALM=MACD OOS Validation — v3.3.4",
        "",
        f"**Verdict: {verdict['verdict']}**",
        "",
        f"Reason: {verdict['reason']}",
        "",
        "## Setup",
        f"- Cell: us_momentum / CALM with F5_CALM=MACD active",
        f"- Train period: {TRAIN_START} .. {TRAIN_END} (exclusive)",
        f"- Test period:  {TEST_START} .. {TEST_END}",
        "",
        "## Per-period metrics",
        "",
        "| period | n_trades | WR | expectancy | total pts |",
        "|---|---:|---:|---:|---:|",
        f"| train | {train['n_trades']} | {train['wr']:.2%} | {train['expectancy']:+.2f} | {train['total_pts']:+.0f} |",
        f"| test  | {test['n_trades']}  | {test['wr']:.2%}  | {test['expectancy']:+.2f}  | {test['total_pts']:+.0f}  |",
        "",
        f"## Decision tree (Pavel v3.3.4)",
        f"- test_exp ≥ 0.7 × train_exp → **PASS** (revert MACD)",
        f"- 0.5 ≤ ratio < 0.7         → **MARGINAL** (revert s WARNING)",
        f"- ratio < 0.5               → **FAIL** (drop US-MOM CALM cell)",
        "",
        f"Ratio computed: **{verdict.get('ratio'):.4f}**" if verdict.get("ratio") is not None else "Ratio: N/A",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[macd_oos] -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
