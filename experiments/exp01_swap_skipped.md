# Experiment #0.1 — Swap Empirical Measurement (SKIPPED)

**Datum rozhodnutí:** 2026-04-26
**Stav:** ⏸ ODLOŽENO / VYNECHÁNO pro Phase 0
**Důvod:** FTMO Modus Operandi risk + offline-only Phase 0 pivot

---

## 1. Kontext

Experiment #0.1 (Strategy v3.2 spec) měl empiricky změřit DAX overnight swap přes
6-test schedule (27.4.2026 – 7.5.2026, viz `scripts/exp01_orchestrator.py`):
1. LONG single (Po→Út)
2. SHORT single (Út→St)
3. LONG single (St→Čt)
4. LONG 4-night WEEKEND (Čt→Po, 1.5. Labour Day)
5. SHORT single (Po→Út)
6. SHORT 2-night (Út→Čt)

Sizing: 0.10 lot, brackets ±2000/±5000 trader-points, MT5 reference baseline
swap_long = -386.93 EUR/lot/noc, swap_short = -47.82 EUR/lot/noc.

## 2. Proč SKIP (2026-04-26)

Uživatel obchoduje **FTMO Real Challenge účet** aktivně na DAX (GER40). Spuštění
naší DEMO strategie s 23 lotů na DAX paralelně by mohlo být klasifikováno jako:

- **Modus Operandi repeated across accounts** — FTMO Forbidden Practice
  ([FTMO Account Rules § "Other forbidden practices"](https://ftmo.com/en/account-agreement/))
- **Substantially larger position sizes vs Real account** — flagging trigger

**Riziko:** blokace FTMO Real účtu při překryvu strategií.

Před Phase 1 LIVE konzultace s FTMO supportem (Phase 0 PASS prerequisite).

## 3. Náhradní řešení (offline-only Phase 0)

Místo empirického měření použijeme **MT5 SYMBOL_INFO baseline** (zjištěno
v Experiment #0 audit, viz `exp0_mt5_audit.md`):

| Field | Hodnota |
|---|---|
| `swap_long`  | -386.93 EUR/lot/noc |
| `swap_short` | -47.82 EUR/lot/noc |
| `swap_3days` | wednesday rollover (3× swap) |

### Strategy clauses (backtest invariants)

1. **Safety multiplier 1.5×** aplikován v close framework:
   - `effective_swap_long = -386.93 × 1.5 = -580.40 EUR/lot/noc`
   - `effective_swap_short = -47.82 × 1.5 = -71.73 EUR/lot/noc`
   - Důvod: variabilita broker-side swap rates + EUR/USD kurz; 1.5× pokrývá
     historické worst-case z what-if stress scenario #10.

2. **Max overnight swap exposure < $1500** (50 % daily loss limit $5000 × 0.30
   pojistka):
   - LONG sizing cap: `lots_max = 1500 / (580.40 × eurusd_rate) ≈ 2.4 lot`
   - SHORT sizing cap: `lots_max = 1500 / (71.73 × eurusd_rate) ≈ 19 lot`
   - V praxi LONG je limiting binding constraint; A-setup 1% risk @ 100k =
     1000 USD, sizing v rozsahu 0.5-1.5 lot — cap nikdy nezasahuje, ale je
     belt-and-suspenders.

3. **No overnight on Wednesday** (3-day rollover) pro positions opened Mon-Tue
   pokud predicted swap > 50% denní R. Discrétní case-by-case rule v `rules_engine.py`.

4. **Weekend hold — pouze A-setup s confidence > 0.85 a min 1:3 RRR** (4-night
   exposure = 4× swap pokud LONG). Default pravidlo: zavřít pátek 18:00 CET.

## 4. Když Phase 0 PASS — co dál?

Po PASS (Phase 0 gate kritéria) konzultace s FTMO supportem o Phase 1 LIVE:
- Otázka: "We trade DAX on our Real account. We'd like to run a DAX-strategy
  Demo in parallel for development. Same instrument, smaller size, different
  setup logic. Is this acceptable, or would it be flagged as Modus Operandi
  repetition?"
- Pokud OK → Experiment #0.1 LIVE re-spuštěn jako součást Phase 1 first-week.
- Pokud ne → Experiment #0.1 trvale použije MT5 baseline + safety multiplier
  (žádné empirické měření, dokud Real účet aktivní).

## 5. Stav infrastruktury (2026-04-26)

- Win Scheduled Task `DAX-FTMO-Exp01`: **State=Disabled**
  (`Disable-ScheduledTask -TaskName 'DAX-FTMO-Exp01'`)
- `data/exp01_state.json`: current_step=0, position_ticket=null, history=[]
- `scripts/exp01_orchestrator.py`: ponechán v repu (idempotentní, neběží),
  reaktivovat pouze po explicitním rozhodnutí.
- `scripts/exp01_swap_measurement.py`: ponechán v repu jako reference impl.

## 6. Změna Phase 0 timeline

| Day | Původně | Aktualizovaně |
|---|---|---|
| 1-7 | exp01 LIVE + framework | data acquisition + framework moduly |
| 8-12 | experimenty #2-#7 | experimenty #1-#7 (offline backtest) |
| 13-14 | Monte Carlo + walk-forward | Monte Carlo + walk-forward + 13 gate |
| 15-16 | reporty | reporty + GitHub tag `v3.2-phase0-offline-complete` |

---

**Závěr:** Experiment #0.1 (LIVE empirical swap) je **odložen** do post-Phase 0
FTMO konzultace. Phase 0 backtest pokračuje s MT5 baseline + 1.5× safety
multiplier. Plný revival path je dokumentován výše pro budoucí spuštění.
