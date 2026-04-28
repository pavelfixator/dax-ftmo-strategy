# Gate #18 — Challenge Success Rate (Block Bootstrap)

**Verdict: FAIL**

## Inputs
- n_simulations: 10,000
- block_size (Challenge days): 30
- n_eligible_days (non-UNDEFINED): 1,058
- n_blocks available: 1,029
- profit target: $5,000

## Result
- Successes: 4,498
- success_rate: **44.98%**

## Final P&L distribution (USD)
| stat | value |
|---|---:|
| mean | $+4619 |
| median | $+4212 |
| p5 | $-3094 |
| p25 | $+443 |
| p75 | $+7892 |
| p95 | $+14921 |

## Acceptance (v3.3.4)
- ≥ 70 % → 🟢 Phase 1 PROCEED
- 60-70 % → 🟡 USER DECISION
- < 60 % → 🔴 NO-GO, return to v3.3.5 redesign

Histogram: `experiments/exp_gate18_histogram.html`
