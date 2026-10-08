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
    AGENDA_EXAM_VALIDITY,
    AGENDA_EXAMS,
    AGENDA_ORAL_QUESTIONS,
    AGENDA_ORAL_TOPICS,
    AGENDA_QUESTIONS,
    AGENDA_TESTS,
    AGENDA_WRITTEN_TOPICS,
    COL_ID,
    MODULE_NAME,
    PAGE_SUBTITLE,
    SEARCH_PLACEHOLDER,
    SHOW_INACTIVE_LABEL,
)
from moduly.testy.sluzby.test_employee_service import test_employee_service
from moduly.testy.ui.exam_validity_tab import ExamValidityTab
from moduly.testy.ui.oral_question_topics_tab import OralQuestionTopicsTab
from moduly.testy.ui.test_exams_tab import TestExamsTab
from moduly.testy.ui.test_definitions_tab import TestDefinitionsTab
from moduly.testy.ui.oral_questions_tab import OralQuestionsTab
from moduly.testy.ui.test_employee_dialog import TestEmployeeDialog
from moduly.testy.ui.test_employee_table import TestEmployeeTable
from moduly.testy.ui.written_question_topics_tab import WrittenQuestionTopicsTab
from moduly.testy.ui.written_questions_tab import WrittenQuestionsTab


class TestyPage(QWidget):
    """Modul Testy: zaměstnanci, otázky a definice testů."""

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
        self.questions_tab = WrittenQuestionsTab()
        self.oral_topics_tab = OralQuestionTopicsTab()
        self.oral_questions_tab = OralQuestionsTab()
        self.tests_tab = TestDefinitionsTab()
        self.exams_tab = TestExamsTab()
        self.validity_tab = ExamValidityTab()
        self.tabs.addTab(self.employees_tab, AGENDA_EMPLOYEES)
        self.tabs.addTab(self.topics_tab, AGENDA_WRITTEN_TOPICS)
        self.tabs.addTab(self.questions_tab, AGENDA_QUESTIONS)
        self.tabs.addTab(self.oral_topics_tab, AGENDA_ORAL_TOPICS)
        self.tabs.addTab(self.oral_questions_tab, AGENDA_ORAL_QUESTIONS)
        self.tabs.addTab(self.tests_tab, AGENDA_TESTS)
        self.tabs.addTab(self.exams_tab, AGENDA_EXAMS)
        self.tabs.addTab(self.validity_tab, AGENDA_EXAM_VALIDITY)
        self.exams_tab.exams_changed.connect(self.validity_tab.refresh)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.tabs, 1)

        self.refresh()

    def show_exams_tab(self, exam_id: int | None = None) -> None:
        index = self.tabs.indexOf(self.exams_tab)
        if index >= 0:
            self.tabs.setCurrentIndex(index)
        self.exams_tab.focus_exam(exam_id)

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
        self.validity_tab.refresh()

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.validity_tab:
            self.validity_tab.refresh()

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
