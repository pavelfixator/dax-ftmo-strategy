"""DAX FTMO trading bot — src package.

Layered architecture:
  - strategy/  signal generation (indicators, data feed, news, setups)
  - risk/      sizing + FTMO/custom rule enforcement
  - execution/ MT5 connector, order execution, health checks
  - journal/   Obsidian writer, pattern DB, shadow tracker, divergence
  - notifier/  Discord (primary) + email (fallback) alerts

Top-level: config.py (env loader), main.py (entry point).
"""
__version__ = "0.2.0"
