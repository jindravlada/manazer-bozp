"""Souhrn výsledku hned po uložení ručně zadaného papírového testu.

Izolovaná databáze v dočasném adresáři. Produkční data se neotevírají.
"""

from __future__ import annotations

import html
import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QGroupBox, QLabel, QMessageBox
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-paper-result-"))

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
        EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        EXAM_COL_ID,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
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
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
    )
    from moduly.testy.sluzby.exam_protocol_layout import (
        ERROR_LIST_HEADING,
        paper_result_text,
    )
    from moduly.testy.sluzby.paper_test_export_service import paper_test_export_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_answer_presentation import (
        CORRECT_COLOR,
        ERROR_COLOR,
    )
    from moduly.testy.sluzby.written_exam_service import written_exam_service
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.paper_answer_dialog import PaperAnswerDialog
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.test_exams_tab import TestExamsTab
    from tests.historical_test_employee import seed_historical_test_employee


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


def _employee(number: str):
    workplace = settings_service.save_workplace(name=f"Provoz {number}")
    role = responsibility_role_service.create_role(name=f"Mistr {number}")
    return seed_historical_test_employee(
        personal_number=number,
        first_name="Jana",
        last_name="Malá",
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
    )


def _exam(employee, name: str, texts: list[str], *, allowed: int):
    topic = written_question_topic_service.create_topic(name=f"Okruh {name}")
    for text in texts:
        written_question_service.create_question(
            topic_id=topic.id,
            text=text,
            answer_kind="text",
            answers=_answers(),
            note="",
        )
    definition = test_definition_service.create_test(
        name=name,
        uses_written=True,
        uses_oral=False,
        allowed_wrong_answers=allowed,
        seconds_per_question=30,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic.id, len(texts))],
    )
    return test_exam_service.prepare_exam(
        employee_id=employee.id,
        test_id=definition.id,
        exam_date=date(2026, 11, 14),
        rng=PrefixReverse(),
        employee_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
        examiner_source=EMPLOYEE_SOURCE_TEST_EMPLOYEE,
    )


def _question(exam_id: int, text: str):
    for question in test_exam_service.get_written_questions(exam_id):
        if question.text == text:
            return question
    raise AssertionError(text)


def _letter(question_id: int, *, correct: bool) -> str:
    for answer in test_exam_service.get_written_answers(question_id):
        if bool(answer.is_correct) == correct:
            return answer.letter
    raise AssertionError("Odpověď ve snapshotu chybí.")


def _select_exam(table, exam_id: int) -> None:
    table.clearSelection()
    for row in range(table.rowCount()):
        item = table.item(row, EXAM_COL_ID)
        if item is not None and int(item.data(Qt.ItemDataRole.UserRole)) == exam_id:
            table.selectRow(row)
            return
    raise AssertionError(f"Zkouška {exam_id} není v tabulce.")


def _exam_count() -> int:
    return len(test_exam_service.list_exams())


def _stamp(exam_id: int) -> tuple:
    exam = test_exam_service.get_exam(exam_id)
    assert exam is not None
    return (
        exam.id,
        exam.status,
        exam.written_result,
        exam.exam_result,
        exam.written_question_count,
        exam.written_correct_count,
        exam.written_incorrect_count,
        exam.written_unanswered_count,
        exam.written_evaluated_at,
    )


