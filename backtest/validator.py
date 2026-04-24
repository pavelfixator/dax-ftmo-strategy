"""Validation engine — 10 povinných kontrol před Fází 1.

Spec: Blok 3 ÚKOL 13.
1. Train/test split — rozdíl max ±20 %
2. Walk-forward — všechny OOS profitabilní
3. Monte Carlo — ruin < 1 %, 5th DD < 8K
4. Data quality — žádné díry, spiky, timezone
5. Realistic costs — spread + slippage + commission
6. Regime testing — bull/bear/range/high-vol
7. Survivorship bias check
8. Sample size min 500 / setup
9. Sharpe > 1.0, Sortino > Sharpe
10. Reality check vs benchmark

Output: backtest_validation_report.md PASS/FAIL.
JAKÁKOLIV FAIL → Phase 0 NEPROJDE → zpět k Architektovi.
"""
