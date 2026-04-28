"""Validate Phase 0 → Phase 1 gate criteria for v3.3.4 (18 gates).

Asymmetric gate #1 (v3.3.2.1+):
  US-MOM ≥ 500 trades total
  ORB-DAX CALM ≥ 100 trades

Gate #15 uniform (v3.3.4 reformulation):
  Pass: PF ≥1.5 AND (WR ≥40% OR R-multiple ≥2.0)
  R-multiple = PF × (1-WR) / WR

Gate #18 NEW (v3.3.4): Challenge Success Rate via Block Bootstrap
  ≥70% PASS / 60-70% WARNING / <60% FAIL

Reads:
  experiments/extended_ablation/master_table.csv
  experiments/phase0/active_cells.csv (when Sekce 6B run)
  experiments/phase0/summary.json
  experiments/rolling_30day_decision.md
  experiments/exp_gate18_challenge_success.md

Output:
  experiments/gate_criteria_validation.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ABLATION_DIR = ROOT / "experiments" / "extended_ablation"
PHASE0_DIR = ROOT / "experiments" / "phase0"
ROLLING_DECISION = ROOT / "experiments" / "rolling_30day_decision.md"
GATE18_OUT = ROOT / "experiments" / "exp_gate18_challenge_success.md"
OUT_PATH = ROOT / "experiments" / "gate_criteria_validation.md"

GATE1_USM_MIN = 500
GATE1_ORB_CALM_MIN = 100
GATE2_WR_MIN = 0.50
GATE3_PF_MIN = 1.5
GATE4_SHARPE_MIN = 1.0
GATE5_SORTINO_MIN = 1.3
GATE6_MAX_DD_PCT_MAX = 0.08
GATE7_RISK_OF_RUIN_MAX = 0.01
GATE8_P_HARD_STOP_MAX = 0.15
GATE9_OOS_RATIO_MIN = 0.80          # uniform 80% kept (acknowledged as Strategy Limitation)
GATE14_PER_REGIME_MIN = 50
GATE15_PF_MIN = 1.5
GATE15_WR_MIN = 0.40
GATE15_R_MULT_MIN = 2.0
GATE18_PASS_PCT = 0.70
GATE18_WARNING_PCT = 0.60


def _read_csv(path: Path):
    return pd.read_csv(path) if path.exists() else None


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ---------- gate calculators ----------

def gate1_sample_size(master: pd.DataFrame) -> dict:
    if master is None or master.empty:
        return {"verdict": "INSUFFICIENT_DATA"}
    usm = master[master["setup"] == "us_momentum"]["n_trades"].sum()
    orb_calm = master[(master["setup"] == "orb_dax")
                       & (master["regime"] == "CALM")]["n_trades"].sum()
    pass_usm = usm >= GATE1_USM_MIN
    pass_orb = orb_calm >= GATE1_ORB_CALM_MIN
    return {
        "verdict": "PASS" if (pass_usm and pass_orb) else "FAIL",
        "us_momentum_trades": int(usm),
        "us_momentum_pass": bool(pass_usm),
        "orb_dax_calm_trades": int(orb_calm),
        "orb_dax_calm_pass": bool(pass_orb),
    }


def gate14_per_regime(master: pd.DataFrame) -> dict:
    if master is None or master.empty:
        return {"verdict": "INSUFFICIENT_DATA"}
    by = master.groupby("regime")["n_trades"].sum()
    fails = by[by < GATE14_PER_REGIME_MIN]
    rolling = _read_rolling_verdict()
    base_pass = fails.empty
    rolling_pass = rolling in ("PASS", "WARNING")
    if base_pass and rolling == "PASS":
        verdict = "PASS"
    elif base_pass and rolling == "WARNING":
        verdict = "WARNING"
    else:
        verdict = "FAIL"
    return {
        "verdict": verdict,
        "per_regime_pass": bool(base_pass),
        "per_regime_counts": {k: int(v) for k, v in by.items()},
        "per_regime_fails": list(fails.index) if not fails.empty else [],
        "rolling_30day_verdict": rolling,
    }


def gate15_uniform_per_cell(active_cells: pd.DataFrame) -> dict:
    """Gate #15 v3.3.4: PF ≥1.5 AND (WR ≥40% OR R-multiple ≥2.0).

    R-multiple = PF × (1-WR) / WR  (avg win/avg loss in $).
    Per active cell.
    """
    if active_cells is None or active_cells.empty:
        return {"verdict": "INSUFFICIENT_DATA"}
    rows = []
    fails = []
    for _, c in active_cells.iterrows():
        wr = float(c["wr"])
        pf = float(c["pf"])
        if wr <= 0 or wr >= 1:
            r_mult = float("inf")
        else:
            r_mult = pf * (1 - wr) / wr
        cond_a = pf >= GATE15_PF_MIN
        cond_b = (wr >= GATE15_WR_MIN) or (r_mult >= GATE15_R_MULT_MIN)
        cell_pass = cond_a and cond_b
        rows.append({
            "setup": c["setup"], "regime": c["regime"],
            "wr": wr, "pf": pf, "r_multiple": r_mult,
            "pass": bool(cell_pass),
            "reason": ("PF<1.5" if not cond_a else
                       ("WR<40 AND R-mult<2.0" if not cond_b else "OK")),
        })
        if not cell_pass:
            fails.append(f"{c['setup']}/{c['regime']}")
    overall = "PASS" if not fails else "FAIL"
    return {
        "verdict": overall,
        "per_cell": rows,
        "failed_cells": fails,
    }


def gate9_walk_forward(phase0_summary: dict | None) -> dict:
    if phase0_summary is None:
        return {"verdict": "NOT_RUN"}
    wfs = phase0_summary.get("walk_forward_summary", {})
    pct = wfs.get("oos_pass_pct", 0) / 100.0
    pass_ = pct >= GATE9_OOS_RATIO_MIN
    return {
        "verdict": "PASS" if pass_ else "FAIL",
        "oos_pass_pct": pct,
        "n_windows": wfs.get("n_windows", 0),
        "oos_pass_count": wfs.get("oos_pass_count", 0),
        "note": ("Strategy Limitation acknowledged v3.3.4: 6m windows produce"
                 " unstable expectancy due to regime-dependent edge."),
    }


def gate6_8_montecarlo(phase0_summary: dict | None) -> dict:
    if phase0_summary is None:
        return {"verdict": "NOT_RUN"}
    mc = phase0_summary.get("monte_carlo", {})
    if not mc:
        return {"verdict": "NOT_RUN"}
    g6 = abs(mc.get("max_dd_pct_5p", 0)) <= GATE6_MAX_DD_PCT_MAX
    g7 = mc.get("risk_of_ruin", 1) <= GATE7_RISK_OF_RUIN_MAX
    g8 = mc.get("p_hard_stop", 1) <= GATE8_P_HARD_STOP_MAX
    g4 = mc.get("sharpe", {}).get("mean", 0) >= GATE4_SHARPE_MIN
    return {
        "gate4_sharpe": {"verdict": "PASS" if g4 else "FAIL",
                          "value": mc.get("sharpe", {}).get("mean", 0)},
        "gate6_max_dd": {"verdict": "PASS" if g6 else "FAIL",
                          "value": mc.get("max_dd_pct_5p", 0)},
        "gate7_ror":   {"verdict": "PASS" if g7 else "FAIL",
                          "value": mc.get("risk_of_ruin", 0)},
        "gate8_phs":   {"verdict": "PASS" if g8 else "FAIL",
                          "value": mc.get("p_hard_stop", 0)},
    }


def gate18_challenge_success() -> dict:
    """Read gate18_block_bootstrap output and apply 70/60% thresholds."""
    if not GATE18_OUT.exists():
        return {"verdict": "NOT_RUN"}
    text = GATE18_OUT.read_text(encoding="utf-8")
    m = re.search(r"success_rate[^\d]*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if not m:
        return {"verdict": "PARSE_ERROR", "raw_excerpt": text[:200]}
    pct = float(m.group(1))
    if pct > 1.5:  # value already in % (e.g. 73.4)
        pct = pct / 100.0
    if pct >= GATE18_PASS_PCT:
        verdict = "PASS"
    elif pct >= GATE18_WARNING_PCT:
        verdict = "WARNING"
    else:
        verdict = "FAIL"
    return {"verdict": verdict, "success_rate": pct}


def _read_rolling_verdict() -> str:
    if not ROLLING_DECISION.exists():
        return "NOT_RUN"
    for line in ROLLING_DECISION.read_text(encoding="utf-8").splitlines():
        if line.startswith("**Verdict:**"):
            return line.split("**")[-2].strip()
    return "UNKNOWN"


def assemble_report(payload: dict) -> str:
    g = payload
    lines = [
        "# Phase 0 → Phase 1 Gate Criteria Validation (v3.3.4)",
        "",
        f"- Asymetric gate #1: US-MOM ≥{GATE1_USM_MIN} / ORB-DAX CALM ≥{GATE1_ORB_CALM_MIN}",
        f"- Gate #9 walk-forward: uniform {int(GATE9_OOS_RATIO_MIN*100)}% (Strategy Limitation v3.3.4)",
        f"- Gate #15 v3.3.4: PF ≥{GATE15_PF_MIN} AND (WR ≥{int(GATE15_WR_MIN*100)}% OR R-multiple ≥{GATE15_R_MULT_MIN})",
        f"- Gate #18 NEW: Challenge Success Rate ≥{int(GATE18_PASS_PCT*100)}% PASS / {int(GATE18_WARNING_PCT*100)}-{int(GATE18_PASS_PCT*100)}% WARNING / <{int(GATE18_WARNING_PCT*100)}% FAIL",
        "",
        f"## Gate #1 sample size: **{g['gate1']['verdict']}**",
        f"- US-MOM trades {g['gate1'].get('us_momentum_trades','—')} / {GATE1_USM_MIN} → {'✓' if g['gate1'].get('us_momentum_pass') else '✗'}",
        f"- ORB-DAX CALM trades {g['gate1'].get('orb_dax_calm_trades','—')} / {GATE1_ORB_CALM_MIN} → {'✓' if g['gate1'].get('orb_dax_calm_pass') else '✗'}",
        "",
        f"## Gates #4/#6/#7/#8 (Monte Carlo)",
        f"- #4 Sharpe ≥{GATE4_SHARPE_MIN}:    **{g['mc']['gate4_sharpe']['verdict']}** (value {g['mc']['gate4_sharpe']['value']:.2f})" if g.get("mc") else "- not run",
        f"- #6 Max DD ≤{GATE6_MAX_DD_PCT_MAX*100}%: **{g['mc']['gate6_max_dd']['verdict']}** (value {abs(g['mc']['gate6_max_dd']['value'])*100:.2f}%)" if g.get("mc") else "",
        f"- #7 Risk of Ruin <{GATE7_RISK_OF_RUIN_MAX*100}%: **{g['mc']['gate7_ror']['verdict']}** (value {g['mc']['gate7_ror']['value']*100:.2f}%)" if g.get("mc") else "",
        f"- #8 P(HARD STOP) <{GATE8_P_HARD_STOP_MAX*100}%: **{g['mc']['gate8_phs']['verdict']}** (value {g['mc']['gate8_phs']['value']*100:.2f}%)" if g.get("mc") else "",
        "",
        f"## Gate #9 walk-forward: **{g['gate9']['verdict']}**",
        f"- {g['gate9'].get('oos_pass_count','—')}/{g['gate9'].get('n_windows','—')} = {g['gate9'].get('oos_pass_pct',0)*100:.1f}% pass (need {int(GATE9_OOS_RATIO_MIN*100)}%)",
        f"- {g['gate9'].get('note','')}",
        "",
        f"## Gate #14 per-regime + rolling: **{g['gate14']['verdict']}**",
        f"- per-regime counts: {g['gate14'].get('per_regime_counts','—')}",
        f"- rolling 30d verdict: **{g['gate14'].get('rolling_30day_verdict','—')}**",
        "",
        f"## Gate #15 uniform v3.3.4: **{g['gate15']['verdict']}**",
        "Per-cell:",
    ]
    for c in g["gate15"].get("per_cell", []):
        lines.append(f"- {c['setup']}/{c['regime']}: PF={c['pf']:.2f} WR={c['wr']:.2%} "
                     f"R-mult={c['r_multiple']:.2f} → {'PASS' if c['pass'] else 'FAIL'} "
                     f"({c['reason']})")
    lines += [
        "",
        f"## Gate #18 Challenge Success Rate (v3.3.4 NEW): **{g['gate18']['verdict']}**",
        f"- success rate: {g['gate18'].get('success_rate', 0) * 100:.1f}% "
        f"(threshold ≥{int(GATE18_PASS_PCT*100)}% PASS, ≥{int(GATE18_WARNING_PCT*100)}% WARNING)",
        "",
        "## Gates pending separate computations",
        "- #2 WR aggregate / #3 PF aggregate / #5 Sortino / #11 close framework / #12 swap coverage / #13 BSC audit / #16 ablation positive / #17 classifier accuracy",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=OUT_PATH)
    a = p.parse_args()
    master = _read_csv(ABLATION_DIR / "master_table.csv")
    active = _read_csv(PHASE0_DIR / "active_cells.csv")
    p0 = _read_json(PHASE0_DIR / "summary.json")

    payload = {
        "gate1": gate1_sample_size(master),
        "gate14": gate14_per_regime(master),
        "gate15": gate15_uniform_per_cell(active),
        "gate9": gate9_walk_forward(p0),
        "mc": gate6_8_montecarlo(p0),
        "gate18": gate18_challenge_success(),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(assemble_report(payload), encoding="utf-8")
    print(json.dumps(payload, indent=2, default=str))
    print(f"[gate] -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
