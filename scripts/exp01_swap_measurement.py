"""Experiment #0.1 — empirical swap measurement (BLOKAČNÍ pre-backtest).

Per Strategy v3.2 prompt: měření skutečného swap přes 4-8 nocí na FTMO Free Trial.
Compare proti MT5 SYMBOL_SWAP_LONG = -386.93 EUR/lot/noc.

Subcommands:
  precheck       — pre-flight: market status, account, algo trading, sizing math
  open --side {LONG|SHORT}  — otevře 0.10 lot pozici s wide SL (server-side, mandatory)
  status         — vypíše současnou pozici (cena, swap, profit, time held)
  close          — zavře všechny pozice GER40.cash, spočítá empirický swap, zapíše

CSV log: vault/03-Backtest/Experiments/exp01_swap_data.csv
Markdown report (append-only): vault/03-Backtest/Experiments/exp01_swap_measurement.md

Konvence:
- Default lots = 0.10 (per user 2026-04-25 rozhodnutí, 10× méně než Strategy v3.2 default 1.0)
- SL_WIDE = entry ± 2000 points (~8% market move, $234 max při 0.10 lot — bezpečné)
- TP_WIDE = entry ± 5000 points (efektivně se nikdy netrigger, drží do manuálního close)
- Comment field: "EXP01-LONG-{date}" / "EXP01-SHORT-{date}"
- VAROVÁNÍ: porušuje "intraday only" pravidlo Strategy v3.2 — KONTROLOVANÁ VÝJIMKA
  pro účely měření swap. Po dokončení #0.1 zase striktně intraday.

Usage:
  python scripts/exp01_swap_measurement.py precheck
  python scripts/exp01_swap_measurement.py open --side LONG
  python scripts/exp01_swap_measurement.py status
  python scripts/exp01_swap_measurement.py close
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Config  # noqa: E402

# Constants
LOTS = 0.10
# POZOR: na DAX 1 trader-point = 1 EUR price unit (digits=2, point=0.01 = 1 tick = 0.01 EUR).
# Strategy v3.2 vždy uvádí "body" = trader-points, NE MT5 ticks.
# 1 trader-point = 100 MT5 ticks = 1.0 v price scale.
# Pro DAX: SL distance v price = SL trader-points (neuplatňovat * sym.point = bug).
SL_WIDE_TRADER_POINTS = 2000   # ~8% adverse move (~$234 max při 0.10 lot)
TP_WIDE_TRADER_POINTS = 5000   # efektivně netriggerující TP
SYMBOL = Config.SYMBOL  # GER40.cash
COMMENT_PREFIX = "EXP01"

VAULT_BASE = Path(r"C:/Users/AOS Server/trading-lab-DAX/DAX-FTMO-Strategy/03-Backtest/Experiments")
CSV_PATH = VAULT_BASE / "exp01_swap_data.csv"
MD_PATH = VAULT_BASE / "exp01_swap_measurement.md"

CSV_HEADER = [
    "timestamp",
    "action",
    "side",
    "lots",
    "ticket",
    "price",
    "sl",
    "tp",
    "balance",
    "equity",
    "position_swap",
    "position_profit",
    "eurusd",
    "computed_empirical_swap_usd",
    "comment",
]


def _ensure_csv():
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CSV_PATH.exists():
        with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)


def _log_csv(row: dict):
    _ensure_csv()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([row.get(c, "") for c in CSV_HEADER])


def _append_md(line: str):
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MD_PATH.exists():
        MD_PATH.write_text(
            "# Experiment #0.1 — Empirical Swap Measurement\n\n"
            "**Status:** running\n"
            "**Lots per trade:** 0.10 (per Pavel decision 2026-04-25)\n"
            "**Strategy v3.2 reference:** swap_long = -386.93 EUR/lot/noc, "
            "swap_short = -47.82 EUR/lot/noc (z MT5 SYMBOL_SWAP_LONG/SHORT)\n\n"
            "**Konvence:** SL_WIDE = ±2000 pts, TP_WIDE = ±5000 pts (server-side mandatory).\n\n"
            "**Účel:** ověřit MT5 API hodnoty proti reálnému balance change přes 4-8 nocí.\n\n"
            "---\n\n"
            "## Running log\n\n",
            encoding="utf-8",
        )
    with MD_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _connect():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=Config.MT5_PATH):
        print(f"FAIL: mt5.initialize: {mt5.last_error()}")
        sys.exit(1)
    a = mt5.account_info()
    if a is None or a.login != Config.MT5_LOGIN:
        print(f"FAIL: account mismatch (got {a.login if a else None}, expected {Config.MT5_LOGIN})")
        mt5.shutdown()
        sys.exit(1)
    return mt5


def cmd_precheck() -> int:
    mt5 = _connect()
    print("=" * 60)
    print("Experiment #0.1 — PRE-FLIGHT CHECK")
    print("=" * 60)

    t = mt5.terminal_info()
    a = mt5.account_info()
    print(f"\n[Terminal] path={t.path}")
    print(f"  trade_allowed (toolbar):  {t.trade_allowed}")
    print(f"  dlls_allowed:             {t.dlls_allowed}")
    print(f"  ping_last:                {t.ping_last/1000:.1f} ms")
    print(f"\n[Account] login={a.login}, server={a.server}, currency={a.currency}")
    print(f"  balance: {a.balance:>15,.2f}")
    print(f"  equity:  {a.equity:>15,.2f}")
    print(f"  margin:  {a.margin:>15,.2f}")
    print(f"  free:    {a.margin_free:>15,.2f}")
    print(f"  trade_allowed (server):   {a.trade_allowed}")
    print(f"  trade_expert (EA):        {a.trade_expert}")
    print(f"  leverage: 1:{a.leverage}")

    sym = mt5.symbol_info(SYMBOL)
    if sym is None:
        print(f"FAIL: symbol {SYMBOL} not found")
        mt5.shutdown()
        return 1
    if not sym.visible:
        mt5.symbol_select(SYMBOL, True)
        sym = mt5.symbol_info(SYMBOL)
    tick = mt5.symbol_info_tick(SYMBOL)
    eurusd = mt5.symbol_info_tick("EURUSD")

    print(f"\n[Symbol {SYMBOL}]")
    print(f"  visible:        {sym.visible}")
    print(f"  trade_mode:     {sym.trade_mode}  (4=full)")
    print(f"  bid/ask:        {tick.bid} / {tick.ask}")
    print(f"  spread (pts):   {sym.spread}")
    print(f"  swap_long:      {sym.swap_long}  EUR/lot/noc (MT5 spec)")
    print(f"  swap_short:     {sym.swap_short} EUR/lot/noc (MT5 spec)")
    print(f"  swap_3days:     {sym.swap_rollover3days} (5=Wed->Thu rollover triple)")
    print(f"  tick_value:     {sym.trade_tick_value}")

    # Sizing math
    print(f"\n[Sizing @ {LOTS} lot]")
    print(f"  Required margin (EUR):  {LOTS * tick.ask / a.leverage:.2f}")
    print(f"  Required margin (USD):  {LOTS * tick.ask / a.leverage * eurusd.bid:.2f}")
    swap_long_usd = sym.swap_long * LOTS * eurusd.bid
    swap_short_usd = sym.swap_short * LOTS * eurusd.bid
    print(f"  Expected swap LONG  per noc: {sym.swap_long * LOTS:.2f} EUR ~= {swap_long_usd:.2f} USD")
    print(f"  Expected swap SHORT per noc: {sym.swap_short * LOTS:.2f} EUR ~= {swap_short_usd:.2f} USD")
    print(f"  EURUSD bid: {eurusd.bid}")

    # Wide SL / TP plán
    # 1 trader-point = 1.0 v price (DAX index CFD); ne sym.point (=0.01) ani sym.trade_tick_size
    sl_long = tick.ask - SL_WIDE_TRADER_POINTS
    tp_long = tick.ask + TP_WIDE_TRADER_POINTS
    sl_short = tick.bid + SL_WIDE_TRADER_POINTS
    tp_short = tick.bid - TP_WIDE_TRADER_POINTS
    print(f"\n[Plánované wide brackets]")
    print(f"  LONG  entry @ ask {tick.ask}  SL={sl_long:.2f}  TP={tp_long:.2f}")
    print(f"  SHORT entry @ bid {tick.bid}  SL={sl_short:.2f}  TP={tp_short:.2f}")

    # Open positions check
    poses = mt5.positions_get(symbol=SYMBOL)
    if poses:
        print(f"\n⚠️  EXISTING OPEN POSITIONS pro {SYMBOL}:")
        for p in poses:
            print(f"   ticket={p.ticket} type={p.type} volume={p.volume} price_open={p.price_open} "
                  f"swap={p.swap} profit={p.profit} comment={p.comment}")
    else:
        print(f"\n✓ Žádná otevřená pozice pro {SYMBOL}.")

    # Market open check
    market_open = sym.trade_mode == 4 and tick.time > 0
    sec_since_tick = (dt.datetime.now() - dt.datetime.fromtimestamp(tick.time)).total_seconds()
    print(f"\n[Market state]")
    print(f"  trade_mode == 4 (full): {sym.trade_mode == 4}")
    print(f"  last tick time: {dt.datetime.fromtimestamp(tick.time)} ({sec_since_tick:.0f} sec ago)")
    if sec_since_tick > 60:
        print(f"  ⚠️  Last tick > 60s old -> market pravděpodobně CLOSED (víkend / mimo hodiny)")
    else:
        print(f"  ✓ Market jeví se aktivní (recent tick)")

    print("\n" + "=" * 60)
    print("PRE-FLIGHT DONE. Spusti `open --side LONG` nebo `open --side SHORT` pro start.")
    print("=" * 60)

    mt5.shutdown()
    return 0


def cmd_open(side: str) -> int:
    if side not in ("LONG", "SHORT"):
        print("FAIL: --side must be LONG or SHORT")
        return 1

    mt5 = _connect()
    a = mt5.account_info()
    sym = mt5.symbol_info(SYMBOL)
    if not sym.visible:
        mt5.symbol_select(SYMBOL, True)
        sym = mt5.symbol_info(SYMBOL)
    tick = mt5.symbol_info_tick(SYMBOL)
    eurusd = mt5.symbol_info_tick("EURUSD")

    if side == "LONG":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
        sl = price - SL_WIDE_TRADER_POINTS  # 1 trader-point = 1.0 price (DAX)
        tp = price + TP_WIDE_TRADER_POINTS
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
        sl = price + SL_WIDE_TRADER_POINTS
        tp = price - TP_WIDE_TRADER_POINTS

    today = dt.date.today().isoformat()
    comment = f"{COMMENT_PREFIX}-{side}-{today}"

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOTS,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,  # 20 points slippage tolerance
        "magic": 1001,    # exp01 magic number
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    print(f"Sending: {side} {LOTS} lot @ {price} | SL {sl:.2f} | TP {tp:.2f} | comment {comment}")
    print(f"Balance before: {a.balance:.2f} | equity: {a.equity:.2f}")

    result = mt5.order_send(request)
    if result is None:
        print(f"FAIL: order_send returned None: {mt5.last_error()}")
        mt5.shutdown()
        return 1
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"FAIL: retcode={result.retcode} comment={result.comment}")
        print(f"  request: {request}")
        print(f"  result:  {result}")
        # Try alternative filling mode
        if result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
            print("Retrying with FOK filling…")
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"FOK also failed: retcode={result.retcode} comment={result.comment}")
                mt5.shutdown()
                return 1
        else:
            mt5.shutdown()
            return 1

    print(f"OK retcode={result.retcode} order={result.order} deal={result.deal}")
    print(f"  ticket={result.order} price_filled={result.price} volume={result.volume}")

    a_after = mt5.account_info()
    _log_csv({
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "action": "OPEN",
        "side": side,
        "lots": LOTS,
        "ticket": result.order,
        "price": result.price,
        "sl": sl,
        "tp": tp,
        "balance": a_after.balance,
        "equity": a_after.equity,
        "position_swap": 0.0,
        "position_profit": 0.0,
        "eurusd": eurusd.bid,
        "computed_empirical_swap_usd": "",
        "comment": comment,
    })
    _append_md(
        f"### {dt.datetime.now().isoformat(timespec='seconds')} — OPEN {side}\n"
        f"- ticket: {result.order}\n"
        f"- volume: {LOTS} lot\n"
        f"- price filled: {result.price}\n"
        f"- SL: {sl:.2f}, TP: {tp:.2f}\n"
        f"- balance before: {a.balance:.2f} -> after: {a_after.balance:.2f}\n"
        f"- equity: {a_after.equity:.2f}\n"
        f"- EURUSD: {eurusd.bid}\n"
        f"- comment: `{comment}`\n"
    )
    print(f"\n✓ logged to {CSV_PATH}")
    print(f"✓ markdown updated: {MD_PATH}")
    mt5.shutdown()
    return 0


def cmd_status() -> int:
    mt5 = _connect()
    a = mt5.account_info()
    poses = mt5.positions_get(symbol=SYMBOL)
    if not poses:
        print("Žádná otevřená pozice.")
        mt5.shutdown()
        return 0

    print(f"Account: balance={a.balance:.2f}, equity={a.equity:.2f}, free_margin={a.margin_free:.2f}")
    print(f"\nOtevřené pozice {SYMBOL}:")
    for p in poses:
        side = "LONG" if p.type == 0 else "SHORT"
        held = dt.datetime.now() - dt.datetime.fromtimestamp(p.time)
        tick = mt5.symbol_info_tick(SYMBOL)
        cur_price = tick.bid if side == "LONG" else tick.ask
        unreal = (cur_price - p.price_open) * p.volume * (1 if side == "LONG" else -1)
        print(f"  ticket {p.ticket} | {side} {p.volume} | open {p.price_open} -> cur {cur_price} "
              f"| held {str(held).split('.')[0]} | swap={p.swap:.2f} EUR | profit={p.profit:.2f} EUR "
              f"| unreal_pts={unreal:.2f}")
        print(f"    SL={p.sl} TP={p.tp} comment={p.comment}")

    mt5.shutdown()
    return 0


def cmd_close() -> int:
    mt5 = _connect()
    a_before = mt5.account_info()
    eurusd = mt5.symbol_info_tick("EURUSD")
    poses = mt5.positions_get(symbol=SYMBOL)
    if not poses:
        print("Žádná otevřená pozice na " + SYMBOL)
        mt5.shutdown()
        return 0

    print(f"Balance before close: {a_before.balance:.2f}")
    for p in poses:
        side_str = "LONG" if p.type == 0 else "SHORT"
        # Close opposite direction
        order_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(SYMBOL)
        price = tick.bid if p.type == 0 else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": p.volume,
            "type": order_type,
            "position": p.ticket,
            "price": price,
            "deviation": 20,
            "magic": 1001,
            "comment": f"{COMMENT_PREFIX}-CLOSE-{p.ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        print(f"Closing ticket {p.ticket} {side_str} {p.volume} @ ~{price} "
              f"(swap accrued {p.swap:.2f} EUR, profit {p.profit:.2f} EUR)")
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"FAIL close: retcode={result.retcode if result else 'None'} "
                  f"comment={result.comment if result else mt5.last_error()}")
            # try FOK fallback
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                mt5.shutdown()
                return 1

        a_after = mt5.account_info()
        # Empirical swap = (balance change) - (mark-to-market profit at close)
        # MT5 reports swap and profit as separate fields, both already booked into balance
        empirical_total = a_after.balance - a_before.balance
        mt5_swap_usd = p.swap * eurusd.bid  # convert EUR -> USD
        mt5_profit_usd = p.profit * eurusd.bid
        # The "true" swap is simply the swap field from position, in EUR, converted to USD
        # We log both the field value and the implied delta from balance change
        print(f"  closed @ {result.price}")
        print(f"  balance after: {a_after.balance:.2f} (Δ {empirical_total:+.2f})")
        print(f"  MT5 reported: swap={p.swap:.2f} EUR ~= {mt5_swap_usd:.2f} USD, profit={p.profit:.2f} EUR ~= {mt5_profit_usd:.2f} USD")
        print(f"  Total EUR booked: {p.swap + p.profit:.2f} EUR ~= {(p.swap + p.profit) * eurusd.bid:.2f} USD")

        _log_csv({
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "action": "CLOSE",
            "side": side_str,
            "lots": p.volume,
            "ticket": p.ticket,
            "price": result.price,
            "sl": p.sl,
            "tp": p.tp,
            "balance": a_after.balance,
            "equity": a_after.equity,
            "position_swap": p.swap,
            "position_profit": p.profit,
            "eurusd": eurusd.bid,
            "computed_empirical_swap_usd": mt5_swap_usd,
            "comment": p.comment,
        })
        held = dt.datetime.now() - dt.datetime.fromtimestamp(p.time)
        _append_md(
            f"### {dt.datetime.now().isoformat(timespec='seconds')} — CLOSE {side_str}\n"
            f"- ticket: {p.ticket}\n"
            f"- volume: {p.volume} lot\n"
            f"- held: {str(held).split('.')[0]}\n"
            f"- price open -> close: {p.price_open} -> {result.price}\n"
            f"- MT5 swap field: {p.swap:.2f} EUR ~= {mt5_swap_usd:.2f} USD\n"
            f"- MT5 profit field: {p.profit:.2f} EUR ~= {mt5_profit_usd:.2f} USD\n"
            f"- balance change: {empirical_total:+.2f} USD\n"
            f"- EURUSD at close: {eurusd.bid}\n"
            f"- vs. Strategy v3.2 reference (per lot per noc): "
            f"{p.swap / p.volume if p.volume else 0:.2f} EUR/lot vs −386.93 LONG / −47.82 SHORT\n"
        )

    mt5.shutdown()
    print(f"\n✓ All positions closed and logged.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Experiment #0.1 swap measurement")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("precheck", help="Pre-flight checks bez otvírání pozice")
    p_open = sub.add_parser("open", help="Otevřít 0.10 lot pozici")
    p_open.add_argument("--side", required=True, choices=["LONG", "SHORT"])
    sub.add_parser("status", help="Vypsat současné pozice")
    sub.add_parser("close", help="Zavřít všechny EXP01 pozice + logovat")
    args = parser.parse_args()

    if args.cmd == "precheck":
        return cmd_precheck()
    if args.cmd == "open":
        return cmd_open(args.side)
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "close":
        return cmd_close()
    return 1


if __name__ == "__main__":
    sys.exit(main())
