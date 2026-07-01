import io
from pathlib import Path

from PIL import Image, ImageOps

MAX_PHOTO_DIMENSION = 1920
TARGET_MAX_BYTES = 500 * 1024
INITIAL_JPEG_QUALITY = 85
MIN_JPEG_QUALITY = 55


def optimize_image_bytes(source_path: Path) -> bytes:
    with Image.open(source_path) as image:
        prepared = ImageOps.exif_transpose(image)
        prepared = prepared.convert("RGB")
        prepared.thumbnail((MAX_PHOTO_DIMENSION, MAX_PHOTO_DIMENSION), Image.Resampling.LANCZOS)

        quality = INITIAL_JPEG_QUALITY
        best_data = b""
        while quality >= MIN_JPEG_QUALITY:
            buffer = io.BytesIO()
            prepared.save(buffer, format="JPEG", quality=quality, optimize=True)
            data = buffer.getvalue()
            best_data = data
            if len(data) <= TARGET_MAX_BYTES:
                return data
            quality -= 5

        return best_data
