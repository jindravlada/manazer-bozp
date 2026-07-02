from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.sluzby.finding_service import finding_service
from core.widgets.dialog_utils import exec_maximized
from core.widgets.finding_dialog import FindingDialog
from moduly.audity.constants import (
    AUDIT_PROGRAM_DASHBOARD_FILTER_OPEN_ONLY,
    AUDIT_PROGRAM_DASHBOARD_FILTER_OVERDUE,
    AUDIT_PROGRAM_DASHBOARD_FILTER_SEVERE,
    AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS,
    AUDIT_PROGRAM_DASHBOARD_TAB_TASKS,
    FINDING_DIALOG_TITLE,
    FINDING_SOURCE_LABEL,
)
from moduly.audity.sluzby.audit_program_dashboard_service import (
    ProgramDashboardSummary,
    ProgramFindingItem,
    ProgramTaskItem,
    audit_program_dashboard_service,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog

_SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class AuditProgramDashboardWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModulePanel")

        self._program_id: int | None = None
        self._findings: tuple[ProgramFindingItem, ...] = ()
        self._tasks: tuple[ProgramTaskItem, ...] = ()
        self._summary = ProgramDashboardSummary(0, 0, 0, 0, 0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        self._summary_panel = QWidget()
        summary_layout = QHBoxLayout(self._summary_panel)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(24)

        findings_column = QVBoxLayout()
        findings_column.setSpacing(2)
        findings_title = QLabel("ZJIŠTĚNÍ")
        findings_title.setObjectName("SectionTitle")
        self._findings_summary_label = QLabel()
        self._findings_summary_label.setObjectName("InfoText")
        findings_column.addWidget(findings_title)
        findings_column.addWidget(self._findings_summary_label)

        tasks_column = QVBoxLayout()
        tasks_column.setSpacing(2)
        tasks_title = QLabel("ÚKOLY")
        tasks_title.setObjectName("SectionTitle")
        self._tasks_summary_label = QLabel()
        self._tasks_summary_label.setObjectName("InfoText")
        tasks_column.addWidget(tasks_title)
        tasks_column.addWidget(self._tasks_summary_label)

        summary_layout.addLayout(findings_column, 1)
        summary_layout.addLayout(tasks_column, 1)
        layout.addWidget(self._summary_panel)

        self._tabs = QTabWidget()
        self._findings_tab = self._build_findings_tab()
        self._tasks_tab = self._build_tasks_tab()
        self._tabs.addTab(self._findings_tab, AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS)
        self._tabs.addTab(self._tasks_tab, AUDIT_PROGRAM_DASHBOARD_TAB_TASKS)
        layout.addWidget(self._tabs, 1)

        self._set_enabled(False)

    def _build_findings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        filters = QHBoxLayout()
        self._filter_open_only = QCheckBox(AUDIT_PROGRAM_DASHBOARD_FILTER_OPEN_ONLY)
        self._filter_overdue = QCheckBox(AUDIT_PROGRAM_DASHBOARD_FILTER_OVERDUE)
        self._filter_severe = QCheckBox(AUDIT_PROGRAM_DASHBOARD_FILTER_SEVERE)
        self._filter_open_only.setChecked(True)
        self._filter_open_only.toggled.connect(self._apply_finding_filters)
        self._filter_overdue.toggled.connect(self._apply_finding_filters)
        self._filter_severe.toggled.connect(self._apply_finding_filters)
        filters.addWidget(self._filter_open_only)
        filters.addWidget(self._filter_overdue)
        filters.addWidget(self._filter_severe)
        filters.addStretch()
        layout.addLayout(filters)

        self._findings_table = self._build_table(
            [
                "finding_id",
                "audit_id",
                "Pracoviště",
                "Audit",
                "Řídicí proces",
                "Název",
                "Závažnost",
                "Termín",
                "Stav",
                "Odpovědný",
            ]
        )
        self._findings_table.doubleClicked.connect(self._on_finding_double_clicked)
        layout.addWidget(self._findings_table, 1)
        return tab

    def _build_tasks_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tasks_table = self._build_table(
            [
                "task_id",
                "audit_id",
                "Pracoviště",
                "Audit",
                "Úkol",
                "Odpovědný",
                "Termín",
                "Splněno",
                "Stav",
            ]
        )
        self._tasks_table.doubleClicked.connect(self._on_task_double_clicked)
        layout.addWidget(self._tasks_table, 1)
        return tab

    @staticmethod
    def _build_table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setColumnHidden(0, True)
        table.setColumnHidden(1, True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(26)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        for column in range(2, len(headers)):
            if column == 5:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def load_program(self, program_id: int | None) -> None:
        self._program_id = program_id
        if program_id is None:
            self._findings = ()
            self._tasks = ()
            self._summary = ProgramDashboardSummary(0, 0, 0, 0, 0, 0, 0)
            self._set_enabled(False)
            self._fill_summary()
            self._fill_findings_table(())
            self._fill_tasks_table(())
            return

        self._findings = audit_program_dashboard_service.get_program_findings(program_id)
        self._tasks = audit_program_dashboard_service.get_program_tasks(program_id)
        self._summary = audit_program_dashboard_service.get_program_summary(program_id)
        self._set_enabled(True)
        self._fill_summary()
        self._apply_finding_filters()
        self._fill_tasks_table(self._tasks)

    def refresh(self) -> None:
        self.load_program(self._program_id)

    def _set_enabled(self, enabled: bool) -> None:
        self._tabs.setEnabled(enabled)
        self._summary_panel.setEnabled(enabled)

    def _fill_summary(self) -> None:
        summary = self._summary
        self._findings_summary_label.setText(
            f"Celkem: {summary.findings_total}\n"
            f"Otevřených: {summary.findings_open}\n"
            f"Po termínu: {summary.findings_overdue}\n"
            f"Kritických: {summary.findings_critical}"
        )
        self._tasks_summary_label.setText(
            f"Celkem: {summary.tasks_total}\n"
            f"Otevřených: {summary.tasks_open}\n"
            f"Po termínu: {summary.tasks_overdue}"
        )

    def _apply_finding_filters(self) -> None:
        rows = list(self._findings)
        if self._filter_open_only.isChecked():
            rows = [item for item in rows if item.is_open]
        if self._filter_overdue.isChecked():
            rows = [item for item in rows if item.is_overdue]
        if self._filter_severe.isChecked():
            rows = [item for item in rows if item.is_severe]
        self._fill_findings_table(tuple(rows))

    def _fill_findings_table(self, rows: tuple[ProgramFindingItem, ...]) -> None:
        self._findings_table.setSortingEnabled(False)
        self._findings_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                str(item.finding_id),
                str(item.audit_id),
                item.workplace_name,
                item.audit_number,
                item.process_name,
                item.title,
                item.severity_label,
                item.due_date.strftime("%d.%m.%Y") if item.due_date else "—",
                item.status_label,
                item.responsible_person,
            ]
            for column_index, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column_index == 7 and item.due_date is not None:
                    cell.setData(_SORT_ROLE, item.due_date.toordinal())
                self._findings_table.setItem(row_index, column_index, cell)
        self._findings_table.setSortingEnabled(True)

    def _fill_tasks_table(self, rows: tuple[ProgramTaskItem, ...]) -> None:
        self._tasks_table.setSortingEnabled(False)
        self._tasks_table.setRowCount(len(rows))
        for row_index, item in enumerate(rows):
            values = [
                str(item.task_id),
                str(item.audit_id),
                item.workplace_name,
                item.audit_number,
                item.title,
                item.responsible_person,
                item.due_date.strftime("%d.%m.%Y") if item.due_date else "—",
                item.completion_label,
                item.status_label,
            ]
            for column_index, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column_index == 6 and item.due_date is not None:
                    cell.setData(_SORT_ROLE, item.due_date.toordinal())
                self._tasks_table.setItem(row_index, column_index, cell)
        self._tasks_table.setSortingEnabled(True)

    def _on_finding_double_clicked(self, index) -> None:
        if index.column() == 3:
            audit_id = self._table_int(self._findings_table, index.row(), 1)
            if audit_id is not None:
                self._open_audit(audit_id)
            return

        finding_id = self._table_int(self._findings_table, index.row(), 0)
        if finding_id is None:
            return
        self._open_finding(finding_id)

    def _on_task_double_clicked(self, index) -> None:
        if index.column() == 3:
            audit_id = self._table_int(self._tasks_table, index.row(), 1)
            if audit_id is not None:
                self._open_audit(audit_id)
            return

        task_id = self._table_int(self._tasks_table, index.row(), 0)
        if task_id is None:
            return
        self._open_task(task_id)

    @staticmethod
    def _table_int(table: QTableWidget, row: int, column: int) -> int | None:
        item = table.item(row, column)
        if item is None:
            return None
        return int(item.text())

    def _open_finding(self, finding_id: int) -> None:
        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            QMessageBox.warning(self, AUDIT_PROGRAM_DASHBOARD_TAB_FINDINGS, "Zjištění nebylo nalezeno.")
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

    def _open_task(self, task_id: int) -> None:
        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, AUDIT_PROGRAM_DASHBOARD_TAB_TASKS, "Úkol nebyl nalezen.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            if data["title"]:
                task_service.update_task(task_id=task_id, **data)
        self.refresh()

    def _open_audit(self, audit_id: int) -> None:
        from moduly.audity.ui.audit_dialog import AuditDialog

        audit = audit_service.get_by_id(audit_id)
        if audit is None:
            QMessageBox.warning(self, self.windowTitle(), "Audit nebyl nalezen.")
            self.refresh()
            return

        dialog = AuditDialog(self, audit=audit)
        if exec_maximized(dialog):
            data = dialog.get_data()
            audit_service.update_audit(audit_id, **dialog.prepare_save_payload(data))
            dialog.save_commission_members(audit_id, data)
        self.refresh()
