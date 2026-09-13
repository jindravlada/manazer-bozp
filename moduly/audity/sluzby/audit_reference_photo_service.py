import re
from pathlib import Path

from core.services.photo_optimization import (
    optimize_image_bytes,
    write_internal_photo_bytes,
)
from core.utils.confined_path import resolve_confined_path
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

_PHOTOS_DIR = "fotografie"
_SNAPSHOT_PREFIX = "snapshot_support_photos/"


class AuditReferencePhotoService:
    """Optimalizace a ukládání referenčních fotografií auditovaných procesů."""

    def photos_dir(self) -> Path:
        path = audit_knowledge_service.audity_dir / _PHOTOS_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_photo_path(self, process_id: str, criterion_id: str, photo_id: str) -> str:
        filename = self._build_filename(process_id, criterion_id, photo_id)
        return f"{_PHOTOS_DIR}/{process_id}/{criterion_id}/{filename}"

    def absolute_photo_path(self, relative_path: str) -> Path:
        confined = self._resolve_photo_path(relative_path)
        return confined if confined is not None else Path()

    def save_optimized(
        self,
        source_path: Path,
        *,
        process_id: str,
        criterion_id: str,
        photo_id: str,
    ) -> str:
        relative_path = self.relative_photo_path(process_id, criterion_id, photo_id)
        target = self._resolve_photo_path(relative_path)
        if target is None:
            raise ValueError("Cesta fotografie je mimo adresář metodiky auditů.")
        write_internal_photo_bytes(target, optimize_image_bytes(source_path))
        return relative_path

    def delete_photo(self, relative_path: str) -> None:
        if not relative_path:
            return

        path = self._resolve_photo_path(relative_path)
        if path is None:
            return
        if path.is_file() or path.is_symlink():
            path.unlink()

    def _resolve_photo_path(self, relative_path: str) -> Path | None:
        raw = str(relative_path or "").strip().replace("\\", "/")
        if not raw:
            return None
        if raw.startswith(_SNAPSHOT_PREFIX):
            from core.services.storage_service import storage_service

            remainder = raw[len(_SNAPSHOT_PREFIX) :]
            root = storage_service.base / "snapshot_support_photos"
            return resolve_confined_path(root, remainder)
        return resolve_confined_path(audit_knowledge_service.audity_dir, raw)

    @staticmethod
    def _build_filename(process_id: str, criterion_id: str, photo_id: str) -> str:
        parts = [process_id, criterion_id, photo_id]
        slug = "_".join(part.strip() for part in parts if part.strip())
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug).strip("_") or "photo"
        return f"{slug}.jpg"


audit_reference_photo_service = AuditReferencePhotoService()
