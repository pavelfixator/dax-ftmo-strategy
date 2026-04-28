"""US-MOM TREND stress test — v3.3.4 CORRECT analytical math.

Replaces previous trend_stress_test.py (which re-ran cell with patched buffer
and produced counterintuitive "wider stops increase expectancy" — that result
came from buffer change shifting which trades hit SL vs TP, but DID NOT charge
the additional buffer cost properly).

CORRECT FORMULA per Architekt v3.3.4 spec:
  Each trade pays the spread+slippage buffer twice (entry + exit).
  Increasing buffer by `delta_buffer = baseline × (multiplier - 1)` adds delta
  cost to every trade, regardless of outcome.

  Projected expectancy:
    new_exp = baseline_exp - delta_buffer
    where delta_buffer = baseline_buffer × (multiplier - 1)

For US-MOM TREND baseline expectancy +3.28 pts, baseline buffer 3.5 pts:

  Multiplier  Δ buffer  Projected exp     v3.3.4 acceptance
  ----------  --------  ---------------    ------------------
  1.0×           +0.0   +3.28 pts          KEEP unchanged
  1.5×           +1.75  +3.28 - 1.75 = +1.53 pts   KEEP s WARNING
  2.0×           +3.5   +3.28 - 3.5 = -0.22 pts    DROP (< +0.5 threshold)
  3.0×           +7.0   +3.28 - 7.0 = -3.72 pts    DROP (informativní)

Acceptance v3.3.2.1 (kept v3.3.4):
  pessimistic ×2.0 ≥ +0.5 pts → KEEP
  pessimistic ×2.0 < +0.5 pts → DROP US-MOM TREND

Output: experiments/exp_trend_stress_test_v2.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "experiments" / "exp_trend_stress_test_v2.md"
PHASE0_SUMMARY = ROOT / "experiments" / "phase0" / "summary.json"

BASELINE_BUFFER_PTS = 3.5    # spread 1.5 + slippage 2.0
THRESHOLD_PESSIMISTIC = 0.5  # v3.3.2.1+v3.3.4

SCENARIOS = [
    ("baseline", 1.0),
    ("mild_x1.5", 1.5),
    ("pessimistic_x2.0", 2.0),
    ("extreme_x3.0", 3.0),
]


def project(baseline_exp: float, multiplier: float,
            baseline_buffer: float = BASELINE_BUFFER_PTS) -> dict:
    delta_buffer = baseline_buffer * (multiplier - 1)
    new_buffer = baseline_buffer * multiplier
    projected_exp = baseline_exp - delta_buffer
    return {"multiplier": multiplier, "buffer": new_buffer,
            "delta_buffer": delta_buffer,
            "projected_exp_pts": projected_exp}


def classify(scenarios: list[dict], threshold: float = THRESHOLD_PESSIMISTIC) -> dict:
    pess = next((s for s in scenarios if s["multiplier"] == 2.0), None)
    pess_exp = pess["projected_exp_pts"] if pess else 0.0
    if pess_exp < threshold:
        return {"verdict": "DROP US-MOM TREND",
                "reason": f"pessimistic projected exp {pess_exp:+.2f} < {threshold} threshold",
                "pessimistic_projected_exp": pess_exp}
    if pess_exp < threshold + 1.0:
        return {"verdict": "KEEP with WARNING",
                "reason": f"pessimistic projected exp {pess_exp:+.2f} (borderline)",
                "pessimistic_projected_exp": pess_exp}
    return {"verdict": "KEEP",
            "reason": f"pessimistic projected exp {pess_exp:+.2f} > {threshold} threshold",
            "pessimistic_projected_exp": pess_exp}


def _baseline_exp_from_phase0() -> float | None:
    if not PHASE0_SUMMARY.exists():
        return None
    s = json.loads(PHASE0_SUMMARY.read_text(encoding="utf-8"))
    for c in s.get("active_cells", []):
        if c["setup"] == "us_momentum" and c["regime"] == "TREND":
            return float(c["expectancy"])
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--baseline-exp", type=float, default=None,
                   help="override baseline expectancy (default: from phase0/summary.json)")
    a = p.parse_args()
    baseline = a.baseline_exp if a.baseline_exp is not None else _baseline_exp_from_phase0()
    if baseline is None:
        baseline = 3.28
        note = "(default 3.28 pts; phase0 summary not available)"
    else:
        note = f"(loaded from phase0/summary.json: us_momentum/TREND exp={baseline:+.2f})"
    print(f"[stress_v2] baseline expectancy: {baseline:+.2f} pts {note}")

    rows = [project(baseline, mult) | {"label": label} for label, mult in SCENARIOS]
    verdict = classify(rows)
    print()
    print(f"{'scenario':22s} {'mult':>5s} {'Δbuffer':>8s} {'new_buffer':>11s} {'projected':>11s}")
    for r in rows:
        print(f"{r['label']:22s} {r['multiplier']:>5.1f} "
              f"{r['delta_buffer']:>+8.2f} {r['buffer']:>11.2f} {r['projected_exp_pts']:>+11.2f}")
    print()
    print(f"VERDICT: {verdict['verdict']} ({verdict['reason']})")

    lines = [
        "# US-MOM TREND Stress Test — v3.3.4 CORRECT (analytical incremental delta)",
        "",
        f"**Verdict: {verdict['verdict']}**",
        "",
        f"Reason: {verdict['reason']}",
        "",
        f"## Methodology v3.3.4",
        "",
        "Replaces previous trend_stress_test.py (re-ran cell with patched buffer,",
        "produced counterintuitive 'wider stops increase expectancy' result — that",
        "was an artifact of which trades hit SL vs TP, NOT actual buffer cost charge).",
        "",
        "CORRECT formula:",
        "  delta_buffer = baseline_buffer × (multiplier - 1)",
        "  projected_exp = baseline_exp - delta_buffer",
        "",
        f"Baseline buffer: {BASELINE_BUFFER_PTS} pts (spread 1.5 + slippage 2.0).",
        f"Baseline expectancy (US-MOM TREND from Phase 0 backtest): {baseline:+.2f} pts.",
        "",
        "## Per-scenario projection",
        "",
        "| scenario | multiplier | Δ buffer | new buffer | projected exp |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(f"| {r['label']} | {r['multiplier']:.1f}× | "
                     f"{r['delta_buffer']:+.2f} | {r['buffer']:.2f} | "
                     f"{r['projected_exp_pts']:+.2f} |")
    lines += [
        "",
        "## Acceptance (v3.3.2.1+v3.3.4)",
        f"- pessimistic ×2.0 ≥ +{THRESHOLD_PESSIMISTIC} pts → KEEP",
        f"- pessimistic ×2.0 < +{THRESHOLD_PESSIMISTIC} pts → DROP US-MOM TREND",
        "",
        f"**Pessimistic projected expectancy: {verdict['pessimistic_projected_exp']:+.2f} pts**",
        f"**Verdict: {verdict['verdict']}**",
        "",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[stress_v2] -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
