# STEP 3 Prep — TODO list pro Architekta + Red Team

**Datum:** 2026-04-29
**Trigger:** Phase 0 v3.3.5 STEP 2 = 🟡 STEP 3 NEEDED (Gate #18 = 61.84 %, 60–69 % band)
**Status:** ⏸ documentation only — žádná implementace bez Pavlova/Architektova schválení

---

## 1. Empirické inputs pro STEP 3 design (post Sekce A+B)

| Metrika | v3.3.4 | STEP 1 | **STEP 2** | Δ Compound vs v3.3.4 |
|---|---|---|---|---|
| Gate #18 success rate | 44.98 % | 55.87 % | **61.84 %** | **+16.86 pp** |
| HARD STOP probability | n/a | 4.07 % | **9.05 %** ⚠️ TIGHT | n/a |
| Mean Challenge P&L | +$4 619 | +$6 339 | **+$7 923** | +$3 304 |
| Median Challenge P&L | n/a | +$5 887 | **+$7 359** | n/a |
| Within-Challenge max DD p5 | n/a | -$6 763 | **-$8 453** | n/a |

**Klíčový poznatek:** STEP 2 risk boost (+25 % per-trade) přinesl +5.97 pp Gate #18, ale
HARD STOP rate vyskočil z 4.07 → 9.05 % (×2.22 nárůst pro ×1.25 risk uplift). Tj.
**HARD STOP rate scaluje non-linearně s risk size**.

---

## 2. KRITICKÝ CONSTRAINT — HARD STOP TIGHT (POZNÁMKA #1 STEP 2)

**Empirická data:**
- HARD STOP STEP 1 (1.0 % risk): 4.07 %
- HARD STOP STEP 2 (1.25 % risk): 9.05 %
- 95 % CI upper bound STEP 2: **9.63 %**
- Threshold strict: **<10 %**
- Margin: **0.37 pp** (point) / **0.37 pp** (CI upper)

**Scaling pattern:** ×1.25 risk → ×2.22 HARD STOP rate (super-linear).

### Princip #5 (Numerical verification) projection pro STEP 3

Pokud STEP 3 zvýší risk per trade další +25 % (1.25 → 1.5625 %), naivní extrapolace:
- HARD STOP STEP 3 ≈ 9.05 × 2.22 = **20 %** (× další 2.22 scaling)
- Margin: -10 pp pod limitem → **automatic NO-GO**

I konzervativní lineární extrapolace (×2 namísto ×2.22):
- HARD STOP STEP 3 ≈ 9.05 × 2 = **18 %** → automatic NO-GO

### Závěr:
**ŽÁDNÉ DALŠÍ RISK BOOSTS v STEP 3.** Per-trade exposure musí zůstat na STEP 2 levels:
- ORB-DAX CALM: 23.15 lots (BSC saturated, fixed)
- US-MOM CALM: 19.29 lots (fixed)
- US-MOM CRASH: 16.53 lots (fixed)

---

## 3. STEP 3 Constraint Set

| Konstrant | Status | Důvod |
|---|---|---|
| Per-trade RISK_TABLE values | **MUST NOT CHANGE** | HARD STOP 9.05 % at 1.25 % risk; další boost → >10 % NO-GO |
| Regime risk multipliers | **MUST NOT CHANGE** | Same reason |
| Black Swan Cap (5K) | MUST NOT CHANGE | FTMO compliance fundamental |
| Margin Cap (30 %) | MUST NOT CHANGE | FTMO compliance fundamental |
| Active cell set (3 cells) | MAY CHANGE | Cell composition is design lever (e.g. drop weak) |
| **UNDEFINED frequency** | **PRIMARY LEVER** | Increase trade flow without per-trade risk boost |
| Filter sets (F1/F5) | MAY CHANGE | If reformulation reduces UNDEFINED noise |
| Classifier (4. signal) | MAY ADD | Reduces UNDEFINED via more decisive classification |

---

## 4. STEP 3 Hypotézy k posouzení Architektem

### H-A: UNDEFINED 2/3 → 1/3 consensus (PRIMARY)
- **Diagnóza:** 1 830 / 2 888 dnů = 63.4 % UNDEFINED → strategy je tichá většinu času.
- **Mechanismus:** Classifier vyžaduje 2/3 indicator agreement; loosen na 1/3 → více
  dnů kategorizovaných jako TREND/CALM/CRASH → více obchodních dnů.
- **Per-trade risk:** UNCHANGED (sizing formula respektuje 1.25 % risk targeting; lots
  jsou cell-specific, ne consensus-specific).
- **Predikce HARD STOP impact:** mírný nárůst (~+1 až +3 pp) — více dnů = více trade
  exposure, ale per-trade risk konstantní. **Must verify <10 %** v STEP 3 re-run.
- **Predikce Gate #18 impact:** +5 to +10 pp (nárůst trade flow přímo zvyšuje
  expected per-Challenge P&L).
