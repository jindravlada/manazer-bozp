"""Klasifikace datových kořenů workspace pro úplnou zálohu.

Jeden seznam pro tvorbu balíčku, obnovu i porovnání instancí.
Neznámé kořeny se do archivu nevkládají; záloha se označí INCOMPLETE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Stejné řetězce jako core.backup.completeness (bez kruhového importu).
_VERDICT_COMPLETE = "COMPLETE"
_VERDICT_COMPLETE_WITH_LIMITATIONS = "COMPLETE_WITH_LIMITATIONS"
_VERDICT_INCOMPLETE = "INCOMPLETE"

SNAPSHOT_SUPPORT_PHOTOS_DIR = "snapshot_support_photos"

# Relativní kořeny workspace v defaultní úplné záloze (A+B).
BACKUP_WORKSPACE_ROOTS: tuple[str, ...] = (
    "prilohy",
    "control_results",
    "ciselniky",
    "templates",
    "konfigurace",
    SNAPSHOT_SUPPORT_PHOTOS_DIR,
)

# Provozní / dočasné – záměrně mimo defaultní zálohu.
NON_BACKUP_WORKSPACE_ROOTS: tuple[str, ...] = (
    "zalohy",
    "import",
    "logy",
    "export",
    "databaze",
)

SNAPSHOT_SUPPORT_PHOTOS_LIMITATION = (
    "Tato záloha neobsahuje deklarované pokrytí složky snapshot_support_photos "
    "(zmrazené fotografie metodické podpory auditů). Balíček není poškozený "
    "a lze ho bezpečně ověřit i obnovit, ale tyto fotografie v něm nejsou."
)

UNKNOWN_ROOTS_MESSAGE_PREFIX = (
    "Úplná záloha je INCOMPLETE: neznámé datové kořeny workspace"
)


@dataclass
class WorkspaceRootScan:
    """Výsledek klasifikace kořenů první úrovně workspace."""

    included: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()
    missing_included: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    verdict: str = _VERDICT_COMPLETE
    messages: list[str] = field(default_factory=list)

    @property
    def incomplete(self) -> bool:
        return self.verdict == _VERDICT_INCOMPLETE


def _first_level_dir_names(workspace_root: Path) -> tuple[str, ...]:
    root = Path(workspace_root)
    if not root.is_dir():
        return ()
    names: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        names.append(child.name)
    return tuple(names)


def resolve_included_workspace_roots(
    include_dirs: tuple[str, ...] | None = None,
    *,
    include_exports: bool = False,
) -> tuple[str, ...]:
    """Kořeny, které tato záloha deklaruje jako pokryté."""
    dirs = list(include_dirs or BACKUP_WORKSPACE_ROOTS)
    excluded = set(NON_BACKUP_WORKSPACE_ROOTS)
    if include_exports:
        excluded.discard("export")
        if "export" not in dirs:
            dirs.append("export")
    return tuple(name for name in dirs if name not in excluded)


def classify_workspace_roots(
    workspace_root: Path,
    *,
    include_dirs: tuple[str, ...] | None = None,
    include_exports: bool = False,
) -> WorkspaceRootScan:
    """Zařadí existující kořeny první úrovně: zahrnuté / známé vyloučené / neznámé."""
    included_declared = resolve_included_workspace_roots(
        include_dirs,
        include_exports=include_exports,
    )
    included_set = set(included_declared)
    excluded_set = set(NON_BACKUP_WORKSPACE_ROOTS)
    if include_exports:
        excluded_set.discard("export")

    present = _first_level_dir_names(workspace_root)
    included = tuple(name for name in present if name in included_set)
    excluded = tuple(name for name in present if name in excluded_set)
    unknown = tuple(
        name for name in present if name not in included_set and name not in excluded_set
    )
    missing_included = tuple(
        name for name in included_declared if name not in present
    )

    messages: list[str] = []
    if unknown:
        listed = ", ".join(unknown)
        messages.append(f"{UNKNOWN_ROOTS_MESSAGE_PREFIX}: {listed}.")
        verdict = _VERDICT_INCOMPLETE
    else:
        verdict = _VERDICT_COMPLETE

    return WorkspaceRootScan(
        included=included,
        excluded=excluded,
        missing_included=missing_included,
        unknown=unknown,
        verdict=verdict,
        messages=messages,
    )


def archive_path_is_snapshot_support_photo(archive_path: str) -> bool:
    prefix = f"workspace/{SNAPSHOT_SUPPORT_PHOTOS_DIR}"
    return archive_path == prefix or archive_path.startswith(prefix + "/")


def package_covers_snapshot_support_photos(
    *,
    included_workspace_roots: list[str] | tuple[str, ...] | None,
    file_paths: list[str] | tuple[str, ...] | None = None,
) -> bool:
    """True, pokud metadata nebo manifest prokážou pokrytí kořene."""
    if included_workspace_roots is not None:
        if SNAPSHOT_SUPPORT_PHOTOS_DIR in included_workspace_roots:
            return True
    for path in file_paths or ():
        if archive_path_is_snapshot_support_photo(str(path)):
            return True
    return False


def snapshot_support_photos_coverage_limitation(
    *,
    included_workspace_roots: list[str] | tuple[str, ...] | None,
    file_paths: list[str] | tuple[str, ...] | None = None,
) -> str | None:
    if package_covers_snapshot_support_photos(
        included_workspace_roots=included_workspace_roots,
        file_paths=file_paths,
    ):
        return None
    return SNAPSHOT_SUPPORT_PHOTOS_LIMITATION


def package_coverage_verdict(
    *,
    unknown_workspace_roots: list[str] | tuple[str, ...] | None = None,
    covers_snapshot_support_photos: bool,
) -> str:
    """Verdikt pokrytí balíčku – neplést s integritou ZIP/hashů."""
    if unknown_workspace_roots:
        return _VERDICT_INCOMPLETE
    if not covers_snapshot_support_photos:
        return _VERDICT_COMPLETE_WITH_LIMITATIONS
    return _VERDICT_COMPLETE
