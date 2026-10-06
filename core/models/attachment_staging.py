"""Odložené přílohy — čistá data bez Qt a bez zápisu do DB / filesystemu."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class AttachmentStagingError(ValueError):
    """Chyba odloženého ukládání příloh."""


def normalize_staging_source_key(path: str | Path) -> str:
    text = str(path or "").strip()
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(os.path.expanduser(text)))


@dataclass
class AttachmentStagingState:
    """Pracovní fronta příloh. Nic nekopíruje a nic nezapisuje.

    Lze plnit i bez ``entity_id`` rodiče. Stejný zdroj se ve frontě
    neobjeví dvakrát. Snapshot je deterministický pro dirty stav editoru.
    """

    pending_add_paths: list[str] = field(default_factory=list)
    pending_remove_ids: list[int] = field(default_factory=list)
    verbatim_keys: set[str] = field(default_factory=set)

    def snapshot(self) -> tuple[tuple[str, ...], tuple[int, ...]]:
        return (tuple(self.pending_add_paths), tuple(self.pending_remove_ids))

    def has_changes(self) -> bool:
        return bool(self.pending_add_paths or self.pending_remove_ids)

    def clear(self) -> None:
        self.pending_add_paths.clear()
        self.pending_remove_ids.clear()
        self.verbatim_keys.clear()

    def add_pending_path(self, path: str | Path) -> bool:
        """Zařadí zdroj. ``False`` = stejný soubor už ve frontě je."""
        text = str(path or "").strip()
        if not text:
            return False
        key = normalize_staging_source_key(text)
        for existing in self.pending_add_paths:
            if normalize_staging_source_key(existing) == key:
                return False
        self.pending_add_paths.append(text)
        return True

    def add_verbatim_path(self, path: str | Path) -> bool:
        """Zařadí už připravený soubor. Uloží se jako bajtová kopie bez rekomprese."""
        added = self.add_pending_path(path)
        key = normalize_staging_source_key(path)
        if key:
            self.verbatim_keys.add(key)
        return added

    def is_verbatim(self, path: str | Path) -> bool:
        return normalize_staging_source_key(path) in self.verbatim_keys

    def remove_pending_path(self, path: str | Path) -> bool:
        key = normalize_staging_source_key(path)
        if not key:
            return False
        kept = [
            item
            for item in self.pending_add_paths
            if normalize_staging_source_key(item) != key
        ]
        changed = len(kept) != len(self.pending_add_paths)
        self.pending_add_paths = kept
        if changed:
            self.verbatim_keys.discard(key)
        return changed

    def mark_for_removal(self, attachment_id: int) -> bool:
        ident = int(attachment_id)
        if ident in self.pending_remove_ids:
            return False
        self.pending_remove_ids.append(ident)
        return True

    def unmark_for_removal(self, attachment_id: int) -> bool:
        ident = int(attachment_id)
        if ident not in self.pending_remove_ids:
            return False
        self.pending_remove_ids = [
            item for item in self.pending_remove_ids if item != ident
        ]
        return True

    def is_marked_for_removal(self, attachment_id: int) -> bool:
        return int(attachment_id) in self.pending_remove_ids

    def visible_existing_ids(self, existing_ids: list[int] | tuple[int, ...]) -> tuple[int, ...]:
        removed = set(self.pending_remove_ids)
        return tuple(int(item) for item in existing_ids if int(item) not in removed)


@dataclass
class PreparedAttachmentChanges:
    """Výsledek prepare před DB commitem — pro finalize nebo rollback_cleanup."""

    entity_type: str
    entity_id: int
    created_attachments: list = field(default_factory=list)
    copied_paths: list[Path] = field(default_factory=list)
    pending_unlink_paths: list[Path] = field(default_factory=list)
    unlink_warnings: list[str] = field(default_factory=list)
    finalized: bool = False
    rolled_back: bool = False
