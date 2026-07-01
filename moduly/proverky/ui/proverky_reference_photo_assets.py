from pathlib import Path


def reference_photo_placeholder_path() -> Path:
    return Path(__file__).resolve().parent.parent / "resources" / "under_construction_placeholder.png"
