from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import asyncpg

from app.config.settings import settings
from app.db.pool import pool


@dataclass
class ChatRow:
    chat_id: int
    type: str
    nsfw: bool
    media_album_limit: int
    captions: bool
    silent: bool
    language: str
    disabled_extractors: List[str]
    delete_links: bool


async def get_or_create_chat(chat_id: int, chat_type: str) -> ChatRow:
    p = pool()
    async with p.acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH upsert_chat AS (
                INSERT INTO chat (chat_id, type)
                VALUES ($1, $2)
                ON CONFLICT (chat_id) DO NOTHING
                RETURNING *
            ),
            upsert_settings AS (
                INSERT INTO settings (chat_id, language, captions, silent, nsfw, media_album_limit, delete_links)
                VALUES ($1, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (chat_id) DO UPDATE SET
                    language = CASE
                        WHEN settings.language = 'XX' THEN EXCLUDED.language
                        ELSE settings.language
                    END
                RETURNING *
            ),
            final_chat AS (
                SELECT * FROM upsert_chat
                UNION ALL
                SELECT * FROM chat WHERE chat_id = $1 AND NOT EXISTS (SELECT 1 FROM upsert_chat)
            ),
            final_settings AS (
                SELECT * FROM upsert_settings
            )
            SELECT
                c.chat_id,
                c.type,
                s.nsfw,
                s.media_album_limit,
                s.captions,
                s.silent,
                s.language,
                s.disabled_extractors,
                s.delete_links
            FROM final_chat c
            JOIN final_settings s ON s.chat_id = c.chat_id;
            """,
            chat_id,
            chat_type,
            settings.DEFAULT_LANGUAGE,
            settings.DEFAULT_ENABLE_CAPTIONS,
            settings.DEFAULT_ENABLE_SILENT,
            settings.DEFAULT_ENABLE_NSFW,
            settings.DEFAULT_MEDIA_ALBUM_LIMIT,
            settings.DEFAULT_DELETE_LINKS,
        )

    return ChatRow(
        chat_id=row["chat_id"],
        type=row["type"],
        nsfw=row["nsfw"],
        media_album_limit=row["media_album_limit"],
        captions=row["captions"],
        silent=row["silent"],
        language=row["language"],
        disabled_extractors=list(row["disabled_extractors"] or []),
        delete_links=row["delete_links"],
    )


async def set_chat_language(chat_id: int, language: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE settings SET language = $1, updated_at = CURRENT_TIMESTAMP WHERE chat_id = $2",
            language,
            chat_id,
        )


async def toggle_chat_captions(chat_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE settings SET captions = NOT captions, updated_at = CURRENT_TIMESTAMP WHERE chat_id = $1",
            chat_id,
        )


async def toggle_chat_nsfw(chat_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE settings SET nsfw = NOT nsfw, updated_at = CURRENT_TIMESTAMP WHERE chat_id = $1",
            chat_id,
        )


async def toggle_chat_silent(chat_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE settings SET silent = NOT silent, updated_at = CURRENT_TIMESTAMP WHERE chat_id = $1",
            chat_id,
        )


async def toggle_chat_delete_links(chat_id: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE settings SET delete_links = NOT delete_links, updated_at = CURRENT_TIMESTAMP WHERE chat_id = $1",
            chat_id,
        )


async def set_chat_media_album_limit(chat_id: int, limit: int) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE settings SET media_album_limit = $1, updated_at = CURRENT_TIMESTAMP WHERE chat_id = $2",
            limit,
            chat_id,
        )


async def add_disabled_extractor(chat_id: int, extractor_id: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """
            UPDATE settings
            SET disabled_extractors = array_append(disabled_extractors, $1), updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = $2 AND NOT ($1 = ANY(disabled_extractors));
            """,
            extractor_id,
            chat_id,
        )


async def remove_disabled_extractor(chat_id: int, extractor_id: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """
            UPDATE settings
            SET disabled_extractors = array_remove(disabled_extractors, $1), updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = $2;
            """,
            extractor_id,
            chat_id,
        )


async def log_error(error_id: str, message: str) -> None:
    async with pool().acquire() as conn:
        await conn.execute(
            """
            INSERT INTO errors (id, message)
            VALUES ($1, $2)
            ON CONFLICT (id) DO UPDATE
            SET occurrences = errors.occurrences + 1,
                last_seen = NOW();
            """,
            error_id,
            message,
        )


async def get_error_by_id(error_id: str) -> Optional[str]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT message FROM errors WHERE id = $1",
            error_id,
        )
    return None if row is None else row["message"]


async def get_stats(days: int = 7) -> Dict[str, Any]:
    since_date = datetime.now(tz=timezone.utc) - timedelta(days=days)
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            WITH private_chats AS (
                SELECT COUNT(*) as total, s.language, COUNT(*) as count_by_lang
                FROM chat c
                JOIN settings s ON c.chat_id = s.chat_id
                WHERE c.type = 'private'
                    AND c.created_at >= $1::TIMESTAMPTZ
                GROUP BY s.language
            ),
            group_chats AS (
                SELECT COUNT(*) as total, s.language, COUNT(*) as count_by_lang
                FROM chat c
                JOIN settings s ON c.chat_id = s.chat_id
                WHERE c.type = 'group'
                    AND c.created_at >= $1::TIMESTAMPTZ
                GROUP BY s.language
            ),
            downloads_stats AS (
                SELECT COUNT(*) as total_downloads, COALESCE(SUM(mf.file_size), 0) as total_size
                FROM media m
                JOIN media_item mi ON mi.media_id = m.id
                JOIN media_format mf ON mf.item_id = mi.id
                WHERE m.created_at >= $1::TIMESTAMPTZ
            )
            SELECT
                COALESCE((SELECT SUM(total) FROM private_chats), 0)::BIGINT as total_private_chats,
                COALESCE((SELECT jsonb_object_agg(language, count_by_lang) FROM private_chats), '{}'::jsonb) as private_chats_by_language,
                COALESCE((SELECT SUM(total) FROM group_chats), 0)::BIGINT as total_group_chats,
                COALESCE((SELECT jsonb_object_agg(language, count_by_lang) FROM group_chats), '{}'::jsonb) as group_chats_by_language,
                COALESCE((SELECT total_downloads FROM downloads_stats), 0)::BIGINT as total_downloads,
                COALESCE((SELECT total_size FROM downloads_stats), 0)::BIGINT as total_downloads_size;
            """,
            since_date,
        )

    return dict(row)

