"""Validate Phase 0 → Phase 1 17 gate criteria for v3.3.2.1.

Asymmetric gate #1 (UPDATED v3.3.2.1):
  US-MOM ≥ 500 trades total
  ORB-DAX CALM ≥ 100 trades

Extended gate #14 (UPDATED v3.3.2.1):
  Per-regime ≥ 50 trades AND
  + 30-day rolling validation (rolling_30day_validation.py)

Reads:
  experiments/extended_ablation/master_table.csv (cell trades, WR, etc.)
  experiments/rolling_30day_decision.md (rolling validation verdict)
  Phase 0 backtest output (Sekce 6 Cast B) — TBD

Output:
  experiments/gate_criteria_validation.md (per-criterion PASS/FAIL/WARNING)

Used in Sekce 6 Cast B once full backtest is run, but stub helpers can be
exercised with current ablation data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ABLATION_DIR = ROOT / "experiments" / "extended_ablation"
ROLLING_DECISION = ROOT / "experiments" / "rolling_30day_decision.md"
OUT_PATH = ROOT / "experiments" / "gate_criteria_validation.md"

# Asymmetric thresholds v3.3.2.1
GATE1_USM_MIN = 500
GATE1_ORB_CALM_MIN = 100
GATE2_WR_MIN = 0.50
GATE3_PF_MIN = 1.5
GATE4_SHARPE_MIN = 1.0
GATE5_SORTINO_MIN = 1.3
GATE6_MAX_DD_PCT_MAX = 0.08
GATE7_RISK_OF_RUIN_MAX = 0.01
GATE8_P_HARD_STOP_MAX = 0.15
GATE9_OOS_RATIO_MIN = 0.80
GATE14_PER_REGIME_MIN = 50


def _read_master() -> pd.DataFrame | None:
    path = ABLATION_DIR / "master_table.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def gate1_sample_size(master: pd.DataFrame) -> dict:
    """Asymmetric gate #1: US-MOM ≥ 500 total, ORB-DAX CALM ≥ 100."""
    if master is None or master.empty:
        return {"verdict": "INSUFFICIENT_DATA"}
    usm = master[master["setup"] == "us_momentum"]["n_trades"].sum()
    orb_calm = master[(master["setup"] == "orb_dax")
                       & (master["regime"] == "CALM")]["n_trades"].sum()
    pass_usm = usm >= GATE1_USM_MIN
    pass_orb = orb_calm >= GATE1_ORB_CALM_MIN
    verdict = "PASS" if (pass_usm and pass_orb) else "FAIL"
    return {
        "verdict": verdict,
        "us_momentum_trades": int(usm),
        "us_momentum_threshold": GATE1_USM_MIN,
        "us_momentum_pass": bool(pass_usm),
        "orb_dax_calm_trades": int(orb_calm),
        "orb_dax_calm_threshold": GATE1_ORB_CALM_MIN,
        "orb_dax_calm_pass": bool(pass_orb),
    }


def gate14_per_regime(master: pd.DataFrame) -> dict:
    """Per-regime ≥50 trades + 30-day rolling result."""
    if master is None or master.empty:
        return {"verdict": "INSUFFICIENT_DATA"}
    by_regime = master.groupby("regime")["n_trades"].sum()
    fails = by_regime[by_regime < GATE14_PER_REGIME_MIN]
    rolling_verdict = _read_rolling_verdict()
    base_pass = fails.empty
    rolling_pass = rolling_verdict in ("PASS", "WARNING")
    verdict = "PASS" if (base_pass and rolling_pass) else (
        "WARNING" if (base_pass and rolling_verdict == "WARNING") else "FAIL"
    )
    return {
        "verdict": verdict,
        "per_regime_pass": bool(base_pass),
        "per_regime_counts": {k: int(v) for k, v in by_regime.items()},
        "per_regime_fails": list(fails.index) if not fails.empty else [],
        "rolling_30day_verdict": rolling_verdict,
    }


def _read_rolling_verdict() -> str:
    if not ROLLING_DECISION.exists():
        return "NOT_RUN"
    text = ROLLING_DECISION.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("**Verdict:**"):
            # "**Verdict:** **PASS**"
            return line.split("**")[-2].strip()
    return "UNKNOWN"


def assemble_report(gate1: dict, gate14: dict) -> str:
    lines = [
        "# Phase 0 → Phase 1 Gate Criteria Validation (v3.3.2.1)",
        "",
        "Stub validation. Full Sekce 6 Cast B backtest will populate gates 2-13.",
        "",
        "## Gate #1 — Sample size (asymmetric v3.3.2.1)",
        "",
        f"- **Verdict:** **{gate1.get('verdict','—')}**",
        f"- US-MOM trades: {gate1.get('us_momentum_trades','—')} / {gate1.get('us_momentum_threshold','—')} → {'✓' if gate1.get('us_momentum_pass') else '✗'}",
        f"- ORB-DAX CALM trades: {gate1.get('orb_dax_calm_trades','—')} / {gate1.get('orb_dax_calm_threshold','—')} → {'✓' if gate1.get('orb_dax_calm_pass') else '✗'}",
        "",
        "## Gate #14 — Per-regime + Rolling 30d (extended v3.3.2.1)",
        "",
        f"- **Verdict:** **{gate14.get('verdict','—')}**",
        f"- Per-regime ≥50 trades: {'✓' if gate14.get('per_regime_pass') else '✗'}",
        f"- Per-regime counts: {gate14.get('per_regime_counts',{})}",
        f"- Per-regime fails: {gate14.get('per_regime_fails',[])}",
        f"- Rolling 30-day verdict: **{gate14.get('rolling_30day_verdict','—')}**",
        "",
        "## Gates #2-#13 + #15-#17",
        "",
        "Pending Sekce 6 Cast B (full Phase 0 backtest with Monte Carlo, walk-forward,",
        "what-if, regime classifier accuracy 6 known events).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=OUT_PATH)
    a = p.parse_args()
    master = _read_master()
    g1 = gate1_sample_size(master)
    g14 = gate14_per_regime(master)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(assemble_report(g1, g14), encoding="utf-8")
    print(json.dumps({"gate1": g1, "gate14": g14}, indent=2, default=str))
    print(f"[gate] -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
