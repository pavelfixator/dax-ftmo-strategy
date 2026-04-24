"""ÚKOL 4 + Experiment #0 — MT5 connect test + leverage resolution.

Připojí se k běžícímu MT5 terminálu přes MT5_PATH (bez password — MT5 si pamatuje).
Vypíše account info + GER40.cash contract spec + leverage.

Usage: python scripts/test_mt5_connect.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Config  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("DAX FTMO — MT5 Connect Test + Experiment #0 (Leverage Resolution)")
    print("=" * 60)

    print("\n[1/5] Config validation…")
    if not Config.MT5_LOGIN:
        print("  FAIL: MT5_LOGIN not set in .env")
        return 1
    if not Config.MT5_SERVER:
        print("  FAIL: MT5_SERVER not set in .env")
        return 1
    if not Config.MT5_PATH:
        print("  FAIL: MT5_PATH not set in .env")
        return 1
    print(f"  Login:  {Config.MT5_LOGIN}")
    print(f"  Server: {Config.MT5_SERVER}")
    print(f"  Path:   {Config.MT5_PATH}")

    print("\n[2/5] MetaTrader5 package…")
    try:
        import MetaTrader5 as mt5
    except ImportError:
        print("  FAIL: MetaTrader5 package not installed.")
        print("  Run: <python> -m pip install MetaTrader5 python-dotenv")
        return 1
    print(f"  MetaTrader5 module: {mt5.__version__}")

    print("\n[3/5] Attach to terminal…")
    if not mt5.initialize(path=Config.MT5_PATH):
        err = mt5.last_error()
        print(f"  FAIL: mt5.initialize(path=...) error {err}")
        print("  Possible causes:")
        print("   - Terminal not running (start it manually)")
        print("   - Path mismatch (verify MT5_PATH in .env)")
        print("   - Multiple terminals — try without path")
        return 1
    term = mt5.terminal_info()
    print(f"  Terminal connected: {term.name} (build {term.build})")
    print(f"  Path: {term.path}")
    print(f"  Connected to broker: {term.connected}")

    print("\n[4/5] Account info…")
    info = mt5.account_info()
    if info is None:
        print(f"  FAIL: mt5.account_info() returned None: {mt5.last_error()}")
        mt5.shutdown()
        return 1
    if info.login != Config.MT5_LOGIN:
        print(f"  WARNING: connected login {info.login} != expected {Config.MT5_LOGIN}")
        print("  Stopping — wrong terminal attached.")
        mt5.shutdown()
        return 1
    print(f"  Login:        {info.login}")
    print(f"  Server:       {info.server}")
    print(f"  Name:         {info.name}")
    print(f"  Company:      {info.company}")
    print(f"  Currency:     {info.currency}")
    print(f"  Balance:      {info.balance:>15,.2f}")
    print(f"  Equity:       {info.equity:>15,.2f}")
    print(f"  Margin:       {info.margin:>15,.2f}")
    print(f"  Free margin:  {info.margin_free:>15,.2f}")
    print(f"  Leverage:     1:{info.leverage}    <-- Experiment #0 — ACCOUNT-level leverage")
    print(f"  Trade mode:   {info.trade_mode}  (0=demo, 1=contest, 2=real)")

    print("\n[5/5] GER40.cash contract spec…")
    sym = mt5.symbol_info(Config.SYMBOL)
    if sym is None:
        print(f"  WARNING: {Config.SYMBOL} not found in Market Watch.")
        print("  Add manually: in MT5 right-click Market Watch -> Symbols -> find GER40.cash -> Show.")
        mt5.shutdown()
        return 2

    if not sym.visible:
        # try to make visible
        mt5.symbol_select(Config.SYMBOL, True)
        sym = mt5.symbol_info(Config.SYMBOL)

    print(f"  Symbol:           {sym.name}")
    print(f"  Description:      {sym.description}")
    print(f"  Visible:          {sym.visible}")
    print(f"  Trade mode:       {sym.trade_mode}  (4=full)")
    print(f"  Contract size:    {sym.trade_contract_size}")
    print(f"  Tick size:        {sym.trade_tick_size}")
    print(f"  Tick value:       {sym.trade_tick_value}")
    print(f"  Point:            {sym.point}")
    print(f"  Digits:           {sym.digits}")
    print(f"  Spread (points):  {sym.spread}")
    print(f"  Stops level:      {sym.trade_stops_level}")
    print(f"  Volume min:       {sym.volume_min}")
    print(f"  Volume max:       {sym.volume_max}")
    print(f"  Volume step:      {sym.volume_step}")
    print(f"  Margin currency:  {sym.currency_margin}")
    print(f"  Profit currency:  {sym.currency_profit}")
    print(f"  Swap long/short:  {sym.swap_long} / {sym.swap_short}")

    # Symbol-level leverage (může být odlišná od account-level)
    sym_lev = getattr(sym, "trade_leverage", None)
    print(f"  Symbol leverage:  {sym_lev}    <-- Experiment #0 — SYMBOL-level leverage")

    # Last tick
    tick = mt5.symbol_info_tick(Config.SYMBOL)
    if tick:
        print(f"\n  Last tick: bid={tick.bid} ask={tick.ask} spread={tick.ask - tick.bid:.2f} time={tick.time}")

    # JSON dump pro Experiment-0 report
    print("\n--- JSON SUMMARY (pro Experiment-0 report) ---")
    summary = {
        "timestamp": str(__import__("datetime").datetime.now()),
        "account": {
            "login": info.login,
            "server": info.server,
            "currency": info.currency,
            "balance": info.balance,
            "equity": info.equity,
            "leverage_account": info.leverage,
        },
        "symbol": {
            "name": sym.name,
            "contract_size": sym.trade_contract_size,
            "tick_size": sym.trade_tick_size,
            "tick_value": sym.trade_tick_value,
            "point": sym.point,
            "digits": sym.digits,
            "spread_points": sym.spread,
            "stops_level": sym.trade_stops_level,
            "volume_min": sym.volume_min,
            "volume_max": sym.volume_max,
            "volume_step": sym.volume_step,
            "currency_margin": sym.currency_margin,
            "currency_profit": sym.currency_profit,
            "leverage_symbol": sym_lev,
        },
        "tick": {
            "bid": tick.bid if tick else None,
            "ask": tick.ask if tick else None,
            "spread": (tick.ask - tick.bid) if tick else None,
        },
    }
    print(json.dumps(summary, indent=2, default=str))

    mt5.shutdown()
    print("\nOK — Experiment #0 done. Save JSON above to vault.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
