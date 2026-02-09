from __future__ import annotations

import os
import asyncpg

from app.utils.logging import get_logger

log = get_logger(__name__)

_pool: asyncpg.Pool | None = None


def _dsn() -> str:
    # Render sets DATABASE_URL as an environment variable
    dsn = os.getenv("DATABASE_URL")
    if not dsn or not dsn.strip():
        raise RuntimeError("Missing required env var: DATABASE_URL")
    return dsn.strip()


async def init_pool() -> asyncpg.Pool:
    """Create and return a global asyncpg pool."""
    global _pool

    if _pool is not None:
        return _pool

    log.info("DB: connecting")

    _pool = await asyncpg.create_pool(
        dsn=_dsn(),
        ssl=False,  # REQUIRED for Render internal Postgres
    )

    log.info("DB: pool ready")
    return _pool


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool is not initialized")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("DB: pool closed")
