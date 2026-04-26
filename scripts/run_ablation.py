"""Iter2b — Filter ablation diagnostika.

Pro každý setup × každou konfiguraci × 2 týdny (klidný + crash):
  - signal count (bary kde check_entry_at vrátil Signal)
  - trade count (signály co prošly RRR + position sizing)
  - win rate (pro completed trades — se simulovaným exitem)

Konfigurace:
  baseline   F1+F2+F3+F4 (= filters="A")
  drop_F1
  drop_F2
  drop_F3
  drop_F4    (= filters="B")
  all_off    F1..F4 všechny skipnuté

Output: experiments/iter2b_filter_ablation.md
        + Discord post do #alerts s identifikovaným binding filterem.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.data_feed import BarFeed
from src.strategy.setups.orb_dax import OrbDaxSetup, aggregate_daily
from src.strategy.setups.vwap_bounce import VwapBounceSetup
from src.strategy.setups.us_momentum import UsMomentumSetup
from src.risk.risk_manager import compute_lots
from src.risk.rules_engine import (
    in_trading_window, before_hard_stop, rrr_acceptable,
    FORCED_CLOSE_MON_THU, FORCED_CLOSE_FRI,
)

PARQUET = ROOT / "data" / "historical" / "GER40_5m_2019-2023.parquet"
REPORT = ROOT / "experiments" / "iter2b_filter_ablation.md"

WEEKS = [
    ("calm_bull_pre_covid", "2020-01-13", "2020-01-18", "bull"),
    ("peak_crash_black_monday_II", "2020-03-16", "2020-03-21", "crash"),
]

CONFIGS = [
    ("baseline_F1234", "A", set()),
    ("drop_F1",        "A", {"F1"}),
    ("drop_F2",        "A", {"F2"}),
    ("drop_F3",        "A", {"F3"}),
    ("drop_F4",        "A", {"F4"}),  # equivalent of B-setup but on A-track
    ("all_off",        "A", {"F1", "F2", "F3", "F4"}),
]

EUR_USD = 1.08


def _force_close_time(ts_cet):
    return FORCED_CLOSE_FRI if ts_cet.weekday() == 4 else FORCED_CLOSE_MON_THU


def _simulate_outcome(df: pd.DataFrame, sig, entry_ts) -> tuple[float, str]:
    """Walk forward from entry_ts until SL/TP/force_close hit."""
    from zoneinfo import ZoneInfo
    cet = ZoneInfo("Europe/Berlin")
    after = df.loc[df.index > entry_ts]
    for ts, bar in after.iterrows():
        ts_cet = ts.tz_convert(cet)
        # SL/TP touch
        if sig.direction == "LONG":
            if float(bar["low"]) <= sig.sl:
                return float(sig.sl) - sig.entry, "sl"
            if float(bar["high"]) >= sig.tp:
                return float(sig.tp) - sig.entry, "tp"
        else:
            if float(bar["high"]) >= sig.sl:
                return sig.entry - float(sig.sl), "sl"
            if float(bar["low"]) <= sig.tp:
                return sig.entry - float(sig.tp), "tp"
        # Force close at end of trading day
        cutoff = _force_close_time(ts_cet)
        if ts_cet.time() >= cutoff:
            close = float(bar["close"])
            pnl_pts = (close - sig.entry) if sig.direction == "LONG" else (sig.entry - close)
            return pnl_pts, "force_close"
    # End of feed
    last = df.iloc[-1]
    close = float(last["close"])
    pnl_pts = (close - sig.entry) if sig.direction == "LONG" else (sig.entry - close)
    return pnl_pts, "end_of_feed"


def _eval_setup(name, setup, ts, today_session, history, daily_history,
                skip: set) -> Optional[object]:
    if name == "orb_dax":
        return setup.check_entry_at(today_session, daily_history, ts,
                                     history_5m=history, skip_filters=skip)
    if name == "vwap_bounce":
        return setup.check_entry_at(history, ts, history_5m=history,
                                     skip_filters=skip)
    if name == "us_momentum":
        return setup.check_entry_at(history, daily_history, ts,
                                     sp500_5m=None, skip_filters=skip)
    return None


def run_one(name: str, setup_factory, week_label: str,
            week_df: pd.DataFrame, daily: pd.DataFrame,
            cet_dates: pd.Series, full_df: pd.DataFrame,
            skip: set, filters: str) -> dict:
    setup = setup_factory(filters=filters)
    n_signals = 0
    n_trades = 0
    pnls_pts: list[float] = []
    wins = 0
    for ts in week_df.index:
        ts_cet = ts.tz_convert("Europe/Berlin")
        if not in_trading_window(ts_cet).allowed:
            continue
        if not before_hard_stop(ts_cet).allowed:
            continue
        today = ts_cet.date()
        today_session = full_df[cet_dates == today].loc[:ts]
        history = full_df.loc[:ts]
        try:
            sig = _eval_setup(name, setup, ts, today_session, history, daily, skip)
        except Exception as e:
            sig = None
            # Catch silently to avoid one bad ts breaking ablation
        if sig is None:
            continue
        n_signals += 1
        # Position sizing + RRR
        sl_pts = abs(sig.entry - sig.sl)
        sized = compute_lots(filters, "normal", sl_pts, EUR_USD,
                              equity_usd=100_000, dax_price=float(week_df.loc[ts, "close"]))
        if sized.lots == 0:
            continue
        if not rrr_acceptable(sig.entry, sig.sl, sig.tp).allowed:
            continue
        # Simulate outcome (only count first signal per direction per day to avoid double-count)
        pnl_pts, reason = _simulate_outcome(full_df, sig, ts)
        n_trades += 1
        pnls_pts.append(pnl_pts)
        if pnl_pts > 0:
            wins += 1
        # Skip ahead past this trade's exit for cleanliness — find next bar after exit
    win_rate = (wins / n_trades) if n_trades else 0.0
    avg_pnl_pts = (sum(pnls_pts) / len(pnls_pts)) if pnls_pts else 0.0
    # Max drawdown in points across the chronological pnl sequence
    max_dd_pts = 0.0
    if pnls_pts:
        cum = 0.0
        peak = 0.0
        for p in pnls_pts:
            cum += p
            if cum > peak:
                peak = cum
            dd = cum - peak
            if dd < max_dd_pts:
                max_dd_pts = dd
    return {
        "n_signals": n_signals,
        "n_trades": n_trades,
        "win_rate": round(win_rate, 3),
        "avg_pnl_pts": round(avg_pnl_pts, 2),
        "max_dd_pts": round(max_dd_pts, 2),
        "pnls_pts": [round(p, 2) for p in pnls_pts],
    }


def main() -> int:
    print(f"[ablation] loading {PARQUET}")
    feed = BarFeed.from_parquet(PARQUET)
    print(f"[ablation] full range: {feed.first} .. {feed.last} ({len(feed)} bars)")
    full = feed.to_dataframe()
    daily = aggregate_daily(full)
    cet_dates = pd.Series([t.tz_convert("Europe/Berlin").date() for t in full.index],
                           index=full.index)

    setup_factories = {
        "orb_dax": lambda filters: OrbDaxSetup(filters=filters),
        "vwap_bounce": lambda filters: VwapBounceSetup(filters=filters),
        "us_momentum": lambda filters: UsMomentumSetup(filters=filters),
    }

    results: dict = {}
    for week_lbl, start, end, regime in WEEKS:
        print(f"\n[ablation] week {week_lbl} ({regime}) {start}..{end}")
        week_feed = feed.range(start, end)
        week_df = week_feed.to_dataframe()
        results.setdefault(week_lbl, {"regime": regime, "by_setup": {}})
        for setup_name, factory in setup_factories.items():
            print(f"  setup {setup_name}")
            results[week_lbl]["by_setup"][setup_name] = {}
            for cfg_lbl, filters, skip in CONFIGS:
                r = run_one(setup_name, factory, week_lbl, week_df,
                            daily, cet_dates, full, skip, filters)
                print(f"    {cfg_lbl:18s}  signals={r['n_signals']:4d}  "
                      f"trades={r['n_trades']:4d}  WR={r['win_rate']:.2f}  "
                      f"avg_pnl_pts={r['avg_pnl_pts']:+.1f}")
                results[week_lbl]["by_setup"][setup_name][cfg_lbl] = r

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    md = _build_report(results)
    REPORT.write_text(md, encoding="utf-8")
    print(f"\n[ablation] report -> {REPORT}")
    return 0


def _build_report(results: dict) -> str:
    lines = [
        "# Iter2b — Filter Ablation Diagnostika",
        "",
        "**Cíl:** identifikovat binding filter — ten s největším signal-count dropoff",
        "po jeho vynechání.",
        "",
        "**Týdny:** 2020-01-13..17 (klidný bull pre-COVID) + 2020-03-16..20 (peak crash).",
        "**Setupy:** orb_dax / vwap_bounce / us_momentum.",
        "**Konfigurace:** baseline (F1+F2+F3+F4), drop_F1, drop_F2, drop_F3, drop_F4, all_off.",
        "",
        "Metriky per (setup, week, config):",
        "- `n_signals` — kolik 5m barů triggerlo Signal (bez RRR/sizing check)",
        "- `n_trades` — počet kompletních trades (po RRR + sizing)",
        "- `win_rate` — % zisků na trade",
        "- `avg_pnl_pts` — průměrný P&L v points (bod = 1 bod indexu)",
        "",
    ]
    for week_lbl, week_data in results.items():
        lines.append(f"## Week `{week_lbl}` ({week_data['regime']})")
        lines.append("")
        for setup_name, configs in week_data["by_setup"].items():
            lines.append(f"### Setup `{setup_name}`")
            lines.append("")
            lines.append("| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |")
            lines.append("|---|---:|---:|---:|---:|---:|")
            for cfg_lbl, r in configs.items():
                lines.append(
                    f"| {cfg_lbl} | {r['n_signals']} | {r['n_trades']} | "
                    f"{r['win_rate']:.2f} | {r['avg_pnl_pts']:+.1f} | "
                    f"{r.get('max_dd_pts', 0):+.1f} |"
                )
            lines.append("")
    lines += [
        "## Diagnostika — který filter je BINDING",
        "",
        "Pro každý setup spočti dropoff per filter:",
        "```",
        "dropoff(F_X) = signals[drop_F_X] - signals[baseline]",
        "```",
        "Nejvyšší dropoff → binding filter.",
        "",
        "**Souhrn (signals napříč oběma týdny):**",
        "",
    ]
    summary = {}
    for week_data in results.values():
        for setup_name, configs in week_data["by_setup"].items():
            for cfg_lbl, r in configs.items():
                key = (setup_name, cfg_lbl)
                summary.setdefault(key, 0)
                summary[key] += r["n_signals"]
    for setup_name in ("orb_dax", "vwap_bounce", "us_momentum"):
        lines.append(f"### {setup_name}")
        lines.append("")
        baseline = summary.get((setup_name, "baseline_F1234"), 0)
        lines.append(f"- baseline_F1234: **{baseline}** signals")
        for cfg_lbl in ("drop_F1", "drop_F2", "drop_F3", "drop_F4"):
            n = summary.get((setup_name, cfg_lbl), 0)
            dropoff = n - baseline
            marker = " ← LIKELY BINDING" if dropoff >= 5 else ""
            lines.append(f"- {cfg_lbl}: {n} signals (Δ {dropoff:+d}){marker}")
        all_off = summary.get((setup_name, "all_off"), 0)
        lines.append(f"- all_off: {all_off} signals (ceiling)")
        lines.append("")
    lines += [
        "## Závěr a kalibrace",
        "",
        "- **Pokud `drop_F1` má největší positive Δ → daily bias je binding.**",
        "  Návrh: 2/3 booleans místo all-3 (např. `yest_close > EMA20D1` AND",
        "  (`yest_close > yest_open` OR `yest_close > day_before_close`)).",
        "",
        "- **Pokud `drop_F3` má největší Δ pro vwap_bounce → Brooks engulfing too strict.**",
        "  Návrh: relax na \"wick-tested + close back inside band\" (touch & reverse).",
        "",
        "- **Pokud `drop_F4` má největší Δ → ATR/volume thresholds restriktivní.**",
        "  Návrh: snížit ratio (1.5× → 1.2× volume; 0.7× → 0.5× ATR median).",
        "",
        "- **Pokud `all_off` zůstává << expected (~50-100 signals/week) →** entry condition",
        "  samotná je restriktivní (ORB range / engulfing / breakout). Re-spec needed.",
        "",
        "Po Pavlově rozhodnutí: implementuj kalibraci, spustit Iter2c (re-run regime sample).",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
