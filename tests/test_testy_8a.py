"""TESTY-8a: limity a normalizace obrázků písemných otázek."""

from __future__ import annotations

import hashlib
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
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import delete, func, select

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-8a-"))

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
    from core.ui.photo_picker_dialog import PHOTO_EXTENSIONS
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_IMAGE,
        ANSWER_KIND_TEXT,
        EXAMINER_MODE_NONE,
        MODULE_NAME,
        VALIDITY_UNIT_YEARS,
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
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_exam_service import (
        FixedWrittenExamClock,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_image_normalizer import (
        IMAGE_CANNOT_STORE,
        IMAGE_TOO_LARGE,
        MAX_INPUT_BYTES,
        MAX_STORED_BYTES,
        SUPPORTED_EXTENSIONS,
        WrittenImageError,
        normalize_written_image,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        WrittenQuestionError,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.written_exam_window import WrittenExamWindow
    from moduly.testy.ui.written_question_dialog import WrittenQuestionDialog


_STARTED = datetime(2026, 10, 6, 14, 0, 0)


class PrefixReverse:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        items.reverse()


def _count(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _stored_files() -> set[str]:
    root = storage_service.attachments_dir
    if not root.exists():
        return set()
    return {str(path) for path in root.rglob("*") if path.is_file()}


def _workdirs() -> set[str]:
    return {
        str(path)
        for path in Path(tempfile.gettempdir()).glob("testy-written-image-*")
        if path.exists()
    }


def _save_image(path: Path, size: tuple[int, int], fmt: str, **options) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (20, 80, 140)).save(path, fmt, **options)
    return path


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první", is_correct=True),
        WrittenAnswerInput(text="druhá"),
        WrittenAnswerInput(text="třetí"),
    ]


def _dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


class WrittenImageNormalizationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.images = _TMP / "images"
        cls.images.mkdir(parents=True, exist_ok=True)

    def setUp(self) -> None:
        self._windows: list[WrittenExamWindow] = []
        self._dialogs: list[WrittenQuestionDialog] = []
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
        self.topic = written_question_topic_service.create_topic(name="Obrázky 8a")
        self.output = Path(tempfile.mkdtemp(prefix="testy-8a-out-"))

    def tearDown(self) -> None:
        for window in self._windows:
            window.release_testing_lock()
            window.close()
        for dialog in self._dialogs:
            dialog.close()

    def _watch_dialog(self, dialog: WrittenQuestionDialog) -> WrittenQuestionDialog:
        self._dialogs.append(dialog)
        return dialog

    def test_supported_formats_match_photo_picker(self) -> None:
        self.assertEqual(SUPPORTED_EXTENSIONS, PHOTO_EXTENSIONS)

    def test_input_over_20_mb_is_rejected_before_decode(self) -> None:
        huge = self.images / "velky.jpg"
        with huge.open("wb") as handle:
            handle.write(b"\xff\xd8\xff")
            handle.truncate(MAX_INPUT_BYTES + 1)
        before = huge.read_bytes()[:16]
        signature = (huge.stat().st_size, huge.stat().st_mtime_ns)
        questions = _count(WrittenQuestion)
        attachments = _count(Attachment)
        files = _stored_files()
        workdirs = _workdirs()

        with patch(
            "moduly.testy.sluzby.written_image_normalizer.Image.open",
            side_effect=AssertionError("dekódování nemá proběhnout"),
        ) as opened:
            with self.assertRaises(WrittenImageError) as direct:
                normalize_written_image(huge, self.output)
            with self.assertRaises(WrittenQuestionError) as saved:
                written_question_service.create_question(
                    topic_id=self.topic.id,
                    text="Příliš velký soubor",
                    answer_kind=ANSWER_KIND_TEXT,
                    answers=_text_answers(),
                    question_image_source_path=str(huge),
                )
        opened.assert_not_called()
        self.assertEqual(str(direct.exception), IMAGE_TOO_LARGE)
        self.assertIn(IMAGE_TOO_LARGE, str(saved.exception))
        self.assertIn("Obrázek otázky", str(saved.exception))
        self.assertEqual(huge.stat().st_size, signature[0])
        self.assertEqual(huge.stat().st_mtime_ns, signature[1])
        self.assertEqual(huge.read_bytes()[:16], before)
        self.assertEqual(_count(WrittenQuestion), questions)
        self.assertEqual(_count(Attachment), attachments)
        self.assertEqual(_stored_files(), files)
        self.assertEqual(_workdirs(), workdirs)

        dialog = self._watch_dialog(WrittenQuestionDialog())
        dialog.topic.setCurrentIndex(dialog.topic.findData(self.topic.id))
        dialog.question_text.setPlainText("Dialog s velkým souborem")
        dialog.correct_buttons[0].setChecked(True)
        for index, text in enumerate(("ano", "ne", "nevím")):
            dialog.answer_texts[index].setText(text)
        dialog.question_image._source_path = str(huge)
        with patch(
            "moduly.testy.ui.written_question_dialog.QMessageBox.warning"
        ) as warning:
            dialog.accept()
        warning.assert_called_once()
        self.assertEqual(warning.call_args.args[1], MODULE_NAME)
        self.assertIn(IMAGE_TOO_LARGE, warning.call_args.args[2])
        self.assertIsNone(dialog.saved_question_id)
        self.assertEqual(_count(WrittenQuestion), questions)
        self.assertEqual(_stored_files(), files)
        self.assertEqual(_workdirs(), workdirs)

        slot = dialog.answer_images[0]
        with patch(
            "moduly.testy.ui.written_question_image_slot.QMessageBox.warning"
        ) as slot_warning:
            slot.set_source_path(str(huge))
        slot_warning.assert_called_once()
        self.assertIn(IMAGE_TOO_LARGE, slot_warning.call_args.args[2])
        self.assertIsNone(slot.source_path())

    def test_exact_20_mb_is_not_rejected_for_size(self) -> None:
        source = self.images / "presne-20.jpg"
        _save_image(source, (32, 24), "JPEG", quality=90)
        payload = source.read_bytes()
        source.write_bytes(payload + b"\0" * (MAX_INPUT_BYTES - len(payload)))
        self.assertEqual(source.stat().st_size, MAX_INPUT_BYTES)
        try:
            normalize_written_image(source, self.output)
        except WrittenImageError as exc:
            self.assertNotIn("20 MB", str(exc))

    def test_resize_keeps_aspect_and_does_not_upscale(self) -> None:
        cases = (
            ((1600, 1200), (800, 600)),
            ((1200, 600), (800, 400)),
            ((600, 1200), (300, 600)),
            ((640, 480), (640, 480)),
        )
        for source_size, expected in cases:
            path = self.images / f"{source_size[0]}x{source_size[1]}.png"
            original = _save_image(path, source_size, "PNG").read_bytes()
            result = normalize_written_image(path, self.output)
            self.assertEqual(_dimensions(result.path), expected)
            self.assertLessEqual(result.width, 800)
            self.assertLessEqual(result.height, 600)
            self.assertEqual(result.byte_size, result.path.stat().st_size)
            self.assertLessEqual(result.byte_size, MAX_STORED_BYTES)
            self.assertEqual(path.read_bytes(), original)
            if source_size[0] <= 800 and source_size[1] <= 600:
                self.assertEqual(result.path.read_bytes(), original)
                self.assertEqual(result.path.suffix, ".png")

    def test_wide_and_tall_ratios_survive_storage(self) -> None:
        wide = _save_image(self.images / "siroky.jpg", (1200, 600), "JPEG", quality=90)
        tall = _save_image(self.images / "vysoky.jpg", (600, 1200), "JPEG", quality=90)
        wide_result = normalize_written_image(wide, self.output)
        tall_result = normalize_written_image(tall, self.output)
        self.assertEqual(_dimensions(wide_result.path), (800, 400))
        self.assertEqual(_dimensions(tall_result.path), (300, 600))
        self.assertAlmostEqual(wide_result.width / wide_result.height, 2, delta=0.01)
        self.assertAlmostEqual(tall_result.width / tall_result.height, 0.5, delta=0.01)
        self.assertEqual(wide_result.path.suffix, ".jpg")
        self.assertEqual(tall_result.path.suffix, ".jpg")

    def test_diagram_png_stays_png_and_unusable_image_is_rejected(self) -> None:
        diagram = self.images / "schema.png"
        image = Image.new("RGB", (420, 280), (255, 255, 255))
        for x in range(40, 380, 20):
            for y in range(40, 240):
                image.putpixel((x, y), (0, 0, 0))
        image.save(diagram, "PNG")
        stored = normalize_written_image(diagram, self.output)
        self.assertEqual(stored.path.suffix, ".png")
        self.assertEqual(_dimensions(stored.path), (420, 280))

        with self.assertRaises(WrittenImageError) as rejected:
            normalize_written_image(
                _save_image(self.images / "sum.jpg", (320, 240), "JPEG", quality=95),
                self.output,
                max_stored_bytes=20,
            )
        self.assertEqual(str(rejected.exception), IMAGE_CANNOT_STORE)

        noisy = self.images / "sum-velky.jpg"
        Image.frombytes("RGB", (1600, 1200), os.urandom(1600 * 1200 * 3)).save(
            noisy,
            "JPEG",
            quality=95,
        )
        original = noisy.read_bytes()
        stored_noise = normalize_written_image(noisy, self.output)
        self.assertLessEqual(stored_noise.byte_size, MAX_STORED_BYTES)
        self.assertLessEqual(stored_noise.width, 800)
        self.assertLessEqual(stored_noise.height, 600)
        self.assertAlmostEqual(stored_noise.width / stored_noise.height, 4 / 3, delta=0.02)
        self.assertEqual(noisy.read_bytes(), original)

    def test_prompt_and_answers_share_normalization_and_keep_original(self) -> None:
        wide = _save_image(self.images / "spolecny.png", (1200, 600), "PNG")
        others = [
            _save_image(self.images / "odp-b.png", (1200, 600), "PNG"),
            _save_image(self.images / "odp-c.png", (600, 1200), "PNG"),
        ]
        originals = {
            wide: wide.read_bytes(),
            others[0]: others[0].read_bytes(),
            others[1]: others[1].read_bytes(),
        }
        direct = normalize_written_image(wide, self.output)
        question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="Stejná normalizace",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(wide), is_correct=True),
                WrittenAnswerInput(image_source_path=str(others[0])),
                WrittenAnswerInput(image_source_path=str(others[1])),
            ],
            question_image_source_path=str(wide),
        )
        prompt = written_question_service.attachment_path(question.image_attachment_id)
        assert prompt is not None
        answers = written_question_service.get_answers(question.id)
        answer_a = written_question_service.attachment_path(answers[0].image_attachment_id)
        answer_c = written_question_service.attachment_path(answers[2].image_attachment_id)
        assert answer_a is not None and answer_c is not None
        self.assertEqual(prompt.read_bytes(), direct.path.read_bytes())
        self.assertEqual(answer_a.read_bytes(), direct.path.read_bytes())
        self.assertEqual(_dimensions(prompt), (800, 400))
        self.assertEqual(_dimensions(answer_a), (800, 400))
        self.assertEqual(_dimensions(answer_c), (300, 600))
        self.assertEqual(prompt.suffix, ".png")
        self.assertEqual(answer_c.suffix, ".png")
        self.assertLessEqual(prompt.stat().st_size, MAX_STORED_BYTES)
        self.assertEqual(_workdirs(), set())
        for path, payload in originals.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_cancel_creates_no_orphan_and_leaves_original(self) -> None:
        original = _save_image(self.images / "puvodni.png", (80, 40), "PNG")
        replacement = _save_image(self.images / "novy.png", (1600, 1200), "PNG")
        payload = replacement.read_bytes()
        question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="Zrušený editor",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(original),
        )
        stored = written_question_service.attachment_path(question.image_attachment_id)
        assert stored is not None
        before_bytes = stored.read_bytes()
        before_files = _stored_files()
        before_rows = _count(Attachment)
        before_dirs = _workdirs()

        dialog = self._watch_dialog(WrittenQuestionDialog(question=question))
        dialog.question_image.set_source_path(str(replacement))
        with patch(
            "moduly.testy.ui.written_question_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog.kind_image.setChecked(True)
        for index, size in enumerate(((640, 480), (1200, 600), (600, 1200))):
            path = _save_image(self.images / f"slot-{index}.png", size, "PNG")
            dialog.answer_images[index].set_source_path(str(path))
        dialog.reject()

        self.assertEqual(_stored_files(), before_files)
        self.assertEqual(_count(Attachment), before_rows)
        self.assertEqual(_count(WrittenQuestion), 1)
        self.assertEqual(stored.read_bytes(), before_bytes)
        self.assertEqual(replacement.read_bytes(), payload)
        self.assertEqual(_workdirs(), before_dirs)
        reloaded = written_question_service.get_question(question.id)
        assert reloaded is not None
        self.assertEqual(reloaded.image_attachment_id, question.image_attachment_id)
        self.assertEqual(reloaded.answer_kind, ANSWER_KIND_TEXT)

    def test_snapshot_copies_normalized_bytes_without_another_pass(self) -> None:
        source = _save_image(self.images / "banka.jpg", (1600, 1200), "JPEG", quality=92)
        original = source.read_bytes()
        question = written_question_service.create_question(
            topic_id=self.topic.id,
            text="Snapshot obrázku",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(
                    image_source_path=str(
                        _save_image(self.images / "a.jpg", (1600, 1200), "JPEG", quality=90)
                    ),
                    is_correct=True,
                ),
                WrittenAnswerInput(
                    image_source_path=str(
                        _save_image(self.images / "b.jpg", (1200, 600), "JPEG", quality=90)
                    )
                ),
                WrittenAnswerInput(
                    image_source_path=str(
                        _save_image(self.images / "c.jpg", (600, 1200), "JPEG", quality=90)
                    )
                ),
            ],
            question_image_source_path=str(source),
        )
        direct = normalize_written_image(source, self.output)
        bank = written_question_service.attachment_path(question.image_attachment_id)
        assert bank is not None
        self.assertEqual(bank.read_bytes(), direct.path.read_bytes())
        self.assertEqual(_dimensions(bank), (800, 600))
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(_dimensions(source), (1600, 1200))

        employee = _employee("81081", "Eva", "Snímková")
        test = test_definition_service.create_test(
            name="Snapshot 8a",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(self.topic.id, 1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=_STARTED.date(),
            rng=PrefixReverse(),
        )
        row = test_exam_service.get_written_questions(exam.id)[0]
        snapshot = test_exam_service.resolve_snapshot_image(row.image_stored_path)
        assert snapshot is not None
        frozen = snapshot.read_bytes()
        self.assertEqual(frozen, bank.read_bytes())
        self.assertEqual(hashlib.sha256(frozen).hexdigest(), row.image_sha256)
        self.assertEqual(_dimensions(snapshot), (800, 600))
        self.assertNotEqual(snapshot.resolve(), bank.resolve())
        for answer in test_exam_service.get_written_answers(row.id):
            answer_path = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
            assert answer_path is not None
            self.assertEqual(
                hashlib.sha256(answer_path.read_bytes()).hexdigest(),
                answer.image_sha256,
            )
            self.assertLessEqual(answer_path.stat().st_size, MAX_STORED_BYTES)
            self.assertLessEqual(_dimensions(answer_path)[0], 800)
            self.assertLessEqual(_dimensions(answer_path)[1], 600)

    def test_exam_screen_shows_snapshot_without_changing_it(self) -> None:
        answers = [
            _save_image(self.images / "ui-a.png", (800, 200), "PNG"),
            _save_image(self.images / "ui-b.png", (800, 200), "PNG"),
            _save_image(self.images / "ui-c.png", (800, 200), "PNG"),
        ]
        prompt = _save_image(self.images / "ui-zadani.png", (1000, 100), "PNG")
        written_question_service.create_question(
            topic_id=self.topic.id,
            text="Tři značky vedle sebe",
            answer_kind=ANSWER_KIND_IMAGE,
            answers=[
                WrittenAnswerInput(image_source_path=str(answers[0]), is_correct=True),
                WrittenAnswerInput(image_source_path=str(answers[1])),
                WrittenAnswerInput(image_source_path=str(answers[2])),
            ],
            question_image_source_path=str(prompt),
        )
        employee = _employee("81082", "Adam", "Řadový")
        test = test_definition_service.create_test(
            name="Řada 8a",
            uses_written=True,
            seconds_per_question=60,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(self.topic.id, 1)],
        )
        exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=_STARTED.date(),
            rng=PrefixReverse(),
        )
        written_exam_service.start(exam.id, now=_STARTED)
        row = test_exam_service.get_written_questions(exam.id)[0]
        snapshot = test_exam_service.resolve_snapshot_image(row.image_stored_path)
        assert snapshot is not None
        before = snapshot.read_bytes()
        before_stamp = snapshot.stat().st_mtime_ns
        answer_bytes = {}
        for answer in test_exam_service.get_written_answers(row.id):
            path = test_exam_service.resolve_snapshot_image(answer.image_stored_path)
            assert path is not None
            answer_bytes[answer.letter] = (path, path.read_bytes(), path.stat().st_mtime_ns)

        window = WrittenExamWindow(exam.id, clock=FixedWrittenExamClock(_STARTED))
        self._windows.append(window)
        window.show_at(1600, 900)
        question = window.findChild(QLabel, "written-exam-question-image")
        assert question is not None
        self.assertEqual(question.property("snapshotPath"), row.image_stored_path)
        self.assertAlmostEqual(
            question.pixmap().width() / question.pixmap().height(),
            10,
            delta=0.2,
        )
        host = window.findChild(QWidget, "written-exam-answers")
        assert host is not None
        self.assertIsInstance(host.layout(), QHBoxLayout)
        positions = []
        for letter in ("A", "B", "C"):
            image = window.findChild(QLabel, f"written-exam-answer-image-{letter}")
            assert image is not None and image.isVisible()
            self.assertAlmostEqual(image.pixmap().width() / image.pixmap().height(), 4, delta=0.2)
            top_left = image.mapTo(window, image.rect().topLeft())
            bottom_right = image.mapTo(window, image.rect().bottomRight())
            self.assertGreaterEqual(top_left.x(), 0)
            self.assertGreaterEqual(top_left.y(), 0)
            self.assertLessEqual(bottom_right.x(), window.width())
            self.assertLessEqual(bottom_right.y(), window.height())
            positions.append(top_left)
        self.assertLess(positions[0].x(), positions[1].x())
        self.assertLess(positions[1].x(), positions[2].x())
        self.assertLess(abs(positions[0].y() - positions[1].y()), 40)
        self.assertLess(abs(positions[1].y() - positions[2].y()), 40)

        self.assertEqual(snapshot.read_bytes(), before)
        self.assertEqual(snapshot.stat().st_mtime_ns, before_stamp)
        for letter, (path, payload, stamp) in answer_bytes.items():
            self.assertEqual(path.read_bytes(), payload, letter)
            self.assertEqual(path.stat().st_mtime_ns, stamp, letter)

        text_topic = written_question_topic_service.create_topic(name="Text 8a")
        written_question_service.create_question(
            topic_id=text_topic.id,
            text="Textové odpovědi pod sebou",
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
        )
        text_test = test_definition_service.create_test(
            name="Text 8a",
            uses_written=True,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(text_topic.id, 1)],
        )
        text_exam = test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=text_test.id,
            exam_date=_STARTED.date(),
            rng=PrefixReverse(),
        )
        written_exam_service.start(text_exam.id, now=_STARTED)
        text_window = WrittenExamWindow(text_exam.id, clock=FixedWrittenExamClock(_STARTED))
        self._windows.append(text_window)
        text_window.show_at(1600, 900)
        text_host = text_window.findChild(QWidget, "written-exam-answers")
        assert text_host is not None
        self.assertIsInstance(text_host.layout(), QVBoxLayout)


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


if __name__ == "__main__":
    unittest.main()
