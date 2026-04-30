# POZNÁMKA #2 — HARD STOP Hypothesis Testing

Two competing hypotheses tested via conditional HARD STOP rate analysis on
projected block bootstrap (n=1,000 30-day Challenges).

## Conditional HARD STOP rates

| Subset | n Challenges | HARD STOP rate |
|---|---:|---:|
| Low-trade Challenges (<5 active days) | 0 | nan% |
| High-trade Challenges (≥10 active days) | 1,000 | 36.30% |
| With CRASH-event proxy (any day < -$3,500) | 20 | 15.00% |
| Without CRASH proxy | 980 | 36.73% |

## Verdict

**Verdict:** inconclusive

Inconclusive: insufficient data in low/high-trade buckets

### Interpretation

- Hypothesis A (dilution): more trades distribute losses → lower HARD STOP rate
- Hypothesis B (concentration): more days = more chances for bad streaks
  → higher HARD STOP rate (super-linear cumulative tail risk)
- Inconclusive: |rate_high − rate_low| < 1 pp; signal too weak to attribute
