# Phase 0 v3.3.5 STEP 3 — FINAL VERDICT (CASE A: STRICT GATE PREEMPTED)

**Datum:** 2026-04-30
**Status:** ✅ Sekce A + B + E complete (Sekce C/D **PREEMPTED** per STRICT_GATE_FAIL)
**Final verdict:** 🔴 **VOLBA D PREEMPTED** — parameter tuning empiricky exhausted

---

## 1. Executive summary

v3.3.5 STEP 3 ablation testbed (Sekce B) prokázal **definitivně**, že frequency-only
lever (1/3 consensus) **nestačí** pro Phase 1 readiness. STRICT GATE 6-criteria
evaluation FAILED 3/6, automatic Volba D preempt per spec resource conservation rule
(saves ~3h Sekce D combined re-run compute).

**Compound parameter tuning trajectory:**

| Stage | Gate #18 | HARD STOP | Δ (incremental) | Δ (compound vs v3.3.4) |
|-------|----------|-----------|------------------|--------------------------|
| v3.3.4 baseline | 44.98 % | n/a | — | 0 |
| v3.3.5 STEP 1 (CRASH 0.5→1.0) | 55.87 % | 4.07 % | +10.89 pp | +10.89 pp |
| v3.3.5 STEP 2 (risk 1%→1.25%) | 61.84 % | 9.05 % TIGHT | +5.97 pp | +16.86 pp |
| v3.3.5 STEP 3 (1/3 consensus, projected) | **35.20 %** | **36.30 %** | **-26.64 pp REGRESSION** | -9.78 pp |

**Three sequential parameter levers tested empirically. Last lever made things WORSE.**

---

## 2. STRICT GATE 6-criteria evaluation (Sekce B output)

| # | Criterion | Threshold | Result | Verdict |
|---|---|---|---|---|
| 1 | Gate #18 lift ≥ +8 pp incremental | +8 pp | **-26.64 pp** | ❌ **FAIL** |
| 2 | Projected HARD STOP < 10 % | <10 % | **36.30 %** | ❌ **FAIL** (3.6× over) |
| 3 | Per-cell PF ≥ 1.4 | ≥1.4 | orb_dax/CALM **0.90**, us_mom/CALM **1.00** | ❌ **FAIL** |
| 4 | UNDEFINED 30-40 % (±5 pp) | 25-45 % | 39.0 % | ✅ PASS |
| 5 | Trade ↑ ≥50 % (eligible non-CRASH) | ≥50 % | +173 %, +146 % | ✅ PASS |
| 6 | Hypothesis testing docs+verdict | clear | inconclusive (verdict clear) | ✅ PASS |

**Aggregate: 🔴 STRICT_GATE_FAIL** (3 FAIL / 3 PASS) → preempt Volba D, skip Sekce D.

---

## 3. Critical empirical insight — Princip #9 validated in opposite direction

**Co fungovalo:**
- Frequency lever WORKED mechanically — UNDEFINED dropped from 63.4 % → 39.0 % (-24.4 pp)
- Trade counts increased dramatically:
  - ORB-DAX CALM: 122 → 333 (+173 %)
  - US-MOM CALM: 232 → 570 (+146 %)
  - US-MOM CRASH: unchanged (instant rule preserved)

**Co se zhroutilo:**
- Per-cell PF degraded sharply due to classification noise:
  - ORB-DAX CALM: 1.76 → **0.90** (-49 %, WR 34.4 → 24.0 %)
  - US-MOM CALM: 1.37 → **1.00** (-27 %, WR 56.5 → 45.3 %)
  - US-MOM TREND (DISABLED): 1.16 → 0.84 (parity check)

**Compound effect:**
- HARD STOP rate: 9.05 % → **36.30 %** (×4 increase)
- Gate #18 success: 61.84 % → **35.20 %** (×0.57)
- Mean P&L expected lower (full distribution v `experiments/step3_ablation/projection.json`)

**Princip #9 lesson extension:**
> Frequency × per-trade quality není jednoduchý násobek. Když 1/3 consensus zvýší
> trade frequency tím, že pustí marginal-quality trades v ambiguous regime days,
> per-trade edge collapsed (PF -27 až -49 %). HARD STOP rate scaling closely tracks
> the *product* of frequency and tail-risk per trade, ne pouze risk size sám o sobě.

Princip #9 byl formulován v STEP 2 → STEP 3 transition, kde HARD STOP scaled
non-linearly s risk size (k≈3.58). STEP 3 ablation rozšiřuje insight: **frequency-only
lever bez quality preservation produkuje ještě horší scaling pattern** (HS ×4 pro
+159 % aggregate trade volume increase, kde quality dropped).

---

## 4. Parameter tuning status — POZNÁMKA #3 update (LITERAL, ne practical)

Per STEP 2 prep TODO POZNÁMKA #3 framing: "parameter tuning exhausted" byl PRACTICAL,
ne LITERAL. Po STEP 3 ablation update **je nyní LITERAL**:

