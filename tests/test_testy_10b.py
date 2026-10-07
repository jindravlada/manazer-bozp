"""TESTY-10b: zadání a vyhodnocení papírového písemného testu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QMessageBox
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-10b-"))
_LATE = datetime(2099, 1, 1, 8, 0, 0)

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
        ELECTRONIC_BLOCKS_PAPER,
        EXAM_ACTION_ENTER_PAPER,
        EXAM_ACTION_RECORD_ORAL_FAILURE,
        EXAM_COL_EXAM_RESULT,
        EXAM_COL_ID,
        EXAM_COL_STATUS,
        EXAM_COL_WRITTEN_RESULT,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_COMPLETED_LABEL,
        EXAM_STATUS_PREPARED,
        EXAMINER_MODE_NONE,
        ORAL_PART_FAILED_LINE,
        PAPER_BLOCKS_ELECTRONIC,
        PAPER_ENTRY_LOCKED,
        PAPER_EVALUATE_CONFIRM,
        PAPER_EVALUATE_INCOMPLETE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_FINISH_PAPER,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_MODE_PAPER,
        WRITTEN_OUTCOME_CORRECT,
        WRITTEN_OUTCOME_INCORRECT,
        WRITTEN_OUTCOME_UNANSWERED,
        WRITTEN_RESULT_FAILED_LABEL,
        WRITTEN_RESULT_PASSED,
        WRITTEN_RESULT_PASSED_LABEL,
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
    from moduly.testy.sluzby.oral_question_topic_service import oral_question_topic_service
    from moduly.testy.sluzby.paper_test_export_service import variant_label
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_exam_service import (
        score_written_outcomes,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.paper_answer_dialog import PaperAnswerDialog
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.testy_page import TestyPage


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
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


def _written_exam(
    employee,
    name: str,
    texts: list[str],
    *,
    allowed: int,
    oral: bool = False,
    exam_day: date = date(2026, 10, 6),
):
    topic = written_question_topic_service.create_topic(name=f"Okruh {name}")
    for text in texts:
        written_question_service.create_question(
            topic_id=topic.id,
            text=text,
            answer_kind="text",
            answers=_answers(),
            note="TajnaPoznamka",
        )
    oral_topics = None
    if oral:
        oral_topic = oral_question_topic_service.create_topic(name=f"Ústní {name}")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Povězte postup")
        oral_topics = [TestTopicQuota(oral_topic.id, 1)]
    definition = test_definition_service.create_test(
        name=name,
        uses_written=True,
        uses_oral=oral,
        allowed_wrong_answers=allowed,
        seconds_per_question=30,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic.id, len(texts))],
        oral_topics=oral_topics,
    )
    return test_exam_service.prepare_exam(
        employee_id=employee.id,
        test_id=definition.id,
        exam_date=exam_day,
        rng=PrefixReverse(),
    )


def _snapshot(exam_id: int) -> tuple:
    rows = []
    for question in test_exam_service.get_written_questions(exam_id):
        answers = tuple(
            (
                answer.id,
                answer.letter,
                answer.position,
                answer.text,
                bool(answer.is_correct),
                answer.image_stored_path,
            )
            for answer in test_exam_service.get_written_answers(question.id)
        )
        rows.append(
            (
                question.id,
                question.position,
                question.text,
                question.answer_kind,
                question.image_stored_path,
                answers,
            )
        )
    return tuple(rows)


def _letter(question_id: int, *, correct: bool) -> str:
    for answer in test_exam_service.get_written_answers(question_id):
        if bool(answer.is_correct) == correct:
            return answer.letter
    raise AssertionError("Odpověď ve snapshotu chybí.")


def _choice_for(exam_id: int, question_id: int):
    for choice in test_exam_service.get_written_choices(exam_id):
        if int(choice.exam_question_id) == int(question_id):
            return choice
    return None


def _select_rows(table, exam_ids: list[int]) -> None:
    table.clearSelection()
    flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
    model = table.selectionModel()
    assert model is not None
    for exam_id in exam_ids:
        for row in range(table.rowCount()):
            item = table.item(row, EXAM_COL_ID)
            if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
                model.select(table.model().index(row, 0), flags)
                break


def _select_exam(table, exam_id: int) -> None:
    table.clearSelection()
    for row in range(table.rowCount()):
        item = table.item(row, EXAM_COL_ID)
        if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
            table.selectRow(row)
            return
    raise AssertionError(f"Zkouška {exam_id} není v tabulce.")


class PaperAnswerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
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
        self.page = TestyPage()
        self.dialogs: list = []

    def tearDown(self) -> None:
        for dialog in self.dialogs:
            dialog.close()
        self.page.close()

    def test_keyboard_saves_snapshot_letters_and_reopens(self) -> None:
        employee = _employee("2001", "Jan", "Novák")
        exam = _written_exam(
            employee,
            "Papírový přepis",
            ["Otázka alfa", "Otázka beta", "Otázka gama"],
            allowed=1,
        )
        before = _snapshot(exam.id)
        questions = test_exam_service.get_written_questions(exam.id)
        dialog = self._open(exam.id)
        self.assertEqual(dialog.variant.text(), variant_label(exam))
        self.assertIn(exam.employee_display_name, dialog.employee.text())
        self.assertIn(exam.test_name, dialog.test_name.text())
        self.assertEqual(dialog.count.text(), "Počet otázek: 3")
        self.assertEqual(dialog.position.text(), "Aktuální otázka: 1")
        self._assert_no_correctness(dialog)
        self.assertNotIn("první", self._visible_text(dialog))
        self.assertNotIn("TajnaPoznamka", self._visible_text(dialog))

        QTest.keyClick(dialog.list, Qt.Key.Key_A)
        self.assertEqual(dialog.list.currentRow(), 1)
        self.assertEqual(dialog.list.item(0).text(), "1. A")
        QTest.keyClick(dialog.list, Qt.Key.Key_B, Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual(dialog.list.currentRow(), 2)
        self.assertEqual(dialog.list.item(1).text(), "2. B")
        QTest.keyClick(dialog.list, Qt.Key.Key_C)
        self.assertEqual(dialog.list.currentRow(), 2)
        self.assertEqual(dialog.list.item(2).text(), "3. C")

        for index, question in enumerate(questions):
            choice = _choice_for(exam.id, question.id)
            assert choice is not None
            self.assertEqual(choice.selected_letter, "ABC"[index])
            matched = [
                answer
                for answer in test_exam_service.get_written_answers(question.id)
                if answer.letter == choice.selected_letter
            ]
            self.assertEqual(len(matched), 1)
            self.assertEqual(choice.exam_answer_id, matched[0].id)

        QTest.keyClick(dialog.list, Qt.Key.Key_Up)
        QTest.keyClick(dialog.list, Qt.Key.Key_Up)
        self.assertEqual(dialog.list.currentRow(), 0)
        QTest.keyClick(dialog.list, Qt.Key.Key_B)
        self.assertEqual(dialog.list.item(0).text(), "1. B")
        replaced = _choice_for(exam.id, questions[0].id)
        assert replaced is not None
        self.assertEqual(replaced.selected_letter, "B")
        self.assertEqual(len(test_exam_service.get_written_choices(exam.id)), 3)

        QTest.keyClick(dialog.list, Qt.Key.Key_Up)
        QTest.keyClick(dialog.list, Qt.Key.Key_Up)
        QTest.keyClick(dialog.list, Qt.Key.Key_Backspace)
        self.assertEqual(dialog.list.item(0).text(), "1. —")
        self.assertIsNone(_choice_for(exam.id, questions[0].id))

        QTest.keyClick(dialog.list, Qt.Key.Key_D)
        QTest.keyClick(dialog.list, Qt.Key.Key_Return)
        self.assertEqual(dialog.list.item(0).text(), "1. —")
        self.assertEqual(dialog.list.item(1).text(), "2. B")
        with self.assertRaises(TestExamError):
            written_exam_service.save_paper_letter(exam.id, questions[0].id, "AB")
        with self.assertRaises(TestExamError):
            written_exam_service.save_paper_letter(exam.id, questions[0].id, "1")

        dialog.close()
        again = self._open(exam.id)
        self.assertEqual(again.list.item(0).text(), "1. —")
        self.assertEqual(again.list.item(1).text(), "2. B")
        self.assertEqual(again.list.item(2).text(), "3. C")
        self.assertEqual(again.list.currentRow(), 0)
        self.assertEqual(again.position.text(), "Aktuální otázka: 1")
        self._assert_no_correctness(again)

        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.status, EXAM_STATUS_PREPARED)
        self.assertEqual(fresh.written_mode, WRITTEN_MODE_PAPER)
        self.assertIsNone(fresh.written_started_at)
        self.assertIsNone(fresh.written_result)
        self.assertEqual(_snapshot(exam.id), before)

        tab = self.page.exams_tab
        tab.refresh()
        self.assertFalse(tab.paper_btn.isEnabled())
        _select_exam(tab.table, exam.id)
        self.assertTrue(tab.paper_btn.isEnabled())
        self.assertEqual(tab.paper_btn.text(), EXAM_ACTION_ENTER_PAPER)
        self.assertFalse(tab.start_btn.isEnabled())

    def test_evaluation_uses_same_rules_and_locks_answers(self) -> None:
        employee = _employee("2002", "Eva", "Malá")
        exam = _written_exam(
            employee,
            "Vyhodnocení papíru",
            ["Jedna", "Dvě", "Tři"],
            allowed=1,
        )
        questions = test_exam_service.get_written_questions(exam.id)
        written_exam_service.save_paper_letter(
            exam.id,
            questions[0].id,
            _letter(questions[0].id, correct=True).lower(),
            now=_LATE,
        )
        written_exam_service.save_paper_letter(
            exam.id,
            questions[1].id,
            _letter(questions[1].id, correct=False),
        )
        outcomes = [
            WRITTEN_OUTCOME_CORRECT,
            WRITTEN_OUTCOME_INCORRECT,
            WRITTEN_OUTCOME_UNANSWERED,
        ]
        expected = score_written_outcomes(outcomes, 1)
        self.assertEqual(expected.result, "failed")
        before = _snapshot(exam.id)
        duration = test_exam_service.get_exam(exam.id).written_duration_seconds

        dialog = self._open(exam.id)
        seen: list[str] = []

        def question_box(*_args, **_kwargs):
            seen.append(_args[2])
            return QMessageBox.StandardButton.No

        with patch(
            "moduly.testy.ui.paper_answer_dialog.QMessageBox.question",
            side_effect=question_box,
        ):
            dialog.evaluate_btn.click()
        self.assertEqual(seen, [PAPER_EVALUATE_INCOMPLETE])
        paused = test_exam_service.get_exam(exam.id)
        assert paused is not None
        self.assertEqual(paused.status, EXAM_STATUS_PREPARED)
        self.assertFalse(dialog.evaluated)

        with patch(
            "moduly.testy.ui.paper_answer_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog.evaluate_btn.click()
        self.assertTrue(dialog.evaluated)
        finished = test_exam_service.get_exam(exam.id)
        assert finished is not None
        self.assertEqual(finished.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(finished.written_mode, WRITTEN_MODE_PAPER)
        self.assertEqual(finished.written_finish_reason, WRITTEN_FINISH_PAPER)
        self.assertIsNone(finished.written_started_at)
        self.assertEqual(finished.written_duration_seconds, duration)
        self.assertIsNotNone(finished.written_evaluated_at)
        self.assertEqual(finished.written_question_count, expected.question_count)
        self.assertEqual(finished.written_correct_count, expected.correct_count)
        self.assertEqual(finished.written_incorrect_count, expected.incorrect_count)
        self.assertEqual(finished.written_unanswered_count, expected.unanswered_count)
        self.assertEqual(
            finished.written_allowed_wrong_answers,
            expected.allowed_wrong_answers,
        )
        self.assertEqual(finished.written_result, expected.result)
        self.assertEqual(finished.exam_result, expected.result)
        self.assertEqual(_snapshot(exam.id), before)
        with self.assertRaises(TestExamError) as locked:
            written_exam_service.save_paper_letter(exam.id, questions[2].id, "A")
        self.assertEqual(str(locked.exception), PAPER_ENTRY_LOCKED)
        with self.assertRaises(TestExamError):
            written_exam_service.clear_paper_answer(exam.id, questions[0].id)
        with self.assertRaises(TestExamError):
            PaperAnswerDialog(exam.id)

        tab = self.page.exams_tab
        tab.refresh()
        _select_exam(tab.table, exam.id)
        row = tab.table.currentRow()
        self.assertEqual(tab.table.item(row, EXAM_COL_STATUS).text(), EXAM_STATUS_COMPLETED_LABEL)
        self.assertEqual(
            tab.table.item(row, EXAM_COL_WRITTEN_RESULT).text(),
            WRITTEN_RESULT_FAILED_LABEL,
        )
        self.assertEqual(
            tab.table.item(row, EXAM_COL_EXAM_RESULT).text(),
            WRITTEN_RESULT_FAILED_LABEL,
        )
        self.assertFalse(tab.paper_btn.isEnabled())
        self.assertFalse(tab.start_btn.isEnabled())

        detail = TestExamDetailDialog(None, exam_id=exam.id)
        self.dialogs.append(detail)
        summary = detail.written_summary.text()
        self.assertIn("Správně: 1", summary)
        self.assertIn("Chybně: 1", summary)
        self.assertIn("Nezodpovězeno: 1", summary)
        self.assertIn("Výsledek písemné části: Nevyhověl", summary)
        employee_answer = detail.findChild(QLabel, "written-employee-answer-3")
        correct_answer = detail.findChild(QLabel, "written-correct-answer-1")
        outcome = detail.findChild(QLabel, "written-outcome-3")
        assert employee_answer is not None
        assert correct_answer is not None
        assert outcome is not None
        self.assertIn("nezodpovězeno", employee_answer.text())
        self.assertTrue(correct_answer.text().startswith("Správná odpověď:"))
        self.assertIn("Nezodpovězeno", outcome.text())

        filled = _written_exam(
            employee,
            "Kompletní papír",
            ["Jen jedna"],
            allowed=0,
            exam_day=date(2026, 10, 7),
        )
        only = test_exam_service.get_written_questions(filled.id)[0]
        written_exam_service.save_paper_letter(
            filled.id,
            only.id,
            _letter(only.id, correct=True),
        )
        passed_dialog = self._open(filled.id)
        with patch(
            "moduly.testy.ui.paper_answer_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as confirm:
            passed_dialog.evaluate_btn.click()
        confirm.assert_called_once()
        self.assertEqual(confirm.call_args.args[2], PAPER_EVALUATE_CONFIRM)
        passed = test_exam_service.get_exam(filled.id)
        assert passed is not None
        self.assertEqual(passed.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(passed.written_correct_count, 1)
        self.assertEqual(passed.written_unanswered_count, 0)
        self.assertEqual(passed.status, EXAM_STATUS_COMPLETED)

    def test_modes_conflict_time_is_not_used_and_oral_failure_remains(self) -> None:
        employee = _employee("2003", "Petr", "Svoboda")
        paper = _written_exam(employee, "Rozpracovaný papír", ["Alfa", "Beta"], allowed=0)
        questions = test_exam_service.get_written_questions(paper.id)
        duration = paper.written_duration_seconds
        written_exam_service.save_paper_letter(
            paper.id,
            questions[0].id,
            "a",
            now=_LATE,
        )
        stored = test_exam_service.get_exam(paper.id)
        assert stored is not None
        self.assertEqual(stored.written_mode, WRITTEN_MODE_PAPER)
        self.assertIsNone(stored.written_started_at)
        self.assertEqual(stored.status, EXAM_STATUS_PREPARED)
        self.assertEqual(stored.written_duration_seconds, duration)
        self.assertEqual(written_exam_service.sync_deadline(paper.id, now=_LATE), "")
        still = test_exam_service.get_exam(paper.id)
        assert still is not None
        self.assertEqual(still.status, EXAM_STATUS_PREPARED)
        self.assertEqual(still.written_finish_reason, "")
        with self.assertRaises(TestExamError) as blocked:
            written_exam_service.start(paper.id, now=_LATE)
        self.assertEqual(str(blocked.exception), PAPER_BLOCKS_ELECTRONIC)
        self.assertEqual(test_exam_service.get_exam(paper.id).status, EXAM_STATUS_PREPARED)

        written_exam_service.clear_paper_answer(paper.id, questions[0].id)
        self.assertEqual(test_exam_service.get_written_choices(paper.id), [])
        self.assertEqual(test_exam_service.get_exam(paper.id).written_mode, WRITTEN_MODE_PAPER)
        with self.assertRaises(TestExamError):
            written_exam_service.start(paper.id)

        electronic = _written_exam(
            employee,
            "Elektronický běh",
            ["Gama"],
            allowed=0,
            exam_day=date(2026, 10, 8),
        )
        written_exam_service.start(electronic.id, now=_LATE)
        started = test_exam_service.get_exam(electronic.id)
        assert started is not None
        self.assertEqual(started.written_mode, WRITTEN_MODE_ELECTRONIC)
        self.assertEqual(started.written_started_at, _LATE)
        question = test_exam_service.get_written_questions(electronic.id)[0]
        with self.assertRaises(TestExamError) as paper_blocked:
            written_exam_service.save_paper_letter(electronic.id, question.id, "A")
        self.assertEqual(str(paper_blocked.exception), ELECTRONIC_BLOCKS_PAPER)
        with self.assertRaises(TestExamError):
            written_exam_service.evaluate_paper(electronic.id, now=_LATE)
        self.assertEqual(test_exam_service.get_written_choices(electronic.id), [])

        tab = self.page.exams_tab
        tab.refresh()
        _select_exam(tab.table, paper.id)
        self.assertTrue(tab.paper_btn.isEnabled())
        self.assertFalse(tab.start_btn.isEnabled())
        _select_exam(tab.table, electronic.id)
        self.assertFalse(tab.paper_btn.isEnabled())
        self.assertTrue(tab.start_btn.isEnabled())

        oral = _written_exam(
            employee,
            "Papír a ústní",
            ["Delta"],
            allowed=0,
            oral=True,
            exam_day=date(2026, 10, 9),
        )
        oral_question = test_exam_service.get_written_questions(oral.id)[0]
        written_exam_service.save_paper_letter(
            oral.id,
            oral_question.id,
            _letter(oral_question.id, correct=True),
        )
        moment = datetime(2026, 10, 9, 15, 0, 0)
        written_exam_service.evaluate_paper(oral.id, now=moment)
        done = test_exam_service.get_exam(oral.id)
        assert done is not None
        self.assertEqual(done.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(done.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(done.written_evaluated_at, moment)
        self.assertIsNone(done.written_started_at)
        self.assertEqual(done.status, EXAM_STATUS_COMPLETED)
        counts = (
            done.written_question_count,
            done.written_correct_count,
            done.written_incorrect_count,
            done.written_unanswered_count,
            done.written_result,
        )
        detail = TestExamDetailDialog(None, exam_id=oral.id)
        self.dialogs.append(detail)
        detail.show()
        QTest.qWait(1)
        self.assertEqual(detail.oral_failure_button.text(), EXAM_ACTION_RECORD_ORAL_FAILURE)
        self.assertTrue(detail.oral_failure_button.isVisible())
        test_exam_service.record_oral_failure(oral.id, now=moment)
        after = test_exam_service.get_exam(oral.id)
        assert after is not None
        self.assertEqual(after.exam_result, "failed")
        self.assertEqual(after.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(
            (
                after.written_question_count,
                after.written_correct_count,
                after.written_incorrect_count,
                after.written_unanswered_count,
                after.written_result,
            ),
            counts,
        )
        self.assertIsNotNone(after.oral_failed_at)
        detail.load_exam(oral.id)
        self.assertIn(ORAL_PART_FAILED_LINE, detail.written_summary.text())
        self.assertIn("Výsledek písemné části: Vyhověl", detail.written_summary.text())
        self.assertIn("Výsledek zkoušky: Nevyhověl", detail.written_summary.text())
        tab.refresh()
        _select_exam(tab.table, oral.id)
        row = tab.table.currentRow()
        self.assertEqual(
            tab.table.item(row, EXAM_COL_WRITTEN_RESULT).text(),
            WRITTEN_RESULT_PASSED_LABEL,
        )
        self.assertEqual(
            tab.table.item(row, EXAM_COL_EXAM_RESULT).text(),
            WRITTEN_RESULT_FAILED_LABEL,
        )

    def test_unset_mode_enables_paper_entry_until_finished_or_electronic(self) -> None:
        employee = _employee("2010", "Petr", "Holý")
        prepared = _written_exam(employee, "Režim nevyplněn", ["Otázka jedna"], allowed=0)
        electronic = _written_exam(employee, "Už electronic", ["Otázka dvě"], allowed=0)
        finished = _written_exam(employee, "Už dokončeno", ["Otázka tři"], allowed=0)
        with get_session() as session:
            row = session.get(TestExam, prepared.id)
            assert row is not None
            row.written_mode = None
            session.commit()

        stored = test_exam_service.get_exam(prepared.id)
        assert stored is not None
        self.assertIsNone(stored.written_mode)
        self.assertEqual(stored.status, EXAM_STATUS_PREPARED)
        self.assertIsNone(stored.written_started_at)
        self.assertTrue(written_exam_service.can_enter_paper(prepared.id))

        tab = self.page.exams_tab
        tab.refresh()
        self.assertFalse(tab.paper_btn.isEnabled())
        _select_rows(tab.table, [prepared.id, electronic.id])
        self.assertFalse(tab.paper_btn.isEnabled())
        _select_exam(tab.table, prepared.id)
        self.assertTrue(tab.paper_btn.isEnabled())
        self.assertTrue(tab.start_btn.isEnabled())
        self.assertTrue(tab.print_btn.isEnabled())

        dialog = self._open(prepared.id)
        dialog.close()
        self.assertIsNone(test_exam_service.get_exam(prepared.id).written_mode)
        tab._update_action_buttons()
        self.assertTrue(tab.paper_btn.isEnabled())

        tab.refresh()
        self.assertEqual(tab.table.selected_exam_id(), prepared.id)
        self.assertTrue(tab.paper_btn.isEnabled())

        self.page.show()

        def close_detail() -> None:
            widget = QApplication.activeModalWidget()
            if widget is not None:
                widget.reject()

        QTimer.singleShot(100, close_detail)
        tab.open_selected()
        self.assertEqual(tab.table.selected_exam_id(), prepared.id)
        self.assertTrue(tab.paper_btn.isEnabled())
        self.assertIsNone(test_exam_service.get_exam(prepared.id).written_mode)

        target = _TMP / "fix1" / "vystup.odt"
        target.parent.mkdir(parents=True, exist_ok=True)
        from moduly.testy.ui.paper_test_options_dialog import PaperTestOptionsDialog

        def accept_without_key(dialog) -> QDialog.DialogCode:
            dialog.key_checkbox.setChecked(False)
            return QDialog.DialogCode.Accepted

        with (
            patch.object(PaperTestOptionsDialog, "exec", accept_without_key),
            patch(
                "moduly.testy.ui.test_exams_tab.QFileDialog.getSaveFileName",
                return_value=(str(target), "OpenDocument (*.odt)"),
            ),
            patch("moduly.testy.ui.test_exams_tab.open_export_file"),
        ):
            tab.print_paper_test()
        self.assertTrue(target.is_file())
        self.assertTrue(tab.paper_btn.isEnabled())
        self.assertIsNone(test_exam_service.get_exam(prepared.id).written_mode)
        self.assertEqual(test_exam_service.get_exam(prepared.id).status, EXAM_STATUS_PREPARED)

        written_exam_service.start(electronic.id)
        tab.refresh()
        _select_exam(tab.table, electronic.id)
        self.assertFalse(tab.paper_btn.isEnabled())
        self.assertFalse(written_exam_service.can_enter_paper(electronic.id))
        with self.assertRaises(TestExamError) as electronic_blocked:
            question = test_exam_service.get_written_questions(electronic.id)[0]
            written_exam_service.save_paper_letter(
                electronic.id,
                question.id,
                _letter(question.id, correct=True),
            )
        self.assertEqual(str(electronic_blocked.exception), ELECTRONIC_BLOCKS_PAPER)

        written_exam_service.evaluate_paper(finished.id, now=_LATE)
        tab.refresh()
        _select_exam(tab.table, finished.id)
        self.assertFalse(tab.paper_btn.isEnabled())
        self.assertFalse(written_exam_service.can_enter_paper(finished.id))
        done = test_exam_service.get_exam(finished.id)
        assert done is not None
        self.assertEqual(done.status, EXAM_STATUS_COMPLETED)
        with self.assertRaises(TestExamError) as finished_blocked:
            question = test_exam_service.get_written_questions(finished.id)[0]
            written_exam_service.save_paper_letter(
                finished.id,
                question.id,
                _letter(question.id, correct=True),
            )
        self.assertEqual(str(finished_blocked.exception), PAPER_ENTRY_LOCKED)

        _select_exam(tab.table, prepared.id)
        self.assertTrue(tab.paper_btn.isEnabled())
        question = test_exam_service.get_written_questions(prepared.id)[0]
        written_exam_service.save_paper_letter(
            prepared.id,
            question.id,
            _letter(question.id, correct=True),
        )
        after_save = test_exam_service.get_exam(prepared.id)
        assert after_save is not None
        self.assertEqual(after_save.written_mode, WRITTEN_MODE_PAPER)
        self.assertEqual(after_save.status, EXAM_STATUS_PREPARED)
        self.assertIsNone(after_save.written_started_at)
        tab._update_action_buttons()
        self.assertTrue(tab.paper_btn.isEnabled())
        self.assertFalse(tab.start_btn.isEnabled())

    def _open(self, exam_id: int) -> PaperAnswerDialog:
        dialog = PaperAnswerDialog(exam_id)
        self.dialogs.append(dialog)
        dialog.show()
        QTest.qWait(1)
        return dialog

    def _visible_text(self, dialog: PaperAnswerDialog) -> str:
        parts = [label.text() for label in dialog.findChildren(QLabel)]
        parts.extend(
            dialog.list.item(row).text()
            for row in range(dialog.list.count())
            if dialog.list.item(row) is not None
        )
        return "\n".join(parts)

    def _assert_no_correctness(self, dialog: PaperAnswerDialog) -> None:
        text = self._visible_text(dialog).casefold()
        for banned in ("správn", "chybně", "vyhodnocení", "vyhověl", "nevyhověl"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
