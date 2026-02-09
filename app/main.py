
from __future__ import annotations

import asyncio
import os

import uvloop
from prometheus_client import start_http_server

from app.bot.bot_app import create_bot, create_dispatcher
from app.bot.handlers import router as main_router
from app.config.settings import settings
from app.db.pool import close_pool, init_pool
from app.db.migrations import run_migrations
from app.i18n.localizer import init_locales
from app.utils.ffmpeg import check_ffmpeg
from app.utils.logging import get_logger, init_logging

log = get_logger(__name__)


async def _startup() -> None:
    init_logging(settings.LOG_LEVEL)

    if not check_ffmpeg():
        raise RuntimeError("ffmpeg binary not found in PATH")

    init_locales()

    await init_pool()
    await run_migrations()

    if settings.METRICS_PORT and settings.METRICS_PORT > 0:
        start_http_server(settings.METRICS_PORT)
        log.info("metrics server started on :%d", settings.METRICS_PORT)

    bot = create_bot()
    dp = create_dispatcher()
    dp.include_router(main_router)

    log.info("starting bot polling")
    await dp.start_polling(bot)


def main() -> None:
    uvloop.install()
    try:
        asyncio.run(_startup())
    finally:
        try:
            asyncio.run(close_pool())
        except Exception:
            pass


if __name__ == "__main__":
    main()
