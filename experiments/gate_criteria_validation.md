# Phase 0 → Phase 1 Gate Criteria Validation (v3.3.2.1)

Stub validation. Full Sekce 6 Cast B backtest will populate gates 2-13.

## Gate #1 — Sample size (asymmetric v3.3.2.1)

- **Verdict:** **PASS**
- US-MOM trades: 20303 / 500 → ✓
- ORB-DAX CALM trades: 638 / 100 → ✓

## Gate #14 — Per-regime + Rolling 30d (extended v3.3.2.1)

- **Verdict:** **FAIL**
- Per-regime ≥50 trades: ✓
- Per-regime counts: {'CALM': 5091, 'CRASH': 1555, 'TREND': 16578}
- Per-regime fails: []
- Rolling 30-day verdict: **REQUIRES ADJUSTMENT**

## Gates #2-#13 + #15-#17

Pending Sekce 6 Cast B (full Phase 0 backtest with Monte Carlo, walk-forward,
what-if, regime classifier accuracy 6 known events).
