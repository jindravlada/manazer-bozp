from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def app_icon_path() -> Path | None:
    root = _project_root()
    for candidate in (root / "AppDir" / "manazer-bozp.png", root / "manager_bozp.ico"):
        if candidate.is_file():
            return candidate
    return None


def load_app_icon() -> QIcon:
    path = app_icon_path()
    if path is None:
        return QIcon()
    return QIcon(str(path))


def load_app_pixmap(size: int = 40) -> QPixmap:
    path = app_icon_path()
    if path is None:
        return QPixmap()

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return QPixmap()

    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
