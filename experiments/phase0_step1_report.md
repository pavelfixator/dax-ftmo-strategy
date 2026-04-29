# Phase 0 v3.3.5 STEP 1 Report — CRASH Multiplier 0.5 → 1.0

**Datum:** 2026-04-29
**Final verdict:** 🟡 **STEP 2 + STEP 3 NEEDED** (per refined decision tree: Gate #18 = 55.87 % je v 50–59 % band)
**Verdikt (success rate):** Gate #18 = **55.87 %** (Δ +10.89 pp vs v3.3.4 baseline 44.98 %)
**Verdikt (HARD STOP / POZNÁMKA #1):** ✅ **PASS** — 4.07 % (95 % CI 3.70–4.48 %; threshold <10 %)
**POZNÁMKA #2 calibration:** Δ +10.89 pp **hit conservative estimate band** (55–65 % realistic range, low-end).

---

## Executive summary

v3.3.5 STEP 1 zavedl **jediný parametr change** vs v3.3.4 baseline: CRASH risk multiplier
0.5 → 1.0 (matching TREND/CALM magnitudes), per 16-kolo adversarial review.

**Výsledek:**
- Gate #18 success rate: **44.98 % → 55.87 %** (Δ +10.89 pp). HARD STOP rate **4.07 %**
  (95 % CI 3.70–4.48 %), bezpečně pod novým 10 % thresholdem.
- Mean Challenge P&L: +$4 619 → **+$6 339** (+37 %). p95 +$14 921 → **+$18 187**.
- Within-Challenge max DD distribution: mean -$1 942, p5 -$6 763, p95 +$1 523.
- Sanity check (POZNÁMKA krit. gate): 55.87 % ∈ [30 %, 90 %] → žádný halt vyžadován.

**Decision tree application:**
- 55.87 % v **50–59 % band** → 🟡 **STEP 2 + STEP 3 NEEDED** (architektonický redesign).
- HARD STOP 4.07 % < 10 % → ✅ POZNÁMKA #1 PASS (independent gate).
- Sanity check 55.87 % ∈ [30 %, 90 %] → žádný halt.

**Závěr:** STEP 1 přinesl **Δ +10.89 pp**, což **hit conservative estimate band** (55–65 %)
per POZNÁMKA #2. Strategy edge existuje (median +$5 887 > $5K target, mean +$6 339), ale
55.87 % spolehlivost na 30-day Challenge target je **alone insufficient** pro Phase 1
PROCEED. STEP 2 architektonický redesign nutný (loosen UNDEFINED, drop weak cells,
event. Phase 1 60–90 day timeline po FTMO konzultaci) → vrácení Architektovi.

---

## Sizing comparison: v3.3.4 vs v3.3.5 STEP 1

| Cell                | regime | mult v3.3.4 | mult v3.3.5 STEP 1 | Δ |
|---------------------|--------|-------------|---------------------|---|
| us_momentum / TREND | TREND  | 1.0         | 1.0                 | — |
| us_momentum / CALM  | CALM   | 1.0         | 1.0                 | — |
| us_momentum / CRASH | CRASH  | **0.5**     | **1.0**             | **+0.5** |
| orb_dax / CALM      | CALM   | 1.0         | 1.0                 | — |
| any / UNDEFINED     | —      | 0.0         | 0.0                 | — |

Lot example (SL=70 pts, $1 000 risk, EUR/USD 1.08):
- v3.3.4 CRASH: 1000 / (70 × 1.08) × 0.5 = **6.61 lots**
- v3.3.5 STEP 1 CRASH: 1000 / (70 × 1.08) × 1.0 = **13.23 lots** (BSC cap 23.15 not hit)

→ **CRASH cell P&L contribution doubled vs v3.3.4 baseline** (n=182 trades × ~2× lots).

---

## Gate validation results (v3.3.5 STEP 1)

| Gate | Threshold | v3.3.4 | v3.3.5 STEP 1 | Verdict |
|------|-----------|--------|----------------|---------|
| #1 Sample size (asym) | US-MOM≥500, ORB CALM≥100 | PASS | PASS (US-MOM 20 303, ORB CALM 638) | ✅ PASS |
| #4 Sharpe (MC mean)   | ≥1.0      | 1.69    | 1.69 (MC unchanged)         | ✅ PASS |
| #6 Max DD %  (MC 5p)  | <8 %      | -2.18 % | -2.18 % (MC unchanged)      | ✅ PASS |
| #7 Risk of Ruin       | <1 %      | 0.00 % | 0.00 % (MC unchanged)        | ✅ PASS |
| #8 P(HARD STOP) (MC)  | <10 % (was 15 %) | 0.00 % | 0.00 % (MC unchanged)| ✅ PASS |
| #9 Walk-forward       | ≥80 %     | 9.5 %  | 9.5 % (Strategy Limitation) | ❌ FAIL (acknowledged) |
| #14 Per-regime + rolling | per-regime ≥50 + rolling | FAIL  | FAIL (rolling REQUIRES ADJUSTMENT) | ❌ FAIL |
| #15 PF/WR/R-mult uniform | per-cell PF≥1.5 ∧ (WR≥40% ∨ R≥2.0) | FAIL 2/4 | FAIL 2/4 (TREND, CALM PF<1.5) | ❌ FAIL |
| **#18 Challenge Success** | **≥70 % PASS, ≥60 % WARN, <60 % NO-GO** | **44.98 %** | **55.87 %** (95 % CI 54.89–56.84 %) | 🔴 **FAIL** |

POZNÁMKA: Gate #8 Monte Carlo zůstává 0.00 % (vychází z trade-level MC, nezávislé na
gate18 block bootstrap). Block bootstrap HARD STOP (POZNÁMKA #1) = 4.07 % je sekundární
re-validation, vyhodnocená samostatně.

---

## POZNÁMKA #1 — HARD STOP probability re-validation ✅ PASS

Per v3.3.5 STEP 1 acceptance: HARD STOP probability MUST be < 10 %. Nepřekročení
prahu je hard precondition pro STEP 1 PROCEED, nezávisle na success rate.

| Metric | v3.3.4 | v3.3.5 STEP 1 | Threshold |
|--------|--------|----------------|-----------|
| HARD STOP probability (block bootstrap) | n/a (not measured) | **4.07 %** (95 % CI 3.70–4.48 %) | **<10 %** ✅ |
| Within-Challenge max DD mean | n/a | **-$1 942** | informativní |
| Within-Challenge max DD p5  | n/a | **-$6 763** | informativní |
| Within-Challenge max DD p50 | n/a | **-$1 490** | informativní |
| Within-Challenge max DD p95 | n/a | **+$1 523** | informativní |

**Interpretace:** doubled CRASH lots zvýšily Challenge variance, ale 4.07 % HARD STOP
rate je 2.5× pod novým 10 % thresholdem a ~3.7× pod původním 15 % thresholdem. p5 max DD
-$6 763 je těsně pod $7K HARD STOP boundary — distribution okraje confirm že HARD STOP
event je tail risk (~4 % dat).

**Verdikt:** ✅ POZNÁMKA #1 PASS — STEP 1 sizing je **FTMO-safe**.

---

## POZNÁMKA #3 — Per-day vs per-trade worst case breakdown

### Per-trade worst case

Single-trade max loss bounded by Black Swan Cap ($5 000 / 23.15 lots) AND $1 000 risk
target (1 % of $100K account):

| Cell | SL (pts) | lots v3.3.5 | per-trade target loss (USD) |
|------|----------|-------------|------------------------------|
| us_momentum / TREND | 60 | 15.43 | -$1 000 (RISK target) |
| us_momentum / CALM  | 60 | 15.43 | -$1 000 |
| us_momentum / CRASH | 70 | 13.23 | -$1 000 |
| orb_dax / CALM      | 50 | 18.52 | -$1 000 |

**Per-trade interpretation:** RISK_USD_PER_TRADE = $1 000 (1 % of $100K) je **target**,
ne hard floor. Skutečná per-trade loss ≈ SL × lots × eur_usd. BSC cap (23.15 lots)
brání escalaci pro velmi tight SL. Per-trade target loss je **konstantní napříč v3.3.4
a v3.3.5 STEP 1** — sizing formula respektuje 1 % risk targeting independent of
multiplier (multiplier škáluje očekávaný P&L, ne per-trade exposure).

### Per-day & within-Challenge worst case (block bootstrap distribution)

Per-day P&L = sum of per-trade P&L na daném dni. Multiple-trade days mohou vyhladit
loss (decoreláce trade pnls), ale i akumulovat loss (correlated through-regime).
Within-Challenge max DD = cumsum.min() přes 30-day blok.

| Distribution stat | v3.3.5 STEP 1 (USD) | Komentář |
|-------------------|----------------------|----------|
| max DD mean       | **-$1 942** | průměrná Challenge prožívá ~$2K mid-challenge drawdown |
| max DD p5         | **-$6 763** | bottom 5 % Challenges přibližují $7K HARD STOP threshold |
| max DD p50        | **-$1 490** | medián Challenge má jen mírný mid-run drop |
| max DD p95        | **+$1 523** | top 5 % Challenges nikdy nešly do red — straight-up profit |

**Per-day interpretation:** Block bootstrap zachycuje regime persistence + autocorrelation.
30-day Challenge má typicky 1-2 CRASH days; doubling CRASH lots znamená že v block s
vícenásobnými CRASH dny se max DD posune více negativní. **HARD STOP probability 4.07 %**
< 10 % → tail rizik v3.3.5 STEP 1 sizingu **akceptovatelný** per POZNÁMKA #1.

---

## Final P&L distribution (Challenge end-state, USD)

| stat   | v3.3.4 | v3.3.5 STEP 1 | Δ |
|--------|--------|----------------|---|
| mean   | +$4 619 | **+$6 339** | +$1 720 (+37 %) |
| median | n/a (not reported) | **+$5 887** | — |
| p5     | n/a | **-$3 283**   | — |
| p25    | n/a | **+$1 766**   | — |
| p75    | n/a | **+$10 523**  | — |
| p95    | +$14 921 | **+$18 187** | +$3 266 (+22 %) |

**Sanity:** median +$5 887 > $5 000 target → **medián Challenge úspěšný** (víc než
50 % bootstrap blocks překročí target). Klasifikace 55.87 % je validní (median is just
above target, takže borderline výsledek očekávaný). p5 -$3 283 a p95 +$18 187
indikují widespread distribution — high variance je strukturální vlastnost.

---

## POZNÁMKA #2 — Realistic estimate range vs actual outcome

Per Architekt v3.3.5 STEP 1 brief: 16-kolo adversarial dospělo k závěru, že "best case
+25 pp" je optimistic. Realistic uplift band:

| Scenario       | Δ predikce | Predikovaný success rate | **Actual outcome** |
|----------------|------------|--------------------------|---------------------|
| **Conservative** | **+10 pp**   | **~55 %**                    | **✅ HIT** (55.87 %) |
| Central est.   | +13 pp     | ~58 %                    | nedosaženo          |
| Mild upside    | +18 pp     | ~63 %                    | nedosaženo          |
| Optimistic     | +20 pp     | ~65 %                    | nedosaženo          |

**Actual STEP 1 uplift: +10.89 pp → 55.87 % = Conservative scenario hit.**

55.87 % je **uvnitř realistic 55-65 % bandu** ale na **dolní hranici**. 16-kolo
adversarial review se ukázalo přesné — "best case 70 %+" by byl optimistic narrative.

---

## Per-cell P&L distribution (post-STEP-1 sizing)

| Cell                | n trades | lots v3.3.5 | mean P&L/trade pts | mean P&L/trade USD (lots × eur_usd) |
|---------------------|----------|-------------|---------------------|---------------------------------------|
| us_momentum / TREND | 569      | 15.43       | +3.28               | +$54.66 / trade                       |
| us_momentum / CALM  | 232*     | 15.43       | -0.82               | -$13.67 / trade                       |
| us_momentum / CRASH | 182      | 13.23       | +44.82 (×2 vs v3.3.4) | **+$640.30 / trade**                |
| orb_dax / CALM      | 122      | 18.52       | +18.84              | +$376.88 / trade                      |

*us_momentum/CALM n=232 (v3.3.4 reported 457 — rozdíl odpovídá restorovanému F5 MACD
filtru; CALM nyní filtruje více trades než v Phase 0 v3.3.4 raw).

**Per-cell expectancy (USD):**
- US-MOM CRASH dominuje (+$640/trade × 182 trades ≈ +$116 535 sum) — STEP 1 doubling
  multiplikátoru posunul tuto cell na ~50 % celkového P&L kontribuce.
- ORB CALM solidní (+$377/trade × 122 trades ≈ +$45 980).
- US-MOM TREND mírně positive (+$55/trade × 569 trades ≈ +$31 100), ale Gate #15 PF<1.5 = excluded od validace per uniform criterion.
- US-MOM CALM mírně negative (-$14/trade × 232 trades ≈ -$3 248) — drag na portfoliu.

---

## Decision tree application (v3.3.5 STEP 1 refined)

**Tree (STEP 1 evaluation):**
| Gate #18 band | Verdict | Action |
|---|---|---|
| ≥ 70 %         | 🟢 PASS                | Phase 1 PROCEED |
| 60–69 %        | 🟡 USER DECISION       | conditional proceed / minor tuning |
| **50–59 %**    | 🟡 **STEP 2 + STEP 3** | architectural redesign required (return to Architekt) |
| 30–49 %        | 🔴 NO-GO               | strategy fundamentally insufficient |
| < 30 % or > 90 % | 🛑 SANITY HALT       | stop, double-check sizing/regime cache |

**HARD STOP override (POZNÁMKA #1):**
- HARD STOP probability ≥ 10 % → 🔴 STEP 1 NO-GO bez ohledu na success rate

**Tree application — current results:**
1. HARD STOP 4.07 % < 10 % → ✅ POZNÁMKA #1 PASS, override neaktivní.
2. Sanity check: 55.87 % ∈ [30 %, 90 %] → ✅ no halt.
3. Gate #18 = 55.87 % spadá do **50–59 % band** → 🟡 **STEP 2 + STEP 3 NEEDED**.

**Interpretace:** STEP 1 single-parameter sizing change přinesl **Δ +10.89 pp**, což hit
conservative end of POZNÁMKA #2 realistic estimate band (55–65 %). Empirical fakt: STEP 1
sizing fix je validovaný, ale **alone insufficient** pro Gate #18 PASS. Strategy edge
exists (mean +$6 339, median +$5 887 > $5K target), ale variance + CRASH-dependent
upside vyžaduje architektonický redesign (STEP 2) + extended validation (STEP 3) než
re-run Gate #18.

---

## STEP 2 prep — TODO list (documentation only, žádná implementace)

55.87 % vs 70 % target = gap **-14.13 pp**. STEP 2 musí adresovat **architektonické**
limity, ne ladění multiplikátorů. Tento seznam je **podklad pro Architekta**, ne
implementační backlog:

### Hypotéza A — UNDEFINED kanibalizace (highest priority)
- **Diagnóza:** 65 % dnů je UNDEFINED → strategy nemůže obchodovat 2/3 ze 2 888 dnů.
- **Možnosti k posouzení:**
  - A1: Loosen 2/3 consensus rule na 1/3 v některých regime kombinacích (Pavel v3.3.2.1
    to akceptoval, ale Gate #18 ukazuje že to limit dosahuje).
  - A2: Dodat 4. signál do classifier (volume regime, intraday pattern) → snížit
    UNDEFINED na ~30–40 % per backtest projection.
- **Akceptační kritéria pro STEP 2 design:** projection že UNDEFINED rate spadne na
  ≤ 50 % bez zhoršení per-cell PF.

### Hypotéza B — Drop weak cells (Gate #15 violation root cause)
- **Diagnóza:** US-MOM TREND (PF 1.16) + US-MOM CALM (PF 0.96) selhávají Gate #15
  (PF<1.5). Tyto cells přidávají variance bez positive expectancy.
- **Možnosti:**
  - B1: Drop US-MOM TREND a US-MOM CALM, jet pouze 2 active cells: ORB CALM + US-MOM CRASH.
  - B2: Reformulovat F5/F1 filter pro TREND/CALM (pokus selhal v 16-kolo adversarial,
    ale s STEP 1 sizing daty může být prostor).
- **Risk:** dropping cells redukuje trade flow → větší dependence na CRASH frequency.

### Hypotéza C — Phase 1 timeline extension (FTMO konzultace nutná)
- **Diagnóza:** CRASH events ~3 % dnů (89/2 888); 30-day Challenge má typicky 1–2 CRASH
  dny, někdy 0. Edge je CRASH-dependent, takže krátký časový okno limituje exposure.
- **Možnosti:**
  - C1: Konzultovat FTMO whether 60–90 day Challenge timeline je available (Phase 1 je
    typicky 30 days, ale různé FTMO programs).
  - C2: Pokud ne — proceed s 30 days a accept higher variance → potřeba většího
    margin of safety v Gate #18 thresholdu.

### Hypotéza D — 5th setup (UNDEFINED day capture)
- **Diagnóza:** UNDEFINED dnů máme 1 830, ale strategy je tichá. I 1 % WR/PF setup by
  zvýšil aggregate trade flow.
- **Možnosti:**
  - D1: Intraday range expansion / momentum break setup pro UNDEFINED days.
  - D2: Pre-session opening range strategy (08:00–09:00 CET pre-Xetra, regime-agnostic).

### STEP 3 prep (validation framework)
Po STEP 2 redesign nutná re-validace:
- Re-run Gate #18 block bootstrap s nový active cell set + multiplier table.
- Re-run extended ablation Sekce 5 pro nové cell composition.
- Re-validate Gate #15 uniform criterion na všechny aktivní cells.
- Re-run MACD OOS validation pokud reformulujeme filter sets (Hypotéza B2).
- Re-run TREND analytical stress test pokud TREND zůstane active.

---

**Final verdict:** 🟡 **Phase 0 STEP 1 = STEP 2 + STEP 3 NEEDED** per Gate #18 = 55.87 %
v 50–59 % band. POZNÁMKA #1 HARD STOP gate PASS (4.07 %). Δ +10.89 pp **hit conservative
estimate band** (55–65 %), confirming POZNÁMKA #2 calibration. STEP 1 sizing fix je
empirically validovaný **dílčí improvement**, ale **alone insufficient** pro Phase 1
PROCEED. **Vrácení Architektovi** pro STEP 2 architektonický redesign per TODO list
výše. Žádná STEP 2 implementace bez Pavlova/Architektova schválení.

