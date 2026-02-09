from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Extractor:
    id: str
    display_name: str
    hosts: List[str]
    url_pattern: re.Pattern
    hidden: bool = False
    redirect: bool = False


def _p(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


EXTRACTORS: List[Extractor] = [
    Extractor(
        id="tiktok",
        display_name="TikTok",
        hosts=["tiktok.com"],
        url_pattern=_p(r"https?://(www\.)?tiktok\.com/.*"),
    ),
    Extractor(
        id="tiktok_vm",
        display_name="TikTok (vm)",
        hosts=["vm.tiktok.com"],
        url_pattern=_p(r"https?://vm\.tiktok\.com/.*"),
        redirect=True,
        hidden=True,
    ),
    Extractor(
        id="soundcloud",
        display_name="SoundCloud",
        hosts=["soundcloud.com"],
        url_pattern=_p(r"https?://(www\.)?soundcloud\.com/.*"),
    ),
    Extractor(
        id="soundcloud_short",
        display_name="SoundCloud (on\.soundcloud)",
        hosts=["on.soundcloud.com"],
        url_pattern=_p(r"https?://on\.soundcloud\.com/.*"),
        redirect=True,
        hidden=True,
    ),
    Extractor(
        id="twitter",
        display_name="X / Twitter",
        hosts=["x.com", "twitter.com"],
        url_pattern=_p(r"https?://(www\.)?(x|twitter)\.com/.*"),
    ),
    Extractor(
        id="twitter_short",
        display_name="t\.co",
        hosts=["t.co"],
        url_pattern=_p(r"https?://t\.co/.*"),
        redirect=True,
        hidden=True,
    ),
    Extractor(
        id="instagram",
        display_name="Instagram",
        hosts=["instagram.com"],
        url_pattern=_p(r"https?://(www\.)?instagram\.com/.*"),
    ),
    Extractor(
        id="instagram_stories",
        display_name="Instagram Stories",
        hosts=["instagram.com"],
        url_pattern=_p(r"https?://(www\.)?instagram\.com/stories/.*"),
        hidden=True,
    ),
    Extractor(
        id="instagram_share",
        display_name="Instagram Share",
        hosts=["instagram.com"],
        url_pattern=_p(r"https?://(www\.)?instagram\.com/share/.*"),
        redirect=True,
        hidden=True,
    ),
    Extractor(
        id="ninegag",
        display_name="9GAG",
        hosts=["9gag.com"],
        url_pattern=_p(r"https?://(www\.)?9gag\.com/.*"),
    ),
    Extractor(
        id="youtube",
        display_name="YouTube",
        hosts=["youtube.com", "youtu.be"],
        url_pattern=_p(r"https?://(www\.)?(youtube\.com|youtu\.be)/.*"),
    ),
    Extractor(
        id="pinterest",
        display_name="Pinterest",
        hosts=["pinterest.com"],
        url_pattern=_p(r"https?://(www\.)?pinterest\.com/.*"),
    ),
    Extractor(
        id="pinterest_short",
        display_name="Pinterest (pin\.it)",
        hosts=["pin.it"],
        url_pattern=_p(r"https?://pin\.it/.*"),
        redirect=True,
        hidden=True,
    ),
    Extractor(
        id="reddit",
        display_name="Reddit",
        hosts=["reddit.com"],
        url_pattern=_p(r"https?://(www\.)?reddit\.com/.*"),
    ),
    Extractor(
        id="reddit_short",
        display_name="Reddit (redd\.it)",
        hosts=["redd.it"],
        url_pattern=_p(r"https?://redd\.it/.*"),
        redirect=True,
        hidden=True,
    ),
    Extractor(
        id="threads",
        display_name="Threads",
        hosts=["threads.net"],
        url_pattern=_p(r"https?://(www\.)?threads\.net/.*"),
    ),
]


def match_extractor(url: str) -> Optional[Extractor]:
    for ex in EXTRACTORS:
        if ex.url_pattern.match(url):
            return ex
    return None


def list_visible_extractors() -> List[Extractor]:
    return [e for e in EXTRACTORS if not e.hidden]
