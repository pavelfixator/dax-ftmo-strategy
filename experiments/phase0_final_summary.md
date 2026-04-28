# Phase 0 Final Summary — v3.3.4 (post-15-rounds adversarial)

**Datum:** 2026-04-28
**Verdikt:** 🔴 **NO-GO** (Gate #18 FAIL, return to v3.3.5 redesign)

---

## Top-line verdict

| Layer | Result |
|---|---|
| **Gate #18 (NEW v3.3.4)** | 🔴 **0.00 % Challenge Success Rate** (10 000 sims, threshold 70 %) |
| MACD OOS validation | ⚠️ MARGINAL (ratio 62.6 %) → revert s WARNING |
| TREND stress test (analytical) | 🔴 DROP US-MOM TREND (pessimistic 2× → -0.22 < +0.5) |
| Phase 0 Final | **🔴 NO-GO → v3.3.5 redesign** |

**Per v3.3.4 spec decision tree:**
- ≥70 % → 🟢 Phase 1 PROCEED
- 60-70 % → 🟡 USER DECISION
- **<60 % → 🔴 AUTOMATIC NO-GO**

---

## Gate Criteria Summary (18 gates)

| # | Gate | Verdict | Value |
|---|---|---|---|
| 1 | Sample size (asym v3.3.2.1) | ✅ PASS | US-MOM 20 303, ORB CALM 638 |
| 2 | Win Rate ≥50 % | ⚠️ MIXED | US-MOM CRASH 53 %, CALM 49 %, TREND 46 %, ORB 34 % |
| 3 | Profit Factor ≥1.5 | ❌ FAIL 2/4 | TREND 1.16 ✗, CALM 0.96 ✗ |
| 4 | Sharpe ≥1.0 (MC mean) | ✅ PASS | 1.69 |
| 5 | Sortino ≥1.3 | ⚠️ MISSING | not computed |
| 6 | Max DD <8 % (MC 5p) | ✅ PASS | -2.18 % |
| 7 | Risk of Ruin <1 % | ✅ PASS | 0.00 % |
| 8 | P(HARD STOP) <15 % | ✅ PASS | 0.00 % |
| 9 | OOS ≥80 % (walk-forward) | ❌ FAIL | 9.5 % (Strategy Limitation) |
| 10 | FTMO compliance 100 % | ✅ PASS | 0 daily violations |
| 11 | Close framework stress | ⚠️ MISSING | not run |
| 12 | Swap coverage >99.5 % | ⚠️ MISSING | Exp #0.1 odložen |
| 13 | BSC verification | ⚠️ PARTIAL | sizing_v331 enforces, no audit |
| 14 | Per-regime + rolling 30d | ❌ FAIL | per-regime ✓, rolling 46.6 % fail (REQUIRES ADJUSTMENT) |
| 15 | Uniform v3.3.4 (PF + WR/R-mult) | ❌ FAIL | TREND fail PF; CALM fail PF |
| 16 | Ablation positive | ⚠️ MISSING | not explicitly run |
| 17 | Classifier accuracy ≥75 % | ⚠️ MISSING | regime cache built, per-event acc not measured |
| **18** | **Challenge Success ≥70 %** | 🔴 **FAIL** | **0.00 %** |

**Aggregate: 6 PASS / 6 FAIL / 1 MIXED / 5 MISSING**

---

## Gate #18 detail (kritický)

| Metric | Value |
|---|---|
| Simulations | 10 000 |
| Block size | 30 trading days |
| Eligible days (non-UNDEFINED) | 1 058 |
| n_blocks available | 1 029 |
| Profit target | $5 000 (Phase 1 +5 %) |
| **Successes** | **0** |
| **Success rate** | **0.00 %** |

### Final P&L distribution (USD)

| stat | value |
|---|---|
| mean | +$436 |
| median | +$401 |
| p5 | -$246 |
| p25 | +$126 |
| p75 | +$719 |
| p95 | +$1 239 |

### Diagnose

- Strategy je **mírně profitable** (mean +$436/30d positive), ale **Phase 1 target +$5 000/30d je ~12× větší** než typický mean.
- I p95 (+$1 239) nedosahuje target.
- Implikace: I s nejlepším 30-day oknem v historii nedosáhneme Phase 1 5 % cíle za měsíc. Strategy musí buď:
  1. Significantly increased risk per trade (víc lots, závisí na BSC + drawdown limits)
  2. Higher per-trade expectancy (lepší filter + entry logic)
  3. Více trades per 30-day window (uvolnit UNDEFINED rule, víc aktivních dnů)

---

## MACD OOS Validation (US-MOM CALM cell)

| Period | n | WR | exp pts | total |
|---|---|---|---|---|
| Train 2015-2022 | 156 | 56.41 % | +7.40 | +1 155 |
| Test 2023-2026 | 76 | 56.58 % | **+4.64** | +352 |

**Ratio:** 0.6262 (62.6 %) → **MARGINAL** band → revert s WARNING.

WR konzistentní; expectancy degradace -37 %, ale stále silně pozitivní.

---

## TREND Stress Test (analytical, v3.3.4 correct math)

| scenario | mult | Δ buffer | projected exp |
|---|---|---|---|
| baseline | 1.0× | +0.0 | +3.28 |
| mild ×1.5 | 1.5× | +1.75 | +1.53 |
| **pessimistic ×2.0** | **2.0×** | **+3.50** | **-0.22** |
| extreme ×3.0 | 3.0× | +7.0 | -3.72 |

**Verdict:** **DROP US-MOM TREND** (pessimistic projected -0.22 < +0.5 threshold).

---

## Active Cells výsledky (Phase 0 backtest 2015-2026)

| setup | regime | n | WR | exp_pts | Sharpe | PF | max_DD pts |
|---|---|---|---|---|---|---|---|
| orb_dax | CALM | 122 | 0.34 | **+18.84** | 3.60 | 1.76 | -669 |
| us_momentum | TREND | 569 | 0.46 | +3.28 | 0.79 | 1.16 | -2 196 |
| us_momentum | CALM | 457 | 0.49 | -0.82 (no F5 MACD) | -0.27 | 0.96 | -2 551 |
| us_momentum | CRASH | **182** | **0.53** | **+44.82** | 4.44 | 2.16 | -4 460 |

**Aggregate FTMO:** total +$12 905, max DD -$7 145 (-7.1 %), 0 violations.

**Monte Carlo 10K:** Sharpe 1.69 mean, max DD 5p -2.18 %, P(HARD STOP) 0 %, RoR 0 %.

---

## Co dál — v3.3.5 redesign hypotézy

Gate #18 FAIL je **architektonický** problém, ne implementační:

1. **UNDEFINED 65 % kanibalizuje trade flow** — strategy nemůže obchodovat 2/3 dní. Možnosti:
   - Loosen 2/3 consensus rule na 1/3 v některých regime kombinacích (Pavel v3.3.2.1 to akceptoval, ale Gate #18 ukazuje že to limit zákona)
   - Dodat 4. signál pro classifier (např. volume regime, intraday pattern) → snížit UNDEFINED na ~30-40 %

2. **Per-trade expectancy je marginal** — orb_dax CALM +18.84 pts a us_mom CRASH +44.82 pts jsou dobré, ale us_mom TREND +3.28 a us_mom CALM -0.82 are weak. Možnosti:
   - Drop TREND + CALM cells úplně, jet pouze ORB CALM + US-MOM CRASH (2 active cells)
   - Add 5. setup pro intraday range expansion / momentum break

3. **30-day window je krátký pro CRASH-dependent edge** — most of profit je v CRASH dnech (89/2888 = 3 %). 30-day okno typically má 1-2 CRASH dny, někdy 0. Pro Phase 1 success buď:
   - Změnit Phase 1 timeline na 60-90 days (FTMO konzultace)
   - Boost risk multiplier v CRASH na 1.0× (vs current 0.5×) — zvýší upside z těch řídkých CRASH okén

4. **Increase position size** — current 1 lot proxy v MC. Real sizing per Strategy v3.3.x je 2-23 lots dle BSC. Pokud MC použil reálný sizing per trade (3-5× větší P&L), výsledek by mohl pass. Tedy bug v gate18: sizing není aplikován per-trade, P&L = pnl_pts × 1.0 lot × eur_usd. **Pavel by měl tento bug review.** Pokud aplikujeme 5× sizing → mean +$2 180/30d, p95 +$6 195 → success rate ~25-35 %, asi WARNING band.

---

**Final verdict:** 🔴 **Phase 0 NO-GO** per v3.3.4 self-imposed constraint Gate #18 <60 %.

**Recommended next:** Review Gate #18 sizing assumption (1 lot vs realistic Strategy v3.3.x lot calculation) before declaring v3.3.5 redesign. Pokud sizing fix → re-run Gate #18 → reálné success rate.
