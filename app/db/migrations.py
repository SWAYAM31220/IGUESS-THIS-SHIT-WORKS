from __future__ import annotations

import os
from pathlib import Path

from app.utils.logging import get_logger
from app.db.pool import pool

log = get_logger(__name__)


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


async def run_migrations() -> None:
    """Runs SQL migrations in lexical order, idempotently."""
    p = pool()
    async with p.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )

        applied = {
            r["filename"]
            for r in await conn.fetch("SELECT filename FROM schema_migrations")
        }

        files = sorted([f for f in MIGRATIONS_DIR.glob("*.sql")])
        if not files:
            log.warning("no migrations found in %s", MIGRATIONS_DIR)
            return

        for f in files:
            if f.name in applied:
                continue

            sql = f.read_text(encoding="utf-8")
            log.info("applying migration %s", f.name)
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", f.name
                )

        log.info("migrations up to date")
