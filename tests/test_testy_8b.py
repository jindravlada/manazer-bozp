"""TESTY-8b: pokračování přerušeného testu a návrat po ukončení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
)
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-8b-"))

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
    from core.windows.main_window import MainWindow
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        AGENDA_EXAMS,
        ANSWER_KIND_TEXT,
        EXAM_ACTION_CONTINUE_WRITTEN,
        EXAM_ACTION_START_WRITTEN,
        EXAM_COL_TEST,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_FINISH_EXPIRED,
        WRITTEN_FINISH_SUBMITTED,
        WRITTEN_HANDOVER_TEXT,
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
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import TestExamError, test_exam_service
    from moduly.testy.sluzby.written_exam_service import (
        FixedWrittenExamClock,
        WrittenExamClosed,
        electronic_written_action,
        is_written_part_in_progress,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.test_exams_tab import TestExamsTab
    from moduly.testy.ui.written_exam_window import WrittenExamWindow


_APP = QApplication.instance() or QApplication([])
_STARTED = datetime(2026, 10, 6, 10, 0, 0)


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


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


def _written_test(name: str, texts: list[str], *, seconds: int):
    topic = written_question_topic_service.create_topic(name=f"SKRYTY_OKRUH_{name}")
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
        allowed_wrong_answers=0,
        seconds_per_question=seconds,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic.id, len(texts))],
    )
    return test


def _prepare(employee_id: int, test_id: int):
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=test_id,
        exam_date=_STARTED.date(),
        rng=PrefixReverse(),
    )


def _layout(exam_id: int):
    rows = []
    for question in test_exam_service.get_written_questions(exam_id):
        answers = tuple(
            (
                answer.id,
                answer.position,
                answer.letter,
                answer.text,
                answer.image_stored_path,
                answer.image_sha256,
            )
            for answer in test_exam_service.get_written_answers(question.id)
        )
        rows.append(
            (
                question.id,
                question.position,
                question.text,
                question.image_stored_path,
                question.image_sha256,
                answers,
            )
        )
    return tuple(rows)


def _choices(exam_id: int):
    return tuple(
        (choice.exam_question_id, choice.exam_answer_id, choice.selected_letter)
        for choice in written_exam_service.choices(exam_id)
    )


class WrittenResumeRulesTestCase(unittest.TestCase):
    def test_in_progress_is_started_without_finish(self) -> None:
        started = _STARTED
        self.assertTrue(
            is_written_part_in_progress(EXAM_STATUS_STARTED, started, None, "")
        )
        self.assertTrue(
            is_written_part_in_progress(EXAM_STATUS_STARTED, started, None, None)
        )
        self.assertFalse(
            is_written_part_in_progress(EXAM_STATUS_PREPARED, None, None, "")
        )
        self.assertFalse(
            is_written_part_in_progress(
                EXAM_STATUS_STARTED,
                started,
                started,
                WRITTEN_FINISH_SUBMITTED,
            )
        )
        self.assertFalse(
            is_written_part_in_progress(
                EXAM_STATUS_STARTED,
                started,
                started,
                WRITTEN_FINISH_EXPIRED,
            )
        )
        self.assertEqual(
            electronic_written_action(
                status=EXAM_STATUS_PREPARED,
                uses_written=True,
                question_count=2,
                written_started_at=None,
                written_finished_at=None,
                written_finish_reason="",
            ),
            "start",
        )
        self.assertEqual(
            electronic_written_action(
                status=EXAM_STATUS_STARTED,
                uses_written=True,
                question_count=2,
                written_started_at=started,
                written_finished_at=None,
                written_finish_reason="",
            ),
            "continue",
        )
        self.assertEqual(
            electronic_written_action(
                status=EXAM_STATUS_STARTED,
                uses_written=True,
                question_count=2,
                written_started_at=started,
                written_finished_at=started,
                written_finish_reason=WRITTEN_FINISH_SUBMITTED,
            ),
            "",
        )
        self.assertEqual(
            electronic_written_action(
                status=EXAM_STATUS_STARTED,
                uses_written=True,
                question_count=2,
                written_started_at=started,
                written_finished_at=started,
                written_finish_reason=WRITTEN_FINISH_EXPIRED,
            ),
            "",
        )


class WrittenResumeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._open: list[WrittenExamWindow] = []
        self._mains: list[MainWindow] = []
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
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.execute(delete(Attachment))
            session.commit()

    def tearDown(self) -> None:
        for window in self._open:
            window.release_testing_lock()
        for main in self._mains:
            main.set_electronic_exam_lock(False)
            main.close()
            main.deleteLater()
        QApplication.processEvents()

    def _watch(self, window: WrittenExamWindow) -> WrittenExamWindow:
        self._open.append(window)
        return window

    def _select(self, tab: TestExamsTab, name: str) -> None:
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, EXAM_COL_TEST)
            if item is not None and item.text() == name:
                tab.table.selectRow(row)
                return
        raise AssertionError(name)

    def _handover(self, parent):
        dialog = parent.findChild(QMessageBox, "written-exam-handover")
        assert dialog is not None
        self.assertEqual(dialog.text(), WRITTEN_HANDOVER_TEXT)
        self.assertIn("Předejte počítač zkoušejícímu.", dialog.text())
        self.assertEqual(dialog.standardButtons(), QMessageBox.StandardButton.Ok)
        self.assertNotIn("Vyhověl", dialog.text())
        self.assertNotIn("Nevyhověl", dialog.text())
        self.assertNotIn("správn", dialog.text().casefold())
        self.assertNotIn("pin", dialog.text().casefold())
        return dialog

    def _accept(self, dialog: QMessageBox) -> None:
        button = dialog.button(QMessageBox.StandardButton.Ok)
        assert button is not None
        self.assertEqual(button.text().casefold(), "ok")
        button.click()
        QTest.qWait(30)
        QApplication.processEvents()

    def test_button_switches_between_start_and_continue(self) -> None:
        employee = _employee("82001", "Iva", "Nová")
        prepared = _prepare(
            employee.id,
            _written_test("Připravený", ["Otázka"], seconds=60).id,
        )
        running_test = _written_test("Rozpracovaný", ["První", "Druhá"], seconds=60)
        running = _prepare(employee.id, running_test.id)
        written_exam_service.start(running.id, now=datetime.now())
        submitted = _prepare(
            employee.id,
            _written_test("Odevzdaný", ["Otázka"], seconds=60).id,
        )
        written_exam_service.start(submitted.id, now=_STARTED)
        written_exam_service.submit(submitted.id, now=_STARTED + timedelta(seconds=10))
        expired = _prepare(
            employee.id,
            _written_test("Vypršelý", ["Otázka"], seconds=60).id,
        )
        written_exam_service.start(expired.id, now=_STARTED)
        written_exam_service.sync_deadline(
            expired.id,
            now=_STARTED + timedelta(seconds=120),
        )

        tab = TestExamsTab()
        self.assertFalse(tab.start_btn.isEnabled())
        self.assertEqual(tab.start_btn.text(), EXAM_ACTION_START_WRITTEN)

        self._select(tab, "Připravený")
        self.assertEqual(tab.start_btn.text(), EXAM_ACTION_START_WRITTEN)
        self.assertTrue(tab.start_btn.isEnabled())
        self.assertTrue(written_exam_service.can_start(prepared.id))
        self.assertFalse(written_exam_service.can_continue(prepared.id))

        self._select(tab, "Rozpracovaný")
        self.assertEqual(tab.start_btn.text(), EXAM_ACTION_CONTINUE_WRITTEN)
        self.assertTrue(tab.start_btn.isEnabled())
        self.assertTrue(written_exam_service.can_continue(running.id))
        self.assertFalse(written_exam_service.can_start(running.id))
        started_at = test_exam_service.get_exam(running.id).written_started_at
        frozen = _layout(running.id)
        exams_before = _count(TestExam)
        with patch.object(written_exam_service, "start") as start:
            tab.start_electronic_test()
        start.assert_not_called()
        opened = tab._written_exam_window
        assert opened is not None
        self._watch(opened)
        self.assertEqual(opened.exam_id, running.id)
        self.assertEqual(test_exam_service.get_exam(running.id).written_started_at, started_at)
        self.assertEqual(_layout(running.id), frozen)
        self.assertEqual(_count(TestExam), exams_before)
        opened.release_testing_lock()

        for name, exam_id in (("Odevzdaný", submitted.id), ("Vypršelý", expired.id)):
            self._select(tab, name)
            self.assertFalse(tab.start_btn.isEnabled(), name)
            self.assertFalse(written_exam_service.can_start(exam_id), name)
            self.assertFalse(written_exam_service.can_continue(exam_id), name)
            with self.assertRaises(TestExamError):
                written_exam_service.resume(exam_id, now=datetime.now())

    def test_continue_keeps_snapshot_order_answers_and_clock(self) -> None:
        employee = _employee("82002", "Petr", "Pokračující")
        test = _written_test(
            "Pokračování",
            ["První zadání", "Druhé zadání", "Třetí zadání"],
            seconds=300,
        )
        exam = _prepare(employee.id, test.id)
        exams_before = _count(TestExam)
        questions_before = _count(TestExamWrittenQuestion)
        written_exam_service.start(exam.id, now=_STARTED)
        frozen = _layout(exam.id)
        screen = written_exam_service.screen(exam.id)
        first, second, third = screen.questions
        written_exam_service.save_choice(
            exam.id,
            first.exam_question_id,
            first.options[1].exam_answer_id,
            now=_STARTED + timedelta(seconds=30),
        )
        written_exam_service.save_choice(
            exam.id,
            third.exam_question_id,
            third.options[0].exam_answer_id,
            now=_STARTED + timedelta(seconds=40),
        )
        stored_choices = _choices(exam.id)
        resumed_at = _STARTED + timedelta(minutes=8)
        with patch.object(written_exam_service, "start") as start:
            reason = written_exam_service.resume(exam.id, now=resumed_at)
        start.assert_not_called()
        self.assertEqual(reason, "")
        fresh = test_exam_service.get_exam(exam.id)
        assert fresh is not None
        self.assertEqual(fresh.status, EXAM_STATUS_STARTED)
        self.assertEqual(fresh.written_started_at, _STARTED)
        self.assertEqual(fresh.written_duration_seconds, 900)
        self.assertIsNone(fresh.written_finished_at)
        self.assertEqual(fresh.written_finish_reason, "")
        self.assertEqual(_count(TestExam), exams_before)
        self.assertEqual(_count(TestExamWrittenQuestion), questions_before)
        self.assertEqual(_layout(exam.id), frozen)
        self.assertEqual(_choices(exam.id), stored_choices)

        clock = FixedWrittenExamClock(resumed_at)
        window = self._watch(WrittenExamWindow(exam.id, clock=clock))
        window.show_at(1600, 900)
        self.assertEqual(window.remaining_label.text(), "Zbývá: 07:00")
        self.assertEqual(
            [question.exam_question_id for question in window._screen.questions],
            [first.exam_question_id, second.exam_question_id, third.exam_question_id],
        )
        self.assertEqual(
            [
                tuple(option.letter for option in question.options)
                for question in window._screen.questions
            ],
            [
                tuple(option.letter for option in question.options)
                for question in (first, second, third)
            ],
        )
        self.assertEqual(
            window.findChild(QPushButton, "written-exam-nav-1").property("answered"),
            "true",
        )
        self.assertEqual(
            window.findChild(QPushButton, "written-exam-nav-2").property("answered"),
            "false",
        )
        self.assertEqual(
            window.findChild(QPushButton, "written-exam-nav-3").property("answered"),
            "true",
        )
        chosen = window.findChild(
            QRadioButton,
            f"written-exam-answer-{first.options[1].letter}",
        )
        assert chosen is not None
        self.assertTrue(chosen.isChecked())
        window._jump(1)
        for option in second.options:
            radio = window.findChild(QRadioButton, f"written-exam-answer-{option.letter}")
            assert radio is not None
            self.assertFalse(radio.isChecked())
        window._jump(0)
        replacement = window.findChild(
            QRadioButton,
            f"written-exam-answer-{first.options[2].letter}",
        )
        assert replacement is not None
        replacement.click()
        updated = written_exam_service.choices(exam.id)
        self.assertEqual(len(updated), 2)
        changed = next(
            choice for choice in updated if choice.exam_question_id == first.exam_question_id
        )
        self.assertEqual(changed.selected_letter, first.options[2].letter)
        self.assertEqual(changed.exam_answer_id, first.options[2].exam_answer_id)
        self.assertEqual(_layout(exam.id), frozen)
        self.assertEqual(test_exam_service.get_exam(exam.id).written_started_at, _STARTED)

        tab = TestExamsTab()
        self._select(tab, "Pokračování")
        self.assertEqual(tab.start_btn.text(), EXAM_ACTION_CONTINUE_WRITTEN)
        self.assertTrue(tab.start_btn.isEnabled())

    def test_gap_does_not_grant_time_and_expiry_finishes_without_answering(self) -> None:
        employee = _employee("82003", "Eva", "Přerušená")
        exam = _prepare(
            employee.id,
            _written_test("Pauza", ["Jedna otázka"], seconds=900).id,
        )
        written_exam_service.start(exam.id, now=_STARTED)
        screen = written_exam_service.screen(exam.id)
        question = screen.questions[0]
        written_exam_service.save_choice(
            exam.id,
            question.exam_question_id,
            question.options[0].exam_answer_id,
            now=_STARTED + timedelta(minutes=5),
        )
        frozen = _layout(exam.id)
        stored = _choices(exam.id)
        later = _STARTED + timedelta(minutes=8)
        self.assertEqual(written_exam_service.resume(exam.id, now=later), "")
        clock = FixedWrittenExamClock(later)
        window = self._watch(WrittenExamWindow(exam.id, clock=clock))
        window.show_at(1280, 800)
        self.assertEqual(window.remaining_label.text(), "Zbývá: 07:00")
        self.assertNotEqual(window.remaining_label.text(), "Zbývá: 10:00")
        self.assertEqual(test_exam_service.get_exam(exam.id).written_started_at, _STARTED)

        expired_at = _STARTED + timedelta(minutes=20)
        tab = TestExamsTab()
        self._select(tab, "Pauza")
        self.assertEqual(tab.start_btn.text(), EXAM_ACTION_CONTINUE_WRITTEN)
        self.assertIsNone(tab._written_exam_window)
        reason = written_exam_service.resume(exam.id, now=expired_at)
        self.assertEqual(reason, WRITTEN_FINISH_EXPIRED)
        finished = test_exam_service.get_exam(exam.id)
        assert finished is not None
        self.assertEqual(finished.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(finished.written_finish_reason, WRITTEN_FINISH_EXPIRED)
        self.assertEqual(finished.written_finished_at, expired_at)
        self.assertEqual(finished.written_started_at, _STARTED)
        self.assertEqual(_layout(exam.id), frozen)
        self.assertEqual(_choices(exam.id), stored)
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam.id,
                question.exam_question_id,
                question.options[1].exam_answer_id,
                now=expired_at,
            )

        tab.refresh()
        self._select(tab, "Pauza")
        self.assertFalse(tab.start_btn.isEnabled())

    def test_continue_after_real_gap_shows_handover_without_exam_window(self) -> None:
        employee = _employee("82004", "Adam", "Pozdě")
        exam = _prepare(
            employee.id,
            _written_test("Po pauze", ["Otázka"], seconds=60).id,
        )
        written_exam_service.start(exam.id, now=datetime.now() - timedelta(minutes=5))
        tab = TestExamsTab()
        self._select(tab, "Po pauze")
        self.assertTrue(tab.start_btn.isEnabled())
        with patch.object(written_exam_service, "start") as start:
            tab.start_electronic_test()
        start.assert_not_called()
        self.assertIsNone(tab._written_exam_window)
        dialog = self._handover(tab)
        finished = test_exam_service.get_exam(exam.id)
        assert finished is not None
        self.assertEqual(finished.written_finish_reason, WRITTEN_FINISH_EXPIRED)
        self.assertEqual(finished.status, EXAM_STATUS_COMPLETED)
        self._accept(dialog)
        self.assertFalse(tab.start_btn.isEnabled())
        self.assertEqual(tab.table.selected_exam_id(), exam.id)
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam.id,
                written_exam_service.screen(exam.id).questions[0].exam_question_id,
                written_exam_service.screen(exam.id).questions[0].options[0].exam_answer_id,
            )

    def test_submit_and_expiry_dialog_returns_to_manager(self) -> None:
        employee = _employee("82005", "Klára", "Předání")
        exam = _prepare(
            employee.id,
            _written_test("Předání", ["Jedna", "Druhá"], seconds=120).id,
        )
        moment = datetime.now().replace(microsecond=0)
        written_exam_service.start(exam.id, now=moment)
        main = MainWindow()
        self._mains.append(main)
        main.show()
        QApplication.processEvents()
        main._show("testy")
        page = main.current_page_widget()
        assert page is not None
        window = self._watch(
            WrittenExamWindow(
                exam.id,
                page.exams_tab,
                clock=FixedWrittenExamClock(moment),
            )
        )
        window.enter_testing_mode()
        QApplication.processEvents()
        self.assertFalse(main._sidebar_panel.isVisible())
        self.assertFalse(main._main_toolbar.isVisible())
        self.assertFalse(main._global_search_shortcut.isEnabled())
        with patch(
            "moduly.testy.ui.written_exam_window.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            window.submit_test()
        dialog = self._handover(window)
        self.assertTrue(window.isVisible())
        self.assertEqual(
            window.findChild(QLabel, "written-exam-finished").text(),
            "Písemná část testu byla ukončena.",
        )
        self._accept(dialog)
        self.assertFalse(window.isVisible())
        self.assertTrue(main._sidebar_panel.isVisible())
        self.assertTrue(main._main_toolbar.isVisible())
        self.assertTrue(main.search_edit.isVisible())
        self.assertTrue(main._global_search_shortcut.isEnabled())
        self.assertIsNot(main._workspace_stack.currentWidget(), main._exam_cover)
        self.assertIs(page.tabs.currentWidget(), page.exams_tab)
        self.assertEqual(page.tabs.tabText(page.tabs.currentIndex()), AGENDA_EXAMS)
        self.assertEqual(page.exams_tab.table.selected_exam_id(), exam.id)
        finished = test_exam_service.get_exam(exam.id)
        assert finished is not None
        self.assertEqual(finished.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(finished.written_finish_reason, WRITTEN_FINISH_SUBMITTED)
        self.assertFalse(page.exams_tab.start_btn.isEnabled())
        with self.assertRaises(WrittenExamClosed):
            written_exam_service.save_choice(
                exam.id,
                written_exam_service.screen(exam.id).questions[0].exam_question_id,
                written_exam_service.screen(exam.id).questions[0].options[1].exam_answer_id,
                now=moment + timedelta(seconds=5),
            )

        other = _prepare(
            employee.id,
            _written_test("Čas vypršel", ["Otázka"], seconds=30).id,
        )
        written_exam_service.start(other.id, now=moment)
        expired_window = self._watch(
            WrittenExamWindow(other.id, clock=FixedWrittenExamClock(moment))
        )
        expired_window.show_at(1280, 800)
        expired_window.clock.set(moment + timedelta(seconds=40))
        expired_window._on_tick()
        expired_dialog = self._handover(expired_window)
        self.assertTrue(expired_window.isVisible())
        self.assertEqual(
            test_exam_service.get_exam(other.id).written_finish_reason,
            WRITTEN_FINISH_EXPIRED,
        )
        self.assertEqual(test_exam_service.get_exam(other.id).status, EXAM_STATUS_COMPLETED)
        self._accept(expired_dialog)
        self.assertFalse(expired_window.isVisible())
        with self.assertRaises(WrittenExamClosed):
            card = written_exam_service.screen(other.id).questions[0]
            written_exam_service.save_choice(
                other.id,
                card.exam_question_id,
                card.options[0].exam_answer_id,
                now=moment + timedelta(seconds=41),
            )


if __name__ == "__main__":
    unittest.main()
