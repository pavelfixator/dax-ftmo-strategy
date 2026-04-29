"""v3.3.5 STEP 3 ablation testbed: 2/3 vs 1/3 consensus per-cell impact.

Goal: Inform STRICT GATE 6-criteria evaluation (Sekce C) BEFORE committing to
combined re-run (Sekce D). Resource conservation: ablation ~8h vs ~11h
ablation+combined re-run.

Outputs:
    experiments/step3_ablation/
        regime_distribution.csv     — per-day regime label 2/3 vs 1/3
        per_cell_results.csv        — backtest metrics 2/3 vs 1/3 per cell
        projection.json             — projected Gate #18 + HARD STOP (block bootstrap MC 1K)
        hypothesis_test.md          — POZNÁMKA #2 dilution-vs-concentration verdict
        ablation_report.md          — full STRICT GATE input

Frequency-only ABSOLUTE per Princip #9: NO sizing changes; STEP 2 risk levels frozen.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.strategy.data_feed import BarFeed
from src.strategy.regime import Regime
from src.strategy.regime.classifier import (
    classify_regime_raw,
    classify_regime_step3,
    derive_signals_from_market_data,
)
from src.strategy.regime.persistence import get_active_regime
from src.strategy.setups.orb_dax import aggregate_daily
from backtest.engine import _aggregate_h4
from scripts.run_extended_ablation import evaluate_cell, build_regime_cache
from scripts.gate18_block_bootstrap import (
    realistic_lots, _pnl_pts_to_usd, block_bootstrap,
    HARD_STOP_USD, PROFIT_TARGET_USD, CHALLENGE_DAYS,
    ACTIVE_CELLS,
)

OUT_DIR = ROOT / "experiments" / "step3_ablation"
EXTENDED_PARQUET = ROOT / "data" / "historical" / "GER40_5m_2015-2026.parquet"

PROJECTION_SIMS = 1_000  # block bootstrap MC for projection (NOT 10K, saves time)


def build_regime_cache_step3(df: pd.DataFrame, daily_history: pd.DataFrame,
                              h4_full: pd.DataFrame) -> dict[dt.date, Regime]:
    """Same scaffolding as build_regime_cache but uses classify_regime_step3 (1/3)."""
    cet = "Europe/Berlin"
    cache: dict[dt.date, Regime] = {}
    raw_history: list[Regime] = []
    active_regime: Optional[Regime] = None
    cet_dates_unique = sorted({t.tz_convert(cet).date() for t in df.index})
    for d in cet_dates_unique:
        ts_8 = pd.Timestamp(dt.datetime.combine(d, dt.time(8, 0)),
                             tz=cet).tz_convert("UTC").to_pydatetime()
        try:
            sig = derive_signals_from_market_data(daily_history, h4_full, df, ts_8)
            raw = classify_regime_step3(sig)
        except (ValueError, KeyError):
            raw = Regime.UNDEFINED
        active = get_active_regime(raw_history, raw, current_active=active_regime)
        cache[d] = active
        raw_history.append(raw)
        active_regime = active
    return cache


def regime_distribution(cache: dict[dt.date, Regime]) -> dict[str, float]:
    n = len(cache)
    if n == 0:
        return {"TREND": 0, "CALM": 0, "CRASH": 0, "UNDEFINED": 0, "n": 0}
    counts = {"TREND": 0, "CALM": 0, "CRASH": 0, "UNDEFINED": 0}
    for r in cache.values():
        counts[r.value] += 1
    return {**{k: v / n * 100 for k, v in counts.items()}, "n": n}


def evaluate_per_cell(df, daily_history, cache, cet_dates) -> dict[str, dict]:
    """Run evaluate_cell for each active cell with given regime cache.

    Returns per-cell metrics: trade_count, PF, WR, expectancy, max_dd_pts, sharpe.
    """
    results: dict[str, dict] = {}
    for setup_name, regime in ACTIVE_CELLS:
        try:
            raw = evaluate_cell(setup_name, regime, set(),
                                 df, daily_history, cache, cet_dates)
        except Exception as e:
            print(f"  WARN evaluate_cell {setup_name}/{regime}: {e}", file=sys.stderr)
            results[f"{setup_name}/{regime.value}"] = {"error": str(e)}
            continue
        pnls = np.array(raw.get("pnls_pts", []), dtype=float)
        n = len(pnls)
        if n == 0:
            results[f"{setup_name}/{regime.value}"] = {
                "trade_count": 0, "PF": float("nan"), "WR": float("nan"),
                "expectancy_pts": float("nan"), "max_dd_pts": 0.0, "sharpe": float("nan"),
            }
            continue
        wins = pnls[pnls > 0].sum()
        losses = -pnls[pnls < 0].sum()
        pf = float(wins / losses) if losses > 0 else float("inf") if wins > 0 else 0.0
        wr = float((pnls > 0).sum() / n)
        expectancy = float(pnls.mean())
        cumsum = np.cumsum(pnls)
        max_dd = float(cumsum.min()) if len(cumsum) > 0 else 0.0
        sharpe = float(pnls.mean() / pnls.std()) if pnls.std() > 0 else float("nan")
        results[f"{setup_name}/{regime.value}"] = {
            "trade_count": int(n), "PF": pf, "WR": wr,
            "expectancy_pts": expectancy, "max_dd_pts": max_dd, "sharpe": sharpe,
        }
    return results


def collect_daily_pnls_from_cache(df, daily_history, cache, cet_dates) -> dict[dt.date, float]:
    """Mirror gate18.collect_daily_pnls but parametric on regime cache."""
    eligible_dates = sorted(d for d, r in cache.items() if r != Regime.UNDEFINED)
    if not eligible_dates:
        return {}
    daily_pnl: dict[dt.date, float] = {d: 0.0 for d in eligible_dates}
    all_pnls_usd: list[float] = []
    for setup_name, regime in ACTIVE_CELLS:
        try:
            raw = evaluate_cell(setup_name, regime, set(),
                                 df, daily_history, cache, cet_dates)
        except Exception as e:
            print(f"  WARN {setup_name}/{regime}: {e}", file=sys.stderr)
            continue
        lots = realistic_lots(setup_name, regime)
        if lots == 0:
            continue
        for p_pts in raw["pnls_pts"]:
            all_pnls_usd.append(_pnl_pts_to_usd(p_pts, lots))
    if not all_pnls_usd:
        return {}
    rng = np.random.default_rng(42)
    rng.shuffle(all_pnls_usd)
    for i, p in enumerate(all_pnls_usd):
        d = eligible_dates[i % len(eligible_dates)]
        daily_pnl[d] += p
    return daily_pnl


def hypothesis_test(daily_pnl: dict[dt.date, float], n_sims: int = PROJECTION_SIMS,
                     seed: int = 42) -> dict:
    """POZNÁMKA #2: hypothesis A (dilution) vs B (concentration).

    For each block bootstrap simulation, count number of trade-eligible days
    (non-zero P&L day count) within the 30-day Challenge block.
      - Low-trade Challenges (<5 days with non-zero P&L) → conditional HS rate
      - High-trade Challenges (≥10 days with non-zero P&L) → conditional HS rate

    Hypothesis A (dilution): high-trade Challenges have LOWER HARD STOP rate
                              (more days dilute concentration of losses)
    Hypothesis B (concentration): high-trade Challenges have HIGHER HARD STOP rate
                                   (cumulative tail risk grows with exposure)
    """
    dates = sorted(daily_pnl.keys())
    pnls = np.array([daily_pnl[d] for d in dates], dtype=float)
    n = len(pnls)
    if n < CHALLENGE_DAYS:
        return {"error": f"insufficient days {n}"}
    n_blocks = n - CHALLENGE_DAYS + 1
    rng = np.random.default_rng(seed)

    low_trade_total = 0
    low_trade_hs = 0
    high_trade_total = 0
    high_trade_hs = 0
    crash_total = 0
    crash_hs = 0
    no_crash_total = 0
    no_crash_hs = 0

    for _ in range(n_sims):
        start = int(rng.integers(0, n_blocks))
        block = pnls[start:start + CHALLENGE_DAYS]
        n_active = int((np.abs(block) > 0).sum())
        cumsum = np.cumsum(block)
        max_dd = float(cumsum.min())
        is_hs = max_dd <= HARD_STOP_USD
        # CRASH proxy: any single-day loss > $3500 (realistic CRASH-day loss with STEP 2 lots)
        has_crash_proxy = bool((block < -3500).any())

        if n_active < 5:
            low_trade_total += 1
            if is_hs:
                low_trade_hs += 1
        elif n_active >= 10:
            high_trade_total += 1
            if is_hs:
                high_trade_hs += 1

        if has_crash_proxy:
            crash_total += 1
            if is_hs:
                crash_hs += 1
        else:
            no_crash_total += 1
            if is_hs:
                no_crash_hs += 1

    low_rate = low_trade_hs / low_trade_total if low_trade_total else float("nan")
    high_rate = high_trade_hs / high_trade_total if high_trade_total else float("nan")
    crash_rate = crash_hs / crash_total if crash_total else float("nan")
    no_crash_rate = no_crash_hs / no_crash_total if no_crash_total else float("nan")

    if not (np.isnan(low_rate) or np.isnan(high_rate)):
        if high_rate < low_rate - 0.01:
            verdict = "A"  # dilution
            verdict_text = "Hypothesis A (dilution) supported: high-trade Challenges have LOWER HARD STOP rate"
        elif high_rate > low_rate + 0.01:
            verdict = "B"  # concentration
            verdict_text = "Hypothesis B (concentration) supported: high-trade Challenges have HIGHER HARD STOP rate"
        else:
            verdict = "inconclusive"
            verdict_text = "Inconclusive: low-trade and high-trade HARD STOP rates within ±1 pp of each other"
    else:
        verdict = "inconclusive"
        verdict_text = "Inconclusive: insufficient data in low/high-trade buckets"

    return {
        "low_trade_count_threshold": 5,
        "high_trade_count_threshold": 10,
        "low_trade_n": low_trade_total,
        "low_trade_hs_rate": low_rate,
        "high_trade_n": high_trade_total,
        "high_trade_hs_rate": high_rate,
        "crash_proxy_n": crash_total,
        "crash_hs_rate": crash_rate,
        "no_crash_n": no_crash_total,
        "no_crash_hs_rate": no_crash_rate,
        "verdict": verdict,
        "verdict_text": verdict_text,
    }


def write_distribution_csv(dist_2_3: dict, dist_1_3: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for regime in ("TREND", "CALM", "CRASH", "UNDEFINED"):
        rows.append({
            "regime": regime,
            "pct_2_of_3_baseline": dist_2_3.get(regime, 0),
            "pct_1_of_3_step3": dist_1_3.get(regime, 0),
            "delta_pp": dist_1_3.get(regime, 0) - dist_2_3.get(regime, 0),
        })
    pd.DataFrame(rows).to_csv(out, index=False)


def write_per_cell_csv(results_2_3: dict, results_1_3: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    cells = sorted(set(results_2_3.keys()) | set(results_1_3.keys()))
    for cell in cells:
        b = results_2_3.get(cell, {})
        s = results_1_3.get(cell, {})
        n_b = b.get("trade_count", 0)
        n_s = s.get("trade_count", 0)
        increase_pct = ((n_s / n_b - 1) * 100) if n_b > 0 else float("nan")
        rows.append({
            "cell": cell,
            "trade_count_2_3": n_b,
            "trade_count_1_3": n_s,
            "trade_count_increase_pct": increase_pct,
            "PF_2_3": b.get("PF", float("nan")),
            "PF_1_3": s.get("PF", float("nan")),
            "WR_2_3": b.get("WR", float("nan")),
            "WR_1_3": s.get("WR", float("nan")),
            "expectancy_pts_2_3": b.get("expectancy_pts", float("nan")),
            "expectancy_pts_1_3": s.get("expectancy_pts", float("nan")),
            "sharpe_2_3": b.get("sharpe", float("nan")),
            "sharpe_1_3": s.get("sharpe", float("nan")),
        })
    pd.DataFrame(rows).to_csv(out, index=False)


def write_hypothesis_md(hyp: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if "error" in hyp:
        out.write_text(f"# Hypothesis Test Error\n\n{hyp['error']}\n", encoding="utf-8")
        return
    lines = [
        "# POZNÁMKA #2 — HARD STOP Hypothesis Testing",
        "",
        "Two competing hypotheses tested via conditional HARD STOP rate analysis on",
        f"projected block bootstrap (n={PROJECTION_SIMS:,} 30-day Challenges).",
        "",
        "## Conditional HARD STOP rates",
        "",
        "| Subset | n Challenges | HARD STOP rate |",
        "|---|---:|---:|",
        f"| Low-trade Challenges (<{hyp['low_trade_count_threshold']} active days) | "
            f"{hyp['low_trade_n']:,} | {hyp['low_trade_hs_rate']*100:.2f}% |",
        f"| High-trade Challenges (≥{hyp['high_trade_count_threshold']} active days) | "
            f"{hyp['high_trade_n']:,} | {hyp['high_trade_hs_rate']*100:.2f}% |",
        f"| With CRASH-event proxy (any day < -$3,500) | "
            f"{hyp['crash_proxy_n']:,} | {hyp['crash_hs_rate']*100:.2f}% |",
        f"| Without CRASH proxy | "
            f"{hyp['no_crash_n']:,} | {hyp['no_crash_hs_rate']*100:.2f}% |",
        "",
        "## Verdict",
        "",
        f"**Verdict:** {hyp['verdict']}",
        "",
        hyp['verdict_text'],
        "",
        "### Interpretation",
        "",
        "- Hypothesis A (dilution): more trades distribute losses → lower HARD STOP rate",
        "- Hypothesis B (concentration): more days = more chances for bad streaks",
        "  → higher HARD STOP rate (super-linear cumulative tail risk)",
        "- Inconclusive: |rate_high − rate_low| < 1 pp; signal too weak to attribute",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def write_ablation_report(dist_2_3: dict, dist_1_3: dict,
                            results_2_3: dict, results_1_3: dict,
                            projection: dict, hyp: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    g18 = projection.get("success_rate", float("nan"))
    hs = projection.get("hard_stop_probability", float("nan"))
    incremental_lift = (g18 * 100 - 61.84) if not np.isnan(g18) else float("nan")

    lines = [
        "# v3.3.5 STEP 3 Ablation Report",
        "",
        "**Status:** Sekce B output → STRICT GATE input (Sekce C, 6 criteria).",
        "",
        f"**Projected Gate #18:** {g18*100:.2f}% (incremental {incremental_lift:+.2f} pp)",
        f"**Projected HARD STOP:** {hs*100:.2f}%",
        f"**Hypothesis verdict (POZNÁMKA #2):** {hyp.get('verdict', 'unknown')}",
        "",
        "---",
        "",
        "## 1. Regime distribution: 2/3 vs 1/3 consensus",
        "",
        "| regime | 2/3 baseline | **1/3 STEP 3** | Δ pp |",
        "|---|---:|---:|---:|",
    ]
    for regime in ("TREND", "CALM", "CRASH", "UNDEFINED"):
        b = dist_2_3.get(regime, 0)
        s = dist_1_3.get(regime, 0)
        lines.append(f"| {regime} | {b:.2f}% | **{s:.2f}%** | {s-b:+.2f} |")
    lines += [
        "",
        f"**n days:** 2/3 baseline = {dist_2_3.get('n', 0)} ; 1/3 STEP 3 = {dist_1_3.get('n', 0)}",
        "",
        "## 2. Per-cell ablation (POZNÁMKA #1: trade count increase ≥50% required for non-CRASH)",
        "",
        "| cell | trades 2/3 | trades 1/3 | increase % | PF 2/3 | PF 1/3 | WR 2/3 | WR 1/3 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for cell in sorted(set(results_2_3.keys()) | set(results_1_3.keys())):
        b = results_2_3.get(cell, {})
        s = results_1_3.get(cell, {})
        n_b = b.get("trade_count", 0)
        n_s = s.get("trade_count", 0)
        inc = ((n_s / n_b - 1) * 100) if n_b > 0 else float("nan")
        lines.append(
            f"| {cell} | {n_b} | {n_s} | {inc:+.1f}% | "
            f"{b.get('PF', float('nan')):.2f} | {s.get('PF', float('nan')):.2f} | "
            f"{b.get('WR', float('nan'))*100:.1f}% | {s.get('WR', float('nan'))*100:.1f}% |"
        )

    lines += [
        "",
        "## 3. Projected Gate #18 (block bootstrap MC, 1,000 sims)",
        "",
        f"- success_rate: **{g18*100:.2f}%** (95% CI Wilson: "
            f"{projection.get('success_ci_low', 0)*100:.2f}% .. "
            f"{projection.get('success_ci_high', 0)*100:.2f}%)",
        f"- incremental lift vs STEP 2 (61.84%): **{incremental_lift:+.2f} pp**",
        f"- compound from v3.3.4 (44.98%): **{(g18*100-44.98):+.2f} pp**",
        "",
        "## 4. Projected HARD STOP probability",
        "",
        f"- HARD STOP probability: **{hs*100:.2f}%** (95% CI Wilson: "
            f"{projection.get('hard_stop_ci_low', 0)*100:.2f}% .. "
            f"{projection.get('hard_stop_ci_high', 0)*100:.2f}%)",
        f"- vs STEP 2 (9.05%): {(hs*100 - 9.05):+.2f} pp",
        f"- threshold strict <10%: {'PASS' if hs < 0.10 else 'FAIL'}",
        "",
        "## 5. Hypothesis testing (POZNÁMKA #2)",
        "",
        f"See `experiments/step3_ablation/hypothesis_test.md` for detailed conditional analysis.",
        f"**Verdict:** {hyp.get('verdict', 'unknown')} — {hyp.get('verdict_text', '')}",
        "",
        "## 6. STRICT GATE evaluation table (6 criteria, Sekce C input)",
        "",
        "| # | Criterion | Threshold | Result | Verdict |",
        "|---|---|---|---|---|",
    ]
    # Compute STRICT GATE criteria
    c1_pass = (g18 * 100 - 61.84) >= 8.0 if not np.isnan(g18) else False
    c2_pass = hs < 0.10 if not np.isnan(hs) else False
    c3_pfs = [r.get("PF", 0) for r in results_1_3.values() if r.get("trade_count", 0) > 0]
    c3_pass = (min(c3_pfs) >= 1.4) if c3_pfs else False
    undef_1_3 = dist_1_3.get("UNDEFINED", 100)
    c4_pass = 25 <= undef_1_3 <= 45  # 30-40% target ±5 pp
    c5_increases = []
    for cell, s in results_1_3.items():
        b = results_2_3.get(cell, {})
        if cell.endswith("/CRASH"):
            continue  # CRASH cell exempt per spec
        n_b = b.get("trade_count", 0)
        n_s = s.get("trade_count", 0)
        if n_b > 0:
            c5_increases.append((n_s / n_b - 1) * 100)
    c5_pass = all(inc >= 50 for inc in c5_increases) if c5_increases else False
    c6_pass = hyp.get("verdict") in ("A", "B", "inconclusive")  # documented and clear

    lines += [
        f"| 1 | G#18 lift ≥+8pp | +8pp | {incremental_lift:+.2f} pp | "
            f"{'✅ PASS' if c1_pass else '❌ FAIL'} |",
        f"| 2 | HARD STOP <10% | <10% | {hs*100:.2f}% | "
            f"{'✅ PASS' if c2_pass else '❌ FAIL'} |",
        f"| 3 | Per-cell PF ≥1.4 | ≥1.4 | min={min(c3_pfs) if c3_pfs else 0:.2f} | "
            f"{'✅ PASS' if c3_pass else '❌ FAIL'} |",
        f"| 4 | UNDEFINED 30-40% (±5) | 25-45% | {undef_1_3:.1f}% | "
            f"{'✅ PASS' if c4_pass else '❌ FAIL'} |",
        f"| 5 | Trade ↑≥50% (non-CRASH) | ≥50% | "
            f"min={min(c5_increases) if c5_increases else 0:+.1f}% | "
            f"{'✅ PASS' if c5_pass else '❌ FAIL'} |",
        f"| 6 | Hypothesis docs+verdict | clear | {hyp.get('verdict', 'unknown')} | "
            f"{'✅ PASS' if c6_pass else '❌ FAIL'} |",
        "",
        "**STRICT GATE aggregate:** "
        f"{'🟢 STRICT_GATE_PASS — proceed to Sekce D' if all([c1_pass, c2_pass, c3_pass, c4_pass, c5_pass, c6_pass]) else '🔴 STRICT_GATE_FAIL — preempt Volba D, skip Sekce D'}",
        "",
    ]
    out.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", type=Path, default=EXTENDED_PARQUET)
    p.add_argument("--projection-sims", type=int, default=PROJECTION_SIMS)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()

    if not a.parquet.exists():
        print(f"parquet not found: {a.parquet}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"[step3-ablation] loading {a.parquet}")
    feed = BarFeed.from_parquet(a.parquet)
    df = feed.to_dataframe()
    daily = aggregate_daily(df)
    h4 = _aggregate_h4(df)
    cet_dates = pd.Series([t.tz_convert("Europe/Berlin").date() for t in df.index],
                           index=df.index)

    print("[step3-ablation] building 2/3 baseline regime cache")
    cache_2_3 = build_regime_cache(df, daily, h4)
    dist_2_3 = regime_distribution(cache_2_3)
    print(f"  baseline: TREND {dist_2_3['TREND']:.1f}% CALM {dist_2_3['CALM']:.1f}% "
          f"CRASH {dist_2_3['CRASH']:.1f}% UNDEFINED {dist_2_3['UNDEFINED']:.1f}%")

    print("[step3-ablation] building 1/3 STEP 3 regime cache")
    cache_1_3 = build_regime_cache_step3(df, daily, h4)
    dist_1_3 = regime_distribution(cache_1_3)
    print(f"  step3:    TREND {dist_1_3['TREND']:.1f}% CALM {dist_1_3['CALM']:.1f}% "
          f"CRASH {dist_1_3['CRASH']:.1f}% UNDEFINED {dist_1_3['UNDEFINED']:.1f}%")

    print(f"[step3-ablation] dist elapsed: {time.time()-t0:.0f}s")

    write_distribution_csv(dist_2_3, dist_1_3, OUT_DIR / "regime_distribution.csv")

    print("[step3-ablation] per-cell ablation backtest 2/3 baseline")
    results_2_3 = evaluate_per_cell(df, daily, cache_2_3, cet_dates)
    for cell, r in results_2_3.items():
        print(f"  2/3 {cell}: trades={r.get('trade_count', 0)} PF={r.get('PF', 0):.2f}")

    print("[step3-ablation] per-cell ablation backtest 1/3 STEP 3")
    results_1_3 = evaluate_per_cell(df, daily, cache_1_3, cet_dates)
    for cell, r in results_1_3.items():
        print(f"  1/3 {cell}: trades={r.get('trade_count', 0)} PF={r.get('PF', 0):.2f}")

    write_per_cell_csv(results_2_3, results_1_3, OUT_DIR / "per_cell_results.csv")

    print(f"[step3-ablation] backtests elapsed: {time.time()-t0:.0f}s")

    print("[step3-ablation] computing daily P&L for STEP 3 projection")
    daily_pnl_step3 = collect_daily_pnls_from_cache(df, daily, cache_1_3, cet_dates)
    print(f"  eligible days: {len(daily_pnl_step3)}")

    print(f"[step3-ablation] projection block bootstrap MC ({a.projection_sims} sims)")
    projection = block_bootstrap(daily_pnl_step3, a.projection_sims,
                                  CHALLENGE_DAYS, seed=a.seed)
    projection.pop("_final_pnls", None)
    projection.pop("_max_dds", None)
    g18 = projection.get("success_rate", 0)
    hs = projection.get("hard_stop_probability", 0)
    print(f"  projected G#18: {g18*100:.2f}% | HARD STOP: {hs*100:.2f}%")

    print("[step3-ablation] hypothesis testing (POZNÁMKA #2)")
    hyp = hypothesis_test(daily_pnl_step3, n_sims=a.projection_sims, seed=a.seed)
    print(f"  hypothesis verdict: {hyp.get('verdict', 'unknown')}")

    write_hypothesis_md(hyp, OUT_DIR / "hypothesis_test.md")

    # Save projection JSON for downstream use
    proj_serializable = {k: v for k, v in projection.items()
                          if not isinstance(v, np.ndarray)}
    with (OUT_DIR / "projection.json").open("w", encoding="utf-8") as f:
        json.dump({
            "projection": proj_serializable,
            "hypothesis": hyp,
            "regime_distribution": {"2_of_3": dist_2_3, "1_of_3": dist_1_3},
            "per_cell": {"2_of_3": results_2_3, "1_of_3": results_1_3},
        }, f, indent=2, default=float)

    write_ablation_report(dist_2_3, dist_1_3, results_2_3, results_1_3,
                            projection, hyp, OUT_DIR / "ablation_report.md")

    print(f"[step3-ablation] total elapsed: {time.time()-t0:.0f}s")
    print(f"[step3-ablation] outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
