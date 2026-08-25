"""České překlady standardních Qt dialogů (QFileDialog, …)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QTranslator
from PySide6.QtWidgets import QApplication

from core.paths import project_root

logger = logging.getLogger(__name__)

QT_BASE_TRANSLATION = "qtbase_cs.qm"
QT_FILEDIALOG_OVERLAY = "qt_filedialog_cs.qm"
_TRANSLATION_FILENAMES = (QT_BASE_TRANSLATION, QT_FILEDIALOG_OVERLAY)
_BUNDLED_SUBDIR = Path("zdroje") / "preklady"

_installed_translators: list[QTranslator] = []


def qt_translation_search_dirs() -> list[Path]:
    """Adresáře s .qm – bundled zdroje, AppImage ``_MEIPASS``, Qt translations path."""
    dirs: list[Path] = []
    seen: set[Path] = set()

    def add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        if resolved in seen:
            return
        seen.add(resolved)
        dirs.append(path)

    add(project_root() / _BUNDLED_SUBDIR)

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        add(Path(sys._MEIPASS) / _BUNDLED_SUBDIR)

    try:
        qt_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if qt_path:
            add(Path(qt_path))
    except Exception:
        logger.warning("Nepodařilo se zjistit Qt TranslationsPath.", exc_info=True)

    return dirs


def find_qt_translation(filename: str, *, search_dirs: list[Path] | None = None) -> Path | None:
    for directory in search_dirs if search_dirs is not None else qt_translation_search_dirs():
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def installed_qt_translators() -> tuple[QTranslator, ...]:
    return tuple(_installed_translators)


def reset_qt_translators(app: QApplication | None = None) -> None:
    """Odinstaluje dříve načtené Qt překlady (pro testy)."""
    if app is None:
        app = QApplication.instance()
    existing = list(getattr(app, "_manazer_bozp_qt_translators", []) if app is not None else [])
    if app is not None:
        for translator in existing:
            app.removeTranslator(translator)
        app._manazer_bozp_qt_translators = []  # type: ignore[attr-defined]
    _installed_translators.clear()


def install_qt_translators(
    app: QApplication | None = None,
    *,
    search_dirs: list[Path] | None = None,
    force: bool = False,
) -> list[QTranslator]:
    """Načte oficiální český Qt překlad a podrží QTranslator u aplikace.

    Při chybějícím souboru aplikace nespadne – zapíše warning.
    """
    if app is None:
        app = QApplication.instance()
    if app is None:
        logger.warning("QApplication ještě neexistuje, český Qt překlad se nenačetl.")
        return []

    existing = getattr(app, "_manazer_bozp_qt_translators", None)
    if existing and not force:
        return list(existing)
    if force:
        reset_qt_translators(app)

    translators: list[QTranslator] = []
    dirs = search_dirs if search_dirs is not None else qt_translation_search_dirs()

    for filename in _TRANSLATION_FILENAMES:
        path = find_qt_translation(filename, search_dirs=dirs)
        if path is None:
            if filename == QT_BASE_TRANSLATION:
                logger.warning(
                    "Český Qt překlad %s nebyl nalezen. Hledané cesty: %s",
                    filename,
                    ", ".join(str(item) for item in dirs),
                )
            continue

        translator = QTranslator(app)
        if not translator.load(str(path)):
            logger.warning("Nepodařilo se načíst český Qt překlad: %s", path)
            continue

        app.installTranslator(translator)
        translators.append(translator)
        logger.info("Načten český Qt překlad path=%s ok=True", path)

    _installed_translators[:] = translators
    app._manazer_bozp_qt_translators = translators  # type: ignore[attr-defined]
    return translators
