from __future__ import annotations

import logging
import sys


def init_logging(level: str = "INFO") -> None:
    # Simple, production-friendly structured-ish logs
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
