"""Optimalizace fotografií pro interní úložiště (EXIF/GPS, Orientation=1, limit velikosti)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, ExifTags
from PIL.ExifTags import IFD

MAX_PHOTO_DIMENSION = 1920
TARGET_MAX_BYTES = 500 * 1024
INTERNAL_PHOTO_MAX_BYTES = 1 * 1024 * 1024
HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES = INTERNAL_PHOTO_MAX_BYTES
INITIAL_JPEG_QUALITY = 85
MIN_JPEG_QUALITY = 40
_EXIF_ORIENTATION = 274
_EXIF_DATETIME_ORIGINAL = 36867
_EXIF_DATETIME_DIGITIZED = 36868
_EXIF_DATETIME = 306

PHOTO_OPTIMIZATION_FAILED = (
    "Fotografii se nepodařilo zmenšit na povolenou velikost."
)


class PhotoOptimizationError(Exception):
    """Nelze vytvořit platnou novou interní fotografii v limitu velikosti."""


@dataclass(frozen=True)
class OptimizedPhotoResult:
    data: bytes
    width: int
    height: int
    taken_at: datetime | None


def _exif_taken_at(image: Image.Image) -> datetime | None:
    try:
        exif = image.getexif()
    except Exception:
        return None
    if not exif:
        return None

    raw = None
    try:
        nested = exif.get_ifd(IFD.Exif)
        raw = nested.get(_EXIF_DATETIME_ORIGINAL) or nested.get(_EXIF_DATETIME_DIGITIZED)
    except Exception:
        raw = None
    if not raw:
        tag_map = {ExifTags.TAGS.get(key, key): value for key, value in exif.items()}
        raw = (
            tag_map.get("DateTimeOriginal")
            or tag_map.get("DateTimeDigitized")
            or tag_map.get("DateTime")
            or exif.get(_EXIF_DATETIME)
        )
    if not raw or not isinstance(raw, str):
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _load_preserved_exif(image: Image.Image):
    """Načte EXIF včetně GPS/Exif IFD, aby se při JPEG save neztratily."""
    try:
        exif = image.getexif()
    except Exception:
        return None
    if not exif:
        return None
    for ifd_id in (IFD.Exif, IFD.GPSInfo, IFD.Interop):
        try:
            exif.get_ifd(ifd_id)
        except Exception:
            continue
    return exif


def _encode_jpeg(image, *, quality: int, exif=None, icc=None) -> bytes | None:
    """Vrátí JPEG bajty, nebo None při selhání zápisu."""
    def _save(*, use_exif, use_icc) -> bytes:
        buffer = io.BytesIO()
        kwargs: dict = {
            "format": "JPEG",
            "quality": quality,
            "optimize": True,
        }
        if use_icc and icc:
            kwargs["icc_profile"] = icc
        if use_exif and exif is not None:
            kwargs["exif"] = exif
        image.save(buffer, **kwargs)
        return buffer.getvalue()

    try:
        return _save(use_exif=True, use_icc=True)
    except Exception:
        if not exif and not icc:
            return None
        try:
            return _save(use_exif=False, use_icc=False)
        except Exception:
            return None


def optimize_photo_for_storage(
    source_path: Path,
    *,
    max_bytes: int = TARGET_MAX_BYTES,
    max_dimension: int = MAX_PHOTO_DIMENSION,
) -> OptimizedPhotoResult:
    """
    Opraví orientaci podle EXIF, zachová dostupná metadata a zmenší soubor
    pod ``max_bytes`` (nejvýše ``INTERNAL_PHOTO_MAX_BYTES``).

    Výstup je vždy JPEG. Po transformaci pixelů je Orientation=1.
    Poškozená metadata se zahodí; kvůli nim se nesmí poškodit snímek
    ani překročit limit. Originální soubor se nemění.
    """
    limit = min(max(1, int(max_bytes)), INTERNAL_PHOTO_MAX_BYTES)
    source = Path(source_path)

    try:
        with Image.open(source) as image:
            taken_at = _exif_taken_at(image)
            icc = image.info.get("icc_profile")
            preserved_exif = _load_preserved_exif(image)
            prepared = ImageOps.exif_transpose(image) or image
            prepared = prepared.convert("RGB")
            prepared.load()
            prepared = prepared.copy()
    except PhotoOptimizationError:
        raise
    except Exception as exc:
        raise PhotoOptimizationError(
            f"Soubor se nepodařilo načíst jako fotografii:\n{source}\n\n{exc}"
        ) from exc

    if preserved_exif is not None:
        try:
            preserved_exif[_EXIF_ORIENTATION] = 1
        except Exception:
            preserved_exif = None

    dimension = max_dimension
    last_working = prepared
    while dimension >= 320:
        working = prepared.copy()
        working.thumbnail((dimension, dimension), Image.Resampling.LANCZOS)
        last_working = working

        quality = INITIAL_JPEG_QUALITY
        while quality >= MIN_JPEG_QUALITY:
            data = _encode_jpeg(
                working,
                quality=quality,
                exif=preserved_exif,
                icc=icc,
            )
            if data and len(data) <= limit:
                return OptimizedPhotoResult(
                    data=data,
                    width=working.width,
                    height=working.height,
                    taken_at=taken_at,
                )
            if data and (preserved_exif is not None or icc):
                stripped = _encode_jpeg(
                    working,
                    quality=quality,
                    exif=None,
                    icc=None,
                )
                if stripped and len(stripped) <= limit:
                    return OptimizedPhotoResult(
                        data=stripped,
                        width=working.width,
                        height=working.height,
                        taken_at=taken_at,
                    )
            quality -= 5

        prepared = working
        dimension = int(dimension * 0.75)

    stripped = _encode_jpeg(
        last_working,
        quality=MIN_JPEG_QUALITY,
        exif=None,
        icc=None,
    )
    if stripped and len(stripped) <= limit:
        return OptimizedPhotoResult(
            data=stripped,
            width=last_working.width,
            height=last_working.height,
            taken_at=taken_at,
        )
    raise PhotoOptimizationError(PHOTO_OPTIMIZATION_FAILED)


def write_internal_photo_bytes(target: Path, data: bytes) -> None:
    """Zapíše novou interní fotografii; soubor > 1 MB se nikdy neuloží."""
    if len(data) > INTERNAL_PHOTO_MAX_BYTES:
        raise PhotoOptimizationError(PHOTO_OPTIMIZATION_FAILED)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def optimize_image_bytes(source_path: Path) -> bytes:
    """Zpětná kompatibilita – výstup JPEG ≤ 500 KB (a vždy ≤ 1 MB)."""
    return optimize_photo_for_storage(
        source_path,
        max_bytes=TARGET_MAX_BYTES,
        max_dimension=MAX_PHOTO_DIMENSION,
    ).data
