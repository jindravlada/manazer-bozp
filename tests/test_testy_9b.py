"""TESTY-9b: dodatečný neúspěch u ústní části."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-9b-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_TEXT,
        EXAM_ACTION_CLEAR_ORAL_FAILURE,
        EXAM_ACTION_RECORD_ORAL_FAILURE,
        EXAM_COL_EXAM_RESULT,
        EXAM_COL_TEST,
        EXAM_COL_WRITTEN_RESULT,
        EXAM_COLUMN_HEADERS,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_NONE,
        ORAL_FAILURE_CLEAR_CONFIRM,
        ORAL_FAILURE_CONFIRM,
        ORAL_PART_FAILED_LINE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_RESULT_FAILED,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.modely.oral_question import OralQuestion
    from moduly.testy.modely.oral_question_topic import OralQuestionTopic
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
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.oral_question_service import oral_question_service
    from moduly.testy.sluzby.oral_question_topic_service import (
        oral_question_topic_service,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_exam_service import written_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exam_table import TestExamTable


_APP = QApplication.instance() or QApplication([])
_STARTED = datetime(2026, 10, 6, 15, 0, 0)


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _employee(number: str):
    workplace = settings_service.save_workplace(name=f"Provoz {number}")
    role = responsibility_role_service.create_role(name=f"Mistr {number}")
    return test_employee_service.create_employee(
        personal_number=number,
        first_name="Jan",
        last_name=f"Zkoušený {number}",
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
    )


def _test(name: str, *, oral: bool, allowed: int = 0):
    topic = written_question_topic_service.create_topic(name=f"Písemný {name}")
    written_question_service.create_question(
        topic_id=topic.id,
        text=f"Písemná otázka {name}",
        answer_kind=ANSWER_KIND_TEXT,
        answers=[
            WrittenAnswerInput(text="první", is_correct=True),
            WrittenAnswerInput(text="druhá"),
            WrittenAnswerInput(text="třetí"),
        ],
    )
    oral_topics = []
    if oral:
        oral_topic = oral_question_topic_service.create_topic(name=f"Ústní {name}")
        oral_question_service.create_question(
            topic_id=oral_topic.id,
            text=f"Ústní otázka {name}",
        )
        oral_topics = [TestTopicQuota(oral_topic.id, 1)]
    return test_definition_service.create_test(
        name=name,
        uses_written=True,
        uses_oral=oral,
        allowed_wrong_answers=allowed,
        seconds_per_question=60,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic.id, 1)],
        oral_topics=oral_topics,
    )


def _prepare(employee_id: int, test_id: int):
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=test_id,
        exam_date=_STARTED.date(),
        rng=PrefixReverse(),
    )


def _written_fingerprint(exam_id: int):
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    questions = tuple(
        (question.id, question.text, question.position)
        for question in test_exam_service.get_written_questions(exam_id)
    )
    choices = tuple(
        (choice.exam_question_id, choice.exam_answer_id, choice.selected_letter)
        for choice in test_exam_service.get_written_choices(exam_id)
    )
    oral = tuple(
        (question.id, question.text, question.position)
        for question in test_exam_service.get_oral_questions(exam_id)
    )
    return (
        exam.status,
        exam.written_result,
        exam.written_question_count,
        exam.written_correct_count,
        exam.written_incorrect_count,
        exam.written_unanswered_count,
        exam.written_allowed_wrong_answers,
        exam.written_evaluated_at,
        exam.written_finish_reason,
        questions,
        choices,
        oral,
    )


class OralFailureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._open: list = []
        with get_session() as session:
            session.execute(delete(TestExamWrittenChoice))
            session.execute(delete(TestExamWrittenAnswer))
            session.execute(delete(TestExamWrittenQuestion))
            session.execute(delete(TestExamOralQuestion))
            session.execute(delete(TestExamExaminer))
            session.execute(delete(TestExam))
            session.execute(delete(TestDefinitionWrittenTopic))
            session.execute(delete(TestDefinitionOralTopic))
            session.execute(delete(TestDefinition))
            session.execute(delete(WrittenQuestionAnswer))
            session.execute(delete(WrittenQuestion))
            session.execute(delete(OralQuestion))
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(OralQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.execute(delete(Attachment))
            session.commit()

    def tearDown(self) -> None:
        for widget in self._open:
            widget.close()
        QApplication.processEvents()

    def test_record_and_clear_changes_only_the_exam_result(self) -> None:
        exam = self._finish("92001", "Úspěšná kombinace", oral=True, correct=True)
        before = _written_fingerprint(exam.id)
        dialog = self._detail(exam.id)
        self.assertEqual(dialog.oral_failure_button.text(), EXAM_ACTION_RECORD_ORAL_FAILURE)
        self.assertTrue(dialog.oral_failure_button.isVisible())
        self.assertNotIn("Ústní část", dialog.written_summary.text())
        self.assertNotIn("Nevyhodnoceno", dialog.written_summary.text())
        self.assertIn("Výsledek písemné části: Vyhověl", dialog.written_summary.text())
        self.assertIn("Výsledek zkoušky: Vyhověl", dialog.written_summary.text())

        with patch(
            "moduly.testy.ui.test_exam_detail_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            dialog.oral_failure_button.click()
        self.assertEqual(question.call_args.args[2], ORAL_FAILURE_CONFIRM)
        self.assertIsNone(test_exam_service.get_exam(exam.id).oral_failed_at)
        self.assertEqual(_written_fingerprint(exam.id), before)

        recorded_at = _STARTED + timedelta(minutes=30)
        with patch(
            "moduly.testy.ui.test_exam_detail_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "moduly.testy.sluzby.test_exam_service.datetime",
        ) as clock:
            clock.now.return_value = recorded_at
            dialog.oral_failure_button.click()
        recorded = test_exam_service.get_exam(exam.id)
        assert recorded is not None
        self.assertEqual(recorded.oral_failed_at, recorded_at)
        self.assertEqual(recorded.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(recorded.exam_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(recorded.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(_written_fingerprint(exam.id), before)
        self.assertIn(ORAL_PART_FAILED_LINE, dialog.written_summary.text())
        self.assertNotIn("Ústní část: Vyhověl", dialog.written_summary.text())
        self.assertNotIn("Nevyhodnoceno", dialog.written_summary.text())
        self.assertIn("Výsledek písemné části: Vyhověl", dialog.written_summary.text())
        self.assertIn("Výsledek zkoušky: Nevyhověl", dialog.written_summary.text())
        self.assertEqual(dialog.oral_failure_button.text(), EXAM_ACTION_CLEAR_ORAL_FAILURE)
        self._assert_table(recorded, "Vyhověl", "Nevyhověl")
        with self.assertRaises(TestExamError) as again:
            test_exam_service.record_oral_failure(exam.id, now=recorded_at)
        self.assertIn("už je zaznamenán", str(again.exception))
        self.assertEqual(_written_fingerprint(exam.id), before)

        with patch(
            "moduly.testy.ui.test_exam_detail_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as clear:
            dialog.oral_failure_button.click()
        self.assertIn("opravu evidovaného údaje", clear.call_args.args[2])
        self.assertEqual(clear.call_args.args[2], ORAL_FAILURE_CLEAR_CONFIRM)
        cleared = test_exam_service.get_exam(exam.id)
        assert cleared is not None
        self.assertIsNone(cleared.oral_failed_at)
        self.assertEqual(cleared.exam_result, cleared.written_result)
        self.assertEqual(cleared.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(cleared.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(_written_fingerprint(exam.id), before)
        self.assertNotIn("Ústní část", dialog.written_summary.text())
        self.assertIn("Výsledek zkoušky: Vyhověl", dialog.written_summary.text())
        self.assertEqual(dialog.oral_failure_button.text(), EXAM_ACTION_RECORD_ORAL_FAILURE)
        self._assert_table(cleared, "Vyhověl", "Vyhověl")

    def test_ineligible_exams_hide_the_action_and_service_rejects_it(self) -> None:
        written_only = self._finish("92002", "Jen písemná", oral=False, correct=True)
        dialog = self._detail(written_only.id)
        self.assertFalse(dialog.oral_failure_button.isVisible())
        with self.assertRaises(TestExamError) as no_oral:
            test_exam_service.record_oral_failure(written_only.id, now=_STARTED)
        self.assertIn("nemá ústní část", str(no_oral.exception))
        self.assertIsNone(test_exam_service.get_exam(written_only.id).oral_failed_at)
        self.assertEqual(
            test_exam_service.get_exam(written_only.id).exam_result,
            WRITTEN_RESULT_PASSED,
        )

        employee = _employee("92003")
        prepared = _prepare(employee.id, _test("Nedokončená", oral=True).id)
        self.assertEqual(prepared.status, EXAM_STATUS_PREPARED)
        open_dialog = self._detail(prepared.id)
        self.assertFalse(open_dialog.oral_failure_button.isVisible())
        with self.assertRaises(TestExamError) as not_done:
            test_exam_service.record_oral_failure(prepared.id, now=_STARTED)
        self.assertIn("dokončené zkoušky", str(not_done.exception))

        started = self._finish("92004", "Rozepsaná", oral=True, correct=True, submit=False)
        self.assertEqual(test_exam_service.get_exam(started.id).status, EXAM_STATUS_STARTED)
        started_dialog = self._detail(started.id)
        self.assertFalse(started_dialog.oral_failure_button.isVisible())
        with self.assertRaises(TestExamError) as running:
            test_exam_service.record_oral_failure(started.id, now=_STARTED)
        self.assertIn("dokončené zkoušky", str(running.exception))

        failed = self._finish("92005", "Písemně neúspěšná", oral=True, correct=False)
        failed_dialog = self._detail(failed.id)
        self.assertFalse(failed_dialog.oral_failure_button.isVisible())
        self.assertNotIn("Ústní část", failed_dialog.written_summary.text())
        with self.assertRaises(TestExamError) as written_failed:
            test_exam_service.record_oral_failure(failed.id, now=_STARTED)
        self.assertIn("písemná část vyhověla", str(written_failed.exception))
        self.assertEqual(
            test_exam_service.get_exam(failed.id).exam_result,
            WRITTEN_RESULT_FAILED,
        )
        self.assertEqual(
            test_exam_service.get_exam(failed.id).written_result,
            WRITTEN_RESULT_FAILED,
        )

        passed = self._finish("92006", "Bez zápisu", oral=True, correct=True)
        with self.assertRaises(TestExamError) as missing:
            test_exam_service.clear_oral_failure(passed.id)
        self.assertIn("není zaznamenán", str(missing.exception))
        self.assertEqual(
            test_exam_service.get_exam(passed.id).exam_result,
            WRITTEN_RESULT_PASSED,
        )

    def _finish(self, number: str, name: str, *, oral: bool, correct: bool, submit: bool = True):
        employee = _employee(number)
        exam = _prepare(employee.id, _test(name, oral=oral).id)
        written_exam_service.start(exam.id, now=_STARTED)
        if not submit:
            return exam
        question = test_exam_service.get_written_questions(exam.id)[0]
        answer = next(
            item
            for item in test_exam_service.get_written_answers(question.id)
            if bool(item.is_correct) is correct
        )
        written_exam_service.save_choice(
            exam.id,
            question.id,
            answer.id,
            now=_STARTED + timedelta(seconds=2),
        )
        written_exam_service.submit(exam.id, now=_STARTED + timedelta(seconds=5))
        return exam

    def _detail(self, exam_id: int) -> TestExamDetailDialog:
        dialog = TestExamDetailDialog(exam_id=exam_id)
        self._open.append(dialog)
        dialog.show()
        QApplication.processEvents()
        return dialog

    def _assert_table(self, exam, written: str, overall: str) -> None:
        self.assertNotIn("Ústní část", EXAM_COLUMN_HEADERS)
        table = TestExamTable()
        table.load_exams([exam])
        self.assertEqual(table.columnCount(), len(EXAM_COLUMN_HEADERS))
        self.assertEqual(table.item(0, EXAM_COL_TEST).text(), exam.test_name)
        self.assertEqual(table.item(0, EXAM_COL_WRITTEN_RESULT).text(), written)
        self.assertEqual(table.item(0, EXAM_COL_EXAM_RESULT).text(), overall)



if __name__ == "__main__":
    unittest.main()
