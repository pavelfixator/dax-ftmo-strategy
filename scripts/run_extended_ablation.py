"""Extended ablation runtime pro Strategy v3.3.1 (Sekce 4).

Window: 2015-01-01 → 2026-03-31 (11 let)
Cells: 36 primary (2 setups × 3 regimes × 6 configs) + 8 F5 (4 cands × 2 cells) = 44
Train/Test split: train 2019-2022 / test (OOS) 2023-2026
2015-2018 = extended history pro CRASH samples (Brexit 6/2016, Trump tariffs 2018)

Stat infra (per Pavel + Red Team Dodatek 1):
  - Wilson 95 % CI pro WR
  - Bootstrap 1000 percentile CI pro expectancy/Sharpe/max DD
  - FDR (Benjamini-Hochberg) primary, Bonferroni secondary, alpha 0.05
  - Acceptance: ≥ +10 % expectancy boost vs baseline + p < FDR-adjusted alpha

Sample size flags: PRIMARY ≥ 100 / WARNING 50-99 / REJECT < 50

Outputs (experiments/extended_ablation/):
  master_table.csv             — 44 cells × per-cell metrics
  per_cell_distributions.html  — distribution plots
  wilson_ci_visualizations.html
  fdr_corrected_pvalues.csv
  oos_validation.md

Usage:
  python scripts/run_extended_ablation.py
  python scripts/run_extended_ablation.py --auto-start  # poll Dukascopy then run
  python scripts/run_extended_ablation.py --quick       # 2020 only sanity run
"""
from __future__ import annotations

import argparse
import csv
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
from src.strategy.regime import Regime, get_active_regime
from src.strategy.regime.classifier import (
    classify_regime_raw, derive_signals_from_market_data,
)
from src.strategy.setups.orb_dax import aggregate_daily
from src.strategy.setups.orb_dax_v331 import OrbDaxSetupV331
from src.strategy.setups.us_momentum_v331 import UsMomentumSetupV331
from src.strategy.setups.f5_candidates import (
    ORB_CRASH_F5_CANDIDATES, US_CALM_F5_CANDIDATES,
)
from src.risk.sizing_v331 import calculate_lots_v331
from src.risk.rules_engine import (
    in_trading_window, before_hard_stop, rrr_acceptable,
    FORCED_CLOSE_MON_THU, FORCED_CLOSE_FRI,
)
from backtest.engine import _aggregate_h4
from src.backtest.extended_ablation import (
    wilson_ci, bootstrap_ci, fdr_bh, bonferroni,
    sample_size_flag, oos_validate, cell_distribution,
    sharpe_ratio, profit_factor, expectancy, expectancy_pvalue,
)

OUT_DIR = ROOT / "experiments" / "extended_ablation"
PROGRESS_PATH = OUT_DIR / "progress.json"
PARQUET = ROOT / "data" / "historical" / "GER40_5m_2019-2023.parquet"
EXTENDED_PARQUET = ROOT / "data" / "historical" / "GER40_5m_2015-2026.parquet"

WINDOW_START = "2015-01-01"
WINDOW_END = "2026-04-01"   # exclusive
TRAIN_END = "2023-01-01"    # train 2019-2022
TEST_START = "2023-01-01"   # test 2023-2026

EUR_USD = 1.08
BOOTSTRAP_ITERS = 1000
ALPHA = 0.05
ACCEPTANCE_BOOST_PCT = 0.10  # +10 % expectancy boost vs baseline

CONFIGS = ["baseline_F1234", "drop_F1", "drop_F2", "drop_F3", "drop_F4", "all_off"]
SETUP_NAMES = ["orb_dax", "us_momentum"]
REGIMES_CYCLED = [Regime.TREND, Regime.CALM, Regime.CRASH]
SKIP_FOR_CONFIG = {
    "baseline_F1234": set(),
    "drop_F1": {"F1"},
    "drop_F2": {"F2"},
    "drop_F3": {"F3"},
    "drop_F4": {"F4"},
    "all_off": {"F1", "F2", "F3", "F4"},
}


# ============================================================
# Cell evaluation — gather per-trade pnls in points
# ============================================================

