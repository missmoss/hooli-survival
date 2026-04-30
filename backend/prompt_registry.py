import random
from types import ModuleType

import prompts_en
import prompts_zh


DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = ("en", "zh-Hant")
PROMPT_BUNDLES: dict[str, ModuleType] = {
    "en": prompts_en,
    "zh-Hant": prompts_zh,
}


def normalize_locale(locale: str | None) -> str:
    raw = (locale or "").strip()
    lowered = raw.lower()
    if lowered in {"zh", "zh-tw", "zh-hant", "zh_hant", "traditional-chinese"}:
        return "zh-Hant"
    if lowered.startswith("zh-"):
        return "zh-Hant"
    if lowered in {"en", "en-us", "en_us", "english"}:
        return "en"
    return DEFAULT_LOCALE


def locale_from_accept_language(header_value: str | None) -> str:
    raw = (header_value or "").strip()
    if not raw:
        return DEFAULT_LOCALE
    for part in raw.split(","):
        token = part.split(";", 1)[0].strip()
        if not token:
            continue
        normalized = normalize_locale(token)
        if normalized in SUPPORTED_LOCALES:
            return normalized
    return DEFAULT_LOCALE


def get_prompt_bundle(locale: str | None) -> ModuleType:
    return PROMPT_BUNDLES[normalize_locale(locale)]


def default_player_name(locale: str | None) -> str:
    return "玩家" if normalize_locale(locale) == "zh-Hant" else "Player"
