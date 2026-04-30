# v3.3.5 STEP 3 Ablation Report

**Status:** Sekce B output → STRICT GATE input (Sekce C, 6 criteria).

**Projected Gate #18:** 35.20% (incremental -26.64 pp)
**Projected HARD STOP:** 36.30%
**Hypothesis verdict (POZNÁMKA #2):** inconclusive

---

## 1. Regime distribution: 2/3 vs 1/3 consensus

| regime | 2/3 baseline | **1/3 STEP 3** | Δ pp |
|---|---:|---:|---:|
| TREND | 26.18% | **39.65%** | +13.47 |
| CALM | 7.38% | **18.32%** | +10.94 |
| CRASH | 3.08% | **3.08%** | +0.00 |
| UNDEFINED | 63.37% | **38.95%** | -24.41 |

**n days:** 2/3 baseline = 2888 ; 1/3 STEP 3 = 2888

## 2. Per-cell ablation (POZNÁMKA #1: trade count increase ≥50% required for non-CRASH)

| cell | trades 2/3 | trades 1/3 | increase % | PF 2/3 | PF 1/3 | WR 2/3 | WR 1/3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| orb_dax/CALM | 122 | 333 | +173.0% | 1.76 | 0.90 | 34.4% | 24.0% |
| us_momentum/CALM | 232 | 570 | +145.7% | 1.37 | 1.00 | 56.5% | 45.3% |
| us_momentum/CRASH | 182 | 182 | +0.0% | 2.16 | 2.16 | 52.7% | 52.7% |
| us_momentum/TREND | 569 | 832 | +46.2% | 1.16 | 0.84 | 45.5% | 40.7% |

## 3. Projected Gate #18 (block bootstrap MC, 1,000 sims)

- success_rate: **35.20%** (95% CI Wilson: 32.30% .. 38.21%)
- incremental lift vs STEP 2 (61.84%): **-26.64 pp**
- compound from v3.3.4 (44.98%): **-9.78 pp**

## 4. Projected HARD STOP probability

- HARD STOP probability: **36.30%** (95% CI Wilson: 33.38% .. 39.33%)
- vs STEP 2 (9.05%): +27.25 pp
- threshold strict <10%: FAIL

## 5. Hypothesis testing (POZNÁMKA #2)

See `experiments/step3_ablation/hypothesis_test.md` for detailed conditional analysis.
**Verdict:** inconclusive — Inconclusive: insufficient data in low/high-trade buckets

## 6. STRICT GATE evaluation table (6 criteria, Sekce C input)

| # | Criterion | Threshold | Result | Verdict |
|---|---|---|---|---|
| 1 | G#18 lift ≥+8pp | +8pp | -26.64 pp | ❌ FAIL |
| 2 | HARD STOP <10% | <10% | 36.30% | ❌ FAIL |
| 3 | Per-cell PF ≥1.4 | ≥1.4 | min=0.84 | ❌ FAIL |
| 4 | UNDEFINED 30-40% (±5) | 25-45% | 39.0% | ✅ PASS |
| 5 | Trade ↑≥50% (non-CRASH, non-DISABLED) | ≥50% | ORB +173%, US-MOM CALM +146% | ✅ PASS¹ |
| 6 | Hypothesis docs+verdict | clear | inconclusive | ✅ PASS |

¹ Criterion #5 per Pavel spec lists only ORB-DAX CALM, US-MOM CALM, US-MOM CRASH
(US-MOM TREND is DISABLED per STEP 2 active set). Script-level table above showed
min=+46.2% which corresponds to the DISABLED TREND cell — exempt. Excluding TREND,
both eligible non-CRASH cells exceed 50% threshold (ORB +173%, US-MOM CALM +146%).

**STRICT GATE aggregate:** 🔴 **STRICT_GATE_FAIL** — preempt Volba D, skip Sekce D

**Failed criteria:**
- #1 Gate #18 lift ≥+8 pp: actual **-26.64 pp** (massive regression vs STEP 2)
- #2 HARD STOP <10%: actual **36.30%** (3.6× over threshold)
- #3 Per-cell PF ≥1.4: orb_dax/CALM **0.90**, us_momentum/CALM **1.00** (both <1.4)

**Passed criteria:**
- #4 UNDEFINED 25-45% range: 39.0% ✅
- #5 Trade count increase ≥50% (eligible cells): +173%, +146% ✅
- #6 Hypothesis verdict documented: inconclusive (verdict clear) ✅

**Princip #9 EMPIRICALLY VALIDATED in opposite direction:**
1/3 consensus increased trade flow as expected (+173%, +146%), ale klasifikační noise
collapsed per-trade quality. PF degradation 27-49 % combined s vyšší exposure produced:
- HARD STOP rate ×4 (9.05% → 36.30%)
- Gate #18 ×0.57 (61.84% → 35.20%)

Frequency-only constraint per Princip #9 nestačil — frequency × quality má dependence
which 1/3 consensus narušil. STEP 3 approach REJECTED.
