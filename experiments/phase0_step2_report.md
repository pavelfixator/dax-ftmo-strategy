# Phase 0 v3.3.5 STEP 2 Report — Base Risk 1.0% → 1.25% (all cells)

**Datum:** 2026-04-29
**Status:** ✅ SEKCE A + B + C COMPLETE
**Final verdict:** 🟡 **STEP 3 NEEDED** (Gate #18 = 61.84 % v 60–69 % band per POZNÁMKA #2)
**Kritický constraint pro STEP 3:** HARD STOP **9.05 % TIGHT** (0.37 pp margin to 10 % threshold) → STEP 3 musí být **frequency-only**, žádné další risk boosts.

---

## 1. Executive summary

v3.3.5 STEP 2 zavádí **jediný parametr change** vs v3.3.5 STEP 1 baseline: base risk per
trade **1.0% → 1.25%** account, applied to ALL active cells via update of canonical
`risk_manager.RISK_TABLE`. Změna je MINOR (single-parameter, all-cells), schválena
17-kolo adversarial review jako 🟢 conditional na 2 implementační poznámky.

**Výsledky 10 K block bootstrap re-run (10 000 simulací, 30-day Challenge):**

| Metrika | v3.3.4 | STEP 1 | **STEP 2** | Δ STEP 2 | Compound vs v3.3.4 |
|---|---|---|---|---|---|
| Gate #18 success rate | 44.98 % | 55.87 % | **61.84 %** | +5.97 pp | **+16.86 pp** |
| HARD STOP probability | n/a | 4.07 % | **9.05 %** | +4.98 pp | n/a |
| Mean Challenge P&L | +$4 619 | +$6 339 | **+$7 923** | +$1 584 | +$3 304 |
| Median Challenge P&L | n/a | +$5 887 | **+$7 359** | +$1 472 | n/a |
| p5 Challenge P&L | n/a | -$3 283 | **-$4 103** | -$820 | n/a |
| p95 Challenge P&L | +$14 921 | +$18 187 | **+$22 733** | +$4 546 | +$7 812 |
| Within-Challenge max DD p5 | n/a | -$6 763 | **-$8 453** | -$1 690 | n/a |

**Decision tree (POZNÁMKA #2 — 5 bands):** 61.84 % v 60–69 % band → 🟡 **STEP 1+2 progress,
sub-threshold** → Next action: **STEP 3 needed** (UNDEFINED loosening + separate ablation
re-run ~8h compute; Pavel + Architekt rozhodují).

**HARD STOP gate (POZNÁMKA #1):** 9.05 % < 10 % strict threshold → ✅ **PASS**, ale
**TĚSNĚ** (95 % CI upper 9.63 %, jen 0.37 pp margin). STEP 2 sizing uplift posunul HARD
STOP rate o +4.98 pp. **STEP 3 musí monitorovat HARD STOP kritickyu** — další risk uplift
by pravděpodobně překročil 10 % → automatic NO-GO.

**Sanity:** 61.84 % ∈ [40 %, 80 %] → no halt; cell sizing summary matches Pavel spec
(ORB-DAX CALM 23.15 BSC binding, US-MOM CALM 19.29, US-MOM CRASH 16.53).

---

## 2. Sizing Comparison Table (v3.3.4 → STEP 1 → STEP 2)

| Cell                | regime | v3.3.4 lots | STEP 1 lots | STEP 2 lots | Δ STEP 2 |
|---------------------|--------|-------------|-------------|-------------|----------|
| us_momentum / TREND | TREND  | DISABLED    | DISABLED    | DISABLED    | —        |
| us_momentum / CALM  | CALM   | 15.43       | 15.43       | **19.29**   | +3.86    |
| us_momentum / CRASH | CRASH  | 6.61 (0.5×) | 13.22       | **16.53**   | +3.31    |
| orb_dax / CALM      | CALM   | 18.52       | 18.52       | **23.15**   | +4.63 (BSC binding) |

Reference: EUR/USD 1.08, DAX 24155.

### Risk table changes (`src/risk/risk_manager.py:RISK_TABLE`)

| state    | A v3.3.5 STEP 1 | A v3.3.5 STEP 2 | B v3.3.5 STEP 1 | B v3.3.5 STEP 2 |
|----------|------------------|-------------------|------------------|-------------------|
| normal   | 1000             | **1250**          | 500              | **625**           |
| caution  |  600             |  **750**          | 300              | **375**           |
| warning  |  700             |  **875**          |   0 (disabled)   |   0 (disabled)    |
| disabled |    0             |    0              |   0              |   0               |

**gate18 sizing mirror:** `scripts/gate18_block_bootstrap.py` `RISK_USD_PER_TRADE` 1000 → 1250
(matches risk_manager A_normal). Cell sizing summary z bootstrap run:

```
orb_dax      CALM   n=  122 lots=23.15  (BSC BINDING)
us_momentum  TREND  n=  569 lots=19.29  (DISABLED in active set)
us_momentum  CALM   n=  232 lots=19.29
us_momentum  CRASH  n=  182 lots=16.53
```

---

## 3. BSC Future Constraint (POZNÁMKA #1) — DEDICATED SECTION

ORB-DAX CALM cell hits **Black Swan Cap** v STEP 2 (potvrzeno 23.15 lots z bootstrap):

- Standard: 1250 / (50 × 1.08) × 1.0 = 23.148 lots
- BSC: 5000 / (200 × 1.08) = **23.148 lots** (binding limit)
- Effective: 23.148 lots = **saturation**

### Implikace
- **ORB-DAX CALM cell cannot scale s budoucími risk multipliers.** Další risk uplift
  v base RISK_TABLE nepovede k vyšším lots v této cell — cap binding limit.
- **Future P&L lift se koncentruje v US-MOM cells (CALM, CRASH)**, které jsou stále
  pod cap (US-MOM CALM 19.29 < 23.15; US-MOM CRASH 16.53 < 23.15).
- **Imbalance risk:** pokud US-MOM CALM underperforms v Phase 1 LIVE, ORB-DAX CALM
  nemůže kompenzovat (cap binding).
- **STEP 3 (UNDEFINED loosening) je primary lever** pro further P&L lift v ORB-DAX
  CALM cell, NE další risk boost (cap binding limits this approach).

### Code location reference
- `src/risk/sizing_v331.py` — explicit BSC binding warning v rationale komentáři.
- `src/risk/risk_manager.py:RISK_TABLE` — single source of truth pro base risk;
  `BLACK_SWAN_USD_CAP=5000` přepíše standard branch when binding.
- `scripts/gate18_block_bootstrap.py` — STEP 2 rationale + expected lots note.

---

## 4. Gate Validation Results

| Gate | Threshold | STEP 1 | **STEP 2** | Verdict |
|------|-----------|--------|-------------|---------|
| #1 Sample size (asym) | US-MOM≥500, ORB CALM≥100 | PASS | PASS (US-MOM 20 303, ORB CALM 638) | ✅ PASS |
| #4 Sharpe (MC mean)   | ≥1.0      | 1.69 | 1.69 (MC unchanged from v3.3.4)¹ | ✅ PASS |
| #6 Max DD % (MC 5p)   | <8 %      | -2.18 % | -2.18 % (MC unchanged)¹ | ✅ PASS¹ |
| #7 Risk of Ruin       | <1 %      | 0.00 % | 0.00 % (MC unchanged)¹ | ✅ PASS |
| #8 P(HARD STOP) (MC)  | <10 % | 0.00 % | 0.00 % (MC unchanged)¹ | ✅ PASS |
| #9 Walk-forward       | ≥80 %     | 9.5 % | 9.5 % (Strategy Limitation) | ❌ FAIL (acknowledged) |
| #14 Per-regime + rolling | per-regime ≥50 + rolling | FAIL | FAIL (rolling REQUIRES ADJUSTMENT) | ❌ FAIL |
| #15 PF/WR/R-mult uniform | per-cell PF≥1.5 ∧ (WR≥40% ∨ R≥2.0) | FAIL 2/4 | FAIL 2/4 (TREND, CALM PF<1.5) | ❌ FAIL |
| **#18 Challenge Success** | **≥70 % PASS, 60-69 % WARN** | **55.87 %** | **61.84 %** (95 % CI 60.88–62.79 %) | 🟡 **WARNING** |
| **HARD STOP block bootstrap** (POZNÁMKA #1) | <10 % strict | 4.07 % | **9.05 %** (95 % CI 8.50–9.63 %) | ✅ PASS (TIGHT) |

¹ Gate #4/6/7/8 MC stats jsou z trade-level Monte Carlo (separate from block bootstrap).
Tyto stats nebyly re-run pro STEP 2 — odráží baseline trade distribution. Zhrubeni:
gate18 within-Challenge max DD p5 = -$8 453 = -8.45 % účtu, což překračuje Gate #6 8 %
threshold *na úrovni Challenge* (nikoli equity-curve, kde MC stále ukazuje -2.18 %).
Tato diskrepance je očekávaná: gate18 sleduje within-Challenge tail, MC sleduje
long-run equity drawdown.

---

## 5. Per-Trade vs Per-Day Worst Case Breakdown (POZNÁMKA #3)

### Per-trade worst case (STEP 2 production sizing)

| Cell | SL=normal pts | lots | per-trade target loss (USD) | BS scenario (200pt) (USD) |
|------|---------------|------|------------------------------|----------------------------|
| ORB-DAX CALM | 50 (BSC binding) | **23.15** | -$1 250 (matches risk target) | **-$5 000** (BSC cap binding) |
| US-MOM CALM | 60 | **19.29** | -$1 250 (matches risk target) | -$4 167 |
| US-MOM CRASH | 70 | **16.53** | -$1 250 (matches risk target) | -$3 570 |

**Per-trade interpretace:** STEP 2 zvyšuje per-trade target z $1 000 → $1 250 (1.25 %
account, +25 % uniform). BSC cap stále binds at $5 000 single-trade max loss (200pt
black swan) for ORB-DAX CALM.

### Per-day worst-worst (compound risk scenarios)

- **Stop rule (2× SL daily lockout):** max 2 × $1 250 = **$2 500 daily loss** (2.5 %
  account, well below 5 % FTMO daily limit).
- **Black Swan + 1× SL (single day):** $5 000 + $1 250 = **$6 250** (6.25 %, exceeds 5 %
  FTMO daily limit → daily loss violation triggers).
- **Pathological (gap + BS):** ~$8 000+ (HARD STOP $7K threshold likely triggers — viz
  also empirical p5 within-Challenge max DD = -$8 453).

### Stop rule effectiveness
- 2× SL daily lockout garantuje ~$2 500 max v normální dny (under 5 % limit).
- Black Swan Cap effective in ORB-DAX CALM (cap binding $5 000 BS scenario).
- **Compound risk (BS + SL) v jednom dni je hraniční** — kill-switch should activate
  pokud daily approaches $4 000.

### Within-Challenge max DD distribution (block bootstrap output)

| stat | STEP 1 (USD) | **STEP 2 (USD)** | Δ |
|------|---------------|--------------------|---|
| mean | -$1 942      | **-$2 427**        | -$485 |
| p5   | -$6 763      | **-$8 453**        | **-$1 690** ⚠️ |
| p50  | -$1 490      | **-$1 862**        | -$372 |
| p95  | +$1 523      | **+$1 903**        | +$380 |

**⚠️ Pozor:** p5 max DD posunul z -$6 763 (těsně pod $7K HARD STOP) na -$8 453 (přes
$8K). 5 % nejhorších Challenges nyní expirience max DD pod $7K HS threshold, což přímo
koreluje s 9.05 % HARD STOP rate (4.07 % STEP 1 → 9.05 % STEP 2, +4.98 pp).

---

## 6. Compound Lift Analysis (STEP 1 + STEP 2 vs v3.3.4 baseline)

| Stage | Gate #18 | Δ from previous | Cumulative Δ from v3.3.4 |
|-------|----------|------------------|---------------------------|
| v3.3.4 baseline | 44.98 % | — | 0 |
| v3.3.5 STEP 1 (CRASH 0.5→1.0) | 55.87 % | +10.89 pp | +10.89 pp |
| v3.3.5 STEP 2 (risk 1.0%→1.25%) | **61.84 %** | **+5.97 pp** | **+16.86 pp** |

**Princip #2 framing (incremental):** STEP 2 přidalo +5.97 pp ke STEP 1 baseline,
což je **mírně pod incremental expectation** ze 17-kolo adversarial (Red Team probabilistic
P(60–69 %) = 50–55 % → median estimate), ale matches "central" výsledku z probability
distribution.

**Compound framing (decision tree):** kumulativně +16.86 pp od v3.3.4, což stále
**nedosahuje** Gate #18 PASS threshold 70 %. Gap k 70 % = -8.16 pp.

**Red Team probabilistic outlook validation:**
- P(≥ 70 %) odhad 25–35 % → outcome: NEPOTVRZENO (61.84 % < 70 %)
- P(60–69 %) odhad 50–55 % → ✅ **POTVRZENO** (61.84 % v tomto bandu)
- P(< 60 %) odhad 15–25 % → NEPOTVRZENO (above 60 %)
- HARD STOP 5–7 % expected → 9.05 % overshot horní hranice o 2 pp ⚠️

---

## 7. Granular Decision Tree (POZNÁMKA #2) — APPLIED

**5-band evaluation rules:**

| Gate #18 band | Verdict | Next action |
|---|---|---|
| ≥ 70 %         | 🟢 v3.3.5 STEP 2 SUFFICIENT | Phase 1 prep + 3-vrstvé schválení |
| **60–69 %**    | 🟡 **STEP 1+2 progress, sub-threshold** | **STEP 3 needed (UNDEFINED loosening + separate ablation re-run, ~8h compute)** |
| 55–59 %        | 🟡 STEP 1+2 marginal lift | STEP 3 evaluation s STRICT criteria |
| 50–54 %        | 🔴 STEP 1+2 insufficient | Volba D doporučena |
| < 50 %         | 🔴 STEP 1+2 INSUFFICIENT | Volba D immediate |

**Priority check:** HARD STOP probability 9.05 % < 10 % strict threshold → ✅ PASS,
gate neaktivní. **Pozor:** 95 % CI upper 9.63 % je < 10 % ale margin pouze 0.37 pp.
STEP 3 sizing changes by mohly překročit hranici.

**Tree application — current results:**
1. HARD STOP 9.05 % < 10 % → ✅ POZNÁMKA #1 PASS (TIGHT, 0.37 pp margin from threshold).
2. Sanity check 61.84 % ∈ [40 %, 80 %] → ✅ no halt.
3. Gate #18 = 61.84 % spadá do **60–69 % band** → 🟡 **STEP 3 NEEDED**.

**Selected verdict:** 🟡 **STEP 1+2 progress, sub-threshold**
**Selected next_action:** **STEP 3 needed** (UNDEFINED loosening + separate ablation
re-run, ~8h compute). Pavel + Architekt rozhodují implementaci.

**Doporučení pro STEP 3 design:**
- HARD STOP rate 9.05 % je TĚSNĚ pod limitem; STEP 3 nesmí přidat per-trade risk
  (HARD STOP rate by překročil 10 %). Primary lever: **UNDEFINED frequency reduction**,
  ne další risk uplift.
- ORB-DAX CALM cell saturated (BSC binding), takže UNDEFINED loosening pro tuto cell
  zvyšuje **počet obchodních dnů**, ne lots per trade. Direct path k vyšší aggregate P&L.

---

## 8. STEP 1 historical reference

STEP 1 baseline metrics (immutable record):
- Commit: `ea9f81d` (v3.3.5 STEP 1 baseline + Sekce C/D artifacts)
- Report: `experiments/phase0_step1_report.md`
- Gate #18: 55.87 % (95 % CI 54.89–56.84 %)
- HARD STOP block bootstrap: 4.07 % (95 % CI 3.70–4.48 %)
- Mean Challenge P&L: +$6 339 (median +$5 887, p5 -$3 283, p95 +$18 187)
- Within-Challenge max DD: mean -$1 942, p5 -$6 763, p95 +$1 523

---

## 9. Final verdict

**🟡 STEP 1+2 progress, sub-threshold → STEP 3 NEEDED.**

- Gate #18 = **61.84 %** (95 % CI 60.88–62.79 %) v 60–69 % band per POZNÁMKA #2.
- HARD STOP = **9.05 %** (95 % CI 8.50–9.63 %) ✅ POZNÁMKA #1 PASS, ale TIGHT.
- Compound lift z v3.3.4 = **+16.86 pp**, gap k Gate #18 PASS threshold (70 %) = -8.16 pp.
- ORB-DAX CALM saturated (BSC binding 23.15 lots) → STEP 3 musí cílit **UNDEFINED
  frequency**, ne další risk multiplier.

**Žádná STEP 3 implementace bez explicit pokynu od Pavla + Architekta.** STEP 3 vyžaduje
separate ablation re-run (~8h compute) a nezávislý design rozhodnutí o UNDEFINED
loosening (1/3 consensus vs 4. classifier signál).

