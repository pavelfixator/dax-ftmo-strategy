# Gate #18 — Challenge Success Rate (Block Bootstrap)

**Verdict: FAIL**

## Inputs
- n_simulations: 10,000
- block_size (Challenge days): 30
- n_eligible_days (non-UNDEFINED): 1,058
- n_blocks available: 1,029
- profit target: $5,000

## Result
- Successes: 0
- success_rate: **0.00%**

## Final P&L distribution (USD)
| stat | value |
|---|---:|
| mean | $+436 |
| median | $+401 |
| p5 | $-246 |
| p25 | $+126 |
| p75 | $+719 |
| p95 | $+1239 |

## Acceptance (v3.3.4)
- ≥ 70 % → 🟢 Phase 1 PROCEED
- 60-70 % → 🟡 USER DECISION
- < 60 % → 🔴 NO-GO, return to v3.3.5 redesign

Histogram: `experiments/exp_gate18_histogram.html`
