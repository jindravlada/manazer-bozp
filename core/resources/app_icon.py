import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

_ICON_BASENAMES = ("manager_bozp.png", "manager_bozp.ico")


def _resource_dirs() -> list[Path]:
    dirs: list[Path] = []

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        dirs.extend(
            (
                meipass / "core" / "resources",
                meipass / "resources",
            )
        )

    dirs.append(Path(__file__).resolve().parent)

    unique_dirs: list[Path] = []
    seen: set[Path] = set()
    for directory in dirs:
        resolved = directory.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_dirs.append(resolved)

    return unique_dirs


def app_icon_path() -> Path | None:
    for directory in _resource_dirs():
        for basename in _ICON_BASENAMES:
            path = directory / basename
            if path.is_file():
                return path
    return None


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