async def insert_download(
    *,
    content_id: str,
    content_url: str,
    extractor_id: str,
    chat_id: int,
    media_type: str,
    audio_codec: str,
    video_codec: str,
    file_size: int,
    duration: int,
    width: int,
    height: int,
    bitrate: int,
) -> None:
    """Persist a single downloaded format for stats/history.

    This mirrors govd's media/media_item/media_format tables, but stores only
    the single format actually downloaded.
    """
    async with pool().acquire() as conn:
        async with conn.transaction():
            media_id_row = await conn.fetchrow(
                """
                INSERT INTO media (content_id, content_url, extractor_id, chat_id)
                VALUES ($1, $2, $3, $4)
                RETURNING id;
                """,
                content_id,
                content_url,
                extractor_id,
                chat_id,
            )
            media_id = media_id_row["id"]

            item_id_row = await conn.fetchrow(
                """
                INSERT INTO media_item (media_id)
                VALUES ($1)
                RETURNING id;
                """,
                media_id,
            )
            item_id = item_id_row["id"]

            await conn.execute(
                """
                INSERT INTO media_format (
                    item_id, format_id, type, audio_codec, video_codec,
                    file_size, duration, width, height, bitrate
                )
                VALUES ($1, 'default', $2, $3, $4, $5, $6, $7, $8, $9);
                """,
                item_id,
                media_type,
                audio_codec,
                video_codec,
                file_size,
                duration,
                width,
                height,
                bitrate,
            )
