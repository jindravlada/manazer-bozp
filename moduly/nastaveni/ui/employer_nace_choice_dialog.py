"""Výběr hlavní CZ-NACE, když ARES vrátí více činností."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QVBoxLayout,
)

from core.services.cz_nace_service import cz_nace_service
from core.widgets.dialog_utils import configure_resizable_form_dialog


class EmployerNaceChoiceDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        codes: list[str],
        current: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("Hlavní CZ-NACE")
        configure_resizable_form_dialog(
            self,
            width=640,
            height=420,
            min_width=480,
            min_height=280,
        )

        layout = QVBoxLayout(self)
        message = QLabel(
            "ARES eviduje u zaměstnavatele více ekonomických činností.\n"
            "Vyberte hlavní CZ-NACE:"
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self.activities = QListWidget()
        self.activities.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        for code in codes:
            text = str(code or "").strip()
            if not text:
                continue
            self.activities.addItem(cz_nace_service.get_display(text))
            item = self.activities.item(self.activities.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, text)
        layout.addWidget(self.activities)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.ok_button is not None:
            self.ok_button.setText("Vybrat")
        if cancel_button is not None:
            cancel_button.setText("Zrušit")
        buttons.accepted.connect(self._accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.activities.itemDoubleClicked.connect(self._accept_selection)
        self.activities.currentItemChanged.connect(lambda *_args: self._update_ok())
        self._preselect(current)
        self._update_ok()

    def choose(self) -> str | None:
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return self.selected_code() or None

    def selected_code(self) -> str:
        item = self.activities.currentItem()
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _preselect(self, current: str) -> None:
        self.activities.setCurrentRow(-1)
        self.activities.clearSelection()
        wanted = _nace_identity(current)
        if not wanted:
            return
        for row in range(self.activities.count()):
            item = self.activities.item(row)
            raw = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if _nace_identity(raw) == wanted:
                self.activities.setCurrentRow(row)
                return

    def _update_ok(self) -> None:
        if self.ok_button is not None:
            self.ok_button.setEnabled(self.activities.currentRow() >= 0)

    def _accept_selection(self, *_args) -> None:
        if self.activities.currentRow() < 0:
            return
        self.accept()


def _nace_identity(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    found = cz_nace_service.lookup(raw)
    if found is None:
        return raw
    return found[0]
