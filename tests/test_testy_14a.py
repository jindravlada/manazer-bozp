"""TESTY-14a: stav podepsaného protokolu v seznamu zkoušek."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-14a-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from sqlalchemy import delete

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from core.theme.status_colors import STATUS_DONE_BG, STATUS_DONE_TEXT, STATUS_NEUTRAL_BG
    from core.widgets.table_utils import configure_table_columns
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EXAM_COL_DATE,
        EXAM_COL_EMPLOYEE,
        EXAM_COL_EXAM_RESULT,
        EXAM_COL_ID,
        EXAM_COL_PROTOCOL,
        EXAM_COL_STATUS,
        EXAM_COL_TEST,
        EXAM_COLUMN_HEADERS,
        EXAM_PROTOCOL_ATTACHED,
        EXAM_PROTOCOL_MISSING,
        EXAM_PROTOCOL_NOT_APPLICABLE,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_COMPLETED_LABEL,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_PREPARED_LABEL,
        EXAM_STATUS_STARTED,
        EXAM_STATUS_STARTED_LABEL,
        EXAMINER_MODE_NONE,
        VALIDITY_COLUMN_HEADERS,
        VALIDITY_UNIT_YEARS,
        WRITTEN_RESULT_PASSED,
        WRITTEN_RESULT_PASSED_LABEL,
    )
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
    from moduly.testy.modely.test_definition_written_topic import TestDefinitionWrittenTopic
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
    from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.sluzby.exam_signed_protocol_service import (
        ENTITY_TYPE,
        exam_signed_protocol_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import format_exam_date, test_exam_service
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exam_table import TestExamTable
    from moduly.testy.ui.test_exams_tab import TestExamsTab


def _pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n" + marker + b"\n%%EOF\n"


def _wipe() -> None:
    from core.services.storage_service import storage_service

    protocol_dir = storage_service.attachments_dir / ENTITY_TYPE
    if protocol_dir.exists():
        shutil.rmtree(protocol_dir)
    with get_session() as session:
        session.execute(delete(TestExamWrittenChoice))
        session.execute(delete(TestExamWrittenAnswer))
        session.execute(delete(TestExamWrittenQuestion))
        session.execute(delete(TestExamOralQuestion))
        session.execute(delete(TestExamExaminer))
        session.execute(delete(TestExam))
        session.execute(delete(TestExamValidityTracking))
        session.execute(delete(Attachment).where(Attachment.entity_type == ENTITY_TYPE))
        session.execute(delete(TestDefinitionWrittenTopic))
        session.execute(delete(TestDefinitionOralTopic))
        session.execute(delete(TestDefinition))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.commit()


class SignedProtocolColumnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.files = Path(tempfile.mkdtemp(prefix="testy-14a-src-"))
        self.workplace = settings_service.save_workplace(name="Hala seznamu")
        self.role = responsibility_role_service.create_role(name="Mistr seznamu")
        self.employee = test_employee_service.create_employee(
            personal_number="00100",
            first_name="Jan",
            last_name="Novák",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        self.test = self._definition("BOZP")
        self.attached = self._exam(EXAM_STATUS_COMPLETED, result=WRITTEN_RESULT_PASSED)
        self.open_exam = self._exam(EXAM_STATUS_COMPLETED, result=WRITTEN_RESULT_PASSED)
        self.prepared = self._exam(EXAM_STATUS_PREPARED, result=None)
        self.started = self._exam(EXAM_STATUS_STARTED, result=None)
        source = self.files / "pripojeny.pdf"
        source.write_bytes(_pdf_bytes(b"seznam"))
        exam_signed_protocol_service.attach(self.attached.id, source)
        self.replacement = self.files / "nahrada.pdf"
        self.replacement.write_bytes(_pdf_bytes(b"nahrada"))

    def tearDown(self) -> None:
        shutil.rmtree(self.files, ignore_errors=True)

    def test_column_shows_protocol_state_without_changing_other_data(self) -> None:
        self.assertEqual(EXAM_COLUMN_HEADERS[-1], "Podepsaný protokol")
        self.assertEqual(EXAM_COL_PROTOCOL, len(EXAM_COLUMN_HEADERS) - 1)
        self.assertNotIn("Podepsaný protokol", VALIDITY_COLUMN_HEADERS)

        table = TestExamTable()
        configure_table_columns(table, "test_exams")
        exams = test_exam_service.list_exams()
        table.load_exams(exams)
        self.assertEqual(table.columnCount(), len(EXAM_COLUMN_HEADERS))
        self.assertEqual(
            table.horizontalHeaderItem(EXAM_COL_PROTOCOL).text(),
            "Podepsaný protokol",
        )

        attached = self._row(table, self.attached.id)
        missing = self._row(table, self.open_exam.id)
        prepared = self._row(table, self.prepared.id)
        started = self._row(table, self.started.id)
        self._assert_protocol(table, attached, EXAM_PROTOCOL_ATTACHED, STATUS_DONE_BG, STATUS_DONE_TEXT)
        self._assert_protocol(table, missing, EXAM_PROTOCOL_MISSING, STATUS_NEUTRAL_BG, None)
        self._assert_protocol(table, prepared, EXAM_PROTOCOL_NOT_APPLICABLE, STATUS_NEUTRAL_BG, None)
        self._assert_protocol(table, started, EXAM_PROTOCOL_NOT_APPLICABLE, STATUS_NEUTRAL_BG, None)

        stored = {exam.id: exam for exam in exams}
        self.assertEqual(table.item(attached, EXAM_COL_EMPLOYEE).text(), stored[self.attached.id].employee_display_name)
        self.assertEqual(table.item(attached, EXAM_COL_TEST).text(), "BOZP")
        self.assertEqual(table.item(attached, EXAM_COL_STATUS).text(), EXAM_STATUS_COMPLETED_LABEL)
        self.assertEqual(table.item(attached, EXAM_COL_EXAM_RESULT).text(), WRITTEN_RESULT_PASSED_LABEL)
        self.assertEqual(
            table.item(attached, EXAM_COL_DATE).text(),
            format_exam_date(date(2026, 6, 15)),
        )
        self.assertEqual(table.item(missing, EXAM_COL_STATUS).text(), EXAM_STATUS_COMPLETED_LABEL)
        self.assertEqual(table.item(missing, EXAM_COL_EXAM_RESULT).text(), WRITTEN_RESULT_PASSED_LABEL)
        self.assertEqual(table.item(prepared, EXAM_COL_STATUS).text(), EXAM_STATUS_PREPARED_LABEL)
        self.assertEqual(table.item(prepared, EXAM_COL_EXAM_RESULT).text(), "")
        self.assertEqual(table.item(started, EXAM_COL_STATUS).text(), EXAM_STATUS_STARTED_LABEL)
        self.assertEqual(table.item(started, EXAM_COL_EXAM_RESULT).text(), "")

    def test_list_updates_after_attach_replace_and_remove(self) -> None:
        tab = TestExamsTab()
        before = test_exam_service.get_exam(self.open_exam.id)
        self._select(tab, self.open_exam.id)
        self._run_dialog(tab, click="attach", pdf=self.files / "pripojeny.pdf")
        row = self._row(tab.table, self.open_exam.id)
        self.assertEqual(tab.table.item(row, EXAM_COL_PROTOCOL).text(), EXAM_PROTOCOL_ATTACHED)
        self.assertEqual(tab.table.item(row, EXAM_COL_EXAM_RESULT).text(), WRITTEN_RESULT_PASSED_LABEL)
        self.assertEqual(tab.table.item(row, EXAM_COL_STATUS).text(), EXAM_STATUS_COMPLETED_LABEL)
        updated = test_exam_service.get_exam(self.open_exam.id)
        self.assertEqual(updated.exam_result, before.exam_result)
        self.assertEqual(updated.status, before.status)
        self.assertEqual(updated.written_finished_at, before.written_finished_at)
        self.assertIsNotNone(updated.signed_protocol_attachment_id)

        self._select(tab, self.open_exam.id)
        self._run_dialog(tab, click="replace", pdf=self.replacement)
        row = self._row(tab.table, self.open_exam.id)
        self.assertEqual(tab.table.item(row, EXAM_COL_PROTOCOL).text(), EXAM_PROTOCOL_ATTACHED)
        replaced = test_exam_service.get_exam(self.open_exam.id)
        self.assertEqual(replaced.exam_result, before.exam_result)
        self.assertNotEqual(
            replaced.signed_protocol_attachment_id,
            updated.signed_protocol_attachment_id,
        )

        stored = exam_signed_protocol_service.validated_copy_path(self.open_exam.id)
        self._select(tab, self.open_exam.id)
        self._run_dialog(tab, click="remove", pdf=None)
        row = self._row(tab.table, self.open_exam.id)
        self.assertEqual(tab.table.item(row, EXAM_COL_PROTOCOL).text(), EXAM_PROTOCOL_MISSING)
        detached = test_exam_service.get_exam(self.open_exam.id)
        self.assertIsNone(detached.signed_protocol_attachment_id)
        self.assertEqual(detached.exam_result, before.exam_result)
        self.assertTrue(stored.is_file())
        prepared = self._row(tab.table, self.prepared.id)
        started = self._row(tab.table, self.started.id)
        self.assertEqual(tab.table.item(prepared, EXAM_COL_PROTOCOL).text(), EXAM_PROTOCOL_NOT_APPLICABLE)
        self.assertEqual(tab.table.item(started, EXAM_COL_PROTOCOL).text(), EXAM_PROTOCOL_NOT_APPLICABLE)
        tab.deleteLater()

    def test_protocol_column_fits_without_horizontal_scrollbar(self) -> None:
        table = TestExamTable()
        configure_table_columns(table, "test_exams")
        table.resize(1100, 420)
        table.show()
        self._app.processEvents()
        self.assertEqual(table.horizontalScrollBar().maximum(), 0)
        metrics = QFontMetrics(table.horizontalHeader().font())
        for column in range(table.columnCount()):
            if table.isColumnHidden(column):
                continue
            text = table.horizontalHeaderItem(column).text()
            self.assertLessEqual(
                metrics.horizontalAdvance(text) + 28,
                table.columnWidth(column),
                text,
            )
        table.close()

    def _run_dialog(self, tab: TestExamsTab, *, click: str, pdf: Path | None) -> None:
        def operate(dialog: TestExamDetailDialog):
            if click == "attach":
                dialog.protocol_attach_btn.click()
            elif click == "replace":
                dialog.protocol_replace_btn.click()
            else:
                dialog.protocol_remove_btn.click()
            return 1

        patches = [
            patch.object(TestExamDetailDialog, "exec", operate),
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
        ]
        if pdf is not None:
            patches.append(
                patch.object(
                    QFileDialog,
                    "getOpenFileName",
                    return_value=(str(pdf), "PDF (*.pdf)"),
                )
            )
        with patches[0], patches[1]:
            if len(patches) == 3:
                with patches[2]:
                    tab.open_selected()
            else:
                tab.open_selected()

    def _select(self, tab: TestExamsTab, exam_id: int) -> None:
        tab.table.selectRow(self._row(tab.table, exam_id))

    def _row(self, table: TestExamTable, exam_id: int) -> int:
        for row in range(table.rowCount()):
            item = table.item(row, EXAM_COL_ID)
            if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
                return row
        self.fail(f"zkouška {exam_id} není v tabulce")

    def _assert_protocol(
        self,
        table: TestExamTable,
        row: int,
        text: str,
        background: str,
        foreground: str | None,
    ) -> None:
        item = table.item(row, EXAM_COL_PROTOCOL)
        self.assertEqual(item.text(), text)
        self.assertEqual(item.background().color(), QColor(background))
        if foreground is None:
            self.assertNotEqual(item.foreground().color(), QColor(STATUS_DONE_TEXT))
        else:
            self.assertEqual(item.foreground().color(), QColor(foreground))

    def _definition(self, name: str) -> TestDefinition:
        test = TestDefinition(
            name=name,
            description="",
            active=True,
            uses_written=False,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
        )
        with get_session() as session:
            session.add(test)
            session.commit()
            session.refresh(test)
            session.expunge(test)
        return test

    def _exam(self, status: str, *, result: str | None) -> TestExam:
        exam = TestExam(
            employee_id=self.employee.id,
            test_definition_id=self.test.id,
            exam_date=date(2026, 6, 15),
            valid_until=date(2027, 6, 15),
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=self.employee.personal_number,
            employee_first_name=self.employee.first_name,
            employee_last_name=self.employee.last_name,
            employee_display_name=self.employee.display_name,
            employee_workplace_name=self.workplace.name,
            test_name=self.test.name,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_finished_at=datetime(2026, 6, 15, 9, 0) if status == EXAM_STATUS_COMPLETED else None,
            exam_result=result,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam


if __name__ == "__main__":
    unittest.main()
