"""Tests pro src.notifier.signal_log."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from src.notifier.signal_log import (
    append_signal, update_status, find_by_message_id, find_by_signal_id,
    get_pending_signals, get_pending_older_than, VALID_STATUSES,
)


@pytest.fixture
def tmp_log(tmp_path) -> Path:
    return tmp_path / "signals.jsonl"


def test_append_creates_file_and_returns_row(tmp_log):
    row = append_signal("S-001", 12345, 67890, "orb_dax_v331", "CALM", "LONG",
                         entry=24100, sl=24050, tp=24200, lots=0.1, path=tmp_log)
    assert tmp_log.exists()
    assert row["status"] == "pending"
    assert row["message_id"] == 12345
    assert row["entry"] == 24100


def test_jsonl_format(tmp_log):
    append_signal("S-001", 1, 2, "x", "CALM", "LONG", path=tmp_log)
    append_signal("S-002", 3, 4, "x", "TREND", "SHORT", path=tmp_log)
    lines = tmp_log.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # parses


def test_update_status_pending_to_go(tmp_log):
    append_signal("S-001", 1, 2, "x", "CALM", "LONG", path=tmp_log)
    assert update_status("S-001", "confirmed_go", path=tmp_log)
    row = find_by_signal_id("S-001", path=tmp_log)
    assert row["status"] == "confirmed_go"
    assert "status_updated_at" in row


def test_update_status_invalid_raises(tmp_log):
    append_signal("S-001", 1, 2, "x", "CALM", "LONG", path=tmp_log)
    with pytest.raises(ValueError):
        update_status("S-001", "garbage", path=tmp_log)


def test_update_unknown_id_returns_false(tmp_log):
    assert update_status("does-not-exist", "confirmed_go", path=tmp_log) is False


def test_find_by_message_id(tmp_log):
    append_signal("S-001", 12345, 67890, "x", "CALM", "LONG", path=tmp_log)
    append_signal("S-002", 99999, 67890, "x", "TREND", "SHORT", path=tmp_log)
    r = find_by_message_id(12345, path=tmp_log)
    assert r is not None and r["signal_id"] == "S-001"
    assert find_by_message_id(404, path=tmp_log) is None


def test_find_by_message_id_returns_most_recent(tmp_log):
    """If duplicate message_ids exist (Discord re-use), return latest."""
    append_signal("S-001", 12345, 1, "x", "CALM", "LONG", path=tmp_log)
    append_signal("S-002", 12345, 1, "x", "CALM", "SHORT", path=tmp_log)
    r = find_by_message_id(12345, path=tmp_log)
    assert r["signal_id"] == "S-002"


def test_get_pending_signals(tmp_log):
    append_signal("S-001", 1, 1, "x", "CALM", "LONG", path=tmp_log)
    append_signal("S-002", 2, 1, "x", "CALM", "LONG", path=tmp_log)
    update_status("S-002", "confirmed_go", path=tmp_log)
    pending = get_pending_signals(path=tmp_log)
    assert len(pending) == 1
    assert pending[0]["signal_id"] == "S-001"


def test_valid_statuses_set():
    assert VALID_STATUSES == {"pending", "confirmed_go", "confirmed_skip", "timeout"}


def test_get_pending_older_than(tmp_log):
    """Manually craft an old timestamp."""
    old_ts = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
              ).strftime("%Y-%m-%dT%H:%M:%SZ")
    append_signal("S-OLD", 1, 1, "x", "CALM", "LONG",
                   timestamp=old_ts, path=tmp_log)
    append_signal("S-NEW", 2, 1, "x", "CALM", "LONG", path=tmp_log)
    older = get_pending_older_than(seconds=180, path=tmp_log)  # 3 min
    assert len(older) == 1
    assert older[0]["signal_id"] == "S-OLD"


def test_atomic_write_does_not_corrupt(tmp_log):
    """Multiple updates don't interleave/corrupt the file."""
    for i in range(50):
        append_signal(f"S-{i}", i, 1, "x", "CALM", "LONG", path=tmp_log)
    update_status("S-25", "confirmed_skip", path=tmp_log)
    rows = tmp_log.read_text(encoding="utf-8").strip().split("\n")
    assert len(rows) == 50
    parsed = [json.loads(r) for r in rows]
    assert sum(1 for p in parsed if p["status"] == "confirmed_skip") == 1
