from __future__ import annotations

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB
    DB_HOST: str = "db"
    DB_PORT: int = 5432
    DB_NAME: str = "govd"
    DB_USER: str = "govd"
    DB_PASSWORD: str = ""

    # Bot
    BOT_TOKEN: str = Field(...)
    BOT_API_URL: str = "https://api.telegram.org"  # kept for parity; aiogram uses base api server
    CONCURRENT_UPDATES: int = 32

    # Runtime
    DOWNLOADS_DIR: str = "downloads"
    PROXY: Optional[str] = None
    MAX_DURATION: int = 60 * 60  # seconds
    MAX_FILE_SIZE: int = 1000 * 1024 * 1024  # 1GB
    REPO_URL: str = "https://github.com/govdbot/govd"

    # Observability
    PROFILER_PORT: int = 0
    METRICS_PORT: int = 0
    LOG_LEVEL: str = "INFO"

    # Access
    WHITELIST: List[int] = Field(default_factory=list)
    ADMINS: List[int] = Field(default_factory=list)

    # Features
    CACHING: bool = True

    CAPTIONS_HEADER: str = "<a href='{{url}}'>source</a> - @{{username}}"
    CAPTIONS_DESCRIPTION: str = "<blockquote expandable>{{text}}</blockquote>"

    DEFAULT_ENABLE_CAPTIONS: bool = True
    DEFAULT_ENABLE_SILENT: bool = False
    DEFAULT_ENABLE_NSFW: bool = False
    DEFAULT_MEDIA_ALBUM_LIMIT: int = 10
    DEFAULT_LANGUAGE: str = "en"
    DEFAULT_DELETE_LINKS: bool = False

    AUTOMATIC_LANGUAGE_DETECTION: bool = True

    @property
    def db_dsn(self) -> str:
        # asyncpg DSN
        pwd = self.DB_PASSWORD.replace("@", "%40")
        return f"postgresql://{self.DB_USER}:{pwd}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"


settings = Settings()
