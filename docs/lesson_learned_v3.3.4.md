# Lesson Learned — v3.3.4 (post 15-rounds adversarial review)

**Datum:** 2026-04-28
**Trigger:** v3.3.2.1 → v3.3.4 cycle exposed remaining methodology gaps:
- Gate #15 reformulation (PF/WR/R-mult uniform)
- Gate #18 NEW (Block Bootstrap challenge success — orthogonal to walk-forward)
- F5_CALM=MACD restoration (drop was empirically wrong)
- TREND stress test math correction (incremental delta)
- Force-trade rule removal (was ad-hoc)
- Gate #9 split-then-unsplit (moving goalposts admitted)

This lesson supersedes v3.3.2.1 (adds Princip #6 + #7).

---

## #1 — Sample minimum 100 trades for design decisions
**(unchanged from v3.3.2.1 — see docs/lesson_learned_v3.3.2.1.md)**

## #2 — No multi-candidate frameworks without prior evidence
**(refined v3.3.4):** Empirical correction — F5_CALM=MACD WAS contributing to
US-MOM CALM edge (drop produced -0.82 exp); we wrongly dropped it because the
4-candidate ablation didn't favor any specific candidate over the others, but
the BASELINE was *with* F5a active. The right call was "keep F5a, do not
expand framework", not "drop framework entirely".

**Rule update:** When a framework "fails" at the candidate-ranking level, ask
two separate questions:
  (a) Did any candidate beat the existing default? (If no → keep current.)
  (b) Did any candidate beat baseline-without-framework? (If no → drop.)
The two-question test prevents accidentally dropping the working default.

## #3 — Empirical primacy (data > intuition)
**(unchanged from v3.3.2.1)**

## #4 — Multiple comparisons hygiene (FDR / Bonferroni for N > 5)
**(unchanged from v3.3.2.1)**

## #5 — META: Numerical verification mandatory
**(unchanged from v3.3.2.1)**

## #6 — NEW v3.3.4 — Stress test math must be analytical, not re-simulated

**Context:** v3.3.2.1 trend stress test re-ran the full ablation cell with
patched buffer. Result: "wider stops *increase* expectancy" (counterintuitive).
That was an artifact: changing buffer shifted which trades hit SL vs TP, but
DID NOT properly charge the additional buffer cost across all trades. The
cell-evaluation infra is signal-discovery oriented; buffer change without
re-simulating slippage cost-per-trade is misleading.

**Empirical refutation of v3.3.2.1 stress result:** Pavel pessimistic ×2.0 was
+3.68 (KEEP). v3.3.4 analytical projection: +3.28 - 3.5 = **-0.22 (DROP)**.
Pavel acknowledged the analytical projection is correct and adopts DROP for
US-MOM TREND in v3.3.4.

**Rule:** Stress-testing cost parameters (spread, slippage, swap) must be
ANALYTICAL — direct subtraction of `delta_cost × n_trades` from baseline P&L
— NOT re-simulation of the strategy with patched parameter. Re-simulation
introduces selection-bias artifacts unrelated to the parameter being tested.

## #7 — NEW v3.3.4 — Distinct Validation Methods (avoid moving goalposts)

**Context:** v3.3.3 introduced a "Gate #9 split" (separate thresholds for
crash-rich vs crash-poor windows) to avoid the 9.5% walk-forward FAIL.
Red Team (kolo 14) flagged this as **moving goalposts** — adjusting the test
to fit the result.

**Empirical refutation:** When walk-forward fails, the right response is one of:
  (a) Acknowledge edge is regime-dependent → declare Strategy Limitation
  (b) Use a DIFFERENT validation method that captures the actual question
       (e.g. "can this strategy pass an FTMO Challenge?" → block bootstrap
       across full history, NOT chronological train/test split)
  (c) Redesign the strategy

What v3.3.3 did was move the threshold (a → 6/15 windows ≥0.7 ratio) — that's
**fitting the test to the data**, contrary to scientific method.

v3.3.4 reverts: walk-forward 80% kept as Strategy Limitation (option a),
NEW Gate #18 added (option b — block bootstrap which preserves regime
persistence + autocorrelation through 30-day blocks).

**Rule:** When a metric shows undesired result, do NOT relax the threshold.
Choose:
  - Acknowledge limitation explicitly (option a)
  - Add ORTHOGONAL test that addresses the underlying question (option b)
  - Redesign (option c)
NEVER reformulate the failing test until it passes.

**Application:** Gate #9 walk-forward kept uniform 80%, formally acknowledged
as Strategy Limitation in spec. Gate #18 NEW (Block Bootstrap Challenge
Success Rate) introduced as orthogonal validation — passing Gate #18 ≥70%
provides actionable Phase 1 confidence that walk-forward (which conflates
edge stability with regime distribution) does not.

---

## Process improvements applied to v3.3.4

1. Stress test analytical projection (Princip #6) replaces re-simulation.
2. Block bootstrap MC for Challenge Success Rate (Princip #7) replaces walk-forward as primary Phase 1 readiness metric.
3. Walk-forward kept but formally labeled as Strategy Limitation indicator.
4. Gate #15 reformulated with R-multiple compensation (PF or WR alone insufficient).
5. F5_CALM=MACD restored (Princip #2 refinement).
6. Force-trade rule removed (was ad-hoc, no spec justification).

## Gate #18 details (NEW)

- Block size: 30 trading days (= 1 FTMO Challenge length)
- Simulations: 10 000
- Block bootstrap preserves regime persistence (vs random sampling which destroys it)
- Acceptance: ≥70% PASS / 60-70% WARNING / <60% FAIL
- This is ORTHOGONAL to walk-forward: walk-forward asks "does edge generalize across time", Gate #18 asks "what fraction of random 30-day windows produce ≥+5% account growth"

The two questions are different. Gate #18 is the operative one for Phase 1
go/no-go decision.

---

## Implications for future projects

1. **Stress-test cost parameters analytically** — never re-simulate.
2. **When walk-forward shows regime-dependent edge, run block bootstrap** as orthogonal validation. Don't tweak walk-forward.
3. **When dropping a "framework", check if you're also dropping its working default** — the framework may have been bundled with a winner.
4. **FTMO-specific:** Challenge success rate (block bootstrap with 30-day blocks) is the operative Phase 1 readiness metric for prop firms. Walk-forward is a secondary/consistency indicator.
