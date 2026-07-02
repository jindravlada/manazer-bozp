"""Dialog pro správu programů auditů."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_close_push_button
from moduly.audity.constants import (
    AUDIT_PROGRAM_ADD_BUTTON,
    AUDIT_PROGRAM_BUTTON_LABEL,
    AUDIT_PROGRAM_CENTER_PANEL_TITLE,
    AUDIT_PROGRAM_DISTRIBUTE_PROCESSES_BUTTON,
    AUDIT_PROGRAM_GENERATE_VISITS_BUTTON,
    AUDIT_PROGRAM_LEFT_PANEL_TITLE,
    AUDIT_PROGRAM_OVERVIEW_COLUMNS,
    AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON,
    AUDIT_PROGRAM_RIGHT_PANEL_TITLE,
    AUDIT_PROGRAM_STATUS_LABELS,
    AUDIT_PROGRAM_STATUS_OVERVIEW_REFRESHED,
    AUDIT_PROGRAM_STATUS_PROCESSES_DISTRIBUTED,
    AUDIT_PROGRAM_STATUS_PROGRAM_CREATED,
    AUDIT_PROGRAM_STATUS_PROGRAM_UPDATED,
    AUDIT_PROGRAM_STATUS_VISITS_GENERATED,
    AUDIT_PROGRAM_WINDOW_TITLE,
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    PROCESS_PANEL_LEFT_WIDTH,
)
from moduly.audity.modely.audit_program import AuditProgram
from moduly.audity.sluzby.audit_program_service import (
    AuditProgramCoverage,
    AuditProgramOverview,
    audit_program_service,
)
from moduly.audity.ui.audit_program_create_dialog import AuditProgramCreateDialog


class AuditProgramManagerDialog(QDialog):
    """Pracovní plocha programu auditů — přehled, generování a pokrytí."""

    _PROGRAM_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(AUDIT_PROGRAM_WINDOW_TITLE)
        self._selected_program_id: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        splitter = QSplitter()

        self._program_list = QListWidget()
        self._program_list.currentItemChanged.connect(self._on_program_selected)

        left_panel = self._build_left_panel()
        center_panel = self._build_center_panel()
        right_panel = self._build_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 520, 520])

        root.addWidget(splitter, 1)
        root.addLayout(self._build_footer())

        self._reload_program_list()

    def exec(self) -> int:
        self.showMaximized()
        return super().exec()

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel(AUDIT_PROGRAM_LEFT_PANEL_TITLE)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        toolbar = QHBoxLayout()
        self._new_program_btn = QPushButton(AUDIT_PROGRAM_ADD_BUTTON)
        self._edit_program_btn = QPushButton("Upravit")
        self._refresh_programs_btn = QPushButton("Obnovit")
        self._new_program_btn.clicked.connect(self._create_program)
        self._edit_program_btn.clicked.connect(self._edit_program)
        self._refresh_programs_btn.clicked.connect(self._reload_program_list)
        toolbar.addWidget(self._new_program_btn)
        toolbar.addWidget(self._edit_program_btn)
        toolbar.addWidget(self._refresh_programs_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        layout.addWidget(self._program_list, 1)

        panel.setMinimumWidth(PROCESS_PANEL_LEFT_WIDTH)
        panel.setMaximumWidth(PROCESS_PANEL_LEFT_WIDTH)
        return panel

    def _build_center_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel(AUDIT_PROGRAM_CENTER_PANEL_TITLE)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._hint_label = QLabel("Vyberte program auditů vlevo nebo vytvořte nový.")
        self._hint_label.setObjectName("InfoText")
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label)

        self._detail_form = QWidget()
        form = QFormLayout(self._detail_form)
        form.setSpacing(8)

        self._name_value = QLabel()
        self._period_value = QLabel()
        self._status_value = QLabel()
        self._standards_value = QLabel()
        self._standards_value.setWordWrap(True)
        self._workplace_count_value = QLabel()
        self._visit_count_value = QLabel()
        self._completion_value = QLabel()

        form.addRow("Název:", self._name_value)
        form.addRow("Období:", self._period_value)
        form.addRow("Stav:", self._status_value)
        form.addRow("Normy:", self._standards_value)
        form.addRow("Počet pracovišť:", self._workplace_count_value)
        form.addRow("Počet návštěv:", self._visit_count_value)
        form.addRow("Plnění:", self._completion_value)
        self._detail_form.setVisible(False)
        layout.addWidget(self._detail_form)

        actions = QHBoxLayout()
        self._generate_visits_btn = QPushButton(AUDIT_PROGRAM_GENERATE_VISITS_BUTTON)
        self._distribute_processes_btn = QPushButton(AUDIT_PROGRAM_DISTRIBUTE_PROCESSES_BUTTON)
        self._refresh_overview_btn = QPushButton(AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON)
        self._generate_visits_btn.clicked.connect(self._generate_visits)
        self._distribute_processes_btn.clicked.connect(self._distribute_processes)
        self._refresh_overview_btn.clicked.connect(self._refresh_overview)
        actions.addWidget(self._generate_visits_btn)
        actions.addWidget(self._distribute_processes_btn)
        actions.addWidget(self._refresh_overview_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self._set_action_buttons_enabled(False)
        layout.addStretch()
        return panel

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(AUDIT_PROGRAM_RIGHT_PANEL_TITLE)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self._overview_table = QTableWidget(0, len(AUDIT_PROGRAM_OVERVIEW_COLUMNS))
        self._overview_table.setHorizontalHeaderLabels(list(AUDIT_PROGRAM_OVERVIEW_COLUMNS))
        self._overview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._overview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._overview_table.setAlternatingRowColors(True)
        self._overview_table.verticalHeader().setVisible(False)
        layout.addWidget(self._overview_table, 1)
        return panel

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)

        self._status_label = QLabel()
        self._status_label.setObjectName("InfoText")

        self._close_btn = QPushButton("Zavřít")
        configure_close_push_button(self._close_btn)
        self._close_btn.clicked.connect(self.reject)

        footer.addWidget(self._status_label, 0)
        footer.addStretch(1)
        footer.addWidget(self._close_btn, 0)
        return footer

    def _reload_program_list(self, *, select_program_id: int | None = None) -> None:
        current_id = select_program_id or self._selected_program_id
        self._program_list.blockSignals(True)
        self._program_list.clear()

        programs = audit_program_service.list_programs()
        selected_item: QListWidgetItem | None = None
        for program in programs:
            item = QListWidgetItem(self._program_list_label(program))
            item.setData(self._PROGRAM_ROLE, program.id)
            self._program_list.addItem(item)
            if current_id == program.id:
                selected_item = item

        if selected_item is not None:
            self._program_list.setCurrentItem(selected_item)
        elif self._program_list.count() > 0:
            self._program_list.setCurrentRow(0)
        self._program_list.blockSignals(False)

        current = self._program_list.currentItem()
        if current is not None:
            self._selected_program_id = int(current.data(self._PROGRAM_ROLE))
            self._refresh_selected_program_views()
        else:
            self._selected_program_id = None
            self._show_empty_state()

    def _create_program(self) -> None:
        dialog = AuditProgramCreateDialog(self)
        dialog.set_default_period()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        program = audit_program_service.create_program(**dialog.program_payload())
        audit_program_service.sync_workplaces_from_settings(program.id)
        self._set_status(AUDIT_PROGRAM_STATUS_PROGRAM_CREATED)
        self._reload_program_list(select_program_id=program.id)

    def _edit_program(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            return

        program = audit_program_service.get_program(program_id)
        if program is None:
            self._reload_program_list()
            return

        dialog = AuditProgramCreateDialog(self, program=program)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        audit_program_service.update_program(program_id, **dialog.program_payload())
        self._set_status(AUDIT_PROGRAM_STATUS_PROGRAM_UPDATED)
        self._reload_program_list(select_program_id=program_id)

    def _generate_visits(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            return

        try:
            audit_program_service.sync_workplaces_from_settings(program_id)
            audit_program_service.generate_visits(program_id)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_VISITS_GENERATED)
        self._refresh_selected_program_views()

    def _distribute_processes(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            return

        try:
            audit_program_service.distribute_processes(program_id)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_PROCESSES_DISTRIBUTED)
        self._refresh_selected_program_views()

    def _refresh_overview(self) -> None:
        if self._selected_program_id is None:
            return
        self._set_status(AUDIT_PROGRAM_STATUS_OVERVIEW_REFRESHED)
        self._refresh_selected_program_views()

    def _on_program_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._selected_program_id = None
            self._show_empty_state()
            return

        self._selected_program_id = int(current.data(self._PROGRAM_ROLE))
        self._refresh_selected_program_views()

    def _refresh_selected_program_views(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            self._show_empty_state()
            return

        overview = audit_program_service.get_program_overview(program_id)
        coverage = audit_program_service.get_program_coverage(program_id)
        if overview is None or coverage is None:
            self._reload_program_list()
            return

        self._hint_label.setVisible(False)
        self._detail_form.setVisible(True)
        self._set_action_buttons_enabled(True)
        self._fill_detail_panel(overview, coverage)
        self._fill_overview_table(overview, coverage)

    def _fill_detail_panel(
        self,
        overview: AuditProgramOverview,
        coverage: AuditProgramCoverage,
    ) -> None:
        program = overview.program
        self._name_value.setText(program.name or "—")
        self._period_value.setText(self._format_period(program.date_from, program.date_to))
        self._status_value.setText(
            AUDIT_PROGRAM_STATUS_LABELS.get(program.status, program.status)
        )
        standards = audit_program_service.parse_standards(program.standards_json)
        self._standards_value.setText(", ".join(standards) if standards else "—")
        self._workplace_count_value.setText(str(coverage.workplace_count))
        self._visit_count_value.setText(str(coverage.visit_count))
        self._completion_value.setText(f"{coverage.completion_percent:.0f} %")

    def _fill_overview_table(
        self,
        overview: AuditProgramOverview,
        coverage: AuditProgramCoverage,
    ) -> None:
        rows = self._workplace_rows(overview, coverage)
        self._overview_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                self._overview_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(str(value)),
                )
        self._overview_table.resizeColumnsToContents()

    def _workplace_rows(
        self,
        overview: AuditProgramOverview,
        coverage: AuditProgramCoverage,
    ) -> list[tuple[str, int, int, int, str]]:
        visits_by_workplace: dict[int | None, list] = defaultdict(list)
        for visit in overview.visits:
            visits_by_workplace[visit.workplace_id].append(visit)

        visit_ids_by_workplace = {
            workplace_id: {visit.id for visit in visits}
            for workplace_id, visits in visits_by_workplace.items()
        }

        processes_by_workplace: dict[int | None, list] = defaultdict(list)
        for visit_process in overview.visit_processes:
            for workplace_id, visit_ids in visit_ids_by_workplace.items():
                if visit_process.visit_id in visit_ids:
                    processes_by_workplace[workplace_id].append(visit_process)
                    break

        rows: list[tuple[str, int, int, int, str]] = []
        for workplace_coverage in coverage.missing_by_workplace:
            workplace_id = workplace_coverage.workplace_id
            visit_count = len(visits_by_workplace.get(workplace_id, []))
            processes = processes_by_workplace.get(workplace_id, [])
            process_count = len(processes)
            completed_count = sum(
                1
                for item in processes
                if item.status == AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED
            )
            percent = (
                f"{round(completed_count / process_count * 100):.0f}"
                if process_count
                else "0"
            )
            workplace_name = workplace_coverage.workplace_name or "—"
            rows.append(
                (
                    workplace_name,
                    visit_count,
                    process_count,
                    completed_count,
                    percent,
                )
            )
        return rows

    def _show_empty_state(self) -> None:
        self._hint_label.setVisible(True)
        self._detail_form.setVisible(False)
        self._set_action_buttons_enabled(False)
        self._overview_table.setRowCount(0)
        self._clear_detail_values()

    def _clear_detail_values(self) -> None:
        for label in (
            self._name_value,
            self._period_value,
            self._status_value,
            self._standards_value,
            self._workplace_count_value,
            self._visit_count_value,
            self._completion_value,
        ):
            label.setText("")

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        self._edit_program_btn.setEnabled(enabled)
        self._generate_visits_btn.setEnabled(enabled)
        self._distribute_processes_btn.setEnabled(enabled)
        self._refresh_overview_btn.setEnabled(enabled)

    def _set_status(self, message: str) -> None:
        self._status_label.setText(message)

    @staticmethod
    def _program_list_label(program: AuditProgram) -> str:
        if program.name.strip():
            return program.name.strip()
        return AuditProgramManagerDialog._format_period(program.date_from, program.date_to)

    @staticmethod
    def _format_period(date_from: date | None, date_to: date | None) -> str:
        if date_from is None or date_to is None:
            return "—"
        return (
            f"{date_from.day}. {date_from.month}. {date_from.year} – "
            f"{date_to.day}. {date_to.month}. {date_to.year}"
        )
