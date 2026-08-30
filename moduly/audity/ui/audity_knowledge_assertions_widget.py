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
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    CONTROL_POINT_SEVERITY_OPTIONS,
    QUESTION_KIND_EDITOR_LABEL_UNCLASSIFIED,
    QUESTION_KIND_EDITOR_OPTIONS,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import (
    AssertionQuestionKindChange,
    audit_knowledge_editor_service,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind
from moduly.audity.ui.audity_knowledge_assertion_dialog import AudityKnowledgeAssertionDialog

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)

_COL_ID = 0
_COL_TEXT = 1
_COL_KIND = 2
_COL_POPIS = 3
_COL_SEVERITY = 4
_COL_VERIFICATION = 5
_COL_PORADI = 6
_COL_AKTIVNI = 7

_VERIFICATION_COMBO_TOOLTIP = (
    "Závazné pro všechny audity. Ad hoc přesun v jednom auditu metodiku nemění."
)
_KIND_COMBO_TOOLTIP = (
    "Systém = pouze u systémového provozu; Provoz = u ostatních provozů. "
    "Změna se uloží až přes Uložit v editoru metodiky."
)


class AudityKnowledgeAssertionsWidget(QWidget):
    """Seznam auditních tvrzení oblasti ověření s CRUD toolbar."""

    content_modified = Signal()
    content_saved = Signal()
    question_kinds_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._process_id = ""
        self._section_id = ""
        self._assertions: list[dict] = []
        # Pracovní kopie druhů: (process_id, section_id, assertion_id) → kind
        self._pending_kinds: dict[tuple[str, str, str], str] = {}
        self._disk_kinds: dict[tuple[str, str, str], str] = {}

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
        self._table.setColumnCount(8)
        self._table.setHorizontalHeaderLabels(
            [
                "ID",
                "Text tvrzení",
                "Druh",
                "Popis",
                "Závažnost",
                "Typ ověření",
                "Pořadí",
                "Aktivní",
            ]
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
        self._table.setColumnWidth(_COL_KIND, 120)
        self._table.setColumnWidth(_COL_SEVERITY, 110)
        self._table.setColumnWidth(_COL_VERIFICATION, 140)
        self._table.setColumnWidth(_COL_PORADI, 70)
        self._table.setColumnWidth(_COL_AKTIVNI, 70)

        root.addLayout(toolbar)
        root.addWidget(self._table, stretch=1)

        self._update_buttons()

    def has_section(self) -> bool:
        return bool(self._process_id and self._section_id)

    def has_pending_question_kinds(self) -> bool:
        return bool(self._pending_kinds)

    def pending_question_kind_overrides(self) -> dict[str, str]:
        """Mapa ``question_stable_key → kind`` pro počítadlo nezařazených."""
        return {
            audit_knowledge_service.question_stable_key(process_id, section_id, assertion_id): kind
            for (process_id, section_id, assertion_id), kind in self._pending_kinds.items()
        }

    def pending_question_kind_changes(self) -> tuple[AssertionQuestionKindChange, ...]:
        """Čistá dávka pending druhů — bez zápisu a bez Qt modelů."""
        return tuple(
            AssertionQuestionKindChange(
                process_id=process_id,
                section_id=section_id,
                assertion_id=assertion_id,
                question_kind=kind,
            )
            for (process_id, section_id, assertion_id), kind in self._pending_kinds.items()
        )

    def clear_pending_question_kinds_after_persist(self) -> None:
        """Po úspěšném zápisu jen vyčistí pracovní kopii (bez čtení disku)."""
        for key, kind in self._pending_kinds.items():
            self._disk_kinds[key] = kind
        self._pending_kinds.clear()

    def discard_pending_question_kinds(self) -> None:
        self._pending_kinds.clear()
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

    def flush_pending_question_kinds(self) -> list[str]:
        if not self._pending_kinds:
            return []
        changes = [
            AssertionQuestionKindChange(
                process_id=process_id,
                section_id=section_id,
                assertion_id=assertion_id,
                question_kind=kind,
            )
            for (process_id, section_id, assertion_id), kind in self._pending_kinds.items()
        ]
        errors = audit_knowledge_editor_service.set_assertion_question_kinds_batch(
            changes
        )
        if errors:
            return errors
        for key, kind in self._pending_kinds.items():
            self._disk_kinds[key] = kind
        self._pending_kinds.clear()
        if self.has_section():
            self.reload_assertions()
        else:
            self.question_kinds_modified.emit()
        return []

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

    def count_unclassified_active_in_section(self) -> int:
        return sum(
            1
            for item in self._assertions
            if item.get("aktivni", True)
            and interpret_question_kind(item.get("question_kind"))
            == AUDIT_QUESTION_KIND_UNCLASSIFIED
        )

    def _pending_key(self, assertion_id: str) -> tuple[str, str, str]:
        return (self._process_id, self._section_id, assertion_id)

    def _reload_from_section(self, section: dict) -> None:
        raw_items = section.get("auditni_tvrzeni") or []
        self._assertions = audit_knowledge_service.normalize_auditni_tvrzeni(raw_items)
        self._assertions.sort(key=lambda item: (item.get("poradi", 0), item.get("id", "")))
        for item in self._assertions:
            assertion_id = str(item.get("id") or "").strip()
            if not assertion_id:
                continue
            key = self._pending_key(assertion_id)
            self._disk_kinds[key] = interpret_question_kind(item.get("question_kind"))
            if key in self._pending_kinds:
                item["question_kind"] = self._pending_kinds[key]
        self._populate_table()

    def _populate_table(self) -> None:
        self._table.setRowCount(len(self._assertions))
        for row, item in enumerate(self._assertions):
            kind = interpret_question_kind(item.get("question_kind"))
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

            # Placeholder buňka pod combem (pro výběr řádku / UserRole).
            kind_cell = QTableWidgetItem("")
            kind_cell.setData(Qt.ItemDataRole.UserRole, item.get("id", ""))
            if not item.get("aktivni", True):
                kind_cell.setForeground(Qt.GlobalColor.gray)
            elif kind == AUDIT_QUESTION_KIND_UNCLASSIFIED:
                kind_cell.setToolTip(QUESTION_KIND_EDITOR_LABEL_UNCLASSIFIED)
            self._table.setItem(row, _COL_KIND, kind_cell)

            self._table.setCellWidget(
                row,
                _COL_KIND,
                self._build_kind_combo(item),
            )
            self._table.setCellWidget(
                row,
                _COL_VERIFICATION,
                self._build_verification_combo(item),
            )
        self._update_buttons()

    def _build_kind_combo(self, item: dict) -> QComboBox:
        combo = QComboBox()
        combo.setFixedWidth(112)
        combo.setToolTip(_KIND_COMBO_TOOLTIP)
        for value, label in QUESTION_KIND_EDITOR_OPTIONS:
            combo.addItem(label, value)

        current = interpret_question_kind(item.get("question_kind"))
        index = combo.findData(current)
        if index >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

        assertion_id = str(item.get("id") or "").strip()
        combo.setProperty("assertion_id", assertion_id)
        combo.setEnabled(bool(item.get("aktivni", True)))
        if current == AUDIT_QUESTION_KIND_UNCLASSIFIED and item.get("aktivni", True):
            combo.setStyleSheet("QComboBox { color: #8a6d00; }")
        else:
            combo.setStyleSheet("")
        combo.currentIndexChanged.connect(
            lambda _index, c=combo: self._on_kind_combo_changed(c)
        )
        return combo

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

    def _on_kind_combo_changed(self, combo: QComboBox) -> None:
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

        new_kind = interpret_question_kind(combo.currentData())
        current_kind = interpret_question_kind(assertion.get("question_kind"))
        if new_kind == current_kind:
            return

        assertion["question_kind"] = new_kind
        key = self._pending_key(assertion_id)
        disk_kind = self._disk_kinds.get(key, AUDIT_QUESTION_KIND_UNCLASSIFIED)
        if new_kind == disk_kind:
            self._pending_kinds.pop(key, None)
        else:
            self._pending_kinds[key] = new_kind

        if new_kind == AUDIT_QUESTION_KIND_UNCLASSIFIED and assertion.get("aktivni", True):
            combo.setStyleSheet("QComboBox { color: #8a6d00; }")
            combo.setToolTip(QUESTION_KIND_EDITOR_LABEL_UNCLASSIFIED)
        else:
            combo.setStyleSheet("")
            combo.setToolTip(_KIND_COMBO_TOOLTIP)

        self.question_kinds_modified.emit()

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
        # Druh nepřepisuj při rychlé změně typu ověření — nezařazené / pending zůstanou.
        existing_kind = interpret_question_kind(assertion.get("question_kind"))
        if existing_kind in (AUDIT_QUESTION_KIND_SYSTEM, AUDIT_QUESTION_KIND_OPERATION):
            # Pending druh má přednost; na disk zatím neukládej pending.
            key = self._pending_key(assertion_id)
            if key not in self._pending_kinds:
                payload["question_kind"] = existing_kind

        self.content_modified.emit()
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

        self.content_modified.emit()
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

        payload = dialog.assertion_payload()
        assertion_id = dialog.editing_assertion_id or str(selected.get("id") or "")
        self.content_modified.emit()
        errors = audit_knowledge_editor_service.save_assertion(
            self._process_id,
            self._section_id,
            payload,
            assertion_id=assertion_id,
        )
        if errors:
            self._show_errors(errors)
            return
        # Detail zapisuje ihned — synchronizuj disk/pending pro danou otázku.
        key = self._pending_key(str(assertion_id).strip())
        saved_kind = interpret_question_kind(payload.get("question_kind"))
        self._pending_kinds.pop(key, None)
        self._disk_kinds[key] = saved_kind
        self.reload_assertions()

    def _deactivate_selected_assertion(self) -> None:
        selected = self._selected_assertion()
        if selected is None or not self.has_section():
            return
        if not selected.get("aktivni", True):
            return

        self.content_modified.emit()
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

        self.content_modified.emit()
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
