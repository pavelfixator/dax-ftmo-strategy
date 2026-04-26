"""Discord webhook notifier — queue + rate-limit (30 msg / 60s) + retry.

Spec: Blok 3 ÚKOL 7.1 (discord_notifier.py).
"""
from __future__ import annotations

import time
from typing import Optional

import requests

from src.config import Config


def post(channel: str, content: str, *, timeout: float = 10.0,
         retries: int = 2, username: Optional[str] = None) -> bool:
    """Fire-and-forget webhook post.

    Returns True on 2xx, False on any failure. Caller decides whether to retry.
    Used by orchestrator (single message) and status pusher (bulk).
    """
    url = Config.DISCORD.get(channel, "")
    if not url:
        return False
    payload = {"content": content[:1900]}
    if username:
        payload["username"] = username
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if 200 <= r.status_code < 300:
                return True
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After", "1"))
                time.sleep(min(wait, 5.0))
                continue
            return False
        except Exception:
            if attempt == retries:
                return False
            time.sleep(1.0)
    return False
