# Phase 0 → Phase 1 Gate Criteria Validation (v3.3.4)

- Asymetric gate #1: US-MOM ≥500 / ORB-DAX CALM ≥100
- Gate #9 walk-forward: uniform 80% (Strategy Limitation v3.3.4)
- Gate #15 v3.3.4: PF ≥1.5 AND (WR ≥40% OR R-multiple ≥2.0)
- Gate #18 NEW: Challenge Success Rate ≥70% PASS / 60-70% WARNING / <60% FAIL

## Gate #1 sample size: **PASS**
- US-MOM trades 20303 / 500 → ✓
- ORB-DAX CALM trades 638 / 100 → ✓

## Gates #4/#6/#7/#8 (Monte Carlo)
- #4 Sharpe ≥1.0:    **PASS** (value 1.69)
- #6 Max DD ≤8.0%: **PASS** (value 2.18%)
- #7 Risk of Ruin <1.0%: **PASS** (value 0.00%)
- #8 P(HARD STOP) <10.0%: **PASS** (value 0.00%)

## Gate #9 walk-forward: **FAIL**
- 2/21 = 9.5% pass (need 80%)
- Strategy Limitation acknowledged v3.3.4: 6m windows produce unstable expectancy due to regime-dependent edge.

## Gate #14 per-regime + rolling: **FAIL**
- per-regime counts: {'CALM': 5091, 'CRASH': 1555, 'TREND': 16578}
- rolling 30d verdict: **REQUIRES ADJUSTMENT**

## Gate #15 uniform v3.3.4: **FAIL**
Per-cell:
- orb_dax/CALM: PF=1.76 WR=34.43% R-mult=3.35 → PASS (OK)
- us_momentum/TREND: PF=1.16 WR=45.52% R-mult=1.38 → FAIL (PF<1.5)
- us_momentum/CALM: PF=0.96 WR=49.23% R-mult=0.99 → FAIL (PF<1.5)
- us_momentum/CRASH: PF=2.16 WR=52.75% R-mult=1.93 → PASS (OK)

## Gate #18 Challenge Success Rate (v3.3.4 NEW): **FAIL**
- success rate: 55.9% (threshold ≥70% PASS, ≥60% WARNING)

## Gates pending separate computations
- #2 WR aggregate / #3 PF aggregate / #5 Sortino / #11 close framework / #12 swap coverage / #13 BSC audit / #16 ablation positive / #17 classifier accuracy