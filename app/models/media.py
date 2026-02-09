from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MediaFormat:
    format_id: str
    media_type: str  # 'video' | 'audio' | 'photo' | 'document'
    url: Optional[str] = None
    file_size: int = 0
    duration: int = 0
    width: int = 0
    height: int = 0
    bitrate: int = 0
    video_codec: str = ""
    audio_codec: str = ""
    title: str = ""
    artist: str = ""
    thumbnail_url: Optional[str] = None


@dataclass
class MediaItem:
    formats: List[MediaFormat] = field(default_factory=list)

    def best_format(self) -> Optional[MediaFormat]:
        if not self.formats:
            return None
        # Prefer AVC/H264 MP4-ish video formats (Telegram friendly)
        vids = [f for f in self.formats if f.media_type == "video"]
        if vids:
            vids.sort(key=lambda f: (f.bitrate, f.height, f.width), reverse=True)
            return vids[0]
        auds = [f for f in self.formats if f.media_type == "audio"]
        if auds:
            auds.sort(key=lambda f: f.bitrate, reverse=True)
            return auds[0]
        photos = [f for f in self.formats if f.media_type == "photo"]
        if photos:
            photos.sort(key=lambda f: (f.width * f.height, f.file_size), reverse=True)
            return photos[0]
        return self.formats[0]


@dataclass
class Media:
    content_id: str
    content_url: str
    extractor_id: str
    caption: str = ""
    nsfw: bool = False
    items: List[MediaItem] = field(default_factory=list)

    def new_item(self) -> MediaItem:
        item = MediaItem()
        self.items.append(item)
        return item


@dataclass
class DownloadedFile:
    path: str
    media_type: str
    file_size: int
    duration: int = 0
    width: int = 0
    height: int = 0
    bitrate: int = 0
    video_codec: str = ""
    audio_codec: str = ""


@dataclass
class DownloadResult:
    content_id: str
    extractor_id: str
    title: str = ""
    uploader: str = ""
    description: str = ""
    files: List[DownloadedFile] = field(default_factory=list)
