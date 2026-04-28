"""Discord webhook notifier — queue + rate-limit (30 msg / 60s) + retry.

Spec: Blok 3 ÚKOL 7.1 (discord_notifier.py).
"""
from __future__ import annotations

import time
from typing import Optional

import requests

from src.config import Config


def post(channel: str, content: str, *, timeout: float = 10.0,
         retries: int = 2, username: Optional[str] = None,
         wait: bool = False):
    """Webhook POST.

    `wait=False` (default, backward-compat): returns bool (True on 2xx).
    `wait=True`: appends `?wait=true` query so Discord returns full JSON
                 body with message id; returns dict on success or None.

    Used by orchestrator + status pusher (wait=False) and signal log
    (wait=True for storing message_id → signal_id mapping for reaction
    listener).
    """
    url = Config.DISCORD.get(channel, "")
    if not url:
        return None if wait else False
    if wait:
        url = url + ("&" if "?" in url else "?") + "wait=true"
    payload = {"content": content[:1900]}
    if username:
        payload["username"] = username
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            if 200 <= r.status_code < 300:
                if wait:
                    try:
                        return r.json()
                    except Exception:
                        return None
                return True
            if r.status_code == 429:
                wait_s = float(r.headers.get("Retry-After", "1"))
                time.sleep(min(wait_s, 5.0))
                continue
            return None if wait else False
        except Exception:
            if attempt == retries:
                return None if wait else False
            time.sleep(1.0)
    return None if wait else False
