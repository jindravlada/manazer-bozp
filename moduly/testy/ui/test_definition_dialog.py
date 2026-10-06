"""Editor definice Testu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.no_wheel_guards import NoWheelComboBox, NoWheelSpinBox
from moduly.testy.constants import (
    DEFAULT_SECONDS_PER_QUESTION,
    EXAMINER_MODE_COMMISSION,
    EXAMINER_MODE_COMMISSION_LABEL,
    EXAMINER_MODE_NONE,
    EXAMINER_MODE_NONE_LABEL,
    EXAMINER_MODE_SINGLE,
    EXAMINER_MODE_SINGLE_LABEL,
    MODULE_NAME,
    TEST_DIALOG_TITLE_EDIT,
    TEST_DIALOG_TITLE_NEW,
    VALIDITY_UNIT_MONTHS,
    VALIDITY_UNIT_MONTHS_LABEL,
    VALIDITY_UNIT_YEARS,
    VALIDITY_UNIT_YEARS_LABEL,
)
from moduly.testy.modely.test_definition import TestDefinition
from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
from moduly.testy.sluzby.test_definition_service import (
    TestDefinitionError,
    TestTopicQuota,
    format_test_duration,
    test_definition_service,
    total_written_questions,
    total_written_seconds,
)
from moduly.testy.sluzby.written_question_topic_service import (
    written_question_topic_service,
)
from moduly.testy.ui.test_definition_composition import TestDefinitionCompositionEditor


class TestDefinitionDialog(QDialog):
    def __init__(self, parent=None, test: TestDefinition | None = None):
        super().__init__(parent)
        self.test_id = test.id if test is not None else None
        self.saved_test_id: int | None = self.test_id
        is_new = test is None

        self.setWindowTitle(TEST_DIALOG_TITLE_NEW if is_new else TEST_DIALOG_TITLE_EDIT)
        configure_resizable_form_dialog(
            self,
            width=820,
            height=720,
            min_width=640,
            min_height=480,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QVBoxLayout(form_host)

        basics = QGroupBox("Základní údaje")
        basics_form = QFormLayout(basics)
        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(72)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)
        basics_form.addRow("Název:", self.name)
        basics_form.addRow("Popis:", self.description)
        basics_form.addRow("", self.active_checkbox)

        self.written_group = QGroupBox("Písemná část")
        self.written_group.setCheckable(True)
        self.written_group.setChecked(False)
        written_layout = QVBoxLayout(self.written_group)
        self.written_composition = TestDefinitionCompositionEditor()
        limits = QFormLayout()
        self.allowed_errors = NoWheelSpinBox()
        self.allowed_errors.setRange(0, 999)
        self.seconds = NoWheelSpinBox()
        self.seconds.setRange(1, 3600)
        self.seconds.setValue(DEFAULT_SECONDS_PER_QUESTION)
        limits.addRow("Povolené chyby:", self.allowed_errors)
        limits.addRow("Sekund na otázku:", self.seconds)
        self.total_questions_label = QLabel("Celkem otázek: 0")
        self.duration_label = QLabel("Čas testu: 0 min")
        written_layout.addWidget(self.written_composition)
        written_layout.addLayout(limits)
        written_layout.addWidget(self.total_questions_label)
        written_layout.addWidget(self.duration_label)

        self.oral_group = QGroupBox("Ústní část")
        self.oral_group.setCheckable(True)
        self.oral_group.setChecked(False)
        oral_layout = QVBoxLayout(self.oral_group)
        self.oral_composition = TestDefinitionCompositionEditor()
        oral_layout.addWidget(self.oral_composition)

        organization = QGroupBox("Organizace")
        organization_layout = QVBoxLayout(organization)
        self.mode_none = QRadioButton(EXAMINER_MODE_NONE_LABEL)
        self.mode_single = QRadioButton(EXAMINER_MODE_SINGLE_LABEL)
        self.mode_commission = QRadioButton(EXAMINER_MODE_COMMISSION_LABEL)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_none)
        self.mode_group.addButton(self.mode_single)
        self.mode_group.addButton(self.mode_commission)
        self.mode_none.setChecked(True)
        organization_layout.addWidget(self.mode_none)
        organization_layout.addWidget(self.mode_single)
        organization_layout.addWidget(self.mode_commission)

        validity = QGroupBox("Platnost")
        validity_row = QHBoxLayout(validity)
        self.validity_value = NoWheelSpinBox()
        self.validity_value.setRange(1, 100)
        self.validity_value.setValue(1)
        self.validity_unit = NoWheelComboBox()
        self.validity_unit.addItem(VALIDITY_UNIT_YEARS_LABEL, VALIDITY_UNIT_YEARS)
        self.validity_unit.addItem(VALIDITY_UNIT_MONTHS_LABEL, VALIDITY_UNIT_MONTHS)
        validity_row.addWidget(QLabel("Platnost:"))
        validity_row.addWidget(self.validity_value)
        validity_row.addWidget(self.validity_unit)
        validity_row.addStretch()

        form.addWidget(basics)
        form.addWidget(self.written_group)
        form.addWidget(self.oral_group)
        form.addWidget(organization)
        form.addWidget(validity)
        form.addStretch()

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = create_save_cancel_box(self, is_new=is_new)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=is_new,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self._snapshot)
        self._editor.install_auto_dirty_tracking()
        self.written_composition.changed.connect(self._editor.mark_dirty)
        self.written_composition.changed.connect(self._update_summary)
        self.oral_composition.changed.connect(self._editor.mark_dirty)
        self.seconds.valueChanged.connect(self._update_summary)
        self.written_group.toggled.connect(self._editor.mark_dirty)
        self.written_group.toggled.connect(self._update_summary)
        self.oral_group.toggled.connect(self._editor.mark_dirty)
        self.mode_group.buttonToggled.connect(lambda *_args: self._editor.mark_dirty())

        self._load_available_topics()
        if test is not None:
            self._load_test(test)
        self._update_summary()
        configure_form_tab_navigation(self)
        self._editor.capture_baseline()
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def accept(self) -> None:
        data = self.get_data()
        try:
            if self.test_id is None:
                created = test_definition_service.create_test(**data)
                self.saved_test_id = created.id
            else:
                updated = test_definition_service.update_test(self.test_id, **data)
                self.saved_test_id = updated.id
        except TestDefinitionError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "name": self.name.text(),
            "description": self.description.toPlainText(),
            "active": self.active_checkbox.isChecked(),
            "uses_written": self.written_group.isChecked(),
            "allowed_wrong_answers": self.allowed_errors.value(),
            "seconds_per_question": self.seconds.value(),
            "uses_oral": self.oral_group.isChecked(),
            "examiner_mode": self._examiner_mode(),
            "validity_value": self.validity_value.value(),
            "validity_unit": self.validity_unit.currentData(),
            "written_topics": [
                TestTopicQuota(topic_id=topic_id, question_count=count)
                for topic_id, count in self.written_composition.rows()
            ],
            "oral_topics": [
                TestTopicQuota(topic_id=topic_id, question_count=count)
                for topic_id, count in self.oral_composition.rows()
            ],
        }

    def _snapshot(self) -> tuple:
        return (
            self.name.text(),
            self.description.toPlainText(),
            self.active_checkbox.isChecked(),
            self.written_group.isChecked(),
            tuple(self.written_composition.rows()),
            self.allowed_errors.value(),
            self.seconds.value(),
            self.oral_group.isChecked(),
            tuple(self.oral_composition.rows()),
            self._examiner_mode(),
            self.validity_value.value(),
            self.validity_unit.currentData(),
        )

    def _examiner_mode(self) -> str:
        if self.mode_single.isChecked():
            return EXAMINER_MODE_SINGLE
        if self.mode_commission.isChecked():
            return EXAMINER_MODE_COMMISSION
        return EXAMINER_MODE_NONE

    def _update_summary(self, *_args) -> None:
        if self.written_group.isChecked():
            quotas = [
                TestTopicQuota(topic_id=topic_id, question_count=count)
                for topic_id, count in self.written_composition.rows()
            ]
            count = total_written_questions(quotas)
        else:
            count = 0
        duration = total_written_seconds(count, self.seconds.value())
        self.total_questions_label.setText(f"Celkem otázek: {count}")
        self.duration_label.setText(f"Čas testu: {format_test_duration(duration)}")

    def _load_available_topics(self) -> None:
        self.written_composition.set_available_topics(
            [
                (int(topic.id), topic.name)
                for topic in written_question_topic_service.list_topics(include_inactive=False)
            ]
        )
        self.oral_composition.set_available_topics(
            [
                (int(topic.id), topic.name)
                for topic in oral_question_topic_service.list_topics(include_inactive=False)
            ]
        )

    def _load_test(self, test: TestDefinition) -> None:
        self.name.setText(test.name)
        self.description.setPlainText(test.description or "")
        self.active_checkbox.setChecked(test.active)
        self.written_group.setChecked(test.uses_written)
        self.oral_group.setChecked(test.uses_oral)
        self.allowed_errors.setValue(test.allowed_wrong_answers)
        self.seconds.setValue(test.seconds_per_question)
        self.validity_value.setValue(test.validity_value)
        unit_index = self.validity_unit.findData(test.validity_unit)
        if unit_index >= 0:
            self.validity_unit.setCurrentIndex(unit_index)
        self.mode_none.setChecked(test.examiner_mode == EXAMINER_MODE_NONE)
        self.mode_single.setChecked(test.examiner_mode == EXAMINER_MODE_SINGLE)
        self.mode_commission.setChecked(test.examiner_mode == EXAMINER_MODE_COMMISSION)
        self.written_composition.set_rows(self._topic_rows(test.id, oral=False))
        self.oral_composition.set_rows(self._topic_rows(test.id, oral=True))

    def _topic_rows(self, test_id: int, *, oral: bool) -> list[tuple[int, str, int]]:
        if oral:
            lines = test_definition_service.get_oral_topics(test_id)
            topic_getter = oral_question_topic_service.get_topic
        else:
            lines = test_definition_service.get_written_topics(test_id)
            topic_getter = written_question_topic_service.get_topic
        rows: list[tuple[int, str, int]] = []
        for line in lines:
            topic = topic_getter(line.topic_id)
            if topic is None:
                label = ""
            elif topic.active:
                label = topic.name
            else:
                label = f"{topic.name} (neaktivní)"
            rows.append((int(line.topic_id), label, int(line.question_count)))
        return rows
