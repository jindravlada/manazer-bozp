"""Nativní systémový výběr složky s českým Qt fallbackem.

V AppImage (frozen) se před QApplication nastaví platform theme
``xdgdesktopportal``, aby Qt použilo hostitelský XDG Desktop Portal
(GNOME, KDE i další prostředí). Source run se nemění.

Pokud portál není dostupný, env se nenastaví a Qt použije interní dialog
s českými překlady z AUDIT-UX-QT-CZ-1.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFileDialog, QWidget

logger = logging.getLogger(__name__)

PHOTO_FOLDER_DIALOG_TITLE = "Vybrat složku s fotografiemi"
PORTAL_PLATFORM_THEME = "xdgdesktopportal"
PORTAL_BUS_NAME = "org.freedesktop.portal.Desktop"
_HEADLESS_PLATFORMS = frozenset(
    {"offscreen", "minimal", "minimalegl", "vnc", "linuxfb"}
)
_PORTAL_PROBE_TIMEOUT_MS = 200


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def prefers_native_folder_dialog(options: QFileDialog.Option) -> bool:
    return not bool(options & QFileDialog.Option.DontUseNativeDialog)


def native_folder_dialog_options() -> QFileDialog.Option:
    """Jen výběr jedné složky; nativní dialog se nevypíná."""
    return QFileDialog.Option.ShowDirsOnly


def xdg_desktop_portal_available(*, timeout_ms: int = _PORTAL_PROBE_TIMEOUT_MS) -> bool:
    """Rychlá kontrola, že session bus nabízí File Chooser portál.

    Nepoužívá vlastní DBus file chooser – jen NameHasOwner s krátkým timeoutem,
    aby nastavení theme nečekalo na výchozí ~25 s DBus timeout Qt.
    """
    if not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
        runtime = os.environ.get("XDG_RUNTIME_DIR")
        if not runtime or not (Path(runtime) / "bus").exists():
            return False

    commands = (
        [
            "dbus-send",
            "--session",
            "--print-reply",
            f"--reply-timeout={timeout_ms}",
            "--dest=org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus.NameHasOwner",
            f"string:{PORTAL_BUS_NAME}",
        ],
        [
            "busctl",
            "--user",
            f"--timeout={max(timeout_ms / 1000.0, 0.05):.2f}",
            "status",
            PORTAL_BUS_NAME,
        ],
    )
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=(timeout_ms / 1000.0) + 0.4,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
        if result.returncode != 0:
            continue
        if command[0] == "dbus-send":
            return "boolean true" in result.stdout.lower()
        return True
    return False


def _qpa_platform() -> str:
    return os.environ.get("QT_QPA_PLATFORM") or ""


def configure_native_folder_dialogs() -> None:
    """Před ``QApplication``: v AppImage preferovat XDG Desktop Portal.

    Nemění ``QT_QPA_PLATFORM`` (Wayland/X11) ani již nastavený
    ``QT_QPA_PLATFORMTHEME``.
    """
    existing_theme = os.environ.get("QT_QPA_PLATFORMTHEME") or ""
    platform = _qpa_platform()
    frozen = is_frozen_app()
    portal = False if platform in _HEADLESS_PLATFORMS else xdg_desktop_portal_available()
    logger.info(
        "native-dialog-config frozen=%s qpa_platform=%s qpa_platformtheme=%s "
        "session=%s desktop=%s gtk_use_portal=%s style_override=%s portal=%s",
        frozen,
        platform or "(unset)",
        existing_theme or "(unset)",
        os.environ.get("XDG_SESSION_TYPE") or "(unset)",
        os.environ.get("XDG_CURRENT_DESKTOP") or "(unset)",
        os.environ.get("GTK_USE_PORTAL") or "(unset)",
        os.environ.get("QT_STYLE_OVERRIDE") or "(unset)",
        portal,
    )
    if existing_theme:
        return
    if platform in _HEADLESS_PLATFORMS:
        logger.info("native-dialog-config headless; Qt widget fallback")
        return
    if not frozen:
        logger.info("native-dialog-config source-run; keep desktop platform theme")
        return
    if not portal:
        logger.info("native-dialog-config portal unavailable; Qt widget fallback")
        return
    os.environ["QT_QPA_PLATFORMTHEME"] = PORTAL_PLATFORM_THEME
    logger.info("native-dialog-config set platformtheme=%s", PORTAL_PLATFORM_THEME)


def _log_folder_dialog(kind: str, title: str, options: QFileDialog.Option) -> None:
    app = QGuiApplication.instance()
    platform_name = app.platformName() if app is not None else "(no-app)"
    logger.info(
        "folder-dialog kind=%s native_preferred=%s title_cs=%s platform=%s "
        "platformtheme=%s frozen=%s session=%s",
        kind,
        prefers_native_folder_dialog(options),
        title == PHOTO_FOLDER_DIALOG_TITLE,
        platform_name,
        os.environ.get("QT_QPA_PLATFORMTHEME") or "(unset)",
        is_frozen_app(),
        os.environ.get("XDG_SESSION_TYPE") or "(unset)",
    )


def choose_existing_directory(
    parent: QWidget | None,
    caption: str = PHOTO_FOLDER_DIALOG_TITLE,
    directory: str = "",
) -> str:
    """Vybere jednu složku. Nativní dialog má přednost, Qt dialog je fallback."""
    options = native_folder_dialog_options()
    _log_folder_dialog("prefer-native", caption, options)
    try:
        selected = QFileDialog.getExistingDirectory(parent, caption, directory, options)
    except Exception:
        logger.warning(
            "Nativní výběr složky selhal, používám český Qt dialog.",
            exc_info=True,
        )
        options = (
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog
        )
        _log_folder_dialog("qt-fallback", caption, options)
        selected = QFileDialog.getExistingDirectory(parent, caption, directory, options)
    return selected or ""
