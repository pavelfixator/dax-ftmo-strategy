# F5_CALM=MACD OOS Validation — v3.3.4

**Verdict: MARGINAL**

Reason: ratio 62.62% in [50%, 70%)

## Setup
- Cell: us_momentum / CALM with F5_CALM=MACD active
- Train period: 2015-01-01 .. 2023-01-01 (exclusive)
- Test period:  2023-01-01 .. 2026-04-01

## Per-period metrics

| period | n_trades | WR | expectancy | total pts |
|---|---:|---:|---:|---:|
| train | 156 | 56.41% | +7.40 | +1155 |
| test  | 76  | 56.58%  | +4.64  | +352  |

## Decision tree (Pavel v3.3.4)
- test_exp ≥ 0.7 × train_exp → **PASS** (revert MACD)
- 0.5 ≤ ratio < 0.7         → **MARGINAL** (revert s WARNING)
- ratio < 0.5               → **FAIL** (drop US-MOM CALM cell)

Ratio computed: **0.6262**
