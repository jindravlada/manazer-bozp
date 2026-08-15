"""Editor externího auditu — Spis / Program / Účastníci / Zjištění / Přílohy (EA-2)."""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.ares_service import ares_service
from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    EDITOR_SAVE_LABEL,
    configure_editor_close_button,
    configure_editor_save_button,
    confirm_unsaved_editor_close,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_EDITOR_TITLE_EDIT,
    EXTERNAL_AUDIT_EDITOR_TITLE_NEW,
    EXTERNAL_AUDIT_INVALID_AUDITOR_LABEL_PREFIX,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_LABELS,
    EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID,
    EXTERNAL_AUDIT_SOURCE_PERSON,
    EXTERNAL_AUDIT_SOURCE_THP_WORKER,
    EXTERNAL_AUDIT_STATUS_LABELS,
    EXTERNAL_AUDIT_STATUSES,
    EXTERNAL_AUDIT_STATUS_PLANNED,
    EXTERNAL_AUDIT_TYPE_LABELS,
    EXTERNAL_AUDIT_TYPES,
    EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    format_display_date,
)
from moduly.externi_audity.sluzby.external_audit_draft import (
    ExternalAuditDraft,
    ParticipantDraft,
    new_client_key,
)
from moduly.externi_audity.sluzby.external_audit_service import (
    ExternalAuditError,
    _resolve_participant_source,
    external_audit_service,
)
from moduly.externi_audity.ui.external_audit_attachment_staging_widget import (
    ExternalAuditAttachmentStagingWidget,
)
from moduly.externi_audity.ui.external_audit_findings_widget import (
    ExternalAuditFindingsWidget,
)
from moduly.externi_audity.ui.external_audit_visit_dialog import ExternalAuditVisitDialog
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service

TAB_SPIS = 0
TAB_PROGRAM = 1
TAB_PARTICIPANTS = 2
TAB_FINDINGS = 3
TAB_ATTACHMENTS = 4


