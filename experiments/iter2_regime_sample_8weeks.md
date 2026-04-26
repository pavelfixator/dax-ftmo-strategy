# Iterace 2 — Regime Sample (8 weeks 2020-2023)

**Cíl:** ověřit chování engine + filtrů přes různé tržní režimy.
**Setupy:** ORB-DAX (A+B), VWAP-Bounce (A+B), US-Momentum (A+B) — paralelně, max 1 pozice.

## Aggregate (8 týdnů)

```json
{
  "n_trades_total": 0,
  "wins": 0,
  "losses": 0,
  "win_rate": 0.0,
  "pnl_total_usd": 0.0,
  "pf": Infinity
}
```

## Per-regime breakdown

```json
{
  "bull": {
    "n_trades": 0,
    "pnl_usd": 0.0,
    "weeks": 2
  },
  "crash": {
    "n_trades": 0,
    "pnl_usd": 0.0,
    "weeks": 2
  },
  "recovery": {
    "n_trades": 0,
    "pnl_usd": 0.0,
    "weeks": 1
  },
  "geopolitical": {
    "n_trades": 0,
    "pnl_usd": 0.0,
    "weeks": 2
  },
  "bear": {
    "n_trades": 0,
    "pnl_usd": 0.0,
    "weeks": 1
  }
}
```

## Per-week breakdown

| # | label | regime | bars | trades | violations | pnl_usd |
|---|---|---|---|---|---|---|
| #1 klidny_bull_pre_covid | bull | 1308 | 0 | 0 | 0.00 |
| #2 crash_start_covid | crash | 1308 | 0 | 0 | 0.00 |
| #3 peak_crash_black_monday_II | crash | 1279 | 0 | 0 | 0.00 |
| #4 recovery_monetary_stimulus | recovery | 1305 | 0 | 0 | 0.00 |
| #5 bull_vaccine_rollout | bull | 1311 | 0 | 0 | 0.00 |
| #6 ukraine_war_start | geopolitical | 1315 | 0 | 0 | 0.00 |
| #7 bear_ecb_hike_fears | bear | 1311 | 0 | 0 | 0.00 |
| #8 banking_crisis_svb_cs | geopolitical | 1319 | 0 | 0 | 0.00 |

## Per-week detail

### #1 klidny_bull_pre_covid (bull) 2020-01-13..2020-01-18

```json
{
  "n": 0
}
```

### #2 crash_start_covid (crash) 2020-02-24..2020-02-29

```json
{
  "n": 0
}
```

### #3 peak_crash_black_monday_II (crash) 2020-03-16..2020-03-21

```json
{
  "n": 0
}
```

### #4 recovery_monetary_stimulus (recovery) 2020-05-11..2020-05-16

```json
{
  "n": 0
}
```

### #5 bull_vaccine_rollout (bull) 2021-04-19..2021-04-24

```json
{
  "n": 0
}
```

### #6 ukraine_war_start (geopolitical) 2022-02-21..2022-02-26

```json
{
  "n": 0
}
```

### #7 bear_ecb_hike_fears (bear) 2022-06-13..2022-06-18

```json
{
  "n": 0
}
```

### #8 banking_crisis_svb_cs (geopolitical) 2023-03-06..2023-03-11

```json
{
  "n": 0
}
```

## Závěr

- Pokud `n_trades_total > 0` a `violations == 0` → engine + filtry kalibrovány
  pro reálné podmínky; lze pokračovat na Iter 3 (plný backtest 2019-2026 po doplnění dat).
- Pokud `n_trades_total == 0` → filtry jsou striktní; nutno snížit thresholds (volume,
  daily bias, ADX, Brooks engulfing definici) v dalším kroku.
- Pokud `violations > 0` → engine bug, fix před pokračováním.