def _protocol_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("content.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(text)


class PaperResultDialogTestCase(unittest.TestCase):
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
        self.tab = TestExamsTab()
        self.opened: list[TestExamDetailDialog] = []
        self.folder = _TMP / self._testMethodName
        self.folder.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        for dialog in self.opened:
            dialog.close()
        self.tab.close()

    def test_passed_without_errors_hides_empty_error_list(self) -> None:
        employee = _employee("pr-1")
        exam = _exam(employee, "Samé správné", ["Jediná otázka"], allowed=0)
        question = _question(exam.id, "Jediná otázka")
        written_exam_service.save_paper_letter(
            exam.id,
            question.id,
            _letter(question.id, correct=True),
        )
        detail = self._enter(exam.id, confirm=QMessageBox.StandardButton.Yes)
        self.assertEqual(self._evaluate_calls, 1)
        self.assertEqual(_exam_count(), 1)
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(stored.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(stored.written_correct_count, 1)
        self.assertEqual(stored.written_incorrect_count, 0)
        self.assertEqual(stored.written_unanswered_count, 0)
        self._assert_banner(detail, WRITTEN_RESULT_PASSED_LABEL, CORRECT_COLOR)
        self.assertIn("Počet otázek: 1", detail.written_summary.text())
        self.assertIn("Správně: 1", detail.written_summary.text())
        self.assertIn("Chybně: 0", detail.written_summary.text())
        self.assertTrue(detail.written_errors_box.isHidden())
        self.assertIsNone(detail.findChild(QLabel, "written-error-1"))
        self.assertFalse(detail.results_changed)

    def test_passed_with_allowed_error_still_lists_that_question(self) -> None:
        employee = _employee("pr-2")
        exam = _exam(
            employee,
            "Jedna povolená",
            ["Správná otázka alfa", "Chybná otázka beta"],
            allowed=1,
        )
        right = _question(exam.id, "Správná otázka alfa")
        wrong = _question(exam.id, "Chybná otázka beta")
        written_exam_service.save_paper_letter(
            exam.id, right.id, _letter(right.id, correct=True)
        )
        written_exam_service.save_paper_letter(
            exam.id, wrong.id, _letter(wrong.id, correct=False)
        )
        detail = self._enter(exam.id, confirm=QMessageBox.StandardButton.Yes)
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(stored.written_incorrect_count, 1)
        self._assert_banner(detail, WRITTEN_RESULT_PASSED_LABEL, CORRECT_COLOR)
        self.assertIn("Počet otázek: 2", detail.written_summary.text())
        self.assertIn("Správně: 1", detail.written_summary.text())
        self.assertIn("Chybně: 1", detail.written_summary.text())
        self._assert_errors(detail, [wrong])
        self._assert_answer_colors(detail, wrong, correct=False)
        self.assertIsNone(detail.findChild(QLabel, f"written-error-{right.position}"))

    def test_several_errors_list_numbers_and_texts(self) -> None:
        employee = _employee("pr-3")
        exam = _exam(
            employee,
            "Více chyb",
            ["Správná otázka alfa", "Chybná otázka beta", "Nezodpovězená otázka gama"],
            allowed=0,
        )
        right = _question(exam.id, "Správná otázka alfa")
        wrong = _question(exam.id, "Chybná otázka beta")
        missed = _question(exam.id, "Nezodpovězená otázka gama")
        written_exam_service.save_paper_letter(
            exam.id, right.id, _letter(right.id, correct=True)
        )
        written_exam_service.save_paper_letter(
            exam.id, wrong.id, _letter(wrong.id, correct=False)
        )
        before_rows = _exam_count()
        detail = self._enter(exam.id, confirm=QMessageBox.StandardButton.Yes)
        stamp = _stamp(exam.id)
        self.assertEqual(self._evaluate_calls, 1)
        self.assertEqual(_exam_count(), before_rows)
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.written_result, "failed")
        self.assertEqual(stored.written_correct_count, 1)
        self.assertEqual(stored.written_incorrect_count, 1)
        self.assertEqual(stored.written_unanswered_count, 1)
        self.assertEqual(stored.written_question_count, 3)
        self._assert_banner(detail, WRITTEN_RESULT_FAILED_LABEL, ERROR_COLOR)
        self._assert_errors(detail, [wrong, missed])
        self.assertIsNone(detail.findChild(QLabel, f"written-error-{right.position}"))
        self._assert_answer_colors(detail, wrong, correct=False)
        missing = detail.findChild(QLabel, f"written-unanswered-{missed.position}")
        assert missing is not None
        self.assertEqual(missing.text(), "Nezodpovězeno — chyba")

        again = TestExamDetailDialog(exam_id=exam.id)
        self.opened.append(again)
        self._assert_banner(again, WRITTEN_RESULT_FAILED_LABEL, ERROR_COLOR)
        self._assert_errors(again, [wrong, missed])
        again.reject()
        self.assertEqual(_stamp(exam.id), stamp)
        self.assertEqual(_exam_count(), before_rows)

        self.assertFalse(exam_protocol_export_service.can_export(exam.id))
        with self.assertRaises(TestExamError) as blocked:
            exam_protocol_export_service.export(exam.id, self.folder / "protokol.odt")
        self.assertIn("Samostatný protokol se nevytváří.", str(blocked.exception))
        printed = paper_test_export_service.export(exam.id, self.folder / "test.odt")
        plain = _protocol_text(printed.test_path)
        self.assertIn(paper_result_text("Výsledek písemné části:"), plain)
        self.assertIn("Chybná otázka beta", plain)
        self.assertIn("Správná otázka alfa", plain)
        self.assertNotIn(ERROR_LIST_HEADING, plain)
        self.assertEqual(_stamp(exam.id), stamp)

    def test_summary_stays_closed_when_save_is_declined_or_fails(self) -> None:
        employee = _employee("pr-4")
        exam = _exam(employee, "Bez uložení", ["Otázka k odmítnutí"], allowed=0)
        question = _question(exam.id, "Otázka k odmítnutí")
        written_exam_service.save_paper_letter(
            exam.id,
            question.id,
            _letter(question.id, correct=False),
        )
        self._enter(exam.id, confirm=QMessageBox.StandardButton.No, expect_detail=False)
        self.assertEqual(self._evaluate_calls, 0)
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.status, EXAM_STATUS_PREPARED)
        self.assertFalse(stored.written_result)
        self.assertEqual(_exam_count(), 1)

        def fail_save(*_args, **_kwargs):
            raise TestExamError("Uložení selhalo.")

        with patch.object(written_exam_service, "evaluate_paper", fail_save):
            self._enter(
                exam.id,
                confirm=QMessageBox.StandardButton.Yes,
                expect_detail=False,
            )
        self.assertEqual(self._evaluate_calls, 1)
        stored = test_exam_service.get_exam(exam.id)
        assert stored is not None
        self.assertEqual(stored.status, EXAM_STATUS_PREPARED)
        self.assertFalse(stored.written_result)
        self.assertEqual(_exam_count(), 1)
        self.assertEqual(len(test_exam_service.get_written_choices(exam.id)), 1)

    def _enter(
        self,
        exam_id: int,
        *,
        confirm: QMessageBox.StandardButton,
        expect_detail: bool = True,
    ) -> TestExamDetailDialog | None:
        self.tab.refresh()
        _select_exam(self.tab.table, exam_id)
        self._evaluate_calls = 0
        current_evaluate = written_exam_service.evaluate_paper

        def counting_evaluate(*args, **kwargs):
            self._evaluate_calls += 1
            return current_evaluate(*args, **kwargs)

        def run_entry(dialog: PaperAnswerDialog):
            dialog.evaluate()
            if dialog.evaluated:
                return QDialog.DialogCode.Accepted
            return QDialog.DialogCode.Rejected

        def capture_detail(dialog: TestExamDetailDialog):
            self.opened.append(dialog)
            dialog._opened_stamp = _stamp(exam_id)  # type: ignore[attr-defined]
            return QDialog.DialogCode.Rejected

        with (
            patch.object(written_exam_service, "evaluate_paper", counting_evaluate),
            patch.object(PaperAnswerDialog, "exec", run_entry),
            patch.object(TestExamDetailDialog, "exec", capture_detail),
            patch(
                "moduly.testy.ui.paper_answer_dialog.QMessageBox.question",
                return_value=confirm,
            ),
            patch("moduly.testy.ui.paper_answer_dialog.QMessageBox.warning"),
        ):
            before = len(self.opened)
            self.tab.enter_paper_answers()
        opened_now = self.opened[before:]
        if not expect_detail:
            self.assertEqual(opened_now, [])
            return None
        self.assertEqual(len(opened_now), 1)
        detail = opened_now[0]
        self.assertEqual(_stamp(exam_id), detail._opened_stamp)  # type: ignore[attr-defined]
        return detail

    def _assert_banner(self, detail: TestExamDetailDialog, label: str, color: str) -> None:
        banner = detail.findChild(QLabel, "exam-result-banner")
        assert banner is not None
        self.assertFalse(banner.isHidden())
        self.assertEqual(banner.text(), f"Výsledek zkoušky: {label}")
        self.assertIn(color, banner.styleSheet())
        self.assertIn("font-weight: 700", banner.styleSheet())
        self.assertEqual(banner.textFormat(), Qt.TextFormat.PlainText)
        self.assertIn(f"Výsledek zkoušky: {label}", detail.written_summary.text())

    def _assert_errors(self, detail: TestExamDetailDialog, questions) -> None:
        box = detail.findChild(QGroupBox, "exam-written-errors")
        assert box is not None
        self.assertFalse(box.isHidden())
        self.assertEqual(box.title(), ERROR_LIST_HEADING)
        labels = []
        for question in questions:
            label = detail.findChild(QLabel, f"written-error-{question.position}")
            assert label is not None
            self.assertEqual(label.text(), f"{question.position}. {question.text}")
            self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
            labels.append(label)
        self.assertEqual(len(labels), len(questions))

    def _assert_answer_colors(self, detail, question, *, correct: bool) -> None:
        chosen_letter = _letter(question.id, correct=correct)
        right_letter = _letter(question.id, correct=True)
        chosen = detail.findChild(QLabel, f"answer-{question.position}-{chosen_letter}")
        right = detail.findChild(QLabel, f"answer-{question.position}-{right_letter}")
        assert chosen is not None and right is not None
        if correct:
            self.assertIn(CORRECT_COLOR, chosen.styleSheet())
            return
        self.assertIn(ERROR_COLOR, chosen.styleSheet())
        self.assertIn("— chyba", chosen.text())
        self.assertIn(CORRECT_COLOR, right.styleSheet())


if __name__ == "__main__":
    unittest.main()
