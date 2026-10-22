"""EMPLOYEE-CENTRAL-19: modul Testy už nezapisuje do test_employees."""

from __future__ import annotations

import html
import importlib
import os
import re
import tempfile
import unittest
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-19-"))
_TODAY = date(2026, 10, 22)
_ROOT = Path(__file__).resolve().parents[1]

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication
    from sqlalchemy import func, select

    from core.dashboard.widget_exam_retraining import ExamRetrainingWidget
    from core.database.session import get_session
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.ui.employee_link_dialog import EmployeeLinkDialog
    from moduly.testy.constants import (
        AGENDA_EXAM_VALIDITY,
        AGENDA_EXAMS,
        AGENDA_ORAL_QUESTIONS,
        AGENDA_ORAL_TOPICS,
        AGENDA_QUESTIONS,
        AGENDA_TESTS,
        AGENDA_WRITTEN_TOPICS,
        ANSWER_KIND_TEXT,
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EMPLOYEE_SOURCE_THP_WORKER,
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
    )
    from moduly.testy.sluzby.exam_validity_service import exam_validity_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.paper_batch_dialog import PaperBatchDialog
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog
    from moduly.testy.ui.testy_page import TestyPage
    from tests.historical_test_employee import seed_historical_test_employee


_VISIBLE_TABS = [
    AGENDA_WRITTEN_TOPICS,
    AGENDA_QUESTIONS,
    AGENDA_ORAL_TOPICS,
    AGENDA_ORAL_QUESTIONS,
    AGENDA_TESTS,
    AGENDA_EXAMS,
    AGENDA_EXAM_VALIDITY,
]
_WRITE_MARKERS = (
    "INSERT INTO test_employees",
    "UPDATE test_employees",
    "DELETE FROM test_employees",
    "INSERT INTO test_employee_roles",
    "UPDATE test_employee_roles",
    "DELETE FROM test_employee_roles",
)


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _plain_odt(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        text = archive.read("content.xml").decode("utf-8")
    return html.unescape(re.sub(r"<[^>]+>", "", text))


class EmployeeCentral19TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.widgets = []
        self.workplace = settings_service.save_workplace(name=f"Hala {self.marker}")
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")

    def tearDown(self) -> None:
        for widget in self.widgets:
            widget.close()

    def test_module_opens_remaining_tabs_only(self) -> None:
        page = self._keep(TestyPage())
        labels = [page.tabs.tabText(index) for index in range(page.tabs.count())]
        self.assertEqual(labels, _VISIBLE_TABS)
        self.assertNotIn("Zaměstnanci", labels)
        self.assertFalse(hasattr(page, "employees_tab"))
        for index, label in enumerate(labels):
            page.tabs.setCurrentIndex(index)
            self.assertEqual(page.tabs.tabText(page.tabs.currentIndex()), label)
            self.assertIsNotNone(page.tabs.widget(index))

    def test_prepare_history_protocol_validity_dashboard_and_link(self) -> None:
        historical = seed_historical_test_employee(
            personal_number=f"h{self.marker}",
            first_name="Jan",
            last_name="Historický",
            title_before="Ing.",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        before_employees = _count(TestEmployee)
        identity = (
            historical.personal_number,
            historical.first_name,
            historical.last_name,
            historical.title_before,
        )
        definition = self._written_test()
        historical_exam = test_exam_service.prepare_exam(
            employee_id=historical.id,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            test_id=definition.id,
            exam_date=_TODAY,
        )
        self._complete(historical_exam.id)
        stored = test_exam_service.get_exam(historical_exam.id)
        self.assertEqual(stored.employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)
        self.assertEqual(stored.employee_display_name, "Ing. Jan Historický")
        protocol = exam_protocol_export_service.export(
            stored.id,
            _TMP / f"protokol-{self.marker}.odt",
        )
        self.assertIn("Ing. Jan Historický", _plain_odt(protocol))

        worker = self._worker("Vladimír", "Jindra", personal_number=f"c{self.marker}")
        page = self._keep(TestyPage())
        prepare = self._keep(TestExamPrepareDialog())
        batch_dialog = self._keep(PaperBatchDialog())
        self.assertEqual(prepare.get_data()["employee_source"], EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(prepare.get_data()["examiner_source"], EMPLOYEE_SOURCE_THP_WORKER)
        created = test_exam_service.prepare_exam(
            employee_id=worker.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
            examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
            test_id=definition.id,
            exam_date=_TODAY,
        )
        batch = test_exam_service.prepare_paper_batch(
            employee_ids=[worker.id],
            test_id=definition.id,
            exam_date=_TODAY,
        )
        self.assertEqual(created.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(batch[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(batch[0].employee_last_name, "Jindra")
        self.assertEqual(_count(TestEmployee), before_employees)

        page.validity_tab.today_override = _TODAY
        page.show_validity_tab()
        rows = [
            row
            for row in exam_validity_service.list_rows(today=_TODAY)
            if row.employee_id == historical.id
            and row.employee_source == EMPLOYEE_SOURCE_TEST_EMPLOYEE
        ]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].personal_number, historical.personal_number)

        dashboard = self._keep(ExamRetrainingWidget())
        dashboard.today_override = _TODAY
        dashboard.refresh()
        self.assertGreaterEqual(int(dashboard.valid_card.value_label.text()), 1)

        dialog = self._keep(EmployeeLinkDialog(worker_id=worker.id))
        numbers = [
            dialog.employee_table.item(row, column).text()
            for row in range(dialog.employee_table.rowCount())
            for column in range(dialog.employee_table.columnCount())
            if dialog.employee_table.item(row, column) is not None
        ]
        self.assertIn(historical.personal_number, numbers)
        dialog.reject()
        employee_central_link_service.link_existing(
            test_employee_id=historical.id,
            thp_worker_id=worker.id,
        )
        loaded = test_employee_service.get_employee(historical.id)
        assert loaded is not None
        self.assertEqual(
            (
                loaded.personal_number,
                loaded.first_name,
                loaded.last_name,
                loaded.title_before,
            ),
            identity,
        )
        fresh = test_exam_service.get_exam(stored.id)
        self.assertEqual(fresh.employee_display_name, stored.employee_display_name)
        self.assertEqual(fresh.employee_personal_number, stored.employee_personal_number)

    def test_production_code_has_no_test_employee_write(self) -> None:
        hits = []
        for folder in ("moduly", "core"):
            for path in (_ROOT / folder).rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                relative = path.relative_to(_ROOT).as_posix()
                for marker in _WRITE_MARKERS:
                    if marker in text:
                        hits.append(f"{relative}: {marker}")
                if "TestEmployee(" in text and "class TestEmployee(" not in text:
                    hits.append(f"{relative}: TestEmployee(")
        self.assertEqual(hits, [])

    def _keep(self, widget):
        self.widgets.append(widget)
        return widget

    def _worker(self, first: str, last: str, **extra):
        data = {
            "first_name": first,
            "last_name": last,
            "workplace_id": self.workplace.id,
            "responsibility_role_ids": [self.role.id],
            "active": True,
            "is_thp": False,
            "may_examine": False,
            "performs_controls": False,
            "personal_number": "",
        }
        data.update(extra)
        return settings_service.save_worker(**data)

    def _written_test(self):
        topic = written_question_topic_service.create_topic(name=f"Okruh {self.marker}")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Jaký je postup?",
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="první", is_correct=True),
                WrittenAnswerInput(text="druhá"),
                WrittenAnswerInput(text="třetí"),
            ],
        )
        return test_definition_service.create_test(
            name=f"Test {self.marker}",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )

    def _complete(self, exam_id: int) -> None:
        with get_session() as session:
            stored = session.get(TestExam, exam_id)
            stored.status = EXAM_STATUS_COMPLETED
            stored.exam_result = WRITTEN_RESULT_PASSED
            stored.written_result = WRITTEN_RESULT_PASSED
            stored.written_mode = WRITTEN_MODE_ELECTRONIC
            stored.valid_until = date(2027, 10, 22)
            stored.written_finished_at = datetime(2026, 10, 22, 9, 0)
            session.commit()
