"""TESTY-8d: čitelnost a ovládání elektronického testu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
)
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-8d-"))

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
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_SUBMIT,
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
        written_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.written_exam_window import WrittenExamWindow


_APP = QApplication.instance() or QApplication([])
_STARTED = datetime(2026, 10, 6, 14, 0, 0)
_LONG_QUESTION = (
    "Při obsluze stroje zaměstnanec kontroluje kryty, zastavení a únikovou cestu. "
    * 4
).strip()


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první možnost odpovědi", is_correct=True),
        WrittenAnswerInput(text="druhá možnost odpovědi"),
        WrittenAnswerInput(text="třetí možnost odpovědi"),
    ]


def _png(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (800, 200), color).save(path, "PNG")
    return path


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


def _written_test(name: str, texts: list[str]):
    topic = written_question_topic_service.create_topic(name=f"Okruh {name}")
    for text in texts:
        written_question_service.create_question(
            topic_id=topic.id,
            text=text,
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
    return test_definition_service.create_test(
        name=name,
        uses_written=True,
        allowed_wrong_answers=0,
        seconds_per_question=60,
        examiner_mode=EXAMINER_MODE_NONE,
        validity_value=1,
        validity_unit=VALIDITY_UNIT_YEARS,
        written_topics=[TestTopicQuota(topic.id, len(texts))],
    )


def _prepare(employee_id: int, test_id: int):
    return test_exam_service.prepare_exam(
        employee_id=employee_id,
        test_id=test_id,
        exam_date=_STARTED.date(),
        rng=PrefixReverse(),
    )


class WrittenExamReadabilityTestCase(unittest.TestCase):
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
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.execute(delete(Attachment))
            session.commit()

    def tearDown(self) -> None:
        for window in self._open:
            window.release_testing_lock()
        QApplication.processEvents()

    def test_answered_question_uses_neutral_mark_and_readable_text(self) -> None:
        window = self._window(
            "84001",
            "Čitelnost",
            [_LONG_QUESTION, "Druhá otázka", "Třetí otázka"],
        )
        long_index = next(
            index
            for index, card in enumerate(window._screen.questions)
            if card.text == _LONG_QUESTION
        )
        window._jump(long_index)
        for width, height in ((1600, 900), (1920, 1080)):
            window.show_at(width, height)
            question = window.findChild(QLabel, "written-exam-question-text")
            assert question is not None
            self.assertEqual(question.text(), _LONG_QUESTION)
            self.assertTrue(question.wordWrap())
            self.assertIn("font-size: 20px", question.styleSheet())
            self.assertGreater(question.maximumHeight(), 400)
            self.assertGreater(question.heightForWidth(600), 40)
            self.assertGreaterEqual(question.height(), question.heightForWidth(question.width()))
            answer = window.findChild(QLabel, "written-exam-answer-text-A")
            assert answer is not None
            self.assertIn("font-size: 18px", answer.styleSheet())
            self.assertTrue(answer.wordWrap())
            radio = window.findChild(QRadioButton, "written-exam-answer-A")
            assert radio is not None
            self.assertGreaterEqual(radio.minimumHeight(), 44)

        window._jump(0)
        legend = window.findChild(QLabel, "written-exam-nav-legend")
        assert legend is not None and legend.isVisible()
        self.assertEqual(legend.text(), "● zodpovězeno")
        style = window._nav_host.styleSheet()
        self.assertIn("#1d4ed8", style)
        self.assertNotIn("#dcfce7", style)
        self.assertNotIn("#14532d", style)

        self._choose(window, "A")
        self.assertEqual(window._index, 1)
        answered = window.findChild(QPushButton, "written-exam-nav-1")
        current = window.findChild(QPushButton, "written-exam-nav-2")
        pending = window.findChild(QPushButton, "written-exam-nav-3")
        assert answered is not None and current is not None and pending is not None
        self.assertEqual(answered.text(), "1 ●")
        self.assertEqual(answered.property("answered"), "true")
        self.assertEqual(answered.property("current"), "false")
        self.assertNotIn("✓", answered.text())
        self.assertEqual(current.text(), "2")
        self.assertNotIn("●", current.text())
        self.assertEqual(current.property("current"), "true")
        self.assertEqual(current.property("answered"), "false")
        self.assertEqual(pending.text(), "3")
        self.assertNotIn("●", pending.text())

    def test_advance_happens_only_after_successful_save(self) -> None:
        window = self._window("84002", "Uložení", ["První", "Druhá", "Třetí"])
        window.show_at(1600, 900)
        seen: dict[str, int] = {}
        original = written_exam_service.save_choice

        def spy(exam_id, question_id, answer_id, *, now=None):
            seen["before"] = window._index
            result = original(exam_id, question_id, answer_id, now=now)
            seen["after"] = window._index
            return result

        with patch.object(written_exam_service, "save_choice", spy):
            self._choose(window, "A")
        self.assertEqual(seen["before"], 0)
        self.assertEqual(seen["after"], 0)
        self.assertEqual(window._index, 1)
        self.assertEqual(len(written_exam_service.choices(window.exam_id)), 1)

    def test_failed_save_stays_on_the_same_question(self) -> None:
        window = self._window("84003", "Chyba", ["První", "Druhá"])
        window.show_at(1600, 900)

        def fail(*_args, **_kwargs):
            raise TestExamError("Odpověď se nepodařilo uložit.")

        with (
            patch.object(written_exam_service, "save_choice", fail),
            patch(
                "moduly.testy.ui.written_exam_window.QMessageBox.warning",
            ) as warning,
        ):
            self._choose(window, "A")
        self.assertEqual(window._index, 0)
        self.assertEqual(
            window.findChild(QLabel, "written-exam-question-text").text(),
            "První",
        )
        self.assertEqual(len(written_exam_service.choices(window.exam_id)), 0)
        radio = window.findChild(QRadioButton, "written-exam-answer-A")
        assert radio is not None
        self.assertFalse(radio.isChecked())
        self.assertEqual(warning.call_args.args[2], "Odpověď se nepodařilo uložit.")
        self.assertEqual(window.findChild(QPushButton, "written-exam-nav-1").text(), "1")

    def test_changed_answer_is_stored_and_advances(self) -> None:
        window = self._window("84004", "Změna", ["První", "Druhá", "Třetí"])
        window.show_at(1600, 900)
        self._choose(window, "A")
        self.assertEqual(window._index, 1)
        window._jump(0)
        self._choose(window, "B")
        self.assertEqual(window._index, 1)
        stored = written_exam_service.choices(window.exam_id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].selected_letter, "B")
        self.assertEqual(window.findChild(QPushButton, "written-exam-nav-1").text(), "1 ●")

    def test_last_answer_does_not_submit(self) -> None:
        window = self._window("84005", "Poslední", ["První", "Poslední otázka"])
        window.show_at(1600, 900)
        window._jump(1)
        with patch(
            "moduly.testy.ui.written_exam_window.QMessageBox.question",
        ) as question:
            self._choose(window, "C")
        question.assert_not_called()
        self.assertEqual(window._index, 1)
        self.assertEqual(window._phase, "running")
        self.assertEqual(
            window.findChild(QLabel, "written-exam-question-text").text(),
            "Poslední otázka",
        )
        exam = test_exam_service.get_exam(window.exam_id)
        assert exam is not None
        self.assertEqual(exam.written_finish_reason, "")
        self.assertIsNone(exam.written_finished_at)
        self.assertEqual(window.submit_button.text(), WRITTEN_SUBMIT)
        self.assertTrue(window.submit_button.isEnabled())
        self.assertEqual(len(written_exam_service.choices(window.exam_id)), 1)

    def test_image_answer_advances_the_same_way(self) -> None:
        images = _TMP / "obrazky"
        topic = written_question_topic_service.create_topic(name="Obrázky 8d")
        written_question_service.create_question(
            topic_id=topic.id,
            text="Textová otázka za obrázkem",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
        written_question_service.create_question(
            topic_id=topic.id,
            text="Vyberte značku",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(
                    image_source_path=str(_png(images / "a.png", (180, 0, 0))),
                    is_correct=True,
                ),
                WrittenAnswerInput(
                    image_source_path=str(_png(images / "b.png", (0, 180, 0))),
                ),
                WrittenAnswerInput(
                    image_source_path=str(_png(images / "c.png", (0, 0, 180))),
                ),
            ],
        )
        test = test_definition_service.create_test(
            name="Obrázkový přechod",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 2)],
        )
        employee = _employee("84006", "Iva", "Obrázková")
        exam = _prepare(employee.id, test.id)
        written_exam_service.start(exam.id, now=_STARTED)
        window = self._watch(WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED)))
        window.show_at(1600, 900)
        image = window.findChild(QLabel, "written-exam-answer-image-A")
        assert image is not None
        row = image.parentWidget()
        assert row is not None and row.parentWidget() is not None
        self.assertIsInstance(row.parentWidget().layout(), QHBoxLayout)
        self._choose(window, "A")
        self.assertEqual(window._index, 1)
        self.assertEqual(
            window.findChild(QLabel, "written-exam-question-text").text(),
            "Textová otázka za obrázkem",
        )
        self.assertIsNone(window.findChild(QLabel, "written-exam-answer-image-A"))
        self.assertEqual(len(written_exam_service.choices(exam.id)), 1)

    def test_resumed_exam_marks_saved_answers_without_correctness(self) -> None:
        window_first = self._window("84007", "Obnova", ["První", "Druhá", "Třetí"])
        screen = window_first._screen
        written_exam_service.save_choice(
            window_first.exam_id,
            screen.questions[0].exam_question_id,
            screen.questions[0].options[0].exam_answer_id,
            now=_STARTED,
        )
        written_exam_service.save_choice(
            window_first.exam_id,
            screen.questions[2].exam_question_id,
            screen.questions[2].options[1].exam_answer_id,
            now=_STARTED,
        )
        window_first.release_testing_lock()
        self._open.remove(window_first)
        resumed = self._watch(
            WrittenExamWindow(
                window_first.exam_id,
                clock=FixedWrittenExamClock(_STARTED),
            )
        )
        resumed.show_at(1600, 900)
        self.assertEqual(resumed.findChild(QPushButton, "written-exam-nav-1").text(), "1 ●")
        self.assertEqual(
            resumed.findChild(QPushButton, "written-exam-nav-1").property("current"),
            "true",
        )
        self.assertEqual(resumed.findChild(QPushButton, "written-exam-nav-2").text(), "2")
        self.assertNotIn("●", resumed.findChild(QPushButton, "written-exam-nav-2").text())
        self.assertEqual(resumed.findChild(QPushButton, "written-exam-nav-3").text(), "3 ●")
        self.assertNotIn("#dcfce7", resumed._nav_host.styleSheet())
        visible = " ".join(
            button.text() for button in resumed.findChildren(QPushButton)
        )
        self.assertNotIn("✓", visible)
        self.assertNotIn("Vyhověl", visible)
        self.assertNotIn("Nevyhověl", visible)
        legend = resumed.findChild(QLabel, "written-exam-nav-legend")
        assert legend is not None
        self.assertEqual(legend.text(), "● zodpovězeno")

    def _window(self, number: str, name: str, texts: list[str]) -> WrittenExamWindow:
        employee = _employee(number, "Jan", name)
        exam = _prepare(employee.id, _written_test(name, texts).id)
        written_exam_service.start(exam.id, now=_STARTED)
        window = self._watch(
            WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        window.show_at(1600, 900)
        return window

    def _watch(self, window: WrittenExamWindow) -> WrittenExamWindow:
        self._open.append(window)
        return window

    def _choose(self, window: WrittenExamWindow, letter: str) -> None:
        radio = window.findChild(QRadioButton, f"written-exam-answer-{letter}")
        assert radio is not None
        radio.click()


if __name__ == "__main__":
    unittest.main()
