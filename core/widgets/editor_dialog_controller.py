"""UX-DIALOG-2 – jednotná logika tlačítek editorů (Uložit / Zrušit / Zavřít)."""

from __future__ import annotations

import warnings
from collections.abc import Callable
from typing import Literal

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QCloseEvent, QIcon, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStyle,
    QTextEdit,
    QWidget,
)

EDITOR_SAVE_LABEL = "Uložit"
EDITOR_CANCEL_LABEL = "Zrušit"
EDITOR_CLOSE_LABEL = "Zavřít"
EDITOR_UNSAVED_PROMPT = "Uložit změny před zavřením?"
EDITOR_UNSAVED_SAVE_LABEL = "Uložit"
EDITOR_UNSAVED_DISCARD_LABEL = "Neukládat"
EDITOR_UNSAVED_ABORT_LABEL = "Zrušit"

UnsavedCloseDecision = Literal["save", "discard", "cancel"]


def _standard_icon(pixmap: QStyle.StandardPixmap) -> QIcon:
    return QApplication.style().standardIcon(pixmap)


def confirm_unsaved_editor_close(parent: QWidget | None, *, title: str) -> UnsavedCloseDecision:
    """Standardní dialog neuložených změn. Vrací ``save`` / ``discard`` / ``cancel``.

    Všechny tři akce mají ``ActionRole``, aby Enter / Accept / Escape
    neaktivovaly omylem „Uložit“ (dříve AcceptRole).
    """
    message = QMessageBox(parent)
    message.setWindowTitle(title)
    message.setText(EDITOR_UNSAVED_PROMPT)
    message.setIcon(QMessageBox.Icon.Question)

    save_btn = message.addButton(
        EDITOR_UNSAVED_SAVE_LABEL,
        QMessageBox.ButtonRole.ActionRole,
    )
    configure_editor_save_button(save_btn)
    discard_btn = message.addButton(
        EDITOR_UNSAVED_DISCARD_LABEL,
        QMessageBox.ButtonRole.ActionRole,
    )
    discard_btn.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogResetButton))
    cancel_btn = message.addButton(
        EDITOR_UNSAVED_ABORT_LABEL,
        QMessageBox.ButtonRole.ActionRole,
    )
    configure_editor_close_button(cancel_btn, is_new=True)
    message.setDefaultButton(cancel_btn)
    message.setEscapeButton(cancel_btn)
    message.exec()

    clicked = message.clickedButton()
    if clicked is save_btn:
        return "save"
    if clicked is discard_btn:
        return "discard"
    return "cancel"


def configure_editor_close_button(
    button: QPushButton | None,
    *,
    is_new: bool,
) -> None:
    """Zrušit (nový) ↔ Zavřít (existující / po prvním uložení)."""
    if button is None:
        return
    if is_new:
        button.setText(EDITOR_CANCEL_LABEL)
        button.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogCancelButton))
    else:
        button.setText(EDITOR_CLOSE_LABEL)
        button.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogCloseButton))


def configure_editor_save_button(button: QPushButton | None) -> None:
    if button is None:
        return
    button.setText(EDITOR_SAVE_LABEL)
    button.setIcon(_standard_icon(QStyle.StandardPixmap.SP_DialogSaveButton))


def configure_editor_buttons(
    buttons: QDialogButtonBox,
    *,
    is_new: bool,
) -> None:
    """Nastaví popisky Uložit + Zrušit/Zavřít podle režimu editoru."""
    configure_editor_save_button(buttons.button(QDialogButtonBox.StandardButton.Save))
    ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_btn is not None:
        configure_editor_save_button(ok_btn)
    configure_editor_close_button(
        buttons.button(QDialogButtonBox.StandardButton.Cancel),
        is_new=is_new,
    )


def create_editor_button_box(
    parent: QWidget | None = None,
    *,
    is_new: bool = True,
) -> QDialogButtonBox:
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save,
        parent=parent,
    )
    configure_editor_buttons(buttons, is_new=is_new)
    return buttons


