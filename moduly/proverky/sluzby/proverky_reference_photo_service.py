import re
from pathlib import Path

from core.services.photo_optimization import optimize_image_bytes
from core.utils.confined_path import resolve_confined_path
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service

_PHOTOS_DIR = "fotografie"


class ProverkyReferencePhotoService:
    """Optimalizace a ukládání referenčních fotografií metodických karet."""

    def photos_dir(self) -> Path:
        path = proverky_knowledge_service.proverky_dir / _PHOTOS_DIR
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_photo_path(self, area_id: str, section_id: str, photo_id: str) -> str:
        filename = self._build_filename(area_id, section_id, photo_id)
        return f"{_PHOTOS_DIR}/{area_id}/{section_id}/{filename}"

    def absolute_photo_path(self, relative_path: str) -> Path:
        confined = self._resolve_photo_path(relative_path)
        return confined if confined is not None else Path()

    def save_optimized(
        self,
        source_path: Path,
        *,
        area_id: str,
        section_id: str,
        photo_id: str,
    ) -> str:
        relative_path = self.relative_photo_path(area_id, section_id, photo_id)
        target = self._resolve_photo_path(relative_path)
        if target is None:
            raise ValueError("Cesta fotografie je mimo adresář metodiky prověrek.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(optimize_image_bytes(source_path))
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
        return resolve_confined_path(proverky_knowledge_service.proverky_dir, raw)

    @staticmethod
    def _build_filename(area_id: str, section_id: str, photo_id: str) -> str:
        parts = [area_id, section_id, photo_id]
        slug = "_".join(part.strip() for part in parts if part.strip())
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug).strip("_") or "photo"
        return f"{slug}.jpg"


proverky_reference_photo_service = ProverkyReferencePhotoService()
