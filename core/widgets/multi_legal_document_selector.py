"""Multivýběr právních předpisů se stejným UX jako MultiExposedGroupSelector."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.constants import legal_document_list_label
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.ui.legal_document_selector import LegalDocumentNameSelector


class MultiLegalDocumentSelector(QWidget):
    """Výběr více předpisů: našeptávač + Přidat/Odebrat + seznam vybraných."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        self.selector = LegalDocumentNameSelector(self)
        if self.selector.lineEdit() is not None:
            self.selector.lineEdit().setPlaceholderText(
                "Začněte psát název, číslo nebo zkratku…",
            )
        self.btn_add = QPushButton("Přidat")
        self.btn_remove = QPushButton("Odebrat")
        top.addWidget(self.selector, 1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_remove)

        selected_label = QLabel("Vybrané právní předpisy:")
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(72)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

        layout.addLayout(top)
        layout.addWidget(selected_label)
        layout.addWidget(self.list_widget)

        self.btn_add.clicked.connect(self.add_current)
        self.btn_remove.clicked.connect(self.remove_selected)
        if self.selector.lineEdit() is not None:
            self.selector.lineEdit().returnPressed.connect(self.add_current)
        self.selector.activated.connect(self._on_selector_activated)
        self.selector.set_document_id(None)

    def add_current(self) -> None:
        document_id = self.selector.current_document_id()
        if document_id is None:
            QMessageBox.warning(
                self.window(),
                "Právní předpis",
                "Vyberte předpis z našeptávače.",
            )
            return
        self._append_document_id(document_id)
        self.selector.set_document_id(None)

    def remove_selected(self) -> None:
        for item in self.list_widget.selectedItems():
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def selected_document_ids(self) -> list[int]:
        """Vrátí ID předpisů ze seznamu včetně dosud nepřidaného výběru v selectoru."""
        self._commit_pending_selector_document()
        return self._list_document_ids()

    def set_document_ids(self, document_ids: list[int] | tuple[int, ...] | None) -> None:
        self.list_widget.clear()
        for document_id in document_ids or ():
            self._append_document_id(int(document_id))
        self.selector.set_document_id(None)

    def reload(self, preserve_ids: list[int] | None = None) -> None:
        current = preserve_ids if preserve_ids is not None else self.selected_document_ids()
        self.selector.reload()
        self.set_document_ids(current)

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        self.selector.setEnabled(enabled)
        self.btn_add.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.list_widget.setEnabled(enabled)

    def _on_selector_activated(self, _index: int) -> None:
        document_id = self.selector.current_document_id()
        if document_id is None:
            return
        self._append_document_id(document_id)
        self.selector.set_document_id(None)

    def _commit_pending_selector_document(self) -> None:
        """Při čtení hodnot zahrne výběr v comboboxu, jen pokud je vyplněný text."""
        if not self.selector.currentText().strip():
            return
        document_id = self.selector.current_document_id()
        if document_id is None:
            return
        self._append_document_id(document_id)
        self.selector.set_document_id(None)

    def _list_document_ids(self) -> list[int]:
        ids: list[int] = []
        for index in range(self.list_widget.count()):
            item = self.list_widget.item(index)
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw is None:
                continue
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                continue
        return ids

    def _append_document_id(self, document_id: int) -> None:
        if document_id in self._list_document_ids():
            return
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            label = f"#{document_id}"
        else:
            label = legal_document_list_label(document)
            if not document.active:
                label = f"{label} (neaktivní)"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, int(document_id))
        self.list_widget.addItem(item)
