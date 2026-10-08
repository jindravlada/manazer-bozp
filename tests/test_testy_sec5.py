"""TESTY-SEC-5: uživatelské texty zkoušek se nesmí vykreslit jako HTML."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec5-"))
_STARTED = datetime(2026, 10, 8, 9, 0, 0)
_CZECH = (
    "Žluťoučký kůň úpěl ďábelské ódy, přezůvky a štěstí. "
    "Dlouhá otázka má zůstat celá, včetně české diakritiky."
)
_MARKUP = "Otázka <b>tučně</b> a <i>kurzívou</i>"
_SCRIPT = "Varování <script>alert(1)</script> konec"
_HIDDEN = "Viditelná část <!--skrytá část otázky--> zůstává"
_SPECIAL = 'Porovnání a < b a > c & d "uvozovky" \'apostrof\''
_ANSWER_A = "první <b>tučně</b>"
_ANSWER_B = 'druhá <i>kurzívou</i> & "uvozovky"'
_ANSWER_C = "třetí <script>x</script> 1 < 2 > 0"
_IMAGE_CAPTION = "Vyberte značku <b>bez značky</b>"
_ORAL = 'Ústní znění <b>tučně</b> & "text"'
_TEST_NAME = 'Školení <i>BOZP</i> & "úvod"'
_LAST_NAME = "Novák <b>X</b>"
_ROLE = "Mistr <i>směny</i>"
_WORKPLACE = "Provoz <b>hala</b>"

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
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
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
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_answer_presentation import answer_caption
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
    from moduly.testy.ui.paper_answer_dialog import PaperAnswerDialog
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.written_exam_window import WrittenExamWindow


def _png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text=_ANSWER_A, is_correct=True),
        WrittenAnswerInput(text=_ANSWER_B),
        WrittenAnswerInput(text=_ANSWER_C),
    ]


def _paint(label: QLabel, width: int) -> QImage:
    label.setFixedWidth(width)
    height = max(label.heightForWidth(width), 1)
    label.resize(width, height)
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.white)
    label.render(image)
    return image


def _same_image(left: QImage, right: QImage) -> bool:
    if left.size() != right.size():
        return False
    for y in range(left.height()):
        for x in range(left.width()):
            if left.pixel(x, y) != right.pixel(x, y):
                return False
    return True


def _styled_label(source: QLabel, text: str, text_format: Qt.TextFormat) -> QLabel:
    label = QLabel()
    label.setTextFormat(text_format)
    label.setText(text)
    label.setWordWrap(source.wordWrap())
    label.setStyleSheet(source.styleSheet())
    label.setFont(source.font())
    label.setAlignment(source.alignment())
    label.setMargin(source.margin())
    label.setTextInteractionFlags(source.textInteractionFlags())
    return label


class _Rng:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        return None


class ExamTextRenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._windows: list[WrittenExamWindow] = []
        self._bait = _png(_TMP / "navnada.png", (400, 200), (220, 0, 0))
        self._question_image = _png(_TMP / "otazka.png", (160, 90), (0, 90, 180))
        self._image_text = f'<img src="file://{self._bait}"> nesmí se načíst'
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
            session.execute(delete(OralQuestion))
            session.execute(delete(OralQuestionTopic))
            session.execute(delete(TestEmployeeRole))
            session.execute(delete(TestEmployee))
            session.execute(delete(Attachment))
            session.commit()
        workplace = settings_service.save_workplace(name=_WORKPLACE)
        role = responsibility_role_service.create_role(name=_ROLE)
        self.employee = test_employee_service.create_employee(
            personal_number="85001",
            first_name="Jan",
            last_name=_LAST_NAME,
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        topic = written_question_topic_service.create_topic(name="Okruh <b>HTML</b>")
        for text in (_CZECH, _MARKUP, _SCRIPT, _HIDDEN, _SPECIAL):
            written_question_service.create_question(
                topic_id=topic.id,
                text=text,
                answer_kind=ANSWER_KIND_TEXT,
                answers=_text_answers(),
            )
        written_question_service.create_question(
            topic_id=topic.id,
            text=self._image_text,
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(self._question_image),
        )
        images = _TMP / "odpovedi"
        written_question_service.create_question(
            topic_id=topic.id,
            text=_IMAGE_CAPTION,
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(
                    image_source_path=str(_png(images / "a.png", (80, 60), (180, 0, 0))),
                    is_correct=True,
                ),
                WrittenAnswerInput(
                    image_source_path=str(_png(images / "b.png", (80, 60), (0, 160, 0))),
                ),
                WrittenAnswerInput(
                    image_source_path=str(_png(images / "c.png", (80, 60), (0, 0, 170))),
                ),
            ],
        )
        oral_topic = oral_question_topic_service.create_topic(name="Ústní <i>okruh</i>")
        oral_question_service.create_question(topic_id=oral_topic.id, text=_ORAL)
        test = test_definition_service.create_test(
            name=_TEST_NAME,
            uses_written=True,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=120,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 7)],
            oral_topics=[TestTopicQuota(oral_topic.id, 1)],
        )
        self.exam = test_exam_service.prepare_exam(
            employee_id=self.employee.id,
            test_id=test.id,
            exam_date=_STARTED.date(),
            rng=_Rng(),
        )

    def tearDown(self) -> None:
        for window in self._windows:
            window.release_testing_lock()
        QApplication.processEvents()

    def test_written_exam_renders_user_text_literally(self) -> None:
        written_exam_service.start(self.exam.id, now=_STARTED)
        window = self._watch(
            WrittenExamWindow(self.exam.id, clock=FixedWrittenExamClock(_STARTED))
        )
        window.show_at(1400, 900)
        screen = window._screen
        self._assert_literal(window.title_label, screen.test_name)
        self._assert_literal(window.employee_label, screen.employee_display_name)
        self.assertIn(_TEST_NAME, window.title_label.text())
        self.assertIn(_LAST_NAME, window.employee_label.text())
        legend = window.findChild(QLabel, "written-exam-nav-legend")
        assert legend is not None
        self.assertEqual(legend.text(), "● zodpovězeno")
        self.assertTrue(window.remaining_label.text().startswith("Zbývá:"))

        for question in screen.questions:
            index = next(
                position
                for position, card in enumerate(screen.questions)
                if card.exam_question_id == question.exam_question_id
            )
            window._jump(index)
            text = window.findChild(QLabel, "written-exam-question-text")
            assert text is not None
            self._assert_literal(text, question.text)
            self.assertTrue(text.wordWrap())
            if question.text == _CZECH:
                self.assertGreater(text.heightForWidth(480), 40)
            for option in question.options:
                if not option.text.strip():
                    continue
                caption = window.findChild(QLabel, f"written-exam-answer-text-{option.letter}")
                assert caption is not None
                self._assert_literal(caption, option.text)

        image_card = next(card for card in screen.questions if card.text == self._image_text)
        window._jump(
            next(
                index
                for index, card in enumerate(screen.questions)
                if card.exam_question_id == image_card.exam_question_id
            )
        )
        question_label = window.findChild(QLabel, "written-exam-question-text")
        assert question_label is not None
        question_pixmap = question_label.pixmap()
        self.assertTrue(question_pixmap is None or question_pixmap.isNull())
        self.assertLess(question_label.heightForWidth(640), 120)
        loaded = _styled_label(question_label, question_label.text(), Qt.TextFormat.RichText)
        self.assertGreaterEqual(loaded.heightForWidth(640), 180)
        picture = window.findChild(QLabel, "written-exam-question-image")
        assert picture is not None and picture.pixmap() is not None
        self.assertFalse(picture.pixmap().isNull())
        self.assertGreater(picture.pixmap().width(), 0)
        self.assertGreater(picture.pixmap().height(), 0)
        self.assertTrue(self._bait.is_file())
        self.assertGreater(self._bait.stat().st_size, 0)

        marks = next(card for card in screen.questions if card.text == _IMAGE_CAPTION)
        window._jump(
            next(
                index
                for index, card in enumerate(screen.questions)
                if card.exam_question_id == marks.exam_question_id
            )
        )
        for letter in ("A", "B", "C"):
            image = window.findChild(QLabel, f"written-exam-answer-image-{letter}")
            assert image is not None and image.pixmap() is not None
            self.assertFalse(image.pixmap().isNull())

        markup = next(card for card in screen.questions if card.text == _MARKUP)
        window._jump(
            next(
                index
                for index, card in enumerate(screen.questions)
                if card.exam_question_id == markup.exam_question_id
            )
        )
        caption = window.findChild(QLabel, "written-exam-answer-text-A")
        assert caption is not None
        QTest.mouseClick(caption, Qt.MouseButton.LeftButton)
        stored = written_exam_service.choices(window.exam_id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].selected_letter, "A")
        self.assertEqual(stored[0].exam_question_id, markup.exam_question_id)

    def test_detail_renders_user_text_literally(self) -> None:
        detail = TestExamDetailDialog(exam_id=self.exam.id)
        summary = detail.summary
        self._assert_literal(summary, summary.text())
        self.assertIn(_LAST_NAME, summary.text())
        self.assertIn(_TEST_NAME, summary.text())
        self.assertIn(_ROLE, summary.text())
        self.assertIn(_WORKPLACE, summary.text())
        for question in test_exam_service.get_written_questions(self.exam.id):
            title = detail.findChild(QLabel, f"written-text-{question.position}")
            assert title is not None
            self._assert_literal(
                title,
                f"{question.position}. {question.topic_name}\n{question.text}",
            )
            for answer in test_exam_service.get_written_answers(question.id):
                caption = detail.findChild(QLabel, f"answer-{question.position}-{answer.letter}")
                assert caption is not None
                self._assert_literal(caption, answer_caption(question, answer))
            if question.image_stored_path:
                image = detail.findChild(QLabel, f"written-image-{question.position}")
                assert image is not None and image.pixmap() is not None
                self.assertFalse(image.pixmap().isNull())
            if question.answer_kind == ANSWER_KIND_IMAGE:
                for answer in test_exam_service.get_written_answers(question.id):
                    image = detail.findChild(
                        QLabel,
                        f"answer-image-{question.position}-{answer.letter}",
                    )
                    assert image is not None and image.pixmap() is not None
                    self.assertFalse(image.pixmap().isNull())
        for question in test_exam_service.get_oral_questions(self.exam.id):
            label = detail.findChild(QLabel, f"oral-text-{question.position}")
            assert label is not None
            self._assert_literal(
                label,
                f"{question.position}. {question.topic_name}\n{question.text}",
            )
            self.assertIn(_ORAL, label.text())
        detail.deleteLater()

    def test_paper_dialog_renders_names_literally(self) -> None:
        dialog = PaperAnswerDialog(self.exam.id)
        self._assert_literal(dialog.employee, self.exam.employee_display_name)
        self._assert_literal(dialog.test_name, self.exam.test_name)
        self.assertIn(_LAST_NAME, dialog.employee.text())
        self.assertIn(_TEST_NAME, dialog.test_name.text())
        dialog.deleteLater()

    def _assert_literal(self, label: QLabel, expected: str) -> None:
        self.assertEqual(label.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(label.text(), expected)
        width = 640
        actual = _paint(label, width)
        plain = _paint(_styled_label(label, expected, Qt.TextFormat.PlainText), width)
        self.assertTrue(_same_image(actual, plain))
        if "<" not in expected:
            return
        rich = _paint(_styled_label(label, expected, Qt.TextFormat.RichText), width)
        self.assertFalse(_same_image(actual, rich))

    def _watch(self, window: WrittenExamWindow) -> WrittenExamWindow:
        self._windows.append(window)
        return window
