# OOS Validation — Extended Ablation

**Train period:** 2019-01-01 .. 2023-01-01
**Test period:**  2023-01-01 .. 2026-04-01

**Acceptance:** test_expectancy ≥ 0.7 × train_expectancy

| setup | regime | config | train_exp | test_exp | ratio | OOS pass | reason |
|---|---|---|---:|---:|---:|---|---|
| orb_dax | TREND | baseline_F1234 | -45.56 | +0.00 | -0.00 | ✗ | train expectancy -45.5557 ≤ 0 (no in-sample edge) |
| orb_dax | TREND | drop_F1 | -8.37 | -41.55 | 4.96 | ✗ | train expectancy -8.3701 ≤ 0 (no in-sample edge) |
| orb_dax | TREND | drop_F2 | -45.56 | +0.00 | -0.00 | ✗ | train expectancy -45.5557 ≤ 0 (no in-sample edge) |
| orb_dax | TREND | drop_F3 | +16.39 | -1.37 | -0.08 | ✗ | test expectancy -1.3676 ≤ 0 (negative OOS) |
| orb_dax | TREND | drop_F4 | -45.56 | +0.00 | -0.00 | ✗ | train expectancy -45.5557 ≤ 0 (no in-sample edge) |
| orb_dax | TREND | all_off | +9.12 | -13.41 | -1.47 | ✗ | test expectancy -13.4133 ≤ 0 (negative OOS) |
| orb_dax | CALM | baseline_F1234 | +87.01 | +0.00 | 0.00 | ✗ | test expectancy 0.0000 ≤ 0 (negative OOS) |
| orb_dax | CALM | drop_F1 | +87.01 | -38.75 | -0.45 | ✗ | test expectancy -38.7539 ≤ 0 (negative OOS) |
| orb_dax | CALM | drop_F2 | +87.01 | +0.00 | 0.00 | ✗ | test expectancy 0.0000 ≤ 0 (negative OOS) |
| orb_dax | CALM | drop_F3 | +11.61 | +25.40 | 2.19 | ✓ | OOS ratio 218.89% ≥ 70% |
| orb_dax | CALM | drop_F4 | +87.01 | +0.00 | 0.00 | ✗ | test expectancy 0.0000 ≤ 0 (negative OOS) |
| orb_dax | CALM | all_off | -8.95 | +17.54 | -1.96 | ✗ | train expectancy -8.9500 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | baseline_F1234 | -46.45 | +194.78 | -4.19 | ✗ | train expectancy -46.4496 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | drop_F1 | -23.28 | +73.66 | -3.16 | ✗ | train expectancy -23.2781 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | drop_F2 | -46.45 | +194.78 | -4.19 | ✗ | train expectancy -46.4496 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | drop_F3 | -46.45 | +194.78 | -4.19 | ✗ | train expectancy -46.4496 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | drop_F4 | -46.45 | +194.78 | -4.19 | ✗ | train expectancy -46.4496 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | all_off | -23.28 | +73.66 | -3.16 | ✗ | train expectancy -23.2781 ≤ 0 (no in-sample edge) |
| us_momentum | TREND | baseline_F1234 | +3.00 | +3.89 | 1.30 | ✓ | OOS ratio 129.68% ≥ 70% |
| us_momentum | TREND | drop_F1 | -0.20 | +9.83 | -49.22 | ✗ | train expectancy -0.1996 ≤ 0 (no in-sample edge) |
| us_momentum | TREND | drop_F2 | +2.76 | +0.79 | 0.29 | ✗ | OOS ratio 28.67% < 70% |
| us_momentum | TREND | drop_F3 | +3.00 | +3.89 | 1.30 | ✓ | OOS ratio 129.68% ≥ 70% |
| us_momentum | TREND | drop_F4 | +3.59 | -8.61 | -2.40 | ✗ | test expectancy -8.6115 ≤ 0 (negative OOS) |
| us_momentum | TREND | all_off | +2.57 | +3.03 | 1.18 | ✓ | OOS ratio 117.95% ≥ 70% |
| us_momentum | CALM | baseline_F1234 | +7.40 | +4.64 | 0.63 | ✗ | OOS ratio 62.62% < 70% |
| us_momentum | CALM | drop_F1 | +12.11 | -1.40 | -0.12 | ✗ | test expectancy -1.3970 ≤ 0 (negative OOS) |
| us_momentum | CALM | drop_F2 | +7.40 | +4.64 | 0.63 | ✗ | OOS ratio 62.62% < 70% |
| us_momentum | CALM | drop_F3 | +7.40 | +4.64 | 0.63 | ✗ | OOS ratio 62.62% < 70% |
| us_momentum | CALM | drop_F4 | +2.57 | +1.95 | 0.76 | ✓ | OOS ratio 75.85% ≥ 70% |
| us_momentum | CALM | all_off | +10.28 | -1.22 | -0.12 | ✗ | test expectancy -1.2184 ≤ 0 (negative OOS) |
| us_momentum | CRASH | baseline_F1234 | +9.47 | +0.00 | 0.00 | ✗ | test expectancy 0.0000 ≤ 0 (negative OOS) |
| us_momentum | CRASH | drop_F1 | +25.27 | +321.77 | 12.73 | ✓ | OOS ratio 1273.41% ≥ 70% |
| us_momentum | CRASH | drop_F2 | +5.79 | -74.27 | -12.84 | ✗ | test expectancy -74.2732 ≤ 0 (negative OOS) |
| us_momentum | CRASH | drop_F3 | +9.47 | +0.00 | 0.00 | ✗ | test expectancy 0.0000 ≤ 0 (negative OOS) |
| us_momentum | CRASH | drop_F4 | +32.42 | +0.00 | 0.00 | ✗ | test expectancy 0.0000 ≤ 0 (negative OOS) |
| us_momentum | CRASH | all_off | +15.30 | +24.04 | 1.57 | ✓ | OOS ratio 157.18% ≥ 70% |
| orb_dax | CRASH | F5_CRASH:F5a_range_exp | -46.45 | +194.78 | -4.19 | ✗ | train expectancy -46.4496 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | F5_CRASH:F5b_brooks_break | +12.99 | +185.03 | 14.25 | ✓ | OOS ratio 1424.72% ≥ 70% |
| orb_dax | CRASH | F5_CRASH:F5c_rsi_extreme | +0.00 | +217.02 | 0.00 | ✗ | train expectancy 0.0000 ≤ 0 (no in-sample edge) |
| orb_dax | CRASH | F5_CRASH:F5d_nr4 | -52.04 | +168.98 | -3.25 | ✗ | train expectancy -52.0402 ≤ 0 (no in-sample edge) |
| us_momentum | CALM | F5_CALM:F5a_macd_3_10 | +7.40 | +4.64 | 0.63 | ✗ | OOS ratio 62.62% < 70% |
| us_momentum | CALM | F5_CALM:F5b_dual_ema | -5.50 | +8.78 | -1.60 | ✗ | train expectancy -5.4981 ≤ 0 (no in-sample edge) |
| us_momentum | CALM | F5_CALM:F5c_volume_profile | -1.06 | +0.90 | -0.85 | ✗ | train expectancy -1.0579 ≤ 0 (no in-sample edge) |
| us_momentum | CALM | F5_CALM:F5d_atr_norm_momentum | -8.39 | +1.66 | -0.20 | ✗ | train expectancy -8.3910 ≤ 0 (no in-sample edge) |
