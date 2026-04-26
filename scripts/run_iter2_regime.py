"""Iterace 2 regime sample — 8 týdnů 2020-2023.

Spec: Pavel hybrid plan 2026-04-26 §Úkol 4.

Týdny:
  #1 2020-01-13..17  klidný bull pre-COVID
  #2 2020-02-24..28  CRASH start (COVID + Putin announcement)
  #3 2020-03-16..20  PEAK CRASH (Black Monday II 16.3.)
  #4 2020-05-11..15  recovery + monetary stimulus
  #5 2021-04-19..23  bull trend (vaccine rollout)
  #6 2022-02-21..25  Ukraine war start (24.2.)
  #7 2022-06-13..17  bear market + ECB rate hike fears
  #8 2023-03-06..10  banking crisis (SVB + Credit Suisse)

Output: experiments/iter2_regime_sample_8weeks.md + Discord summary
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
REPORT = ROOT / "experiments" / "iter2_regime_sample_8weeks.md"

WEEKS = [
    ("#1 klidny_bull_pre_covid",       "2020-01-13", "2020-01-18", "bull"),
    ("#2 crash_start_covid",           "2020-02-24", "2020-02-29", "crash"),
    ("#3 peak_crash_black_monday_II",  "2020-03-16", "2020-03-21", "crash"),
    ("#4 recovery_monetary_stimulus",  "2020-05-11", "2020-05-16", "recovery"),
    ("#5 bull_vaccine_rollout",        "2021-04-19", "2021-04-24", "bull"),
    ("#6 ukraine_war_start",           "2022-02-21", "2022-02-26", "geopolitical"),
    ("#7 bear_ecb_hike_fears",         "2022-06-13", "2022-06-18", "bear"),
    ("#8 banking_crisis_svb_cs",       "2023-03-06", "2023-03-11", "geopolitical"),
]


def main() -> int:
    print(f"[iter2] loading {PARQUET}")
    feed = BarFeed.from_parquet(PARQUET)
    print(f"[iter2] full range: {feed.first} .. {feed.last} ({len(feed)} bars)")

    per_week = []
    for label, start_cet, end_cet, regime in WEEKS:
        print(f"\n[iter2] {label}  ({regime})  {start_cet}..{end_cet}")
        sub = feed.range(start_cet, end_cet)
        if len(sub) == 0:
            print(f"  WARN empty slice, skipping")
            per_week.append({"label": label, "regime": regime, "n_bars": 0, "stats": {}})
            continue
        res = run_backtest(sub)
        st = res.stats()
        print(f"  bars={len(sub)} trades={res.n_trades} viol={len(res.invariant_violations)}")
        if res.invariant_violations:
            for v in res.invariant_violations[:5]:
                print(f"    !! {v}")
        if res.trades:
            for t in res.trades:
                print(f"    {t.entry_ts.tz_convert('Europe/Berlin')} {t.setup} {t.direction} "
                      f"@ {t.entry:.1f} -> {t.exit:.1f} ({t.exit_reason}) {t.pnl_usd:+.2f} USD")
        per_week.append({
            "label": label, "regime": regime,
            "start": start_cet, "end": end_cet,
            "n_bars": len(sub),
            "n_trades": res.n_trades,
            "stats": st,
            "violations": res.invariant_violations,
            "trades": [
                {
                    "ts_in": str(t.entry_ts), "ts_out": str(t.exit_ts),
                    "setup": t.setup, "dir": t.direction,
                    "entry": t.entry, "exit": t.exit, "lots": t.lots,
                    "reason": t.exit_reason, "pnl_usd": t.pnl_usd,
                    "filters": f"{t.filters_met}/{t.filters_total}",
                }
                for t in res.trades
            ],
        })

    # Aggregate
    all_trades_pnl = [tt["pnl_usd"] for w in per_week for tt in w.get("trades", [])]
    n_total = len(all_trades_pnl)
    wins = [p for p in all_trades_pnl if p > 0]
    aggregate = {
        "n_trades_total": n_total,
        "wins": len(wins),
        "losses": len([p for p in all_trades_pnl if p < 0]),
        "win_rate": (len(wins) / n_total) if n_total else 0.0,
        "pnl_total_usd": float(sum(all_trades_pnl)),
        "pf": (sum(wins) / abs(sum([p for p in all_trades_pnl if p < 0])))
              if any(p < 0 for p in all_trades_pnl) else float("inf"),
    }

    # Per-regime
    per_regime = {}
    for w in per_week:
        r = w["regime"]
        per_regime.setdefault(r, {"n_trades": 0, "pnl_usd": 0.0, "weeks": 0})
        per_regime[r]["weeks"] += 1
        per_regime[r]["n_trades"] += w.get("n_trades", 0)
        per_regime[r]["pnl_usd"] += w.get("stats", {}).get("pnl_total_usd", 0.0)

    print(f"\n[iter2] AGGREGATE: {json.dumps(aggregate, indent=2, default=str)}")
    print(f"[iter2] BY REGIME: {json.dumps(per_regime, indent=2, default=str)}")

    md = _build_report(per_week, aggregate, per_regime)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(md, encoding="utf-8")
    print(f"\n[iter2] report -> {REPORT}")
    return 0


def _build_report(weeks, agg, by_regime) -> str:
    lines = [
        "# Iterace 2 — Regime Sample (8 weeks 2020-2023)",
        "",
        "**Cíl:** ověřit chování engine + filtrů přes různé tržní režimy.",
        "**Setupy:** ORB-DAX (A+B), VWAP-Bounce (A+B), US-Momentum (A+B) — paralelně, max 1 pozice.",
        "",
        "## Aggregate (8 týdnů)",
        "",
        "```json",
        json.dumps(agg, indent=2, default=str),
        "```",
        "",
        "## Per-regime breakdown",
        "",
        "```json",
        json.dumps(by_regime, indent=2, default=str),
        "```",
        "",
        "## Per-week breakdown",
        "",
        "| # | label | regime | bars | trades | violations | pnl_usd |",
        "|---|---|---|---|---|---|---|",
    ]
    for w in weeks:
        lines.append(
            f"| {w['label']} | {w['regime']} | {w.get('n_bars', 0)} | "
            f"{w.get('n_trades', 0)} | {len(w.get('violations', []))} | "
            f"{w.get('stats', {}).get('pnl_total_usd', 0):.2f} |"
        )
    lines += [
        "",
        "## Per-week detail",
        "",
    ]
    for w in weeks:
        lines.append(f"### {w['label']} ({w['regime']}) {w['start']}..{w['end']}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(w.get("stats", {}), indent=2, default=str))
        lines.append("```")
        if w.get("trades"):
            lines.append("")
            lines.append("**Per-trade:**")
            lines.append("")
            for t in w["trades"]:
                lines.append(
                    f"- {t['ts_in']} {t['setup']} {t['dir']} @ {t['entry']:.1f} → "
                    f"{t['exit']:.1f} ({t['reason']}) {t['pnl_usd']:+.2f} USD "
                    f"[filters {t['filters']}, lots {t['lots']}]"
                )
        if w.get("violations"):
            lines.append("")
            lines.append("**Violations:**")
            for v in w["violations"]:
                lines.append(f"- {v}")
        lines.append("")
    lines += [
        "## Závěr",
        "",
        "- Pokud `n_trades_total > 0` a `violations == 0` → engine + filtry kalibrovány",
        "  pro reálné podmínky; lze pokračovat na Iter 3 (plný backtest 2019-2026 po doplnění dat).",
        "- Pokud `n_trades_total == 0` → filtry jsou striktní; nutno snížit thresholds (volume,",
        "  daily bias, ADX, Brooks engulfing definici) v dalším kroku.",
        "- Pokud `violations > 0` → engine bug, fix před pokračováním.",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
