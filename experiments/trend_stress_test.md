# US-MOM TREND Stress Test — v3.3.2.1

**Verdict:** **KEEP with WARNING**

## Acceptance thresholds (v3.3.2.1)
- Baseline    ≥ 3.3 pts → KEEP unchanged
- Mild ×1.5   ≥ 1.5 pts → KEEP
- Pessimistic ×2.0 ≥ 0.5 pts → KEEP with WARNING (UPDATED from ≥0 in v3.3.2)
- Pessimistic < 0.5 pts → DROP US-MOM TREND

## Per-scenario results

| scenario | multiplier | buffer_pts | n_trades | WR | expectancy | sharpe | max_dd |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1.0 | 3.50 | 569 | 0.46 | +3.28 | 0.79 | -2196 |
| mild_x1.5 | 1.5 | 5.25 | 569 | 0.46 | +3.60 | 0.86 | -2129 |
| pessimistic_x2.0 | 2.0 | 7.00 | 569 | 0.47 | +3.68 | 0.87 | -2247 |
| extreme_x3.0 | 3.0 | 10.50 | 569 | 0.47 | +3.59 | 0.83 | -2552 |

## Verdict detail
- baseline expectancy: +3.28 (threshold 3.3)
- mild expectancy:     +3.60 (threshold 1.5)
- pessimistic exp:     +3.68 (threshold 0.5 v3.3.2.1)
