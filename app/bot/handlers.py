
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import List, Optional

from aiogram import F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InputFile,
    Message,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from app.config.settings import settings
from app.db import queries
from app.extractors.downloader import download, resolve_redirect
from app.extractors.registry import list_visible_extractors, match_extractor
from app.i18n.localizer import available_languages, t
from app.utils.logging import get_logger

log = get_logger(__name__)

router = Router()

URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _is_admin(user_id: int) -> bool:
    return user_id in set(settings.ADMINS or [])


def _is_whitelisted(user_id: int) -> bool:
    if not settings.WHITELIST:
        return True
    return user_id in set(settings.WHITELIST or [])


def _chat_type_str(msg: Message) -> str:
    if msg.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        return "group"
    return "private"


def main_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t("SettingsButton", lang), callback_data="settings"),
                InlineKeyboardButton(text=t("ExtractorsButton", lang), callback_data="extractors"),
            ],
            [InlineKeyboardButton(text=t("CloseButton", lang), callback_data="close")],
        ]
    )


def settings_keyboard(chat: queries.ChatRow) -> InlineKeyboardMarkup:
    lang = chat.language
    def onoff(v: bool) -> str:
        return t("EnabledButton", lang) if v else t("DisabledButton", lang)

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{t('LanguageButton', lang)}: {available_languages().get(chat.language, chat.language)}",
                    callback_data="settings.select.language",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"{t('CaptionsButton', lang)}: {onoff(chat.captions)}",
                    callback_data="settings.toggle.captions",
                ),
                InlineKeyboardButton(
                    text=f"{t('SilentButton', lang)}: {onoff(chat.silent)}",
                    callback_data="settings.toggle.silent",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{t('NsfwButton', lang)}: {onoff(chat.nsfw)}",
                    callback_data="settings.toggle.nsfw",
                ),
                InlineKeyboardButton(
                    text=f"{t('DeleteProcessedButton', lang)}: {onoff(chat.delete_links)}",
                    callback_data="settings.toggle.delete_links",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"{t('MediaAlbumButton', lang)}: {chat.media_album_limit}",
                    callback_data="settings.select.album_limit",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("DisabledExtractorsButton", lang),
                    callback_data="settings.select.disabled_extractors",
                )
            ],
            [
                InlineKeyboardButton(text=t("BackButton", lang), callback_data="start"),
                InlineKeyboardButton(text=t("CloseButton", lang), callback_data="close"),
            ],
        ]
    )


