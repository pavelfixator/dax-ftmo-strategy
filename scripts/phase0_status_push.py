"""Hourly Discord status push for Phase 0 backtest runtime.

Reads experiments/phase0/progress.json (written by run_phase0_backtest.py)
and posts compact summary to #system-health.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.notifier.discord_notifier import post  # noqa: E402

PROGRESS = ROOT / "experiments" / "phase0" / "progress.json"


def _fmt(seconds):
    if seconds is None or seconds < 0:
        return "?"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds/60)}m"
    return f"{seconds/3600:.1f}h"


def build_message():
    now_cet = dt.datetime.now(dt.timezone(dt.timedelta(hours=2)))
    if not PROGRESS.exists():
        return f"Phase 0 backtest progress | {now_cet:%Y-%m-%d %H:%M %Z}\nprogress.json not yet written"
    try:
        p = json.loads(PROGRESS.read_text(encoding="utf-8"))
    except Exception as e:
        return f"Phase 0 backtest progress | {now_cet:%Y-%m-%d %H:%M %Z}\nERROR reading progress: {e}"
    return (
        f"Phase 0 backtest progress | {now_cet:%Y-%m-%d %H:%M %Z}\n"
        f"Status: {p.get('status','?')} | stage: {p.get('stage','?')} | pct: {p.get('pct',0):.1f}%\n"
        f"Note: {p.get('note','')}\n"
        f"Elapsed: {_fmt(p.get('elapsed_s',0))}"
    )


def main():
    pp = argparse.ArgumentParser()
    pp.add_argument("--dry-run", action="store_true")
    pp.add_argument("--channel", default="system_health")
    a = pp.parse_args()
    msg = build_message()
    if a.dry_run:
        print(msg)
        return 0
    ok = post(a.channel, msg, username="DAX-Phase0-Status")
    print(f"[phase0_status] ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
