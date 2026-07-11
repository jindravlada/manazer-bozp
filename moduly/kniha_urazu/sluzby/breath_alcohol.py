"""Normalizace výsledku dechové zkoušky (promile)."""

from __future__ import annotations

import re

_UNIT_RE = re.compile(r"[‰%]")


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


def format_breath_alcohol_for_export(text: str) -> str:
    """Tisková podoba s jednotkou, např. „0,24 ‰“."""
    number = normalize_breath_alcohol_storage(text)
    if not number:
        return ""
    return f"{number} ‰"
