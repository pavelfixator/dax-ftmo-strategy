"""Hourly Discord status push for extended ablation runtime.

Reads experiments/extended_ablation/progress.json (written by
run_extended_ablation.py per cell) and posts compact summary to
#system-health.

Usage:
  python scripts/ablation_status_push.py
  python scripts/ablation_status_push.py --dry-run
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

PROGRESS = ROOT / "experiments" / "extended_ablation" / "progress.json"


def _fmt_eta(seconds: float) -> str:
    if seconds is None or seconds < 0:
        return "?"
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds/60)}m"
    return f"{seconds/3600:.1f}h"


def build_message() -> str:
    now_cet = dt.datetime.now(dt.timezone(dt.timedelta(hours=2)))
    if not PROGRESS.exists():
        return f"**Ablation progress** | {now_cet:%Y-%m-%d %H:%M %Z}\n_progress.json not yet written — ablation has not started._"
    try:
        p = json.loads(PROGRESS.read_text(encoding="utf-8"))
    except Exception as e:
        return f"**Ablation progress** | {now_cet:%Y-%m-%d %H:%M %Z}\nERROR reading progress.json: {e}"
    completed = p.get("completed_cells", 0)
    total = p.get("total_cells", 44)
    pct = p.get("pct", 0.0)
    elapsed = p.get("elapsed_s", 0)
    eta = p.get("eta_s")
    cur = p.get("current_cell", "?")
    status = p.get("status", "?")
    return (
        f"**Ablation progress** | {now_cet:%Y-%m-%d %H:%M %Z}\n"
        f"Status: **{status}** — `{completed}/{total}` cells = **{pct:.1f}%**\n"
        f"Elapsed: {_fmt_eta(elapsed)}, ETA remaining: **{_fmt_eta(eta)}**\n"
        f"Current cell: `{cur}`"
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--channel", default="system_health")
    a = p.parse_args()
    msg = build_message()
    if a.dry_run:
        print(msg)
        return 0
    ok = post(a.channel, msg, username="DAX-Ablation-Status")
    print(f"[ablation_status] channel={a.channel} ok={ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
