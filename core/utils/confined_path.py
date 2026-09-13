"""Omezení relativní cesty na povolený kořenový adresář."""

from __future__ import annotations

from pathlib import Path


def resolve_confined_path(root: Path, relative: str | None) -> Path | None:
    """Vrátí normalizovanou cestu uvnitř ``root``, jinak ``None``.

    Odmítne prázdnou hodnotu, absolutní cestu a jakýkoli ``..`` / symlink,
    který po ``resolve()`` opustí kořen.
    """
    raw = str(relative or "").strip().replace("\\", "/")
    if not raw or "\x00" in raw:
        return None

    candidate = Path(raw)
    if candidate.is_absolute() or bool(candidate.anchor):
        return None
    if raw.startswith("/") or raw.startswith("//"):
        return None
    if len(raw) >= 2 and raw[0].isalpha() and raw[1] == ":":
        return None

    try:
        root_resolved = root.resolve()
        resolved = (root_resolved / candidate).resolve()
        resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        return None

    if resolved == root_resolved:
        return None
    return resolved
