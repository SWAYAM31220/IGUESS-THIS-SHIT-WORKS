from __future__ import annotations

import asyncpg

from app.config.settings import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Create a global asyncpg pool."""
    global _pool
    if _pool is not None:
        return _pool

    log.info("DB: connecting")
    _pool = await asyncpg.create_pool(
        dsn=settings.db_dsn,
        min_size=1,
        max_size=max(2, settings.CONCURRENT_UPDATES),
        command_timeout=60,
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
