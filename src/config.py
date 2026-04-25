"""Config — načítá .env a validuje při startu.

Spec: Blok 3 ÚKOL 7.1 (config.py).
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    # Python
    PYTHON_EXE = os.getenv("PYTHON_EXE", "")

    # MT5
    MT5_LOGIN = int(os.getenv("MT5_LOGIN") or 0)
    MT5_SERVER = os.getenv("MT5_SERVER", "")
    MT5_PATH = os.getenv("MT5_PATH", "")

    # Discord
    DISCORD = {
        "signaly": os.getenv("DISCORD_WEBHOOK_SIGNALY", ""),
        "journal": os.getenv("DISCORD_WEBHOOK_JOURNAL", ""),
        "backtest": os.getenv("DISCORD_WEBHOOK_BACKTEST", ""),
        "mistakes": os.getenv("DISCORD_WEBHOOK_MISTAKES", ""),
        "account": os.getenv("DISCORD_WEBHOOK_ACCOUNT", ""),
        "alerts": os.getenv("DISCORD_WEBHOOK_ALERTS", ""),
        "divergence": os.getenv("DISCORD_WEBHOOK_DIVERGENCE", ""),
        "experiments": os.getenv("DISCORD_WEBHOOK_EXPERIMENTS", ""),
    }

    # Email
    SMTP_SERVER = os.getenv("SMTP_SERVER", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    EMAIL_TO = os.getenv("EMAIL_TO", "")

    # Paths
    OBSIDIAN_VAULT = Path(os.getenv("OBSIDIAN_VAULT_PATH", ""))

    # Trading rules (constants, NOT user-tunable)
    SYMBOL = "GER40.cash"
    MAX_DAILY_LOSS_USD = 5_000
    MAX_TOTAL_LOSS_USD = 10_000
    MIN_RRR = 2.0
    A_SETUP_RISK_USD = 1_000
    B_SETUP_RISK_USD = 500
    MAX_TRADES_PER_DAY = 5
    STOP_RULE_CONSECUTIVE_LOSSES = 2
    ENTRY_WINDOW_START_CET = (8, 0)
    ENTRY_WINDOW_END_CET = (18, 0)
    FORCED_CLOSE_CET = (20, 55)

    @classmethod
    def validate(cls) -> list[str]:
        errors: list[str] = []
        if not cls.MT5_LOGIN:
            errors.append("MT5_LOGIN not set in .env")
        if not cls.MT5_SERVER:
            errors.append("MT5_SERVER not set in .env")
        if not cls.OBSIDIAN_VAULT.exists():
            errors.append(f"OBSIDIAN_VAULT_PATH invalid: {cls.OBSIDIAN_VAULT}")
        return errors
