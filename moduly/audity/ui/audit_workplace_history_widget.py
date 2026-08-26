"""Záložka Úvod — historie provozu a změny od posledního auditu (AUDIT-INTRO-1)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.shared.finding_display import FINDING_TYPE_LABELS
from core.shared.sluzby.finding_service import finding_service
from core.widgets.dialog_utils import exec_maximized
from core.widgets.finding_dialog import FindingDialog
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.audity.constants import (
    AUDIT_INTRO_CHANGES_LABEL,
    AUDIT_INTRO_FINDINGS_GROUP,
    AUDIT_INTRO_FIRST_AUDIT_MESSAGE,
    AUDIT_INTRO_NO_WORKPLACE_HINT,
    AUDIT_INTRO_PREVIOUS_AUDITS_GROUP,
    AUDIT_INTRO_TASKS_GROUP,
    FINDING_DIALOG_TITLE,
    FINDING_SOURCE_LABEL,
    TAB_UVOD,
)
from moduly.audity.sluzby.audit_history_service import (
    WorkplaceHistory,
    audit_history_service,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog

_FINDING_STATUS_ORDER = ("Otevřené", "V procesu", "Vypořádané")
_FINDING_SEVERITY_ORDER = tuple(FINDING_TYPE_LABELS.values())
_TASK_STATUS_ORDER = (
    "Aktivní",
    "Po termínu",
    "Splněno - čeká na kontrolu",
    "Ukončeno",
    "Zrušeno",
)


def _order_status(value: str, order: tuple[str, ...]):
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class AuditWorkplaceHistoryWidget(QWidget):
    """Záložka Úvod: předchozí audity, zjištění, úkoly a změny od posledního auditu."""

    content_modified = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._audit = None
        self._history: WorkplaceHistory | None = None
        self._deferred_edits = None
        self._loaded = False
        self._changes_loaded_from_audit: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        self._hint_label = QLabel(AUDIT_INTRO_NO_WORKPLACE_HINT)
        self._hint_label.setWordWrap(True)
        self._hint_label.setObjectName("InfoText")
        layout.addWidget(self._hint_label)

        self._first_audit_label = QLabel(AUDIT_INTRO_FIRST_AUDIT_MESSAGE)
        self._first_audit_label.setWordWrap(True)
        self._first_audit_label.setObjectName("InfoText")
        self._first_audit_label.setVisible(False)
        layout.addWidget(self._first_audit_label)

        changes_group = QGroupBox(AUDIT_INTRO_CHANGES_LABEL)
        changes_layout = QVBoxLayout(changes_group)
        self._changes_edit = QPlainTextEdit()
        self._changes_edit.setPlaceholderText(
            "Popište relevantní změny provozu od posledního auditu…"
        )
        self._changes_edit.setMinimumHeight(110)
        self._changes_edit.textChanged.connect(self._on_changes_edited)
        changes_layout.addWidget(self._changes_edit)
        layout.addWidget(changes_group)

        audits_group = QGroupBox(AUDIT_INTRO_PREVIOUS_AUDITS_GROUP)
        audits_layout = QVBoxLayout(audits_group)
        self._audits_empty = QLabel("Žádné předchozí audity.")
        self._audits_empty.setObjectName("InfoText")
        audits_layout.addWidget(self._audits_empty)
        self._audits_table = self._build_table(
            ["ID", "Datum", "Číslo", "Stav", "Typ", "Program"]
        )
        self._audits_table.doubleClicked.connect(self._open_selected_audit)
        audits_layout.addWidget(self._audits_table)
        layout.addWidget(audits_group)

        findings_group = QGroupBox(AUDIT_INTRO_FINDINGS_GROUP)
        findings_layout = QVBoxLayout(findings_group)
        self._findings_empty = QLabel("Žádná zjištění z předchozích auditů.")
        self._findings_empty.setObjectName("InfoText")
        findings_layout.addWidget(self._findings_empty)
        self._findings_table = self._build_table(
            [
                "ID",
                "Zjištění",
                "Stav",
                "Závažnost",
                "Audit",
                "Vznik",
                "Vypořádání",
            ]
        )
        self._findings_table.doubleClicked.connect(self._open_selected_finding)
        findings_layout.addWidget(self._findings_table)
        layout.addWidget(findings_group)

        tasks_group = QGroupBox(AUDIT_INTRO_TASKS_GROUP)
        tasks_layout = QVBoxLayout(tasks_group)
        self._tasks_empty = QLabel("Žádné úkoly navázané na zjištění z předchozích auditů.")
        self._tasks_empty.setObjectName("InfoText")
        tasks_layout.addWidget(self._tasks_empty)
        self._tasks_table = self._build_table(
            [
                "ID",
                "Úkol",
                "Stav",
                "Odpovědný",
                "Termín",
                "Dokončení",
                "Zjištění",
                "Audit",
            ]
        )
        self._tasks_table.doubleClicked.connect(self._open_selected_task)
        tasks_layout.addWidget(self._tasks_table)
        layout.addWidget(tasks_group)
        layout.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll)

        self._content_widgets = (
            changes_group,
            audits_group,
            findings_group,
            tasks_group,
        )
        self._set_content_visible(False)

    @staticmethod
    def _build_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setColumnHidden(0, True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in range(2, len(headers)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        enable_typed_sorting(table)
        return table

    def load_audit(self, audit) -> None:
        """Uloží kontext; historii načte lazy při ensure_loaded/refresh."""
        self._audit = audit
        self._loaded = False
        self._history = None
        raw = getattr(audit, "changes_since_last", None) if audit is not None else None
        text = "" if raw is None else str(raw)
        self._changes_loaded_from_audit = text
        self._changes_edit.blockSignals(True)
        self._changes_edit.setPlainText(text)
        self._changes_edit.blockSignals(False)

    def ensure_loaded(self) -> None:
        if self._loaded:
            return
        self.refresh()

    def set_deferred_edits(self, deferred_edits) -> None:
        self._deferred_edits = deferred_edits

    def get_data(self) -> dict:
        return {"changes_since_last": self._changes_edit.toPlainText()}

    def discard_changes(self) -> None:
        text = self._changes_loaded_from_audit or ""
        self._changes_edit.blockSignals(True)
        self._changes_edit.setPlainText(text)
        self._changes_edit.blockSignals(False)

    def _on_changes_edited(self) -> None:
        self.content_modified.emit()

    def refresh(self) -> None:
        """Obnoví jen data Úvodu — bez reloadu metodiky AuditDialogu."""
        workplace_id = getattr(self._audit, "workplace_id", None) if self._audit else None

        if workplace_id is None:
            self._history = None
            self._loaded = True
            self._set_content_visible(False)
            self._hint_label.setVisible(True)
            self._first_audit_label.setVisible(False)
            return

        self._history = audit_history_service.get_workplace_history(
            workplace_id,
            current_audit=self._audit,
            include_process_history=False,
        )
        self._loaded = True
        self._hint_label.setVisible(False)
        self._set_content_visible(True)
        self._first_audit_label.setVisible(bool(self._history.is_first_audit))
        self._fill_audits()
        self._fill_findings()
        self._fill_tasks()

    def _set_content_visible(self, visible: bool) -> None:
        for widget in self._content_widgets:
            widget.setVisible(visible)

    def _fill_audits(self) -> None:
        history = self._history
        rows = history.previous_audits if history is not None else ()
        self._audits_empty.setVisible(len(rows) == 0)
        self._audits_table.setVisible(len(rows) > 0)
        with sorting_paused(self._audits_table):
            self._audits_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                record_id = int(item.audit_id)
                date_display = (
                    item.audit_date.strftime("%d.%m.%Y") if item.audit_date else "—"
                )
                values = [
                    (str(item.audit_id), typed_int(item.audit_id)),
                    (
                        date_display,
                        typed_date(item.audit_date) if item.audit_date else typed_empty(),
                    ),
                    (item.audit_number, _text_or_empty(item.audit_number)),
                    (item.status, _text_or_empty(item.status)),
                    (item.audit_type, _text_or_empty(item.audit_type)),
                    (item.program_name, _text_or_empty(item.program_name)),
                ]
                for column_index, (display_text, sort_value) in enumerate(values):
                    self._audits_table.setItem(
                        row_index,
                        column_index,
                        create_typed_item(display_text, sort_value, stable_id=record_id),
                    )

    def _fill_findings(self) -> None:
        history = self._history
        rows = history.findings if history is not None else ()
        self._findings_empty.setVisible(len(rows) == 0)
        self._findings_table.setVisible(len(rows) > 0)
        with sorting_paused(self._findings_table):
            self._findings_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                record_id = int(item.finding_id)
                created = (
                    item.created_at.strftime("%d.%m.%Y") if item.created_at else "—"
                )
                resolved = (
                    item.resolved_at.strftime("%d.%m.%Y") if item.resolved_at else "—"
                )
                values = [
                    (str(item.finding_id), typed_int(item.finding_id)),
                    (item.title, _text_or_empty(item.title)),
                    (item.status_label, _order_status(item.status_label, _FINDING_STATUS_ORDER)),
                    (
                        item.severity_label,
                        _order_status(item.severity_label, _FINDING_SEVERITY_ORDER),
                    ),
                    (item.audit_number, _text_or_empty(item.audit_number)),
                    (
                        created,
                        typed_date(item.created_at) if item.created_at else typed_empty(),
                    ),
                    (
                        resolved,
                        typed_date(item.resolved_at) if item.resolved_at else typed_empty(),
                    ),
                ]
                for column_index, (display_text, sort_value) in enumerate(values):
                    self._findings_table.setItem(
                        row_index,
                        column_index,
                        create_typed_item(display_text, sort_value, stable_id=record_id),
                    )

    def _fill_tasks(self) -> None:
        history = self._history
        rows = history.tasks if history is not None else ()
        self._tasks_empty.setVisible(len(rows) == 0)
        self._tasks_table.setVisible(len(rows) > 0)
        with sorting_paused(self._tasks_table):
            self._tasks_table.setRowCount(len(rows))
            for row_index, item in enumerate(rows):
                record_id = int(item.task_id)
                due_display = item.due_date.strftime("%d.%m.%Y") if item.due_date else "—"
                completed_display = (
                    item.completed_date.strftime("%d.%m.%Y") if item.completed_date else "—"
                )
                values = [
                    (str(item.task_id), typed_int(item.task_id)),
                    (item.title, _text_or_empty(item.title)),
                    (item.status_label, _order_status(item.status_label, _TASK_STATUS_ORDER)),
                    (item.responsible_person, _text_or_empty(item.responsible_person)),
                    (due_display, typed_date(item.due_date) if item.due_date else typed_empty()),
                    (
                        completed_display,
                        typed_date(item.completed_date)
                        if item.completed_date
                        else typed_empty(),
                    ),
                    (item.finding_title, _text_or_empty(item.finding_title)),
                    (item.audit_number, _text_or_empty(item.audit_number)),
                ]
                for column_index, (display_text, sort_value) in enumerate(values):
                    self._tasks_table.setItem(
                        row_index,
                        column_index,
                        create_typed_item(display_text, sort_value, stable_id=record_id),
                    )

    def _selected_table_id(self, table: QTableWidget) -> int | None:
        selected = table.selectionModel().selectedRows()
        if not selected:
            return None
        item = table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _open_selected_audit(self) -> None:
        audit_id = self._selected_table_id(self._audits_table)
        if audit_id is None:
            return
        self._open_audit(audit_id)

    def _open_audit(self, audit_id: int) -> None:
        from moduly.audity.ui.audit_dialog import AuditDialog

        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, TAB_UVOD, "Audit nebyl nalezen.")
            self.refresh()
            return

        dialog = AuditDialog(self, audit=audit)
        exec_maximized(dialog)
        self.refresh()

    def _open_selected_finding(self) -> None:
        finding_id = self._selected_table_id(self._findings_table)
        if finding_id is None:
            return

        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            QMessageBox.warning(self, TAB_UVOD, "Zjištění nebylo nalezeno.")
            self.refresh()
            return

        if self._deferred_edits is not None:
            viewed = self._deferred_edits.get_finding(finding_id)
            if viewed is not None:
                finding = viewed

        dialog = FindingDialog(
            self,
            finding=finding,
            title=FINDING_DIALOG_TITLE,
            knowledge_source={
                "source_label": FINDING_SOURCE_LABEL,
                "area_label": finding.source_area_label or "—",
                "section_label": finding.source_section_label or "—",
                "control_point_label": finding.source_control_point_label
                or finding.reference_label
                or "—",
            },
        )
        if dialog.exec():
            data = dialog.get_data()
            if self._deferred_edits is not None:
                self._deferred_edits.stage_finding_update(finding_id, data)
            else:
                finding_service.update(finding_id, **data)
        self.refresh()

    def _open_selected_task(self) -> None:
        task_id = self._selected_table_id(self._tasks_table)
        if task_id is None:
            return

        task = (
            self._deferred_edits.get_task(task_id)
            if self._deferred_edits is not None
            else task_service.get_task_by_id(task_id)
        )
        if task is None:
            QMessageBox.warning(self, TAB_UVOD, "Úkol nebyl nalezen.")
            self.refresh()
            return

        if self._deferred_edits is not None:
            dialog = TaskDialog(
                self,
                task=task,
                persist_handler=lambda current, data: self._deferred_edits.stage_task_update(
                    int(current.id), data
                ),
            )
        else:
            dialog = TaskDialog(self, task=task)
        dialog.exec()
        self.refresh()