- **Akceptační kritérium:** projection že nový UNDEFINED rate spadne na ≤ 30–40 %
  bez zhoršení per-cell PF.
- **Risk:** classification noise může degradovat per-cell PF (loosen consensus =
  méně reliable signál → nižší WR/PF na nové marginal trades).

### H-B: 4. classifier signál (ALTERNATIVE PRIMARY)
- **Diagnóza:** Same UNDEFINED problém; 3 indicators (TREND/CALM/CRASH) often inconclusive.
- **Mechanismus:** Add volume regime / intraday pattern → 4 indicators → 2/4 consensus
  rule → více decisive classifications.
- **Per-trade risk:** UNCHANGED.
- **Predikce HARD STOP impact:** podobný H-A (~+1 to +3 pp).
- **Predikce Gate #18 impact:** +5 to +12 pp (lepší classification → lepší per-cell
  selectivity → potenciálně vyšší WR/PF).
- **Risk:** komplexita designu; 4. signál vyžaduje validaci (sample size, OOS).

### H-C: Drop weak cells (DEFENSIVE alternative)
- **Diagnóza:** US-MOM CALM PF 0.96 (Gate #15 fail) drag na portfolio.
- **Mechanismus:** Drop US-MOM CALM → 2 active cells (ORB-DAX CALM + US-MOM CRASH).
- **Per-trade risk:** UNCHANGED.
- **Predikce HARD STOP impact:** **REDUCE** (méně trade flow → méně exposure → nižší HS).
- **Predikce Gate #18 impact:** **AMBIGUOUS** — méně trades znamená nižší aggregate P&L,
  ale lepší per-trade quality. Empirický test required.
- **Risk:** může zhoršit Gate #18 pokud US-MOM CALM aggregate contribution > drag.

### H-D: Combined H-A + H-C (UNDEFINED loosen + drop weak cell)
- **Mechanismus:** UNDEFINED 1/3 consensus + drop US-MOM CALM.
- **Per-trade risk:** UNCHANGED.
- **Predikce HARD STOP impact:** unclear (H-A increases, H-C decreases).
- **Predikce Gate #18 impact:** potenciálně highest aggregate lift — frequency boost
  s improved per-trade quality.
- **Risk:** complex interaction; vyžaduje rigorous separate ablation.

---

## 5. Architekt + Red Team brief — required deliverables

Před STEP 3 implementací, Architekt musí specifikovat:
1. **Selected hypothesis** (A / B / C / D nebo combination).
2. **Acceptance criteria pro STEP 3:**
   - Gate #18 ≥ +X pp incremental (per POZNÁMKA #2 56–59 % band would require ≥+15 pp;
     pro current 60–69 % band Pavel může nastavit lower threshold).
   - HARD STOP < 10 % strict (no exceptions).
   - Per-cell Gate #15 nezhorší pod aktuální 2/4 PASS (orb_dax CALM PASS, us_momentum
     CRASH PASS).
3. **Separate ablation re-run scope** (~8h compute) — what cells, what regimes, what
   filter combinations.
4. **Risk register** — co když H-A introduces classification noise zhorší PF?
   Fallback path?
5. **Phase 1 timeline contingency** (POZNÁMKA: pokud STEP 3 stále < 70 %, Volba D
   alternatives include FTMO 60–90 day program konzultace).

