# US-MOM TREND Stress Test — v3.3.4 CORRECT (analytical incremental delta)

**Verdict: DROP US-MOM TREND**

Reason: pessimistic projected exp -0.22 < 0.5 threshold

## Methodology v3.3.4

Replaces previous trend_stress_test.py (re-ran cell with patched buffer,
produced counterintuitive 'wider stops increase expectancy' result — that
was an artifact of which trades hit SL vs TP, NOT actual buffer cost charge).

CORRECT formula:
  delta_buffer = baseline_buffer × (multiplier - 1)
  projected_exp = baseline_exp - delta_buffer

Baseline buffer: 3.5 pts (spread 1.5 + slippage 2.0).
Baseline expectancy (US-MOM TREND from Phase 0 backtest): +3.28 pts.

## Per-scenario projection

| scenario | multiplier | Δ buffer | new buffer | projected exp |
|---|---:|---:|---:|---:|
| baseline | 1.0× | +0.00 | 3.50 | +3.28 |
| mild_x1.5 | 1.5× | +1.75 | 5.25 | +1.53 |
| pessimistic_x2.0 | 2.0× | +3.50 | 7.00 | -0.22 |
| extreme_x3.0 | 3.0× | +7.00 | 10.50 | -3.72 |

## Acceptance (v3.3.2.1+v3.3.4)
- pessimistic ×2.0 ≥ +0.5 pts → KEEP
- pessimistic ×2.0 < +0.5 pts → DROP US-MOM TREND

**Pessimistic projected expectancy: -0.22 pts**
**Verdict: DROP US-MOM TREND**
