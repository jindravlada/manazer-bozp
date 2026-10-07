"""TESTY-9a: automatické vyhodnocení písemné části."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QWidget,
)
from sqlalchemy import delete, inspect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-9a-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import engine, get_session
    from core.models.attachment import Attachment
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAM_COL_DATE,
        EXAM_COL_EMPLOYEE,
        EXAM_COL_EXAM_RESULT,
        EXAM_COL_STATUS,
        EXAM_COL_TEST,
        EXAM_COL_WRITTEN_RESULT,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_COMPLETED_LABEL,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_FINISHED_TEXT,
        WRITTEN_HANDOVER_TEXT,
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
    from moduly.testy.sluzby.written_exam_service import (
        FixedWrittenExamClock,
        WrittenExamClosed,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exam_table import TestExamTable
    from moduly.testy.ui.written_exam_window import WrittenExamWindow


_APP = QApplication.instance() or QApplication([])
_STARTED = datetime(2026, 10, 6, 14, 0, 0)
_ANSWER_CORRECT_STYLE = "color: #15803d; font-weight: 700;"
_ANSWER_ERROR_STYLE = "color: #b91c1c; font-weight: 700;"


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _text_answers(*, correct: str = "první") -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=correct == "první"),
        WrittenAnswerInput(text="druhá", is_correct=correct == "druhá"),
        WrittenAnswerInput(text="třetí", is_correct=correct == "třetí"),
    ]


def _employee(number: str, first: str, last: str):
    workplace = settings_service.save_workplace(name=f"Provoz {number}")
    role = responsibility_role_service.create_role(name=f"Mistr {number}")
    return test_employee_service.create_employee(
        personal_number=number,
        first_name=first,
        last_name=last,
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
    )


def _written_test(name: str, texts: list[str], *, allowed: int):
    topic = written_question_topic_service.create_topic(name=f"Okruh {name}")
    for text in texts:
        written_question_service.create_question(
            topic_id=topic.id,
            text=text,
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
    test = test_definition_service.create_test(
        name=name,
        uses_written=True,
        allowed_wrong_answers=allowed,
        seconds_per_question=60,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic.id, len(texts))],
    )
    return topic, test


def _prepare(employee_id: int, test_id: int):
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=test_id,
        exam_date=_STARTED.date(),
        rng=PrefixReverse(),
    )


def _visible_text(window) -> str:
    parts = []
    for label in window.findChildren(QLabel):
        if label.isVisible():
            parts.append(label.text())
    for button in window.findChildren(QPushButton):
        if button.isVisible():
            parts.append(button.text())
    return "\n".join(parts)


class WrittenEvaluationTestCase(unittest.TestCase):
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
            release = getattr(widget, "release_testing_lock", None)
            if callable(release):
                release()
            else:
                widget.close()
        QApplication.processEvents()

    def test_all_correct_answers_pass_and_ignore_later_bank_changes(self) -> None:
        topic, test = _written_test("Vše správně", ["První zadání", "Druhé zadání"], allowed=0)
        exam = self._started("91001", "Vše správně", test)
        questions = test_exam_service.get_written_questions(exam.id)
        source = questions[0]
        written_question_service.update_question(
            source.source_question_id,
            topic_id=topic.id,
            text="Jiná bankovní otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(correct="druhá"),
        )
        for question in questions:
            self._answer(exam.id, question, correct=True)
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertIsNone(fresh.written_result)
        self.assertIsNone(fresh.exam_result)
        self.assertEqual(fresh.status, EXAM_STATUS_STARTED)
        submitted_at = _STARTED + timedelta(seconds=8)
        self.assertEqual(
            written_exam_service.submit(exam.id, now=submitted_at),
            "submitted",
        )
        done = test_exam_service.get_exam(exam.id)
        assert done is not None
        self.assertEqual(done.written_question_count, 2)
        self.assertEqual(done.written_correct_count, 2)
        self.assertEqual(done.written_incorrect_count, 0)
        self.assertEqual(done.written_unanswered_count, 0)
        self.assertEqual(done.written_allowed_wrong_answers, 0)
        self.assertEqual(done.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(done.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(done.written_evaluated_at, submitted_at)
        self.assertEqual(done.status, EXAM_STATUS_COMPLETED)
        written_question_service.update_question(
            source.source_question_id,
            topic_id=topic.id,
            text="Ještě jiná bankovní otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(correct="třetí"),
        )
        test_definition_service.update_test(
            test.id,
            name=test.name,
            uses_written=True,
            allowed_wrong_answers=1,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
        )
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(stored.written_correct_count, 2)
        self.assertEqual(stored.written_allowed_wrong_answers, 0)
        self.assertEqual(stored.allowed_wrong_answers, 0)
        self._assert_closed(exam.id)

    def test_errors_on_the_limit_pass_and_above_the_limit_fail(self) -> None:
        _topic, on_limit = _written_test(
            "Na limitu",
            ["Limita A", "Limita B", "Limita C"],
            allowed=1,
        )
        passed = self._started("91002", "Na limitu", on_limit)
        passed_questions = test_exam_service.get_written_questions(passed.id)
        self._answer(passed.id, passed_questions[0], correct=False)
        self._answer(passed.id, passed_questions[1], correct=True)
        self._answer(passed.id, passed_questions[2], correct=True)
        written_exam_service.submit(passed.id, now=_STARTED + timedelta(seconds=5))
        on_limit_exam = test_exam_service.get_exam(passed.id)
        assert on_limit_exam is not None
        self.assertEqual(on_limit_exam.written_incorrect_count, 1)
        self.assertEqual(on_limit_exam.written_unanswered_count, 0)
        self.assertEqual(on_limit_exam.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(on_limit_exam.exam_result, WRITTEN_RESULT_PASSED)

        _topic_b, over = _written_test(
            "Nad limitem",
            ["Nad A", "Nad B", "Nad C"],
            allowed=1,
        )
        failed = self._started("91003", "Nad limitem", over)
        failed_questions = test_exam_service.get_written_questions(failed.id)
        self._answer(failed.id, failed_questions[0], correct=False)
        self._answer(failed.id, failed_questions[1], correct=False)
        self._answer(failed.id, failed_questions[2], correct=True)
        written_exam_service.submit(failed.id, now=_STARTED + timedelta(seconds=5))
        over_exam = test_exam_service.get_exam(failed.id)
        assert over_exam is not None
        self.assertEqual(over_exam.written_incorrect_count, 2)
        self.assertEqual(over_exam.written_correct_count, 1)
        self.assertEqual(over_exam.written_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(over_exam.exam_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(over_exam.status, EXAM_STATUS_COMPLETED)

    def test_unanswered_counts_as_an_error(self) -> None:
        _topic, test = _written_test("Ticho", ["Zodpovězená", "Tichá"], allowed=0)
        exam = self._started("91004", "Ticho", test)
        questions = test_exam_service.get_written_questions(exam.id)
        answered = next(question for question in questions if question.text == "Zodpovězená")
        self._answer(exam.id, answered, correct=True)
        written_exam_service.submit(exam.id, now=_STARTED + timedelta(seconds=5))
        done = test_exam_service.get_exam(exam.id)
        assert done is not None
        self.assertEqual(done.written_correct_count, 1)
        self.assertEqual(done.written_incorrect_count, 0)
        self.assertEqual(done.written_unanswered_count, 1)
        self.assertEqual(done.written_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(done.exam_result, WRITTEN_RESULT_FAILED)

    def test_wrong_and_unanswered_are_added(self) -> None:
        _topic, test = _written_test(
            "Součet",
            ["Dobrá", "Špatná", "Prázdná", "Ještě dobrá"],
            allowed=1,
        )
        exam = self._started("91005", "Součet", test)
        questions = {
            question.text: question
            for question in test_exam_service.get_written_questions(exam.id)
        }
        self._answer(exam.id, questions["Dobrá"], correct=True)
        self._answer(exam.id, questions["Špatná"], correct=False)
        self._answer(exam.id, questions["Ještě dobrá"], correct=True)
        written_exam_service.submit(exam.id, now=_STARTED + timedelta(seconds=5))
        done = test_exam_service.get_exam(exam.id)
        assert done is not None
        self.assertEqual(done.written_question_count, 4)
        self.assertEqual(done.written_correct_count, 2)
        self.assertEqual(done.written_incorrect_count, 1)
        self.assertEqual(done.written_unanswered_count, 1)
        self.assertEqual(done.written_allowed_wrong_answers, 1)
        self.assertEqual(done.written_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(done.exam_result, WRITTEN_RESULT_FAILED)

    def test_expiry_and_resume_expiry_store_the_result(self) -> None:
        _topic, test = _written_test("Vypršení", ["Jedna otázka"], allowed=0)
        exam = self._started("91006", "Vypršení", test)
        deadline = _STARTED + timedelta(seconds=60)
        self.assertEqual(written_exam_service.sync_deadline(exam.id, now=deadline), "expired")
        expired = test_exam_service.get_exam(exam.id)
        assert expired is not None
        self.assertEqual(expired.written_finish_reason, "expired")
        self.assertEqual(expired.written_unanswered_count, 1)
        self.assertEqual(expired.written_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(expired.exam_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(expired.written_evaluated_at, deadline)
        self.assertEqual(expired.status, EXAM_STATUS_COMPLETED)
        self._assert_closed(exam.id)

        _topic_b, resumed_test = _written_test("Obnova", ["Po pauze"], allowed=0)
        resumed = self._started("91007", "Obnova", resumed_test)
        question = test_exam_service.get_written_questions(resumed.id)[0]
        self._answer(resumed.id, question, correct=True)
        later = _STARTED + timedelta(seconds=90)
        self.assertEqual(written_exam_service.resume(resumed.id, now=later), "expired")
        finished = test_exam_service.get_exam(resumed.id)
        assert finished is not None
        self.assertEqual(finished.written_correct_count, 1)
        self.assertEqual(finished.written_unanswered_count, 0)
        self.assertEqual(finished.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(finished.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(finished.written_evaluated_at, later)
        self.assertEqual(finished.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(finished.written_started_at, _STARTED)

    def test_written_and_oral_exam_follows_the_written_part_only(self) -> None:
        topic = written_question_topic_service.create_topic(name="Písemný okruh 9a")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Písemná otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
        oral_topic = oral_question_topic_service.create_topic(name="Ústní okruh 9a")
        oral_question_service.create_question(
            topic_id=oral_topic.id,
            text="Ústní otázka beze stavu",
        )
        test = test_definition_service.create_test(
            name="Písemná a ústní",
            uses_written=True,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        exam = self._started("91008", "Kombinace", test)
        oral_before = [
            (question.id, question.position, question.text)
            for question in test_exam_service.get_oral_questions(exam.id)
        ]
        self.assertEqual(oral_before, [(oral_before[0][0], 1, "Ústní otázka beze stavu")])
        question = test_exam_service.get_written_questions(exam.id)[0]
        self._answer(exam.id, question, correct=False)
        written_exam_service.submit(exam.id, now=_STARTED + timedelta(seconds=4))
        done = test_exam_service.get_exam(exam.id)
        assert done is not None
        self.assertTrue(done.uses_oral)
        self.assertTrue(done.uses_written)
        self.assertEqual(done.written_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(done.exam_result, WRITTEN_RESULT_FAILED)
        self.assertEqual(done.status, EXAM_STATUS_COMPLETED)
        oral_after = [
            (question.id, question.position, question.text)
            for question in test_exam_service.get_oral_questions(exam.id)
        ]
        self.assertEqual(oral_after, oral_before)
        columns = {column["name"] for column in inspect(engine).get_columns("test_exams")}
        self.assertNotIn("oral_result", columns)
        self.assertNotIn("oral_status", columns)
        self.assertIn("written_result", columns)
        self.assertIn("written_evaluated_at", columns)

    def test_detail_distinguishes_correct_wrong_and_unanswered(self) -> None:
        _topic, test = _written_test(
            "Detail",
            ["Správná otázka", "Chybná otázka", "Tichá otázka"],
            allowed=0,
        )
        exam = self._started("91009", "Detail", test)
        questions = {
            question.text: question
            for question in test_exam_service.get_written_questions(exam.id)
        }
        self._answer(exam.id, questions["Správná otázka"], correct=True)
        self._answer(exam.id, questions["Chybná otázka"], correct=False)
        open_detail = self._watch(TestExamDetailDialog(exam_id=exam.id))
        self.assertFalse(open_detail.written_summary.isVisible())
        self.assertFalse(open_detail.written_summary.text())
        self.assertIsNone(open_detail.findChild(QLabel, "written-outcome-1"))

        written_exam_service.submit(exam.id, now=_STARTED + timedelta(seconds=6))
        detail = self._watch(TestExamDetailDialog(exam_id=exam.id))
        summary = detail.written_summary.text()
        self.assertIn("Počet otázek: 3", summary)
        self.assertIn("Správně: 1", summary)
        self.assertIn("Chybně: 1", summary)
        self.assertIn("Nezodpovězeno: 1", summary)
        self.assertIn("Povolené chyby: 0", summary)
        self.assertIn("Výsledek písemné části: Nevyhověl(a)", summary)
        self.assertIn("Výsledek zkoušky: Nevyhověl(a)", summary)
        self._assert_question(detail, questions["Správná otázka"], same=True)
        self._assert_question(detail, questions["Chybná otázka"], same=False)
        silent = questions["Tichá otázka"]
        missing = detail.findChild(QLabel, f"written-unanswered-{silent.position}")
        assert missing is not None
        self.assertEqual(missing.text(), "Nezodpovězeno — chyba")
        self.assertEqual(missing.styleSheet(), _ANSWER_ERROR_STYLE)
        silent_answers = test_exam_service.get_written_answers(silent.id)
        correct = next(answer for answer in silent_answers if answer.is_correct)
        correct_label = detail.findChild(
            QLabel,
            f"answer-{silent.position}-{correct.letter}",
        )
        assert correct_label is not None
        self.assertEqual(correct_label.styleSheet(), _ANSWER_CORRECT_STYLE)
        self.assertNotIn("chyba", correct_label.text())
        for answer in silent_answers:
            if answer.letter == correct.letter:
                continue
            plain = detail.findChild(QLabel, f"answer-{silent.position}-{answer.letter}")
            assert plain is not None
            self.assertEqual(plain.styleSheet(), "")
        self.assertIsNone(detail.findChild(QLabel, f"written-outcome-{silent.position}"))
        self.assertIsNone(detail.findChild(QLabel, f"written-employee-answer-{silent.position}"))
        self.assertIsNone(detail.findChild(QLabel, f"written-correct-answer-{silent.position}"))
        visible = "\n".join(label.text() for label in detail.findChildren(QLabel))
        self.assertNotIn("(správná)", visible)
        self.assertNotIn("Vyhodnocení:", visible)
        self.assertNotIn("Odpověď zaměstnance:", visible)
        self.assertNotIn("Správná odpověď:", visible)

        table = TestExamTable()
        prepared = _prepare(
            _employee("91010", "Eva", "Čekající").id,
            _written_test("Čeká", ["Ještě ne"], allowed=0)[1].id,
        )
        done = test_exam_service.get_exam(exam.id)
        table.load_exams([done, prepared])
        self.assertEqual(
            table.horizontalHeaderItem(EXAM_COL_WRITTEN_RESULT).text(),
            "Písemná část",
        )
        self.assertEqual(
            table.horizontalHeaderItem(EXAM_COL_EXAM_RESULT).text(),
            "Výsledek zkoušky",
        )
        self.assertEqual(table.horizontalHeaderItem(EXAM_COL_EMPLOYEE).text(), "Zaměstnanec")
        self.assertEqual(table.horizontalHeaderItem(EXAM_COL_TEST).text(), "Test")
        self.assertEqual(table.horizontalHeaderItem(EXAM_COL_DATE).text(), "Datum")
        self.assertEqual(table.horizontalHeaderItem(EXAM_COL_STATUS).text(), "Stav")
        failed_row = self._row(table, "Detail")
        waiting_row = self._row(table, "Čeká")
        self.assertEqual(table.item(failed_row, EXAM_COL_STATUS).text(), EXAM_STATUS_COMPLETED_LABEL)
        self.assertEqual(table.item(failed_row, EXAM_COL_WRITTEN_RESULT).text(), "Nevyhověl(a)")
        self.assertEqual(table.item(failed_row, EXAM_COL_EXAM_RESULT).text(), "Nevyhověl(a)")
        self.assertEqual(table.item(waiting_row, EXAM_COL_STATUS).text(), "Připraveno")
        self.assertEqual(table.item(waiting_row, EXAM_COL_WRITTEN_RESULT).text(), "")
        self.assertEqual(table.item(waiting_row, EXAM_COL_EXAM_RESULT).text(), "")

    def test_finished_screen_hides_the_result_from_the_employee(self) -> None:
        _topic, test = _written_test("Obrazovka", ["Otázka pro zaměstnance"], allowed=0)
        exam = self._started("91011", "Obrazovka", test)
        question = test_exam_service.get_written_questions(exam.id)[0]
        window = self._watch(
            WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        window.show_at(1600, 900)
        letter = self._correct_letter(question.id)
        radio = window.findChild(QRadioButton, f"written-exam-answer-{letter}")
        assert radio is not None
        radio.click()
        with patch(
            "moduly.testy.ui.written_exam_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.submit_test()
        QApplication.processEvents()
        visible = _visible_text(window)
        self.assertIn(WRITTEN_FINISHED_TEXT, visible)
        self.assertIn(WRITTEN_HANDOVER_TEXT, visible)
        self.assertNotIn("Vyhověl", visible)
        self.assertNotIn("Nevyhověl", visible)
        self.assertNotIn("Správně", visible)
        self.assertNotIn("Chybně", visible)
        self.assertNotIn("(správná)", visible)
        done = test_exam_service.get_exam(exam.id)
        assert done is not None
        self.assertEqual(done.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(done.status, EXAM_STATUS_COMPLETED)

    def test_historical_exam_without_result_is_left_blank(self) -> None:
        _topic, test = _written_test("Historie", ["Stará otázka"], allowed=0)
        employee = _employee("91012", "Oldřich", "Starý")
        exam = _prepare(employee.id, test.id)
        question_count = len(test_exam_service.get_written_questions(exam.id))
        with get_session() as session:
            row = session.get(TestExam, exam.id)
            assert row is not None
            row.status = EXAM_STATUS_COMPLETED
            row.written_started_at = _STARTED
            row.written_finished_at = _STARTED
            row.written_finish_reason = "submitted"
            row.written_result = None
            row.exam_result = None
            session.commit()
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.status, EXAM_STATUS_COMPLETED)
        self.assertIsNone(stored.written_result)
        self.assertIsNone(stored.exam_result)
        self.assertEqual(len(test_exam_service.get_written_questions(exam.id)), question_count)
        detail = self._watch(TestExamDetailDialog(exam_id=exam.id))
        self.assertFalse(detail.written_summary.isVisible())
        self.assertNotIn("Vyhověl", detail.summary.text())
        self.assertNotIn("Nevyhověl", detail.summary.text())
        table = TestExamTable()
        table.load_exams([stored])
        self.assertEqual(table.item(0, EXAM_COL_WRITTEN_RESULT).text(), "")
        self.assertEqual(table.item(0, EXAM_COL_EXAM_RESULT).text(), "")

    def _started(self, number: str, last: str, test):
        employee = _employee(number, "Jan", last)
        exam = _prepare(employee.id, test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        return exam

    def _answer(self, exam_id: int, question, *, correct: bool) -> None:
        chosen = self._option(question.id, correct=correct)
        written_exam_service.save_choice(
            exam_id,
            question.id,
            chosen.id,
            now=_STARTED + timedelta(seconds=2),
        )

    def _option(self, question_id: int, *, correct: bool):
        return next(
            answer
            for answer in test_exam_service.get_written_answers(question_id)
            if bool(answer.is_correct) is correct
        )

    def _correct_letter(self, question_id: int) -> str:
        return self._option(question_id, correct=True).letter

    def _assert_closed(self, exam_id: int) -> None:
        self.assertFalse(written_exam_service.can_start(exam_id))
        self.assertFalse(written_exam_service.can_continue(exam_id))
        self.assertEqual(written_exam_service.electronic_action(exam_id), "")
        with self.assertRaises(TestExamError):
            written_exam_service.start(exam_id, now=_STARTED + timedelta(minutes=5))
        with self.assertRaises(TestExamError):
            written_exam_service.resume(exam_id, now=_STARTED + timedelta(minutes=5))
        question = test_exam_service.get_written_questions(exam_id)[0]
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam_id,
                question.id,
                self._option(question.id, correct=True).id,
                now=_STARTED + timedelta(minutes=5),
            )

    def test_detail_highlights_image_answers_without_changing_pictures(self) -> None:
        from PIL import Image

        topic = written_question_topic_service.create_topic(name="Obrázky detail")
        folder = _TMP / "obrazky-detail"
        folder.mkdir(parents=True, exist_ok=True)
        colors = ((255, 0, 0), (0, 180, 0), (0, 0, 255))
        paths = []
        for index, color in enumerate(colors):
            path = folder / f"{index}.png"
            Image.new("RGB", (8, 8), color).save(path, "PNG")
            paths.append(path)
        written_question_service.create_question(
            topic_id=topic.id,
            text="Vyberte značku",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(paths[0])),
                WrittenAnswerInput(image_source_path=str(paths[1]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(paths[2])),
            ],
        )
        test = test_definition_service.create_test(
            name="Obrázkový detail",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = self._started("91013", "Obrázek", test)
        question = test_exam_service.get_written_questions(exam.id)[0]
        answers = test_exam_service.get_written_answers(question.id)
        wrong = next(answer for answer in answers if not answer.is_correct)
        correct = next(answer for answer in answers if answer.is_correct)
        before = {
            answer.letter: test_exam_service.resolve_snapshot_image(answer.image_stored_path).read_bytes()
            for answer in answers
        }
        written_exam_service.save_choice(
            exam.id,
            question.id,
            wrong.id,
            now=_STARTED + timedelta(seconds=2),
        )
        written_exam_service.submit(exam.id, now=_STARTED + timedelta(seconds=6))
        detail = self._watch(TestExamDetailDialog(exam_id=exam.id))
        wrong_label = detail.findChild(QLabel, f"answer-{question.position}-{wrong.letter}")
        correct_label = detail.findChild(
            QLabel,
            f"answer-{question.position}-{correct.letter}",
        )
        assert wrong_label is not None and correct_label is not None
        self.assertEqual(wrong_label.styleSheet(), _ANSWER_ERROR_STYLE)
        self.assertIn("— chyba", wrong_label.text())
        self.assertTrue(wrong_label.text().startswith(f"{wrong.letter})"))
        self.assertEqual(correct_label.styleSheet(), _ANSWER_CORRECT_STYLE)
        self.assertNotIn("chyba", correct_label.text())
        plain = next(
            answer
            for answer in answers
            if answer.letter not in {wrong.letter, correct.letter}
        )
        plain_label = detail.findChild(QLabel, f"answer-{question.position}-{plain.letter}")
        assert plain_label is not None
        self.assertEqual(plain_label.styleSheet(), "")
        self.assertNotIn("chyba", plain_label.text())
        for answer in answers:
            picture = detail.findChild(
                QLabel,
                f"answer-image-{question.position}-{answer.letter}",
            )
            assert picture is not None
            self.assertEqual(picture.styleSheet(), "")
            self.assertFalse(picture.pixmap().isNull())
            stored = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
            assert stored is not None
            self.assertEqual(stored.read_bytes(), before[answer.letter])
        joined = "\n".join(label.text() for label in detail.findChildren(QLabel))
        self.assertNotIn("(správná)", joined)
        self.assertNotIn("Vyhodnocení:", joined)

    def _assert_question(self, detail, question, *, same: bool) -> None:
        block = detail.findChild(QWidget, f"written-question-{question.position}")
        assert block is not None
        joined = "\n".join(label.text() for label in block.findChildren(QLabel))
        self.assertNotIn("Vyhodnocení:", joined)
        self.assertNotIn("(správná)", joined)
        self.assertNotIn("Odpověď zaměstnance:", joined)
        self.assertNotIn("Správná odpověď:", joined)
        answers = test_exam_service.get_written_answers(question.id)
        choice = next(
            item
            for item in test_exam_service.get_written_choices(detail.exam_id)
            if int(item.exam_question_id) == int(question.id)
        )
        selected = next(
            answer for answer in answers if int(answer.id) == int(choice.exam_answer_id)
        )
        correct = next(answer for answer in answers if answer.is_correct)
        chosen = detail.findChild(QLabel, f"answer-{question.position}-{selected.letter}")
        right = detail.findChild(QLabel, f"answer-{question.position}-{correct.letter}")
        assert chosen is not None and right is not None
        if same:
            self.assertTrue(selected.is_correct)
            self.assertEqual(chosen.styleSheet(), _ANSWER_CORRECT_STYLE)
            self.assertNotIn("chyba", chosen.text())
            self.assertNotIn("Vyhodnocení: Správně", joined)
        else:
            self.assertFalse(selected.is_correct)
            self.assertEqual(chosen.styleSheet(), _ANSWER_ERROR_STYLE)
            self.assertIn("— chyba", chosen.text())
            self.assertEqual(right.styleSheet(), _ANSWER_CORRECT_STYLE)
            self.assertNotIn("chyba", right.text())
        for answer in answers:
            if answer.letter in {selected.letter, correct.letter}:
                continue
            plain = detail.findChild(QLabel, f"answer-{question.position}-{answer.letter}")
            assert plain is not None
            self.assertEqual(plain.styleSheet(), "")

    def _row(self, table: TestExamTable, name: str) -> int:
        for row in range(table.rowCount()):
            item = table.item(row, EXAM_COL_TEST)
            if item is not None and item.text() == name:
                return row
        raise AssertionError(name)

    def _watch(self, widget):
        self._open.append(widget)
        return widget


if __name__ == "__main__":
    unittest.main()
