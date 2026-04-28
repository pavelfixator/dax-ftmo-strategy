# Rolling 30-day Validation — v3.3.2.1 Gate #14 Extension

**Verdict:** **REQUIRES ADJUSTMENT**

- Windows evaluated: 2888
- Threshold: ≥7 non-UNDEFINED days per 30-day window
- Fail count: 1346 (46.61%)
- Median eligible days: 7.0
- P25 / P75: 3.0 / 12.0
- Min / Max: 0 / 22

## Decision tree (Pavel spec)
- < 5% fail   → PASS
- 5-15% fail  → WARNING
- > 15% fail  → REQUIRES ADJUSTMENT

## Sample of failed windows

| window_start | eligible_days |
|---|---:|
| 2015-01-02 | 0 |
| 2015-01-05 | 0 |
| 2015-01-06 | 0 |
| 2015-01-07 | 0 |
| 2015-01-08 | 0 |
| 2015-01-09 | 0 |
| 2015-01-12 | 0 |
| 2015-01-13 | 0 |
| 2015-01-14 | 0 |
| 2015-01-15 | 0 |
| 2015-01-16 | 0 |
| 2015-01-19 | 0 |
| 2015-01-20 | 0 |
| 2015-01-21 | 0 |
| 2015-01-22 | 0 |
| 2015-01-23 | 0 |
| 2015-01-26 | 0 |
| 2015-01-27 | 0 |
| 2015-01-28 | 0 |
| 2015-01-29 | 0 |
