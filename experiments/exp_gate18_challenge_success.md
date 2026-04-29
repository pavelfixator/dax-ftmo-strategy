# Gate #18 — Challenge Success Rate (Block Bootstrap)

**Success-rate verdict: WARNING**
**HARD STOP verdict (POZNAMKA #1): PASS**

## Inputs
- n_simulations: 10,000
- block_size (Challenge days): 30
- n_eligible_days (non-UNDEFINED): 1,058
- n_blocks available: 1,029
- profit target: $5,000
- HARD STOP threshold: $-7000

## Challenge Success
- Successes: 6,184 / 10,000
- success_rate: **61.84%**  (95% CI Wilson: 60.88% .. 62.79%)

## POZNAMKA #1 — HARD STOP probability (v3.3.5 STEP 1)
- HARD STOP triggers: 905 / 10,000
- **HARD STOP probability: 9.05%**  (95% CI Wilson: 8.50% .. 9.63%)
- Gate #8 threshold v3.3.5 STEP 1: <10%  → **PASS**

### Within-Challenge max DD distribution (USD)
| stat | value |
|---|---:|
| mean | $-2427 |
| p5   | $-8453 |
| p50  | $-1862 |
| p95  | $+1903 |

## Final P&L distribution (USD)
| stat | value |
|---|---:|
| mean | $+7923 |
| median | $+7359 |
| p5 | $-4103 |
| p25 | $+2208 |
| p75 | $+13153 |
| p95 | $+22733 |

## Acceptance
- success_rate ≥ 70 % → Phase 1 PROCEED
- 60-70 %               → USER DECISION
- < 60 %                → NO-GO
- HARD STOP probability < 10 % required (POZNAMKA #1, STEP 1 NO-GO if not met)

Histogram: `experiments/exp_gate18_histogram.html`