def languages_keyboard(chat: queries.ChatRow) -> InlineKeyboardMarkup:
    langs = available_languages()
    buttons = []
    for code, name in sorted(langs.items(), key=lambda x: x[0]):
        mark = " ✅" if code == chat.language else ""
        buttons.append([InlineKeyboardButton(text=f"{name}{mark}", callback_data=f"settings.language.{code}")])
    buttons.append([InlineKeyboardButton(text=t("BackButton", chat.language), callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def album_limit_keyboard(chat: queries.ChatRow) -> InlineKeyboardMarkup:
    lang = chat.language
    limits = [1, 2, 3, 5, 10, 15, 20]
    rows = []
    for n in limits:
        mark = " ✅" if n == chat.media_album_limit else ""
        rows.append([InlineKeyboardButton(text=f"{n}{mark}", callback_data=f"settings.album.{n}")])
    rows.append([InlineKeyboardButton(text=t("BackButton", lang), callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def extractors_keyboard(chat: queries.ChatRow) -> InlineKeyboardMarkup:
    lang = chat.language
    rows = []
    for ex in list_visible_extractors():
        disabled = ex.id in chat.disabled_extractors
        mark = f" ({t('DisabledButton', lang)})" if disabled else ""
        rows.append([InlineKeyboardButton(text=f"{ex.display_name}{mark}", callback_data=f"settings.extractor.{ex.id}")])
    rows.append([InlineKeyboardButton(text=t("BackButton", lang), callback_data="settings")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def start_text(lang: str) -> str:
    # StartMessage key exists in locales; fallback to a simple welcome.
    return t("StartMessage", lang)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not message.from_user:
        return
    if not _is_whitelisted(message.from_user.id):
        return

    chat = await queries.get_or_create_chat(message.chat.id, _chat_type_str(message))
    await message.answer(
        start_text(chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(chat.language),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "start")
async def cb_start(call: CallbackQuery) -> None:
    if not call.from_user:
        return
    chat = await queries.get_or_create_chat(call.message.chat.id, "group" if call.message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) else "private")
    await call.message.edit_text(
        start_text(chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard(chat.language),
        disable_web_page_preview=True,
    )
    await call.answer()


@router.callback_query(F.data == "close")
async def cb_close(call: CallbackQuery) -> None:
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@router.message(Command("settings"))
async def cmd_settings(message: Message) -> None:
    if not message.from_user:
        return
    if not _is_whitelisted(message.from_user.id):
        return

    chat = await queries.get_or_create_chat(message.chat.id, _chat_type_str(message))
    await message.answer(
        t("GroupSettingsMessage" if chat.type == "group" else "PrivateSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=settings_keyboard(chat),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "settings")
async def cb_settings(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_text(
        t("GroupSettingsMessage" if chat.type == "group" else "PrivateSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=settings_keyboard(chat),
        disable_web_page_preview=True,
    )
    await call.answer()


@router.callback_query(F.data.startswith("settings.toggle."))
async def cb_toggle(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    action = call.data.split(".", 2)[2]

    if action == "captions":
        await queries.toggle_chat_captions(chat.chat_id)
    elif action == "silent":
        await queries.toggle_chat_silent(chat.chat_id)
    elif action == "nsfw":
        await queries.toggle_chat_nsfw(chat.chat_id)
    elif action == "delete_links":
        await queries.toggle_chat_delete_links(chat.chat_id)

    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_reply_markup(reply_markup=settings_keyboard(chat))
    await call.answer()


@router.callback_query(F.data == "settings.select.language")
async def cb_select_language(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_text(
        t("LanguageSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=languages_keyboard(chat),
    )
    await call.answer()


@router.callback_query(F.data.startswith("settings.language."))
async def cb_language(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    lang = call.data.split(".", 2)[2]
    await queries.set_chat_language(chat.chat_id, lang)
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_text(
        t("GroupSettingsMessage" if chat.type == "group" else "PrivateSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=settings_keyboard(chat),
        disable_web_page_preview=True,
    )
    await call.answer()


@router.callback_query(F.data == "settings.select.album_limit")
async def cb_album_limit(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_text(
        t("MediaAlbumSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=album_limit_keyboard(chat),
    )
    await call.answer()


@router.callback_query(F.data.startswith("settings.album."))
async def cb_album_set(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    n = int(call.data.split(".", 2)[2])
    if n < 1 or n > 20:
        await call.answer()
        return
    # global limit enforcement
    if n > settings.DEFAULT_MEDIA_ALBUM_LIMIT and settings.DEFAULT_MEDIA_ALBUM_LIMIT > 0:
        # Instance-wide hard cap equals DEFAULT_MEDIA_ALBUM_LIMIT to mirror Go's range guard.
        n = settings.DEFAULT_MEDIA_ALBUM_LIMIT
    await queries.set_chat_media_album_limit(chat.chat_id, n)
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_text(
        t("GroupSettingsMessage" if chat.type == "group" else "PrivateSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=settings_keyboard(chat),
        disable_web_page_preview=True,
    )
    await call.answer()


@router.callback_query(F.data == "settings.select.disabled_extractors")
async def cb_disabled_extractors(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_text(
        t("DisabledExtractorsSettingsMessage", chat.language),
        parse_mode=ParseMode.HTML,
        reply_markup=extractors_keyboard(chat),
    )
    await call.answer()


@router.callback_query(F.data.startswith("settings.extractor."))
async def cb_toggle_extractor(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    ex_id = call.data.split(".", 2)[2]
    if ex_id in chat.disabled_extractors:
        await queries.remove_disabled_extractor(chat.chat_id, ex_id)
    else:
        await queries.add_disabled_extractor(chat.chat_id, ex_id)
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    await call.message.edit_reply_markup(reply_markup=extractors_keyboard(chat))
    await call.answer()


@router.callback_query(F.data == "extractors")
async def cb_extractors(call: CallbackQuery) -> None:
    chat = await queries.get_or_create_chat(call.message.chat.id, _chat_type_str(call.message))
    lines = [t("ExtractorsMessage", chat.language)]
    for ex in list_visible_extractors():
        lines.append(f"• {ex.display_name}")
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t("BackButton", chat.language), callback_data="start")]]
    ))
    await call.answer()


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    stats = await queries.get_stats(7)
    await message.answer(
        f"<b>Stats (last 7d)</b>\n"
        f"Private chats: {stats['total_private_chats']}\n"
        f"Group chats: {stats['total_group_chats']}\n"
        f"Downloads: {stats['total_downloads']}\n"
        f"Total size: {stats['total_downloads_size']} bytes\n",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("derr"))
async def cmd_derr(message: Message) -> None:
    if not message.from_user or not _is_admin(message.from_user.id):
        return
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        return
    err_id = parts[1].strip()
    msg = await queries.get_error_by_id(err_id)
    if msg:
        await message.answer(msg)
    else:
        await message.answer("not found")


def _extract_urls(message: Message) -> List[str]:
    urls: List[str] = []
    text = message.text or message.caption or ""
    urls.extend(URL_RE.findall(text))
    return urls


@router.message(F.text | F.caption)
async def url_handler(message: Message) -> None:
    if not message.from_user:
        return
    if not _is_whitelisted(message.from_user.id):
        return

    urls = _extract_urls(message)
    if not urls:
        return

    chat = await queries.get_or_create_chat(message.chat.id, _chat_type_str(message))
    lang = chat.language

    for url in urls:
        ex = match_extractor(url)
        if not ex:
            continue
        if ex.id in chat.disabled_extractors:
            continue

        try:
            processing = await message.reply(t("ProcessingMessage", lang), disable_web_page_preview=True)
        except Exception:
            processing = None

        final_url = url
        if ex.redirect:
            try:
                final_url = await resolve_redirect(url)
            except Exception:
                final_url = url

        # Download
        try:
            res = await download(final_url, max_items=chat.media_album_limit)
        except Exception as e:
            # store hashed error like govd (short id)
            err_id = hashlib.sha256(str(e).encode("utf-8")).hexdigest()[:16]
            await queries.log_error(err_id, repr(e))
            if processing:
                await processing.edit_text(t("ErrorMessage", lang) + f"\n\nid: <code>{err_id}</code>", parse_mode=ParseMode.HTML)
            else:
                await message.reply(t("ErrorMessage", lang) + f"\n\nid: {err_id}")
            continue

        caption = ""
        if chat.captions:
            # mirror govd captions header/description templates (best-effort)
            caption = f"<b>{res.title}</b>"
            if res.uploader:
                caption += f"\n@{res.uploader}" if not res.uploader.startswith("@") else f"\n{res.uploader}"
            if res.description:
                caption += f"\n\n{res.description[:900]}"

        # Send files (album if >1)
        try:
            if len(res.files) == 1:
                f = res.files[0]
                await message.answer_document(
                    InputFile(f.path),
                    caption=caption if caption else None,
                    parse_mode=ParseMode.HTML,
                    disable_notification=chat.silent,
                )
                await queries.insert_download(
                    content_id=res.content_id,
                    content_url=final_url,
                    extractor_id=res.extractor_id,
                    chat_id=chat.chat_id,
                    media_type=f.media_type,
                    audio_codec=f.audio_codec,
                    video_codec=f.video_codec,
                    file_size=f.file_size,
                    duration=f.duration,
                    width=f.width,
                    height=f.height,
                    bitrate=f.bitrate,
                )
            else:
                # Send as documents in multiple messages to respect telegram limits
                for i, f in enumerate(res.files):
                    await message.answer_document(
                        InputFile(f.path),
                        caption=caption if (caption and i == 0) else None,
                        parse_mode=ParseMode.HTML,
                        disable_notification=chat.silent,
                    )
                    await queries.insert_download(
                        content_id=res.content_id,
                        content_url=final_url,
                        extractor_id=res.extractor_id,
                        chat_id=chat.chat_id,
                        media_type=f.media_type,
                        audio_codec=f.audio_codec,
                        video_codec=f.video_codec,
                        file_size=f.file_size,
                        duration=f.duration,
                        width=f.width,
                        height=f.height,
                        bitrate=f.bitrate,
                    )

        except Exception as e:
            err_id = hashlib.sha256(str(e).encode("utf-8")).hexdigest()[:16]
            await queries.log_error(err_id, repr(e))
            await message.reply(t("ErrorMessage", lang) + f"\n\nid: <code>{err_id}</code>", parse_mode=ParseMode.HTML)

        # Delete original link message if enabled
        if chat.delete_links:
            try:
                await message.delete()
            except Exception:
                pass

        if processing:
            try:
                await processing.delete()
            except Exception:
                pass


# Inline mode (best-effort parity with govd)
@router.inline_query()
async def inline_handler(query: InlineQuery) -> None:
    url = (query.query or "").strip()
    if not url or not URL_RE.match(url):
        await query.answer([], is_personal=True, cache_time=1)
        return

    ex = match_extractor(url)
    if not ex:
        await query.answer([], is_personal=True, cache_time=1)
        return

    # We can't download in inline query response (time constraints). We return an article;
    # chosen_inline_result will trigger the actual download and send to user privately.
    result = InlineQueryResultArticle(
        id="1",
        title=t("InlineShareMessage", "en"),
        input_message_content=InputTextMessageContent(
            message_text=t("InlineProcessingMessage", "en"),
            parse_mode=ParseMode.HTML,
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=t("InlineLoadingMessage", "en"), callback_data="inline:loading")]]
        ),
    )
    await query.answer([result], is_personal=True, cache_time=1)


@router.callback_query(F.data == "inline:loading")
async def inline_loading(call: CallbackQuery) -> None:
    await call.answer(t("InlineLoadingMessage", "en"), show_alert=False)
