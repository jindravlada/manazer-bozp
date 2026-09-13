"""Zmrazení referenčních fotografií metodické podpory (content-addressed)."""

from __future__ import annotations

import hashlib
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

from core.services.storage_service import storage_service
from core.utils.confined_path import resolve_confined_path
from moduly.audity.sluzby.audit_reference_photo_service import (
    audit_reference_photo_service,
)

logger = logging.getLogger(__name__)

SNAPSHOT_SUPPORT_PHOTOS_DIR = "snapshot_support_photos"


class MethodSupportPhotoError(RuntimeError):
    """Chyba při zmrazení referenční fotografie."""


def support_photos_root() -> Path:
    root = storage_service.base / SNAPSHOT_SUPPORT_PHOTOS_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def absolute_support_photo_path(relative_path: str) -> Path:
    rel = str(relative_path or "").strip().replace("\\", "/")
    if not rel:
        return Path()
    prefix = f"{SNAPSHOT_SUPPORT_PHOTOS_DIR}/"
    if rel.startswith(prefix):
        remainder = rel[len(prefix) :]
        confined = resolve_confined_path(
            storage_service.base / SNAPSHOT_SUPPORT_PHOTOS_DIR,
            remainder,
        )
        return confined if confined is not None else Path()
    if rel == SNAPSHOT_SUPPORT_PHOTOS_DIR:
        return Path()
    return audit_reference_photo_service.absolute_photo_path(rel)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def freeze_reference_photos_in_payload(
    payload: dict[str, Any],
    *,
    staging_dir: Path | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    """
    Zkopíruje referenční fotografie do content-addressed úložiště.

    Vrací (upravený payload, seznam staging souborů k pozdějšímu publish).
    Chybějící zdroj → item s missing=True, bez pádu.
    """
    section = payload.get("section")
    if not isinstance(section, dict):
        return payload, []

    photos = section.get("referencni_fotografie")
    if not isinstance(photos, list) or not photos:
        return payload, []

    own_staging = staging_dir is None
    staging = Path(staging_dir) if staging_dir else Path(
        tempfile.mkdtemp(prefix="method-support-photos-")
    )
    staged_files: list[Path] = []
    frozen_photos: list[dict] = []

    try:
        for raw in photos:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            source_rel = str(item.get("soubor") or "").strip()
            if not source_rel:
                item["missing"] = True
                item["soubor"] = ""
                frozen_photos.append(item)
                continue

            source_abs = audit_reference_photo_service.absolute_photo_path(source_rel)
            if source_abs == Path() or not source_abs.is_file():
                item["missing"] = True
                item["source_soubor"] = source_rel
                item["soubor"] = ""
                frozen_photos.append(item)
                continue

            file_hash = _sha256_file(source_abs)
            suffix = source_abs.suffix.lower() or ".jpg"
            if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                suffix = ".jpg"
            relative = f"{SNAPSHOT_SUPPORT_PHOTOS_DIR}/{file_hash[:2]}/{file_hash}{suffix}"
            staging_target = staging / relative
            staging_target.parent.mkdir(parents=True, exist_ok=True)
            if not staging_target.exists():
                shutil.copy2(source_abs, staging_target)
            # ověř hash staging kopie
            if _sha256_file(staging_target) != file_hash:
                raise MethodSupportPhotoError(
                    f"Hash staging fotografie nesouhlasí: {source_rel}"
                )
            staged_files.append(staging_target)
            item["soubor"] = relative
            item["file_sha256"] = file_hash
            item.pop("missing", None)
            item["source_soubor"] = source_rel
            frozen_photos.append(item)

        new_payload = dict(payload)
        new_section = dict(section)
        new_section["referencni_fotografie"] = frozen_photos
        new_payload["section"] = new_section
        return new_payload, staged_files
    except Exception:
        if own_staging and staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        raise


def publish_staged_support_photos(staged_files: list[Path], staging_root: Path) -> None:
    """Přesune ověřené staging soubory do finálního úložiště (dedup podle SHA)."""
    root = support_photos_root()
    for staged in staged_files:
        try:
            relative = staged.relative_to(staging_root)
        except ValueError:
            continue
        final_path = storage_service.base / relative
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if final_path.exists():
            continue
        shutil.copy2(staged, final_path)
        if not final_path.is_file():
            raise MethodSupportPhotoError(f"Nelze zveřejnit fotografii {relative}")


def cleanup_staging(staging_root: Path | None) -> None:
    if staging_root is None:
        return
    path = Path(staging_root)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
