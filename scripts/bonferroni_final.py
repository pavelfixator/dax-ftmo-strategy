"""Bonferroni re-evaluation pro v3.3.2.1 final winners.

Reads experiments/extended_ablation/master_table.csv and applies Bonferroni
correction restricted to the *final* selected cells (4 active per v3.3.2.1)
+ FDR-significant winners. Reports per-cell adjusted p-values and
PASS/FAIL.

Output: experiments/bonferroni_final.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest.extended_ablation import bonferroni, fdr_bh

ABLATION = ROOT / "experiments" / "extended_ablation" / "master_table.csv"
OUT = ROOT / "experiments" / "bonferroni_final.csv"

# Cells corresponding to v3.3.2.1 active config (post-ablation winner mapping)
# orb_dax CALM drop_F3 (winner), us_momentum TREND/CALM/CRASH variants matching v3.3.2.1.
TARGETS = [
    ("orb_dax", "CALM", "drop_F3"),
    ("us_momentum", "TREND", "baseline_F1234"),
    ("us_momentum", "CALM", "drop_F2"),
    ("us_momentum", "CRASH", "drop_F1"),
]


def main() -> int:
    if not ABLATION.exists():
        print(f"missing {ABLATION}", file=sys.stderr)
        return 1
    df = pd.read_csv(ABLATION)
    rows = []
    for setup, regime, config in TARGETS:
        match = df[(df["setup"] == setup) & (df["regime"] == regime)
                   & (df["config"] == config)]
        if match.empty:
            print(f"WARN: {setup}/{regime}/{config} not found in master_table",
                  file=sys.stderr)
            continue
        m = match.iloc[0]
        rows.append({
            "setup": setup, "regime": regime, "config": config,
            "n_trades": int(m["n_trades"]),
            "p_value": float(m["p_value"]),
            "expectancy": float(m["expectancy"]),
            "wr": float(m["wr"]),
            "fdr_significant_in_full_44cell_run": bool(m["fdr_significant"]),
        })
    pvals = [r["p_value"] for r in rows]
    bonf = bonferroni(pvals, alpha=0.05)
    fdr = fdr_bh(pvals, alpha=0.05)
    for r, b, f in zip(rows, bonf, fdr):
        r["bonferroni_pass_4cell_subset"] = bool(b)
        r["fdr_pass_4cell_subset"] = bool(f)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[bonferroni] wrote {len(rows)} cells -> {OUT}")
    for r in rows:
        print(f"  {r['setup']:12s} {r['regime']:6s} {r['config']:18s} "
              f"n={r['n_trades']:5d} p={r['p_value']:.4f} "
              f"bonf={r['bonferroni_pass_4cell_subset']} "
              f"fdr={r['fdr_pass_4cell_subset']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
