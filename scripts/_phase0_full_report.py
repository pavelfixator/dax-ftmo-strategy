"""One-shot full report dump for Pavel Sekce 6B review."""
import json
import collections
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
s = json.load(open(ROOT / "experiments" / "phase0" / "summary.json"))


def hdr(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


# ============ 7. Per-regime breakdown ============
hdr("7. PER-REGIME BREAKDOWN (active cells)")
print(f"{'setup':12s} {'regime':6s} {'n':>4s} {'WR':>5s} {'exp_pts':>8s} "
      f"{'sharpe':>7s} {'PF':>5s} {'max_dd':>10s} {'flag':<8s}")
for c in s["active_cells"]:
    print(f"{c['setup']:12s} {c['regime']:6s} {c['n_trades']:4d} "
          f"{c['wr']:5.2f} {c['expectancy']:+8.2f} {c['sharpe']:7.2f} "
          f"{c['pf']:5.2f} {c['max_dd_pts']:10.1f} {c['sample_flag']}")

agg = collections.defaultdict(lambda: {"n": 0, "pnl": 0, "dd": 0})
for c in s["active_cells"]:
    agg[c["regime"]]["n"] += c["n_trades"]
    agg[c["regime"]]["pnl"] += c["n_trades"] * c["expectancy"]
    if c["max_dd_pts"] < agg[c["regime"]]["dd"]:
        agg[c["regime"]]["dd"] = c["max_dd_pts"]
print()
print("Per-regime aggregate:")
for r in sorted(agg):
    d = agg[r]
    avg = d["pnl"] / d["n"] if d["n"] else 0
    print(f"  {r}: n={d['n']}, total_pnl={d['pnl']:+.0f}pts, "
          f"avg_exp={avg:+.2f}pts, worst_max_dd={d['dd']:.1f}pts")

# ============ 6. Monte Carlo ============
hdr("6. MONTE CARLO 10 000 ITER")
mc = s["monte_carlo"]
print(f"  P&L total mean:   ${mc['pnl_total_usd']['mean']:+.0f}")
print(f"  P&L total median: ${mc['pnl_total_usd']['median']:+.0f}")
print(f"  P&L total p5:     ${mc['pnl_total_usd']['p5']:+.0f}")
print(f"  P&L total p95:    ${mc['pnl_total_usd']['p95']:+.0f}")
print()
print(f"  Max DD mean:  ${mc['max_dd_usd']['mean']:.0f}")
print(f"  Max DD p5:    ${mc['max_dd_usd']['p5']:.0f}  "
      f"({mc['max_dd_pct_5p']*100:.2f}% of equity) [GATE #6 <8%]")
print(f"  Max DD p50:   ${mc['max_dd_usd']['p50']:.0f}")
print(f"  Max DD p95:   ${mc['max_dd_usd']['p95']:.0f}")
print()
print(f"  Sharpe mean:    {mc['sharpe']['mean']:.2f}  [GATE #4 >=1.0]")
print(f"  Sharpe p5:      {mc['sharpe']['p5']:.2f}")
print(f"  P(HARD STOP):   {mc['p_hard_stop']*100:.2f}%  [GATE #8 <15%]")
print(f"  Risk of Ruin:   {mc['risk_of_ruin']*100:.2f}%  [GATE #7 <1%]")

# ============ 2. Walk-forward ============
hdr("2. WALK-FORWARD (gate #9 >=80%)")
wfs = s["walk_forward_summary"]
print(f"n windows: {wfs['n_windows']}")
print(f"OOS pass:  {wfs['oos_pass_count']}/{wfs['n_windows']} = {wfs['oos_pass_pct']:.1f}%")
print(f"VERDICT: FAIL (need >=80%, actual 9.5%)")
print()
wf = pd.read_csv(ROOT / "experiments" / "phase0" / "walk_forward.csv")
print(f"{'train_start':12s} {'train_end':12s} {'test_end':12s} "
      f"{'n_tr':>5s} {'n_te':>5s} {'train_exp':>10s} {'test_exp':>10s} {'pass':<6s}")
for _, row in wf.iterrows():
    print(f"{str(row['train_start']):12s} {str(row['train_end']):12s} "
          f"{str(row['test_end']):12s} "
          f"{int(row['n_train']):5d} {int(row['n_test']):5d} "
          f"{row['train_expectancy']:+10.2f} {row['test_expectancy']:+10.2f} "
          f"{str(row['oos_pass']):<6s}")
print()
print("Train vs test summary:")
print(f"  mean train_exp: {wf['train_expectancy'].mean():+.2f}")
print(f"  mean test_exp:  {wf['test_expectancy'].mean():+.2f}")
print(f"  consistency (test/train if train>0): "
      f"{(wf['test_expectancy']/wf['train_expectancy'].where(wf['train_expectancy']>0)).dropna().median():+.2f}")

# ============ 5. Bonferroni ============
hdr("5. BONFERRONI FINAL (4-cell subset)")
bonf = pd.read_csv(ROOT / "experiments" / "bonferroni_final.csv")
for _, r in bonf.iterrows():
    fdr_full = r["fdr_significant_in_full_44cell_run"]
    print(f"  {r['setup']:12s} {r['regime']:6s} {r['config']:20s} "
          f"n={int(r['n_trades']):5d} p={r['p_value']:.4f} "
          f"exp={r['expectancy']:+.2f} "
          f"bonf={'PASS' if r['bonferroni_pass_4cell_subset'] else 'FAIL':<4s} "
          f"fdr={'PASS' if r['fdr_pass_4cell_subset'] else 'FAIL':<4s} "
          f"fdr_44={fdr_full}")

# ============ 3. TREND stress test ============
hdr("3. TREND STRESS TEST (US-MOM)")
stress_md = (ROOT / "experiments" / "trend_stress_test.md").read_text(encoding="utf-8")
# extract verdict + table
for line in stress_md.split("\n"):
    if line.startswith("**Verdict") or "|" in line[:1] or line.startswith("- ") or line.startswith("baseline") or line.startswith("mild") or line.startswith("pess") or line.startswith("extreme"):
        print(line)

# ============ 4. Rolling 30d ============
hdr("4. ROLLING 30-DAY HISTOGRAM")
roll_md = (ROOT / "experiments" / "rolling_30day_decision.md").read_text(encoding="utf-8")
print(roll_md.split("## Sample of failed windows")[0])