def set_editor_save_enabled(buttons: QDialogButtonBox, enabled: bool) -> None:
    for role in (
        QDialogButtonBox.StandardButton.Save,
        QDialogButtonBox.StandardButton.Ok,
    ):
        button = buttons.button(role)
        if button is not None:
            button.setEnabled(enabled)


def _safe_disconnect(signal, slot) -> None:
    """Odpojí konkrétní slot. Idempotentní vůči již neexistujícímu spojení."""
    with warnings.catch_warnings():
        # PySide 6.7+ při chybějícím spojení často jen vypíše RuntimeWarning
        # (bez výjimky). Potlačujeme pouze toto konkrétní hlášení u jednoho volání.
        warnings.filterwarnings(
            "ignore",
            category=RuntimeWarning,
            message=r".*Failed to disconnect.*",
        )
        try:
            signal.disconnect(slot)
        except (TypeError, RuntimeError):
            pass


class EditorDialogController(QObject):
    """Řídí Uložit / Zrušit|Zavřít a dotaz při neuložených změnách.

    Stay-open editory: po úspěšném vytvoření zavolejte ``become_existing()``.
    Modalní editory (Uložit = accept): stačí ``is_new`` + dirty tracking.
    """

    def __init__(
        self,
        dialog: QDialog,
        buttons: QDialogButtonBox,
        *,
        is_new: bool,
        title: str,
        on_save: Callable[[], bool] | None = None,
        is_dirty: Callable[[], bool] | None = None,
        parent: QObject | None = None,
    ):
        super().__init__(parent or dialog)
        self._dialog = dialog
        self._buttons = buttons
        self._is_new = bool(is_new)
        self._title = title
        self._on_save = on_save
        self._is_dirty_fn = is_dirty
        self._dirty = bool(is_new)
        self._closing = False
        self._cleaned = False
        self._baseline: object | None = None
        self._snapshot_fn: Callable[[], object] | None = None
        self._connections: list[tuple[object, Callable]] = []

        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if self.save_button is None:
            self.save_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.close_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)

        configure_editor_buttons(buttons, is_new=self._is_new)
        self._refresh_save_enabled()

        if self.save_button is not None:
            self._connect(self.save_button.clicked, self._handle_save_clicked)
        if self.close_button is not None:
            self._connect(self.close_button.clicked, self._handle_close_clicked)

        # finished se neeviduje – cleanup se z něj volá a musí zůstat bezpečný i po úklidu.
        dialog.finished.connect(self.cleanup)
        dialog.installEventFilter(self)

    def _connect(self, signal, slot: Callable) -> None:
        signal.connect(slot)
        self._connections.append((signal, slot))

    def cleanup(self, *_args) -> None:
        """Odpojí pouze sloty, které controller sám připojil. Idempotentní."""
        if self._cleaned:
            return
        self._cleaned = True
        connections = list(self._connections)
        self._connections.clear()
        for signal, slot in connections:
            _safe_disconnect(signal, slot)
        dialog = getattr(self, "_dialog", None)
        if dialog is not None:
            try:
                dialog.removeEventFilter(self)
            except RuntimeError:
                pass
            # finished→cleanup necháváme; další volání jsou no-op díky ``_cleaned``.

    @property
    def is_new(self) -> bool:
        return self._is_new

    def set_save_handler(self, on_save: Callable[[], bool]) -> None:
        self._on_save = on_save

    def set_dirty_checker(self, is_dirty: Callable[[], bool]) -> None:
        self._is_dirty_fn = is_dirty
        self._refresh_save_enabled()

    def set_snapshot_provider(self, snapshot_fn: Callable[[], object]) -> None:
        """Dirty = snapshot() != baseline. Po načtení volejte ``capture_baseline()``."""
        self._snapshot_fn = snapshot_fn

    def capture_baseline(self) -> None:
        if self._snapshot_fn is not None:
            self._baseline = self._snapshot_fn()
        if not self._is_new:
            self._dirty = False
        self._refresh_save_enabled()

    def mark_dirty(self, *_args) -> None:
        self._dirty = True
        self._refresh_save_enabled()

    def mark_clean(self) -> None:
        self._dirty = False
        if self._snapshot_fn is not None:
            self._baseline = self._snapshot_fn()
        self._refresh_save_enabled()

    def become_existing(self) -> None:
        """Po prvním úspěšném uložení nového záznamu: Zrušit → Zavřít."""
        self._is_new = False
        configure_editor_close_button(self.close_button, is_new=False)
        self.mark_clean()

    def is_dirty(self) -> bool:
        if self._is_dirty_fn is not None:
            return bool(self._is_dirty_fn())
        if self._snapshot_fn is not None:
            return self._snapshot_fn() != self._baseline
        return self._dirty

    def install_auto_dirty_tracking(self, root: QWidget | None = None) -> None:
        """Napojí běžné editační widgety na ``mark_dirty``."""
        host = root or self._dialog
        for widget in host.findChildren(QLineEdit):
            self._connect(widget.textChanged, self.mark_dirty)
        for widget in host.findChildren(QTextEdit):
            self._connect(widget.textChanged, self.mark_dirty)
        for widget in host.findChildren(QPlainTextEdit):
            self._connect(widget.textChanged, self.mark_dirty)
        for widget in host.findChildren(QComboBox):
            self._connect(widget.currentIndexChanged, self.mark_dirty)
        for widget in host.findChildren(QCheckBox):
            self._connect(widget.stateChanged, self.mark_dirty)
        for widget in host.findChildren(QDateEdit):
            self._connect(widget.dateChanged, self.mark_dirty)
        for widget in host.findChildren(QSpinBox):
            self._connect(widget.valueChanged, self.mark_dirty)

    def request_close(self) -> bool:
        """Zpracuje požadavek na zavření. ``True`` = smí se zavřít."""
        if self._closing:
            return True
        if not self.is_dirty():
            return True

        decision = confirm_unsaved_editor_close(self._dialog, title=self._title)
        if decision == "cancel":
            return False
        if decision == "save":
            return self._run_save()
        # discard
        return True

    def force_close(self) -> None:
        self._closing = True
        self._dialog.reject()

    def _refresh_save_enabled(self) -> None:
        if self._is_new:
            set_editor_save_enabled(self._buttons, True)
            return
        set_editor_save_enabled(self._buttons, self.is_dirty())

    def _run_save(self) -> bool:
        if self._on_save is None:
            # Klasický modal: parent uloží po accept(); validace může accept zrušit.
            self._dialog.accept()
            return self._dialog.result() == QDialog.DialogCode.Accepted
        ok = bool(self._on_save())
        if not ok:
            return False
        if self._is_new:
            self.become_existing()
        else:
            self.mark_clean()
        return True

    def _handle_save_clicked(self) -> None:
        if self._on_save is None:
            # Klasický modal: parent uloží po accept().
            if not self._is_new and not self.is_dirty():
                return
            self._dialog.accept()
            return
        self._run_save()

    def _handle_close_clicked(self) -> None:
        if not self.request_close():
            return
        self._closing = True
        # „Uložit“ v promptu mohlo dialog už acceptnout (modální editor).
        if self._dialog.result() == QDialog.DialogCode.Accepted:
            return
        self._dialog.reject()

    def eventFilter(self, watched, event):  # noqa: N802
        dialog = getattr(self, "_dialog", None)
        if dialog is not None and watched is dialog:
            if isinstance(event, QCloseEvent):
                if self._closing:
                    return False
                # Nezobrazený dialog (typicky unit testy / cleanup) – bez promptu.
                if not dialog.isVisible():
                    self._closing = True
                    return False
                if not self.request_close():
                    event.ignore()
                    return True
                self._closing = True
                if dialog.result() == QDialog.DialogCode.Accepted:
                    event.accept()
                    return True
                return False
            if (
                isinstance(event, QKeyEvent)
                and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape
            ):
                if self._closing:
                    return False
                if not dialog.isVisible():
                    return False
                if not self.request_close():
                    return True
                self._closing = True
                if dialog.result() == QDialog.DialogCode.Accepted:
                    return True
                dialog.reject()
                return True
        return super().eventFilter(watched, event)
