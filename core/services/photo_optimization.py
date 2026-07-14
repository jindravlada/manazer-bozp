"""Optimalizace fotografií pro úložiště (orientace EXIF, bez metadat, limit velikosti)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageOps, ExifTags

MAX_PHOTO_DIMENSION = 1920
TARGET_MAX_BYTES = 500 * 1024
HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES = 1 * 1024 * 1024
INITIAL_JPEG_QUALITY = 85
MIN_JPEG_QUALITY = 40


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

    tag_map = {ExifTags.TAGS.get(key, key): value for key, value in exif.items()}
    raw = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
    if not raw or not isinstance(raw, str):
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y:%m:%d %H:%M"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def optimize_photo_for_storage(
    source_path: Path,
    *,
    max_bytes: int = TARGET_MAX_BYTES,
    max_dimension: int = MAX_PHOTO_DIMENSION,
) -> OptimizedPhotoResult:
    """
    Opraví orientaci podle EXIF, odstraní metadata a zmenší soubor pod max_bytes.
    Výstup je vždy JPEG bez EXIF.
    """
    with Image.open(source_path) as image:
        taken_at = _exif_taken_at(image)
        prepared = ImageOps.exif_transpose(image)
        prepared = prepared.convert("RGB")

        dimension = max_dimension
        while dimension >= 320:
            working = prepared.copy()
            working.thumbnail((dimension, dimension), Image.Resampling.LANCZOS)

            quality = INITIAL_JPEG_QUALITY
            best_data = b""
            while quality >= MIN_JPEG_QUALITY:
                buffer = io.BytesIO()
                # Bez exif= — metadata se nezapisují.
                working.save(buffer, format="JPEG", quality=quality, optimize=True)
                data = buffer.getvalue()
                best_data = data
                if len(data) <= max_bytes:
                    return OptimizedPhotoResult(
                        data=data,
                        width=working.width,
                        height=working.height,
                        taken_at=taken_at,
                    )
                quality -= 5

            prepared = working
            dimension = int(dimension * 0.75)

        # Poslední pokus — vrať nejmenší dosažený výsledek i kdyby přesáhl limit
        # (v praxi by se sem nemělo dojít při rozumném vstupu).
        buffer = io.BytesIO()
        prepared.save(buffer, format="JPEG", quality=MIN_JPEG_QUALITY, optimize=True)
        data = buffer.getvalue()
        return OptimizedPhotoResult(
            data=data,
            width=prepared.width,
            height=prepared.height,
            taken_at=taken_at,
        )


def optimize_image_bytes(source_path: Path) -> bytes:
    """Zpětná kompatibilita – výstup JPEG ≤ 500 KB."""
    return optimize_photo_for_storage(
        source_path,
        max_bytes=TARGET_MAX_BYTES,
        max_dimension=MAX_PHOTO_DIMENSION,
    ).data
