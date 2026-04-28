"""Tests pro src.notifier.discord_bot — mocked listener + reaction logic.

Approach: do not connect to Discord (no real token). Instead instantiate the
bot, manually call on_raw_reaction_add with synthetic payloads, verify state
transitions in signals.jsonl.
"""
from __future__ import annotations

import asyncio
import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.notifier.discord_bot import (
    DAXDiscordBot, GO_EMOJI, SKIP_EMOJI, AUTO_SKIP_TIMEOUT_S,
)
from src.notifier.signal_log import (
    append_signal, find_by_signal_id,
)


@dataclass
class FakePayload:
    message_id: int
    user_id: int
    emoji: str
    guild_id: int = 12345


@pytest.fixture
def bot(tmp_path):
    """Bot wired to a temp signals file. No actual Discord connection."""
    signals = tmp_path / "signals.jsonl"
    b = DAXDiscordBot(signals_path=signals, guild_id=None,
                       auto_skip_timeout_s=2)
    return b, signals


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.asyncio
async def test_go_reaction_marks_confirmed_go(bot):
    b, signals = bot
    append_signal("S-001", 12345, 99, "x", "CALM", "LONG", path=signals)
    await b.on_raw_reaction_add(FakePayload(message_id=12345, user_id=1, emoji=GO_EMOJI))
    r = find_by_signal_id("S-001", path=signals)
    assert r["status"] == "confirmed_go"


@pytest.mark.asyncio
async def test_skip_reaction_marks_confirmed_skip(bot):
    b, signals = bot
    append_signal("S-001", 12345, 99, "x", "CALM", "LONG", path=signals)
    await b.on_raw_reaction_add(FakePayload(message_id=12345, user_id=1, emoji=SKIP_EMOJI))
    r = find_by_signal_id("S-001", path=signals)
    assert r["status"] == "confirmed_skip"


@pytest.mark.asyncio
async def test_unknown_emoji_ignored(bot):
    b, signals = bot
    append_signal("S-001", 12345, 99, "x", "CALM", "LONG", path=signals)
    await b.on_raw_reaction_add(FakePayload(message_id=12345, user_id=1, emoji="🚀"))
    r = find_by_signal_id("S-001", path=signals)
    assert r["status"] == "pending"


@pytest.mark.asyncio
async def test_unknown_message_id_ignored(bot):
    b, signals = bot
    append_signal("S-001", 12345, 99, "x", "CALM", "LONG", path=signals)
    await b.on_raw_reaction_add(FakePayload(message_id=99999, user_id=1, emoji=GO_EMOJI))
    r = find_by_signal_id("S-001", path=signals)
    assert r["status"] == "pending"


@pytest.mark.asyncio
async def test_already_confirmed_signal_not_re_updated(bot):
    """Reaction on signal whose status is no longer pending must be no-op."""
    b, signals = bot
    append_signal("S-001", 12345, 99, "x", "CALM", "LONG", path=signals)
    await b.on_raw_reaction_add(FakePayload(message_id=12345, user_id=1, emoji=GO_EMOJI))
    # Now react again with SKIP — should NOT change status (already go)
    await b.on_raw_reaction_add(FakePayload(message_id=12345, user_id=2, emoji=SKIP_EMOJI))
    r = find_by_signal_id("S-001", path=signals)
    assert r["status"] == "confirmed_go"


@pytest.mark.asyncio
async def test_guild_filter_blocks_other_guild(tmp_path):
    signals = tmp_path / "signals.jsonl"
    b = DAXDiscordBot(signals_path=signals, guild_id=42, auto_skip_timeout_s=10)
    append_signal("S-001", 12345, 99, "x", "CALM", "LONG", path=signals)
    await b.on_raw_reaction_add(FakePayload(message_id=12345, user_id=1,
                                              emoji=GO_EMOJI, guild_id=999))
    r = find_by_signal_id("S-001", path=signals)
    assert r["status"] == "pending"  # not affected — wrong guild


def test_auto_skip_timeout_constant():
    assert AUTO_SKIP_TIMEOUT_S == 180


def test_emoji_constants():
    assert GO_EMOJI == "✅"
    assert SKIP_EMOJI == "❌"


def test_make_bot_reads_env_guild(monkeypatch, tmp_path):
    from src.notifier.discord_bot import make_bot
    monkeypatch.setenv("DISCORD_GUILD_ID", "9876543210")
    b = make_bot(signals_path=tmp_path / "s.jsonl")
    assert b.guild_id == 9876543210


def test_make_bot_no_guild_when_unset(monkeypatch, tmp_path):
    from src.notifier.discord_bot import make_bot
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    b = make_bot(signals_path=tmp_path / "s.jsonl")
    assert b.guild_id is None
