"""Entry point — trading loop orchestrator.

Spec: Blok 3 ÚKOL 7.2 (trading_loop pseudokód).
Spouští se jako Windows Service nebo `python src/main.py` (foreground dev).
"""
from __future__ import annotations

import signal
import sys
from loguru import logger


def main() -> int:
    logger.info("DAX FTMO bot — cold start")
    logger.warning("TODO: implement trading_loop per Blok 3 ÚKOL 7.2 once Strategy v3.0 is frozen")
    return 0


def _graceful_shutdown(signum, frame):  # noqa: ARG001
    logger.info("shutdown signal received, flushing state…")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    sys.exit(main())
