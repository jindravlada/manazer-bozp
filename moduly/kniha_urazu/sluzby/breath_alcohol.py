"""Normalizace množství alkoholu v promile."""

from __future__ import annotations

import re

_UNIT_RE = re.compile(r"[‰%]")

EXTREME_BREATH_ALCOHOL_LIMIT = 4.0

EXTREME_BREATH_ALCOHOL_CONFIRM_TITLE = "Pozor"
EXTREME_BREATH_ALCOHOL_CONFIRM_MESSAGE = (
    "Zadaná hodnota alkoholu je velmi vysoká.\n\n"
    "Ověřte prosím, že nedošlo k překlepu.\n\n"
    "Opravdu chcete tuto hodnotu uložit?"
)


def sanitize_breath_alcohol_input(text: str) -> str:
    """Ponechá jen číslice a jednu desetinnou čárku; tečku převede na čárku."""
    raw = _UNIT_RE.sub("", text or "")
    raw = raw.replace(".", ",")
    parts: list[str] = []
    comma_seen = False
    for char in raw:
        if char.isdigit():
            parts.append(char)
        elif char == "," and not comma_seen:
            parts.append(char)
            comma_seen = True
    return "".join(parts)


def normalize_breath_alcohol_storage(text: str) -> str:
    """Hodnota k uložení do DB – jen číslo, bez ‰ a bez koncové čárky."""
    cleaned = sanitize_breath_alcohol_input(text).strip()
    if cleaned.endswith(","):
        cleaned = cleaned[:-1]
    return cleaned


def breath_alcohol_for_display(text: str) -> str:
    """Zobrazení ve formuláři (staré záznamy s ‰ se očistí)."""
    return normalize_breath_alcohol_storage(text)


def parse_breath_alcohol_number(text: str) -> float | None:
    normalized = normalize_breath_alcohol_storage(text)
    if not normalized:
        return None
    try:
        return float(normalized.replace(",", "."))
    except ValueError:
        return None


def is_extreme_breath_alcohol(
    text: str,
    *,
    limit: float = EXTREME_BREATH_ALCOHOL_LIMIT,
) -> bool:
    """True pokud je hodnota větší než limit (výchozí 4,00 ‰)."""
    value = parse_breath_alcohol_number(text)
    if value is None:
        return False
    return value > limit


def format_breath_alcohol_for_export(text: str) -> str:
    """Tisková podoba s jednotkou, např. „0,24 ‰“."""
    number = normalize_breath_alcohol_storage(text)
    if not number:
        return ""
    return f"{number} ‰"