def simulate_trade(df: pd.DataFrame, sig, entry_ts) -> tuple[float, str]:
    """Walk forward from entry_ts until SL/TP/force-close."""
    cet = "Europe/Berlin"
    after = df.loc[df.index > entry_ts]
    for ts, bar in after.iterrows():
        ts_cet = ts.tz_convert(cet)
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
        cutoff = FORCED_CLOSE_FRI if ts_cet.weekday() == 4 else FORCED_CLOSE_MON_THU
        if ts_cet.time() >= cutoff:
            close = float(bar["close"])
            pnl = close - sig.entry if sig.direction == "LONG" else sig.entry - close
            return pnl, "force_close"
    last = df.iloc[-1]
    close = float(last["close"])
    pnl = close - sig.entry if sig.direction == "LONG" else sig.entry - close
    return pnl, "end_of_feed"


def evaluate_cell(setup_name: str, regime: Regime, skip_filters: set,
                   df: pd.DataFrame, daily_history: pd.DataFrame,
                   regime_by_date: dict[dt.date, Regime],
                   cet_dates: pd.Series,
                   f5_override=None) -> dict:
    """Iterate window, collect signals + simulated trades for one cell."""
    if setup_name == "orb_dax":
        setup = OrbDaxSetupV331()
    elif setup_name == "us_momentum":
        setup = UsMomentumSetupV331()
    else:
        raise ValueError(setup_name)

    pnls_pts: list[float] = []
    n_signals = 0
    n_trades = 0
    pnls_train: list[float] = []
    pnls_test: list[float] = []
    train_cut = pd.Timestamp(TRAIN_END, tz="UTC")

    for ts in df.index:
        ts_cet = ts.tz_convert("Europe/Berlin")
        if not in_trading_window(ts_cet).allowed:
            continue
        if not before_hard_stop(ts_cet).allowed:
            continue
        today = ts_cet.date()
        active_regime = regime_by_date.get(today, Regime.UNDEFINED)
        if active_regime != regime:
            continue

        history = df.loc[:ts]
        today_session = df[cet_dates == today].loc[:ts]
        try:
            if setup_name == "orb_dax":
                sig = setup.check_entry_at(today_session, daily_history, ts,
                                            regime, history_5m=history,
                                            skip_filters=skip_filters,
                                            f5_override=f5_override)
            else:
                sig = setup.check_entry_at(history, daily_history, ts,
                                            regime, sp500_5m=None,
                                            skip_filters=skip_filters,
                                            f5_override=f5_override)
        except Exception:
            sig = None
        if sig is None:
            continue
        n_signals += 1
        sl_pts = abs(sig.entry - sig.sl)
        sized = calculate_lots_v331(
            "A" if sig.filters_met == sig.filters_total else "B",
            "normal", regime, sl_pts, EUR_USD,
            equity_usd=100_000, dax_price=float(df.loc[ts, "close"]))
        if sized.lots == 0:
            continue
        if not rrr_acceptable(sig.entry, sig.sl, sig.tp).allowed:
            continue
        pnl_pts, _ = simulate_trade(df, sig, ts)
        n_trades += 1
        pnls_pts.append(pnl_pts)
        if ts < train_cut:
            pnls_train.append(pnl_pts)
        else:
            pnls_test.append(pnl_pts)

    return {
        "setup": setup_name,
        "regime": regime.value,
        "config": "_".join(sorted(skip_filters)) if skip_filters else "baseline_F1234",
        "n_signals": n_signals,
        "n_trades": n_trades,
        "pnls_pts": pnls_pts,
        "pnls_train": pnls_train,
        "pnls_test": pnls_test,
    }


# ============================================================
# Cell metrics aggregation
# ============================================================

