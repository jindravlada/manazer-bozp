"""Záložka auditních tvrzení v editoru metodiky auditora."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.verification_type import VERIFICATION_TYPE_OPTIONS
from moduly.audity.constants import CONTROL_POINT_SEVERITY_OPTIONS
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audity_knowledge_assertion_dialog import AudityKnowledgeAssertionDialog

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)

_COL_ID = 0
_COL_TEXT = 1
_COL_POPIS = 2
_COL_SEVERITY = 3
_COL_VERIFICATION = 4
_COL_PORADI = 5
_COL_AKTIVNI = 6

_VERIFICATION_COMBO_TOOLTIP = (
    "Závazné pro všechny audity. Ad hoc přesun v jednom auditu metodiku nemění."
)


class AudityKnowledgeAssertionsWidget(QWidget):
    """Seznam auditních tvrzení oblasti ověření s CRUD toolbar."""

    content_modified = Signal()
    content_saved = Signal()

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
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Text tvrzení", "Popis", "Závažnost", "Typ ověření", "Pořadí", "Aktivní"]
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
        self._table.setColumnWidth(_COL_VERIFICATION, 140)
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
        self.content_saved.emit()

    def _reload_from_section(self, section: dict) -> None:
        raw_items = section.get("auditni_tvrzeni") or []
        self._assertions = audit_knowledge_service.normalize_auditni_tvrzeni(raw_items)
        self._assertions.sort(key=lambda item: (item.get("poradi", 0), item.get("id", "")))
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._assertions))
        for row, item in enumerate(self._assertions):
            values = {
                _COL_ID: item.get("id", ""),
                _COL_TEXT: item.get("text", ""),
                _COL_POPIS: item.get("popis", ""),
                _COL_SEVERITY: _SEVERITY_LABELS.get(
                    item.get("zavaznost", ""), item.get("zavaznost", "")
                ),
                _COL_PORADI: str(item.get("poradi", "")),
                _COL_AKTIVNI: "Ano" if item.get("aktivni", True) else "Ne",
            }
            for column, value in values.items():
                cell = QTableWidgetItem(str(value))
                cell.setData(Qt.ItemDataRole.UserRole, item.get("id", ""))
                if not item.get("aktivni", True):
                    cell.setForeground(Qt.GlobalColor.gray)
                self._table.setItem(row, column, cell)

            self._table.setCellWidget(
                row,
                _COL_VERIFICATION,
                self._build_verification_combo(item),
            )
        self._update_buttons()

    def _build_verification_combo(self, item: dict) -> QComboBox:
        combo = QComboBox()
        combo.setFixedWidth(128)
        combo.setToolTip(_VERIFICATION_COMBO_TOOLTIP)
        for value, label in VERIFICATION_TYPE_OPTIONS:
            combo.addItem(label, value)

        current = audit_knowledge_service.normalize_verification_type(
            item.get("verification_type")
        )
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)

        assertion_id = str(item.get("id") or "").strip()
        combo.setProperty("assertion_id", assertion_id)
        combo.currentIndexChanged.connect(
            lambda _index, c=combo: self._on_verification_combo_changed(c)
        )
        return combo

    def _on_verification_combo_changed(self, combo: QComboBox) -> None:
        if not self.has_section():
            return
        assertion_id = str(combo.property("assertion_id") or "").strip()
        if not assertion_id:
            return

        assertion = next(
            (
                item
                for item in self._assertions
                if str(item.get("id") or "").strip() == assertion_id
            ),
            None,
        )
        if assertion is None:
            return

        new_type = audit_knowledge_service.normalize_verification_type(combo.currentData())
        current_type = audit_knowledge_service.normalize_verification_type(
            assertion.get("verification_type")
        )
        if new_type == current_type:
            return

        payload = {
            "id": assertion_id,
            "text": assertion.get("text") or assertion.get("nazev") or "",
            "popis": assertion.get("popis") or "",
            "zavaznost": assertion.get("zavaznost"),
            "verification_type": new_type,
            "poradi": assertion.get("poradi", 0),
            "aktivni": bool(assertion.get("aktivni", True)),
        }

        # Okamžité uložení (FO-3) — neoznačovat odložený dirty stav editoru.
        errors = audit_knowledge_editor_service.save_assertion(
            self._process_id,
            self._section_id,
            payload,
            assertion_id=assertion_id,
        )
        if errors:
            self._show_errors(errors)
            self.reload_assertions()
            return
        self.reload_assertions()

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

        # Nested dialog + okamžité uložení — stay-open footer ukládá jen metadata.
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
