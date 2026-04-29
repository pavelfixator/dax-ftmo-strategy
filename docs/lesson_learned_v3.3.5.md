# Lesson Learned — v3.3.5 (post 18-rounds adversarial review)

**Datum:** 2026-04-29
**Trigger:** v3.3.4 → v3.3.5 sequential parameter step cycle (STEP 1 → STEP 2 → STEP 3
ablation):
- STEP 1: CRASH multiplier 0.5 → 1.0 (single-cell change) — Gate #18 = 55.87 %
- STEP 2: base risk 1.0 % → 1.25 % all cells (single-parameter all-cells) — Gate #18 = 61.84 %
- STEP 2 → STEP 3: HARD STOP rate scaled non-linearly (4.07 % → 9.05 % for 1.25× risk
  uplift = 2.22× HS multiplier, k ≈ 3.58 quadratic-like exponent)

This lesson extends v3.3.4 (adds Princip #9). Princips #1–#8 unchanged — see
`docs/lesson_learned_v3.3.4.md`.

---

## #9 — Non-Linear Effects Must Be Empirically Measured

**Trigger incident:** Architekt's initial STEP 3 design proposed an additional risk
multiplier uplift atop STEP 2. Linear extrapolation of HARD STOP scaling
(STEP 1 → STEP 2: +25 % risk → +1.25× HS rate naive) suggested STEP 3 +25 % risk would
land HARD STOP at ~11 %. **Architekt's Python verification revealed actual scaling is
quadratic-like (k ≈ 3.58)** — STEP 1 → STEP 2 was +25 % risk → **+222 %** HS rate
boost (4.07 % → 9.05 %, ×2.22). Linear projection underestimated by factor ~1.8.

A naive STEP 3 with +12.5 % additional risk would project HARD STOP at 11.45 % under
empirical scaling — **automatic NO-GO**. A +25 % boost would project 14.14 % — serious
compliance failure.

**Princip:**

> Risk parameter scaling není lineární. Each parameter increment requires explicit
> measurement before commitment to subsequent steps. Linear projections systematically
> underestimate scaling effects on tail-risk metrics (HARD STOP probability,
> within-Challenge max DD). Margin estimates based on linear assumptions are
> unreliable for compliance-critical thresholds.

### Aplikace

1. **Risk multipliers, position sizing, frequency parameters** — every increment
   measured, never extrapolated.
2. **Compound effects** — STEP 1 → STEP 2 → STEP 3 sequencing requires per-step
   empirical re-validation, not analytical compounding.
3. **Compliance thresholds** (HARD STOP <10 %, max DD <8 %, daily loss <5 %) musí
   mít sufficient margin k tolerování non-linear scaling. STEP 2 outcome HS = 9.05 %
   means margin to threshold is only 0.37 pp; STEP 3 must be **frequency-only**
   to avoid breaching the limit.
4. **Empirical scaling pattern itself is data-dependent** — k ≈ 3.58 was specific to
   v3.3.5 STEP 1 → STEP 2 transition. Future steps may have different scaling
   behavior; do not assume k is invariant.

### Vztah k Principu #5 (numerical verification) a #8 (magnitude testing)

Princip #9 is an extension of #5 + #8 with an explicit recognition that *the scaling
pattern itself is empirical, not theoretical*. Princip #5 asserts numerical
verification of single-state values; Princip #8 asserts measurement of magnitude per
step. Princip #9 adds: **the relationship between adjacent steps must also be
measured, not assumed linear.**

### Operational rule pro v3.3.5+ design

1. Pre-implementation, projection any compliance metric using **at least two scaling
   models**: linear AND empirical (k-power) extrapolation.
2. If projections diverge by > 50 % on threshold-relevant metric → STOP, run separate
   small-n MC simulation (1K sims) to empirically confirm before commitment to full
   ablation.
3. Document the empirical k-value once observed (v3.3.5 STEP 1→STEP 2 k ≈ 3.58 for
   HARD STOP rate vs risk multiplier).
4. Treat compliance thresholds as soft budgets when margin < 1 pp; design subsequent
   steps **as if** the threshold is at the 95 % CI upper bound (here HS upper CI
   9.63 % → effective threshold 10 % gives 0.37 pp budget, but treat any further
   risk increase as automatic NO-GO).

### Concrete consequence pro STEP 3 design

- **FREQUENCY-ONLY ABSOLUTE constraint:** STEP 3 cannot include any per-trade risk
  uplift. Only structural levers without per-trade exposure increase are permitted
  (UNDEFINED loosening, classifier signal restructure, cell composition).
- ORB-DAX CALM cell already saturates Black Swan Cap (23.15 lots) post-STEP 2 →
  further risk boost cannot scale this cell anyway.
- STEP 3 hypothesis testing (POZNÁMKA #2 v Sekce B) must explicitly test whether
  *frequency increase* (more trade days) preserves the non-linear scaling pattern,
  or whether it introduces a different scaling regime (dilution vs concentration
  hypothesis A/B).

---

## Implications for future projects

1. **Each parameter step is empirically distinct.** Sequential parameter tuning
   without per-step compliance re-validation is unsafe; non-linear effects compound.
2. **Volatility-based and tail-risk metrics tend to scale super-linearly.**
   HARD STOP probability is not the only such metric — within-Challenge max DD,
   p5 final P&L, drawdown duration likely follow similar k > 1 patterns.
3. **Linear projections must always have an empirical companion model**, especially
   for FTMO-style binary compliance gates where threshold breach = full failure.
4. **"Practical" parameter tuning has a quantifiable horizon** — once a compliance
   metric reaches < 1 pp margin, further parameter increments cannot be safely
   committed. After that point, structural redesign (Volba D) is the remaining
   path, not additional tuning rounds.

---

**Konec lesson_learned v3.3.5. Pokud STEP 3 ablation fails (Sekce C STRICT GATE FAIL),
Princip #9 will have been validated by the constraint binding outcome itself.**
