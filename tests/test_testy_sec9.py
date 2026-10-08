"""TESTY-SEC-9: zmrazený obrázek se použije jen s ověřeným SHA-256."""

from __future__ import annotations

import hashlib
import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QRadioButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec9-"))
_STARTED = datetime(2026, 10, 8, 11, 0, 0)
_QUESTION = "Otázka s obrázkem zůstane"
_SECRET_NAME = "secret-sec9.png"
_INTEGRITY = "Obrázek nebylo možné bezpečně zobrazit kvůli chybě integrity."
_LEGACY = "Obrázek ze starší zkoušky nelze ověřit, proto se nezobrazuje."

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
    from core.services.storage_service import storage_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_IMAGE,
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_MODE_ELECTRONIC,
        WRITTEN_RESULT_PASSED,
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
    from moduly.testy.sluzby import test_exam_service as exam_module
    from moduly.testy.sluzby.exam_protocol_export_service import (
        exam_protocol_export_service,
    )
    from moduly.testy.sluzby.paper_test_export_service import paper_test_export_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import (
        SNAPSHOT_IMAGE_ABSENT,
        SNAPSHOT_IMAGE_MISMATCH,
        SNAPSHOT_IMAGE_OK,
        SNAPSHOT_IMAGE_UNVERIFIED,
        test_exam_service,
    )
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
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.written_exam_window import WrittenExamWindow


class _Rng:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        return None


def _png(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (24, 16), color).save(path, "PNG")


def _pixel(data: bytes) -> int:
    pixmap = QPixmap()
    assert pixmap.loadFromData(data)
    return pixmap.toImage().pixel(0, 0)


def _zip_has(path: Path, payload: bytes) -> bool:
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if payload in archive.read(name):
                return True
    return False


def _content_xml(path: Path) -> bytes:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml")


class SnapshotImageIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._windows: list[WrittenExamWindow] = []
        self.outside = _TMP / "mimo-uloziste"
        self.outside.mkdir(exist_ok=True)
        self.secret = self.outside / _SECRET_NAME
        _png(self.secret, (1, 2, 3))
        self.opened: list[str] = []
        self._wipe()
        self.output = _TMP / "export"
        self.output.mkdir(exist_ok=True)
        self.sources = _TMP / "zdroje"
        if self.sources.exists():
            for child in self.sources.iterdir():
                child.unlink()
        else:
            self.sources.mkdir()
        self.exam = self._prepared_exam()
        self.question = test_exam_service.get_written_questions(self.exam.id)[0]
        self.frozen = test_exam_service.resolve_snapshot_image(self.question.image_stored_path)
        assert self.frozen is not None
        self.original = self.frozen.read_bytes()
        self.original_hash = self.question.image_sha256

    def tearDown(self) -> None:
        for window in self._windows:
            window.release_testing_lock()
        QApplication.processEvents()

    def test_valid_image_matches_stored_hash(self) -> None:
        loaded = test_exam_service.load_snapshot_image(
            self.question.image_stored_path,
            self.original_hash,
        )
        self.assertEqual(loaded.status, SNAPSHOT_IMAGE_OK)
        assert loaded.data is not None
        self.assertEqual(loaded.data, self.original)
        self.assertEqual(hashlib.sha256(loaded.data).hexdigest(), self.original_hash)
        self._assert_hash_unchanged()

    def test_rejected_images_are_not_returned(self) -> None:
        self.frozen.write_bytes(self._flipped(self.original))
        mismatched = test_exam_service.load_snapshot_image(
            self.question.image_stored_path,
            self.original_hash,
        )
        self.assertEqual(mismatched.status, SNAPSHOT_IMAGE_MISMATCH)
        self.assertIsNone(mismatched.data)
        self._assert_hash_unchanged()

        replacement = self.sources / "jiny.png"
        _png(replacement, (0, 0, 255))
        self.frozen.write_bytes(replacement.read_bytes())
        replaced = test_exam_service.load_snapshot_image(
            self.question.image_stored_path,
            self.original_hash,
        )
        self.assertEqual(replaced.status, SNAPSHOT_IMAGE_MISMATCH)
        self.assertIsNone(replaced.data)
        self.assertNotEqual(self.frozen.read_bytes(), self.original)
        self._assert_hash_unchanged()

        self.frozen.unlink()
        missing = test_exam_service.load_snapshot_image(
            self.question.image_stored_path,
            self.original_hash,
        )
        self.assertEqual(missing.status, SNAPSHOT_IMAGE_ABSENT)
        self.assertIsNone(missing.data)

        for relative in (
            "../mimo-uloziste/secret-sec9.png",
            str(self.secret),
            "test_exam_snapshot/odkaz.png",
        ):
            self._point_question(relative)
            with self._watch_opens():
                loaded = test_exam_service.load_snapshot_image(relative, self.original_hash)
            self.assertEqual(loaded.status, SNAPSHOT_IMAGE_ABSENT, relative)
            self.assertIsNone(loaded.data)
            self.assertEqual(self.opened, [])
        self.assertEqual(self.secret.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_unreadable_file_is_not_used(self) -> None:
        real_open = exam_module.os.open

        def wrapped(path, flags, mode=0o777, *, dir_fd=None):
            if dir_fd is None and os.fsdecode(path) == str(self.frozen):
                raise PermissionError("nelze číst")
            return real_open(path, flags, mode, dir_fd=dir_fd)

        with patch.object(exam_module.os, "open", wrapped):
            loaded = test_exam_service.load_snapshot_image(
                self.question.image_stored_path,
                self.original_hash,
            )
        self.assertEqual(loaded.status, SNAPSHOT_IMAGE_ABSENT)
        self.assertIsNone(loaded.data)
        self.assertEqual(self.frozen.read_bytes(), self.original)
        self._assert_hash_unchanged()

    def test_legacy_snapshot_without_hash_is_not_backfilled(self) -> None:
        before_mtime = self.frozen.stat().st_mtime_ns
        self._point_question(self.question.image_stored_path, digest="")
        loaded = test_exam_service.load_snapshot_image(self.question.image_stored_path, "")
        self.assertEqual(loaded.status, SNAPSHOT_IMAGE_UNVERIFIED)
        self.assertIsNone(loaded.data)
        self.assertEqual(self.frozen.read_bytes(), self.original)
        self.assertEqual(self.frozen.stat().st_mtime_ns, before_mtime)
        stored = test_exam_service.get_written_questions(self.exam.id)[0]
        self.assertEqual(stored.image_sha256, "")

    def test_display_and_export_use_only_verified_bytes(self) -> None:
        blue = self.sources / "modry.png"
        _png(blue, (0, 0, 255))
        blue_bytes = blue.read_bytes()
        self.assertNotEqual(_pixel(self.original), _pixel(blue_bytes))
        real = test_exam_service.load_snapshot_image

        def swap_after_check(relative_path, expected_sha256):
            result = real(relative_path, expected_sha256)
            if result.data:
                self.frozen.write_bytes(blue_bytes)
            return result

        paper = self.output / "overeno.odt"
        with patch.object(test_exam_service, "load_snapshot_image", swap_after_check):
            paper_test_export_service.export(self.exam.id, paper)
        self.assertEqual(self.frozen.read_bytes(), blue_bytes)
        self.assertTrue(_zip_has(paper, self.original))
        self.assertFalse(_zip_has(paper, blue_bytes))
        self._assert_hash_unchanged()

        self.frozen.write_bytes(self.original)
        written_exam_service.start(self.exam.id, now=_STARTED)
        with patch.object(test_exam_service, "load_snapshot_image", swap_after_check):
            window = WrittenExamWindow(self.exam.id, clock=FixedWrittenExamClock(_STARTED))
            self._windows.append(window)
            window.show_at(1400, 900)
        label = window.findChild(QLabel, "written-exam-question-image")
        assert label is not None
        pixmap = label.pixmap()
        assert pixmap is not None and not pixmap.isNull()
        self.assertEqual(pixmap.toImage().pixel(0, 0), _pixel(self.original))
        self.assertEqual(self.frozen.read_bytes(), blue_bytes)
        self.assertIsNone(window.findChild(QLabel, "written-exam-question-image-notice"))
        self._assert_hash_unchanged()

    def test_mismatch_keeps_exam_detail_and_documents_usable(self) -> None:
        self.frozen.write_bytes(self._flipped(self.original))
        damaged = self.frozen.read_bytes()
        written_exam_service.start(self.exam.id, now=_STARTED)
        window = WrittenExamWindow(self.exam.id, clock=FixedWrittenExamClock(_STARTED))
        self._windows.append(window)
        window.show_at(1400, 900)
        question = window.findChild(QLabel, "written-exam-question-text")
        assert question is not None
        self.assertEqual(question.text(), _QUESTION)
        notice = window.findChild(QLabel, "written-exam-question-image-notice")
        assert notice is not None
        self.assertEqual(notice.text(), _INTEGRITY)
        self.assertNotIn(str(self.frozen), notice.text())
        self.assertIsNone(window.findChild(QLabel, "written-exam-question-image"))
        radio = window.findChild(QRadioButton, "written-exam-answer-B")
        assert radio is not None
        radio.setChecked(True)
        QApplication.processEvents()
        stored_choice = written_exam_service.choices(self.exam.id)
        self.assertEqual(stored_choice[0].selected_letter, "B")
        current = test_exam_service.get_exam(self.exam.id)
        self.assertEqual(current.status, "started")
        self.assertFalse(current.written_result)

        self._complete()
        detail = TestExamDetailDialog(exam_id=self.exam.id)
        title = detail.findChild(QLabel, "written-text-1")
        assert title is not None
        self.assertIn(_QUESTION, title.text())
        detail_notice = detail.findChild(QLabel, "written-image-1-notice")
        assert detail_notice is not None
        self.assertEqual(detail_notice.text(), _INTEGRITY)
        self.assertIsNone(detail.findChild(QLabel, "written-image-1"))
        detail.deleteLater()

        paper = self.output / "poskozeny.odt"
        paper_test_export_service.export(self.exam.id, paper)
        protocol = self.output / "protokol.odt"
        exam_protocol_export_service.export(self.exam.id, protocol)
        for document in (paper, protocol):
            content = _content_xml(document)
            self.assertIn(_QUESTION.encode("utf-8"), content)
            self.assertIn(_INTEGRITY.encode("utf-8"), content)
            self.assertNotIn(str(self.frozen).encode("utf-8"), content)
            self.assertFalse(_zip_has(document, damaged))
            self.assertFalse(_zip_has(document, self.original))
        self._assert_hash_unchanged()
        self.assertEqual(self.frozen.read_bytes(), damaged)

    def test_legacy_notice_in_exam_and_export(self) -> None:
        self._point_question(self.question.image_stored_path, digest="")
        self._complete()
        detail = TestExamDetailDialog(exam_id=self.exam.id)
        notice = detail.findChild(QLabel, "written-image-1-notice")
        assert notice is not None
        self.assertEqual(notice.text(), _LEGACY)
        self.assertNotEqual(notice.text(), _INTEGRITY)
        self.assertIsNone(detail.findChild(QLabel, "written-image-1"))
        detail.deleteLater()
        paper = self.output / "stary.odt"
        paper_test_export_service.export(self.exam.id, paper)
        content = _content_xml(paper)
        self.assertIn(_LEGACY.encode("utf-8"), content)
        self.assertNotIn(_INTEGRITY.encode("utf-8"), content)
        self.assertFalse(_zip_has(paper, self.original))
        stored = test_exam_service.get_written_questions(self.exam.id)[0]
        self.assertEqual(stored.image_sha256, "")
        self.assertEqual(self.frozen.read_bytes(), self.original)

    def _flipped(self, data: bytes) -> bytes:
        last = bytearray(data)
        last[-1] ^= 0x01
        return bytes(last)

    def _point_question(self, relative: str, digest: str | None = None) -> None:
        link = storage_service.attachments_dir / "test_exam_snapshot" / "odkaz.png"
        link.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith("odkaz.png") and not link.is_symlink():
            if link.exists():
                link.unlink()
            link.symlink_to(self.secret)
        with get_session() as session:
            row = session.get(TestExamWrittenQuestion, self.question.id)
            assert row is not None
            row.image_stored_path = relative
            if digest is not None:
                row.image_sha256 = digest
            session.commit()

    def _complete(self) -> None:
        with get_session() as session:
            exam = session.get(TestExam, self.exam.id)
            assert exam is not None
            exam.status = EXAM_STATUS_COMPLETED
            exam.written_mode = WRITTEN_MODE_ELECTRONIC
            exam.written_result = WRITTEN_RESULT_PASSED
            exam.written_finished_at = _STARTED
            session.commit()

    def _assert_hash_unchanged(self) -> None:
        stored = test_exam_service.get_written_questions(self.exam.id)[0]
        self.assertEqual(stored.image_sha256, self.original_hash)

    def _watch_opens(self):
        real_open = exam_module.os.open

        def wrapped(path, flags, mode=0o777, *, dir_fd=None):
            if dir_fd is None and not isinstance(path, int):
                if _SECRET_NAME in os.fsdecode(path):
                    self.opened.append(os.fsdecode(path))
            return real_open(path, flags, mode, dir_fd=dir_fd)

        return patch.object(exam_module.os, "open", wrapped)

    def _prepared_exam(self):
        workplace = settings_service.save_workplace(name="Provoz SEC9")
        role = responsibility_role_service.create_role(name="Mistr SEC9")
        employee = test_employee_service.create_employee(
            personal_number="89001",
            first_name="Jan",
            last_name="Otisk",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        topic = written_question_topic_service.create_topic(name="Okruh SEC9")
        question_image = self.sources / "zadani.png"
        _png(question_image, (200, 10, 10))
        colors = ((10, 180, 10), (10, 10, 200), (240, 240, 240))
        answers = []
        for index, color in enumerate(colors):
            path = self.sources / f"odpoved-{index}.png"
            _png(path, color)
            answers.append(
                WrittenAnswerInput(
                    image_source_path=str(path),
                    is_correct=index == 0,
                )
            )
        written_question_service.create_question(
            topic_id=topic.id,
            text=_QUESTION,
            answer_kind=ANSWER_KIND_IMAGE,
            answers=answers,
            question_image_source_path=str(question_image),
        )
        test = test_definition_service.create_test(
            name="Zkouška SEC9",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=120,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(topic.id, 1)],
        )
        return test_exam_service.prepare_exam(
            employee_id=employee.id,
            test_id=test.id,
            exam_date=date(2026, 10, 8),
            rng=_Rng(),
        )

    def _wipe(self) -> None:
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
