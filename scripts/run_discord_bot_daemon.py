"""Discord Bot daemon entry point.

Usage:
  python scripts/run_discord_bot_daemon.py

Reads DISCORD_BOT_TOKEN + DISCORD_GUILD_ID from .env. Logs to logs/discord_bot.log.
Graceful shutdown on SIGINT / SIGTERM.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from src.notifier.discord_bot import make_bot, DEFAULT_PATH  # noqa: E402

LOG_PATH = ROOT / "logs" / "discord_bot.log"


def _setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=5_000_000,
                                                backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(fh)
    root.addHandler(sh)


def main() -> int:
    _setup_logging()
    log = logging.getLogger("dax.daemon")
    token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        log.error("DISCORD_BOT_TOKEN not set in .env. Aborting.")
        return 2
    bot = make_bot(signals_path=DEFAULT_PATH)
    log.info("starting Discord Bot listener (signals=%s)", DEFAULT_PATH)
    try:
        bot.run(token, log_handler=None)  # we configured logging ourselves
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — shutting down")
    except Exception as e:
        log.exception("daemon crashed: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    # Graceful shutdown via signal — discord.py handles via run() / .close()
    def _term(signum, frame):  # noqa: ARG001
        sys.exit(0)
    try:
        signal.signal(signal.SIGTERM, _term)
    except (AttributeError, ValueError):
        pass  # Windows compatibility
    sys.exit(main())
