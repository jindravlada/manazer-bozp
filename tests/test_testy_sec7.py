"""TESTY-SEC-7: neplatná cesta ke zmrazenému obrázku neshodí zkoušku ani export."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QLabel, QPlainTextEdit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec7-"))
_STARTED = datetime(2026, 10, 8, 10, 0, 0)
_SECRET_NAME = "secret-sec7.png"
_SECRET_MARK = b"SECRET-OUTSIDE-SEC7"
_QUESTION = "Otázka zůstane vidět"

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
        ANSWER_KIND_TEXT,
        EXAMINER_MODE_NONE,
        EXAM_STATUS_PREPARED,
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
    from moduly.testy.sluzby.paper_test_export_service import paper_test_export_service
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.sluzby.written_exam_service import (
        WrittenExamImageBlocked,
        written_exam_service,
    )
    from moduly.testy.sluzby.written_question_service import (
        WrittenAnswerInput,
        written_question_service,
    )
    from moduly.testy.sluzby.written_question_topic_service import (
        written_question_topic_service,
    )
    from moduly.testy.ui.snapshot_image_diagnostic_dialog import (
        SnapshotImageDiagnosticDialog,
    )
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog
    from moduly.testy.ui.written_exam_window import WrittenExamWindow


class _Rng:
    def sample(self, population, k):
        return list(population)[:k]

    def shuffle(self, items):
        return None


def _text_answers() -> list[WrittenAnswerInput]:
    return [
        WrittenAnswerInput(text="první odpověď", is_correct=True),
        WrittenAnswerInput(text="druhá odpověď"),
        WrittenAnswerInput(text="třetí odpověď"),
    ]


class SnapshotImagePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._windows: list[WrittenExamWindow] = []
        self.outside = _TMP / "mimo-uloziste"
        self.outside.mkdir(exist_ok=True)
        self.secret = self.outside / _SECRET_NAME
        self.secret.write_bytes(_SECRET_MARK)
        self.opened: list[str] = []
        attachments = storage_service.attachments_dir.resolve()
        self.assertFalse(self.secret.resolve().is_relative_to(attachments))
        self._wipe()
        self.output = _TMP / "export"
        self.output.mkdir(exist_ok=True)

    def tearDown(self) -> None:
        for window in self._windows:
            window.release_testing_lock()
        QApplication.processEvents()

    def test_valid_path_stays_inside_storage(self) -> None:
        relative = "test_exam_snapshot/platny.png"
        stored = storage_service.attachments_dir / relative
        stored.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8), (20, 40, 60)).save(stored, "PNG")
        with self._watch_opens():
            resolved = test_exam_service.resolve_snapshot_image(relative)
        assert resolved is not None
        self.assertTrue(resolved.is_file())
        self.assertTrue(resolved.resolve().is_relative_to(storage_service.attachments_dir.resolve()))
        self.assertEqual(self.opened, [])
        self.assertEqual(self.secret.read_bytes(), _SECRET_MARK)

    def test_rejected_paths_return_none_without_opening_outside(self) -> None:
        link_dir = storage_service.attachments_dir / "test_exam_snapshot"
        link_dir.mkdir(parents=True, exist_ok=True)
        link = link_dir / "odkaz.png"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(self.secret)
        rejected = (
            "test_exam_snapshot/chybi.png",
            "../mimo-uloziste/secret-sec7.png",
            "test_exam_snapshot/../../mimo-uloziste/secret-sec7.png",
            str(self.secret),
            "test_exam_snapshot/odkaz.png",
            "obrazek\x00.png",
            "a" * 4000 + ".png",
        )
        with self._watch_opens():
            for relative in rejected:
                self.assertIsNone(
                    test_exam_service.resolve_snapshot_image(relative),
                    relative,
                )
        self.assertEqual(self.opened, [])
        self.assertEqual(self.secret.read_bytes(), _SECRET_MARK)

    def test_lookup_oserror_returns_none_and_unexpected_error_propagates(self) -> None:
        relative = "test_exam_snapshot/platny.png"
        stored = storage_service.attachments_dir / relative
        stored.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (4, 4), (1, 2, 3)).save(stored, "PNG")
        with patch.object(Path, "is_file", side_effect=OSError("nelze přečíst")):
            self.assertIsNone(test_exam_service.resolve_snapshot_image(relative))
        with patch.object(Path, "is_file", side_effect=RuntimeError("programová chyba")):
            with self.assertRaises(RuntimeError):
                test_exam_service.resolve_snapshot_image(relative)

    def test_exam_detail_and_export_skip_invalid_image(self) -> None:
        exam = self._prepared_exam()
        self._corrupt_image_paths(exam.id)
        detail = TestExamDetailDialog(exam_id=exam.id)
        title = detail.findChild(QLabel, "written-text-1")
        assert title is not None
        self.assertIn(_QUESTION, title.text())
        self.assertIn("první odpověď", detail.findChild(QLabel, "answer-1-A").text())
        self.assertIsNone(detail.findChild(QLabel, "written-image-1"))
        detail.deleteLater()

        target = self.output / "test.odt"
        before = test_exam_service.get_exam(exam.id)
        with self._watch_opens():
            paper_test_export_service.export(exam.id, target)
        self.assertTrue(target.is_file())
        self.assertNotIn(_SECRET_MARK, target.read_bytes())
        with zipfile.ZipFile(target) as archive:
            content = archive.read("content.xml")
        self.assertIn(_QUESTION.encode("utf-8"), content)
        self.assertIn("první odpověď".encode("utf-8"), content)
        after = test_exam_service.get_exam(exam.id)
        self.assertEqual(after.status, before.status)
        self.assertEqual(after.written_result, before.written_result)
        self.assertEqual(after.exam_result, before.exam_result)
        self.assertEqual(self.opened, [])
        self.assertEqual(self.secret.read_bytes(), _SECRET_MARK)

    def test_written_exam_opens_and_accepts_answer_without_image(self) -> None:
        exam = self._prepared_exam()
        self._corrupt_image_paths(exam.id)
        with self._watch_opens():
            with self.assertRaises(WrittenExamImageBlocked) as caught:
                written_exam_service.start(exam.id, now=_STARTED)
        self.assertIn("nelze zahájit", str(caught.exception))
        self.assertGreaterEqual(len(caught.exception.problems), 1)
        dialog = SnapshotImageDiagnosticDialog(caught.exception.problems)
        dialog.show()
        intro = dialog.findChild(QLabel, "snapshot-image-diagnostic-intro")
        detail = dialog.findChild(QPlainTextEdit, "snapshot-image-diagnostic-text")
        assert intro is not None and detail is not None
        self.assertIn("nelze zahájit", intro.text())
        self.assertIn("Časový limit nebyl spuštěn", intro.text())
        shown = detail.toPlainText()
        self.assertIn("Soubor:", shown)
        self.assertIn("../mimo-uloziste/secret-sec7.png", shown)
        dialog.close()
        current = test_exam_service.get_exam(exam.id)
        self.assertEqual(current.status, EXAM_STATUS_PREPARED)
        self.assertIsNone(current.written_started_at)
        self.assertIsNone(current.written_finished_at)
        self.assertFalse(current.written_result)
        self.assertFalse(current.exam_result)
        self.assertEqual(current.written_finish_reason or "", "")
        self.assertEqual(written_exam_service.choices(exam.id), [])
        self.assertEqual(self.opened, [])
        self.assertEqual(self.secret.read_bytes(), _SECRET_MARK)

    def _corrupt_image_paths(self, exam_id: int) -> None:
        question = test_exam_service.get_written_questions(exam_id)[0]
        answers = test_exam_service.get_written_answers(question.id)
        with get_session() as session:
            row = session.get(TestExamWrittenQuestion, question.id)
            assert row is not None
            row.image_stored_path = "../mimo-uloziste/secret-sec7.png"
            for answer, relative in zip(
                answers,
                (
                    str(self.secret),
                    "test_exam_snapshot/odkaz.png",
                    "obrazek\x00.png",
                ),
                strict=True,
            ):
                stored = session.get(TestExamWrittenAnswer, answer.id)
                assert stored is not None
                stored.image_stored_path = relative
            session.commit()
        link_dir = storage_service.attachments_dir / "test_exam_snapshot"
        link_dir.mkdir(parents=True, exist_ok=True)
        link = link_dir / "odkaz.png"
        if not link.is_symlink():
            if link.exists():
                link.unlink()
            link.symlink_to(self.secret)

    def _prepared_exam(self):
        workplace = settings_service.save_workplace(name="Provoz SEC7")
        role = responsibility_role_service.create_role(name="Mistr SEC7")
        employee = test_employee_service.create_employee(
            personal_number="87001",
            first_name="Jan",
            last_name="Cesta",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        topic = written_question_topic_service.create_topic(name="Okruh SEC7")
        image = _TMP / "zdroj.png"
        Image.new("RGB", (32, 16), (10, 20, 30)).save(image, "PNG")
        written_question_service.create_question(
            topic_id=topic.id,
            text=_QUESTION,
            answer_kind=ANSWER_KIND_TEXT,
            answers=_text_answers(),
            question_image_source_path=str(image),
        )
        test = test_definition_service.create_test(
            name="Zkouška SEC7",
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
            exam_date=_STARTED.date(),
            rng=_Rng(),
        )

    def _watch_opens(self):
        real_open = os.open

        def wrapped(path, flags, mode=0o777, *, dir_fd=None):
            if dir_fd is None and not isinstance(path, int):
                decoded = os.fsdecode(path)
                if _SECRET_NAME in decoded:
                    self.opened.append(decoded)
            return real_open(path, flags, mode, dir_fd=dir_fd)

        return patch("os.open", wrapped)

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
