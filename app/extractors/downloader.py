from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from aiohttp import ClientSession
from yt_dlp import YoutubeDL

from app.config.settings import settings
from app.models.media import DownloadResult, DownloadedFile


async def resolve_redirect(url: str) -> str:
    """Follow HTTP redirects and return final URL."""
    async with ClientSession() as session:
        async with session.get(url, allow_redirects=True, timeout=15) as resp:
            return str(resp.url)


def _ydl_opts(out_dir: str) -> dict:
    return {
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "max_filesize": settings.MAX_FILE_SIZE,
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "postprocessors": [
            {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"},
        ],
    }


def _pick_codec_meta(info: dict) -> tuple[str, str, int, int, int, int]:
    """(vcodec, acodec, tbr, width, height, duration)"""
    vcodec = ""
    acodec = ""
    tbr = 0
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    duration = int(info.get("duration") or 0)

    rd = info.get("requested_downloads")
    if rd and isinstance(rd, list) and rd:
        f = rd[0]
        vcodec = str(f.get("vcodec") or "")
        acodec = str(f.get("acodec") or "")
        tbr = int(f.get("tbr") or 0)
        width = int(f.get("width") or width)
        height = int(f.get("height") or height)

    if vcodec == "none":
        vcodec = ""
    if acodec == "none":
        acodec = ""

    return vcodec, acodec, tbr, width, height, duration


def _file_path(out_dir: str, content_id: str, ext: str) -> str:
    p = os.path.join(out_dir, f"{content_id}.{ext}")
    if os.path.exists(p):
        return p
    # yt-dlp often remuxes to mp4
    mp4 = os.path.join(out_dir, f"{content_id}.mp4")
    if os.path.exists(mp4):
        return mp4
    # fallback: find any file starting with id
    for f in Path(out_dir).glob(f"{content_id}.*"):
        if f.is_file():
            return str(f)
    return p


def _as_downloaded_file(out_dir: str, info: dict) -> DownloadedFile:
    content_id = str(info.get("id") or "unknown")
    ext = str(info.get("ext") or "mp4")
    path = _file_path(out_dir, content_id, ext)
    st = os.stat(path)

    vcodec, acodec, tbr, width, height, duration = _pick_codec_meta(info)

    media_type = "video" if vcodec else ("audio" if acodec else "document")

    return DownloadedFile(
        path=path,
        media_type=media_type,
        file_size=int(st.st_size),
        duration=duration,
        width=width,
        height=height,
        bitrate=tbr,
        video_codec=vcodec,
        audio_codec=acodec,
    )


def _download_sync(url: str, out_dir: str, max_items: int) -> DownloadResult:
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    with YoutubeDL(_ydl_opts(out_dir)) as ydl:
        info = ydl.extract_info(url, download=True)

    # media album / playlist
    entries: List[dict] = []
    if info.get("_type") in {"playlist", "multi_video"} and info.get("entries"):
        for e in info["entries"]:
            if e:
                entries.append(e)
            if len(entries) >= max_items:
                break
    else:
        entries = [info]

    # Title/uploader/desc from top-level when available
    title = str(info.get("title") or (entries[0].get("title") if entries else ""))
    uploader = str(info.get("uploader") or info.get("uploader_id") or "")
    description = str(info.get("description") or "")

    files = [_as_downloaded_file(out_dir, e) for e in entries]
    content_id = str(info.get("id") or (entries[0].get("id") if entries else "unknown"))
    extractor_id = str(info.get("extractor") or (entries[0].get("extractor") if entries else "generic"))

    return DownloadResult(
        content_id=content_id,
        extractor_id=extractor_id,
        title=title,
        uploader=uploader,
        description=description,
        files=files,
    )


async def download(url: str, *, out_dir: Optional[str] = None, max_items: Optional[int] = None) -> DownloadResult:
    out_dir = out_dir or settings.DOWNLOADS_DIR
    max_items = int(max_items or settings.DEFAULT_MEDIA_ALBUM_LIMIT)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _download_sync, url, out_dir, max_items)
