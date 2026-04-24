# dax-ftmo-strategy

DAX (GER40.cash) FTMO 2-Step Swing 100K trading bot.

**Stav:** Fáze 0 (backtest + vývoj). Bot zatím neobchoduje.

## Architektura

Python robot běží 24/7 jako Windows Service, připojuje se do MetaTrader 5 terminálu (FTMO demo/Challenge), obchoduje dle Strategy v3.0 (dodá Architekt).

## Struktura

```
dax-ftmo-bot/
├── src/               — produkční kód bota
│   ├── main.py        — entry point, trading loop
│   ├── config.py      — .env, konstanty
│   ├── mt5_connector.py — MT5 API wrapper
│   ├── setups/        — setupy (dědí z base_setup.py)
│   ├── risk_manager.py, rules_engine.py, executor.py
│   ├── shadow_tracker.py, divergence_detector.py
│   ├── news_scraper.py, discord_notifier.py, email_notifier.py
│   ├── health_check.py, journal_writer.py, pattern_database.py
│   └── indicators.py, data_feed.py
├── backtest/          — backtest engine, Monte Carlo, what-if, walk-forward, validator
├── scripts/           — instalace Service, data download, backtest runner
├── tests/             — pytest unit + integration testy
└── docs/              — technická dokumentace
```

Obsidian vault (zápisy, ML, templates) je **samostatný repo** v `../trading-lab-DAX/DAX-FTMO-Strategy/`.

## Instalace

```powershell
# 1. Python 3.12 je nainstalován per-user (winget)
# 2. Clone repo
git clone https://github.com/<user>/dax-ftmo-strategy.git dax-ftmo-bot
cd dax-ftmo-bot

# 3. Virtualenv (doporučeno)
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
.\.venv\Scripts\Activate.ps1

# 4. Deps
pip install -r requirements.txt

# 5. Config
copy .env.example .env
notepad .env   # doplň hodnoty

# 6. Test MT5 spojení
python scripts/test_mt5_connect.py
```

## Spuštění

```powershell
# Backtest
python scripts/run_backtest.py --start 2019-01-01 --end 2026-03-31

# Bot (dev mode, foreground)
python src/main.py

# Bot (Windows Service)
python scripts/install_service.py install
net start DAX-FTMO-Bot
```

## FTMO pravidla (stručně)

Viz `../trading-lab-DAX/DAX-FTMO-Strategy/00-System/FTMO-Rules.md` pro plnou specifikaci.

- Max daily loss 5 000 USD
- Max total loss 10 000 USD
- Min 4 trading days / phase
- Žádný hedging, HFT
- Entry window 08:00–18:00 CET, forced close 20:55 CET

## Status

| Úkol | Status |
|---|---|
| 1. Prostředí | ✅ (Python 3.12.10, Git, MT5 běží) |
| 2. GitHub | ⏸ |
| 3. Discord | ⏸ |
| 4. FTMO demo | ⏸ |
| 5. Obsidian vault | ✅ |
| 6. Python kostra | 🟡 |
| 7–20 | ⏳ čeká Strategy v3.0 |

## Licence

Private. Vývoj: Pavel + Claude Code.