**Three parameter levers tested empirically across v3.3.5 cycle:**
1. **CRASH multiplier** (0.5 → 1.0, single-cell) → STEP 1 +10.89 pp ✓
2. **Base risk** (1.0 % → 1.25 %, all-cells) → STEP 2 +5.97 pp ✓ (HARD STOP tight)
3. **Regime consensus frequency** (2/3 → 1/3, structural) → STEP 3 **-26.64 pp ✗ regression**

**Theoretical levers stále existují s structural cost (per POZNÁMKA #3):**
- Filter restructure (drop/add filters per cell): NEW ablation cycle ~12h compute,
  edge degradation risk (frameworks already optimized v Sekce 5/6 v3.3.2.1+)
- Per-cell threshold relaxation: 17-kolo adversarial review explicit nedoporučil
- Alternative SL/TP logic: structural change, identity drift
- Setup count expansion (back to VWAP-Bounce or new setup): full new design cycle

Každý theoretical lever ≥ 8h compute + cyklus adversarial review + risk že další
parameter degraduje (precedens: STEP 3). **Strategy v3.3.5 dosáhla parameter tuning
ceiling.**

---

## 5. VOLBA D recommendations — Pavel decides

Per spec CASE A template, 4 alternative paths pro fundamental redesign:

### a) Multi-instrument diversification — 4-6 týdnů scope
- Add US100, US30, EUR/USD jako nezávislé strategy instances
- Each instrument backtested separately, position sizing per FTMO 100K
- Diversifies away CRASH-dependence (89 dnů z 2 888 = 3.1 %) napříč instrument-specific
  CRASH events
- **Risk:** každý instrument vyžaduje vlastní filter set, regime calibration, ablation cycle

### b) Non-CRASH edge re-design (alternative setups) — 6-8 týdnů scope
- Drop CRASH-dependent setups, build alternative edge that's not regime-bound
- Examples: mean-reversion in defined ranges, calendar-effect strategies, news-event
  fades
- **Risk:** strategy identity drift; current backtest infrastructure built around
  regime classifier — major refactor

### c) Alternative timeframes (15m, 30m setups) — 3-4 týdny scope
- Re-derive ORB / momentum logic na vyšších timeframes
- Less noise, fewer trades, but per-trade higher quality
- Compatible with current FTMO compliance framework
- **Risk:** smaller sample sizes per cell (Princip #1 minimum 100 trades), Phase 1
  Challenge timeline (30 days) může mít insufficient trade count

### d) Accept strategy not viable for FTMO 100K Challenge horizon
- Acknowledge structural CRASH-dependence + 30-day Challenge variance
- Either pivot k different prop firm program (60-90 day Challenge?) nebo
  abandon prop-firm path
- **Risk:** sunk cost; ale 18-kolo adversarial review je explicit data point pro
  evidence-based decision

---

## 6. Compute resource summary

| Phase | Compute | Outcome |
|-------|---------|---------|
| v3.3.4 Phase 0 | ~6h backtest + ~10h ablation Sekce 5 | NO-GO baseline 44.98 % |
| v3.3.5 STEP 1 | ~1.5h gate18 re-run | 55.87 % |
| v3.3.5 STEP 2 | ~1.5h gate18 re-run | 61.84 % |
| v3.3.5 STEP 3 ablation | ~5.7h ablation testbed | STRICT_GATE_FAIL |
| v3.3.5 STEP 3 combined re-run | **~3h SAVED** (preempted) | n/a |
| **Total v3.3.5 cycle** | **~8.7h** | Parameter tuning empirically exhausted |

Resource conservation rule per spec: STRICT GATE FAIL → skip Sekce D. **Saved 3h
compute and prevented committing 1/3 consensus to production codebase** (would have
required revert).

---

## 7. Validated principles

Adversarial review process produced 9 principles, all validated by v3.3.5 cycle:

1. **#1 Sample minimum 100 trades** — STEP 3 PF degradation visible at n=333, 570
2. **#2 Multi-candidate evidence** — F5_CALM=MACD restoration, 3 sequential STEP 1/2/3
3. **#3 Empirical primacy** — STEP 3 projection contradicted optimistic expectations
4. **#4 Multiple comparisons hygiene** — FDR/Bonferroni in extended ablation
5. **#5 Numerical verification** — Architekt's Python catched HARD STOP scaling bug
   pre-STEP 3 risk-boost design
6. **#6 Per-cell FDR validation** — Sekce 5 11-year FDR + Bonferroni
7. **#7 Distinct validation methods** — Gate #18 block bootstrap orthogonal to walk-forward
8. **#8 Magnitude testing** — incremental measurement per step
9. **#9 Non-linear effects empirical measurement** — STEP 2 → STEP 3 quadratic-like
   HARD STOP scaling (k≈3.58); STEP 3 extension: frequency × quality coupling

**Principles are now production-ready output of v3.3.5 cycle. Future strategy designs
inherit these principles directly.**

---

**🔴 Final verdict: VOLBA D PREEMPTED. Pavel rozhoduje fundamental redesign approach.**

**ČEKÁM na Pavlovo rozhodnutí.** Žádná Volba D implementace bez explicit Pavel +
Architekt rozhodnutí (per NE-AUTORIZOVANÉ section spec).
