from __future__ import annotations

from pathlib import Path
from typing import Dict

from app.utils.logging import get_logger

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

log = get_logger(__name__)

_LOCALES: Dict[str, Dict[str, str]] = {}


def init_locales() -> None:
    """Load TOML translations shipped in app/i18n/locales."""
    locales_dir = Path(__file__).resolve().parent / "locales"
    for file in locales_dir.glob("active.*.toml"):
        lang = file.stem.split(".")[-1]
        try:
            data = tomllib.loads(file.read_text(encoding="utf-8"))
            _LOCALES[lang] = {str(k): str(v) for k, v in data.items()}
        except Exception as e:
            log.exception("failed to load locale %s: %s", file, e)

    if "en" not in _LOCALES:
        raise RuntimeError("missing base locale: en")

    log.info("i18n: loaded %d locales", len(_LOCALES))


def t(key: str, lang: str = "en") -> str:
    table = _LOCALES.get(lang) or _LOCALES.get("en", {})
    return table.get(key) or _LOCALES.get("en", {}).get(key) or key


def available_languages() -> Dict[str, str]:
    """Returns mapping lang_code -> localized language name (from each locale's 'Language' key)."""
    out: Dict[str, str] = {}
    for code, table in _LOCALES.items():
        out[code] = table.get("Language", code)
    return out