Red Team review musí specificky validovat:
1. **HARD STOP scaling assumption** — je naive ×2.22 extrapolation correct? Or does
   frequency increase scale differently than risk boost?
2. **Per-cell PF robustness** — UNDEFINED loosening může expose marginal trades
   s lower PF. Robust to this?
3. **Classifier accuracy degradation** — H-B 4. signál: introduces overfitting risk
   on 11-year backtest?
4. **Combined hypothesis interaction** (H-D) — možnost amplification efektu nebo
   confounding?

---

## 6. STEP 3 validation framework (post-implementation)

Po Architektově STEP 3 designu musí proběhnout (per spec — žádná implementace bez
schválení):

1. **Separate ablation re-run** (~8h compute) per Architekt scope.
2. **Re-run Gate #18 block bootstrap** s novou config (10K sims, 30-day blocks,
   HARD STOP < 10 % stále hard precondition).
3. **Re-validate Gate #15** uniform criterion na všechny aktivní cells.
4. **HARD STOP probability re-validation** s novými lots & frequency — kritické
   zejména pokud H-D (combined) shows non-trivial interactions.
5. **Per-day vs per-trade breakdown update** pro STEP 3 sizing (Pavel POZNÁMKA #3
   pattern).
6. **Confidence interval analysis** — pokud HARD STOP CI upper > 10 %, STEP 3 musí
   být revised even if point estimate < 10 %.

---

## 7. Decision matrix (post-STEP 3 outcome)

Per POZNÁMKA #2 5-band (kept from STEP 2):

| Gate #18 STEP 3 outcome | Verdict | Next step |
|---|---|---|
| ≥ 70 % | 🟢 PHASE 1 PROCEED | 3-vrstvé schválení (Architekt + Red Team + Pavel) |
| 65–69 % | 🟡 BORDERLINE | Pavel decides: marginal Phase 1 attempt vs Volba D |
| 60–64 % | 🟡 STEP 4 needed nebo Volba D | Architekt + Pavel rozhodují |
| 55–59 % | 🟡 STRICT criteria nepotvrzeny | Volba D doporučena |
| < 55 % | 🔴 STEP 3 INSUFFICIENT | Volba D immediate |

**HARD STOP override:** ≥ 10 % → automatic Volba D bez ohledu na Gate #18.

---

## 8. Rozhodovací bod (Pavel + Architekt + Red Team)

**Před STEP 3 implementací:**
1. Pavel rozhodne o STEP 3 hypothesis prioritization (A / B / C / D).
2. Architekt napíše STEP 3 spec (single-purpose change preferred per Princip #2).
3. Red Team review: validate HARD STOP scaling, classifier robustness.
4. Pavel schválí → impl → STEP 3 validation framework spustím.

**Žádná implementace bez explicit "Pokračuj sekce X" pokynu po STEP 3 spec finalization.**

---

## 9. Risk register pro STEP 3

| Risk | Pravděpodobnost | Mitigace |
|---|---|---|
| H-A 1/3 consensus zvýší classification noise → false signals | medium-high | Per-cell PF check pre/post; H-B fallback |
| HARD STOP exceeds 10 % v STEP 3 re-run | medium (TIGHT margin) | Strict cap; pokud >10 % → revise nebo Volba D |
| Per-cell Gate #15 degrades (extra trades dilute PF) | medium | Uniform criterion check; drop cell if needed (H-C) |
| Classifier overfitting (H-B 4. signál on 11y backtest) | medium | OOS validation strict; walk-forward windows |
| Combined hypothesis (H-D) interactions | unknown | Sequential validation: A → A+C → A+B+C |
| STEP 3 bridges < 70 % gap (final outcome 60-69 %) | medium-high | Pre-defined Volba D fallback; FTMO timeline konzultace (POZNÁMKA STEP 2 H-C) |

---

**Konec STEP 3 prep TODO. Vrácení Architektovi + Red Team pro design rozhodnutí.**

**Klíčový takeaway:** STEP 3 = frequency-only, ne risk-only. HARD STOP scaling
empirically demonstrated non-linear (×2.22 pro ×1.25 risk); STEP 3 musí cílit
trade flow expansion při zachování per-trade exposure.
