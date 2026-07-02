"""Editor seznamu s popisem (postup kontroly)."""

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

from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_described_list_item_dialog import (
    AudityKnowledgeDescribedListItemDialog,
)

_COL_ID = 0
_COL_NAZEV = 1
_COL_POPIS = 2
_COL_PORADI = 3
_COL_AKTIVNI = 4


class AudityKnowledgeDescribedListEditorWidget(QWidget):
    """Seznam kroků postupu kontroly s CRUD toolbar."""

    def __init__(self, field_name: str, parent=None):
        super().__init__(parent)

        self._field_name = field_name
        self._process_id = ""
        self._section_id = ""
        self._items: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._add_btn = QPushButton("Přidat")
        self._edit_btn = QPushButton("Upravit")
        self._deactivate_btn = QPushButton("Deaktivovat")
        self._restore_btn = QPushButton("Obnovit")

        self._add_btn.clicked.connect(self._add_item)
        self._edit_btn.clicked.connect(self._edit_selected_item)
        self._deactivate_btn.clicked.connect(self._deactivate_selected_item)
        self._restore_btn.clicked.connect(self._restore_selected_item)

        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._edit_btn)
        toolbar.addWidget(self._deactivate_btn)
        toolbar.addWidget(self._restore_btn)
        toolbar.addStretch()

        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Název kroku", "Popis kroku", "Pořadí", "Aktivní"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._edit_selected_item)
        self._table.itemSelectionChanged.connect(self._update_buttons)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(_COL_NAZEV, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_POPIS, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnHidden(_COL_ID, True)
        self._table.setColumnWidth(_COL_PORADI, 70)
        self._table.setColumnWidth(_COL_AKTIVNI, 70)

        root.addLayout(toolbar)
        root.addWidget(self._table, stretch=1)

        self._update_buttons()

    def load_section(
        self,
        *,
        process_id: str,
        section_id: str,
        section: dict,
    ) -> None:
        self._process_id = process_id
        self._section_id = section_id
        self._reload_from_section(section)

    def clear_section(self) -> None:
        self._process_id = ""
        self._section_id = ""
        self._items = []
        self._table.setRowCount(0)
        self._update_buttons()

    def reload_items(self) -> None:
        if not self._process_id or not self._section_id:
            return
        section = audit_knowledge_service.get_criterion(
            self._process_id,
            self._section_id,
            ensure=False,
        )
        if section is None:
            self.clear_section()
            return
        self._reload_from_section(section)

    def _reload_from_section(self, section: dict) -> None:
        raw_items = section.get(self._field_name) or []
        self._items = audit_knowledge_service.normalize_list_items(raw_items)
        self._items.sort(key=lambda item: (item.get("poradi", 0), item.get("id", "")))
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            values = [
                item.get("id", ""),
                item.get("nazev", ""),
                item.get("popis", ""),
                str(item.get("poradi", "")),
                "Ano" if item.get("aktivni", True) else "Ne",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if not item.get("aktivni", True):
                    cell.setForeground(Qt.GlobalColor.gray)
                self._table.setItem(row, column, cell)
        self._update_buttons()

    def _selected_item(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _existing_ids(self) -> set[str]:
        return {
            str(item.get("id") or "").strip()
            for item in self._items
            if str(item.get("id") or "").strip()
        }

    def _show_errors(self, errors: list[str]) -> None:
        if errors:
            QMessageBox.warning(self, "Editor metodiky auditora", "\n".join(errors))

    def _add_item(self) -> None:
        if not self._process_id or not self._section_id:
            return

        dialog = AudityKnowledgeDescribedListItemDialog(
            existing_ids=self._existing_ids(),
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeDescribedListItemDialog.DialogCode.Accepted:
            return

        errors = audit_knowledge_editor_service.save_section_list_item(
            self._process_id,
            self._section_id,
            self._field_name,
            dialog.item_payload(),
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _edit_selected_item(self) -> None:
        selected = self._selected_item()
        if selected is None or not self._process_id or not self._section_id:
            return

        dialog = AudityKnowledgeDescribedListItemDialog(
            existing_ids=self._existing_ids(),
            item=selected,
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeDescribedListItemDialog.DialogCode.Accepted:
            return

        errors = audit_knowledge_editor_service.save_section_list_item(
            self._process_id,
            self._section_id,
            self._field_name,
            dialog.item_payload(),
            item_id=dialog.editing_item_id,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _deactivate_selected_item(self) -> None:
        selected = self._selected_item()
        if selected is None or not selected.get("aktivni", True):
            return
        errors = audit_knowledge_editor_service.set_section_list_item_active(
            self._process_id,
            self._section_id,
            self._field_name,
            str(selected.get("id") or ""),
            aktivni=False,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _restore_selected_item(self) -> None:
        selected = self._selected_item()
        if selected is None or selected.get("aktivni", True):
            return
        errors = audit_knowledge_editor_service.set_section_list_item_active(
            self._process_id,
            self._section_id,
            self._field_name,
            str(selected.get("id") or ""),
            aktivni=True,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_items()

    def _update_buttons(self) -> None:
        has_section = bool(self._process_id and self._section_id)
        selected = self._selected_item()
        is_active = bool(selected.get("aktivni", True)) if selected else False

        self._add_btn.setEnabled(has_section)
        self._edit_btn.setEnabled(has_section and selected is not None)
        self._deactivate_btn.setEnabled(has_section and selected is not None and is_active)
        self._restore_btn.setEnabled(has_section and selected is not None and not is_active)
