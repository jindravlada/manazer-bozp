from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.constants import (
    legal_document_regulation_number,
    legal_section_provision_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_requirement_source_add_dialog import (
    LegalRequirementSourceAddDialog,
)

_SECTION_ID_ROLE = Qt.ItemDataRole.UserRole
_MISSING_SECTION_TEXT = "Znění ustanovení není k dispozici."


class LegalRequirementSourcesWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat ustanovení")
        self.remove_btn = QPushButton("Odebrat")
        self.remove_btn.setEnabled(False)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Předpis", "Ustanovení"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self._add_source)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.table.itemSelectionChanged.connect(self._update_buttons)

    def load_section_ids(self, section_ids: list[int]) -> None:
        self.table.setRowCount(0)
        for section_id in section_ids:
            self._append_row(section_id)
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
        else:
            self.table.clearSelection()

    def get_section_ids(self) -> list[int]:
        section_ids: list[int] = []
        for row in range(self.table.rowCount()):
            section_id = self.section_id_for_row(row)
            if section_id is not None and section_id not in section_ids:
                section_ids.append(section_id)
        return section_ids

    def section_id_for_row(self, row: int) -> int | None:
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        section_id = item.data(_SECTION_ID_ROLE)
        return section_id if isinstance(section_id, int) else None

    def selected_section_id(self) -> int | None:
        return self.section_id_for_row(self.table.currentRow())

    def select_first_row(self) -> None:
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
        else:
            self.table.clearSelection()

    def _append_row(self, section_id: int) -> None:
        section = legal_section_service.get_by_id(section_id)
        if section is None:
            return

        document = legal_document_service.get_by_id(section.legal_document_id)
        sections_by_id = legal_section_service.build_sections_map([section])
        document_label = ""
        if document is not None:
            title = (document.title or "").strip()
            document_label = title or legal_document_regulation_number(document)
        provision_label = legal_section_provision_label(section, sections_by_id=sections_by_id)
        if not provision_label:
            provision_label = f"Ustanovení #{section.id}"

        row = self.table.rowCount()
        self.table.insertRow(row)
        document_item = QTableWidgetItem(document_label)
        document_item.setData(_SECTION_ID_ROLE, section_id)
        provision_item = QTableWidgetItem(provision_label)
        self.table.setItem(row, 0, document_item)
        self.table.setItem(row, 1, provision_item)
        if self.table.rowCount() == 1:
            self.table.selectRow(0)

    def _add_source(self) -> None:
        dialog = LegalRequirementSourceAddDialog(
            self,
            excluded_section_ids=set(self.get_section_ids()),
        )
        if exec_maximized(dialog) != LegalRequirementSourceAddDialog.DialogCode.Accepted:
            return

        section_id = dialog.selected_section_id()
        if section_id is None:
            return
        if section_id in self.get_section_ids():
            QMessageBox.information(
                self,
                "Právní podklad",
                "Toto ustanovení je již přidáno.",
            )
            return
        self._append_row(section_id)

    def _remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        self.table.removeRow(row)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.remove_btn.setEnabled(self.table.currentRow() >= 0)
