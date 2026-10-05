from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_edit_action_button,
    configure_new_action_button,
)
from core.widgets.filter_bar import FilterBar
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import refresh_and_restore_selection
from core.widgets.table_utils import configure_table_columns
from moduly.testy.constants import (
    ACTION_EDIT,
    ACTION_NEW,
    AGENDA_EMPLOYEES,
    AGENDA_WRITTEN_TOPICS,
    COL_ID,
    MODULE_NAME,
    PAGE_SUBTITLE,
    SEARCH_PLACEHOLDER,
    SHOW_INACTIVE_LABEL,
)
from moduly.testy.sluzby.test_employee_service import test_employee_service
from moduly.testy.ui.test_employee_dialog import TestEmployeeDialog
from moduly.testy.ui.test_employee_table import TestEmployeeTable
from moduly.testy.ui.written_question_topics_tab import WrittenQuestionTopicsTab


class TestyPage(QWidget):
    """Modul Testy: agendy zaměstnanců a okruhů písemných otázek."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel(MODULE_NAME)
        title.setObjectName("PageTitle")
        subtitle = QLabel(PAGE_SUBTITLE)
        subtitle.setObjectName("InfoText")
        subtitle.setWordWrap(True)

        self.tabs = QTabWidget()
        self.employees_tab = self._build_employees_tab()
        self.topics_tab = WrittenQuestionTopicsTab()
        self.tabs.addTab(self.employees_tab, AGENDA_EMPLOYEES)
        self.tabs.addTab(self.topics_tab, AGENDA_WRITTEN_TOPICS)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.tabs, 1)

        self.refresh()

    def _build_employees_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(ACTION_NEW)
        configure_new_action_button(self.new_btn)
        self.edit_btn = QPushButton(ACTION_EDIT)
        configure_edit_action_button(self.edit_btn)
        self.edit_btn.setEnabled(False)
        self.show_inactive = QCheckBox(SHOW_INACTIVE_LABEL)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.show_inactive)

        self.table = TestEmployeeTable()
        configure_table_columns(self.table, "test_employees")
        self.text_filter = FilterBar(self.table, placeholder=SEARCH_PLACEHOLDER)

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self.new_btn.clicked.connect(self.new_employee)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.show_inactive.toggled.connect(self.refresh)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        install_table_row_actions(
            self.table,
            on_edit=self.edit_selected,
            can_edit=lambda: self.edit_btn.isEnabled(),
        )
        return tab

    def refresh(self) -> None:
        selected_id = self.table.selected_employee_id()
        employees = test_employee_service.list_employees(
            include_inactive=self.show_inactive.isChecked(),
        )
        self.table.load_employees(employees)
        configure_table_columns(self.table, "test_employees")
        refresh_and_restore_selection(self.table, selected_id, id_column=COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def new_employee(self) -> None:
        dialog = TestEmployeeDialog(self)
        if not dialog.exec():
            return
        self._reload(dialog.saved_employee_id)

    def edit_selected(self) -> None:
        employee_id = self.table.selected_employee_id()
        if employee_id is None:
            return
        employee = test_employee_service.get_employee(employee_id)
        if employee is None:
            QMessageBox.warning(self, MODULE_NAME, "Zaměstnanec nebyl nalezen.")
            self.refresh()
            return
        dialog = TestEmployeeDialog(
            self,
            employee=employee,
            role_ids=test_employee_service.get_role_ids(employee_id),
        )
        if not dialog.exec():
            return
        self._reload(dialog.saved_employee_id)

    def _reload(self, employee_id: int | None) -> None:
        employees = test_employee_service.list_employees(
            include_inactive=self.show_inactive.isChecked(),
        )
        self.table.load_employees(employees)
        configure_table_columns(self.table, "test_employees")
        refresh_and_restore_selection(self.table, employee_id, id_column=COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        self.edit_btn.setEnabled(self.table.selected_employee_id() is not None)
