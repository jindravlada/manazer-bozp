"""TESTY-8: elektronické provedení písemného testu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
)
from sqlalchemy import delete, func, inspect, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-8-"))

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
    from core.windows.main_window import MainWindow
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAM_COL_TEST,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_NONE,
        TEST_DIALOG_TITLE_EDIT,
        TEST_DIALOG_TITLE_NEW,
        VALIDITY_UNIT_YEARS,
        WRITTEN_FINISHED_TEXT,
        WRITTEN_SUBMIT_CONFIRM,
        WRITTEN_SUBMIT_INCOMPLETE,
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
        WRITTEN_EXAM_DEV_EXIT_ENV,
        FixedWrittenExamClock,
        WrittenAnswerOption,
        WrittenQuestionCard,
        clamp_question_index,
        format_remaining_clock,
        format_remaining_label,
        question_answer_marks,
        remaining_written_seconds,
        step_question_index,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_exam_service import WrittenExamClosed
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_definition_dialog import TestDefinitionDialog
    from moduly.testy.ui.test_definitions_tab import TestDefinitionsTab
    from moduly.testy.ui.test_exams_tab import TestExamsTab
    from moduly.testy.ui.written_exam_window import WrittenExamWindow
    from core.widgets.dialog_utils import exec_maximized


_APP = QApplication.instance() or QApplication([])
_STARTED = datetime(2026, 10, 6, 14, 0, 0)


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _png(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (12, 8)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
    ]


def _employee(number: str, first: str, last: str):
    workplace = settings_service.save_workplace(name=f"PROVOZ_TAJNY_{number}")
    role = responsibility_role_service.create_role(name=f"Mistr {number}")
    return test_employee_service.create_employee(
        personal_number=number,
        first_name=first,
        last_name=last,
        workplace_id=workplace.id,
        responsibility_role_ids=[role.id],
    )


def _written_test(name: str, texts: list[str], *, seconds: int = 30, note: str = ""):
    topic = written_question_topic_service.create_topic(name=f"SKRYTY_OKRUH_{name}")
    for text in texts:
        written_question_service.create_question(
            topic_id=topic.id,
            text=text,
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            note=note,
        )
    test = test_definition_service.create_test(
        name=name,
        uses_written=True,
        allowed_wrong_answers=0,
        seconds_per_question=seconds,
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
        exam_date=datetime(2026, 10, 6).date(),
        rng=PrefixReverse(),
    )


def _fingerprint(exam_id: int):
    rows = []
    for question in test_exam_service.get_written_questions(exam_id):
        answers = tuple(
            (
                answer.id,
                answer.letter,
                answer.position,
                answer.text,
                answer.is_correct,
                answer.image_stored_path,
                answer.image_sha256,
            )
            for answer in test_exam_service.get_written_answers(question.id)
        )
        rows.append(
            (
                question.id,
                question.source_question_id,
                question.text,
                question.topic_name,
                question.answer_kind,
                question.position,
                question.image_stored_path,
                question.image_sha256,
                answers,
            )
        )
    return tuple(rows)


def _visible_text(window) -> str:
    parts = []
    for label in window.findChildren(QLabel):
        if label.isVisible():
            parts.append(label.text())
    for button in window.findChildren(QPushButton):
        if button.isVisible():
            parts.append(button.text())
    for radio in window.findChildren(QRadioButton):
        if radio.isVisible():
            parts.append(radio.text())
    return "\n".join(parts)


class WrittenExamRulesTestCase(unittest.TestCase):
    def test_remaining_time_uses_stored_start(self) -> None:
        start = _STARTED
        self.assertEqual(format_remaining_clock(14 * 60 + 32), "14:32")
        self.assertEqual(format_remaining_label(14 * 60 + 32), "Zbývá: 14:32")
        self.assertEqual(format_remaining_clock(3661), "1:01:01")
        self.assertEqual(remaining_written_seconds(start, 900, start), 900)
        self.assertEqual(
            remaining_written_seconds(start, 900, start + timedelta(seconds=328)),
            572,
        )
        self.assertEqual(format_remaining_clock(572), "09:32")
        self.assertEqual(
            remaining_written_seconds(start, 900, start - timedelta(seconds=20)),
            900,
        )
        self.assertEqual(
            remaining_written_seconds(start, 900, start + timedelta(seconds=900)),
            0,
        )
        self.assertEqual(
            remaining_written_seconds(start, 900, start + timedelta(seconds=950)),
            0,
        )

    def test_question_navigation_stops_at_ends(self) -> None:
        self.assertEqual(step_question_index(0, 5, -1), 0)
        self.assertEqual(step_question_index(4, 5, 1), 4)
        self.assertEqual(step_question_index(1, 5, 1), 2)
        self.assertEqual(step_question_index(2, 5, -1), 1)
        self.assertEqual(clamp_question_index(-4, 3), 0)
        self.assertEqual(clamp_question_index(9, 3), 2)
        self.assertEqual(
            question_answer_marks([10, 11, 12], {10}, 1),
            [(True, False), (False, True), (False, False)],
        )

    def test_employee_screen_has_no_correctness_or_internal_fields(self) -> None:
        self.assertNotIn("is_correct", WrittenQuestionCard.__dataclass_fields__)
        self.assertNotIn("is_correct", WrittenAnswerOption.__dataclass_fields__)
        self.assertNotIn("note", WrittenQuestionCard.__dataclass_fields__)
        self.assertNotIn("source_question_id", WrittenQuestionCard.__dataclass_fields__)


class ElectronicWrittenExamTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.images = _TMP / "images"

    def setUp(self) -> None:
        self._open: list[WrittenExamWindow] = []
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
        for window in self._open:
            window.release_testing_lock()
        QApplication.processEvents()

    def _watch(self, window: WrittenExamWindow) -> WrittenExamWindow:
        self._open.append(window)
        return window

    def test_schema_keeps_written_progress(self) -> None:
        columns = {column["name"] for column in inspect(engine).get_columns("test_exams")}
        self.assertIn("written_started_at", columns)
        self.assertIn("written_finished_at", columns)
        self.assertIn("written_finish_reason", columns)
        self.assertTrue(inspect(engine).has_table("test_exam_written_choices"))

    def test_start_only_prepared_exam_with_written_part(self) -> None:
        employee = _employee("81001", "Jana", "Malá")
        _topic, test = _written_test("Písemný", ["Otázka A", "Otázka B"], seconds=45)
        exam = _prepare(employee.id, test.id)
        self.assertTrue(written_exam_service.can_start(exam.id))
        oral_topic = oral_question_topic_service.create_topic(name="Ústní okruh")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Ústní otázka")
        oral_test = test_definition_service.create_test(
            name="Jen ústní",
            uses_written=False,
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        oral_exam = _prepare(employee.id, oral_test.id)
        self.assertFalse(written_exam_service.can_start(oral_exam.id))
        with self.assertRaises(TestExamError) as blocked:
            written_exam_service.start(oral_exam.id, now=_STARTED)
        self.assertIn("písemnou část", str(blocked.exception))
        self.assertEqual(
            test_exam_service.get_exam(oral_exam.id).status,
            EXAM_STATUS_PREPARED,
        )

        started = written_exam_service.start(exam.id, now=_STARTED)
        self.assertEqual(started.status, EXAM_STATUS_STARTED)
        self.assertEqual(started.written_started_at, _STARTED)
        self.assertEqual(started.written_finish_reason, "")
        self.assertIsNone(started.written_finished_at)
        self.assertFalse(written_exam_service.can_start(exam.id))
        with self.assertRaises(TestExamError) as again:
            written_exam_service.start(exam.id, now=_STARTED + timedelta(minutes=5))
        self.assertIn("Připraveno", str(again.exception))
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.written_started_at, _STARTED)
        self.assertEqual(fresh.status, EXAM_STATUS_STARTED)

    def test_choices_are_saved_immediately_and_can_change(self) -> None:
        employee = _employee("81002", "Petr", "Veselý")
        _topic, test = _written_test(
            "Volby",
            ["První zadání", "Druhé zadání", "Třetí zadání"],
            seconds=30,
            note="INTERNI_POZNAMKA_8",
        )
        exam = _prepare(employee.id, test.id)
        before = _fingerprint(exam.id)
        question_count = _count(TestExamWrittenQuestion)
        answer_count = _count(TestExamWrittenAnswer)
        written_exam_service.start(exam.id, now=_STARTED)
        screen = written_exam_service.screen(exam.id)
        self.assertEqual(len(screen.questions), 3)
        self.assertEqual(written_exam_service.unanswered_count(exam.id), 3)
        self.assertNotIn("INTERNI_POZNAMKA_8", screen.questions[0].text)
        self.assertNotIn("SKRYTY_OKRUH", screen.test_name)

        first = screen.questions[0]
        second = screen.questions[1]
        chosen = first.options[0]
        replacement = first.options[1]
        saved_at = _STARTED + timedelta(seconds=4)
        written_exam_service.save_choice(
            exam.id,
            first.exam_question_id,
            chosen.exam_answer_id,
            now=saved_at,
        )
        stored = written_exam_service.choices(exam.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].exam_question_id, first.exam_question_id)
        self.assertEqual(stored[0].exam_answer_id, chosen.exam_answer_id)
        self.assertEqual(stored[0].selected_letter, chosen.letter)
        self.assertEqual(stored[0].saved_at, saved_at)
        self.assertEqual(written_exam_service.unanswered_count(exam.id), 2)
        snapshot_answers = test_exam_service.get_written_answers(first.exam_question_id)
        matched = next(
            answer for answer in snapshot_answers if answer.id == stored[0].exam_answer_id
        )
        self.assertEqual(matched.letter, chosen.letter)

        written_exam_service.save_choice(
            exam.id,
            first.exam_question_id,
            replacement.exam_answer_id,
            now=saved_at + timedelta(seconds=2),
        )
        updated = written_exam_service.choices(exam.id)
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].exam_answer_id, replacement.exam_answer_id)
        self.assertEqual(updated[0].selected_letter, replacement.letter)
        self.assertIsNone(
            written_exam_service.screen(exam.id).questions[1].selected_exam_answer_id
        )
        self.assertEqual(second.exam_question_id, screen.questions[1].exam_question_id)
        self.assertEqual(_fingerprint(exam.id), before)
        self.assertEqual(_count(TestExamWrittenQuestion), question_count)
        self.assertEqual(_count(TestExamWrittenAnswer), answer_count)

    def test_submit_and_expiry_close_written_part_without_completing_exam(self) -> None:
        employee = _employee("81003", "Eva", "Krátká")
        _topic, test = _written_test("Odevzdání", ["Jedna", "Dvě"], seconds=30)
        exam = _prepare(employee.id, test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        screen = written_exam_service.screen(exam.id)
        written_exam_service.save_choice(
            exam.id,
            screen.questions[0].exam_question_id,
            screen.questions[0].options[0].exam_answer_id,
            now=_STARTED + timedelta(seconds=3),
        )
        submitted_at = _STARTED + timedelta(seconds=20)
        reason = written_exam_service.submit(exam.id, now=submitted_at)
        self.assertEqual(reason, "submitted")
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.status, EXAM_STATUS_STARTED)
        self.assertNotEqual(fresh.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(fresh.written_finish_reason, "submitted")
        self.assertEqual(fresh.written_finished_at, submitted_at)
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam.id,
                screen.questions[1].exam_question_id,
                screen.questions[1].options[0].exam_answer_id,
                now=submitted_at + timedelta(seconds=1),
            )
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.submit(exam.id, now=submitted_at + timedelta(seconds=1))
        self.assertEqual(len(written_exam_service.choices(exam.id)), 1)
        self.assertEqual(
            test_exam_service.get_exam(exam.id).written_finished_at,
            submitted_at,
        )

        employee_b = _employee("81004", "Adam", "Dlouhý")
        _topic_b, test_b = _written_test("Čas", ["Hodiny"], seconds=30)
        timed = _prepare(employee_b.id, test_b.id)
        written_exam_service.start(timed.id, now=_STARTED)
        card = written_exam_service.screen(timed.id).questions[0]
        deadline = _STARTED + timedelta(seconds=30)
        self.assertEqual(
            written_exam_service.sync_deadline(
                timed.id,
                now=deadline - timedelta(seconds=1),
            ),
            "",
        )
        self.assertEqual(
            written_exam_service.sync_deadline(timed.id, now=deadline),
            "expired",
        )
        expired = test_exam_service.get_exam(timed.id)
        assert expired is not None
        self.assertEqual(expired.status, EXAM_STATUS_STARTED)
        self.assertEqual(expired.written_finish_reason, "expired")
        self.assertEqual(expired.written_finished_at, deadline)
        later = deadline + timedelta(seconds=15)
        self.assertEqual(written_exam_service.sync_deadline(timed.id, now=later), "expired")
        self.assertEqual(test_exam_service.get_exam(timed.id).written_finished_at, deadline)
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                timed.id,
                card.exam_question_id,
                card.options[0].exam_answer_id,
                now=later,
            )
        self.assertEqual(written_exam_service.choices(timed.id), [])
        self.assertEqual(remaining_written_seconds(_STARTED, 30, later), 0)

    def test_late_answer_expires_part_and_keeps_snapshot_images(self) -> None:
        employee = _employee("81005", "Iva", "Obrazová")
        topic = written_question_topic_service.create_topic(name="SKRYTY_OKRUH_obraz")
        question_image = _png(self.images / "zadani.png", (10, 20, 30), (1000, 100))
        paths = [
            _png(self.images / "a.png", (200, 0, 0), (800, 200)),
            _png(self.images / "b.png", (0, 200, 0), (800, 200)),
            _png(self.images / "c.png", (0, 0, 200), (800, 200)),
        ]
        written_question_service.create_question(
            topic_id=topic.id,
            text="Vyberte značku",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(paths[0]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(paths[1])),
                WrittenAnswerInput(image_source_path=str(paths[2])),
            ],
            question_image_source_path=str(question_image),
            note="INTERNI_POZNAMKA_8",
        )
        test = test_definition_service.create_test(
            name="Obrázkový test",
            uses_written=True,
            seconds_per_question=20,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = _prepare(employee.id, test.id)
        frozen = _fingerprint(exam.id)
        written_exam_service.start(exam.id, now=_STARTED)
        screen = written_exam_service.screen(exam.id)
        card = screen.questions[0]
        self.assertTrue(card.image_stored_path)
        self.assertTrue(all(option.image_stored_path for option in card.options))
        self.assertNotIn("is_correct", card.__dataclass_fields__)
        snapshot = test_exam_service.get_written_questions(exam.id)[0]
        self.assertEqual(card.image_stored_path, snapshot.image_stored_path)
        self.assertEqual(
            card.options[0].image_stored_path,
            test_exam_service.get_written_answers(snapshot.id)[0].image_stored_path,
        )
        past = _STARTED + timedelta(seconds=20)
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam.id,
                card.exam_question_id,
                card.options[0].exam_answer_id,
                now=past,
            )
        self.assertEqual(test_exam_service.get_exam(exam.id).written_finish_reason, "expired")
        self.assertEqual(written_exam_service.choices(exam.id), [])
        self.assertEqual(_fingerprint(exam.id), frozen)

        replacement = _png(self.images / "zadani-nove.png", (1, 2, 3), (20, 20))
        bank = written_question_service.list_questions(include_inactive=True, topic_id=topic.id)[0]
        written_question_service.update_question(
            bank.id,
            topic_id=topic.id,
            text="Jiná značka",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(replacement), is_correct=True),
                WrittenAnswerInput(image_source_path=str(replacement)),
                WrittenAnswerInput(image_source_path=str(replacement)),
            ],
            question_image_source_path=str(replacement),
        )
        again = written_exam_service.screen(exam.id).questions[0]
        self.assertEqual(again.text, "Vyberte značku")
        self.assertEqual(again.image_stored_path, snapshot.image_stored_path)
        self.assertEqual(_fingerprint(exam.id), frozen)

    def test_start_button_confirmation_and_fullscreen_window(self) -> None:
        employee = _employee("81006", "Jana", "Malá")
        _topic, test = _written_test("Potvrzení", ["Jedna", "Dvě"], seconds=45)
        exam = _prepare(employee.id, test.id)
        oral_topic = oral_question_topic_service.create_topic(name="Ústní tlačítko")
        oral_question_service.create_question(topic_id=oral_topic.id, text="Řekněte")
        oral_test = test_definition_service.create_test(
            name="Bez písemné",
            uses_oral=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        oral_exam = _prepare(employee.id, oral_test.id)
        tab = TestExamsTab()
        self.assertFalse(tab.start_btn.isEnabled())
        self.assertEqual(tab.start_btn.text(), "Zahájit elektronický test")
        self._select_named(tab, "Potvrzení")
        self.assertTrue(tab.start_btn.isEnabled())
        self.assertTrue(tab.detail_btn.isEnabled())
        self._select_named(tab, "Bez písemné")
        self.assertFalse(tab.start_btn.isEnabled())
        self._select_named(tab, "Potvrzení")
        tab.table.selectionModel().select(
            tab.table.model().index(self._row_named(tab, "Bez písemné"), 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        self.assertIsNone(tab.table.selected_exam_id())
        self.assertFalse(tab.start_btn.isEnabled())
        self.assertFalse(tab.detail_btn.isEnabled())

        self._select_named(tab, "Potvrzení")
        with patch(
            "moduly.testy.ui.test_exams_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            tab.start_electronic_test()
        message = question.call_args.args[2]
        self.assertIn("Jana Malá", message)
        self.assertIn("Potvrzení", message)
        self.assertIn("Počet písemných otázek: 2", message)
        self.assertIn("Časový limit: 01:30", message)
        self.assertEqual(test_exam_service.get_exam(exam.id).status, EXAM_STATUS_PREPARED)
        self.assertIsNone(tab._written_exam_window)

        with patch(
            "moduly.testy.ui.test_exams_tab.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            tab.start_electronic_test()
        window = tab._written_exam_window
        assert window is not None
        self._watch(window)
        self.assertTrue(window.windowState() & Qt.WindowState.WindowFullScreen)
        self.assertEqual(window.windowModality(), Qt.WindowModality.ApplicationModal)
        self.assertEqual(test_exam_service.get_exam(exam.id).status, EXAM_STATUS_STARTED)
        self.assertIsNotNone(test_exam_service.get_exam(exam.id).written_started_at)
        self.assertNotIn("PROVOZ_TAJNY", _visible_text(window))
        self.assertNotIn("INTERNI", _visible_text(window))
        self.assertNotIn("test_exam", _visible_text(window))
        self._select_named(tab, "Potvrzení")
        self.assertEqual(tab.start_btn.text(), "Pokračovat v elektronickém testu")
        self.assertTrue(tab.start_btn.isEnabled())
        self.assertEqual(oral_exam.status, EXAM_STATUS_PREPARED)

    def test_testing_screen_navigation_answers_and_submit(self) -> None:
        employee = _employee("81007", "Klára", "Nová")
        _topic, test = _written_test(
            "Obrazovka",
            ["První zadání", "Druhé zadání", "Třetí zadání"],
            seconds=120,
            note="INTERNI_POZNAMKA_8",
        )
        exam = _prepare(employee.id, test.id)
        clock = FixedWrittenExamClock(_STARTED)
        written_exam_service.start(exam.id, now=_STARTED)
        screen = written_exam_service.screen(exam.id)
        window = self._watch(WrittenExamWindow(exam.id, clock=clock))
        window.show_at(1600, 900)
        self.assertEqual(window.title_label.text(), "Obrazovka")
        self.assertIn("Klára Nová", window.employee_label.text())
        self.assertEqual(window.remaining_label.text(), "Zbývá: 06:00")
        self.assertEqual(
            window.findChild(QLabel, "written-exam-question-text").text(),
            screen.questions[0].text,
        )
        self.assertFalse(window.prev_button.isEnabled())
        self.assertTrue(window.next_button.isEnabled())
        self.assertIsNone(window.findChild(QPushButton, "written-exam-dev-exit"))
        visible = _visible_text(window)
        self.assertNotIn("(správná)", visible)
        self.assertNotIn("INTERNI_POZNAMKA_8", visible)
        self.assertNotIn("SKRYTY_OKRUH", visible)
        self.assertNotIn("PROVOZ_TAJNY", visible)
        self.assertNotIn("Vyhověl", visible)
        self.assertNotIn("Nevyhověl", visible)

        first = screen.questions[0]
        self._choose(window, first.options[0].letter)
        self.assertEqual(len(written_exam_service.choices(exam.id)), 1)
        self._choose(window, first.options[1].letter)
        stored = written_exam_service.choices(exam.id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].selected_letter, first.options[1].letter)

        window.next_button.click()
        self.assertEqual(window._index, 1)
        self.assertEqual(
            window.findChild(QLabel, "written-exam-question-text").text(),
            screen.questions[1].text,
        )
        self.assertEqual(
            window.findChild(QPushButton, "written-exam-nav-1").property("answered"),
            "true",
        )
        self.assertEqual(
            window.findChild(QPushButton, "written-exam-nav-1").property("current"),
            "false",
        )
        current_nav = window.findChild(
            QPushButton,
            f"written-exam-nav-{screen.questions[1].position}",
        )
        self.assertEqual(current_nav.property("current"), "true")
        self.assertEqual(current_nav.property("answered"), "false")
        window.findChild(QPushButton, "written-exam-nav-1").click()
        self.assertEqual(window._index, 0)
        checked = window.findChild(
            QRadioButton,
            f"written-exam-answer-{first.options[1].letter}",
        )
        self.assertTrue(checked.isChecked())

        window._jump(len(screen.questions) - 1)
        self.assertFalse(window.next_button.isEnabled())
        window._go_next()
        self.assertEqual(window._index, len(screen.questions) - 1)
        window._jump(0)
        self.assertFalse(window.prev_button.isEnabled())
        window._go_previous()
        self.assertEqual(window._index, 0)

        with patch(
            "moduly.testy.ui.written_exam_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            window.submit_test()
        self.assertEqual(question.call_args.args[2], WRITTEN_SUBMIT_INCOMPLETE)
        self.assertEqual(window._phase, "running")
        self.assertEqual(test_exam_service.get_exam(exam.id).written_finish_reason, "")

        for card in written_exam_service.screen(exam.id).questions:
            if card.selected_exam_answer_id is None:
                window._jump(card.position - 1)
                self._choose(window, card.options[0].letter)
        with patch(
            "moduly.testy.ui.written_exam_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as confirm:
            window.submit_test()
        self.assertEqual(confirm.call_args.args[2], WRITTEN_SUBMIT_CONFIRM)
        finished = test_exam_service.get_exam(exam.id)
        assert finished is not None
        self.assertEqual(finished.status, EXAM_STATUS_STARTED)
        self.assertEqual(finished.written_finish_reason, "submitted")
        self.assertIsNotNone(finished.written_finished_at)
        label = window.findChild(QLabel, "written-exam-finished")
        self.assertEqual(label.text(), WRITTEN_FINISHED_TEXT)
        self.assertTrue(label.isVisible())
        self.assertFalse(window.findChild(QLabel, "written-exam-question-text").isVisible())
        self.assertFalse(window.submit_button.isVisible())
        after = _visible_text(window)
        self.assertNotIn("Vyhověl", after)
        self.assertNotIn("Nevyhověl", after)
        self.assertNotIn("(správná)", after)
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam.id,
                first.exam_question_id,
                first.options[0].exam_answer_id,
                now=_STARTED + timedelta(seconds=10),
            )

    def test_clock_jump_expires_without_granting_time(self) -> None:
        employee = _employee("81008", "Nora", "Časová")
        _topic, test = _written_test("Limit", ["Jedna otázka"], seconds=60)
        exam = _prepare(employee.id, test.id)
        clock = FixedWrittenExamClock(_STARTED)
        written_exam_service.start(exam.id, now=_STARTED)
        clock.set(_STARTED + timedelta(seconds=10))
        window = self._watch(WrittenExamWindow(exam.id, clock=clock))
        window.show_at(1920, 1080)
        self.assertEqual(window.remaining_label.text(), "Zbývá: 00:50")
        clock.set(_STARTED + timedelta(seconds=40))
        window._on_tick()
        self.assertEqual(window.remaining_label.text(), "Zbývá: 00:20")
        clock.set(_STARTED + timedelta(seconds=70))
        window._on_tick()
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.written_finish_reason, "expired")
        self.assertEqual(fresh.written_finished_at, _STARTED + timedelta(seconds=70))
        self.assertEqual(fresh.status, EXAM_STATUS_STARTED)
        self.assertEqual(
            window.findChild(QLabel, "written-exam-finished").text(),
            WRITTEN_FINISHED_TEXT,
        )
        self.assertFalse(window.findChild(QRadioButton, "written-exam-answer-A").isVisible())

    def test_escape_and_close_do_not_leave_testing_mode(self) -> None:
        employee = _employee("81009", "Ota", "Zámek")
        _topic, test = _written_test("Zámek", ["Otázka"], seconds=60)
        exam = _prepare(employee.id, test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        window = self._watch(
            WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        window.show_at(1600, 900)
        QTest.keyClick(window, Qt.Key.Key_Escape)
        window.reject()
        window.close()
        QApplication.processEvents()
        self.assertTrue(window.isVisible())
        self.assertEqual(window._phase, "running")
        self.assertEqual(test_exam_service.get_exam(exam.id).written_finish_reason, "")
        self.assertIsNone(window.findChild(QPushButton, "written-exam-dev-exit"))

        with patch.dict(os.environ, {WRITTEN_EXAM_DEV_EXIT_ENV: "1"}):
            dev_window = self._watch(
                WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
            )
        button = dev_window.findChild(QPushButton, "written-exam-dev-exit")
        assert button is not None
        self.assertEqual(button.text(), "Vývojové opuštění")
        dev_window.show()
        button.click()
        self.assertFalse(dev_window.isVisible())

    def test_layout_keeps_navigation_on_target_resolutions(self) -> None:
        employee = _employee("81010", "Pavel", "Dlouhý")
        topic = written_question_topic_service.create_topic(name="SKRYTY_OKRUH_layout")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Dlouhý text otázky. " * 80,
            answer_kind=ANSWER_KIND_TEXT,
            answers=[
                WrittenAnswerInput(text="odpověď " * 30, is_correct=True),
                WrittenAnswerInput(text="další " * 30),
                WrittenAnswerInput(text="poslední " * 30),
            ],
        )
        test = test_definition_service.create_test(
            name="Dlouhý test",
            uses_written=True,
            seconds_per_question=90,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = _prepare(employee.id, test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        window = self._watch(
            WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        for width, height in ((1600, 900), (1920, 1080)):
            window.show_at(width, height)
            self.assertLessEqual(window.height(), height)
            self.assertGreaterEqual(window.width(), width - 2)
            for name in (
                "written-exam-prev",
                "written-exam-next",
                "written-exam-submit",
                "written-exam-remaining",
                "written-exam-nav-1",
            ):
                widget = window.findChild(QPushButton, name) or window.findChild(QLabel, name)
                assert widget is not None
                self.assertTrue(widget.isVisible(), name)
                bottom_right = widget.mapTo(window, widget.rect().bottomRight())
                top_left = widget.mapTo(window, widget.rect().topLeft())
                self.assertGreaterEqual(top_left.y(), 0, name)
                self.assertLessEqual(bottom_right.y(), window.height(), name)
                self.assertLessEqual(bottom_right.x(), window.width(), name)

    def test_screen_uses_snapshot_images_without_distortion(self) -> None:
        employee = _employee("81011", "Rita", "Obrázková")
        topic = written_question_topic_service.create_topic(name="SKRYTY_OKRUH_pomer")
        question_image = _png(self.images / "pomer-zadani.png", (8, 8, 8), (1000, 100))
        answers = [
            _png(self.images / "pomer-a.png", (180, 0, 0), (800, 200)),
            _png(self.images / "pomer-b.png", (0, 180, 0), (800, 200)),
            _png(self.images / "pomer-c.png", (0, 0, 180), (800, 200)),
        ]
        written_question_service.create_question(
            topic_id=topic.id,
            text="Značka v zadání",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(answers[0]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(answers[1])),
                WrittenAnswerInput(image_source_path=str(answers[2])),
            ],
            question_image_source_path=str(question_image),
        )
        text_topic = written_question_topic_service.create_topic(name="SKRYTY_OKRUH_text")
        text_image = _png(self.images / "text-zadani.png", (4, 4, 4), (640, 200))
        written_question_service.create_question(
            topic_id=text_topic.id,
            text="Text a obrázek zadání",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(text_image),
        )
        image_test = test_definition_service.create_test(
            name="Poměr",
            uses_written=True,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        exam = _prepare(employee.id, image_test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        snapshot = test_exam_service.get_written_questions(exam.id)[0]
        window = self._watch(
            WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        window.show_at(1600, 900)
        question_label = window.findChild(QLabel, "written-exam-question-image")
        assert question_label is not None
        self.assertEqual(question_label.property("snapshotPath"), snapshot.image_stored_path)
        pixmap = question_label.pixmap()
        self.assertFalse(pixmap.isNull())
        self.assertAlmostEqual(pixmap.width() / pixmap.height(), 10, delta=0.2)
        self.assertLess(pixmap.height(), 400)
        for letter in ("A", "B", "C"):
            image = window.findChild(QLabel, f"written-exam-answer-image-{letter}")
            assert image is not None
            self.assertFalse(image.pixmap().isNull())
            self.assertAlmostEqual(image.pixmap().width() / image.pixmap().height(), 4, delta=0.2)
            stored = next(
                answer.image_stored_path
                for answer in test_exam_service.get_written_answers(snapshot.id)
                if answer.letter == letter
            )
            self.assertEqual(image.property("snapshotPath"), stored)
        self.assertNotIn("(správná)", _visible_text(window))

        text_test = test_definition_service.create_test(
            name="Textové volby",
            uses_written=True,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(text_topic.id, 1)],
        )
        text_exam = _prepare(employee.id, text_test.id)
        written_exam_service.start(text_exam.id, now=_STARTED)
        text_window = self._watch(
            WrittenExamWindow(text_exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        text_window.show_at(1600, 900)
        self.assertIsNotNone(text_window.findChild(QLabel, "written-exam-question-image"))
        self.assertIsNotNone(text_window.findChild(QLabel, "written-exam-answer-text-A"))
        self.assertIsNone(text_window.findChild(QLabel, "written-exam-answer-image-A"))

    def test_definition_editor_opens_maximized(self) -> None:
        tab = TestDefinitionsTab()
        seen: dict = {}

        def fake_exec(dialog):
            seen["state"] = dialog.windowState()
            seen["title"] = dialog.windowTitle()
            seen["has_name"] = hasattr(dialog, "name")
            dialog.close()
            return 0

        with patch(
            "moduly.testy.ui.test_definitions_tab.exec_maximized",
            side_effect=fake_exec,
        ) as mocked:
            tab.new_test()
        mocked.assert_called_once()
        self.assertTrue(seen["state"] & Qt.WindowState.WindowMaximized)
        self.assertEqual(seen["title"], TEST_DIALOG_TITLE_NEW)
        self.assertTrue(seen["has_name"])

        _topic, test = _written_test("Editor", ["Otázka editoru"])
        tab.refresh()
        self._select_named_table(tab.table, test.name, name_column=1)
        with patch(
            "moduly.testy.ui.test_definitions_tab.exec_maximized",
            side_effect=fake_exec,
        ):
            tab.edit_selected()
        self.assertEqual(seen["title"], TEST_DIALOG_TITLE_EDIT)
        self.assertTrue(seen["state"] & Qt.WindowState.WindowMaximized)

        dialog = TestDefinitionDialog()
        try:
            with patch.object(QDialog, "exec", return_value=0):
                self.assertEqual(exec_maximized(dialog), 0)
            self.assertTrue(dialog.windowState() & Qt.WindowState.WindowMaximized)
        finally:
            dialog.close()

    def test_manager_lock_hides_navigation_and_ignores_close(self) -> None:
        window = MainWindow()
        try:
            window.show()
            QApplication.processEvents()
            window.set_electronic_exam_lock(True)
            self.assertFalse(window._sidebar_panel.isVisible())
            self.assertFalse(window._main_toolbar.isVisible())
            self.assertFalse(window._global_search_shortcut.isEnabled())
            self.assertIs(window._workspace_stack.currentWidget(), window._exam_cover)
            window._show("testy")
            self.assertIs(window._workspace_stack.currentWidget(), window._exam_cover)
            window.close()
            QApplication.processEvents()
            self.assertTrue(window.isVisible())
            QTest.keyClick(window, Qt.Key.Key_Escape)
            self.assertTrue(window._electronic_exam_locked)
        finally:
            window.set_electronic_exam_lock(False)
            window.deleteLater()
            QApplication.processEvents()

    def _choose(self, window: WrittenExamWindow, letter: str) -> None:
        radio = window.findChild(QRadioButton, f"written-exam-answer-{letter}")
        assert radio is not None
        radio.click()

    def _row_named(self, tab: TestExamsTab, name: str) -> int:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, EXAM_COL_TEST)
            if item is not None and item.text() == name:
                return row
        raise AssertionError(name)

    def _select_named(self, tab: TestExamsTab, name: str) -> None:
        tab.table.selectRow(self._row_named(tab, name))

    def _select_named_table(self, table, name: str, *, name_column: int) -> None:
        for row in range(table.rowCount()):
            item = table.item(row, name_column)
            if item is not None and item.text() == name:
                table.selectRow(row)
                return
        raise AssertionError(name)


if __name__ == "__main__":
    unittest.main()
