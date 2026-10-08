"""Agenda připravených zkoušek."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.export import open_export_file
from core.services.storage_service import storage_service
from core.widgets.dialog_utils import (
    configure_edit_action_button,
    configure_new_action_button,
    configure_perform_action_button,
)
from core.widgets.filter_bar import FilterBar
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import refresh_and_restore_selection
from core.widgets.table_utils import configure_table_columns
from moduly.testy.constants import (
    EXAM_ACTION_BATCH_PAPER,
    EXAM_ACTION_CONTINUE_WRITTEN,
    EXAM_ACTION_DETAIL,
    EXAM_ACTION_ENTER_PAPER,
    EXAM_ACTION_PREPARE,
    EXAM_ACTION_PRINT_PROTOCOL,
    EXAM_ACTION_PRINT_WRITTEN,
    EXAM_ACTION_START_WRITTEN,
    EXAM_COL_EMPLOYEE,
    EXAM_COL_ID,
    EXAM_COL_TEST,
    EXAM_SEARCH_PLACEHOLDER,
    MODULE_NAME,
    WRITTEN_FINISH_EXPIRED,
)
from moduly.testy.sluzby.exam_protocol_export_service import (
    exam_protocol_export_service,
    protocol_filename,
)
from moduly.testy.sluzby.paper_test_export_service import paper_test_export_service
from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
from moduly.testy.sluzby.written_exam_service import written_exam_service
from moduly.testy.ui.paper_answer_dialog import PaperAnswerDialog
from moduly.testy.ui.paper_batch_dialog import PaperBatchDialog
from moduly.testy.ui.paper_test_options_dialog import PaperTestOptionsDialog
from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog
from moduly.testy.ui.test_exam_table import TestExamTable
from moduly.testy.ui.written_exam_window import (
    WrittenExamWindow,
    present_written_handover,
)

_ROLE_SEARCH = Qt.ItemDataRole.UserRole + 1


class TestExamsTab(QWidget):
    exams_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.prepare_btn = QPushButton(EXAM_ACTION_PREPARE)
        configure_new_action_button(self.prepare_btn)
        self.batch_btn = QPushButton(EXAM_ACTION_BATCH_PAPER)
        self.batch_btn.setObjectName("exam-batch-paper-button")
        configure_new_action_button(self.batch_btn)
        self.detail_btn = QPushButton(EXAM_ACTION_DETAIL)
        configure_edit_action_button(self.detail_btn)
        self.detail_btn.setEnabled(False)
        self.start_btn = QPushButton(EXAM_ACTION_START_WRITTEN)
        configure_perform_action_button(self.start_btn)
        self.start_btn.setEnabled(False)
        self.print_btn = QPushButton(EXAM_ACTION_PRINT_WRITTEN)
        self.print_btn.setObjectName("exam-print-paper-button")
        configure_perform_action_button(self.print_btn)
        self.print_btn.setEnabled(False)
        self.protocol_btn = QPushButton(EXAM_ACTION_PRINT_PROTOCOL)
        self.protocol_btn.setObjectName("exam-print-protocol-button")
        configure_perform_action_button(self.protocol_btn)
        self.protocol_btn.setEnabled(False)
        self.paper_btn = QPushButton(EXAM_ACTION_ENTER_PAPER)
        self.paper_btn.setObjectName("exam-enter-paper-button")
        configure_perform_action_button(self.paper_btn)
        self.paper_btn.setEnabled(False)
        toolbar.addWidget(self.prepare_btn)
        toolbar.addWidget(self.batch_btn)
        toolbar.addWidget(self.detail_btn)
        toolbar.addWidget(self.start_btn)
        toolbar.addWidget(self.print_btn)
        toolbar.addWidget(self.protocol_btn)
        toolbar.addWidget(self.paper_btn)
        toolbar.addStretch()

        self.table = TestExamTable()
        configure_table_columns(self.table, "test_exams")
        self.text_filter = FilterBar(
            self.table,
            placeholder=EXAM_SEARCH_PLACEHOLDER,
            apply_fn=self._apply_search,
        )

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table, 1)

        self.prepare_btn.clicked.connect(self.prepare_exam)
        self.batch_btn.clicked.connect(self.prepare_paper_batch)
        self.detail_btn.clicked.connect(self.open_selected)
        self.start_btn.clicked.connect(self.start_electronic_test)
        self.print_btn.clicked.connect(self.print_paper_test)
        self.protocol_btn.clicked.connect(self.print_exam_protocol)
        self.paper_btn.clicked.connect(self.enter_paper_answers)
        self._written_exam_window: WrittenExamWindow | None = None
        self._handover = None
        self.table.doubleClicked.connect(self.open_selected)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        install_table_row_actions(
            self.table,
            on_edit=self.open_selected,
            can_edit=lambda: self.detail_btn.isEnabled(),
        )
        self.refresh()

    def refresh(self) -> None:
        selected_id = self.table.selected_exam_id()
        self.table.load_exams(test_exam_service.list_exams())
        configure_table_columns(self.table, "test_exams")
        refresh_and_restore_selection(self.table, selected_id, id_column=EXAM_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()
        self.exams_changed.emit()

    def prepare_exam(self) -> None:
        dialog = TestExamPrepareDialog(self)
        if not dialog.exec():
            return
        self._reload(dialog.saved_exam_id)

    def prepare_paper_batch(self) -> None:
        dialog = PaperBatchDialog(self)
        if not dialog.exec():
            return
        focus_id = None
        if dialog.batch_result is not None and dialog.batch_result.exams:
            focus_id = int(dialog.batch_result.exams[-1].id)
        self._reload(focus_id)

    def open_selected(self) -> None:
        exam_id = self.table.selected_exam_id()
        if exam_id is None:
            return
        exam = test_exam_service.get_exam(exam_id)
        if exam is None:
            QMessageBox.warning(self, MODULE_NAME, "Zkouška nebyla nalezena.")
            self.refresh()
            return
        dialog = TestExamDetailDialog(self, exam_id=exam.id)
        dialog.exec()
        if dialog.results_changed or dialog.protocol_changed:
            self.refresh()
        else:
            self._update_action_buttons()

    def start_electronic_test(self) -> None:
        exam_id = self.table.selected_exam_id()
        action = written_exam_service.electronic_action(exam_id) if exam_id else ""
        if action == "continue":
            self._continue_electronic_test(int(exam_id))
            return
        if exam_id is None or action != "start":
            self._update_action_buttons()
            return
        answer = QMessageBox.question(
            self,
            MODULE_NAME,
            written_exam_service.confirmation_text(exam_id),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            written_exam_service.start(exam_id)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            self.refresh()
            return
        self.refresh()
        window = WrittenExamWindow(exam_id, self)
        self._written_exam_window = window
        window.enter_testing_mode()

    def _continue_electronic_test(self, exam_id: int) -> None:
        try:
            reason = written_exam_service.resume(exam_id)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            self.refresh()
            return
        if reason == WRITTEN_FINISH_EXPIRED:
            self._handover = present_written_handover(
                self,
                lambda: self.focus_exam(exam_id),
            )
            return
        window = WrittenExamWindow(exam_id, self)
        self._written_exam_window = window
        window.enter_testing_mode()

    def focus_exam(self, exam_id: int | None) -> None:
        self._reload(exam_id)

    def note_written_exam_finished(self, exam_id: int) -> None:
        self.focus_exam(exam_id)

    def _reload(self, exam_id: int | None) -> None:
        self.table.load_exams(test_exam_service.list_exams())
        configure_table_columns(self.table, "test_exams")
        refresh_and_restore_selection(self.table, exam_id, id_column=EXAM_COL_ID)
        self.text_filter.apply_filter()
        self._update_action_buttons()
        self.exams_changed.emit()

    def _apply_search(self, text: str) -> tuple[int, int]:
        needle = text.casefold()
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            item = self.table.item(row, EXAM_COL_EMPLOYEE)
            haystack = str(item.data(_ROLE_SEARCH) or "") if item is not None else ""
            test_item = self.table.item(row, EXAM_COL_TEST)
            if test_item is not None:
                haystack = f"{haystack} {test_item.text()}"
            match = needle in haystack.casefold() if needle else True
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1
        return visible, total

    def print_paper_test(self) -> None:
        exam_id = self.table.selected_exam_id()
        if exam_id is None or not paper_test_export_service.can_export(exam_id):
            self._update_action_buttons()
            return
        options = PaperTestOptionsDialog(self)
        if not options.exec():
            return
        exam = test_exam_service.get_exam(exam_id)
        if exam is None:
            self.refresh()
            return
        default_path = storage_service.exports_dir / paper_test_export_service.test_filename(exam)
        chosen, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Písemný test",
            str(default_path),
            "OpenDocument (*.odt)",
        )
        if not chosen:
            return
        test_path = Path(chosen)
        key_path = None
        if options.include_key:
            key_path = test_path.with_name(paper_test_export_service.key_filename(exam))
        try:
            result = paper_test_export_service.export(
                exam_id,
                test_path,
                include_key=options.include_key,
                key_path=key_path,
            )
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        open_export_file(result.test_path, parent=self, title="Písemný test")
        if result.key_path is not None:
            open_export_file(result.key_path, parent=self, title="Klíč správných odpovědí")
        self._update_action_buttons()

    def print_exam_protocol(self) -> None:
        exam_id = self.table.selected_exam_id()
        if exam_id is None or not exam_protocol_export_service.can_export(exam_id):
            self._update_action_buttons()
            return
        exam = test_exam_service.get_exam(exam_id)
        if exam is None:
            self.refresh()
            return
        default_path = storage_service.exports_dir / protocol_filename(exam)
        chosen, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Protokol o zkoušce",
            str(default_path),
            "OpenDocument (*.odt)",
        )
        if not chosen:
            return
        try:
            path = exam_protocol_export_service.export(exam_id, chosen)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        open_export_file(path, parent=self, title="Protokol o zkoušce")
        self._update_action_buttons()

    def enter_paper_answers(self) -> None:
        exam_id = self.table.selected_exam_id()
        if exam_id is None or not written_exam_service.can_enter_paper(exam_id):
            self._update_action_buttons()
            return
        try:
            dialog = PaperAnswerDialog(exam_id, self)
        except TestExamError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        dialog.exec()
        if dialog.evaluated:
            self.focus_exam(exam_id)
        else:
            self._update_action_buttons()

    def _update_action_buttons(self) -> None:
        exam_id = self.table.selected_exam_id()
        self.detail_btn.setEnabled(exam_id is not None)
        self.print_btn.setEnabled(
            exam_id is not None and paper_test_export_service.can_export(exam_id)
        )
        self.paper_btn.setEnabled(
            exam_id is not None and written_exam_service.can_enter_paper(exam_id)
        )
        self.protocol_btn.setEnabled(
            exam_id is not None and exam_protocol_export_service.can_export(exam_id)
        )
        action = written_exam_service.electronic_action(exam_id) if exam_id else ""
        if action == "continue":
            self.start_btn.setText(EXAM_ACTION_CONTINUE_WRITTEN)
            self.start_btn.setEnabled(True)
            return
        self.start_btn.setText(EXAM_ACTION_START_WRITTEN)
        self.start_btn.setEnabled(action == "start")
