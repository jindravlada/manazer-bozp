"""Bezpečné načtení odpovědi AI ze ZIP archivu."""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_EXPORT_RESPONSE_BASENAMES,
    AI_PEER_REVIEW_NOT_AI_RESPONSE,
    AI_PEER_REVIEW_RESPONSE_ZIP_MAX_UNCOMPRESSED_BYTES,
    AI_PEER_REVIEW_RESPONSE_ZIP_PREFERRED_NAMES,
    AI_PEER_REVIEW_ZIP_CORRUPT,
    AI_PEER_REVIEW_ZIP_NO_RESPONSE,
    AI_PEER_REVIEW_ZIP_SIZE_EXCEEDED,
)

_SUPPORTED_SUFFIXES = {".json", ".txt"}


class AiPeerReviewZipLoadError(ValueError):
    """Chyba při načítání odpovědi ze ZIP archivu."""


@dataclass(frozen=True)
class AiPeerReviewZipDiscovery:
    """Nalezené soubory odpovědi v ZIP archivu."""

    entries: tuple[str, ...]
    auto_entry: str | None


@dataclass(frozen=True)
class AiPeerReviewZipLoadResult:
    """Obsah vybraného souboru odpovědi ze ZIP."""

    text: str
    entry_name: str


def discover_zip_response_entries(zip_path: Path) -> AiPeerReviewZipDiscovery:
    """Vrátí kandidáty a případně jediný soubor pro automatické načtení."""
    entries, had_export_files = _list_supported_entries(zip_path)
    if not entries:
        if had_export_files:
            raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_NOT_AI_RESPONSE)
        raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_NO_RESPONSE)
    auto_entry = _pick_auto_entry(entries)
    return AiPeerReviewZipDiscovery(entries=tuple(entries), auto_entry=auto_entry)


def load_response_from_zip(
    zip_path: Path,
    *,
    entry_name: str | None = None,
) -> AiPeerReviewZipLoadResult:
    """
    Načte text odpovědi ze ZIP.

    Pokud entry_name není zadán, použije pravidla automatického výběru.
    Při více kandidátech bez jednoznačné volby vyvolá AiPeerReviewZipLoadError
    s atributem selection_required=True a seznamem entries.
    """
    discovery = discover_zip_response_entries(zip_path)
    selected = entry_name or discovery.auto_entry
    if selected is None:
        error = AiPeerReviewZipLoadError(
            "V ZIP archivu je více podporovaných odpovědí – vyberte soubor."
        )
        error.selection_required = True  # type: ignore[attr-defined]
        error.entries = list(discovery.entries)  # type: ignore[attr-defined]
        raise error
    if selected not in discovery.entries:
        raise AiPeerReviewZipLoadError(
            f"Soubor „{selected}“ v ZIP archivu nebyl nalezen."
        )
    text = _read_zip_entry_text(zip_path, selected)
    return AiPeerReviewZipLoadResult(text=text, entry_name=selected)


def _list_supported_entries(zip_path: Path) -> tuple[list[str], bool]:
    """Vrátí (kandidáti odpovědi, zda ZIP obsahuje soubory exportu zadání)."""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            total_uncompressed = 0
            candidates: list[str] = []
            had_export_files = False
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if not _is_safe_zip_entry(info.filename):
                    continue
                basename = PurePosixPath(info.filename).name.casefold()
                if basename in AI_PEER_REVIEW_EXPORT_RESPONSE_BASENAMES:
                    # RISK-AI-17: export zadání nikdy není odpověď AI.
                    had_export_files = True
                    continue
                suffix = PurePosixPath(info.filename).suffix.casefold()
                if suffix not in _SUPPORTED_SUFFIXES:
                    continue
                file_size = info.file_size
                if file_size < 0:
                    continue
                total_uncompressed += file_size
                if total_uncompressed > AI_PEER_REVIEW_RESPONSE_ZIP_MAX_UNCOMPRESSED_BYTES:
                    raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_SIZE_EXCEEDED)
                candidates.append(info.filename)
    except zipfile.BadZipFile as error:
        raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_CORRUPT) from error
    except OSError as error:
        raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_CORRUPT) from error

    return sorted(candidates, key=_entry_sort_key), had_export_files


def _read_zip_entry_text(zip_path: Path, entry_name: str) -> str:
    if not _is_safe_zip_entry(entry_name):
        raise AiPeerReviewZipLoadError(f"Neplatná cesta v ZIP archivu: {entry_name}")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            info = zf.getinfo(entry_name)
            if info.file_size > AI_PEER_REVIEW_RESPONSE_ZIP_MAX_UNCOMPRESSED_BYTES:
                raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_SIZE_EXCEEDED)
            raw = zf.read(entry_name)
    except KeyError as error:
        raise AiPeerReviewZipLoadError(
            f"Soubor „{entry_name}“ v ZIP archivu nebyl nalezen."
        ) from error
    except zipfile.BadZipFile as error:
        raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_CORRUPT) from error
    except OSError as error:
        raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_CORRUPT) from error

    if len(raw) > AI_PEER_REVIEW_RESPONSE_ZIP_MAX_UNCOMPRESSED_BYTES:
        raise AiPeerReviewZipLoadError(AI_PEER_REVIEW_ZIP_SIZE_EXCEEDED)

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise AiPeerReviewZipLoadError(
            f"Soubor „{entry_name}“ nelze načíst jako UTF-8 text."
        ) from error


def _pick_auto_entry(entries: list[str]) -> str | None:
    for preferred_name in AI_PEER_REVIEW_RESPONSE_ZIP_PREFERRED_NAMES:
        matches = [
            entry
            for entry in entries
            if PurePosixPath(entry).name.casefold() == preferred_name.casefold()
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None

    json_entries = [
        entry for entry in entries if PurePosixPath(entry).suffix.casefold() == ".json"
    ]
    txt_entries = [
        entry for entry in entries if PurePosixPath(entry).suffix.casefold() == ".txt"
    ]
    if len(json_entries) == 1 and not txt_entries:
        return json_entries[0]
    if len(txt_entries) == 1 and not json_entries:
        return txt_entries[0]
    if len(entries) == 1:
        return entries[0]
    return None


def _entry_sort_key(entry: str) -> tuple[int, str]:
    basename = PurePosixPath(entry).name.casefold()
    for index, preferred in enumerate(AI_PEER_REVIEW_RESPONSE_ZIP_PREFERRED_NAMES):
        if basename == preferred.casefold():
            return index, entry.casefold()
    suffix = PurePosixPath(entry).suffix.casefold()
    tier = 10 if suffix == ".json" else 11
    return tier, entry.casefold()


def _is_safe_zip_entry(name: str) -> bool:
    if not name or name.startswith(("/", "\\")):
        return False
    path = PurePosixPath(name)
    if any(part in {"..", ""} for part in path.parts):
        return False
    suffix = path.suffix.casefold()
    if suffix == ".zip":
        return False
    return True
