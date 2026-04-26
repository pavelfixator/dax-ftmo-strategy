# Iterace 1 — Smoke Test 2020-01-13..2020-01-17

**Týden:** Po 2020-01-13 .. Pá 2020-01-17 (klidný bull pre-COVID)
**Bary:** 1308 (5m) | **Range UTC:** 2020-01-13 00:00:00+00:00 .. 2020-01-17 20:55:00+00:00
**Setupy:** ORB-DAX (A+B), VWAP-Bounce (A+B), US-Momentum (A+B)

## Aggregate stats

```json
{
  "n": 0
}
```

**Invariant violations:** 0

## Per-trade log

**No trades** — žádný setup nedosáhl confirmation v daném týdnu.

**Možné důvody (debug v Iter2):**
- Daily bias filtr může být přísný (potřebuje 3 booleans).
- ORB volume threshold 1.5× nemusí být splněn v tichém týdnu.
- VWAP-Bounce vyžaduje ADX < 20 + Keltner touch + Brooks engulfing — restrictive.
- US-Momentum vyžaduje pre-US trend HH/LL series + alignment.

## Co fungovalo / Co selhalo

**Fungovalo:**
- Backtest engine prošel bez crashes a bez invariant violations.
- 5m parquet (2019-2023) loadnut OK, range filter funguje (CET → UTC conversion).
- Setups + risk_manager + rules_engine integrace bez výjimek.

**Selhalo / k debug v Iter2:**
- (vyplň po Iter2)

## Další krok

Pokud Iter1 bez fatálních problémů → spustit Iterace 2 (8 týdnů regime sample).
