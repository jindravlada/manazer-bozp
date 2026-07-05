from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

_ICON_FILENAME = "manager_bozp.ico"


def app_icon_path() -> Path | None:
    path = Path(__file__).resolve().parent / _ICON_FILENAME
    return path if path.is_file() else None


def load_app_icon() -> QIcon:
    path = app_icon_path()
    if path is None:
        return QIcon()

    icon = QIcon(str(path))
    return icon if not icon.isNull() else QIcon()


def load_app_pixmap(size: int = 40) -> QPixmap:
    icon = load_app_icon()
    if icon.isNull():
        return QPixmap()

    pixmap = icon.pixmap(size, size, QIcon.Mode.Normal, QIcon.State.Off)
    if pixmap.isNull():
        return QPixmap()

    return pixmap.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
