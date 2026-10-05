"""TESTY-4: banka písemných otázek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-4-"))

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
    from core.services.storage_service import storage_service
    from moduly.testy.constants import (
        AGENDA_QUESTIONS,
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_IMAGE_LABEL,
        ANSWER_KIND_SWITCH_CONFIRM,
        ANSWER_KIND_TEXT,
        ANSWER_KIND_TEXT_LABEL,
        QUESTION_COL_STATUS,
        QUESTION_COL_TEXT,
        QUESTION_COL_TOPIC,
        STATUS_INACTIVE_LABEL,
    )
    from moduly.testy.modely.written_question import WrittenQuestion
    from moduly.testy.modely.written_question_answer import WrittenQuestionAnswer
    from moduly.testy.modely.written_question_topic import WrittenQuestionTopic
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        WrittenQuestionError,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.testy_page import TestyPage
    from moduly.testy.ui.written_question_dialog import WrittenQuestionDialog


def _png(path: Path, color: tuple[int, int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (12, 8), color).save(path, "PNG")
    return path


def _texts(correct: int = 0, **overrides) -> list[WrittenAnswerInput]:
    answers = [
        WrittenAnswerInput(text="první", is_correct=correct == 0),
        WrittenAnswerInput(text="druhá", is_correct=correct == 1),
        WrittenAnswerInput(text="třetí", is_correct=correct == 2),
    ]
    for index, text in overrides.items():
        answers[index] = WrittenAnswerInput(text=text, is_correct=answers[index].is_correct)
    return answers


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _stored_files() -> set[str]:
    root = storage_service.attachments_dir
    if not root.exists():
        return set()
    return {str(path) for path in root.rglob("*") if path.is_file()}


class WrittenQuestionBankTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(WrittenQuestionAnswer))
            session.execute(delete(WrittenQuestion))
            session.execute(delete(WrittenQuestionTopic))
            session.execute(delete(Attachment))
            session.commit()
        self.images = Path(tempfile.mkdtemp(prefix="testy-4-img-"))
        self.topic = written_question_topic_service.create_topic(name="BOZP 4")
        self.other_topic = written_question_topic_service.create_topic(name="OOPP 4")
        self.page = TestyPage()
        self.questions = self.page.questions_tab

    def tearDown(self) -> None:
        self.page.close()

    def test_text_question_with_prompt_image_and_image_answers(self) -> None:
        prompt = _png(self.images / "zadani.png", (10, 20, 30))
        text_question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="  Kdo hlásí úraz?  ",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(),
            question_image_source_path=str(prompt),
            note="interní",
        )
        self.assertEqual(text_question.text, "Kdo hlásí úraz?")
        self.assertEqual(text_question.answer_kind, ANSWER_KIND_TEXT)
        self.assertEqual(text_question.topic_id, self.topic.id)
        self.assertTrue(text_question.active)
        self.assertIsNotNone(text_question.image_attachment_id)
        prompt_path = written_question_service.attachment_path(text_question.image_attachment_id)
        assert prompt_path is not None
        self.assertTrue(prompt_path.is_file())
        self.assertTrue(str(prompt_path).startswith(str(storage_service.attachments_dir)))
        answers = written_question_service.get_answers(text_question.id)
        self.assertEqual([item.text for item in answers], ["první", "druhá", "třetí"])
        self.assertEqual([item.is_correct for item in answers], [True, False, False])
        self.assertEqual([item.position for item in answers], [1, 2, 3])

        pictures = [
            _png(self.images / f"odp-{letter}.png", (index, 40, 80))
            for index, letter in enumerate("abc")
        ]
        image_question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="Který symbol je správný?",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(pictures[0])),
                WrittenAnswerInput(image_source_path=str(pictures[1]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(pictures[2])),
            ],
            question_image_source_path=str(prompt),
        )
        image_answers = written_question_service.get_answers(image_question.id)
        self.assertEqual(image_question.answer_kind, ANSWER_KIND_IMAGE)
        self.assertTrue(all(item.image_attachment_id for item in image_answers))
        self.assertEqual([item.is_correct for item in image_answers], [False, True, False])
        self.assertTrue(all(not item.text for item in image_answers))

    def test_validation_of_answers_kind_and_topic(self) -> None:
        with self.assertRaises(WrittenQuestionError) as none_correct:
            written_question_service.create_question(
                topic_id=self.topic.id,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=[
                    WrittenAnswerInput(text="a"),
                    WrittenAnswerInput(text="b"),
                    WrittenAnswerInput(text="c"),
                ],
            )
        self.assertIn("právě jednu", str(none_correct.exception))

        with self.assertRaises(WrittenQuestionError) as many_correct:
            written_question_service.create_question(
                topic_id=self.topic.id,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=[
                    WrittenAnswerInput(text="a", is_correct=True),
                    WrittenAnswerInput(text="b", is_correct=True),
                    WrittenAnswerInput(text="c"),
                ],
            )
        self.assertIn("právě jednu", str(many_correct.exception))

        with self.assertRaises(WrittenQuestionError) as incomplete:
            written_question_service.create_question(
                topic_id=self.topic.id,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=[
                    WrittenAnswerInput(text="a", is_correct=True),
                    WrittenAnswerInput(text=" "),
                    WrittenAnswerInput(text="c"),
                ],
            )
        self.assertIn("odpovědi B", str(incomplete.exception))

        with self.assertRaises(WrittenQuestionError) as count:
            written_question_service.create_question(
                topic_id=self.topic.id,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=_texts()[:2],
            )
        self.assertIn("právě 3", str(count.exception))

        picture = _png(self.images / "mix.png", (1, 2, 3))
        with self.assertRaises(WrittenQuestionError) as mixed:
            written_question_service.create_question(
                topic_id=self.topic.id,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=[
                    WrittenAnswerInput(text="a", is_correct=True),
                    WrittenAnswerInput(text="b", image_source_path=str(picture)),
                    WrittenAnswerInput(text="c"),
                ],
            )
        self.assertIn("kombinovat", str(mixed.exception))

        with self.assertRaises(WrittenQuestionError) as missing_topic:
            written_question_service.create_question(
                topic_id=None,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=_texts(),
            )
        self.assertIn("okruh", str(missing_topic.exception).casefold())

        written_question_topic_service.deactivate(self.other_topic.id)
        with self.assertRaises(WrittenQuestionError):
            written_question_service.create_question(
                topic_id=self.other_topic.id,
                text="Otázka",
                answer_kind=ANSWER_KIND_TEXT,
                answers=_texts(),
            )

    def test_inactive_topic_stays_on_existing_question(self) -> None:
        question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="Historická otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(),
        )
        written_question_topic_service.deactivate(self.topic.id)
        kept = written_question_service.update_question(
            question.id,
            topic_id=self.topic.id,
            text="Historická otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(),
            active=True,
        )
        self.assertEqual(kept.topic_id, self.topic.id)

        edit = WrittenQuestionDialog(question=kept)
        try:
            self.assertIn("(neaktivní)", edit.topic.currentText())
            self.assertEqual(edit._topic_id(), self.topic.id)
        finally:
            edit.close()

        fresh = WrittenQuestionDialog()
        try:
            self.assertLess(fresh.topic.findData(self.topic.id), 0)
            self.assertGreaterEqual(fresh.topic.findData(self.other_topic.id), 0)
        finally:
            fresh.close()

        moved = written_question_service.update_question(
            question.id,
            topic_id=self.other_topic.id,
            text="Historická otázka",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(),
        )
        self.assertEqual(moved.topic_id, self.other_topic.id)

    def test_active_flag_and_topic_filter(self) -> None:
        first = written_question_service.create_question(
            topic_id=self.topic.id,
            text="Otázka BOZP",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(),
        )
        written_question_service.create_question(
            topic_id=self.other_topic.id,
            text="Otázka OOPP",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(1),
        )
        written_question_service.deactivate(first.id)
        self.assertEqual(_count(WrittenQuestion), 2)
        self.assertIsNotNone(written_question_service.get_question(first.id))

        self.questions.refresh()
        self.assertEqual(self.questions.table.rowCount(), 1)
        self.assertEqual(self.questions.table.item(0, QUESTION_COL_TEXT).text(), "Otázka OOPP")
        self.assertEqual(
            self.questions.table.item(0, QUESTION_COL_TOPIC).text(),
            "OOPP 4",
        )

        self.questions.show_inactive.setChecked(True)
        self.assertEqual(self.questions.table.rowCount(), 2)
        index = self.questions.topic_filter.findData(self.topic.id)
        self.questions.topic_filter.setCurrentIndex(index)
        self.assertEqual(self.questions.table.rowCount(), 1)
        self.assertEqual(self.questions.table.item(0, QUESTION_COL_TEXT).text(), "Otázka BOZP")
        self.assertEqual(
            self.questions.table.item(0, QUESTION_COL_STATUS).text(),
            STATUS_INACTIVE_LABEL,
        )

        self.assertEqual(self.page.tabs.tabText(2), AGENDA_QUESTIONS)
        self.assertFalse(self.questions.edit_btn.isEnabled())
        self.questions.table.selectRow(0)
        self.assertTrue(self.questions.edit_btn.isEnabled())

    def test_answer_kind_switch_requires_confirmation(self) -> None:
        dialog = WrittenQuestionDialog()
        dialog.answer_texts[0].setText("ano")
        dialog.answer_texts[1].setText("ne")
        dialog.answer_texts[2].setText("nevím")
        try:
            with patch(
                "moduly.testy.ui.written_question_dialog.QMessageBox.question",
                return_value=QMessageBox.StandardButton.No,
            ) as question:
                dialog.kind_image.setChecked(True)
            question.assert_called_once()
            self.assertIn(ANSWER_KIND_SWITCH_CONFIRM, question.call_args.args[2])
            self.assertTrue(dialog.kind_text.isChecked())
            self.assertEqual(dialog._kind, ANSWER_KIND_TEXT)
            self.assertEqual(dialog.answer_texts[0].text(), "ano")
            self.assertFalse(dialog.answer_texts[0].isHidden())
            self.assertTrue(dialog.answer_images[0].isHidden())

            with patch(
                "moduly.testy.ui.written_question_dialog.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                dialog.kind_image.setChecked(True)
            self.assertEqual(dialog._kind, ANSWER_KIND_IMAGE)
            self.assertEqual(dialog.answer_texts[0].text(), "")
            self.assertTrue(dialog.answer_texts[0].isHidden())
            self.assertFalse(dialog.answer_images[0].isHidden())
            self.assertEqual(
                dialog.kind_image.text(),
                ANSWER_KIND_IMAGE_LABEL,
            )
            self.assertEqual(dialog.kind_text.text(), ANSWER_KIND_TEXT_LABEL)
        finally:
            dialog.close()

    def test_cancel_keeps_original_image_and_creates_no_orphans(self) -> None:
        original = _png(self.images / "puvodni.png", (9, 9, 9))
        replacement = _png(self.images / "novy.png", (200, 10, 10))
        question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="S obrázkem",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_texts(),
            question_image_source_path=str(original),
        )
        stored = written_question_service.attachment_path(question.image_attachment_id)
        assert stored is not None
        before_bytes = stored.read_bytes()
        before_files = _stored_files()
        before_rows = _count(Attachment)

        dialog = WrittenQuestionDialog(question=question)
        dialog.question_image.set_source_path(str(replacement))
        with patch(
            "moduly.testy.ui.written_question_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog.kind_image.setChecked(True)
        for index, color in enumerate(((1, 1, 1), (2, 2, 2), (3, 3, 3))):
            path = _png(self.images / f"rozpracovane-{index}.png", color)
            dialog.answer_images[index].set_source_path(str(path))
        dialog.reject()
        dialog.close()

        self.assertEqual(_stored_files(), before_files)
        self.assertEqual(_count(Attachment), before_rows)
        self.assertEqual(stored.read_bytes(), before_bytes)
        reloaded = written_question_service.get_question(question.id)
        assert reloaded is not None
        self.assertEqual(reloaded.image_attachment_id, question.image_attachment_id)
        self.assertEqual(reloaded.answer_kind, ANSWER_KIND_TEXT)

    def test_dialog_rejects_incomplete_question(self) -> None:
        dialog = WrittenQuestionDialog()
        dialog.topic.setCurrentIndex(dialog.topic.findData(self.topic.id))
        dialog.question_text.setPlainText("Text")
        dialog.answer_texts[0].setText("a")
        dialog.correct_buttons[0].setChecked(True)
        with patch(
            "moduly.testy.ui.written_question_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        self.assertIn("odpovědi", str(warning.call_args[0][2]).casefold())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(_count(WrittenQuestion), 0)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
