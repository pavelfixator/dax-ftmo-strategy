# STEP 2 Prep — TODO list pro Architekta

**Datum:** 2026-04-29
**Trigger:** Phase 0 v3.3.5 STEP 1 = 🟡 STEP 2 + STEP 3 NEEDED (Gate #18 = 55.87 %, 50–59 % band)
**Status:** ⏸ documentation only — žádná implementace bez Pavlova/Architektova schválení

---

## 1. Empirické inputs pro STEP 2 design

| Metrika | v3.3.4 | v3.3.5 STEP 1 | Δ |
|---|---|---|---|
| Gate #18 success rate | 44.98 % | 55.87 % | +10.89 pp ✅ conservative band hit |
| HARD STOP probability | n/a | 4.07 % (CI 3.70–4.48 %) | PASS (<10 %) |
| Mean Challenge P&L | +$4 619 | +$6 339 | +$1 720 (+37 %) |
| Median Challenge P&L | n/a | +$5 887 | > $5K target |
| Within-Challenge max DD p5 | n/a | -$6 763 | těsně pod $7K HS |

**Klíčový poznatek:** sizing alone improvement insufficient. Gap k 70 % PASS je
**-14.13 pp** — vyžaduje architektonický change, ne další multiplikátorové ladění.

---

## 2. Gate #15 violations (root cause weak cells)

| Cell | n | WR | PF | R-mult | Verdict | Akce kandidát |
|---|---|---|---|---|---|---|
| orb_dax / CALM | 122 | 34.43 % | 1.76 | 3.35 | ✅ PASS | KEEP |
| us_momentum / TREND | 569 | 45.52 % | 1.16 | 1.38 | ❌ FAIL (PF<1.5) | DROP nebo redesign |
| us_momentum / CALM | 232 | 49.23 % | 0.96 | 0.99 | ❌ FAIL (PF<1.5) | DROP nebo redesign |
| us_momentum / CRASH | 182 | 52.75 % | 2.16 | 1.93 | ✅ PASS | KEEP (high priority — STEP 1 doubled contribution) |

**Empirický fakt:** 2/4 active cells selhávají Gate #15. Je-li cell weak per Gate #15,
pak její příspěvek do Gate #18 bootstrap je net-neutral nebo net-negative.

---

## 3. Hypotézy k posouzení Architektem

### H-A: UNDEFINED reduction (highest priority)
- **Fakt:** 1 830 / 2 888 dnů = 63.4 % UNDEFINED → strategy je tichá většinu času.
- **Volby:**
  - A1: Loosen 2/3 → 1/3 consensus (Pavel v3.3.2.1 limit dosažen).
  - A2: 4. classifier signál (volume regime / intraday pattern).
- **Kritérium:** projection UNDEFINED ≤ 50 % bez per-cell PF degradace.
- **Risk:** větší UNDEFINED-day exposure → potřeba nového setupu (H-D) nebo akceptovat
  classification noise.

### H-B: Drop weak cells
- **Fakt:** US-MOM TREND PF 1.16, US-MOM CALM PF 0.96 (oba < 1.5).
- **Volby:**
  - B1: Drop oba → 2 active cells (ORB CALM + US-MOM CRASH).
  - B2: Reformulovat F1/F5 filter sets pro TREND/CALM.
- **Risk:** B1 zvýší CRASH-event dependence (89 dnů z 2 888 = 3.1 %); 30-day okno často
  obsahuje 0–1 CRASH dnů → vyšší variance, potenciálně horší Gate #18.
- **Akceptační kritérium:** projection že drop nezhorší aggregate Gate #18 přes
  block bootstrap re-run.

### H-C: Phase 1 timeline (FTMO operational)
- **Fakt:** CRASH ~3 % dnů, 30-day Challenge má typicky 1–2 CRASH dny.
- **Volby:**
  - C1: FTMO konzultace whether 60–90 day Phase 1 program available.
  - C2: Pokud ne → keep 30 days, accept higher variance, redesign internal threshold.
- **Risk:** Pavel musí ověřit dostupnost u FTMO před spoléháním.

### H-D: 5. setup pro UNDEFINED capture
- **Fakt:** UNDEFINED dnů 63 % → ~1 830 dnů bez aktivní strategie.
- **Volby:**
  - D1: Intraday range expansion / momentum break (regime-agnostic).
  - D2: Pre-Xetra opening range setup (08:00–09:00 CET).
- **Risk:** přidat 5. setup zvýší implementational complexity; potřeba uniform Gate #15
  PF≥1.5 + WR≥40 % nebo R-mult≥2.0 na nový setup.

---

## 4. STEP 3 — validation framework po STEP 2

Po Architektově STEP 2 designu musí proběhnout (per spec — žádná implementace bez
schválení):

1. **Re-run Gate #18 block bootstrap** s novou active cell set + multiplier table
   (10K sims, 30-day blocks, HARD STOP < 10 % stále hard precondition).
2. **Re-run extended ablation Sekce 5** pro nové cell composition (FDR + Bonferroni
   + OOS + bootstrap CI per cell).
3. **Re-validate Gate #15** uniform criterion na všechny aktivní cells.
4. **Re-run MACD OOS validation** pokud reformulujeme filter sets (H-B2).
5. **Re-run TREND analytical stress test** pokud TREND zůstane active.
6. **HARD STOP probability re-validation** s novými lots — kritické zejména pokud
   STEP 2 zvýší per-trade exposure.

---

## 5. Rozhodovací bod (Pavel + Architekt)

**Před STEP 2 implementací:**
1. Pavel rozhodne, které hypotézy z H-A/B/C/D pursue.
2. Architekt napíše STEP 2 spec (jako u STEP 1 — single-purpose changes preferred).
3. Pavel schválí → impl → STEP 3 validation framework spustím.

**Žádná implementace bez explicit "Pokračuj sekce X" pokynu.**

---

## 6. Risk register pro STEP 2

| Risk | Pravděpodobnost | Mitigace |
|---|---|---|
| H-A1 (1/3 consensus) zvýší classification noise → false signals | high | A/B per-cell PF check; A2 jako fallback |
| H-B1 (drop cells) zvýší CRASH dependence → větší variance, horší G18 | medium-high | block bootstrap projection před implementací |
| H-C1 FTMO 60-day program neexistuje | unknown | C2 fallback (keep 30d) |
| H-D5 nový setup nesplní Gate #15 | medium | uniform criterion strict; backtest před live |
| Multiple H-* combined → overfit / look-ahead bias | medium | nezávislý backtest+walk-forward; OOS strict |

---

**Konec STEP 2 prep TODO. Vrácení Architektovi pro design rozhodnutí.**
