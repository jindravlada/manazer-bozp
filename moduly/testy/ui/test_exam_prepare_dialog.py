"""Dialog přípravy konkrétní zkoušky."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
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
from core.widgets.no_wheel_guards import NoWheelComboBox
from moduly.testy.constants import (
    EXAM_DIALOG_TITLE,
    EXAMINER_MODE_COMMISSION,
    EXAMINER_MODE_LABELS,
    EXAMINER_MODE_NONE,
    EXAMINER_MODE_SINGLE,
    MODULE_NAME,
)
from moduly.testy.sluzby.test_definition_service import test_definition_service
from moduly.testy.sluzby.test_employee_service import test_employee_service
from moduly.testy.sluzby.test_exam_service import (
    EXAMINEE_CANNOT_EXAMINE,
    TestExamError,
    calculate_valid_until,
    test_exam_service,
)
from moduly.testy.ui.exam_person_combo import ExamPersonCombo


class TestExamPrepareDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.saved_exam_id: int | None = None
        self._setting_valid = False
        self._valid_custom = False

        self.setWindowTitle(EXAM_DIALOG_TITLE)
        configure_resizable_form_dialog(
            self,
            width=760,
            height=680,
            min_width=620,
            min_height=460,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QVBoxLayout(form_host)

        basics = QGroupBox("Zkouška")
        basics_form = QFormLayout(basics)
        self.employee = ExamPersonCombo()
        self.test = NoWheelComboBox()
        self.exam_date = QDateEdit()
        self.exam_date.setCalendarPopup(True)
        self.exam_date.setDisplayFormat("d. M. yyyy")
        self.valid_until = QDateEdit()
        self.valid_until.setCalendarPopup(True)
        self.valid_until.setDisplayFormat("d. M. yyyy")
        today = date.today()
        self.exam_date.setDate(QDate(today.year, today.month, today.day))
        self.valid_until.setDate(QDate(today.year, today.month, today.day))
        self.mode_label = QLabel("")
        self.mode_label.setWordWrap(True)
        basics_form.addRow("Zaměstnanec:", self.employee)
        basics_form.addRow("Test:", self.test)
        basics_form.addRow("Datum zkoušky:", self.exam_date)
        basics_form.addRow("Platí do:", self.valid_until)
        basics_form.addRow("Režim:", self.mode_label)

        self.single_box = QGroupBox("Zkoušející")
        single_form = QFormLayout(self.single_box)
        self.examiner = ExamPersonCombo()
        single_form.addRow("Zkoušející:", self.examiner)

        self.commission_box = QGroupBox("Komise")
        commission_layout = QVBoxLayout(self.commission_box)
        chair_form = QFormLayout()
        self.chair = ExamPersonCombo()
        chair_form.addRow("Předseda:", self.chair)
        member_row = QHBoxLayout()
        self.member = ExamPersonCombo()
        self.add_member_btn = QPushButton("Přidat člena")
        member_row.addWidget(self.member, 1)
        member_row.addWidget(self.add_member_btn)
        self.members = QListWidget()
        self.members.setMaximumHeight(120)
        self.remove_member_btn = QPushButton("Odebrat člena")
        commission_layout.addLayout(chair_form)
        commission_layout.addLayout(member_row)
        commission_layout.addWidget(self.members)
        commission_layout.addWidget(self.remove_member_btn)

        form.addWidget(basics)
        form.addWidget(self.single_box)
        form.addWidget(self.commission_box)
        form.addStretch()

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = create_save_cancel_box(self, is_new=True)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=True,
            title=self.windowTitle(),
        )
        self._editor.install_auto_dirty_tracking()

        self.employee.set_people(test_employee_service.list_employees(include_inactive=False))
        self._eligible_examiners = test_employee_service.list_eligible_examiners()
        self._apply_examiner_choices()
        self._load_tests()
        self._apply_mode()

        self.employee.currentTextChanged.connect(self._on_examinee_changed)
        self.test.currentIndexChanged.connect(self._on_test_changed)
        self.exam_date.dateChanged.connect(self._on_exam_date_changed)
        self.valid_until.dateChanged.connect(self._on_valid_edited)
        self.add_member_btn.clicked.connect(self._add_member)
        self.remove_member_btn.clicked.connect(self._remove_member)
        configure_form_tab_navigation(self)

    def accept(self) -> None:
        try:
            created = test_exam_service.prepare_exam(**self.get_data())
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self.saved_exam_id = created.id
        super().accept()

    def get_data(self) -> dict:
        mode = self._mode()
        return {
            "employee_id": self.employee.person_id(),
            "test_id": self._test_id(),
            "exam_date": self.exam_date.date().toPython(),
            "valid_until": self.valid_until.date().toPython(),
            "examiner_id": self.examiner.person_id() if mode == EXAMINER_MODE_SINGLE else None,
            "chair_id": self.chair.person_id() if mode == EXAMINER_MODE_COMMISSION else None,
            "member_ids": self._member_ids() if mode == EXAMINER_MODE_COMMISSION else [],
        }

    def _load_tests(self) -> None:
        self.test.clear()
        self.test.addItem("", None)
        for item in test_definition_service.list_tests(include_inactive=False):
            self.test.addItem(item.name, int(item.id))

    def _test_id(self) -> int | None:
        data = self.test.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _on_test_changed(self) -> None:
        self._valid_custom = False
        self._apply_mode()
        self._recompute_valid_until()

    def _on_exam_date_changed(self) -> None:
        self._recompute_valid_until()

    def _on_valid_edited(self) -> None:
        if self._setting_valid:
            return
        self._valid_custom = True

    def _recompute_valid_until(self) -> None:
        if self._valid_custom:
            return
        test = test_definition_service.get_test(self._test_id())
        if test is None:
            return
        valid = calculate_valid_until(
            self.exam_date.date().toPython(),
            test.validity_value,
            test.validity_unit,
        )
        self._set_valid_until(valid)

    def _set_valid_until(self, value: date) -> None:
        self._setting_valid = True
        self.valid_until.setDate(QDate(value.year, value.month, value.day))
        self._setting_valid = False

    def _mode(self) -> str:
        test = test_definition_service.get_test(self._test_id())
        if test is None:
            return EXAMINER_MODE_NONE
        return test.examiner_mode

    def _apply_mode(self) -> None:
        mode = self._mode()
        self.mode_label.setText(EXAMINER_MODE_LABELS.get(mode, ""))
        self.single_box.setVisible(mode == EXAMINER_MODE_SINGLE)
        self.commission_box.setVisible(mode == EXAMINER_MODE_COMMISSION)

    def _on_examinee_changed(self) -> None:
        examinee_id = self.employee.person_id()
        removed = False
        if examinee_id is not None:
            removed = self._drop_examinee_from_selection(int(examinee_id))
        self._apply_examiner_choices()
        if removed:
            QMessageBox.warning(self, MODULE_NAME, EXAMINEE_CANNOT_EXAMINE)

    def _apply_examiner_choices(self) -> None:
        examinee_id = self.employee.person_id()
        offered = [
            person
            for person in self._eligible_examiners
            if examinee_id is None or int(person.id) != int(examinee_id)
        ]
        clear_examiner = self._combo_matches(self.examiner, examinee_id)
        clear_chair = self._combo_matches(self.chair, examinee_id)
        clear_member = self._combo_matches(self.member, examinee_id)
        self.examiner.set_people(offered)
        self.chair.set_people(offered)
        self.member.set_people(offered)
        if clear_examiner:
            self.examiner.setCurrentIndex(0)
        if clear_chair:
            self.chair.setCurrentIndex(0)
        if clear_member:
            self.member.setCurrentIndex(0)

    def _drop_examinee_from_selection(self, examinee_id: int) -> bool:
        removed = self._combo_matches(self.examiner, examinee_id)
        removed = self._combo_matches(self.chair, examinee_id) or removed
        return self._remove_member_id(examinee_id) > 0 or removed

    def _combo_matches(self, combo: ExamPersonCombo, employee_id: int | None) -> bool:
        if employee_id is None:
            return False
        selected = combo.person_id()
        return selected is not None and int(selected) == int(employee_id)

    def _remove_member_id(self, employee_id: int) -> int:
        removed = 0
        for row in range(self.members.count() - 1, -1, -1):
            item = self.members.item(row)
            if item is None:
                continue
            try:
                member_id = int(item.data(Qt.ItemDataRole.UserRole))
            except (TypeError, ValueError):
                continue
            if member_id == int(employee_id):
                self.members.takeItem(row)
                removed += 1
        return removed

    def _add_member(self) -> None:
        member_id = self.member.person_id()
        if member_id is None:
            QMessageBox.warning(self, MODULE_NAME, "Vyberte člena komise.")
            return
        if member_id == self.chair.person_id() or member_id in self._member_ids():
            QMessageBox.warning(
                self,
                MODULE_NAME,
                "Předseda nemůže být současně členem komise."
                if member_id == self.chair.person_id()
                else "Osoba je v komisi vícekrát.",
            )
            return
        item = QListWidgetItem(self.member.currentText())
        item.setData(Qt.ItemDataRole.UserRole, int(member_id))
        self.members.addItem(item)
        self.member.setCurrentIndex(0)

    def _remove_member(self) -> None:
        row = self.members.currentRow()
        if row >= 0:
            self.members.takeItem(row)

    def _member_ids(self) -> list[int]:
        result = []
        for row in range(self.members.count()):
            item = self.members.item(row)
            if item is None:
                continue
            try:
                result.append(int(item.data(Qt.ItemDataRole.UserRole)))
            except (TypeError, ValueError):
                continue
        return result
