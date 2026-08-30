"""Formátování cesty umístění ve výsledcích Analýzy podobností."""

from __future__ import annotations

from core.shared.sluzby.similarity_domain import (
    SCOPE_AUDIT,
    SCOPE_LEGAL,
    SCOPE_MEASURES,
    SCOPE_PBP,
    SCOPE_PROVERKY,
    SCOPE_RISKS,
    domain_label,
)

LOCATION_PATH_SEPARATOR = " → "


def similarity_location_root(scope_key: str) -> str:
    """Kořen cesty ``location_label`` pro oblast ze snapshotu.

    Shodný prefix, který sběrače dávají na začátek umístění (název modulu).
    """
    if scope_key == SCOPE_PROVERKY:
        from moduly.proverky.constants import MODULE_NAME

        return MODULE_NAME
    if scope_key == SCOPE_AUDIT:
        from moduly.audity.constants import MODULE_NAME

        return MODULE_NAME
    if scope_key in {SCOPE_RISKS, SCOPE_MEASURES, SCOPE_PBP}:
        from moduly.rizeni_rizik.constants import MODULE_NAME

        return MODULE_NAME
    if scope_key == SCOPE_LEGAL:
        return domain_label(scope_key)
    return domain_label(scope_key)


def format_similarity_location(full_path: str | None, root_label: str | None) -> str:
    """Vrátí viditelnou cestu bez přesného počátečního kořene oblasti.

    Odstraní pouze ``root_label`` + oddělovač na začátku. Kořen uprostřed
    cesty se nemění. Prázdný výsledek po ořezu ponechá původní umístění.
    """
    path = str(full_path or "").strip()
    root = str(root_label or "").strip()
    if not path:
        return ""
    if not root:
        return path
    prefix = f"{root}{LOCATION_PATH_SEPARATOR}"
    if path == root or path == prefix.strip():
        return path
    if not path.startswith(prefix):
        return path
    remainder = path[len(prefix) :].strip()
    if not remainder:
        return path
    return remainder
