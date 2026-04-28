"""End-to-end test of Discord Bot GO/SKIP workflow.

REQUIRES:
  1. DISCORD_BOT_TOKEN set in .env
  2. discord_bot daemon running:  python scripts/run_discord_bot_daemon.py
     (Pavel spustí v separátním okně, bot must show "Bot online")

WORKFLOW:
  Step 1 — POST signal #1 to #signaly (wait=true → store message_id)
  Step 2 — Wait 60s for human to react ✅ in Discord
  Step 3 — Confirm: signals.jsonl status=confirmed_go (bot did its job)
  Step 4 — POST signal #2
  Step 5 — Wait 60s for ✅
  Step 6 — Confirm status=confirmed_go for #2

If both pass → Phase 1 GO/SKIP workflow READY.

Usage:
  python scripts/test_discord_bot.py
  python scripts/test_discord_bot.py --timeout 30   (shorter wait per signal)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.notifier.discord_notifier import post  # noqa: E402
from src.notifier.signal_log import (  # noqa: E402
    DEFAULT_PATH, append_signal, find_by_signal_id,
)


SIGNAL_TEMPLATE = (
    "**[TEST MODE] SIGNAL #{n}** | DAX-FTMO Phase 1 dry run\n\n"
    "Setup: ORB-DAX / CALM regime / drop_F3\n"
    "Direction: LONG @ 24 105.5\n"
    "SL: 24 067.0 (-38.5 pts) | TP: 24 181.5 (+76.0 pts)\n"
    "RRR: 1:2 | Filters: F1+F2+F4 (3/3 met) | Confidence: 75%\n"
    "Lots: 0.10 (TEST sizing)\n\n"
    "{prompt}\n\n"
    "_TEST mode: zadny realny trade nebude proveden._"
)


def post_signal(n: int, prompt: str = "Reaguj ✅ approve / ❌ skip") -> dict | None:
    msg = SIGNAL_TEMPLATE.format(n=n, prompt=prompt)
    resp = post("signaly", msg, username=f"DAX-Test-Signal", wait=True)
    if not resp:
        return None
    return resp


def wait_for_status(signal_id: str, timeout_s: int) -> str:
    deadline = time.time() + timeout_s
    last = "pending"
    while time.time() < deadline:
        row = find_by_signal_id(signal_id)
        if row:
            last = row.get("status", "pending")
            if last != "pending":
                return last
        time.sleep(1)
    return last


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--timeout", type=int, default=60,
                   help="seconds to wait per signal for reaction (default 60)")
    a = p.parse_args()

    print(f"[test] DEFAULT_PATH = {DEFAULT_PATH}")
    print(f"[test] timeout per signal: {a.timeout}s")
    print()

    # --- Signal #1 ---
    print("[test] STEP 1: POST signal #1 to #signaly (wait=true)")
    resp = post_signal(1)
    if not resp:
        print("[test] FAIL — webhook POST returned None (check #signaly webhook URL)")
        return 1
    msg_id = int(resp.get("id", 0))
    chan_id = int(resp.get("channel_id", 0))
    sig_id = f"TEST-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')}-1"
    append_signal(sig_id, msg_id, chan_id, "test_bot", "CALM", "LONG",
                   entry=24105.5, sl=24067.0, tp=24181.5, lots=0.10)
    print(f"[test] signal #1 posted: msg_id={msg_id}, signal_id={sig_id}")
    print(f"[test] STEP 2: waiting up to {a.timeout}s for ✅ reaction...")
    s1 = wait_for_status(sig_id, a.timeout)
    if s1 != "confirmed_go":
        print(f"[test] FAIL signal #1 — final status: {s1}")
        print("       Check: 1) bot daemon running?")
        print("              2) Pavel reacted ✅ in #signaly?")
        return 2
    print(f"[test] PASS signal #1 → status={s1}")
    print()

    # --- Signal #2 ---
    print("[test] STEP 3: POST signal #2 to #signaly")
    resp = post_signal(2)
    if not resp:
        print("[test] FAIL signal #2 webhook POST")
        return 3
    msg_id2 = int(resp.get("id", 0))
    sig_id2 = f"TEST-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')}-2"
    append_signal(sig_id2, msg_id2, chan_id, "test_bot", "CALM", "LONG")
    print(f"[test] signal #2 posted: msg_id={msg_id2}, signal_id={sig_id2}")
    print(f"[test] STEP 4: waiting up to {a.timeout}s for ✅ reaction...")
    s2 = wait_for_status(sig_id2, a.timeout)
    if s2 != "confirmed_go":
        print(f"[test] FAIL signal #2 — final status: {s2}")
        return 4
    print(f"[test] PASS signal #2 → status={s2}")
    print()
    print("[test] ============================================================")
    print("[test] PHASE 1 GO/SKIP WORKFLOW READY")
    print("[test] ============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
