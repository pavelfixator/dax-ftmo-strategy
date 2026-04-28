"""Trend US-MOM stress test — v3.3.2.1 acceptance threshold.

Tests US-MOM TREND baseline with 4 scenarios of increased buffer (spread+slip):
  Baseline    spread 1.5 + slip 2.0 = 3.5 pts buffer
  Mild ×1.5    5.25 pts
  Pessimistic ×2.0  7.0 pts
  Extreme ×3.0     10.5 pts (informative)

For each scenario re-runs ablation cell us_momentum/TREND/baseline_F1234 and
reports expectancy.

Acceptance criteria (v3.3.2.1, updated from v3.3.2):
  Baseline      ≥ +3.3 pts → KEEP unchanged
  Mild stress   ≥ +1.5 pts → KEEP
  Pessimistic   ≥ +0.5 pts → KEEP with WARNING (was ≥0 in v3.3.2)
  Pessimistic   < +0.5 pts → DROP US-MOM TREND

Output: experiments/trend_stress_test.md
"""
from __future__ import annotations

import argparse
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

OUT_PATH = ROOT / "experiments" / "trend_stress_test.md"
EXTENDED_PARQUET = ROOT / "data" / "historical" / "GER40_5m_2015-2026.parquet"

# Baseline buffer = 3.5 pts (1.5 spread + 2.0 slippage). Stress multipliers:
SCENARIOS = [
    ("baseline",     1.0),
    ("mild_x1.5",    1.5),
    ("pessimistic_x2.0", 2.0),
    ("extreme_x3.0",     3.0),
]
BASELINE_BUFFER = 3.5

# Acceptance thresholds (v3.3.2.1)
THRESHOLD_BASELINE = 3.3
THRESHOLD_MILD = 1.5
THRESHOLD_PESSIMISTIC = 0.5    # UPDATED v3.3.2.1 (was 0.0 in v3.3.2)


def stress_evaluate(parquet: Path) -> list[dict]:
    """Re-run us_momentum TREND baseline with patched buffer per scenario.

    NOTE: this script demonstrates the framework. Full re-evaluation per
    scenario requires monkey-patching SLIPPAGE_AND_SPREAD in us_momentum_v331.
    For Sekce 6 Cast A scope we expose the framework + decision logic; full
    Monte-Carlo style stress is Cast B (full backtest overnight).
    """
    print(f"[stress] loading {parquet}")
    feed = BarFeed.from_parquet(parquet)
    df = feed.to_dataframe()
    daily = aggregate_daily(df)
    h4 = _aggregate_h4(df)
    cet_dates = pd.Series([t.tz_convert("Europe/Berlin").date() for t in df.index],
                           index=df.index)
    print("[stress] building regime cache")
    regime_cache = build_regime_cache(df, daily, h4)

    results = []
    import src.strategy.setups.us_momentum_v331 as usm
    original_buffer = usm.SLIPPAGE_AND_SPREAD
    try:
        for label, mult in SCENARIOS:
            usm.SLIPPAGE_AND_SPREAD = original_buffer * mult
            print(f"[stress] scenario={label} buffer={usm.SLIPPAGE_AND_SPREAD:.2f}")
            raw = evaluate_cell("us_momentum", Regime.TREND, set(),
                                 df, daily, regime_cache, cet_dates)
            m = cell_metrics(raw)
            results.append({
                "scenario": label, "multiplier": mult,
                "buffer_pts": usm.SLIPPAGE_AND_SPREAD,
                "n_trades": m["n_trades"],
                "wr": m["wr"],
                "expectancy": m["expectancy"],
                "sharpe": m["sharpe"],
                "max_dd": m["max_dd"],
            })
    finally:
        usm.SLIPPAGE_AND_SPREAD = original_buffer
    return results


def classify(results: list[dict]) -> dict:
    by_label = {r["scenario"]: r for r in results}
    base = by_label.get("baseline", {}).get("expectancy", 0)
    mild = by_label.get("mild_x1.5", {}).get("expectancy", 0)
    pess = by_label.get("pessimistic_x2.0", {}).get("expectancy", 0)
    if pess < THRESHOLD_PESSIMISTIC:
        verdict = "DROP US-MOM TREND"
    elif pess < 0:
        verdict = "DROP US-MOM TREND"
    elif mild < THRESHOLD_MILD or base < THRESHOLD_BASELINE:
        verdict = "KEEP with WARNING"
    elif pess < THRESHOLD_PESSIMISTIC + 1:
        verdict = "KEEP with WARNING (pessimistic borderline)"
    else:
        verdict = "KEEP"
    return {
        "verdict": verdict,
        "baseline_exp": base,
        "mild_exp": mild,
        "pessimistic_exp": pess,
        "threshold_baseline": THRESHOLD_BASELINE,
        "threshold_mild": THRESHOLD_MILD,
        "threshold_pessimistic": THRESHOLD_PESSIMISTIC,
    }


def write_md(results: list[dict], verdict: dict, path: Path) -> None:
    lines = [
        "# US-MOM TREND Stress Test — v3.3.2.1",
        "",
        f"**Verdict:** **{verdict['verdict']}**",
        "",
        "## Acceptance thresholds (v3.3.2.1)",
        f"- Baseline    ≥ {THRESHOLD_BASELINE} pts → KEEP unchanged",
        f"- Mild ×1.5   ≥ {THRESHOLD_MILD} pts → KEEP",
        f"- Pessimistic ×2.0 ≥ {THRESHOLD_PESSIMISTIC} pts → KEEP with WARNING (UPDATED from ≥0 in v3.3.2)",
        f"- Pessimistic < {THRESHOLD_PESSIMISTIC} pts → DROP US-MOM TREND",
        "",
        "## Per-scenario results",
        "",
        "| scenario | multiplier | buffer_pts | n_trades | WR | expectancy | sharpe | max_dd |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(f"| {r['scenario']} | {r['multiplier']} | {r['buffer_pts']:.2f} | "
                     f"{r['n_trades']} | {r['wr']:.2f} | {r['expectancy']:+.2f} | "
                     f"{r['sharpe']:.2f} | {r['max_dd']:.0f} |")
    lines += [
        "",
        "## Verdict detail",
        f"- baseline expectancy: {verdict['baseline_exp']:+.2f} (threshold {verdict['threshold_baseline']})",
        f"- mild expectancy:     {verdict['mild_exp']:+.2f} (threshold {verdict['threshold_mild']})",
        f"- pessimistic exp:     {verdict['pessimistic_exp']:+.2f} (threshold {verdict['threshold_pessimistic']} v3.3.2.1)",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", type=Path, default=EXTENDED_PARQUET)
    a = p.parse_args()
    if not a.parquet.exists():
        print(f"parquet not found: {a.parquet}", file=sys.stderr)
        return 1
    results = stress_evaluate(a.parquet)
    verdict = classify(results)
    print(f"[stress] verdict: {verdict['verdict']}")
    write_md(results, verdict, OUT_PATH)
    print(f"[stress] output -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
