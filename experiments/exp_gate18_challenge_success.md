# Gate #18 — Challenge Success Rate (Block Bootstrap)

**Success-rate verdict: FAIL**
**HARD STOP verdict (POZNAMKA #1): PASS**

## Inputs
- n_simulations: 10,000
- block_size (Challenge days): 30
- n_eligible_days (non-UNDEFINED): 1,058
- n_blocks available: 1,029
- profit target: $5,000
- HARD STOP threshold: $-7000

## Challenge Success
- Successes: 5,587 / 10,000
- success_rate: **55.87%**  (95% CI Wilson: 54.89% .. 56.84%)

## POZNAMKA #1 — HARD STOP probability (v3.3.5 STEP 1)
- HARD STOP triggers: 407 / 10,000
- **HARD STOP probability: 4.07%**  (95% CI Wilson: 3.70% .. 4.48%)
- Gate #8 threshold v3.3.5 STEP 1: <10%  → **PASS**

### Within-Challenge max DD distribution (USD)
| stat | value |
|---|---:|
| mean | $-1942 |
| p5   | $-6763 |
| p50  | $-1490 |
| p95  | $+1523 |

## Final P&L distribution (USD)
| stat | value |
|---|---:|
| mean | $+6339 |
| median | $+5887 |
| p5 | $-3283 |
| p25 | $+1766 |
| p75 | $+10523 |
| p95 | $+18187 |

## Acceptance
- success_rate ≥ 70 % → Phase 1 PROCEED
- 60-70 %               → USER DECISION
- < 60 %                → NO-GO
- HARD STOP probability < 10 % required (POZNAMKA #1, STEP 1 NO-GO if not met)

Histogram: `experiments/exp_gate18_histogram.html`
