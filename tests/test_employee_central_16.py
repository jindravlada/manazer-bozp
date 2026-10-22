"""EMPLOYEE-CENTRAL-16: v Testech už není druhá správa zaměstnanců."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-16-"))
_TODAY = date(2026, 10, 22)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QLabel, QPushButton
    from sqlalchemy import delete, func, select

    from core.dashboard.widget_exam_retraining import ExamRetrainingWidget
    from core.database.session import get_session
    from moduly.nastaveni.modely.test_employee_central_link import (
        TestEmployeeCentralLink,
    )
    from moduly.nastaveni.modely.thp_worker import ThpWorker
    from moduly.nastaveni.modely.thp_worker_role import ThpWorkerRole
    from moduly.nastaveni.sluzby.employee_central_link_service import (
        employee_central_link_service,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.ui.employee_link_dialog import EmployeeLinkDialog
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.testy.constants import (
        ACTION_NEW,
        AGENDA_EMPLOYEES,
        AGENDA_EXAM_VALIDITY,
        AGENDA_EXAMS,
        ANSWER_KIND_TEXT,
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EMPLOYEE_SOURCE_THP_WORKER,
        EXAM_PROTOCOL_ATTACHED,
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
    from moduly.testy.modely.test_definition_written_topic import (
        TestDefinitionWrittenTopic,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
    from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.exam_protocol_layout import protocol_people
    from moduly.testy.sluzby.exam_signed_protocol_service import (
        exam_signed_protocol_service,
    )
    from moduly.testy.sluzby.exam_validity_service import exam_validity_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from tests.historical_test_employee import (
        seed_historical_test_employee,
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
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exam_prepare_dialog import TestExamPrepareDialog
    from moduly.testy.ui.testy_page import TestyPage


def _wipe() -> None:
    with get_session() as session:
        session.execute(delete(TestExamWrittenChoice))
        session.execute(delete(TestExamWrittenAnswer))
        session.execute(delete(TestExamWrittenQuestion))
        session.execute(delete(TestExamOralQuestion))
        session.execute(delete(TestExamExaminer))
        session.execute(delete(TestExam))
        session.execute(delete(TestExamValidityTracking))
        session.execute(delete(TestDefinitionWrittenTopic))
        session.execute(delete(TestDefinitionOralTopic))
        session.execute(delete(TestDefinition))
        session.execute(delete(WrittenQuestionAnswer))
        session.execute(delete(WrittenQuestion))
        session.execute(delete(WrittenQuestionTopic))
        session.execute(delete(TestEmployeeCentralLink))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.execute(delete(ThpWorkerRole))
        session.execute(delete(ThpWorker))
        session.commit()


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _visible_tabs(page: TestyPage) -> list[str]:
    return [
        page.tabs.tabText(index)
        for index in range(page.tabs.count())
        if page.tabs.isTabVisible(index)
    ]


def _row_containing(table, text: str) -> int:
    for row in range(table.rowCount()):
        for column in range(table.columnCount()):
            item = table.item(row, column)
            if item is not None and item.text() == text:
                return row
    raise AssertionError(text)


class EmployeeCentral16TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.marker = uuid.uuid4().hex[:8]
        self.widgets = []
        self.workplace = settings_service.save_workplace(name=f"Hala {self.marker}")
        self.role = responsibility_role_service.create_role(name=f"Mistr {self.marker}")

    def tearDown(self) -> None:
        for widget in self.widgets:
            widget.close()

    def test_employees_tab_is_hidden_and_settings_keep_the_registry(self) -> None:
        historical = self._historical_employee("h16", "Jan", "Historický")
        before = _count(TestEmployee)
        page = self._keep(TestyPage())
        visible = _visible_tabs(page)
        self.assertNotIn(AGENDA_EMPLOYEES, visible)
        self.assertIn(AGENDA_EXAMS, visible)
        self.assertIn(AGENDA_EXAM_VALIDITY, visible)
        self.assertFalse(hasattr(page, "employees_tab"))
        self.assertEqual(page.tabs.count(), len(visible))
        self.assertEqual(page.tabs.tabText(page.tabs.currentIndex()), visible[0])
        visible_buttons = []
        for button in page.findChildren(QPushButton):
            index = page.tabs.indexOf(button)
            parent = button.parentWidget()
            while parent is not None and index < 0:
                index = page.tabs.indexOf(parent)
                parent = parent.parentWidget()
            if index >= 0 and page.tabs.isTabVisible(index):
                visible_buttons.append(button.text())
        self.assertNotIn(ACTION_NEW, visible_buttons)
        self.assertEqual(_count(TestEmployee), before)
        self.assertEqual(
            test_employee_service.get_employee(historical.id).personal_number,
            historical.personal_number,
        )

        settings = self._keep(NastaveniPage())
        settings_tabs = [
            settings.tabs.tabText(index)
            for index in range(settings.tabs.count())
            if settings.tabs.isTabVisible(index)
        ]
        self.assertIn("Zaměstnanci", settings_tabs)
        self.assertEqual(settings.worker_link_button.text(), "Propojit s Testy")

    def test_exam_screens_do_not_create_test_employees(self) -> None:
        worker = self._worker("Vladimír", "Jindra", personal_number=f"c{self.marker}")
        definition = self._written_test()
        before_employees = _count(TestEmployee)
        before_ids = {
            int(employee.id)
            for employee in test_employee_service.list_employees(include_inactive=True)
        }
        page = self._keep(TestyPage())
        self._keep(TestExamPrepareDialog())
        self._keep(PaperBatchDialog())
        created = test_exam_service.prepare_exam(
            employee_id=worker.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
            test_id=definition.id,
            exam_date=_TODAY,
            examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
        )
        batch = test_exam_service.prepare_paper_batch(
            employee_ids=[worker.id],
            test_id=definition.id,
            exam_date=_TODAY,
        )
        self.assertEqual(created.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(created.employee_id, worker.id)
        self.assertEqual(batch[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(_count(TestEmployee), before_employees)
        self.assertEqual(
            {
                int(employee.id)
                for employee in test_employee_service.list_employees(include_inactive=True)
            },
            before_ids,
        )
        self.assertEqual(_count(TestEmployeeCentralLink), 0)
        page.exams_tab.refresh()
        names = []
        for row in range(page.exams_tab.table.rowCount()):
            for column in range(page.exams_tab.table.columnCount()):
                item = page.exams_tab.table.item(row, column)
                if item is not None:
                    names.append(item.text())
        self.assertTrue(any("Jindra" in text for text in names))

    def test_history_validity_dashboard_and_manual_link_stay(self) -> None:
        historical = self._historical_employee(f"h{self.marker}", "Jan", "Historický")
        unlinked = self._historical_employee(f"u{self.marker}", "Eva", "Samostatná")
        same_number = f"s{self.marker}"
        hinted_employee = self._historical_employee(same_number, "Petr", "Nápověda")
        hinted_worker = self._worker("Petr", "Nápověda", personal_number=same_number)
        worker = self._worker("Jan", "Historický", personal_number=f"c{self.marker}")
        definition = self._written_test()
        historical_exam = test_exam_service.prepare_exam(
            employee_id=historical.id,
            test_id=definition.id,
            exam_date=_TODAY,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        self._complete(historical_exam.id)
        stored = test_exam_service.get_exam(historical_exam.id)
        snapshot = (
            stored.employee_source,
            stored.employee_id,
            stored.employee_display_name,
            stored.employee_personal_number,
            stored.employee_roles_text,
            stored.status,
            stored.exam_result,
        )
        question = test_exam_service.get_written_questions(stored.id)[0]
        answer_text = test_exam_service.get_written_answers(question.id)[0].text
        protocol_path = _TMP / f"protokol-{self.marker}.pdf"
        protocol_path.write_bytes(b"%PDF-1.4\ncentral-16\n%%EOF\n")
        attachment_id = exam_signed_protocol_service.attach(stored.id, protocol_path)
        people = protocol_people(test_exam_service.get_exam(stored.id), [])
        self.assertEqual(people[0][1], stored.employee_display_name)

        test_exam_service.prepare_exam(
            employee_id=unlinked.id,
            test_id=definition.id,
            exam_date=_TODAY,
            employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
            examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        )
        employee_central_link_service.link_existing(
            test_employee_id=historical.id,
            thp_worker_id=worker.id,
        )
        central_exam = test_exam_service.prepare_exam(
            employee_id=worker.id,
            employee_source=EMPLOYEE_SOURCE_THP_WORKER,
            test_id=definition.id,
            exam_date=_TODAY,
            examiner_source=EMPLOYEE_SOURCE_THP_WORKER,
        )

        detail = self._keep(TestExamDetailDialog(exam_id=stored.id))
        self.assertIn(stored.employee_display_name, detail.summary.text())
        self.assertIn(stored.employee_personal_number, detail.summary.text())
        self.assertEqual(detail.protocol_status.text(), EXAM_PROTOCOL_ATTACHED)
        question_labels = [label.text() for label in detail.findChildren(QLabel)]
        self.assertTrue(any(question.text in text for text in question_labels))
        self.assertTrue(any(answer_text in text for text in question_labels))

        page = self._keep(TestyPage())
        page.exams_tab.refresh()
        page.validity_tab.today_override = _TODAY
        page.validity_tab.refresh()
        rows = [
            row
            for row in exam_validity_service.list_rows(today=_TODAY)
            if row.test_definition_id == definition.id
        ]
        linked_rows = [
            row for row in rows if row.personal_number == worker.personal_number
        ]
        self.assertEqual(len(linked_rows), 1)
        self.assertEqual(linked_rows[0].employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertEqual(linked_rows[0].employee_id, worker.id)
        self.assertTrue(linked_rows[0].tracked)
        self.assertNotIn(historical.personal_number, {row.personal_number for row in rows})
        unlinked_rows = [
            row for row in rows if row.personal_number == unlinked.personal_number
        ]
        self.assertEqual(len(unlinked_rows), 1)
        self.assertEqual(unlinked_rows[0].employee_source, EMPLOYEE_SOURCE_TEST_EMPLOYEE)

        dashboard = self._keep(ExamRetrainingWidget())
        dashboard.today_override = _TODAY
        dashboard.refresh()
        self.assertEqual(dashboard.valid_card.value_label.text(), "1")
        self.assertGreaterEqual(int(dashboard.unfinished_card.value_label.text()), 2)

        links_before = _count(TestEmployeeCentralLink)
        settings = self._keep(NastaveniPage())
        settings.worker_table.selectRow(
            _row_containing(settings.worker_table, hinted_worker.last_name)
        )
        settings.update_worker_buttons()
        self.assertTrue(settings.worker_link_button.isEnabled())
        dialog = self._keep(EmployeeLinkDialog(worker_id=hinted_worker.id))
        self.assertIn("Stejné osobní číslo", dialog.hint_label.text())
        self.assertIn("samo neprovede", dialog.hint_label.text())
        self.assertEqual(
            _row_containing(dialog.employee_table, hinted_employee.personal_number) >= 0,
            True,
        )
        dialog.reject()
        self.assertEqual(_count(TestEmployeeCentralLink), links_before)
        self.assertIsNotNone(test_employee_service.get_employee(hinted_employee.id))
        self.assertIsNotNone(test_employee_service.get_employee(unlinked.id))

        fresh = test_exam_service.get_exam(stored.id)
        self.assertEqual(
            (
                fresh.employee_source,
                fresh.employee_id,
                fresh.employee_display_name,
                fresh.employee_personal_number,
                fresh.employee_roles_text,
                fresh.status,
                fresh.exam_result,
            ),
            snapshot,
        )
        self.assertEqual(fresh.signed_protocol_attachment_id, attachment_id)
        self.assertEqual(central_exam.employee_source, EMPLOYEE_SOURCE_THP_WORKER)
        self.assertNotEqual(central_exam.id, stored.id)

    def _keep(self, widget):
        self.widgets.append(widget)
        return widget

    def _historical_employee(self, number: str, first: str, last: str):
        return seed_historical_test_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )

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
