"""UX-DIALOG-1 – jednotný vzhled QMessageBox v celé aplikaci."""

from __future__ import annotations

import re
from typing import cast

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from core.version import APP_NAME, app_display_name

# Rozměry: dost široké pro běžné věty, bez obřích prázdných ploch.
MESSAGE_BOX_MIN_WIDTH = 440
MESSAGE_BOX_MAX_WIDTH = 720
MESSAGE_BOX_SIDE_PADDING = 100  # ikona + okraje kolem textu
MESSAGE_BOX_TITLE_CHROME = 140  # ovládací prvky titulku

_TITLE_APP_SUFFIX_RE = re.compile(
    rf"\s*[—–-]\s*{re.escape(APP_NAME)}(?:\s+\d+(?:\.\d+)*)?\s*$",
    re.IGNORECASE,
)

_BUTTON_LABELS: dict[QMessageBox.StandardButton, str] = {
    QMessageBox.StandardButton.Ok: "OK",
    QMessageBox.StandardButton.Yes: "Ano",
    QMessageBox.StandardButton.No: "Ne",
    QMessageBox.StandardButton.Cancel: "Storno",
    QMessageBox.StandardButton.Abort: "Storno",
    QMessageBox.StandardButton.Close: "Zavřít",
}

# Vlastní české popisky (např. neuložené změny) nepřepisovat.
_CUSTOM_BUTTON_TEXTS = {
    "uložit",
    "neukládat",
    "zahodit",
    "zůstat",
    "zrušit",
    "ano, obnovit",
    "přejít",
    "správa dat",
}

_original_information = QMessageBox.information
_original_warning = QMessageBox.warning
_original_critical = QMessageBox.critical
_original_question = QMessageBox.question

_installed = False
_filter: "_MessageBoxPolishFilter | None" = None


def strip_application_title_suffix(title: str) -> str:
    """Odstraní „ — Manažer BOZP“ / verzi z titulku, pokud se tam dostal."""
    text = str(title or "").strip()
    if not text:
        return text
    cleaned = _TITLE_APP_SUFFIX_RE.sub("", text).strip()
    display = app_display_name()
    if cleaned.endswith(display):
        cleaned = cleaned[: -len(display)].rstrip(" —–-").strip()
    return cleaned or text


def preferred_message_box_width(box: QMessageBox) -> int:
    """Šířka podle titulku a textu – běžné věty se zbytečně nelámou."""
    metrics = QFontMetrics(box.font())
    title = strip_application_title_suffix(box.windowTitle())
    parts = [box.text() or "", box.informativeText() or ""]
    longest_line = 0
    for part in parts:
        for line in str(part).splitlines() or [""]:
            longest_line = max(longest_line, metrics.horizontalAdvance(line))

    title_width = metrics.horizontalAdvance(title) + MESSAGE_BOX_TITLE_CHROME
    content_width = longest_line + MESSAGE_BOX_SIDE_PADDING
    width = max(MESSAGE_BOX_MIN_WIDTH, title_width, content_width)
    screen = QApplication.primaryScreen()
    if screen is not None:
        available = screen.availableGeometry().width()
        if available > 0:
            width = min(width, max(MESSAGE_BOX_MIN_WIDTH, available - 40))
    return min(width, MESSAGE_BOX_MAX_WIDTH)


def _is_custom_button_text(text: str) -> bool:
    normalized = str(text or "").strip().lower().replace("&", "")
    if not normalized:
        return False
    if normalized in _CUSTOM_BUTTON_TEXTS:
        return True
    return any(normalized.startswith(prefix) for prefix in _CUSTOM_BUTTON_TEXTS)


def apply_standard_button_labels(box: QMessageBox) -> None:
    """Sjednotí OK / Ano / Ne / Storno u standardních tlačítek."""
    for standard, label in _BUTTON_LABELS.items():
        button = box.button(standard)
        if button is None:
            continue
        current = button.text()
        if _is_custom_button_text(current):
            continue
        button.setText(label)


