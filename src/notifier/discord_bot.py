"""Discord Bot listener for Phase 1 GO/SKIP workflow.

Subclasses discord.Client. Listens for reactions on webhook-posted signal
messages. ✅ → confirmed_go, ❌ → confirmed_skip. Also runs background
auto-skip task for pending signals older than 3 minutes.

Required Discord intents (configure in Bot settings + Privileged Intents):
  default + members + message_content + reactions

Required env:
  DISCORD_BOT_TOKEN  — bot token from Discord Developer Portal
  DISCORD_GUILD_ID   — optional, if set, ignore messages from other guilds

Usage (daemon entry: scripts/run_discord_bot_daemon.py):
  bot = DAXDiscordBot(signals_path)
  bot.run(token)
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import os
from pathlib import Path
from typing import Optional

import discord

from src.notifier.signal_log import (
    DEFAULT_PATH, find_by_message_id, update_status,
    get_pending_older_than,
)

log = logging.getLogger("dax.discord_bot")

GO_EMOJI = "✅"
SKIP_EMOJI = "❌"
AUTO_SKIP_TIMEOUT_S = 180  # 3 min per Pavel spec
AUTO_SKIP_POLL_S = 30      # poll every 30 s


class DAXDiscordBot(discord.Client):
    def __init__(self, signals_path: Path = DEFAULT_PATH,
                 guild_id: Optional[int] = None,
                 auto_skip_timeout_s: int = AUTO_SKIP_TIMEOUT_S):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.reactions = True
        super().__init__(intents=intents)
        self.signals_path = Path(signals_path)
        self.guild_id = guild_id
        self.auto_skip_timeout_s = auto_skip_timeout_s
        self._auto_skip_task: Optional[asyncio.Task] = None

    async def on_ready(self) -> None:
        log.info("Bot online: user=%s id=%s", self.user, self.user.id if self.user else None)
        if self._auto_skip_task is None or self._auto_skip_task.done():
            self._auto_skip_task = asyncio.create_task(self._auto_skip_loop())

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Use raw reaction for webhook messages (no cached message)."""
        if self.guild_id and payload.guild_id and payload.guild_id != self.guild_id:
            return
        if self.user and payload.user_id == self.user.id:
            return
        emoji = str(payload.emoji)
        signal = find_by_message_id(payload.message_id, path=self.signals_path)
        if not signal:
            return
        if signal.get("status") != "pending":
            log.info("ignoring reaction on non-pending signal %s status=%s",
                     signal["signal_id"], signal["status"])
            return
        new_status = None
        if emoji == GO_EMOJI:
            new_status = "confirmed_go"
        elif emoji == SKIP_EMOJI:
            new_status = "confirmed_skip"
        else:
            log.info("ignoring non-GO/SKIP emoji %r on signal %s",
                     emoji, signal["signal_id"])
            return
        if update_status(signal["signal_id"], new_status, path=self.signals_path):
            log.info("signal %s updated -> %s by user %s",
                     signal["signal_id"], new_status, payload.user_id)

    async def _auto_skip_loop(self) -> None:
        """Background task: every poll_s, mark expired pending signals as timeout."""
        while not self.is_closed():
            try:
                expired = get_pending_older_than(self.auto_skip_timeout_s,
                                                  path=self.signals_path)
                for s in expired:
                    if update_status(s["signal_id"], "timeout",
                                     path=self.signals_path):
                        log.info("signal %s auto-skipped (timeout %ds)",
                                 s["signal_id"], self.auto_skip_timeout_s)
            except Exception as e:
                log.warning("auto-skip loop error: %s", e)
            await asyncio.sleep(AUTO_SKIP_POLL_S)


def make_bot(signals_path: Path = DEFAULT_PATH,
             guild_id_env: str = "DISCORD_GUILD_ID",
             auto_skip_timeout_s: int = AUTO_SKIP_TIMEOUT_S) -> DAXDiscordBot:
    gid_raw = os.getenv(guild_id_env, "").strip()
    gid = int(gid_raw) if gid_raw else None
    return DAXDiscordBot(signals_path=signals_path, guild_id=gid,
                         auto_skip_timeout_s=auto_skip_timeout_s)
