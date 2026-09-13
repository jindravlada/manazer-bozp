"""Služba fotodokumentace identifikace rizik."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from pathlib import Path

from PIL import Image

from core.services.photo_optimization import (
    HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES,
    OptimizedPhotoResult,
    optimize_photo_for_storage,
)
from core.services.storage_service import storage_service
from core.utils.confined_path import resolve_confined_path
from moduly.rizeni_rizik.modely.hazard_identification_photo import HazardIdentificationPhoto
from moduly.rizeni_rizik.repository.hazard_identification_photo_repository import (
    HazardIdentificationPhotoRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)

ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class HazardIdentificationPhotoError(ValueError):
    pass


class HazardIdentificationPhotoService:
    def __init__(self):
        self.repository = HazardIdentificationPhotoRepository()

    def get_for_identification(
        self,
        hazard_identification_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[HazardIdentificationPhoto]:
        return self.repository.get_for_identification(
            hazard_identification_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, photo_id: int | None) -> HazardIdentificationPhoto | None:
        if not photo_id:
            return None
        return self.repository.get_by_id(photo_id)

    def absolute_path(self, photo: HazardIdentificationPhoto) -> Path:
        confined = resolve_confined_path(
            storage_service.attachments_dir, photo.relative_path
        )
        return confined if confined is not None else Path()

    def file_exists(self, photo: HazardIdentificationPhoto) -> bool:
        return self.absolute_path(photo).is_file()

    def peek_taken_at(self, source_path: str | Path) -> datetime | None:
        """Přečte datum pořízení z EXIF bez uložení souboru."""
        source = Path(source_path)
        if not source.is_file():
            return None
        try:
            with Image.open(source) as image:
                from core.services.photo_optimization import _exif_taken_at

                return _exif_taken_at(image)
        except Exception:
            return None

    def create_photo(
        self,
        *,
        hazard_identification_id: int,
        source_path: str | Path,
        caption: str = "",
        note: str = "",
        taken_at: date | datetime | None = None,
        active: bool = True,
    ) -> HazardIdentificationPhoto:
        identification = hazard_identification_service.get_by_id(hazard_identification_id)
        if identification is None:
            raise HazardIdentificationPhotoError("Identifikace nebezpečí neexistuje.")

        source = Path(source_path)
        if not source.is_file():
            raise HazardIdentificationPhotoError("Vybraný soubor neexistuje.")

        suffix = source.suffix.lower()
        if suffix not in ALLOWED_PHOTO_EXTENSIONS:
            raise HazardIdentificationPhotoError(
                "Podporované formáty fotografií jsou JPG, JPEG, PNG a WEBP."
            )

        optimized = self._optimize(source)

        identification_number = identification.identification_number or str(
            identification.id
        )
        relative_dir = (
            Path("rizeni_rizik")
            / self._safe_folder_name(identification_number)
            / "fotografie"
        )
        stored_filename = (
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        )
        relative_path = relative_dir / stored_filename
        try:
            absolute = storage_service.attachment_absolute(str(relative_path))
        except ValueError as exc:
            raise HazardIdentificationPhotoError(
                "Cesta fotografie je mimo úložiště příloh."
            ) from exc
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(optimized.data)

        resolved_taken_at = self._normalize_taken_at(taken_at)
        if resolved_taken_at is None and optimized.taken_at is not None:
            resolved_taken_at = optimized.taken_at

        photo = HazardIdentificationPhoto(
            hazard_identification_id=hazard_identification_id,
            filename=source.name,
            stored_filename=stored_filename,
            relative_path=str(relative_path).replace("\\", "/"),
            caption=(caption or "").strip(),
            note=(note or "").strip(),
            taken_at=resolved_taken_at,
            file_size=len(optimized.data),
            width=optimized.width,
            height=optimized.height,
            active=active,
            sort_order=self.repository.next_sort_order(hazard_identification_id),
        )
        return self.repository.add(photo)

    def update_photo(
        self,
        photo_id: int,
        *,
        hazard_identification_id: int,
        caption: str = "",
        note: str = "",
        taken_at: date | datetime | None = None,
        active: bool = True,
    ) -> HazardIdentificationPhoto | None:
        photo = self.repository.get_by_id(photo_id)
        if photo is None:
            return None
        if photo.hazard_identification_id != hazard_identification_id:
            raise HazardIdentificationPhotoError(
                "Fotografie nepatří k aktuální identifikaci."
            )
        photo.caption = (caption or "").strip()
        photo.note = (note or "").strip()
        photo.taken_at = self._normalize_taken_at(taken_at)
        photo.active = active
        photo.updated_at = datetime.now()
        return self.repository.update(photo)

    def activate_photo(self, photo_id: int) -> bool:
        photo = self.repository.get_by_id(photo_id)
        if photo is None:
            return False
        photo.active = True
        photo.updated_at = datetime.now()
        self.repository.update(photo)
        return True

    def deactivate_photo(self, photo_id: int) -> bool:
        photo = self.repository.get_by_id(photo_id)
        if photo is None:
            return False
        photo.active = False
        photo.updated_at = datetime.now()
        self.repository.update(photo)
        return True

    def _optimize(self, source: Path) -> OptimizedPhotoResult:
        try:
            optimized = optimize_photo_for_storage(
                source,
                max_bytes=HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES,
            )
        except OSError as error:
            raise HazardIdentificationPhotoError(
                f"Soubor se nepodařilo načíst jako obrázek: {error}"
            ) from error
        except Exception as error:
            raise HazardIdentificationPhotoError(
                f"Soubor se nepodařilo zpracovat jako fotografii: {error}"
            ) from error

        if len(optimized.data) > HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES:
            raise HazardIdentificationPhotoError(
                "Fotografii se nepodařilo zmenšit pod 1 MB."
            )
        return optimized

    @staticmethod
    def _safe_folder_name(value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", (value or "").strip())
        return cleaned.strip("._") or "bez_cisla"

    @staticmethod
    def _normalize_taken_at(value: date | datetime | None) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        return None


hazard_identification_photo_service = HazardIdentificationPhotoService()
