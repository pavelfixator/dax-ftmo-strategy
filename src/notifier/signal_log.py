"""Signal log persistence for Phase 1 GO/SKIP workflow.

Append-only JSONL at experiments/signals.jsonl (configurable). Each row:
  {
    "signal_id": "DAX-2026-04-28-093000-001",
    "message_id": 1234567890,            # Discord webhook return
    "channel_id": 1497368357677305946,   # Discord channel
    "timestamp": "2026-04-28T09:30:00Z",
    "status": "pending",                 # pending|confirmed_go|confirmed_skip|timeout
    "setup": "orb_dax_v331",
    "regime": "CALM",
    "action": "LONG",                    # LONG|SHORT
    "entry": 24105.5, "sl": 24067.0, "tp": 24181.5, "lots": 0.10,
  }

Updates rewrite the file (atomic via tempfile + replace).
File lock via fcntl/msvcrt (best-effort). For Phase 0 single-process tests
the lock is a no-op; Phase 1+ daemon will run alone.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "experiments" / "signals.jsonl"

VALID_STATUSES = {"pending", "confirmed_go", "confirmed_skip", "timeout"}


def _now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_signal(
    signal_id: str,
    message_id: int,
    channel_id: int,
    setup: str,
    regime: str,
    action: str,
    *,
    entry: float | None = None,
    sl: float | None = None,
    tp: float | None = None,
    lots: float | None = None,
    timestamp: str | None = None,
    path: Path = DEFAULT_PATH,
) -> dict:
    """Append a new pending signal. Returns the row dict."""
    row = {
        "signal_id": signal_id,
        "message_id": int(message_id) if message_id is not None else None,
        "channel_id": int(channel_id) if channel_id is not None else None,
        "timestamp": timestamp or _now_utc_iso(),
        "status": "pending",
        "setup": setup,
        "regime": regime,
        "action": action,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "lots": lots,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _read_all(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _write_all(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".signals_tmp_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update_status(signal_id: str, new_status: str, *,
                   path: Path = DEFAULT_PATH) -> bool:
    """Set status of a signal_id. Returns True if found+updated."""
    if new_status not in VALID_STATUSES:
        raise ValueError(f"invalid status {new_status!r}; expected one of {VALID_STATUSES}")
    rows = _read_all(path)
    found = False
    for r in rows:
        if r.get("signal_id") == signal_id:
            r["status"] = new_status
            r["status_updated_at"] = _now_utc_iso()
            found = True
            break
    if found:
        _write_all(rows, path)
    return found


def find_by_message_id(message_id: int, *,
                        path: Path = DEFAULT_PATH) -> Optional[dict]:
    """Return the (most recent) signal row matching message_id, or None."""
    rows = _read_all(path)
    for r in reversed(rows):
        if r.get("message_id") == int(message_id):
            return r
    return None


def find_by_signal_id(signal_id: str, *,
                       path: Path = DEFAULT_PATH) -> Optional[dict]:
    rows = _read_all(path)
    for r in reversed(rows):
        if r.get("signal_id") == signal_id:
            return r
    return None


def get_pending_signals(*, path: Path = DEFAULT_PATH) -> list[dict]:
    return [r for r in _read_all(path) if r.get("status") == "pending"]


def get_pending_older_than(seconds: int, *,
                            path: Path = DEFAULT_PATH) -> list[dict]:
    """Return pending signals older than `seconds`. Used for auto-skip timeout."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=seconds)
    out = []
    for r in get_pending_signals(path=path):
        try:
            ts = dt.datetime.strptime(r["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
            if ts <= cutoff:
                out.append(r)
        except Exception:
            continue
    return out