def cell_metrics(raw: dict) -> dict:
    pnls = raw["pnls_pts"]
    n = len(pnls)
    if n == 0:
        return {
            **raw, "wr": 0.0, "wr_ci_low": 0.0, "wr_ci_high": 0.0,
            "expectancy": 0.0, "exp_ci_low": 0.0, "exp_ci_high": 0.0,
            "sharpe": 0.0, "pf": 0.0, "max_dd": 0.0,
            "p_value": 1.0, "sample_flag": sample_size_flag(0),
            "median_pnl": 0.0, "p25": 0.0, "p75": 0.0, "std": 0.0,
        }
    wins = sum(1 for p in pnls if p > 0)
    wr = wins / n
    wr_lo, wr_hi = wilson_ci(wins, n)
    exp_lo, exp_hi = bootstrap_ci(pnls, n_iter=BOOTSTRAP_ITERS, seed=42)
    dist = cell_distribution(pnls)
    return {
        **raw, "wr": wr, "wr_ci_low": wr_lo, "wr_ci_high": wr_hi,
        "expectancy": expectancy(pnls), "exp_ci_low": exp_lo, "exp_ci_high": exp_hi,
        "sharpe": sharpe_ratio(pnls), "pf": profit_factor(pnls),
        "max_dd": dist.max_dd, "p_value": expectancy_pvalue(pnls),
        "sample_flag": sample_size_flag(n),
        "median_pnl": dist.median, "p25": dist.p25, "p75": dist.p75,
        "std": dist.std,
    }


# ============================================================
# Main runtime
# ============================================================

def build_regime_cache(df: pd.DataFrame, daily_history: pd.DataFrame,
                       h4_full: pd.DataFrame) -> dict[dt.date, Regime]:
    cet = "Europe/Berlin"
    regime_cache: dict[dt.date, Regime] = {}
    raw_history: list[Regime] = []
    active_regime: Optional[Regime] = None
    cet_dates_unique = sorted({t.tz_convert(cet).date() for t in df.index})
    for d in cet_dates_unique:
        ts_8 = pd.Timestamp(dt.datetime.combine(d, dt.time(8, 0)),
                             tz=cet).tz_convert("UTC").to_pydatetime()
        try:
            sig = derive_signals_from_market_data(daily_history, h4_full, df, ts_8)
            raw = classify_regime_raw(sig)
        except (ValueError, KeyError):
            raw = Regime.UNDEFINED
        active = get_active_regime(raw_history, raw, current_active=active_regime)
        regime_cache[d] = active
        raw_history.append(raw)
        active_regime = active
    return regime_cache


