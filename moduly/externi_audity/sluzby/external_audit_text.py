"""Společné zkrácení textu zjištění (Dashboard + úkoly)."""

from __future__ import annotations

DEFAULT_FINDING_TITLE_LIMIT = 80


def shorten_finding_title(
    value: str | None,
    *,
    limit: int = DEFAULT_FINDING_TITLE_LIMIT,
) -> str:
    """
    Čistý zkrácený název zjištění bez prefixů.

    - sloučí mezery a prázdné řádky,
    - krátký text ponechá celý,
    - dlouhý zkrátí na ``limit`` znaků,
    - pokud lze, neřeže uprostřed slova,
    - zkrácení označí „…“.
    """
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    if len(text) <= limit:
        return text

    cut = text[: max(1, limit)].rstrip()
    if len(text) > len(cut) and cut and not cut[-1].isspace():
        # Pokud jsme uřízli uprostřed slova, ustoupit k poslední mezeře.
        last_space = cut.rfind(" ")
        min_keep = max(20, limit // 2)
        if last_space >= min_keep:
            cut = cut[:last_space].rstrip()
    cut = cut.rstrip(".,;:–- ")
    if not cut:
        cut = text[: max(1, limit - 1)].rstrip()
    return f"{cut}…"