class ExternalAuditEditorDialog(QDialog):
    def __init__(self, parent=None, *, audit_id: int | None = None):
        super().__init__(parent)
        self._closing = False
        self._baseline: dict | None = None
        self._draft = external_audit_service.load_draft(audit_id)
        self.setWindowTitle(
            EXTERNAL_AUDIT_EDITOR_TITLE_EDIT
            if audit_id
            else EXTERNAL_AUDIT_EDITOR_TITLE_NEW
        )
        self.resize(980, 720)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_spis_tab(), "Spis")
        self.tabs.addTab(self._build_program_tab(), "Program")
        self.tabs.addTab(self._build_participants_tab(), "Účastníci")
        self.tabs.addTab(self._build_findings_tab(), "Zjištění")
        self.tabs.addTab(self._build_attachments_tab(), "Přílohy")
        layout.addWidget(self.tabs, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self._save_btn = QPushButton()
        configure_editor_save_button(self._save_btn)
        self._save_btn.setText(EDITOR_SAVE_LABEL)
        self._save_close_btn = QPushButton("Uložit a zavřít")
        self._close_btn = QPushButton()
        configure_editor_close_button(
            self._close_btn, is_new=self._draft.audit_id is None
        )
        self._close_btn.setText(EDITOR_CLOSE_LABEL)
        for button in (self._save_btn, self._save_close_btn, self._close_btn):
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            footer.addWidget(button)
        layout.addLayout(footer)

        self._save_btn.clicked.connect(self._save_keep_open)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._close_btn.clicked.connect(self._request_close)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._load_draft_into_widgets()
        self._capture_baseline()
        self._refresh_attachment_gate()

    def _on_tab_changed(self, index: int) -> None:
        if index == TAB_PARTICIPANTS:
            # Nově založené Osoby se projeví v selektoru auditora.
            if hasattr(self.auditor_selector, "reload"):
                self.auditor_selector.reload()

    def _build_spis_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.audit_type = QComboBox()
        for value in sorted(EXTERNAL_AUDIT_TYPES):
            self.audit_type.addItem(EXTERNAL_AUDIT_TYPE_LABELS[value], value)

        self.status = QComboBox()
        for value in (
            "planned",
            "in_progress",
            "closed",
            "cancelled",
        ):
            if value in EXTERNAL_AUDIT_STATUSES:
                self.status.addItem(EXTERNAL_AUDIT_STATUS_LABELS[value], value)

        self.ico = QLineEdit()
        ico_row = QHBoxLayout()
        ico_row.addWidget(self.ico, 1)
        self.ares_btn = QPushButton("Načíst z ARES")
        self.ares_btn.setAutoDefault(False)
        self.ares_btn.clicked.connect(self._load_from_ares)
        ico_row.addWidget(self.ares_btn)
        ico_host = QWidget()
        ico_host.setLayout(ico_row)

        self.organization_name = QLineEdit()
        self.organization_address = QLineEdit()
        self.date_from = QLineEdit()
        self.date_from.setReadOnly(True)
        self.date_to = QLineEdit()
        self.date_to.setReadOnly(True)
        self.remind_from = NullableDateEdit()
        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMinimumHeight(120)

        form.addRow("Typ auditu *:", self.audit_type)
        form.addRow("Stav *:", self.status)
        form.addRow("IČ *:", ico_host)
        form.addRow("Název organizace *:", self.organization_name)
        form.addRow("Adresa organizace:", self.organization_address)
        form.addRow("Termín od:", self.date_from)
        form.addRow("Termín do:", self.date_to)
        form.addRow("Připomenout od:", self.remind_from)
        form.addRow("Poznámka:", self.note)
        return page

    def _build_program_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        toolbar = QHBoxLayout()
        self.visit_add_btn = QPushButton("Přidat")
        self.visit_edit_btn = QPushButton("Upravit")
        self.visit_remove_btn = QPushButton("Odebrat")
        self.visit_up_btn = QPushButton("Nahoru")
        self.visit_down_btn = QPushButton("Dolů")
        for button in (
            self.visit_add_btn,
            self.visit_edit_btn,
            self.visit_remove_btn,
            self.visit_up_btn,
            self.visit_down_btn,
        ):
            button.setAutoDefault(False)
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.visits_table = QTableWidget(0, 8)
        self.visits_table.setHorizontalHeaderLabels(
            [
                "Datum",
                "Čas od",
                "Čas do",
                "Provoz",
                "Externí auditoři",
                "Zástupci společnosti",
                "Přizvané osoby",
                "Poznámka",
            ]
        )
        self.visits_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.visits_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.visits_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.visits_table.verticalHeader().setVisible(False)
        self.visits_table.itemSelectionChanged.connect(self._refresh_visit_actions)
        self.visits_table.doubleClicked.connect(self._edit_visit)
        from core.widgets.typed_table_sort import enable_typed_sorting

        enable_typed_sorting(self.visits_table)
        layout.addWidget(self.visits_table, 1)

        self.visit_add_btn.clicked.connect(self._add_visit)
        self.visit_edit_btn.clicked.connect(self._edit_visit)
        self.visit_remove_btn.clicked.connect(self._remove_visit)
        self.visit_up_btn.clicked.connect(lambda: self._move_visit(-1))
        self.visit_down_btn.clicked.connect(lambda: self._move_visit(1))
        return page

    def _build_participants_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.auditor_box, self.auditor_list, self.auditor_selector = (
            self._participant_group(
                EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source="person",
            )
        )
        self.rep_box, self.rep_list, self.rep_selector = self._participant_group(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
            source="thp",
        )
        self.invited_box, self.invited_list, self.invited_selector = (
            self._participant_group(
                EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
                source="combined",
            )
        )
        layout.addWidget(self.auditor_box)
        layout.addWidget(self.rep_box)
        layout.addWidget(self.invited_box)
        layout.addStretch(1)
        return page

    def _participant_group(self, role: str, *, source: str):
        box = QGroupBox(EXTERNAL_AUDIT_PARTICIPANT_ROLE_LABELS[role])
        layout = QVBoxLayout(box)
        row = QHBoxLayout()
        if source == "person":
            selector = PersonSelector(
                self,
                include_empty=True,
                allow_add_new=False,
                exclude_thp_linked=True,
            )
        elif source == "combined":
            from moduly.schuzky.ui.meeting_people_widgets import MeetingPersonTypeahead

            selector = MeetingPersonTypeahead(self, include_empty=True)
        else:
            selector = ThpWorkerSelector(self)
        add_btn = QPushButton("Přidat")
        remove_btn = QPushButton("Odebrat")
        up_btn = QPushButton("Nahoru")
        down_btn = QPushButton("Dolů")
        for button in (add_btn, remove_btn, up_btn, down_btn):
            button.setAutoDefault(False)
        row.addWidget(selector, 1)
        row.addWidget(add_btn)
        row.addWidget(remove_btn)
        row.addWidget(up_btn)
        row.addWidget(down_btn)
        layout.addLayout(row)
        list_widget = QListWidget()
        list_widget.setMinimumHeight(90)
        layout.addWidget(list_widget)

        add_btn.clicked.connect(
            lambda: self._add_participant(role, source, selector, list_widget)
        )
        remove_btn.clicked.connect(lambda: self._remove_participant(role, list_widget))
        up_btn.clicked.connect(lambda: self._move_participant(role, list_widget, -1))
        down_btn.clicked.connect(lambda: self._move_participant(role, list_widget, 1))
        return box, list_widget, selector

    def _build_attachments_tab(self) -> QWidget:
        self.attachments = ExternalAuditAttachmentStagingWidget()
        return self.attachments

    def _build_findings_tab(self) -> QWidget:
        self.findings = ExternalAuditFindingsWidget(
            self,
            get_draft=lambda: self._draft,
            ensure_saved=self._ensure_saved_for_tasks,
        )
        return self.findings

    def _ensure_saved_for_tasks(self) -> bool:
        """Úkol vyžaduje uložený audit + zjištění; při dirty nejdřív Uložit."""
        if not self._is_dirty():
            return self._draft.audit_id is not None
        answer = QMessageBox.question(
            self,
            EXTERNAL_AUDIT_EDITOR_TITLE_EDIT,
            "Externí audit má neuložené změny. Uložit nyní a pokračovat vytvořením úkolu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        return self._persist()

    def _load_draft_into_widgets(self) -> None:
        draft = self._draft
        type_index = self.audit_type.findData(draft.audit_type)
        self.audit_type.setCurrentIndex(
            type_index if type_index >= 0 else self.audit_type.findData(
                EXTERNAL_AUDIT_TYPE_SURVEILLANCE
            )
        )
        status_index = self.status.findData(draft.status)
        self.status.setCurrentIndex(
            status_index if status_index >= 0 else self.status.findData(
                EXTERNAL_AUDIT_STATUS_PLANNED
            )
        )
        self.ico.setText(draft.organization_ico)
        self.organization_name.setText(draft.organization_name)
        self.organization_address.setText(draft.organization_address)
        self.remind_from.set_date_value(draft.remind_from)
        self.note.setPlainText(draft.note or "")
        self._refresh_dates()
        self._refresh_participant_lists()
        self._refresh_visits_table()
        self.findings.refresh()
        self.attachments.set_audit_id(draft.audit_id)
        self.attachments.reset_staging()
        # staging state lives on draft
        self.attachments._staging = draft.attachments
        self.attachments._refresh_list()

    def _refresh_attachment_gate(self) -> None:
        self.attachments.set_audit_id(self._draft.audit_id)
        self.attachments._staging = self._draft.attachments
        if self._draft.audit_id is not None:
            self.attachments.reload_existing()
            self.attachments._refresh_list()

    def _refresh_dates(self) -> None:
        date_from, date_to = self._draft.derived_date_range()
        self.date_from.setText(format_display_date(date_from))
        self.date_to.setText(format_display_date(date_to))

    def _refresh_participant_lists(self) -> None:
        mapping = {
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR: self.auditor_list,
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE: self.rep_list,
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON: self.invited_list,
        }
        for role, widget in mapping.items():
            widget.clear()
            for participant in self._draft.participants_for_role(role):
                label = participant.display_name_snapshot or ""
                if participant.source_type == EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID:
                    label = (
                        f"{EXTERNAL_AUDIT_INVALID_AUDITOR_LABEL_PREFIX}: {label}"
                        if label
                        else EXTERNAL_AUDIT_INVALID_AUDITOR_LABEL_PREFIX
                    )
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, participant.client_key)
                widget.addItem(item)

    def _participant_names_for_visit(self, visit, role: str) -> str:
        names: list[str] = []
        for key in visit.participant_keys:
            participant = self._draft.participant_by_key(key)
            if participant and participant.role == role:
                names.append(participant.display_name_snapshot)
        return ", ".join(names)

    def _refresh_visits_table(self) -> None:
        from core.widgets.typed_table_sort import create_typed_item, typed_date, typed_text

        visits = list(self._draft.visits)
        self.visits_table.setRowCount(len(visits))
        for row, visit in enumerate(visits):
            values = [
                (format_display_date(visit.visit_date), typed_date(visit.visit_date)),
                (visit.time_from or "", typed_text(visit.time_from or "")),
                (visit.time_to or "", typed_text(visit.time_to or "")),
                (
                    visit.workplace_name_snapshot,
                    typed_text(visit.workplace_name_snapshot),
                ),
                (
                    self._participant_names_for_visit(
                        visit, EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
                    ),
                    None,
                ),
                (
                    self._participant_names_for_visit(
                        visit, EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE
                    ),
                    None,
                ),
                (
                    self._participant_names_for_visit(
                        visit, EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON
                    ),
                    None,
                ),
                (visit.note or "", typed_text(visit.note or "")),
            ]
            for col, (text, sort_value) in enumerate(values):
                if sort_value is None:
                    item = create_typed_item(text, typed_text(text))
                else:
                    item = create_typed_item(text, sort_value)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, visit.client_key)
                self.visits_table.setItem(row, col, item)
        self.visits_table.resizeColumnsToContents()
        self._refresh_visit_actions()
        self._refresh_dates()

    def _selected_visit_key(self) -> str | None:
        selected = self.visits_table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.visits_table.item(selected[0].row(), 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def _refresh_visit_actions(self) -> None:
        key = self._selected_visit_key()
        single = key is not None
        self.visit_edit_btn.setEnabled(single)
        self.visit_remove_btn.setEnabled(single)
        index = next(
            (
                i
                for i, visit in enumerate(self._draft.visits)
                if visit.client_key == key
            ),
            -1,
        )
        self.visit_up_btn.setEnabled(single and index > 0)
        self.visit_down_btn.setEnabled(
            single and index >= 0 and index < len(self._draft.visits) - 1
        )

    def _add_visit(self) -> None:
        dialog = ExternalAuditVisitDialog(
            self, participants=self._draft.participants
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_visit is None:
            return
        visit = dialog.result_visit
        visit.display_order = (len(self._draft.visits) + 1) * 10
        self._draft.visits.append(visit)
        self._refresh_visits_table()

    def _edit_visit(self) -> None:
        key = self._selected_visit_key()
        if key is None:
            return
        visit = next(
            (item for item in self._draft.visits if item.client_key == key), None
        )
        if visit is None:
            return
        dialog = ExternalAuditVisitDialog(
            self, visit=visit, participants=self._draft.participants
        )
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_visit is None:
            return
        index = self._draft.visits.index(visit)
        self._draft.visits[index] = dialog.result_visit
        self._refresh_visits_table()

    def _remove_visit(self) -> None:
        key = self._selected_visit_key()
        if key is None:
            return
        self._draft.visits = [
            visit for visit in self._draft.visits if visit.client_key != key
        ]
        self._renumber_visits()
        self._refresh_visits_table()

    def _move_visit(self, delta: int) -> None:
        key = self._selected_visit_key()
        if key is None:
            return
        index = next(
            (
                i
                for i, visit in enumerate(self._draft.visits)
                if visit.client_key == key
            ),
            -1,
        )
        target = index + delta
        if index < 0 or target < 0 or target >= len(self._draft.visits):
            return
        visits = self._draft.visits
        visits[index], visits[target] = visits[target], visits[index]
        self._renumber_visits()
        self._refresh_visits_table()
        self.visits_table.selectRow(target)

    def _renumber_visits(self) -> None:
        for index, visit in enumerate(self._draft.visits):
            visit.display_order = (index + 1) * 10

    def _add_participant(
        self, role: str, source: str, selector, list_widget: QListWidget
    ) -> None:
        if source == "combined":
            ref = selector.current_ref()
            if ref is None:
                return
            source_type = ref["source_type"]
            source_id = int(ref["source_id"])
            from moduly.schuzky.sluzby.meeting_service import meeting_service

            display = meeting_service.resolve_ref_display_name(ref)
            selector.clear_selection()
        elif source == "person":
            source_id = selector.current_person_id()
            source_type = EXTERNAL_AUDIT_SOURCE_PERSON
            if source_id is None:
                QMessageBox.information(
                    self,
                    "Účastníci",
                    "Vyberte osobu ze seznamu (nestačí jen opsat jméno).",
                )
                return
            person = person_service.get_by_id(source_id)
            display = person.display_name if person else f"Osoba #{source_id}"
            selector.set_person_id(None)
        else:
            source_id = selector.current_person_id()
            source_type = EXTERNAL_AUDIT_SOURCE_THP_WORKER
            if source_id is None:
                return
            worker = settings_service.get_worker_by_id(source_id)
            display = worker.display_name if worker else f"THP #{source_id}"
            selector.set_person_id(None)

        try:
            source_type, source_id, resolved_display = _resolve_participant_source(
                role=role,
                source_type=source_type,
                source_id=int(source_id),
                display_name_snapshot=str(display or "").strip() or None,
            )
            if not str(display or "").strip():
                display = resolved_display
        except ExternalAuditError as exc:
            QMessageBox.warning(self, "Účastníci", str(exc))
            return

        for existing in self._draft.participants_for_role(role):
            if (
                existing.source_type == source_type
                and int(existing.source_id) == int(source_id)
            ):
                QMessageBox.information(
                    self,
                    "Účastníci",
                    "Stejná osoba je v této roli už přidaná.",
                )
                return

        order = (len(self._draft.participants_for_role(role)) + 1) * 10
        self._draft.participants.append(
            ParticipantDraft(
                client_key=new_client_key(),
                role=role,
                source_type=source_type,
                source_id=int(source_id),
                display_name_snapshot=str(display or "").strip(),
                display_order=order,
            )
        )
        self._refresh_participant_lists()
        self._refresh_visits_table()

    def _remove_participant(self, role: str, list_widget: QListWidget) -> None:
        item = list_widget.currentItem()
        if item is None:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole))
        used = any(key in visit.participant_keys for visit in self._draft.visits)
        if used:
            answer = QMessageBox.question(
                self,
                "Účastníci",
                "Účastník je použit v programu. Odebrat jej i ze všech návštěv?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            for visit in self._draft.visits:
                visit.participant_keys = [
                    value for value in visit.participant_keys if value != key
                ]
        self._draft.participants = [
            participant
            for participant in self._draft.participants
            if participant.client_key != key
        ]
        self._refresh_participant_lists()
        self._refresh_visits_table()

    def _move_participant(
        self, role: str, list_widget: QListWidget, delta: int
    ) -> None:
        item = list_widget.currentItem()
        if item is None:
            return
        key = str(item.data(Qt.ItemDataRole.UserRole))
        role_items = self._draft.participants_for_role(role)
        index = next(
            (i for i, participant in enumerate(role_items) if participant.client_key == key),
            -1,
        )
        target = index + delta
        if index < 0 or target < 0 or target >= len(role_items):
            return
        role_items[index], role_items[target] = role_items[target], role_items[index]
        others = [
            participant
            for participant in self._draft.participants
            if participant.role != role
        ]
        for order, participant in enumerate(role_items):
            participant.display_order = (order + 1) * 10
        self._draft.participants = others + role_items
        self._refresh_participant_lists()
        self._refresh_visits_table()

    def _load_from_ares(self) -> None:
        ico = self.ico.text().strip()
        if not ico:
            QMessageBox.warning(self, "ARES", "Zadejte IČO.")
            return
        try:
            data = ares_service.find_by_ico(ico)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "ARES",
                f"Nepodařilo se načíst data z ARES.\n\n{exc}",
            )
            return
        if not data:
            QMessageBox.warning(self, "ARES", "Záznam nebyl nalezen.")
            return
        self.ico.setText(str(data.get("ico") or ico))
        self.organization_name.setText(str(data.get("name") or ""))
        self.organization_address.setText(str(data.get("address") or ""))
        self._draft.organization_extra = {"source": "ares"}

    def _collect_draft_from_widgets(self) -> ExternalAuditDraft:
        # Dokončit rozpracovanou editaci Připomenout od před snapshotem.
        self.remind_from._normalize_input()
        draft = self._draft
        draft.audit_type = str(self.audit_type.currentData() or draft.audit_type)
        draft.status = str(self.status.currentData() or draft.status)
        draft.organization_ico = self.ico.text().strip()
        draft.organization_name = self.organization_name.text().strip()
        draft.organization_address = self.organization_address.text().strip()
        draft.remind_from = self.remind_from.get_date()
        draft.note = self.note.toPlainText().strip() or None
        draft.attachments = self.attachments.staging
        return draft

    def _snapshot(self) -> dict:
        draft = self._collect_draft_from_widgets()
        return {
            "audit_type": draft.audit_type,
            "status": draft.status,
            "ico": draft.organization_ico,
            "name": draft.organization_name,
            "address": draft.organization_address,
            "remind_from": draft.remind_from,
            "note": draft.note,
            "participants": [
                (
                    p.client_key,
                    p.role,
                    p.source_type,
                    p.source_id,
                    p.display_name_snapshot,
                    p.display_order,
                )
                for p in draft.participants
            ],
            "visits": [
                (
                    v.client_key,
                    v.visit_date,
                    v.time_from,
                    v.time_to,
                    v.workplace_id,
                    v.workplace_name_snapshot,
                    v.display_order,
                    tuple(v.participant_keys),
                    v.note,
                )
                for v in draft.visits
            ],
            "findings": [
                (
                    f.client_key,
                    f.finding_type,
                    f.description,
                    f.status,
                    f.due_date,
                    f.resolution_text,
                    f.resolved_at,
                    f.display_order,
                    f.db_id,
                )
                for f in draft.findings
            ],
            "attachments_add": list(draft.attachments.pending_add_paths),
            "attachments_remove": list(draft.attachments.pending_remove_ids),
        }

    def _capture_baseline(self) -> None:
        self._baseline = deepcopy(self._snapshot())

    def _is_dirty(self) -> bool:
        return self._baseline != self._snapshot()

    def _persist(self) -> bool:
        draft = self._collect_draft_from_widgets()
        try:
            saved = external_audit_service.save_bundle(draft)
            self._draft.audit_id = int(saved.id)
            external_audit_service.flush_attachment_staging(
                int(saved.id), draft.attachments
            )
        except ExternalAuditError as exc:
            QMessageBox.warning(self, EXTERNAL_AUDIT_EDITOR_TITLE_EDIT, str(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                EXTERNAL_AUDIT_EDITOR_TITLE_EDIT,
                f"Uložení selhalo.\n\n{exc}",
            )
            return False

        # Obnovit draft z DB (stabilní ID/klíče) a baseline.
        self._draft = external_audit_service.load_draft(int(saved.id))
        self.setWindowTitle(EXTERNAL_AUDIT_EDITOR_TITLE_EDIT)
        configure_editor_close_button(self._close_btn, is_new=False)
        self._close_btn.setText(EDITOR_CLOSE_LABEL)
        self._load_draft_into_widgets()
        self._capture_baseline()
        self._refresh_attachment_gate()
        return True

    def _save_keep_open(self) -> None:
        self._persist()

    def _save_and_close(self) -> None:
        if self._persist():
            self._closing = True
            self.accept()

    def _request_close(self) -> None:
        if self._closing:
            self.reject()
            return
        if not self._is_dirty():
            self._closing = True
            self.reject()
            return
        decision = confirm_unsaved_editor_close(
            self, title=self.windowTitle()
        )
        if decision == "save":
            if self._persist():
                self._closing = True
                self.accept()
            return
        if decision == "discard":
            # Neukládat — staging se neaplikuje (orphan nevznikne).
            self._draft.attachments.clear()
            self._closing = True
            self.reject()
            return

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return
        if not self._is_dirty():
            event.accept()
            return
        decision = confirm_unsaved_editor_close(
            self, title=self.windowTitle()
        )
        if decision == "save":
            if self._persist():
                self._closing = True
                event.accept()
            else:
                event.ignore()
            return
        if decision == "discard":
            self._draft.attachments.clear()
            self._closing = True
            event.accept()
            return
        event.ignore()

    def reject(self) -> None:
        if self._closing or not self._is_dirty():
            super().reject()
            return
        self._request_close()
