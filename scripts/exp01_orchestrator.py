"""Experiment #0.1 auto-loop orchestrator (idempotent state machine).

Schedule per Pavel decision 2026-04-25 (CEST = UTC+2):
  #1 Po 27.4. 10:00 -> Ut 28.4. 10:00 LONG single
  #2 Ut 28.4. 10:00 -> St 29.4. 10:00 SHORT single
  #3 St 29.4. 10:00 -> Ct 30.4. 10:00 LONG single
  #4 Ct 30.4. 10:00 -> Po 4.5. 10:00 LONG 4-night WEEKEND
  #5 Po 4.5. 10:00 -> Ut 5.5. 10:00 SHORT single
  #6 Ut 5.5. 10:00 -> Ct 7.5. 10:00 SHORT 2-night

Subcommands: status | run [--dry-run] | daemon [--interval N] | reset
State: dax-ftmo-bot/data/exp01_state.json
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import Config  # noqa
import requests  # noqa

LOTS = 0.10
SL_WIDE = 2000
TP_WIDE = 5000
MAGIC = 1001
PFX = "EXP01"
SYMBOL = Config.SYMBOL
ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "exp01_state.json"
VAULT = Path(r"C:/Users/AOS Server/trading-lab-DAX/DAX-FTMO-Strategy/03-Backtest/Experiments")
CSV_PATH = VAULT / "exp01_swap_data.csv"
MD_PATH = VAULT / "exp01_swap_measurement.md"
CET = dt.timezone(dt.timedelta(hours=2))

SCHEDULE = [
    {"step": 1, "side": "LONG",  "open": "2026-04-27T10:00:00+02:00", "close": "2026-04-28T10:00:00+02:00", "label": "LONG single"},
    {"step": 2, "side": "SHORT", "open": "2026-04-28T10:00:00+02:00", "close": "2026-04-29T10:00:00+02:00", "label": "SHORT single"},
    {"step": 3, "side": "LONG",  "open": "2026-04-29T10:00:00+02:00", "close": "2026-04-30T10:00:00+02:00", "label": "LONG single"},
    {"step": 4, "side": "LONG",  "open": "2026-04-30T10:00:00+02:00", "close": "2026-05-04T10:00:00+02:00", "label": "LONG 4-night WEEKEND (1.5. DE Labour Day)"},
    {"step": 5, "side": "SHORT", "open": "2026-05-04T10:00:00+02:00", "close": "2026-05-05T10:00:00+02:00", "label": "SHORT single"},
    {"step": 6, "side": "SHORT", "open": "2026-05-05T10:00:00+02:00", "close": "2026-05-07T10:00:00+02:00", "label": "SHORT 2-night"},
]

CSV_HEADER = ["timestamp", "step", "action", "side", "lots", "ticket", "price", "sl", "tp",
              "balance", "equity", "position_swap_eur", "position_profit_eur", "eurusd", "comment"]


def parse_iso(s): return dt.datetime.fromisoformat(s)
def now_cet(): return dt.datetime.now(tz=CET)


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"current_step": 0, "position_ticket": None, "last_action_at": None,
            "last_action_kind": None, "history": []}


def save_state(s):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(s, indent=2, default=str), encoding="utf-8")


def discord(channel, msg):
    url = Config.DISCORD.get(channel, "")
    if not url:
        return
    try:
        requests.post(url, json={"content": msg}, timeout=10)
    except Exception as e:
        print(f"  discord {channel} err: {e}")


def connect():
    import MetaTrader5 as mt5
    if not mt5.initialize(path=Config.MT5_PATH):
        raise RuntimeError(f"initialize: {mt5.last_error()}")
    a = mt5.account_info()
    if a is None or a.login != Config.MT5_LOGIN:
        mt5.shutdown()
        raise RuntimeError("account mismatch")
    return mt5


def find_pos(mt5):
    for p in mt5.positions_get(symbol=SYMBOL) or []:
        if p.magic == MAGIC and p.comment.startswith(PFX):
            return p
    return None


def do_open(mt5, side, step):
    sym = mt5.symbol_info(SYMBOL)
    if not sym.visible:
        mt5.symbol_select(SYMBOL, True)
    tick = mt5.symbol_info_tick(SYMBOL)
    if side == "LONG":
        ot, price = mt5.ORDER_TYPE_BUY, tick.ask
        sl, tp = price - SL_WIDE, price + TP_WIDE
    else:
        ot, price = mt5.ORDER_TYPE_SELL, tick.bid
        sl, tp = price + SL_WIDE, price - TP_WIDE
    cm = f"{PFX}-S{step}-{side}-{dt.date.today().isoformat()}"
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "volume": LOTS,
           "type": ot, "price": price, "sl": sl, "tp": tp, "deviation": 20,
           "magic": MAGIC, "comment": cm,
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        req["type_filling"] = mt5.ORDER_FILLING_FOK
        res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"open failed: retcode={res.retcode if res else None} {res.comment if res else mt5.last_error()}")
    return {"ticket": res.order, "price": res.price, "sl": sl, "tp": tp, "comment": cm}


def do_close(mt5, p):
    tick = mt5.symbol_info_tick(SYMBOL)
    if p.type == 0:
        ot, price = mt5.ORDER_TYPE_SELL, tick.bid
    else:
        ot, price = mt5.ORDER_TYPE_BUY, tick.ask
    req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": SYMBOL, "volume": p.volume,
           "type": ot, "position": p.ticket, "price": price, "deviation": 20,
           "magic": MAGIC, "comment": f"{PFX}-CL-{p.ticket}",
           "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        req["type_filling"] = mt5.ORDER_FILLING_FOK
        res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"close failed: retcode={res.retcode if res else None}")
    return {"ticket": p.ticket, "price": res.price, "swap_eur": p.swap, "profit_eur": p.profit}


def log_csv(row):
    import csv
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    new = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_HEADER)
        w.writerow([row.get(c, "") for c in CSV_HEADER])


def append_md(text):
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not MD_PATH.exists():
        h = ("# Experiment #0.1 - Empirical Swap Measurement (Auto-loop)\n\n"
             "**Sizing:** 0.10 lot. **Brackets:** SL +-2000 / TP +-5000 trader-points.\n\n"
             "**MT5 reference:** swap_long -386.93 EUR/lot/noc, swap_short -47.82 EUR/lot/noc.\n\n"
             "## Schedule\n\n| # | Side | Open | Close | Label |\n|---|---|---|---|---|\n")
        for s in SCHEDULE:
            h += f"| {s['step']} | {s['side']} | {s['open']} | {s['close']} | {s['label']} |\n"
        h += "\n## Action log\n\n"
        MD_PATH.write_text(h, encoding="utf-8")
    with MD_PATH.open("a", encoding="utf-8") as f:
        f.write(text + "\n\n")


def get_target(now):
    for s in SCHEDULE:
        if parse_iso(s["open"]) <= now < parse_iso(s["close"]):
            return s
    return None


def get_next(now):
    for s in SCHEDULE:
        if parse_iso(s["open"]) > now:
            return parse_iso(s["open"]), f"step {s['step']} {s['side']}"
    return None, "all done"


def cmd_status(state):
    now = now_cet()
    cur = get_target(now)
    nxt_t, nxt_d = get_next(now)
    print(f"now (CET): {now.isoformat(timespec='seconds')}")
    print(f"current_step: {state.get('current_step', 0)} | position_ticket: {state.get('position_ticket')}")
    print(f"last_action: {state.get('last_action_kind')} @ {state.get('last_action_at')}")
    if cur:
        print(f"\nIN-WINDOW: step #{cur['step']} {cur['side']}: {cur['label']}")
        print(f"  open {cur['open']} -> close {cur['close']}")
    else:
        print("\nnot in any window")
    if nxt_t:
        d = nxt_t - now
        print(f"\nNEXT: {nxt_d} at {nxt_t.isoformat(timespec='seconds')} (in {d}, {d.total_seconds()/3600:.1f} h)")
    print(f"\nstate: {STATE_PATH}, history: {len(state.get('history', []))} entries")


def cmd_run(state, dry=False):
    now = now_cet()
    target = get_target(now)
    print(f"[run] now={now.isoformat(timespec='seconds')} target={target['step'] if target else None}")
    try:
        mt5 = connect()
    except Exception as e:
        print(f"[run] connect FAIL: {e}")
        return state
    try:
        pos = find_pos(mt5)
        eurusd = mt5.symbol_info_tick("EURUSD")

        if target is None:
            if pos:
                step_id = state.get("current_step", "?")
                print(f"[run] mimo okno + pozice -> close late (step {step_id})")
                if not dry:
                    res = do_close(mt5, pos)
                    a2 = mt5.account_info()
                    log_csv({"timestamp": now.isoformat(timespec="seconds"), "step": step_id,
                             "action": "CLOSE-LATE", "side": "LONG" if pos.type == 0 else "SHORT",
                             "lots": pos.volume, "ticket": res["ticket"], "price": res["price"],
                             "sl": pos.sl, "tp": pos.tp, "balance": a2.balance, "equity": a2.equity,
                             "position_swap_eur": res["swap_eur"], "position_profit_eur": res["profit_eur"],
                             "eurusd": eurusd.bid, "comment": pos.comment})
                    state["history"].append({"ts": now.isoformat(), "step": step_id, "action": "close-late",
                                             "ticket": res["ticket"], "swap_eur": res["swap_eur"],
                                             "profit_eur": res["profit_eur"], "balance": a2.balance})
                    state["position_ticket"] = None
                    state["last_action_at"] = now.isoformat()
                    state["last_action_kind"] = "close-late"
                    discord("experiments",
                            f"WARN EXP01 step #{step_id} late CLOSE swap={res['swap_eur']:.2f} EUR balance: {a2.balance:.2f}")
            return state

        step_id = target["step"]
        side = target["side"]
        prev = state.get("current_step", 0)

        if prev != step_id:
            if pos:
                print(f"[run] advance {prev}->{step_id}: close prev")
                if not dry:
                    res = do_close(mt5, pos)
                    a2 = mt5.account_info()
                    duration = parse_iso(SCHEDULE[prev - 1]["close"]) - parse_iso(SCHEDULE[prev - 1]["open"])
                    nights = max(1, duration.days)
                    swap_pln = res["swap_eur"] / pos.volume / nights
                    log_csv({"timestamp": now.isoformat(timespec="seconds"), "step": prev,
                             "action": "CLOSE", "side": "LONG" if pos.type == 0 else "SHORT",
                             "lots": pos.volume, "ticket": res["ticket"], "price": res["price"],
                             "sl": pos.sl, "tp": pos.tp, "balance": a2.balance, "equity": a2.equity,
                             "position_swap_eur": res["swap_eur"], "position_profit_eur": res["profit_eur"],
                             "eurusd": eurusd.bid, "comment": pos.comment})
                    ref = -386.93 if pos.type == 0 else -47.82
                    md = (f"### Step #{prev} - CLOSE @ {now.isoformat(timespec='seconds')}\n"
                          f"- ticket {res['ticket']}, vol {pos.volume} {('LONG' if pos.type == 0 else 'SHORT')}\n"
                          f"- duration {duration} ({nights} nights)\n"
                          f"- price {pos.price_open} -> {res['price']}\n"
                          f"- MT5 swap (cumul): {res['swap_eur']:.2f} EUR\n"
                          f"- MT5 profit (M2M): {res['profit_eur']:.2f} EUR\n"
                          f"- swap/lot/night: {swap_pln:.2f} EUR (ref {ref})\n"
                          f"- balance after: {a2.balance:.2f} USD\n")
                    append_md(md)
                    state["history"].append({"ts": now.isoformat(), "step": prev, "action": "close",
                                             "ticket": res["ticket"], "swap_eur": res["swap_eur"],
                                             "profit_eur": res["profit_eur"], "balance": a2.balance})
                    discord("experiments",
                            f"EXP01 step #{prev} CLOSED | swap={res['swap_eur']:.2f} EUR ({swap_pln:.2f}/lot/noc, ref {ref}) | profit={res['profit_eur']:.2f} EUR | balance: {a2.balance:.2f} USD")
                    pos = None

            if parse_iso(target["open"]) <= now:
                print(f"[run] open step {step_id} {side}")
                if not dry:
                    discord("experiments",
                            f"EXP01 step #{step_id} {side} - opening 0.10 lot ({target['label']})")
                    res = do_open(mt5, side, step_id)
                    a2 = mt5.account_info()
                    log_csv({"timestamp": now.isoformat(timespec="seconds"), "step": step_id,
                             "action": "OPEN", "side": side, "lots": LOTS, "ticket": res["ticket"],
                             "price": res["price"], "sl": res["sl"], "tp": res["tp"],
                             "balance": a2.balance, "equity": a2.equity,
                             "position_swap_eur": 0, "position_profit_eur": 0,
                             "eurusd": eurusd.bid, "comment": res["comment"]})
                    md = (f"### Step #{step_id} - OPEN {side} @ {now.isoformat(timespec='seconds')}\n"
                          f"- ticket {res['ticket']}, price {res['price']} (SL {res['sl']:.2f}, TP {res['tp']:.2f})\n"
                          f"- target close {target['close']} | {target['label']}\n"
                          f"- balance: {a2.balance:.2f} USD, EURUSD: {eurusd.bid}\n")
                    append_md(md)
                    state["history"].append({"ts": now.isoformat(), "step": step_id, "action": "open",
                                             "ticket": res["ticket"], "side": side,
                                             "price": res["price"], "balance": a2.balance})
                    state["position_ticket"] = res["ticket"]
                    state["current_step"] = step_id
                    state["last_action_at"] = now.isoformat()
                    state["last_action_kind"] = "open"
                    discord("experiments",
                            f"EXP01 step #{step_id} {side} OPENED | ticket {res['ticket']} @ {res['price']} (SL {res['sl']:.2f} TP {res['tp']:.2f}) | balance: {a2.balance:.2f}")
        else:
            if pos:
                print(f"[run] step {step_id} active, monitor (swap {pos.swap:.2f} EUR)")
                state["last_action_at"] = now.isoformat()
                state["last_action_kind"] = "monitor"
            else:
                print(f"[run] WARN step {step_id} active no position - re-open {side}")
                if not dry:
                    res = do_open(mt5, side, step_id)
                    state["position_ticket"] = res["ticket"]
                    discord("alerts",
                            f"WARN EXP01 step #{step_id} re-opened (state inconsistency) | ticket {res['ticket']}")
    finally:
        mt5.shutdown()
    return state


def cmd_daemon(state, interval=60):
    print(f"[daemon] start, interval={interval}s")
    discord("experiments", "EXP01 daemon STARTED")
    try:
        while True:
            try:
                state = cmd_run(state)
                save_state(state)
            except Exception as e:
                print(f"[daemon] err: {e}")
                traceback.print_exc()
                discord("alerts", f"WARN EXP01 daemon iter err: {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[daemon] stop")
        discord("experiments", "EXP01 daemon STOPPED")


def main():
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    pr = sub.add_parser("run")
    pr.add_argument("--dry-run", action="store_true")
    pd = sub.add_parser("daemon")
    pd.add_argument("--interval", type=int, default=60)
    sub.add_parser("reset")
    a = p.parse_args()
    state = load_state()
    if a.cmd == "status":
        cmd_status(state); return 0
    if a.cmd == "run":
        state = cmd_run(state, a.dry_run); save_state(state); return 0
    if a.cmd == "daemon":
        cmd_daemon(state, a.interval); return 0
    if a.cmd == "reset":
        if STATE_PATH.exists():
            STATE_PATH.unlink()
        print("reset"); return 0


if __name__ == "__main__":
    sys.exit(main())
