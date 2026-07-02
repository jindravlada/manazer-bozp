"""Záložka auditních tvrzení v editoru metodiky auditora."""

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

from moduly.audity.constants import CONTROL_POINT_SEVERITY_OPTIONS
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_assertion_dialog import AudityKnowledgeAssertionDialog

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)

_COL_ID = 0
_COL_TEXT = 1
_COL_POPIS = 2
_COL_SEVERITY = 3
_COL_PORADI = 4
_COL_AKTIVNI = 5


class AudityKnowledgeAssertionsWidget(QWidget):
    """Seznam auditních tvrzení oblasti ověření s CRUD toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._process_id = ""
        self._section_id = ""
        self._assertions: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        toolbar = QHBoxLayout()
        self._add_btn = QPushButton("Přidat")
        self._edit_btn = QPushButton("Upravit")
        self._deactivate_btn = QPushButton("Deaktivovat")
        self._restore_btn = QPushButton("Obnovit")

        self._add_btn.clicked.connect(self._add_assertion)
        self._edit_btn.clicked.connect(self._edit_selected_assertion)
        self._deactivate_btn.clicked.connect(self._deactivate_selected_assertion)
        self._restore_btn.clicked.connect(self._restore_selected_assertion)

        toolbar.addWidget(self._add_btn)
        toolbar.addWidget(self._edit_btn)
        toolbar.addWidget(self._deactivate_btn)
        toolbar.addWidget(self._restore_btn)
        toolbar.addStretch()

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Text tvrzení", "Popis", "Závažnost", "Pořadí", "Aktivní"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._edit_selected_assertion)
        self._table.itemSelectionChanged.connect(self._update_buttons)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(_COL_TEXT, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_COL_POPIS, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnHidden(_COL_ID, True)
        self._table.setColumnWidth(_COL_SEVERITY, 110)
        self._table.setColumnWidth(_COL_PORADI, 70)
        self._table.setColumnWidth(_COL_AKTIVNI, 70)

        root.addLayout(toolbar)
        root.addWidget(self._table, stretch=1)

        self._update_buttons()

    def has_section(self) -> bool:
        return bool(self._process_id and self._section_id)

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
        self._assertions = []
        self._table.setRowCount(0)
        self._update_buttons()

    def reload_assertions(self) -> None:
        if not self.has_section():
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
        raw_items = section.get("auditni_tvrzeni") or []
        self._assertions = audit_knowledge_service.normalize_auditni_tvrzeni(raw_items)
        self._assertions.sort(key=lambda item: (item.get("poradi", 0), item.get("id", "")))
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._assertions))
        for row, item in enumerate(self._assertions):
            values = [
                item.get("id", ""),
                item.get("text", ""),
                item.get("popis", ""),
                _SEVERITY_LABELS.get(item.get("zavaznost", ""), item.get("zavaznost", "")),
                str(item.get("poradi", "")),
                "Ano" if item.get("aktivni", True) else "Ne",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, item.get("id", ""))
                if not item.get("aktivni", True):
                    cell.setForeground(Qt.GlobalColor.gray)
                self._table.setItem(row, column, cell)
        self._update_buttons()

    def _selected_assertion(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._assertions):
            return None
        return self._assertions[row]

    def _existing_ids(self) -> set[str]:
        return {
            str(item.get("id") or "").strip()
            for item in self._assertions
            if str(item.get("id") or "").strip()
        }

    def _show_errors(self, errors: list[str]) -> None:
        if not errors:
            return
        QMessageBox.warning(
            self,
            "Editor metodiky auditora",
            "\n".join(errors),
        )

    def _add_assertion(self) -> None:
        if not self.has_section():
            return

        dialog = AudityKnowledgeAssertionDialog(
            existing_ids=self._existing_ids(),
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeAssertionDialog.DialogCode.Accepted:
            return

        errors = audit_knowledge_editor_service.save_assertion(
            self._process_id,
            self._section_id,
            dialog.assertion_payload(),
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_assertions()

    def _edit_selected_assertion(self) -> None:
        if not self.has_section():
            return

        selected = self._selected_assertion()
        if selected is None:
            return

        dialog = AudityKnowledgeAssertionDialog(
            existing_ids=self._existing_ids(),
            assertion=selected,
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeAssertionDialog.DialogCode.Accepted:
            return

        errors = audit_knowledge_editor_service.save_assertion(
            self._process_id,
            self._section_id,
            dialog.assertion_payload(),
            assertion_id=dialog.editing_assertion_id,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_assertions()

    def _deactivate_selected_assertion(self) -> None:
        selected = self._selected_assertion()
        if selected is None or not self.has_section():
            return
        if not selected.get("aktivni", True):
            return

        errors = audit_knowledge_editor_service.set_assertion_active(
            self._process_id,
            self._section_id,
            str(selected.get("id") or ""),
            aktivni=False,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_assertions()

    def _restore_selected_assertion(self) -> None:
        selected = self._selected_assertion()
        if selected is None or not self.has_section():
            return
        if selected.get("aktivni", True):
            return

        errors = audit_knowledge_editor_service.set_assertion_active(
            self._process_id,
            self._section_id,
            str(selected.get("id") or ""),
            aktivni=True,
        )
        if errors:
            self._show_errors(errors)
            return
        self.reload_assertions()

    def _update_buttons(self) -> None:
        has_section = self.has_section()
        selected = self._selected_assertion()
        is_active = bool(selected.get("aktivni", True)) if selected else False

        self._add_btn.setEnabled(has_section)
        self._edit_btn.setEnabled(has_section and selected is not None)
        self._deactivate_btn.setEnabled(has_section and selected is not None and is_active)
        self._restore_btn.setEnabled(has_section and selected is not None and not is_active)
