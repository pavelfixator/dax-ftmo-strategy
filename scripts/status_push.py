"""2-hodinový status snapshot do Discord #alerts.

Sbírá lehký health snapshot (žádné MT5 volání, žádné CDP) a postuje do #alerts.
Cíl: víkendová viditelnost — Pavel vidí každé 2h, že robot framework + data
pipeline + Exp01 orchestrator žijou.

Spouští se z Windows Scheduled Task `DAX-Status-Push-2h` (každé 2h).
Manual test: `python scripts/status_push.py`
Dry run (stdout, žádný HTTP):  `python scripts/status_push.py --dry-run`
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import Config  # noqa: E402
from src.notifier import discord_notifier  # noqa: E402

CET = dt.timezone(dt.timedelta(hours=2))
EXP01_STATE = ROOT / "data" / "exp01_state.json"
EXP01_CSV = Path(r"C:/Users/AOS Server/trading-lab-DAX/DAX-FTMO-Strategy/03-Backtest/Experiments/exp01_swap_data.csv")
DUKASCOPY_CACHE = ROOT / "data" / "dukascopy_cache"


def _git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--pretty=%h %s"],
            stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
        return out or "n/a"
    except Exception:
        return "n/a"


def _scheduled_task_state(name: str) -> str:
    try:
        out = subprocess.check_output(
            ["schtasks", "/Query", "/TN", name, "/FO", "LIST"],
            stderr=subprocess.DEVNULL, text=True, timeout=5)
        for line in out.splitlines():
            if line.lower().startswith("status"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "?"


def _exp01_summary() -> dict:
    if not EXP01_STATE.exists():
        return {"step": 0, "ticket": None, "history": 0, "last_action": None}
    s = json.loads(EXP01_STATE.read_text(encoding="utf-8"))
    return {
        "step": s.get("current_step", 0),
        "ticket": s.get("position_ticket"),
        "history": len(s.get("history", [])),
        "last_action": s.get("last_action_kind"),
        "last_at": s.get("last_action_at"),
    }


def _csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as f:
            return max(0, sum(1 for _ in f) - 1)  # minus header
    except Exception:
        return -1


def _cache_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for r, _, files in os.walk(path):
        for fn in files:
            try:
                total += (Path(r) / fn).stat().st_size
            except OSError:
                pass
    return total / (1024 * 1024)


def build_message() -> str:
    now_cet = dt.datetime.now(tz=CET)
    exp = _exp01_summary()
    csv_rows = _csv_rows(EXP01_CSV)
    cache_mb = _cache_size_mb(DUKASCOPY_CACHE)
    head = _git_head()
    task_exp01 = _scheduled_task_state("DAX-FTMO-Exp01")
    task_status = _scheduled_task_state("DAX-Status-Push-2h")

    lines = [
        f"**DAX bot status** | {now_cet:%Y-%m-%d %H:%M %Z}",
        f"host: `{platform.node()}` | git HEAD: `{head}`",
        f"sched DAX-FTMO-Exp01: **{task_exp01}** | DAX-Status-Push-2h: **{task_status}**",
        f"Exp01 state: step=**{exp['step']}** ticket=`{exp['ticket']}` "
        f"history={exp['history']} last={exp['last_action']}@{exp['last_at']}",
        f"Exp01 CSV rows: **{csv_rows}** | Dukascopy cache: **{cache_mb:.1f} MB**",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="print to stdout, do not post")
    p.add_argument("--channel", default="alerts",
                   help="Discord channel key (default: alerts)")
    a = p.parse_args()

    msg = build_message()
    if a.dry_run:
        print(msg)
        return 0

    ok = discord_notifier.post(a.channel, msg, username="DAX-Status")
    print(f"[status_push] channel={a.channel} ok={ok} bytes={len(msg)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
