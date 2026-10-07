"""Hromadná příprava papírových testů pro více zaměstnanců."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
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
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.constants import (
    EXAM_ROLE_CHAIR_LABEL,
    EXAMINER_MODE_COMMISSION,
    EXAMINER_MODE_LABELS,
    EXAMINER_MODE_NONE,
    EXAMINER_MODE_SINGLE,
    MODULE_NAME,
    PAPER_BATCH_DIALOG_TITLE,
    PAPER_BATCH_KEY_OPTION,
)
from moduly.testy.sluzby.paper_batch_service import (
    format_batch_summary,
    prepare_and_export_paper_batch,
)
from moduly.testy.sluzby.test_definition_service import test_definition_service
from moduly.testy.sluzby.test_employee_service import test_employee_service
from moduly.testy.sluzby.test_exam_service import TestExamError, calculate_valid_until
from moduly.testy.ui.exam_person_combo import ExamPersonCombo

_ROLE_ID = Qt.ItemDataRole.UserRole
_ROLE_WORKPLACE = Qt.ItemDataRole.UserRole + 1
_ROLE_SEARCH = Qt.ItemDataRole.UserRole + 2


class PaperBatchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.batch_result = None
        self._setting_valid = False
        self._valid_custom = False

        self.setWindowTitle(PAPER_BATCH_DIALOG_TITLE)
        configure_resizable_form_dialog(
            self,
            width=920,
            height=760,
            min_width=720,
            min_height=560,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QVBoxLayout(form_host)

        basics = QGroupBox("Zkouška")
        basics_form = QFormLayout(basics)
        self.test = NoWheelComboBox()
        self.test.setObjectName("batch-test")
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
        folder_row = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setObjectName("batch-folder")
        self.folder.setPlaceholderText("Složka pro vygenerované testy")
        self.browse_folder_btn = QPushButton("Vybrat složku")
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.browse_folder_btn)
        basics_form.addRow("Test:", self.test)
        basics_form.addRow("Datum zkoušky:", self.exam_date)
        basics_form.addRow("Platí do:", self.valid_until)
        basics_form.addRow("Režim:", self.mode_label)
        basics_form.addRow("Složka:", folder_row)
        self.shared_key = QCheckBox(PAPER_BATCH_KEY_OPTION)
        self.shared_key.setObjectName("batch-shared-key-checkbox")
        self.shared_key.setChecked(False)
        basics_form.addRow("", self.shared_key)

        self.single_box = QGroupBox("Zkoušející")
        single_form = QFormLayout(self.single_box)
        self.examiner = ExamPersonCombo()
        single_form.addRow("Zkoušející:", self.examiner)

        self.commission_box = QGroupBox("Komise")
        commission_layout = QVBoxLayout(self.commission_box)
        chair_form = QFormLayout()
        self.chair = ExamPersonCombo()
        chair_form.addRow(f"{EXAM_ROLE_CHAIR_LABEL}:", self.chair)
        member_row = QHBoxLayout()
        self.member = ExamPersonCombo()
        self.add_member_btn = QPushButton("Přidat člena/členku")
        member_row.addWidget(self.member, 1)
        member_row.addWidget(self.add_member_btn)
        self.members = QListWidget()
        self.members.setMaximumHeight(100)
        self.remove_member_btn = QPushButton("Odebrat člena/členku")
        commission_layout.addLayout(chair_form)
        commission_layout.addLayout(member_row)
        commission_layout.addWidget(self.members)
        commission_layout.addWidget(self.remove_member_btn)

        people = QGroupBox("Zaměstnanci")
        people_layout = QVBoxLayout(people)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("batch-employee-search")
        self.search.setPlaceholderText("Osobní číslo, příjmení nebo jméno")
        self.workplace = NoWheelComboBox()
        self.workplace.setObjectName("batch-workplace-filter")
        filters.addWidget(self.search, 1)
        filters.addWidget(self.workplace)
        actions = QHBoxLayout()
        self.select_visible_btn = QPushButton("Označit vše zobrazené")
        self.select_visible_btn.setObjectName("batch-select-visible")
        self.clear_visible_btn = QPushButton("Odznačit vše zobrazené")
        self.clear_visible_btn.setObjectName("batch-clear-visible")
        actions.addWidget(self.select_visible_btn)
        actions.addWidget(self.clear_visible_btn)
        actions.addStretch()
        self.employees = QTableWidget()
        self.employees.setObjectName("batch-employee-table")
        self.employees.setColumnCount(4)
        self.employees.setHorizontalHeaderLabels(
            ["", "Osobní číslo", "Příjmení a jméno", "Pracoviště"]
        )
        self.employees.verticalHeader().setVisible(False)
        self.employees.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.employees.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.employees.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.employees.setMinimumHeight(220)
        people_layout.addLayout(filters)
        people_layout.addLayout(actions)
        people_layout.addWidget(self.employees, 1)

        form.addWidget(basics)
        form.addWidget(self.single_box)
        form.addWidget(self.commission_box)
        form.addWidget(people, 1)

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

        self._eligible_examiners = test_employee_service.list_eligible_examiners()
        self.examiner.set_people(self._eligible_examiners)
        self.chair.set_people(self._eligible_examiners)
        self.member.set_people(self._eligible_examiners)
        self._load_tests()
        self._load_employees()
        self._apply_mode()

        self.test.currentIndexChanged.connect(self._on_test_changed)
        self.exam_date.dateChanged.connect(self._on_exam_date_changed)
        self.valid_until.dateChanged.connect(self._on_valid_edited)
        self.add_member_btn.clicked.connect(self._add_member)
        self.remove_member_btn.clicked.connect(self._remove_member)
        self.search.textChanged.connect(self._apply_employee_filter)
        self.workplace.currentIndexChanged.connect(self._apply_employee_filter)
        self.select_visible_btn.clicked.connect(self._select_visible)
        self.clear_visible_btn.clicked.connect(self._clear_visible)
        self.browse_folder_btn.clicked.connect(self._browse_folder)
        configure_form_tab_navigation(self)

    def accept(self) -> None:
        folder = self._ensure_folder()
        if folder is None:
            return
        try:
            result = prepare_and_export_paper_batch(
                directory=folder,
                include_shared_key=self.shared_key.isChecked(),
                **self.get_data(),
            )
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        self.batch_result = result
        QMessageBox.information(self, MODULE_NAME, format_batch_summary(result))
        super().accept()

    def get_data(self) -> dict:
        mode = self._mode()
        return {
            "employee_ids": self.selected_employee_ids(),
            "test_id": self._test_id(),
            "exam_date": self.exam_date.date().toPython(),
            "valid_until": self.valid_until.date().toPython(),
            "examiner_id": self.examiner.person_id() if mode == EXAMINER_MODE_SINGLE else None,
            "chair_id": self.chair.person_id() if mode == EXAMINER_MODE_COMMISSION else None,
            "member_ids": self._member_ids() if mode == EXAMINER_MODE_COMMISSION else [],
        }

    def selected_employee_ids(self) -> list[int]:
        result = []
        for row in range(self.employees.rowCount()):
            item = self.employees.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            try:
                result.append(int(item.data(_ROLE_ID)))
            except (TypeError, ValueError):
                continue
        return result

    def _load_tests(self) -> None:
        self.test.clear()
        self.test.addItem("", None)
        for item in test_definition_service.list_tests(include_inactive=False):
            if not item.uses_written:
                continue
            self.test.addItem(item.name, int(item.id))

    def _load_employees(self) -> None:
        employees = [
            employee
            for employee in test_employee_service.list_employees(include_inactive=False)
            if employee.active
        ]
        employees.sort(
            key=lambda employee: (
                employee.last_name.casefold(),
                employee.first_name.casefold(),
                employee.personal_number.casefold(),
            )
        )
        workplaces = {
            workplace.id: workplace.name
            for workplace in settings_service.get_workplaces(include_inactive=True)
        }
        self.employees.setRowCount(len(employees))
        seen_workplaces: dict[int, str] = {}
        for row, employee in enumerate(employees):
            workplace_name = workplaces.get(employee.workplace_id, "")
            seen_workplaces[int(employee.workplace_id)] = workplace_name
            check = QTableWidgetItem()
            check.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            check.setCheckState(Qt.CheckState.Unchecked)
            check.setData(_ROLE_ID, int(employee.id))
            check.setData(_ROLE_WORKPLACE, int(employee.workplace_id))
            needle = " ".join(
                (
                    employee.personal_number,
                    employee.last_name,
                    employee.first_name,
                )
            )
            check.setData(_ROLE_SEARCH, needle.casefold())
            self.employees.setItem(row, 0, check)
            self.employees.setItem(row, 1, QTableWidgetItem(employee.personal_number))
            self.employees.setItem(
                row,
                2,
                QTableWidgetItem(f"{employee.last_name} {employee.first_name}"),
            )
            self.employees.setItem(row, 3, QTableWidgetItem(workplace_name))
        self.workplace.blockSignals(True)
        self.workplace.clear()
        self.workplace.addItem("Všechna pracoviště", None)
        for workplace_id, name in sorted(seen_workplaces.items(), key=lambda item: item[1].casefold()):
            self.workplace.addItem(name or "Bez pracoviště", workplace_id)
        self.workplace.blockSignals(False)
        self._apply_employee_filter()

    def _apply_employee_filter(self) -> None:
        needle = self.search.text().strip().casefold()
        workplace_id = self.workplace.currentData()
        for row in range(self.employees.rowCount()):
            item = self.employees.item(row, 0)
            if item is None:
                self.employees.setRowHidden(row, True)
                continue
            haystack = str(item.data(_ROLE_SEARCH) or "")
            text_match = needle in haystack if needle else True
            place_match = True
            if workplace_id is not None:
                place_match = item.data(_ROLE_WORKPLACE) == workplace_id
            self.employees.setRowHidden(row, not (text_match and place_match))

    def _select_visible(self) -> None:
        self._set_visible_checks(Qt.CheckState.Checked)

    def _clear_visible(self) -> None:
        self._set_visible_checks(Qt.CheckState.Unchecked)

    def _set_visible_checks(self, state: Qt.CheckState) -> None:
        for row in range(self.employees.rowCount()):
            if self.employees.isRowHidden(row):
                continue
            item = self.employees.item(row, 0)
            if item is not None:
                item.setCheckState(state)

    def _browse_folder(self) -> None:
        current = self.folder.text().strip()
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Složka pro papírové testy",
            current,
        )
        if chosen:
            self.folder.setText(chosen)

    def _ensure_folder(self) -> Path | None:
        text = self.folder.text().strip()
        if not text:
            self._browse_folder()
            text = self.folder.text().strip()
        if not text:
            return None
        folder = Path(text)
        if not folder.is_dir():
            QMessageBox.warning(self, MODULE_NAME, "Vyberte existující složku pro testy.")
            return None
        return folder

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

    def _add_member(self) -> None:
        member_id = self.member.person_id()
        if member_id is None:
            QMessageBox.warning(self, MODULE_NAME, "Vyberte člena/členku komise.")
            return
        if member_id == self.chair.person_id() or member_id in self._member_ids():
            QMessageBox.warning(
                self,
                MODULE_NAME,
                "Předseda/předsedkyně komise nemůže být současně členem/členkou komise."
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
