import re
from pathlib import Path

from core.services.photo_optimization import optimize_image_bytes
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

_PHOTOS_DIR = "fotografie"


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
        if not relative_path:
            return Path()
        rel = str(relative_path).strip()
        if rel.startswith("snapshot_support_photos/"):
            from core.services.storage_service import storage_service

            return storage_service.base / rel
        return audit_knowledge_service.audity_dir / relative_path

    def save_optimized(
        self,
        source_path: Path,
        *,
        process_id: str,
        criterion_id: str,
        photo_id: str,
    ) -> str:
        relative_path = self.relative_photo_path(process_id, criterion_id, photo_id)
        target = self.absolute_photo_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(optimize_image_bytes(source_path))
        return relative_path

    def delete_photo(self, relative_path: str) -> None:
        if not relative_path:
            return

        path = self.absolute_photo_path(relative_path)
        if path.is_file():
            path.unlink()

    @staticmethod
    def _build_filename(process_id: str, criterion_id: str, photo_id: str) -> str:
        parts = [process_id, criterion_id, photo_id]
        slug = "_".join(part.strip() for part in parts if part.strip())
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug).strip("_") or "photo"
        return f"{slug}.jpg"


audit_reference_photo_service = AuditReferencePhotoService()
