from __future__ import annotations

import shutil


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None
