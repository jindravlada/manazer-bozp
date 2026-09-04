"""Dialog pro správu programů auditů."""

import traceback
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.export import open_local_file
from core.widgets.dialog_utils import configure_close_push_button, exec_maximized
from moduly.audity.constants import (
    AUDIT_PROGRAM_ADD_BUTTON,
    AUDIT_PROGRAM_BUTTON_LABEL,
    AUDIT_PROGRAM_ADD_VISIT_BUTTON,
    AUDIT_PROGRAM_CENTER_PANEL_TITLE,
    AUDIT_PROGRAM_DETAIL_ACTIONS_LABEL,
    AUDIT_PROGRAM_DETAIL_STANDARDS_LABEL,
    AUDIT_PROGRAM_EXPORT_PLAN_BUTTON,
    AUDIT_PROGRAM_EXPORT_PLAN_DIALOG_TITLE,
    AUDIT_PROGRAM_EXPORT_PLAN_OPEN_FAILED,
    AUDIT_PROGRAM_FINAL_REPORT_BUTTON,
    AUDIT_PROGRAM_PREVIOUS_PROGRAM_LABEL,
    audit_program_distribute_processes_button_label,
    AUDIT_PROGRAM_EDIT_VISIT_BUTTON,
    AUDIT_PROGRAM_GENERATE_VISITS_BUTTON,
    AUDIT_PROGRAM_LEFT_PANEL_TITLE,
    AUDIT_PROGRAM_MOVE_PROCESS_BUTTON,
    AUDIT_PROGRAM_OPEN_AUDIT_BUTTON,
    AUDIT_PROGRAM_PLAN_TAB_TREE,
    AUDIT_PROGRAM_PLAN_TAB_VISITS,
    AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON,
    AUDIT_PROGRAM_RIGHT_PANEL_TITLE,
    AUDIT_PROGRAM_SKIP_VISIT_BUTTON,
    AUDIT_PROGRAM_START_AUDIT_BUTTON,
    AUDIT_PROGRAM_STATUS_AUDIT_COMPLETED,
    AUDIT_PROGRAM_STATUS_AUDIT_CREATED,
    AUDIT_PROGRAM_STATUS_BADGE_ICONS,
    AUDIT_PROGRAM_STATUS_LABELS,
    AUDIT_PROGRAM_STATUS_OVERVIEW_REFRESHED,
    AUDIT_PROGRAM_STATUS_PROCESSES_DISTRIBUTED,
    AUDIT_PROGRAM_STATUS_PROCESS_MOVED,
    AUDIT_PROGRAM_STATUS_PROGRAM_CREATED,
    AUDIT_PROGRAM_STATUS_PROGRAM_UPDATED,
    AUDIT_PROGRAM_STATUS_VISITS_GENERATED,
    AUDIT_PROGRAM_STATUS_VISIT_CREATED,
    AUDIT_PROGRAM_STATUS_VISIT_SKIPPED,
    AUDIT_PROGRAM_STATUS_VISIT_UPDATED,
    AUDIT_PROGRAM_STATUS_WORKPLACES_SUPPLEMENTED,
    AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_BUTTON,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
    AUDIT_PROGRAM_WINDOW_TITLE,
    AUDIT_DETAILED_REPORT_BUTTON_LABEL,
    AUDIT_DETAILED_REPORT_DIALOG_TITLE,
    AUDIT_PROTOCOL_BUTTON_LABEL,
    AUDIT_PROTOCOL_DIALOG_TITLE,
    AUDIT_STATUS_DOKONCENO,
    PROCESS_PANEL_LEFT_WIDTH,
)
from moduly.audity.modely.audit_program import AuditProgram
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.audit_program_plan_export_service import (
    audit_program_plan_export_service,
)
from moduly.audity.sluzby.audit_program_service import (
    AuditProgramCoverage,
    AuditProgramOverview,
    audit_program_service,
)
from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
from moduly.audity.ui.audit_dialog import AuditDialog
from moduly.audity.ui.audit_program_create_dialog import AuditProgramCreateDialog
from moduly.audity.ui.audit_program_dashboard_widget import AuditProgramDashboardWidget
from moduly.audity.ui.audit_program_move_process_dialog import (
    AuditProgramMoveProcessDialog,
    load_target_visits,
)
from moduly.audity.ui.audit_program_planned_visits_widget import (
    AuditProgramPlannedVisitsWidget,
)
from moduly.audity.ui.audit_program_supplement_workplaces_dialog import (
    AuditProgramSupplementWorkplacesDialog,
)
from moduly.audity.ui.audit_program_plan_tree_widget import (
    NODE_PROCESS,
    NODE_VISIT,
    NODE_WORKPLACE,
    AuditProgramPlanTreeWidget,
)
from moduly.audity.ui.audit_program_visit_dialog import AuditProgramVisitDialog
from moduly.audity.ui.zaverecna_zprava_programu_auditu_dialog import (
    ZaverecnaZpravaProgramuAudituDialog,
)


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

        main_splitter = QSplitter(Qt.Orientation.Vertical)

        plan_splitter = QSplitter()

        self._program_list = QListWidget()
        self._program_list.currentItemChanged.connect(self._on_program_selected)

        left_panel = self._build_left_panel()
        center_panel = self._build_center_panel()
        right_panel = self._build_right_panel()

        plan_splitter.addWidget(left_panel)
        plan_splitter.addWidget(center_panel)
        plan_splitter.addWidget(right_panel)
        plan_splitter.setStretchFactor(0, 0)
        plan_splitter.setStretchFactor(1, 0)
        plan_splitter.setStretchFactor(2, 2)
        plan_splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 300, 640])

        self._dashboard_widget = AuditProgramDashboardWidget()

        main_splitter.addWidget(plan_splitter)
        main_splitter.addWidget(self._dashboard_widget)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setSizes([380, 520])

        root.addWidget(main_splitter, 1)
        root.addLayout(self._build_footer())

        self._reload_program_list()

    def _build_left_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(AUDIT_PROGRAM_LEFT_PANEL_TITLE)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        toolbar = QVBoxLayout()
        toolbar.setSpacing(6)
        self._new_program_btn = QPushButton(AUDIT_PROGRAM_ADD_BUTTON)
        self._edit_program_btn = QPushButton("Upravit")
        self._refresh_programs_btn = QPushButton("Obnovit")
        self._new_program_btn.clicked.connect(self._create_program)
        self._edit_program_btn.clicked.connect(self._edit_program)
        self._refresh_programs_btn.clicked.connect(self._reload_program_list)
        toolbar.addWidget(self._new_program_btn)
        toolbar.addWidget(self._edit_program_btn)
        toolbar.addWidget(self._refresh_programs_btn)
        layout.addLayout(toolbar)
        layout.addWidget(self._program_list, 1)

        panel.setMinimumWidth(PROCESS_PANEL_LEFT_WIDTH)
        panel.setMaximumWidth(PROCESS_PANEL_LEFT_WIDTH)
        return panel

    def _build_center_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel(AUDIT_PROGRAM_CENTER_PANEL_TITLE)
        title.setObjectName("SectionTitle")
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignTop)

        self._hint_label = QLabel("Vyberte program auditů vlevo nebo vytvořte nový.")
        self._hint_label.setObjectName("InfoText")
        self._hint_label.setWordWrap(True)
        layout.addWidget(self._hint_label, 0, Qt.AlignmentFlag.AlignTop)

        self._detail_card = QFrame()
        self._detail_card.setObjectName("ProgramDetailCard")
        card_layout = QVBoxLayout(self._detail_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._program_title_label = QLabel()
        self._program_title_label.setObjectName("ProgramDetailTitle")
        self._program_title_label.setWordWrap(True)
        card_layout.addWidget(self._program_title_label)

        self._program_status_badge = QLabel()
        self._program_status_badge.setObjectName("ProgramStatusBadge")
        card_layout.addWidget(self._program_status_badge, 0, Qt.AlignmentFlag.AlignLeft)

        self._program_period_label = QLabel()
        self._program_period_label.setObjectName("MutedText")
        card_layout.addWidget(self._program_period_label)

        self._previous_program_label = QLabel()
        self._previous_program_label.setObjectName("InfoText")
        self._previous_program_label.setWordWrap(True)
        card_layout.addWidget(self._previous_program_label)

        card_layout.addWidget(self._card_separator())

        standards_label = QLabel(AUDIT_PROGRAM_DETAIL_STANDARDS_LABEL)
        standards_label.setObjectName("MutedText")
        card_layout.addWidget(standards_label)

        self._standards_value = QLabel()
        self._standards_value.setObjectName("InfoText")
        self._standards_value.setWordWrap(True)
        card_layout.addWidget(self._standards_value)

        card_layout.addWidget(self._card_separator())

        self._workplaces_stat_label = QLabel()
        self._workplaces_stat_label.setObjectName("InfoText")
        card_layout.addWidget(self._workplaces_stat_label)

        self._visits_stat_label = QLabel()
        self._visits_stat_label.setObjectName("InfoText")
        card_layout.addWidget(self._visits_stat_label)

        self._completion_stat_label = QLabel()
        self._completion_stat_label.setObjectName("InfoText")
        card_layout.addWidget(self._completion_stat_label)

        card_layout.addWidget(self._card_separator())

        actions_title = QLabel(AUDIT_PROGRAM_DETAIL_ACTIONS_LABEL)
        actions_title.setObjectName("MutedText")
        card_layout.addWidget(actions_title)

        actions = QVBoxLayout()
        actions.setSpacing(6)
        actions.setContentsMargins(0, 0, 0, 0)
        self._generate_visits_btn = QPushButton(AUDIT_PROGRAM_GENERATE_VISITS_BUTTON)
        self._supplement_workplaces_btn = QPushButton(AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_BUTTON)
        self._distribute_processes_btn = QPushButton(
            audit_program_distribute_processes_button_label(False)
        )
        self._refresh_overview_btn = QPushButton(AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON)
        self._export_plan_btn = QPushButton(AUDIT_PROGRAM_EXPORT_PLAN_BUTTON)
        self._final_report_btn = QPushButton(AUDIT_PROGRAM_FINAL_REPORT_BUTTON)
        self._generate_visits_btn.clicked.connect(self._generate_visits)
        self._supplement_workplaces_btn.clicked.connect(self._supplement_workplaces)
        self._distribute_processes_btn.clicked.connect(self._distribute_processes)
        self._refresh_overview_btn.clicked.connect(self._refresh_overview)
        self._export_plan_btn.clicked.connect(self._export_plan)
        self._final_report_btn.clicked.connect(self._open_final_report_dialog)
        actions.addWidget(self._generate_visits_btn)
        actions.addWidget(self._supplement_workplaces_btn)
        actions.addWidget(self._distribute_processes_btn)
        actions.addWidget(self._refresh_overview_btn)
        actions.addWidget(self._export_plan_btn)
        actions.addWidget(self._final_report_btn)
        card_layout.addLayout(actions)

        self._detail_card.setVisible(False)
        layout.addWidget(self._detail_card, 0, Qt.AlignmentFlag.AlignTop)

        self._set_action_buttons_enabled(False)
        panel.setMinimumWidth(280)
        panel.setMaximumWidth(360)
        return panel

    @staticmethod
    def _card_separator() -> QFrame:
        line = QFrame()
        line.setObjectName("ProgramDetailCardSeparator")
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        return line

    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel(AUDIT_PROGRAM_RIGHT_PANEL_TITLE)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        tree_toolbar = QHBoxLayout()
        self._add_visit_btn = QPushButton(AUDIT_PROGRAM_ADD_VISIT_BUTTON)
        self._edit_visit_btn = QPushButton(AUDIT_PROGRAM_EDIT_VISIT_BUTTON)
        self._skip_visit_btn = QPushButton(AUDIT_PROGRAM_SKIP_VISIT_BUTTON)
        self._move_process_btn = QPushButton(AUDIT_PROGRAM_MOVE_PROCESS_BUTTON)
        self._start_audit_btn = QPushButton(AUDIT_PROGRAM_START_AUDIT_BUTTON)
        self._open_audit_btn = QPushButton(AUDIT_PROGRAM_OPEN_AUDIT_BUTTON)
        self._protocol_btn = QPushButton(AUDIT_PROTOCOL_BUTTON_LABEL)
        self._protocol_btn.setEnabled(False)
        self._protocol_btn.setToolTip(
            "Export protokolu je dostupný pouze pro dokončené (uzavřené) audity."
        )
        self._detailed_report_btn = QPushButton(AUDIT_DETAILED_REPORT_BUTTON_LABEL)
        self._detailed_report_btn.setEnabled(False)
        self._detailed_report_btn.setToolTip(
            "Podrobná zpráva je dostupná pouze pro dokončené (uzavřené) audity."
        )
        self._add_visit_btn.clicked.connect(self._create_visit_for_selection)
        self._edit_visit_btn.clicked.connect(self._edit_selected_visit)
        self._skip_visit_btn.clicked.connect(self._skip_selected_visit)
        self._move_process_btn.clicked.connect(self._move_selected_process)
        self._start_audit_btn.clicked.connect(self._start_audit_for_selection)
        self._open_audit_btn.clicked.connect(self._open_audit_for_selection)
        self._protocol_btn.clicked.connect(self._export_protocol_for_selection)
        self._detailed_report_btn.clicked.connect(
            self._export_detailed_report_for_selection
        )
        tree_toolbar.addWidget(self._add_visit_btn)
        tree_toolbar.addWidget(self._edit_visit_btn)
        tree_toolbar.addWidget(self._skip_visit_btn)
        tree_toolbar.addWidget(self._move_process_btn)
        tree_toolbar.addWidget(self._start_audit_btn)
        tree_toolbar.addWidget(self._open_audit_btn)
        tree_toolbar.addWidget(self._protocol_btn)
        tree_toolbar.addWidget(self._detailed_report_btn)
        tree_toolbar.addStretch()
        layout.addLayout(tree_toolbar)

        self._plan_tree = AuditProgramPlanTreeWidget()
        self._plan_tree.customContextMenuRequested.connect(self._show_plan_context_menu)
        self._plan_tree.itemSelectionChanged.connect(self._update_plan_actions)
        self._plan_tree.itemDoubleClicked.connect(self._on_plan_tree_double_clicked)

        self._planned_visits_widget = AuditProgramPlannedVisitsWidget()

        self._plan_tabs = QTabWidget()
        self._plan_tabs.addTab(self._plan_tree, AUDIT_PROGRAM_PLAN_TAB_TREE)
        self._plan_tabs.addTab(
            self._planned_visits_widget,
            AUDIT_PROGRAM_PLAN_TAB_VISITS,
        )
        layout.addWidget(self._plan_tabs, 1)

        self._set_plan_actions_enabled(False)
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

    def _supplement_workplaces(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            return

        try:
            missing = audit_program_service.list_missing_auditable_workplaces(program_id)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        if not missing:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "Všechna auditovaná pracoviště z nastavení jsou již v programu.",
            )
            return

        dialog = AuditProgramSupplementWorkplacesDialog(self, workplaces=missing)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dialog.selected_workplace_ids()
        if not selected:
            return

        try:
            audit_program_service.supplement_workplaces(program_id, selected)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_WORKPLACES_SUPPLEMENTED)
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

    def _open_final_report_dialog(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            return
        exec_maximized(ZaverecnaZpravaProgramuAudituDialog(self, program_id=program_id))

    def _export_plan(self) -> None:
        program_id = self._selected_program_id
        if program_id is None:
            return
        overview = audit_program_service.get_program_overview(program_id)
        if overview is None or not overview.visits:
            return

        try:
            path = audit_program_plan_export_service.generate_preview_for_program(
                program_id
            )
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_PROGRAM_EXPORT_PLAN_DIALOG_TITLE,
                f"Plán se nepodařilo exportovat.\n\n{exc}",
            )
            return

        try:
            opened = open_local_file(
                path,
                parent=self,
                title=AUDIT_PROGRAM_EXPORT_PLAN_DIALOG_TITLE,
                show_error=False,
            )
        except Exception:
            traceback.print_exc()
            opened = False
        if not opened:
            QMessageBox.warning(
                self,
                AUDIT_PROGRAM_EXPORT_PLAN_DIALOG_TITLE,
                f"{AUDIT_PROGRAM_EXPORT_PLAN_OPEN_FAILED}\n\n{path}",
            )

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
        self._detail_card.setVisible(True)
        self._set_action_buttons_enabled(True, has_visits=bool(overview.visits))
        self._fill_detail_panel(overview, coverage)
        self._plan_tree.populate(overview)
        self._planned_visits_widget.load_program(program_id)
        self._update_plan_actions()
        self._dashboard_widget.load_program(program_id)

    def _update_plan_actions(self) -> None:
        if self._selected_program_id is None:
            self._set_plan_actions_enabled(False)
            return

        item = self._plan_tree.currentItem()
        node_type = AuditProgramPlanTreeWidget.node_type(item)
        self._add_visit_btn.setEnabled(node_type == NODE_WORKPLACE)
        self._edit_visit_btn.setEnabled(node_type == NODE_VISIT)
        self._skip_visit_btn.setEnabled(
            node_type == NODE_VISIT and self._visit_can_be_edited(item)
        )
        self._move_process_btn.setEnabled(node_type == NODE_PROCESS)
        self._start_audit_btn.setEnabled(
            node_type == NODE_VISIT and self._visit_can_start_audit(item)
        )
        self._open_audit_btn.setEnabled(
            node_type == NODE_VISIT and self._visit_has_audit(item)
        )
        self._protocol_btn.setEnabled(
            node_type == NODE_VISIT and self._visit_has_completed_audit(item)
        )
        self._detailed_report_btn.setEnabled(
            node_type == NODE_VISIT and self._visit_has_completed_audit(item)
        )

    def _visit_can_be_edited(self, item) -> bool:
        visit = self._visit_for_tree_item(item)
        if visit is None:
            return False
        return visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED

    def _visit_can_start_audit(self, item) -> bool:
        visit = self._visit_for_tree_item(item)
        if visit is None:
            return False
        return (
            visit.status != AUDIT_PROGRAM_VISIT_STATUS_SKIPPED
            and visit.audit_id is None
        )

    def _visit_has_audit(self, item) -> bool:
        visit = self._visit_for_tree_item(item)
        return visit is not None and visit.audit_id is not None

    def _visit_has_completed_audit(self, item) -> bool:
        visit = self._visit_for_tree_item(item)
        if visit is None or visit.audit_id is None:
            return False
        audit = audit_service.get_by_id(visit.audit_id)
        return audit is not None and audit.status == AUDIT_STATUS_DOKONCENO

    def _visit_for_tree_item(self, item):
        visit_id = AuditProgramPlanTreeWidget.node_id(item)
        if visit_id is None or AuditProgramPlanTreeWidget.node_type(item) != NODE_VISIT:
            return None
        return audit_program_service.repository.get_visit(visit_id)

    def _set_plan_actions_enabled(self, enabled: bool) -> None:
        self._add_visit_btn.setEnabled(enabled)
        self._edit_visit_btn.setEnabled(enabled)
        self._skip_visit_btn.setEnabled(enabled)
        self._move_process_btn.setEnabled(enabled)
        self._start_audit_btn.setEnabled(enabled)
        self._open_audit_btn.setEnabled(enabled)
        self._protocol_btn.setEnabled(enabled)
        self._detailed_report_btn.setEnabled(enabled)

    def _show_plan_context_menu(self, position) -> None:
        item = self._plan_tree.itemAt(position)
        if item is None:
            return

        self._plan_tree.setCurrentItem(item)
        node_type = AuditProgramPlanTreeWidget.node_type(item)
        menu = QMenu(self)

        if node_type == NODE_WORKPLACE:
            menu.addAction(AUDIT_PROGRAM_ADD_VISIT_BUTTON, self._create_visit_for_selection)
        elif node_type == NODE_VISIT:
            menu.addAction(AUDIT_PROGRAM_EDIT_VISIT_BUTTON, self._edit_selected_visit)
            if self._visit_can_start_audit(item):
                menu.addAction(AUDIT_PROGRAM_START_AUDIT_BUTTON, self._start_audit_for_selection)
            if self._visit_has_audit(item):
                menu.addAction(AUDIT_PROGRAM_OPEN_AUDIT_BUTTON, self._open_audit_for_selection)
            if self._visit_has_completed_audit(item):
                menu.addAction(
                    AUDIT_PROTOCOL_BUTTON_LABEL,
                    self._export_protocol_for_selection,
                )
                menu.addAction(
                    AUDIT_DETAILED_REPORT_BUTTON_LABEL,
                    self._export_detailed_report_for_selection,
                )
            if self._visit_can_be_edited(item):
                menu.addAction(AUDIT_PROGRAM_SKIP_VISIT_BUTTON, self._skip_selected_visit)
        elif node_type == NODE_PROCESS:
            menu.addAction(AUDIT_PROGRAM_MOVE_PROCESS_BUTTON, self._move_selected_process)

        if not menu.isEmpty():
            menu.exec(self._plan_tree.viewport().mapToGlobal(position))

    def _selected_tree_item(self):
        return self._plan_tree.currentItem()

    def _create_visit_for_selection(self) -> None:
        program_id = self._selected_program_id
        item = self._selected_tree_item()
        if program_id is None or item is None:
            return

        workplace_id = AuditProgramPlanTreeWidget.workplace_id(item)
        if AuditProgramPlanTreeWidget.node_type(item) != NODE_WORKPLACE:
            return

        dialog = AuditProgramVisitDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            audit_program_service.create_manual_visit(
                program_id,
                workplace_id=workplace_id,
                **dialog.visit_payload(),
            )
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_VISIT_CREATED)
        self._refresh_selected_program_views()

    def _edit_selected_visit(self) -> None:
        item = self._selected_tree_item()
        visit_id = AuditProgramPlanTreeWidget.node_id(item)
        if visit_id is None or AuditProgramPlanTreeWidget.node_type(item) != NODE_VISIT:
            return

        visit = audit_program_service.repository.get_visit(visit_id)
        if visit is None:
            self._refresh_selected_program_views()
            return

        dialog = AuditProgramVisitDialog(self, visit=visit)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            audit_program_service.update_visit_plan(visit_id, **dialog.visit_payload())
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_VISIT_UPDATED)
        self._refresh_selected_program_views()

    def _skip_selected_visit(self) -> None:
        item = self._selected_tree_item()
        visit_id = AuditProgramPlanTreeWidget.node_id(item)
        if visit_id is None or AuditProgramPlanTreeWidget.node_type(item) != NODE_VISIT:
            return

        try:
            audit_program_service.skip_visit(visit_id)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_VISIT_SKIPPED)
        self._refresh_selected_program_views()

    def _move_selected_process(self) -> None:
        program_id = self._selected_program_id
        item = self._selected_tree_item()
        process_id = AuditProgramPlanTreeWidget.node_id(item)
        if (
            program_id is None
            or process_id is None
            or AuditProgramPlanTreeWidget.node_type(item) != NODE_PROCESS
        ):
            return

        visit_process = audit_program_service.repository.get_visit_process(process_id)
        if visit_process is None:
            self._refresh_selected_program_views()
            return

        source_visit = audit_program_service.repository.get_visit(visit_process.visit_id)
        if source_visit is None:
            return

        target_visits = load_target_visits(
            program_id,
            workplace_id=source_visit.workplace_id,
            current_visit_id=source_visit.id,
        )
        if not target_visits:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "Pro tento proces není k dispozici jiná aktivní návštěva.",
            )
            return

        dialog = AuditProgramMoveProcessDialog(
            self,
            visit_process=visit_process,
            visits=target_visits,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        target_visit_id = dialog.target_visit_id()
        if target_visit_id is None:
            return

        try:
            audit_program_service.move_visit_process(process_id, target_visit_id)
        except ValueError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return

        self._set_status(AUDIT_PROGRAM_STATUS_PROCESS_MOVED)
        self._refresh_selected_program_views()

    def _on_plan_tree_double_clicked(self, item, _column: int) -> None:
        if AuditProgramPlanTreeWidget.node_type(item) != NODE_VISIT:
            return
        if self._visit_has_audit(item):
            self._open_audit_for_selection()
        elif self._visit_can_start_audit(item):
            self._start_audit_for_selection()

    def _start_audit_for_selection(self) -> None:
        item = self._selected_tree_item()
        visit_id = AuditProgramPlanTreeWidget.node_id(item)
        if visit_id is None or AuditProgramPlanTreeWidget.node_type(item) != NODE_VISIT:
            return

        visit = self._visit_for_tree_item(item)
        if visit is None:
            return
        if visit.audit_id is not None:
            self._open_audit_for_selection()
            return

        visit_context = audit_program_service.get_visit_audit_context(visit_id)
        if visit_context is None:
            QMessageBox.warning(self, self.windowTitle(), "Návštěva nebyla nalezena.")
            return

        self._open_audit_dialog(audit_id=None, visit_context=visit_context)

    def _open_audit_for_selection(self) -> None:
        item = self._selected_tree_item()
        visit = self._visit_for_tree_item(item)
        if visit is None or visit.audit_id is None:
            return

        visit_context = audit_program_service.get_visit_audit_context(visit.id)
        self._open_audit_dialog(visit.audit_id, visit_context=visit_context)

    def _export_protocol_for_selection(self) -> None:
        item = self._selected_tree_item()
        visit = self._visit_for_tree_item(item)
        if visit is None or visit.audit_id is None:
            QMessageBox.information(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                "Vyberte návštěvu s dokončeným auditem.",
            )
            return

        audit = audit_service.get_by_id(visit.audit_id)
        if audit is None:
            QMessageBox.warning(self, AUDIT_PROTOCOL_DIALOG_TITLE, "Audit nebyl nalezen.")
            self._refresh_selected_program_views()
            return
        if audit.status != AUDIT_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                "Protokol lze exportovat pouze u dokončeného (uzavřeného) auditu.",
            )
            self._update_plan_actions()
            return

        try:
            protokol_audit_service.open_for_audit(audit)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_PROTOCOL_DIALOG_TITLE,
                f"Protokol se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _export_detailed_report_for_selection(self) -> None:
        item = self._selected_tree_item()
        visit = self._visit_for_tree_item(item)
        if visit is None or visit.audit_id is None:
            QMessageBox.information(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                "Vyberte návštěvu s dokončeným auditem.",
            )
            return

        audit = audit_service.get_by_id(visit.audit_id)
        if audit is None:
            QMessageBox.warning(
                self, AUDIT_DETAILED_REPORT_DIALOG_TITLE, "Audit nebyl nalezen."
            )
            self._refresh_selected_program_views()
            return
        if audit.status != AUDIT_STATUS_DOKONCENO:
            QMessageBox.information(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                "Podrobnou zprávu lze exportovat pouze u dokončeného (uzavřeného) auditu.",
            )
            self._update_plan_actions()
            return

        try:
            protokol_audit_service.open_detailed_report_for_audit(audit)
        except Exception as exc:
            traceback.print_exc()
            QMessageBox.warning(
                self,
                AUDIT_DETAILED_REPORT_DIALOG_TITLE,
                f"Podrobnou zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _open_audit_dialog(self, audit_id: int | None = None, *, visit_context=None) -> bool:
        audit = None
        if audit_id is not None:
            audit = audit_service.get_by_id(audit_id)
            if audit is None:
                QMessageBox.warning(self, self.windowTitle(), "Audit nebyl nalezen.")
                self._refresh_selected_program_views()
                return False

        dialog = AuditDialog(self, audit=audit, visit_context=visit_context)
        exec_maximized(dialog)

        resolved_id = audit_id
        if resolved_id is None and visit_context is not None:
            visit = audit_program_service.repository.get_visit(visit_context.visit_id)
            if visit is not None:
                resolved_id = visit.audit_id

        updated = audit_service.get_by_id(resolved_id) if resolved_id is not None else None
        completed = (
            updated is not None and updated.status == AUDIT_STATUS_DOKONCENO
        )

        self._refresh_selected_program_views()
        if completed:
            self._set_status(AUDIT_PROGRAM_STATUS_AUDIT_COMPLETED)
        elif updated is not None:
            self._set_status(AUDIT_PROGRAM_STATUS_AUDIT_CREATED)
        return completed

    def _fill_detail_panel(
        self,
        overview: AuditProgramOverview,
        coverage: AuditProgramCoverage,
    ) -> None:
        program = overview.program
        self._program_title_label.setText(program.name or "—")
        self._program_period_label.setText(
            self._format_period(program.date_from, program.date_to)
        )
        if program.previous_program_id is None:
            self._previous_program_label.setText(
                f"{AUDIT_PROGRAM_PREVIOUS_PROGRAM_LABEL} —"
            )
        else:
            previous = audit_program_service.get_program(program.previous_program_id)
            previous_name = previous.name if previous is not None else "—"
            self._previous_program_label.setText(
                f"{AUDIT_PROGRAM_PREVIOUS_PROGRAM_LABEL} {previous_name}"
            )
        self._set_program_status_badge(program.status)
        standards = audit_program_service.parse_standards(program.standards_json)
        self._standards_value.setText("\n".join(standards) if standards else "—")
        self._workplaces_stat_label.setText(f"Pracoviště: {coverage.workplace_count}")
        self._visits_stat_label.setText(
            f"Návštěvy: {coverage.completed_visit_count} / {coverage.visit_count}"
        )
        self._completion_stat_label.setText(
            f"Plnění: {coverage.completion_percent:.0f} %"
        )
        self._apply_distribute_processes_button_label(overview)

    def _apply_distribute_processes_button_label(
        self,
        overview: AuditProgramOverview,
    ) -> None:
        has_processes = bool(overview.visit_processes)
        self._distribute_processes_btn.setText(
            audit_program_distribute_processes_button_label(has_processes)
        )

    def _set_program_status_badge(self, status: str) -> None:
        icon = AUDIT_PROGRAM_STATUS_BADGE_ICONS.get(status, "")
        label_text = AUDIT_PROGRAM_STATUS_LABELS.get(status, status)
        self._program_status_badge.setText(
            f"{icon} {label_text}".strip() if icon else label_text
        )
        self._program_status_badge.setProperty("programStatus", status)
        self._program_status_badge.style().unpolish(self._program_status_badge)
        self._program_status_badge.style().polish(self._program_status_badge)

    def _show_empty_state(self) -> None:
        self._hint_label.setVisible(True)
        self._detail_card.setVisible(False)
        self._set_action_buttons_enabled(False)
        self._plan_tree.clear()
        self._planned_visits_widget.load_program(None)
        self._set_plan_actions_enabled(False)
        self._dashboard_widget.load_program(None)
        self._clear_detail_values()

    def _clear_detail_values(self) -> None:
        for label in (
            self._program_title_label,
            self._program_period_label,
            self._previous_program_label,
            self._program_status_badge,
            self._standards_value,
            self._workplaces_stat_label,
            self._visits_stat_label,
            self._completion_stat_label,
        ):
            label.setText("")
        self._program_status_badge.setProperty("programStatus", "")

    def _set_action_buttons_enabled(self, enabled: bool, *, has_visits: bool = False) -> None:
        self._edit_program_btn.setEnabled(enabled)
        self._generate_visits_btn.setEnabled(enabled)
        self._supplement_workplaces_btn.setEnabled(enabled)
        self._distribute_processes_btn.setEnabled(enabled)
        self._refresh_overview_btn.setEnabled(enabled)
        self._export_plan_btn.setEnabled(enabled and has_visits)
        self._final_report_btn.setEnabled(enabled)

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
