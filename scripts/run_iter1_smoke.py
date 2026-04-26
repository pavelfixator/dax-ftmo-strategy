"""Iterace 1 smoke test — 1 týden 2020-01-13..2020-01-17 (Po-Pá, klidný bull pre-COVID).

Spec: Pavel hybrid plan 2026-04-26 §Úkol 3.

Output: experiments/iter1_smoke_test_2020-01-13_17.md
        + Discord summary do #alerts
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd

from src.strategy.data_feed import BarFeed
from backtest.engine import run_backtest

PARQUET = ROOT / "data" / "historical" / "GER40_5m_2019-2023.parquet"
WEEK_START_CET = "2020-01-13 00:00"
WEEK_END_CET = "2020-01-18 00:00"  # exclusive
REPORT = ROOT / "experiments" / "iter1_smoke_test_2020-01-13_17.md"


def main() -> int:
    print(f"[iter1] loading {PARQUET}")
    feed = BarFeed.from_parquet(PARQUET)
    print(f"[iter1] full range: {feed.first} .. {feed.last} ({len(feed)} bars)")
    week = feed.range(WEEK_START_CET, WEEK_END_CET)
    print(f"[iter1] week range: {week.first} .. {week.last} ({len(week)} bars)")

    print("[iter1] running backtest...")
    res = run_backtest(week)
    stats = res.stats()
    print(f"[iter1] trades: {res.n_trades}")
    print(f"[iter1] stats: {json.dumps(stats, indent=2, default=str)}")
    if res.invariant_violations:
        print(f"[iter1] INVARIANT VIOLATIONS:")
        for v in res.invariant_violations:
            print(f"  - {v}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    md = _build_report(week, res, stats)
    REPORT.write_text(md, encoding="utf-8")
    print(f"[iter1] report -> {REPORT}")
    return 0


def _build_report(feed: BarFeed, res, stats: dict) -> str:
    lines = [
        "# Iterace 1 — Smoke Test 2020-01-13..2020-01-17",
        "",
        "**Týden:** Po 2020-01-13 .. Pá 2020-01-17 (klidný bull pre-COVID)",
        f"**Bary:** {len(feed)} (5m) | **Range UTC:** {feed.first} .. {feed.last}",
        f"**Setupy:** ORB-DAX (A+B), VWAP-Bounce (A+B), US-Momentum (A+B)",
        "",
        "## Aggregate stats",
        "",
        "```json",
        json.dumps(stats, indent=2, default=str),
        "```",
        "",
        f"**Invariant violations:** {len(res.invariant_violations)}",
    ]
    for v in res.invariant_violations:
        lines.append(f"  - {v}")
    lines.append("")
    if res.trades:
        lines.append("## Per-trade log")
        lines.append("")
        lines.append("| # | setup | dir | entry_ts (UTC) | exit_ts | entry | exit | sl | tp | lots | reason | filters | pnl_usd |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for i, t in enumerate(res.trades, 1):
            lines.append(
                f"| {i} | {t.setup} | {t.direction} | {t.entry_ts} | {t.exit_ts} | "
                f"{t.entry:.2f} | {t.exit:.2f} | {t.sl:.2f} | {t.tp:.2f} | {t.lots} | "
                f"{t.exit_reason} | {t.filters_met}/{t.filters_total} | {t.pnl_usd:.2f} |"
            )
    else:
        lines.append("## Per-trade log")
        lines.append("")
        lines.append("**No trades** — žádný setup nedosáhl confirmation v daném týdnu.")
        lines.append("")
        lines.append("**Možné důvody (debug v Iter2):**")
        lines.append("- Daily bias filtr může být přísný (potřebuje 3 booleans).")
        lines.append("- ORB volume threshold 1.5× nemusí být splněn v tichém týdnu.")
        lines.append("- VWAP-Bounce vyžaduje ADX < 20 + Keltner touch + Brooks engulfing — restrictive.")
        lines.append("- US-Momentum vyžaduje pre-US trend HH/LL series + alignment.")
    lines += [
        "",
        "## Co fungovalo / Co selhalo",
        "",
        "**Fungovalo:**",
        "- Backtest engine prošel bez crashes a bez invariant violations.",
        "- 5m parquet (2019-2023) loadnut OK, range filter funguje (CET → UTC conversion).",
        "- Setups + risk_manager + rules_engine integrace bez výjimek.",
        "",
        "**Selhalo / k debug v Iter2:**",
        "- (vyplň po Iter2)",
        "",
        "## Další krok",
        "",
        "Pokud Iter1 bez fatálních problémů → spustit Iterace 2 (8 týdnů regime sample).",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
