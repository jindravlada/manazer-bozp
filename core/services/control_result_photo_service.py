import re
from pathlib import Path

from core.services.photo_optimization import optimize_image_bytes
from core.services.storage_service import storage_service
from core.utils.confined_path import resolve_confined_path


_CONTROL_RESULTS_PREFIX = "control_results/"


class ControlResultPhotoService:
    """Optimalizace a ukládání fotografií kontrolních bodů."""

    def storage_root(self) -> Path:
        path = storage_service.control_results_dir
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
        confined = self._resolve_photo_path(relative_path)
        return confined if confined is not None else Path()

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
        target = self._resolve_photo_path(relative_path)
        if target is None:
            raise ValueError("Cesta fotografie je mimo adresář control_results.")
        target.parent.mkdir(parents=True, exist_ok=True)

        optimized = optimize_image_bytes(source_path)
        target.write_bytes(optimized)
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
        if raw.startswith(_CONTROL_RESULTS_PREFIX):
            raw = raw[len(_CONTROL_RESULTS_PREFIX) :]
        elif raw == "control_results":
            return None
        return resolve_confined_path(self.storage_root(), raw)

    @staticmethod
    def _build_filename(area_id: str, section_id: str, control_point_id: str) -> str:
        parts = [area_id, section_id, control_point_id, "photo"]
        slug = "_".join(part.strip() for part in parts if part.strip())
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug).strip("_") or "photo"
        return f"{slug}.jpg"


control_result_photo_service = ControlResultPhotoService()
