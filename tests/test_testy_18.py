"""TESTY-18: filtry evidence zkoušek."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-18-"))

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
    from core.services.storage_service import storage_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EXAM_COL_PROTOCOL,
        EXAM_COLUMN_HEADERS,
        EXAM_LIST_FILTER_ALL,
        EXAM_LIST_FILTER_ALL_TESTS,
        EXAM_LIST_FILTER_ALL_YEARS,
        EXAM_LIST_FILTER_RESULT_NONE,
        EXAM_LIST_FILTER_STATUS_RUNNING,
        EXAM_PROTOCOL_ATTACHED,
        EXAM_PROTOCOL_MISSING,
        EXAM_PROTOCOL_NOT_APPLICABLE,
        EXAM_STATUS_CANCELLED,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAM_STATUS_TECHNICAL_LABEL,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_RESULT_FAILED,
        WRITTEN_RESULT_PASSED,
        WRITTEN_RESULT_UNRATED_LABEL,
    )
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.sluzby.exam_signed_protocol_service import ENTITY_TYPE
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exams_tab import TestExamsTab


def _pdf(path: Path, marker: bytes) -> Path:
    path.write_bytes(b"%PDF-1.4\n" + marker + b"\n%%EOF\n")
    return path


def _wipe() -> None:
    protocol_dir = storage_service.attachments_dir / ENTITY_TYPE
    if protocol_dir.exists():
        shutil.rmtree(protocol_dir)
    with get_session() as session:
        session.execute(delete(TestExam))
        session.execute(delete(Attachment).where(Attachment.entity_type == ENTITY_TYPE))
        session.execute(delete(TestDefinition))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.commit()


class ExamListFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.files = Path(tempfile.mkdtemp(prefix="testy-18-src-"))
        token = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(name=f"Hala filtrů {token}")
        self.role = responsibility_role_service.create_role(name=f"Mistr filtrů {token}")
        self.bozp = self._definition("BOZP")
        self.fire = self._definition("Požární ochrana")
        self.crane = self._definition("Jeřáb")
        self.archived = self._definition("Archiv nepoužitý", active=False)
        self.prepared = self._exam(
            "1001",
            "Jan",
            "Novák",
            self.bozp,
            date(2026, 3, 1),
            EXAM_STATUS_PREPARED,
            None,
        )
        self.started = self._exam(
            "1002",
            "Petra",
            "Svobodová",
            self.bozp,
            date(2026, 4, 2),
            EXAM_STATUS_STARTED,
            None,
        )
        self.passed = self._exam(
            "1003",
            "Lucie",
            "Dvořáková",
            self.bozp,
            date(2025, 5, 3),
            EXAM_STATUS_COMPLETED,
            WRITTEN_RESULT_PASSED,
        )
        self.failed = self._exam(
            "1004",
            "Karel",
            "Černý",
            self.fire,
            date(2025, 6, 4),
            EXAM_STATUS_COMPLETED,
            WRITTEN_RESULT_FAILED,
        )
        self.attached = self._exam(
            "1005",
            "Eva",
            "Malá",
            self.fire,
            date(2024, 7, 5),
            EXAM_STATUS_COMPLETED,
            WRITTEN_RESULT_PASSED,
        )
        self.cancelled = self._exam(
            "1006",
            "Adam",
            "Horák",
            self.bozp,
            date(2026, 8, 6),
            EXAM_STATUS_CANCELLED,
            None,
        )
        from moduly.testy.sluzby.exam_signed_protocol_service import (
            exam_signed_protocol_service,
        )

        exam_signed_protocol_service.attach(
            self.attached.id,
            _pdf(self.files / "pripojeny.pdf", b"pripojeny"),
        )
        self.replacement = _pdf(self.files / "nahrada.pdf", b"nahrada")
        self.tab = TestExamsTab()

    def tearDown(self) -> None:
        self.tab.deleteLater()
        self._app.processEvents()
        shutil.rmtree(self.files, ignore_errors=True)

    def test_filter_row_sits_between_search_and_table(self) -> None:
        layout = self.tab.layout()
        self.assertIs(layout.itemAt(1).widget(), self.tab.text_filter)
        self.assertIs(layout.itemAt(2).widget(), self.tab.filter_row)
        self.assertIs(layout.itemAt(3).widget(), self.tab.table)
        self.assertEqual(self.tab.filter_row.findChildren(QPushButton), [])
        self.assertEqual(
            self._labels(self.tab.status_filter),
            [
                EXAM_LIST_FILTER_ALL,
                "Připraveno",
                EXAM_LIST_FILTER_STATUS_RUNNING,
                "Dokončeno",
                EXAM_STATUS_TECHNICAL_LABEL,
            ],
        )
        self.assertEqual(
            self._labels(self.tab.result_filter),
            [
                EXAM_LIST_FILTER_ALL,
                "Vyhověl(a)",
                "Nevyhověl(a)",
                WRITTEN_RESULT_UNRATED_LABEL,
                EXAM_LIST_FILTER_RESULT_NONE,
            ],
        )
        self.assertEqual(
            self._labels(self.tab.protocol_filter),
            [EXAM_LIST_FILTER_ALL, EXAM_PROTOCOL_ATTACHED, EXAM_PROTOCOL_MISSING],
        )
        self.assertEqual(
            self._labels(self.tab.test_filter),
            [EXAM_LIST_FILTER_ALL_TESTS, "BOZP", "Jeřáb", "Požární ochrana"],
        )
        self.assertNotIn("Archiv nepoužitý", self._labels(self.tab.test_filter))
        self.assertEqual(
            self._labels(self.tab.year_filter),
            [EXAM_LIST_FILTER_ALL_YEARS, "2026", "2025", "2024"],
        )
        headers = [
            self.tab.table.horizontalHeaderItem(column).text()
            for column in range(self.tab.table.columnCount())
        ]
        self.assertEqual(headers, EXAM_COLUMN_HEADERS)
        self.assertTrue(self.tab.table.isSortingEnabled())

    def test_each_filter_and_search_combine_with_the_counter(self) -> None:
        self.assertCountEqual(
            self._visible(),
            ["1001", "1002", "1003", "1004", "1005", "1006"],
        )
        self._assert_count(6, 6)

        self._choose(self.tab.status_filter, "Připraveno")
        self.assertEqual(self._visible(), ["1001"])
        self._choose(self.tab.status_filter, EXAM_LIST_FILTER_STATUS_RUNNING)
        self.assertEqual(self._visible(), ["1002"])
        self._choose(self.tab.status_filter, "Dokončeno")
        self.assertCountEqual(self._visible(), ["1003", "1004", "1005"])
        self._reset(self.tab.status_filter)

        self._choose(self.tab.result_filter, "Vyhověl(a)")
        self.assertCountEqual(self._visible(), ["1003", "1005"])
        self._choose(self.tab.result_filter, "Nevyhověl(a)")
        self.assertEqual(self._visible(), ["1004"])
        self._choose(self.tab.result_filter, EXAM_LIST_FILTER_RESULT_NONE)
        self.assertCountEqual(self._visible(), ["1001", "1002", "1006"])
        self._reset(self.tab.result_filter)

        self._choose(self.tab.protocol_filter, EXAM_PROTOCOL_ATTACHED)
        self.assertEqual(self._visible(), ["1005"])
        self._choose(self.tab.protocol_filter, EXAM_PROTOCOL_MISSING)
        self.assertCountEqual(self._visible(), ["1003", "1004"])
        for number in ("1001", "1002", "1006"):
            row = self._row(number)
            self.assertTrue(self.tab.table.isRowHidden(row))
            self.assertEqual(
                self.tab.table.item(row, EXAM_COL_PROTOCOL).text(),
                EXAM_PROTOCOL_NOT_APPLICABLE,
            )
        self._assert_count(2, 6)
        self._reset(self.tab.protocol_filter)

        self._choose(self.tab.year_filter, "2024")
        self.assertEqual(self._visible(), ["1005"])
        self._choose(self.tab.year_filter, "2026")
        self.assertCountEqual(self._visible(), ["1001", "1002", "1006"])
        self._reset(self.tab.year_filter)

        self._choose_data(self.tab.test_filter, self.bozp.id)
        self.assertCountEqual(self._visible(), ["1001", "1002", "1003", "1006"])
        self._choose_data(self.tab.test_filter, self.fire.id)
        self.assertCountEqual(self._visible(), ["1004", "1005"])
        self._choose_data(self.tab.test_filter, self.crane.id)
        self.assertEqual(self._visible(), [])
        self._assert_count(0, 6)
        self._reset(self.tab.test_filter)

        self.tab.text_filter.search_edit.setText("malá")
        self.assertEqual(self._visible(), ["1005"])
        self._assert_count(1, 6)
        self.tab.text_filter.search_edit.clear()

        self._choose_data(self.tab.test_filter, self.bozp.id)
        self._choose(self.tab.status_filter, "Dokončeno")
        self._choose(self.tab.result_filter, "Vyhověl(a)")
        self._choose(self.tab.protocol_filter, EXAM_PROTOCOL_MISSING)
        self._choose(self.tab.year_filter, "2025")
        self.tab.text_filter.search_edit.setText("dvořák")
        self.assertEqual(self._visible(), ["1003"])
        self._assert_count(1, 6)
        self.tab.text_filter.search_edit.setText("1004")
        self.assertEqual(self._visible(), [])
        self._assert_count(0, 6)

    def test_filters_and_rows_refresh_after_exam_changes(self) -> None:
        self._choose(self.tab.year_filter, "2026")
        self._choose(self.tab.result_filter, EXAM_LIST_FILTER_RESULT_NONE)
        self.assertIn("1001", self._visible())

        with get_session() as session:
            row = session.get(TestExam, self.prepared.id)
            row.status = EXAM_STATUS_COMPLETED
            row.exam_result = WRITTEN_RESULT_PASSED
            row.written_result = WRITTEN_RESULT_PASSED
            session.commit()
        self.tab.refresh()

        self.assertEqual(self.tab.year_filter.currentText(), "2026")
        self.assertEqual(self.tab.result_filter.currentText(), EXAM_LIST_FILTER_RESULT_NONE)
        self.assertNotIn("1001", self._visible())
        self._choose(self.tab.result_filter, "Vyhověl(a)")
        self._choose(self.tab.status_filter, "Dokončeno")
        self.assertIn("1001", self._visible())

        fresh = self._exam(
            "1007",
            "Iva",
            "Nová",
            self._definition("Nový test"),
            date(2023, 1, 9),
            EXAM_STATUS_PREPARED,
            None,
        )
        self.tab.refresh()
        self.assertEqual(self.tab.year_filter.currentText(), "2026")
        self.assertIn("2023", self._labels(self.tab.year_filter))
        self.assertIn("Nový test", self._labels(self.tab.test_filter))
        self.assertNotIn("1007", self._visible())
        self.assertEqual(self.tab.table.rowCount(), 7)
        self._reset(self.tab.year_filter)
        self._reset(self.tab.result_filter)
        self._reset(self.tab.status_filter)
        self.assertIn("1007", self._visible())
        self.assertEqual(fresh.employee_personal_number, "1007")

    def test_protocol_changes_keep_the_active_filter(self) -> None:
        self._choose(self.tab.protocol_filter, EXAM_PROTOCOL_MISSING)
        self.assertIn("1003", self._visible())
        self.assertNotIn("1001", self._visible())
        self._select("1003")
        self._run_dialog("attach", self.files / "dalsi.pdf")
        self.assertEqual(self.tab.protocol_filter.currentText(), EXAM_PROTOCOL_MISSING)
        self.assertNotIn("1003", self._visible())
        self.assertIn("1004", self._visible())
        self._assert_count(1, 6)

        self._choose(self.tab.protocol_filter, EXAM_PROTOCOL_ATTACHED)
        self.assertCountEqual(self._visible(), ["1003", "1005"])
        self._select("1003")
        self._run_dialog("replace", self.replacement)
        self.assertEqual(self.tab.protocol_filter.currentText(), EXAM_PROTOCOL_ATTACHED)
        self.assertIn("1003", self._visible())
        self.assertEqual(
            self.tab.table.item(self._row("1003"), EXAM_COL_PROTOCOL).text(),
            EXAM_PROTOCOL_ATTACHED,
        )

        self._select("1003")
        self._run_dialog("remove", None)
        self.assertNotIn("1003", self._visible())
        self.assertIn("1005", self._visible())
        self._choose(self.tab.protocol_filter, EXAM_PROTOCOL_MISSING)
        self.assertCountEqual(self._visible(), ["1003", "1004"])
        self.assertEqual(
            self.tab.table.item(self._row("1003"), EXAM_COL_PROTOCOL).text(),
            EXAM_PROTOCOL_MISSING,
        )

    def test_actions_stay_available_for_the_selected_exam(self) -> None:
        self._choose(self.tab.status_filter, "Připraveno")
        self.assertFalse(self.tab.detail_btn.isEnabled())
        self.assertTrue(self.tab.prepare_btn.isEnabled())
        self.assertTrue(self.tab.batch_btn.isEnabled())
        self._select("1001")
        self.assertTrue(self.tab.detail_btn.isEnabled())
        self.assertEqual(self.tab.table.selected_exam_id(), self.prepared.id)
        self.assertTrue(self.tab.prepare_btn.isEnabled())
        self.assertTrue(self.tab.batch_btn.isEnabled())
        self.tab.table.clearSelection()
        self.assertFalse(self.tab.detail_btn.isEnabled())
        self.assertFalse(self.tab.start_btn.isEnabled())
        self.assertFalse(self.tab.print_btn.isEnabled())
        self.assertFalse(self.tab.protocol_btn.isEnabled())
        self.assertFalse(self.tab.paper_btn.isEnabled())
        self.assertEqual(self.tab.batch_btn.objectName(), "exam-batch-paper-button")
        self.assertEqual(self.tab.print_btn.objectName(), "exam-print-paper-button")
        self.assertEqual(self.tab.protocol_btn.objectName(), "exam-print-protocol-button")
        self.assertEqual(self.tab.paper_btn.objectName(), "exam-enter-paper-button")

    def _definition(self, name: str, *, active: bool = True) -> TestDefinition:
        test = TestDefinition(
            name=name,
            description="",
            active=active,
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

    def _exam(
        self,
        number: str,
        first: str,
        last: str,
        test: TestDefinition,
        exam_date: date,
        status: str,
        result: str | None,
    ) -> TestExam:
        employee = test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=test.id,
            exam_date=exam_date,
            valid_until=date(exam_date.year + 1, exam_date.month, exam_date.day),
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=number,
            employee_first_name=first,
            employee_last_name=last,
            employee_display_name=employee.display_name,
            employee_workplace_name=self.workplace.name,
            test_name=test.name,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_finished_at=(
                datetime(exam_date.year, exam_date.month, exam_date.day, 9, 0)
                if status == EXAM_STATUS_COMPLETED
                else None
            ),
            exam_result=result,
            written_result=result,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam

    def _choose(self, combo, text: str) -> None:
        index = combo.findText(text)
        self.assertGreaterEqual(index, 0, text)
        combo.setCurrentIndex(index)

    def _choose_data(self, combo, data) -> None:
        index = combo.findData(data)
        self.assertGreaterEqual(index, 0, data)
        combo.setCurrentIndex(index)

    def _reset(self, combo) -> None:
        combo.setCurrentIndex(0)

    def _visible(self) -> list[str]:
        numbers = []
        for row in range(self.tab.table.rowCount()):
            if self.tab.table.isRowHidden(row):
                continue
            item = self.tab.table.item(row, 2)
            search = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
            numbers.append(search.split()[0])
        return numbers

    def _row(self, number: str) -> int:
        for row in range(self.tab.table.rowCount()):
            item = self.tab.table.item(row, 2)
            search = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
            if search.split()[0] == number:
                return row
        self.fail(f"zkouška {number} není v tabulce")

    def _select(self, number: str) -> None:
        self.tab.table.selectRow(self._row(number))

    def _assert_count(self, visible: int, total: int) -> None:
        self.assertEqual(
            self.tab.text_filter.count_label.text(),
            f"Zobrazeno: {visible} / {total}",
        )

    def _labels(self, combo) -> list[str]:
        return [combo.itemText(index) for index in range(combo.count())]

    def _run_dialog(self, click: str, pdf: Path | None) -> None:
        if pdf is not None and not pdf.exists():
            _pdf(pdf, b"dialog")

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
                    self.tab.open_selected()
            else:
                self.tab.open_selected()


if __name__ == "__main__":
    unittest.main()
