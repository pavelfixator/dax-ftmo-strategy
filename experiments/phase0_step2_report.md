# Phase 0 v3.3.5 STEP 2 Report — Base Risk 1.0% → 1.25% (all cells)

**Datum:** 2026-04-29
**Status:** 🟡 IMPLEMENTATION DONE (Sekce A) — re-run pending (Sekce B)
**Final verdict:** TODO (filled post Sekce B Gate #18 re-run)

---

## 1. Executive summary

v3.3.5 STEP 2 zavádí **jediný parametr change** vs v3.3.5 STEP 1 baseline: base risk per
trade **1.0% → 1.25%** account, applied to ALL active cells via update of canonical
`risk_manager.RISK_TABLE`. Změna je MINOR (single-parameter, all-cells), schválena
17-kolo adversarial review jako 🟢 conditional na 2 implementační poznámky.

**Cíl:** kompoundovat STEP 1 zlepšení (+10.89 pp) o additional risk uplift
směrem ke Gate #18 ≥ 70 % PASS threshold. Per Red Team estimate: STEP 1 + STEP 2
compound projection 65–71 % range (±tail uncertainty).

**Výsledek:** TODO_VERDICT (Gate #18 = TODO_G18 % po Sekce B re-run)

---

## 2. Sizing Comparison Table (v3.3.4 → STEP 1 → STEP 2)

| Cell                | regime | v3.3.4 lots | STEP 1 lots | STEP 2 lots | Δ STEP 2 |
|---------------------|--------|-------------|-------------|-------------|----------|
| us_momentum / TREND | TREND  | DISABLED    | DISABLED    | DISABLED    | —        |
| us_momentum / CALM  | CALM   | 15.43       | 15.43       | **19.29**   | +3.86    |
| us_momentum / CRASH | CRASH  | 6.61 (0.5×) | 13.22       | **16.53**   | +3.31    |
| orb_dax / CALM      | CALM   | 18.52       | 18.52       | **23.15**   | +4.63 (BSC binding) |

Reference: EUR/USD 1.08, DAX 24155.
Risk table change: A_normal 1000 → 1250 (Δ +250); proporcionální napříč všemi non-disabled entries.

### Risk table changes (`src/risk/risk_manager.py:RISK_TABLE`)

| state    | A v3.3.5 STEP 1 | A v3.3.5 STEP 2 | B v3.3.5 STEP 1 | B v3.3.5 STEP 2 |
|----------|------------------|-------------------|------------------|-------------------|
| normal   | 1000             | **1250**          | 500              | **625**           |
| caution  |  600             |  **750**          | 300              | **375**           |
| warning  |  700             |  **875**          |   0 (disabled)   |   0 (disabled)    |
| disabled |    0             |    0              |   0              |   0               |

---

## 3. BSC Future Constraint (POZNÁMKA #1) — DEDICATED SECTION

ORB-DAX CALM cell hits **Black Swan Cap** v STEP 2:
- Standard: 1250 / (38.5 × 1.08) × 0.7 = 21.07 lots
- BSC: 5000 / (200 × 1.08) = **23.15 lots** (binding)
- Effective: 23.15 lots = saturation

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
- `src/risk/sizing_v331.py` — explicit BSC binding warning v rationale komentáři
  (post v3.3.5 STEP 1 block).
- `src/risk/risk_manager.py:RISK_TABLE` — single source of truth pro base risk
  hodnoty; BSC cap (`BLACK_SWAN_USD_CAP=5000`) přepíše standard branch when binding.

---

## 4. Gate Validation Results — TODO post Sekce B

| Gate | Threshold | STEP 1 result | STEP 2 result | Verdict |
|------|-----------|---------------|----------------|---------|
| #6 Max DD %  | <8 %      | -2.18 %       | TODO_G6 %      | TODO_G6_V |
| #8 P(HARD STOP, MC) | <10 % | 0.00 %     | TODO_HS_MC %   | TODO_HS_MC_V |
| #15 PF/WR/R-mult uniform | per-cell | FAIL 2/4 | TODO_G15  | TODO_G15_V |
| **#18 Challenge Success** | **≥70 % PASS** | **55.87 %** | **TODO_G18 %** | **TODO_G18_V** |
| **HARD STOP block bootstrap** (POZNÁMKA #1) | <10 % | 4.07 % | TODO_HS_BB % | TODO_HS_BB_V |

(Filled post `gate18_block_bootstrap.py` + `validate_gate_criteria.py` re-run v Sekce B.)

---

## 5. Per-Trade vs Per-Day Worst Case Breakdown (continued from STEP 1 POZNÁMKA #3)

### Per-trade worst case (STEP 2 sizing)

| Cell | SL=normal | lots | per-trade target loss (USD) | BS scenario (200pt) (USD) |
|------|-----------|------|------------------------------|----------------------------|
| ORB-DAX CALM | 38.5 (BSC binding) | 23.15 | -$963 (target $1250 capped by BSC) | **-$5 000** (BSC cap binding) |
| US-MOM CALM | 70 | 19.29 | -$1 458 | -$4 167 |
| US-MOM CRASH | 70 | 16.53 | -$1 250 (= $1 250 risk target) | -$3 570 |

**Per-trade interpretace:** STEP 2 zvyšuje per-trade target z $1 000 → $1 250 (1.25 %
account). BSC cap stále binds at $5 000 single-trade max loss (200pt black swan).
Per-trade risk se zvýšil o 25 % uniform.

### Per-day worst-worst (compound risk scenarios)

- **Stop rule (2× SL daily lockout):** max 2 × $1 458 = **$2 916 daily loss** (2.92 %
  account, well below 5 % FTMO daily limit).
- **Black Swan + 1× SL (single day):** $5 000 + $1 458 = **$6 458** (6.46 %, exceeds 5 %
  FTMO daily limit → daily loss violation triggers).
- **Pathological (gap + BS):** ~$8K+ (HARD STOP $7K threshold likely triggers).

### Stop rule effectiveness
- 2× SL daily lockout garantuje ~$2 916 max v normální dny (under 5 % limit).
- Black Swan Cap effective in ORB-DAX CALM (cap binding $5 000 BS scenario).
- **Compound risk (BS + SL) v jednom dni je hraniční** — monitor v live; pokud daily
  loss approaches $4 000, kill-switch should activate.

### Within-Challenge max DD distribution — TODO post Sekce B

| stat | STEP 1 (USD) | STEP 2 (USD) | Δ |
|------|--------------|---------------|---|
| mean | -$1 942      | TODO          | TODO |
| p5   | -$6 763      | TODO          | TODO |
| p50  | -$1 490      | TODO          | TODO |
| p95  | +$1 523      | TODO          | TODO |

---

## 6. Compound Lift Analysis (STEP 1 + STEP 2 vs v3.3.4 baseline)

| Stage | Gate #18 | Δ from previous | Cumulative Δ from v3.3.4 |
|-------|----------|------------------|---------------------------|
| v3.3.4 baseline | 44.98 % | — | 0 |
| v3.3.5 STEP 1 (CRASH 0.5→1.0) | 55.87 % | +10.89 pp | +10.89 pp |
| v3.3.5 STEP 2 (risk 1.0%→1.25%) | TODO_G18 % | TODO_Δ_S2 | TODO_COMPOUND |

**Red Team probabilistic outlook (pre-run):**
- P(≥ 70 %): 25–35 % (PASS scenario)
- P(60–69 %): 50–55 % (STEP 3 needed scenario)
- P(< 60 %): 15–25 % (Volba D scenario)
- Most likely: 60–69 % band → STEP 3 needed
- HARD STOP expected: 5–7 % (must verify <10 %)

---

## 7. Granular Decision Tree (POZNÁMKA #2) — TODO application post Sekce B

**5-band evaluation rules:**

| Gate #18 band | Verdict | Next action |
|---|---|---|
| ≥ 70 %         | 🟢 v3.3.5 STEP 2 SUFFICIENT | Phase 1 prep + 3-vrstvé schválení (Architekt + Red Team + Pavel) |
| 60–69 %        | 🟡 STEP 1+2 progress, sub-threshold | STEP 3 needed (UNDEFINED loosening + separate ablation re-run, ~8h compute) |
| **55–59 %**    | 🟡 STEP 1+2 marginal lift | STEP 3 evaluation s STRICT criteria (ablation must show ≥+15pp incremental); pokud projected < +15 pp → Volba D |
| 50–54 %        | 🔴 STEP 1+2 insufficient | Volba D doporučena (parameter tuning has limits — fundamental redesign) |
| < 50 %         | 🔴 STEP 1+2 INSUFFICIENT (regression?) | Volba D immediate |

**Priority check:** pokud HARD STOP probability ≥ 10 % → 🔴 STEP 2 FAIL (compliance
risk), Volba D doporučena, NO further evaluation.

**Selected verdict:** TODO post Sekce B
**Selected next_action:** TODO post Sekce B

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

**Konec template. Sekce B re-run vyplní TODO sekce + finalizuje verdikt.**
