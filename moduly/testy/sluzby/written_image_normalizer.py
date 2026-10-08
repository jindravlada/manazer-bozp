"""Normalizace obrázků písemných otázek.

Stejná pravidla pro zadání i odpovědi A/B/C. Originální soubor uživatele
se jen čte. Výsledek je nový soubor v předaném adresáři.

Každý přijatý obrázek se dekóduje a znovu zakóduje. Do uloženého souboru
se nedostanou původní bajty, EXIF, GPS, komentáře ani data za koncem
obrázku. Formáty odpovídají PhotoPickerDialog: jpg, jpeg, png, webp,
heic, heif.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_STORED_BYTES = 500 * 1024
MAX_WIDTH = 800
MAX_HEIGHT = 600

SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"})

IMAGE_TOO_LARGE = (
    "Obrázek je příliš velký. Maximální velikost vstupního souboru je 20 MB."
)
IMAGE_CANNOT_STORE = (
    "Obrázek se nepodařilo uložit v použitelné kvalitě. "
    "Maximální velikost uloženého souboru je 500 kB."
)
IMAGE_LOAD_FAILED = "Obrázek se nepodařilo načíst."
IMAGE_UNSUPPORTED = "Obrázek není v podporovaném formátu."

_JPEG_QUALITIES = (90, 85, 80, 75)
_SHRINK_FACTORS = (1.0, 0.85, 0.7)


class WrittenImageError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedWrittenImage:
    path: Path
    width: int
    height: int
    byte_size: int


def assert_input_within_limit(path: Path) -> None:
    """Velikost souboru dřív, než se obrázek otevře."""
    try:
        size = Path(path).stat().st_size
    except OSError as exc:
        raise WrittenImageError(IMAGE_LOAD_FAILED) from exc
    if size > MAX_INPUT_BYTES:
        raise WrittenImageError(IMAGE_TOO_LARGE)


def fit_within_box(
    width: int,
    height: int,
    *,
    max_width: int = MAX_WIDTH,
    max_height: int = MAX_HEIGHT,
) -> tuple[int, int]:
    """Vrátí rozměry uvnitř boxu. Menší obrázek nezvětší a nedeformuje."""
    if width <= 0 or height <= 0:
        raise WrittenImageError(IMAGE_LOAD_FAILED)
    if width <= max_width and height <= max_height:
        return width, height
    scale = min(max_width / width, max_height / height)
    fitted_width = max(1, int(width * scale))
    fitted_height = max(1, int(height * scale))
    if fitted_width > max_width:
        fitted_width = max_width
    if fitted_height > max_height:
        fitted_height = max_height
    return fitted_width, fitted_height


def normalize_written_image(
    source: Path,
    destination_dir: Path,
    *,
    max_stored_bytes: int = MAX_STORED_BYTES,
) -> NormalizedWrittenImage:
    """Vytvoří normalizovanou kopii. ``source`` se nemění."""
    file_path = Path(source)
    if not file_path.is_file():
        raise WrittenImageError(IMAGE_LOAD_FAILED)
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise WrittenImageError(IMAGE_UNSUPPORTED)
    assert_input_within_limit(file_path)

    limit = max(1, int(max_stored_bytes))
    signature = _file_signature(file_path)
    suffix = file_path.suffix.lower()
    image = _decode_pixels(file_path)
    _assert_unchanged(file_path, signature)
    data, suffix = _encode(image, suffix, limit)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    target = destination_dir / f"written-{uuid.uuid4().hex}{suffix}"
    target.write_bytes(data)
    try:
        _assert_unchanged(file_path, signature)
    except WrittenImageError:
        target.unlink(missing_ok=True)
        raise
    with Image.open(target) as stored:
        width, height = stored.size
    return NormalizedWrittenImage(
        path=target,
        width=width,
        height=height,
        byte_size=len(data),
    )


def _file_signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def _assert_unchanged(path: Path, signature: tuple[int, int]) -> None:
    if _file_signature(path) != signature:
        raise WrittenImageError(IMAGE_LOAD_FAILED)


def _decode_pixels(path: Path) -> Image.Image:
    """Složí jen obrazové body. Metadata ani bajty za koncem souboru nevrací."""
    try:
        with Image.open(path) as opened:
            transposed = ImageOps.exif_transpose(opened) or opened
            transposed.load()
            image = _pixels_only(transposed)
    except Exception as exc:
        raise WrittenImageError(IMAGE_LOAD_FAILED) from exc
    width, height = fit_within_box(image.width, image.height)
    if (width, height) != (image.width, image.height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return image


def _pixels_only(image: Image.Image) -> Image.Image:
    """Nový obrázek bez EXIF, komentářů, profilu a ostatních metadat."""
    prepared = _apply_embedded_profile(image)
    if _needs_alpha(prepared):
        raster = prepared.convert("RGBA")
    elif prepared.mode in {"RGB", "L"}:
        raster = prepared
    else:
        raster = prepared.convert("RGB")
    return Image.frombytes(raster.mode, raster.size, raster.tobytes())


def _needs_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA", "PA", "RGBa"} or "transparency" in image.info


def _apply_embedded_profile(image: Image.Image) -> Image.Image:
    profile = image.info.get("icc_profile")
    if not profile:
        return image
    try:
        from PIL import ImageCms

        source = ImageCms.ImageCmsProfile(io.BytesIO(profile))
        target = ImageCms.createProfile("sRGB")
        output_mode = "RGBA" if _needs_alpha(image) else "RGB"
        converted = ImageCms.profileToProfile(
            image,
            source,
            target,
            outputMode=output_mode,
        )
    except Exception:
        return image
    return converted or image


def _encode(image: Image.Image, suffix: str, limit: int) -> tuple[bytes, str]:
    if suffix == ".png" or _has_partial_alpha(image):
        png = _png_bytes(image)
        if len(png) <= limit:
            return png, ".png"
        if _has_partial_alpha(image):
            shrunk = _smallest_fitting_png(image, limit)
            if shrunk is not None:
                return shrunk, ".png"
            raise WrittenImageError(IMAGE_CANNOT_STORE)
    if suffix == ".webp" and not _has_partial_alpha(image):
        webp = _lossy_within_limit(image.convert("RGB"), limit, fmt="WEBP")
        if webp is not None:
            return webp, ".webp"
    jpeg = _lossy_within_limit(image.convert("RGB"), limit, fmt="JPEG")
    if jpeg is not None:
        return jpeg, ".jpg"
    if suffix == ".png":
        shrunk_png = _smallest_fitting_png(image, limit)
        if shrunk_png is not None:
            return shrunk_png, ".png"
    raise WrittenImageError(IMAGE_CANNOT_STORE)


def _has_partial_alpha(image: Image.Image) -> bool:
    if image.mode != "RGBA":
        return False
    low, _high = image.getchannel("A").getextrema()
    return int(low) < 255


def _png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _smallest_fitting_png(image: Image.Image, limit: int) -> bytes | None:
    working = image
    for factor in _SHRINK_FACTORS:
        candidate = working if factor == 1.0 else _scaled(image, factor)
        data = _png_bytes(candidate)
        if len(data) <= limit:
            return data
    return None


def _lossy_within_limit(image: Image.Image, limit: int, *, fmt: str) -> bytes | None:
    rgb = image.convert("RGB")
    for factor in _SHRINK_FACTORS:
        candidate = rgb if factor == 1.0 else _scaled(rgb, factor)
        for quality in _JPEG_QUALITIES:
            data = _lossy_bytes(candidate, fmt=fmt, quality=quality)
            if data is not None and len(data) <= limit:
                return data
    return None


def _lossy_bytes(image: Image.Image, *, fmt: str, quality: int) -> bytes | None:
    buffer = io.BytesIO()
    try:
        image.save(buffer, format=fmt, quality=quality, optimize=True)
    except Exception:
        return None
    return buffer.getvalue()


def _scaled(image: Image.Image, factor: float) -> Image.Image:
    width = max(1, int(image.width * factor))
    height = max(1, int(image.height * factor))
    if (width, height) == (image.width, image.height):
        return image
    return image.resize((width, height), Image.Resampling.LANCZOS)
