from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.sluzby.finding_service import finding_service
from core.widgets.dialog_utils import exec_maximized
from core.widgets.finding_dialog import FindingDialog
from moduly.audity.constants import FINDING_DIALOG_TITLE, FINDING_SOURCE_LABEL, TAB_WORKPLACE_HISTORY
from moduly.audity.sluzby.audit_history_service import (
    WorkplaceHistory,
    audit_history_service,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog


class AuditWorkplaceHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._audit = None
        self._history: WorkplaceHistory | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._hint_label = QLabel(
            "Historie pracoviště bude dostupná po výběru auditovaného provozu."
        )
        self._hint_label.setWordWrap(True)
        self._hint_label.setObjectName("InfoText")
        layout.addWidget(self._hint_label)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("InfoText")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        last_audit_group = QGroupBox("Poslední audit")
        last_audit_layout = QVBoxLayout(last_audit_group)
        self._last_audit_form = QWidget()
        form = QFormLayout(self._last_audit_form)
        self._last_audit_date_value = QLabel("—")
        self._last_audit_number_value = QLabel("—")
        self._last_audit_leader_value = QLabel("—")
        self._last_audit_conclusion_value = QLabel("—")
        self._last_audit_conclusion_value.setWordWrap(True)
        form.addRow("Datum:", self._last_audit_date_value)
        form.addRow("Číslo auditu:", self._last_audit_number_value)
        form.addRow("Vedoucí auditor:", self._last_audit_leader_value)
        form.addRow("Závěr:", self._last_audit_conclusion_value)
        last_audit_layout.addWidget(self._last_audit_form)

        last_audit_actions = QHBoxLayout()
        self._open_last_audit_btn = QPushButton("Otevřít audit")
        self._open_last_audit_btn.clicked.connect(self._open_last_audit)
        last_audit_actions.addWidget(self._open_last_audit_btn)
        last_audit_actions.addStretch()
        last_audit_layout.addLayout(last_audit_actions)
        layout.addWidget(last_audit_group)

        findings_group = QGroupBox("Neuzavřená zjištění")
        findings_layout = QVBoxLayout(findings_group)
        self._findings_table = self._build_table(
            ["ID", "Název", "Závažnost", "Termín", "Stav", "Audit"]
        )
        self._findings_table.doubleClicked.connect(self._open_selected_finding)
        findings_layout.addWidget(self._findings_table)
        layout.addWidget(findings_group)

        tasks_group = QGroupBox("Otevřené úkoly")
        tasks_layout = QVBoxLayout(tasks_group)
        self._tasks_table = self._build_table(
            ["ID", "Úkol", "Odpovědný", "Termín", "Splněno"]
        )
        self._tasks_table.doubleClicked.connect(self._open_selected_task)
        tasks_layout.addWidget(self._tasks_table)
        layout.addWidget(tasks_group)

        processes_group = QGroupBox("Řídicí procesy")
        processes_layout = QVBoxLayout(processes_group)
        self._process_list = QListWidget()
        processes_layout.addWidget(self._process_list)
        layout.addWidget(processes_group, 1)

        self._content_widgets = (
            self._summary_label,
            last_audit_group,
            findings_group,
            tasks_group,
            processes_group,
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
        return table

    def load_audit(self, audit) -> None:
        self._audit = audit
        self.refresh()

    def refresh(self) -> None:
        workplace_id = getattr(self._audit, "workplace_id", None) if self._audit else None
        exclude_audit_id = getattr(self._audit, "id", None) if self._audit else None

        if workplace_id is None:
            self._history = None
            self._set_content_visible(False)
            self._hint_label.setVisible(True)
            return

        self._history = audit_history_service.get_workplace_history(
            workplace_id,
            exclude_audit_id=exclude_audit_id,
        )
        self._hint_label.setVisible(False)
        self._set_content_visible(True)
        self._fill_summary()
        self._fill_last_audit()
        self._fill_findings()
        self._fill_tasks()
        self._fill_processes()

    def _set_content_visible(self, visible: bool) -> None:
        for widget in self._content_widgets:
            widget.setVisible(visible)

    def _fill_summary(self) -> None:
        history = self._history
        if history is None:
            self._summary_label.setText("")
            return

        summary = history.summary
        last_audit_text = (
            summary.last_audit_date.strftime("%d.%m.%Y")
            if summary.last_audit_date is not None
            else "—"
        )
        self._summary_label.setText(
            "──────────────────────────\n"
            f"Poslední audit:\n{last_audit_text}\n"
            f"Neuzavřená zjištění:\n{summary.open_findings_count}\n"
            f"Otevřené úkoly:\n{summary.open_tasks_count}\n"
            f"Auditovaných procesů:\n"
            f"{summary.audited_processes_count} / {summary.total_processes_count}\n"
            "──────────────────────────"
        )

    def _fill_last_audit(self) -> None:
        history = self._history
        if history is None or history.last_audit is None:
            self._last_audit_date_value.setText("—")
            self._last_audit_number_value.setText("—")
            self._last_audit_leader_value.setText("—")
            self._last_audit_conclusion_value.setText("Dosud neproběhl žádný audit tohoto pracoviště.")
            self._open_last_audit_btn.setEnabled(False)
            return

        last_audit = history.last_audit
        self._last_audit_date_value.setText(
            last_audit.audit_date.strftime("%d.%m.%Y")
            if last_audit.audit_date is not None
            else "—"
        )
        self._last_audit_number_value.setText(last_audit.audit_number)
        self._last_audit_leader_value.setText(last_audit.leader_name)
        self._last_audit_conclusion_value.setText(last_audit.conclusion)
        self._open_last_audit_btn.setEnabled(True)

    def _fill_findings(self) -> None:
        history = self._history
        rows = history.findings if history is not None else ()
        self._findings_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                str(item.finding_id),
                item.title,
                item.severity_label,
                item.due_date.strftime("%d.%m.%Y") if item.due_date else "—",
                item.status_label,
                item.audit_number,
            ]
            for column_index, value in enumerate(values):
                self._findings_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

    def _fill_tasks(self) -> None:
        history = self._history
        rows = history.tasks if history is not None else ()
        self._tasks_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                str(item.task_id),
                item.title,
                item.responsible_person,
                item.due_date.strftime("%d.%m.%Y") if item.due_date else "—",
                item.completion_label,
            ]
            for column_index, value in enumerate(values):
                self._tasks_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(value),
                )

    def _fill_processes(self) -> None:
        self._process_list.clear()
        history = self._history
        if history is None:
            return

        for item in history.process_history:
            if item.last_audit_date is None:
                label = f"{item.process_name}\nNikdy"
            else:
                label = f"{item.process_name}\n✔ {item.last_audit_label}"
            list_item = QListWidgetItem(label)
            list_item.setFlags(list_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._process_list.addItem(list_item)

    def _open_last_audit(self) -> None:
        if self._history is None or self._history.last_audit is None:
            return
        self._open_audit(self._history.last_audit.audit_id)

    def _open_audit(self, audit_id: int) -> None:
        from moduly.audity.ui.audit_dialog import AuditDialog

        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, TAB_WORKPLACE_HISTORY, "Audit nebyl nalezen.")
            self.refresh()
            return

        dialog = AuditDialog(self, audit=audit)
        if exec_maximized(dialog):
            data = dialog.get_data()
            audit_service.update_audit(audit_id, **dialog.prepare_save_payload(data))
            dialog.save_commission_members(audit_id, data)
        self.refresh()

    def _selected_table_id(self, table: QTableWidget) -> int | None:
        selected = table.selectionModel().selectedRows()
        if not selected:
            return None
        item = table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _open_selected_finding(self) -> None:
        finding_id = self._selected_table_id(self._findings_table)
        if finding_id is None:
            return

        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            QMessageBox.warning(self, TAB_WORKPLACE_HISTORY, "Zjištění nebylo nalezeno.")
            self.refresh()
            return

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
            finding_service.update(finding_id, **dialog.get_data())
        self.refresh()

    def _open_selected_task(self) -> None:
        task_id = self._selected_table_id(self._tasks_table)
        if task_id is None:
            return

        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, TAB_WORKPLACE_HISTORY, "Úkol nebyl nalezen.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"]:
                task_service.update_task(task_id=task_id, **data)
        self.refresh()
