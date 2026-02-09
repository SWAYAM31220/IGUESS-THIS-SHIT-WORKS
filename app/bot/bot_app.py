
from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config.settings import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


def create_bot() -> Bot:
    session = AiohttpSession(proxy=settings.PROXY) if settings.PROXY else AiohttpSession()
    # aiogram v3 uses base_url param for Bot if you need self-hosted API.
    # settings.BOT_API_URL is kept for parity; if you run a self-hosted Bot API,
    # set BOT_API_URL and we'll pass it as `server`.
    bot = Bot(
        token=settings.BOT_TOKEN,
        parse_mode=ParseMode.HTML,
        session=session,
    )
    return bot


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    return dp
