"""Historický backtest engine.

Spec: Blok 3 ÚKOL 9.
- Data: MT5 copy_rates_range() nebo StrategyQuant CSV
- Timezone: CET (single source of truth)
- Simulace: tick-by-tick nebo 1m bars
- Realistický spread + slippage model
- Aplikace VŠECH pravidel identicky jako live bot
- Output: list obchodů + equity curve + metriky (WR, PF, Sharpe, Sortino, Calmar, max DD, per-setup breakdown)
"""