def polish_message_box(box: QMessageBox) -> None:
    """Sjednotí titulek, tlačítka a šířku jednoho QMessageBox."""
    title = strip_application_title_suffix(box.windowTitle())
    if title != box.windowTitle():
        box.setWindowTitle(title)

    apply_standard_button_labels(box)

    width = preferred_message_box_width(box)
    box.setMinimumWidth(width)
    # Necháme Qt dopočítat výšku podle obsahu – bez umělé min. výšky (prázdné plochy).
    box.setMaximumWidth(MESSAGE_BOX_MAX_WIDTH)
    box.adjustSize()
    if box.width() < width:
        box.resize(width, box.height())


def _build_box(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton,
    default_button: QMessageBox.StandardButton,
) -> QMessageBox:
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(strip_application_title_suffix(title))
    box.setText(str(text or ""))
    box.setStandardButtons(buttons)
    if default_button != QMessageBox.StandardButton.NoButton:
        box.setDefaultButton(default_button)
    polish_message_box(box)
    return box


def show_information(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    box = _build_box(
        parent,
        QMessageBox.Icon.Information,
        title,
        text,
        buttons,
        defaultButton,
    )
    return cast(QMessageBox.StandardButton, box.exec())


def show_warning(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    box = _build_box(
        parent,
        QMessageBox.Icon.Warning,
        title,
        text,
        buttons,
        defaultButton,
    )
    return cast(QMessageBox.StandardButton, box.exec())


def show_critical(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
    defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    box = _build_box(
        parent,
        QMessageBox.Icon.Critical,
        title,
        text,
        buttons,
        defaultButton,
    )
    return cast(QMessageBox.StandardButton, box.exec())


def show_question(
    parent: QWidget | None,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = (
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    ),
    defaultButton: QMessageBox.StandardButton = QMessageBox.StandardButton.NoButton,
) -> QMessageBox.StandardButton:
    box = _build_box(
        parent,
        QMessageBox.Icon.Question,
        title,
        text,
        buttons,
        defaultButton,
    )
    return cast(QMessageBox.StandardButton, box.exec())


class _MessageBoxPolishFilter(QObject):
    """Zachytí i ručně sestavené QMessageBox (nejen statické helpery)."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Show and isinstance(watched, QMessageBox):
            polish_message_box(watched)
        return super().eventFilter(watched, event)


def configure_application_for_dialogs(app: QApplication) -> None:
    """Zabrání WM v přidávání „ — Manažer BOZP“ do titulků dialogů.

    Hlavní okno si titulek nastavuje samo přes ``setWindowTitle(app_display_name())``.
    KDE při prázdném display name bere ``applicationName`` – proto technický identifikátor.
    """
    app.setApplicationDisplayName("")
    app.setApplicationName("manazer-bozp")


def install_unified_message_boxes(app: QApplication | None = None) -> None:
    """Nainstaluje jednotné statické API + polish filtr pro celou aplikaci."""
    global _installed, _filter

    QMessageBox.information = staticmethod(show_information)  # type: ignore[method-assign]
    QMessageBox.warning = staticmethod(show_warning)  # type: ignore[method-assign]
    QMessageBox.critical = staticmethod(show_critical)  # type: ignore[method-assign]
    QMessageBox.question = staticmethod(show_question)  # type: ignore[method-assign]

    application = app or QApplication.instance()
    if application is not None and _filter is None:
        _filter = _MessageBoxPolishFilter(application)
        application.installEventFilter(_filter)
        configure_application_for_dialogs(application)

    _installed = True


def uninstall_unified_message_boxes() -> None:
    """Obnoví původní QMessageBox API (pro testy)."""
    global _installed, _filter

    QMessageBox.information = _original_information  # type: ignore[method-assign]
    QMessageBox.warning = _original_warning  # type: ignore[method-assign]
    QMessageBox.critical = _original_critical  # type: ignore[method-assign]
    QMessageBox.question = _original_question  # type: ignore[method-assign]

    application = QApplication.instance()
    if application is not None and _filter is not None:
        application.removeEventFilter(_filter)
    _filter = None
    _installed = False