def run(parquet_path: Path, *, quick: bool = False) -> dict:
    """Execute full ablation. quick=True restricts to 2020 only for sanity check."""
    print(f"[ablation] loading {parquet_path}")
    feed = BarFeed.from_parquet(parquet_path)
    if quick:
        feed = feed.range("2020-01-01", "2020-04-01")
    print(f"[ablation] window: {feed.first} .. {feed.last} ({len(feed)} bars)")

    df = feed.to_dataframe()
    daily_history = aggregate_daily(df)
    h4_full = _aggregate_h4(df)
    cet_dates = pd.Series([t.tz_convert("Europe/Berlin").date() for t in df.index],
                          index=df.index)

    print("[ablation] building regime cache (per CET date)")
    regime_cache = build_regime_cache(df, daily_history, h4_full)
    regime_counts = {r: 0 for r in Regime}
    for r in regime_cache.values():
        regime_counts[r] += 1
    print(f"[ablation] regime distribution: { {k.value: v for k, v in regime_counts.items()} }")

    cells = []
    primary_count = len(SETUP_NAMES) * len(REGIMES_CYCLED) * len(CONFIGS)
    f5_count = len(ORB_CRASH_F5_CANDIDATES) + len(US_CALM_F5_CANDIDATES)
    total_cells = primary_count + f5_count
    print(f"[ablation] evaluating {primary_count} primary + {f5_count} F5 = {total_cells} cells")
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps({
        "started_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "total_cells": total_cells,
        "completed_cells": 0,
        "elapsed_s": 0,
        "eta_s": None,
        "current_cell": None,
        "status": "running",
    }, indent=2), encoding="utf-8")

    def _update_progress(idx: int, label: str, status: str = "running"):
        elapsed = time.time() - t0
        avg_per_cell = elapsed / max(idx, 1)
        eta_s = (total_cells - idx) * avg_per_cell if idx < total_cells else 0
        PROGRESS_PATH.write_text(json.dumps({
            "started_at_utc": dt.datetime.utcfromtimestamp(t0).isoformat() + "Z",
            "now_utc": dt.datetime.utcnow().isoformat() + "Z",
            "total_cells": total_cells,
            "completed_cells": idx,
            "pct": round(100 * idx / total_cells, 1),
            "elapsed_s": round(elapsed, 1),
            "eta_s": round(eta_s, 1),
            "current_cell": label,
            "status": status,
        }, indent=2), encoding="utf-8")
    for setup in SETUP_NAMES:
        for regime in REGIMES_CYCLED:
            for cfg in CONFIGS:
                skip = SKIP_FOR_CONFIG[cfg]
                raw = evaluate_cell(setup, regime, skip, df, daily_history,
                                     regime_cache, cet_dates)
                m = cell_metrics(raw)
                m["config"] = cfg
                cells.append(m)
                label = f"{setup}/{regime.value}/{cfg}"
                print(f"  {setup} {regime.value:10s} {cfg:18s} "
                      f"sig={m['n_signals']:5d} trd={m['n_trades']:5d} "
                      f"WR={m['wr']:.2f} exp={m['expectancy']:+.1f} "
                      f"flag={m['sample_flag']}")
                _update_progress(len(cells), label)
    # F5 cells — Exp #12 candidates
    for cand_name, cand_func in ORB_CRASH_F5_CANDIDATES.items():
        raw = evaluate_cell("orb_dax", Regime.CRASH, set(),
                             df, daily_history, regime_cache, cet_dates,
                             f5_override=cand_func)
        m = cell_metrics(raw)
        m["config"] = f"F5_CRASH:{cand_name}"
        cells.append(m)
        print(f"  orb_dax    CRASH      F5:{cand_name:22s} "
              f"sig={m['n_signals']:5d} trd={m['n_trades']:5d} "
              f"WR={m['wr']:.2f} exp={m['expectancy']:+.1f}")
        _update_progress(len(cells), f"orb_dax/CRASH/F5:{cand_name}")
    for cand_name, cand_func in US_CALM_F5_CANDIDATES.items():
        # Wrap us-style F5 (history, direction) signature to a uniform interface
        def _wrap(history, direction, _cf=cand_func):
            return _cf(history, direction)
        raw = evaluate_cell("us_momentum", Regime.CALM, set(),
                             df, daily_history, regime_cache, cet_dates,
                             f5_override=_wrap)
        m = cell_metrics(raw)
        m["config"] = f"F5_CALM:{cand_name}"
        cells.append(m)
        print(f"  us_momentum CALM      F5:{cand_name:22s} "
              f"sig={m['n_signals']:5d} trd={m['n_trades']:5d} "
              f"WR={m['wr']:.2f} exp={m['expectancy']:+.1f}")
        _update_progress(len(cells), f"us_momentum/CALM/F5:{cand_name}")
    _update_progress(len(cells), "all cells done", status="completed")
    print(f"[ablation] all cells done in {time.time() - t0:.1f}s")

    # FDR correction across cells
    pvalues = [c["p_value"] for c in cells]
    fdr_rej = fdr_bh(pvalues, alpha=ALPHA)
    bonf_rej = bonferroni(pvalues, alpha=ALPHA)
    for c, fr, br in zip(cells, fdr_rej, bonf_rej):
        c["fdr_significant"] = bool(fr)
        c["bonferroni_significant"] = bool(br)

    # OOS validation (per-cell train vs test expectancy)
    for c in cells:
        train_exp = expectancy(c["pnls_train"]) if c["pnls_train"] else 0.0
        test_exp = expectancy(c["pnls_test"]) if c["pnls_test"] else 0.0
        oos = oos_validate(train_exp, test_exp)
        c["train_expectancy"] = train_exp
        c["test_expectancy"] = test_exp
        c["oos_pass"] = oos.pass_
        c["oos_reason"] = oos.reason

    return {
        "cells": cells,
        "n_cells": len(cells),
        "regime_counts": {k.value: v for k, v in regime_counts.items()},
    }


# ============================================================
# Output writers
# ============================================================

