import re
from pathlib import Path

from core.services.photo_optimization import optimize_image_bytes
from core.services.storage_service import storage_service


class ControlResultPhotoService:
    """Optimalizace a ukládání fotografií kontrolních bodů."""

    def storage_root(self) -> Path:
        path = storage_service.base / "control_results"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_photo_path(
        self,
        entity_type: str,
        entity_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> str:
        filename = self._build_filename(area_id, section_id, control_point_id)
        return f"control_results/{entity_type}/{entity_id}/{filename}"

    def absolute_photo_path(self, relative_path: str) -> Path:
        if not relative_path:
            return Path()
        return storage_service.base / relative_path

    def save_optimized(
        self,
        source_path: Path,
        *,
        entity_type: str,
        entity_id: int,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> str:
        relative_path = self.relative_photo_path(
            entity_type,
            entity_id,
            area_id=area_id,
            section_id=section_id,
            control_point_id=control_point_id,
        )
        target = self.absolute_photo_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        optimized = optimize_image_bytes(source_path)
        target.write_bytes(optimized)
        return relative_path

    def delete_photo(self, relative_path: str) -> None:
        if not relative_path:
            return

        path = self.absolute_photo_path(relative_path)
        if path.is_file():
            path.unlink()

    @staticmethod
    def _build_filename(area_id: str, section_id: str, control_point_id: str) -> str:
        parts = [area_id, section_id, control_point_id, "photo"]
        slug = "_".join(part.strip() for part in parts if part.strip())
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug).strip("_") or "photo"
        return f"{slug}.jpg"


control_result_photo_service = ControlResultPhotoService()
