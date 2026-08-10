"""Sdílený typ ověření Dokumentace / Terén (Prověrky, Audity)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

VERIFICATION_TYPE_DOCUMENTATION = "dokumentace"
VERIFICATION_TYPE_TERRAIN = "teren"
VERIFICATION_TYPE_DEFAULT = VERIFICATION_TYPE_DOCUMENTATION

VERIFICATION_TYPE_OPTIONS = (
    (VERIFICATION_TYPE_DOCUMENTATION, "Dokumentace"),
    (VERIFICATION_TYPE_TERRAIN, "Terén"),
)

VERIFICATION_TYPE_LABELS = dict(VERIFICATION_TYPE_OPTIONS)

_DOCUMENTATION_ALIASES = frozenset(
    {
        VERIFICATION_TYPE_DOCUMENTATION,
        "dokumentace",
        "documentation",
        "document",
        "docs",
        "doc",
    }
)
_TERRAIN_ALIASES = frozenset(
    {
        VERIFICATION_TYPE_TERRAIN,
        "teren",
        "terén",
        "terrain",
        "field",
    }
)


def normalize_verification_type(value) -> str:
    """Sjednotí typ ověření na kanonické hodnoty projektu (dokumentace / teren)."""
    raw = str(value or "").strip()
    normalized = raw.casefold()
    if normalized in _DOCUMENTATION_ALIASES:
        return VERIFICATION_TYPE_DOCUMENTATION
    if normalized in _TERRAIN_ALIASES:
        return VERIFICATION_TYPE_TERRAIN
    if raw:
        logger.warning(
            "Neznámý typ ověření %r – použito výchozí %s.",
            value,
            VERIFICATION_TYPE_DEFAULT,
        )
    return VERIFICATION_TYPE_DEFAULT


def methodology_verification_type(item: dict | None) -> str:
    if not isinstance(item, dict):
        return VERIFICATION_TYPE_DEFAULT
    return normalize_verification_type(item.get("verification_type"))
