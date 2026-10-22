from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.testy.constants import (
    AGENDA_EXAM_VALIDITY,
    AGENDA_EXAMS,
    AGENDA_ORAL_QUESTIONS,
    AGENDA_ORAL_TOPICS,
    AGENDA_QUESTIONS,
    AGENDA_TESTS,
    AGENDA_WRITTEN_TOPICS,
    MODULE_NAME,
    PAGE_SUBTITLE,
)
from moduly.testy.ui.exam_validity_tab import ExamValidityTab
from moduly.testy.ui.oral_question_topics_tab import OralQuestionTopicsTab
from moduly.testy.ui.test_exams_tab import TestExamsTab
from moduly.testy.ui.test_definitions_tab import TestDefinitionsTab
from moduly.testy.ui.oral_questions_tab import OralQuestionsTab
from moduly.testy.ui.written_question_topics_tab import WrittenQuestionTopicsTab
from moduly.testy.ui.written_questions_tab import WrittenQuestionsTab


class TestyPage(QWidget):
    """Modul Testy: příprava testů a evidence výsledků.

    Zaměstnanci se zakládají v Nastavení. Historická evidence
    ``test_employees`` se odtud neupravuje.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel(MODULE_NAME)
        title.setObjectName("PageTitle")
        subtitle = QLabel(PAGE_SUBTITLE)
        subtitle.setObjectName("InfoText")
        subtitle.setWordWrap(True)

        self.tabs = QTabWidget()
        self.topics_tab = WrittenQuestionTopicsTab()
        self.questions_tab = WrittenQuestionsTab()
        self.oral_topics_tab = OralQuestionTopicsTab()
        self.oral_questions_tab = OralQuestionsTab()
        self.tests_tab = TestDefinitionsTab()
        self.exams_tab = TestExamsTab()
        self.validity_tab = ExamValidityTab()
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

    def show_validity_tab(self) -> None:
        index = self.tabs.indexOf(self.validity_tab)
        if index >= 0:
            self.tabs.setCurrentIndex(index)

    def refresh(self) -> None:
        self.validity_tab.refresh()

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.validity_tab:
            self.validity_tab.refresh()
