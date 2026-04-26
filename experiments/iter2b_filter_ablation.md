# Iter2b — Filter Ablation Diagnostika

**Cíl:** identifikovat binding filter — ten s největším signal-count dropoff
po jeho vynechání.

**Týdny:** 2020-01-13..17 (klidný bull pre-COVID) + 2020-03-16..20 (peak crash).
**Setupy:** orb_dax / vwap_bounce / us_momentum.
**Konfigurace:** baseline (F1+F2+F3+F4), drop_F1, drop_F2, drop_F3, drop_F4, all_off.

Metriky per (setup, week, config):
- `n_signals` — kolik 5m barů triggerlo Signal (bez RRR/sizing check)
- `n_trades` — počet kompletních trades (po RRR + sizing)
- `win_rate` — % zisků na trade
- `avg_pnl_pts` — průměrný P&L v points (bod = 1 bod indexu)

## Week `calm_bull_pre_covid` (bull)

### Setup `orb_dax`

| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |
|---|---:|---:|---:|---:|---:|
| baseline_F1234 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F1 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F2 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F3 | 4 | 4 | 0.00 | -31.8 | -127.2 |
| drop_F4 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| all_off | 13 | 13 | 0.00 | -36.4 | -473.7 |

### Setup `vwap_bounce`

| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |
|---|---:|---:|---:|---:|---:|
| baseline_F1234 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F1 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F2 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F3 | 5 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F4 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| all_off | 120 | 0 | 0.00 | +0.0 | +0.0 |

### Setup `us_momentum`

| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |
|---|---:|---:|---:|---:|---:|
| baseline_F1234 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F1 | 5 | 5 | 0.00 | -23.7 | -118.4 |
| drop_F2 | 12 | 12 | 0.92 | +10.3 | -2.5 |
| drop_F3 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F4 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| all_off | 54 | 54 | 0.43 | -11.8 | -664.1 |

## Week `peak_crash_black_monday_II` (crash)

### Setup `orb_dax`

| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |
|---|---:|---:|---:|---:|---:|
| baseline_F1234 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F1 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F2 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F3 | 9 | 9 | 0.89 | +181.0 | -117.3 |
| drop_F4 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| all_off | 28 | 28 | 0.39 | +21.8 | -1118.0 |

### Setup `vwap_bounce`

| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |
|---|---:|---:|---:|---:|---:|
| baseline_F1234 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F1 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F2 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F3 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F4 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| all_off | 120 | 10 | 0.20 | -33.4 | -417.9 |

### Setup `us_momentum`

| config | signals | trades | win_rate | avg_pnl_pts | max_dd_pts |
|---|---:|---:|---:|---:|---:|
| baseline_F1234 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F1 | 36 | 36 | 0.33 | -9.8 | -3484.3 |
| drop_F2 | 12 | 12 | 0.08 | -108.7 | -1304.4 |
| drop_F3 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| drop_F4 | 0 | 0 | 0.00 | +0.0 | +0.0 |
| all_off | 54 | 54 | 0.24 | -43.5 | -4788.7 |

## Diagnostika — který filter je BINDING

Pro každý setup spočti dropoff per filter:
```
dropoff(F_X) = signals[drop_F_X] - signals[baseline]
```
Nejvyšší dropoff → binding filter.

**Souhrn (signals napříč oběma týdny):**

### orb_dax

- baseline_F1234: **0** signals
- drop_F1: 0 signals (Δ +0)
- drop_F2: 0 signals (Δ +0)
- drop_F3: 13 signals (Δ +13) ← LIKELY BINDING
- drop_F4: 0 signals (Δ +0)
- all_off: 41 signals (ceiling)

### vwap_bounce

- baseline_F1234: **0** signals
- drop_F1: 0 signals (Δ +0)
- drop_F2: 0 signals (Δ +0)
- drop_F3: 5 signals (Δ +5) ← LIKELY BINDING
- drop_F4: 0 signals (Δ +0)
- all_off: 240 signals (ceiling)

### us_momentum

- baseline_F1234: **0** signals
- drop_F1: 41 signals (Δ +41) ← LIKELY BINDING
- drop_F2: 24 signals (Δ +24) ← LIKELY BINDING
- drop_F3: 0 signals (Δ +0)
- drop_F4: 0 signals (Δ +0)
- all_off: 108 signals (ceiling)

## Závěr a kalibrace

- **Pokud `drop_F1` má největší positive Δ → daily bias je binding.**
  Návrh: 2/3 booleans místo all-3 (např. `yest_close > EMA20D1` AND
  (`yest_close > yest_open` OR `yest_close > day_before_close`)).

- **Pokud `drop_F3` má největší Δ pro vwap_bounce → Brooks engulfing too strict.**
  Návrh: relax na "wick-tested + close back inside band" (touch & reverse).

- **Pokud `drop_F4` má největší Δ → ATR/volume thresholds restriktivní.**
  Návrh: snížit ratio (1.5× → 1.2× volume; 0.7× → 0.5× ATR median).

- **Pokud `all_off` zůstává << expected (~50-100 signals/week) →** entry condition
  samotná je restriktivní (ORB range / engulfing / breakout). Re-spec needed.

Po Pavlově rozhodnutí: implementuj kalibraci, spustit Iter2c (re-run regime sample).