def write_master_csv(cells: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["setup", "regime", "config", "sample_flag",
            "n_signals", "n_trades",
            "wr", "wr_ci_low", "wr_ci_high",
            "expectancy", "exp_ci_low", "exp_ci_high",
            "median_pnl", "p25", "p75", "std",
            "sharpe", "pf", "max_dd",
            "p_value", "fdr_significant", "bonferroni_significant",
            "train_expectancy", "test_expectancy",
            "oos_pass", "oos_reason"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in cells:
            w.writerow({k: c.get(k, "") for k in cols})


def write_oos_md(cells: list[dict], path: Path) -> None:
    lines = ["# OOS Validation — Extended Ablation",
             "", f"**Train period:** 2019-01-01 .. {TRAIN_END}",
             f"**Test period:**  {TEST_START} .. {WINDOW_END}",
             "", f"**Acceptance:** test_expectancy ≥ 0.7 × train_expectancy",
             "", "| setup | regime | config | train_exp | test_exp | ratio | OOS pass | reason |",
             "|---|---|---|---:|---:|---:|---|---|"]
    for c in cells:
        ratio = (c["test_expectancy"] / c["train_expectancy"]
                 if c["train_expectancy"] else 0.0)
        lines.append(f"| {c['setup']} | {c['regime']} | {c['config']} | "
                     f"{c['train_expectancy']:+.2f} | {c['test_expectancy']:+.2f} | "
                     f"{ratio:.2f} | {'✓' if c['oos_pass'] else '✗'} | {c['oos_reason']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_fdr_csv(cells: list[dict], path: Path) -> None:
    cols = ["setup", "regime", "config", "p_value", "fdr_significant",
            "bonferroni_significant"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for c in cells:
            w.writerow({k: c.get(k, "") for k in cols})


# ============================================================
# Auto-start polling for Dukascopy
# ============================================================

def poll_dukascopy_done(log_path: Path, poll_s: int = 60,
                          max_wait_s: int = 30 * 60 * 60) -> bool:
    """Poll until Dukascopy log shows completion. Returns True if done."""
    print(f"[ablation] polling Dukascopy log {log_path} every {poll_s}s (max {max_wait_s}s)")
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        if not log_path.exists():
            time.sleep(poll_s); continue
        text = log_path.read_text(errors="ignore")
        if "[extend] download counts:" in text or "[extend] validation summary:" in text:
            return True
        time.sleep(poll_s)
    return False


# ============================================================
# Main
# ============================================================

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--auto-start", action="store_true",
                   help="poll Dukascopy log, then run on extended parquet")
    p.add_argument("--quick", action="store_true",
                   help="restrict to 2020 Q1 for sanity (fast)")
    p.add_argument("--parquet", type=Path, default=None,
                   help="explicit parquet input (default: 2019-2023 or 2015-2026)")
    a = p.parse_args()

    parquet = a.parquet
    if parquet is None:
        parquet = EXTENDED_PARQUET if EXTENDED_PARQUET.exists() else PARQUET
    if a.auto_start:
        log = ROOT / "logs" / "extend_dukascopy_2015-2018.log"
        if not poll_dukascopy_done(log):
            print("[ablation] Dukascopy did not complete within budget; aborting.")
            return 1

    if not parquet.exists():
        print(f"[ablation] parquet not found: {parquet}", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = run(parquet, quick=a.quick)
    print(f"[ablation] {out['n_cells']} cells evaluated")
    write_master_csv(out["cells"], OUT_DIR / "master_table.csv")
    write_oos_md(out["cells"], OUT_DIR / "oos_validation.md")
    write_fdr_csv(out["cells"], OUT_DIR / "fdr_corrected_pvalues.csv")
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps({
        "n_cells": out["n_cells"],
        "regime_counts": out["regime_counts"],
        "alpha": ALPHA,
        "bootstrap_iters": BOOTSTRAP_ITERS,
        "acceptance_boost_pct": ACCEPTANCE_BOOST_PCT,
        "train_end": TRAIN_END,
        "test_start": TEST_START,
    }, indent=2), encoding="utf-8")
    print(f"[ablation] outputs -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
