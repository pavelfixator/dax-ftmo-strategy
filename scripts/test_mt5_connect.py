"""Quick MT5 connection smoke test (ÚKOL 4 verifikace).

Usage: python scripts/test_mt5_connect.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Config  # noqa: E402


def main() -> int:
    errors = Config.validate()
    if errors:
        print("Config errors:")
        for e in errors:
            print(f"  - {e}")
        return 1

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("MetaTrader5 package not installed. Run: pip install -r requirements.txt")
        return 1

    if not mt5.initialize(login=Config.MT5_LOGIN, server=Config.MT5_SERVER):
        print(f"mt5.initialize() failed: {mt5.last_error()}")
        return 1

    info = mt5.account_info()
    if info is None:
        print(f"mt5.account_info() returned None: {mt5.last_error()}")
        mt5.shutdown()
        return 1

    print(f"Login:     {info.login}")
    print(f"Server:    {info.server}")
    print(f"Balance:   {info.balance} {info.currency}")
    print(f"Equity:    {info.equity}")
    print(f"Leverage:  1:{info.leverage}")
    print(f"Company:   {info.company}")

    sym = mt5.symbol_info(Config.SYMBOL)
    if sym is None:
        print(f"Symbol {Config.SYMBOL} not found in Market Watch — ruční přidej.")
    else:
        print(f"\n{Config.SYMBOL}:")
        print(f"  Contract size:  {sym.trade_contract_size}")
        print(f"  Tick size:      {sym.trade_tick_size}")
        print(f"  Tick value:     {sym.trade_tick_value}")
        print(f"  Spread:         {sym.spread}")

    mt5.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
