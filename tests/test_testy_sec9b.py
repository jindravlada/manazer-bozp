"""TESTY-SEC-9b: vadný obrázek zkoušku nespustí nebo ji technicky ukončí."""

from __future__ import annotations

import importlib
import os
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication, QCheckBox, QLabel, QPlainTextEdit, QPushButton

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec9b-"))
_STARTED = datetime(2026, 10, 8, 12, 0, 0)
_QUESTION = "Otázka s kontrolou obrázku"
_TRIALS = 8

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        ANSWER_KIND_IMAGE,
        EXAM_PROTOCOL_NOT_APPLICABLE,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_TECHNICAL,
        EXAM_STATUS_TECHNICAL_LABEL,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
        WRITTEN_FINISH_TECHNICAL,
        WRITTEN_RESULT_FAILED,
        WRITTEN_RESULT_PASSED,
        WRITTEN_RESULT_UNRATED,
        WRITTEN_RESULT_UNRATED_LABEL,
        WRITTEN_TECHNICAL_END_TEXT,
    )
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.sluzby import test_exam_service as exam_module
    from moduly.testy.sluzby.exam_protocol_export_service import protocol_block_reason
    from moduly.testy.sluzby.exam_validity_service import (
        exam_validity_service,
        is_successful_exam,
    )
    from moduly.testy.sluzby.test_definition_service import (
        TestTopicQuota,
        test_definition_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import (
        SNAPSHOT_REASON_INVALID_PATH,
        SNAPSHOT_REASON_LABELS,
        SNAPSHOT_REASON_MISMATCH,
        SNAPSHOT_REASON_MISSING,
        SNAPSHOT_REASON_UNREADABLE,
        SNAPSHOT_REASON_UNVERIFIED,
        snapshot_slot_problem,
        test_exam_service,
    )
    from moduly.testy.sluzby.written_exam_service import (
        FixedWrittenExamClock,
        WrittenExamImageBlocked,
        WrittenExamTechnical,
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


def _png(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (24, 16), color).save(path, "PNG")


class TechnicalExamEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        workplace = settings_service.save_workplace(name="Provoz SEC9b")
        role = responsibility_role_service.create_role(name="Mistr SEC9b")
        cls.employee = test_employee_service.create_employee(
            personal_number="89002",
            first_name="Eva",
            last_name="Kontrola",
            workplace_id=workplace.id,
            responsibility_role_ids=[role.id],
        )
        cls.topic = written_question_topic_service.create_topic(name="Okruh SEC9b")
        sources = _TMP / "zdroje"
        sources.mkdir(exist_ok=True)
        question_image = sources / "zadani.png"
        _png(question_image, (200, 10, 10))
        colors = ((10, 180, 10), (10, 10, 200), (240, 240, 240))
        answers = []
        for index, color in enumerate(colors):
            path = sources / f"odpoved-{index}.png"
            _png(path, color)
            answers.append(
                WrittenAnswerInput(
                    image_source_path=str(path),
                    is_correct=index == 0,
                )
            )
        written_question_service.create_question(
            topic_id=cls.topic.id,
            text=_QUESTION,
            answer_kind=ANSWER_KIND_IMAGE,
            answers=answers,
            question_image_source_path=str(question_image),
        )
        cls.test = test_definition_service.create_test(
            name="Zkouška SEC9b",
            uses_written=True,
            allowed_wrong_answers=0,
            seconds_per_question=120,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_topics=[TestTopicQuota(cls.topic.id, 1)],
        )

    def setUp(self) -> None:
        self._windows: list[WrittenExamWindow] = []
        self._dialogs: list[QApplication] = []
        self.exam = test_exam_service.prepare_exam(
            employee_id=self.employee.id,
            test_id=self.test.id,
            exam_date=date(2026, 10, 8),
            rng=_Rng(),
        )
        self.question = test_exam_service.get_written_questions(self.exam.id)[0]
        self.answers = test_exam_service.get_written_answers(self.question.id)
        self.original = {
            row.image_stored_path: self._file(row.image_stored_path).read_bytes()
            for row in (self.question, *self.answers)
        }
        self.question_hash = self.question.image_sha256
        self.answer_hashes = {row.id: row.image_sha256 for row in self.answers}

    def tearDown(self) -> None:
        for window in self._windows:
            window.release_testing_lock()
        QApplication.processEvents()

    def test_empty_slot_is_not_a_problem(self) -> None:
        self.assertIsNone(
            snapshot_slot_problem(
                question_position=1,
                role="prompt",
                letter="",
                relative_path="",
                expected_sha256="",
            )
        )

    def test_broken_images_block_start_without_result_or_clock(self) -> None:
        problems = self._break_every_slot()
        with self.assertRaises(WrittenExamImageBlocked) as caught:
            written_exam_service.start(self.exam.id, now=_STARTED)
        self.assertEqual(len(caught.exception.problems), 4)
        reasons = {item.reason for item in caught.exception.problems}
        self.assertEqual(
            reasons,
            {
                SNAPSHOT_REASON_MISMATCH,
                SNAPSHOT_REASON_MISSING,
                SNAPSHOT_REASON_INVALID_PATH,
                SNAPSHOT_REASON_UNVERIFIED,
            },
        )
        fresh = self._fresh()
        self.assertEqual(fresh.status, EXAM_STATUS_PREPARED)
        self.assertIsNone(fresh.written_started_at)
        self.assertIsNone(fresh.written_finished_at)
        self.assertIsNone(fresh.written_result)
        self.assertIsNone(fresh.exam_result)
        self.assertEqual(fresh.written_finish_reason, "")
        self.assertFalse(written_exam_service.can_continue(self.exam.id))
        self._assert_hashes_unchanged()
        self.assertTrue(problems)

    def test_diagnostic_lists_every_problem_and_copies_full_paths(self) -> None:
        self._break_every_slot()
        with self.assertRaises(WrittenExamImageBlocked) as caught:
            written_exam_service.start(self.exam.id, now=_STARTED)
        dialog = SnapshotImageDiagnosticDialog(caught.exception.problems)
        dialog.show()
        text = dialog.findChild(QPlainTextEdit, "snapshot-image-diagnostic-text")
        assert text is not None
        shown = text.toPlainText()
        self.assertIn("Otázka 1, obrázek zadání", shown)
        self.assertIn("Otázka 1, obrázek odpovědi A", shown)
        self.assertIn("Otázka 1, obrázek odpovědi B", shown)
        self.assertIn("Otázka 1, obrázek odpovědi C", shown)
        for reason in (
            SNAPSHOT_REASON_MISMATCH,
            SNAPSHOT_REASON_MISSING,
            SNAPSHOT_REASON_INVALID_PATH,
            SNAPSHOT_REASON_UNVERIFIED,
        ):
            self.assertIn(SNAPSHOT_REASON_LABELS[reason], shown)
        self.assertIn(self.question.image_stored_path, shown)
        self.assertNotIn("Úplná cesta:", shown)
        full = dialog.detailed_text()
        self.assertIn("Úplná cesta:", full)
        self.assertIn("nelze bezpečně zobrazit", full)
        box = dialog.findChild(QCheckBox, "snapshot-image-diagnostic-full-path")
        assert box is not None
        box.setChecked(True)
        toggled = text.toPlainText()
        self.assertIn("Úplná cesta:", toggled)
        self.assertIn(
            str(test_exam_service.resolve_snapshot_image(self.answers[0].image_stored_path) or ""),
            toggled.replace("Úplná cesta: nelze bezpečně zobrazit.", ""),
        )
        button = dialog.findChild(QPushButton, "snapshot-image-diagnostic-copy")
        assert button is not None
        self.assertEqual(button.text(), "Zkopírovat podrobnosti")
        button.click()
        QApplication.processEvents()
        copied = QApplication.clipboard().text()
        self.assertEqual(copied, dialog.detailed_text())
        self.assertIn("Časový limit nebyl spuštěn", copied)
        self.assertIn("Úplná cesta:", copied)
        dialog.close()

    def test_repaired_image_allows_the_same_prepared_exam_to_start(self) -> None:
        self._flip(self.question.image_stored_path)
        with self.assertRaises(WrittenExamImageBlocked):
            written_exam_service.start(self.exam.id, now=_STARTED)
        self._restore(self.question.image_stored_path)
        started = written_exam_service.start(self.exam.id, now=_STARTED)
        self.assertEqual(started.status, "started")
        self.assertEqual(started.written_started_at, _STARTED)
        self.assertIsNone(started.written_result)
        self.assertEqual(self._fresh().written_finish_reason, "")

    def test_changed_image_ends_the_attempt_without_scoring(self) -> None:
        self._start_and_answer()
        self._flip(self.question.image_stored_path)
        moment = _STARTED + timedelta(seconds=10)
        with self.assertRaises(WrittenExamTechnical):
            written_exam_service.save_choice(
                self.exam.id,
                self.question.id,
                self.answers[1].id,
                now=moment,
            )
        self._assert_technical(moment)
        self.assertEqual(written_exam_service.choices(self.exam.id)[0].selected_letter, "A")
        self.assertIn("Nesouhlasí SHA-256.", self._fresh().written_technical_detail)
        self.assertIn(self.question.image_stored_path, self._fresh().written_technical_detail)
        self.assertNotIn(str(_TMP), self._fresh().written_technical_detail)

    def test_deleted_image_ends_the_attempt_without_scoring(self) -> None:
        self._start_and_answer()
        self._file(self.answers[0].image_stored_path).unlink()
        moment = _STARTED + timedelta(seconds=12)
        reason = written_exam_service.submit(self.exam.id, now=moment)
        self.assertEqual(reason, WRITTEN_FINISH_TECHNICAL)
        self._assert_technical(moment)
        self.assertIn("Soubor nebyl nalezen.", self._fresh().written_technical_detail)
        self.assertEqual(written_exam_service.choices(self.exam.id)[0].selected_letter, "A")

    def test_window_stops_without_paths_or_a_normal_handover(self) -> None:
        self._start_and_answer()
        window = WrittenExamWindow(
            self.exam.id,
            clock=FixedWrittenExamClock(_STARTED + timedelta(seconds=3)),
        )
        self._windows.append(window)
        self._flip(self.question.image_stored_path)
        window._jump(0)
        fresh = self._fresh()
        self.assertEqual(fresh.status, EXAM_STATUS_TECHNICAL)
        self.assertEqual(fresh.exam_result, WRITTEN_RESULT_UNRATED)
        assert window._technical is not None
        self.assertEqual(window._technical.text(), WRITTEN_TECHNICAL_END_TEXT)
        self.assertNotIn(self.question.image_stored_path, window._technical.text())
        self.assertNotIn("Vyhověl", window._technical.text())
        self.assertNotIn("Nevyhověl", window._technical.text())
        self.assertFalse(window._timer.isActive())
        self.assertIsNone(window._handover)
        self.assertFalse(written_exam_service.can_continue(self.exam.id))

    def test_technical_exam_stays_in_history_and_allows_a_new_attempt(self) -> None:
        self._start_and_answer()
        passed_until = self._fresh().valid_until
        self._flip(self.question.image_stored_path)
        with self.assertRaises(WrittenExamTechnical):
            written_exam_service.ensure_snapshot_images(
                self.exam.id,
                now=_STARTED + timedelta(seconds=8),
            )
        fresh = self._fresh()
        self.assertEqual(fresh.status, EXAM_STATUS_TECHNICAL)
        self.assertIsNone(fresh.valid_until)
        self.assertIsNotNone(passed_until)
        detail = TestExamDetailDialog(exam_id=self.exam.id)
        summary = detail.findChild(QLabel, "exam-written-summary")
        assert summary is not None
        self.assertIn(EXAM_STATUS_TECHNICAL_LABEL, summary.text())
        self.assertIn(WRITTEN_RESULT_UNRATED_LABEL, summary.text())
        self.assertIn("Nesouhlasí SHA-256.", summary.text())
        self.assertIn("Ukončeno:", summary.text())
        self.assertNotIn("None", summary.text())
        self.assertNotIn("Správně:", summary.text())
        protocol = detail.findChild(QLabel, "exam-protocol-status")
        assert protocol is not None
        self.assertEqual(protocol.text(), EXAM_PROTOCOL_NOT_APPLICABLE)
        title = detail.findChild(QLabel, "written-text-1")
        assert title is not None
        self.assertIn(_QUESTION, title.text())
        detail.deleteLater()
        self.assertIsNotNone(protocol_block_reason(fresh))
        self.assertFalse(is_successful_exam(fresh))
        with self.assertRaises(Exception):
            written_exam_service.start(self.exam.id, now=_STARTED + timedelta(minutes=5))
        restored = self._prepare_again()
        started = written_exam_service.start(restored.id, now=_STARTED + timedelta(minutes=10))
        self.assertEqual(started.status, "started")
        self.assertIsNone(started.written_result)

    def test_technical_end_does_not_change_existing_validity(self) -> None:
        self._pass_current_exam()
        passed = self._fresh()
        assert passed.valid_until is not None
        follow = self._prepare_again()
        written_exam_service.start(follow.id, now=_STARTED + timedelta(hours=1))
        question = test_exam_service.get_written_questions(follow.id)[0]
        self._flip(question.image_stored_path)
        with self.assertRaises(WrittenExamTechnical):
            written_exam_service.ensure_snapshot_images(
                follow.id,
                now=_STARTED + timedelta(hours=1, seconds=5),
            )
        passed_again = test_exam_service.get_exam(passed.id)
        assert passed_again is not None
        self.assertEqual(passed_again.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(passed_again.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(passed_again.valid_until, passed.valid_until)
        technical = test_exam_service.get_exam(follow.id)
        assert technical is not None
        self.assertFalse(is_successful_exam(technical))
        self.assertTrue(is_successful_exam(passed_again))
        rows = exam_validity_service.list_rows(today=date(2026, 10, 8))
        row = next(
            item
            for item in rows
            if item.employee_id == self.employee.id
            and item.test_definition_id == self.test.id
        )
        self.assertEqual(row.last_success_exam_id, passed.id)
        self.assertEqual(row.valid_until, passed.valid_until)
        self.assertEqual(technical.status, EXAM_STATUS_TECHNICAL)
        exams = test_exam_service.list_exams()
        started = sum(
            1
            for item in exams
            if item.employee_id == self.employee.id
            and item.test_definition_id == self.test.id
            and item.status == "started"
        )
        prepared = sum(
            1
            for item in exams
            if item.employee_id == self.employee.id
            and item.test_definition_id == self.test.id
            and item.status == EXAM_STATUS_PREPARED
        )
        self.assertEqual(row.in_progress_count, started)
        self.assertEqual(row.prepared_count, prepared)
        self.assertNotEqual(technical.status, "started")

    def test_completed_exam_keeps_its_result_when_images_break(self) -> None:
        self._pass_current_exam()
        before = self._fresh()
        self._flip(self.question.image_stored_path)
        written_exam_service.ensure_snapshot_images(
            self.exam.id,
            now=_STARTED + timedelta(days=1),
        )
        reason = written_exam_service.sync_deadline(
            self.exam.id,
            now=_STARTED + timedelta(days=1),
        )
        fresh = self._fresh()
        self.assertEqual(fresh.status, EXAM_STATUS_COMPLETED)
        self.assertEqual(fresh.written_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(fresh.exam_result, WRITTEN_RESULT_PASSED)
        self.assertEqual(fresh.written_finish_reason, before.written_finish_reason)
        self.assertEqual(fresh.written_evaluated_at, before.written_evaluated_at)
        self.assertEqual(fresh.valid_until, before.valid_until)
        self.assertNotEqual(reason, WRITTEN_FINISH_TECHNICAL)
        self._assert_hashes_unchanged()
        detail = TestExamDetailDialog(exam_id=self.exam.id)
        notice = detail.findChild(QLabel, "written-image-1-notice")
        assert notice is not None
        self.assertIn("integrity", notice.text())
        self.assertIsNone(detail.findChild(QLabel, "written-image-1"))
        detail.deleteLater()

    def test_legacy_snapshot_without_hash_is_not_rewritten(self) -> None:
        self._point_hash(self.question.id, "")
        before_file = self._file(self.question.image_stored_path).read_bytes()
        with self.assertRaises(WrittenExamImageBlocked) as caught:
            written_exam_service.start(self.exam.id, now=_STARTED)
        self.assertIn(
            SNAPSHOT_REASON_UNVERIFIED,
            {item.reason for item in caught.exception.problems},
        )
        stored = test_exam_service.get_written_questions(self.exam.id)[0]
        self.assertEqual(stored.image_sha256, "")
        self.assertEqual(self._file(stored.image_stored_path).read_bytes(), before_file)
        self.assertEqual(self._fresh().status, EXAM_STATUS_PREPARED)

        self._point_hash(self.question.id, self.question_hash)
        self._pass_current_exam()
        self._point_hash(self.question.id, "")
        written_exam_service.ensure_snapshot_images(
            self.exam.id,
            now=_STARTED + timedelta(days=2),
        )
        finished = test_exam_service.get_written_questions(self.exam.id)[0]
        self.assertEqual(finished.image_sha256, "")
        self.assertEqual(self._fresh().status, EXAM_STATUS_COMPLETED)
        self.assertEqual(self._fresh().written_result, WRITTEN_RESULT_PASSED)

    def test_unreadable_image_is_named_separately(self) -> None:
        path = self._file(self.question.image_stored_path)
        real_open = exam_module.os.open

        def wrapped(target, flags, mode=0o777, *, dir_fd=None):
            if dir_fd is None and os.fsdecode(target) == str(path):
                raise PermissionError("nelze číst")
            return real_open(target, flags, mode, dir_fd=dir_fd)

        with patch.object(exam_module.os, "open", wrapped):
            with self.assertRaises(WrittenExamImageBlocked) as caught:
                written_exam_service.start(self.exam.id, now=_STARTED)
        self.assertIn(
            SNAPSHOT_REASON_UNREADABLE,
            {item.reason for item in caught.exception.problems},
        )
        self.assertEqual(self._fresh().status, EXAM_STATUS_PREPARED)

    def test_concurrent_operations_cannot_overwrite_technical_end(self) -> None:
        for trial in range(_TRIALS):
            exam = self._prepare_again()
            written_exam_service.start(exam.id, now=_STARTED)
            question = test_exam_service.get_written_questions(exam.id)[0]
            answers = test_exam_service.get_written_answers(question.id)
            written_exam_service.save_choice(
                exam.id,
                question.id,
                answers[0].id,
                now=_STARTED + timedelta(seconds=2),
            )
            kept = written_exam_service.choices(exam.id)[0].selected_letter
            self._flip(question.image_stored_path)
            moment = _STARTED + timedelta(seconds=5)
            expired = _STARTED + timedelta(seconds=180)
            save = lambda: written_exam_service.save_choice(
                exam.id,
                question.id,
                answers[1].id,
                now=moment,
            )
            finish = lambda: written_exam_service.submit(exam.id, now=moment)
            expire = lambda: written_exam_service.sync_deadline(exam.id, now=expired)
            if trial % 3 == 0:
                outcome = self._race(save, finish)
            elif trial % 3 == 1:
                outcome = self._race(finish, expire)
            else:
                outcome = self._race(save, expire)
            self._assert_no_lock(outcome)
            fresh = test_exam_service.get_exam(exam.id)
            assert fresh is not None
            self.assertEqual(fresh.status, EXAM_STATUS_TECHNICAL)
            self.assertEqual(fresh.written_finish_reason, WRITTEN_FINISH_TECHNICAL)
            self.assertEqual(fresh.written_result, WRITTEN_RESULT_UNRATED)
            self.assertEqual(fresh.exam_result, WRITTEN_RESULT_UNRATED)
            self.assertNotEqual(fresh.exam_result, WRITTEN_RESULT_PASSED)
            self.assertNotEqual(fresh.exam_result, WRITTEN_RESULT_FAILED)
            self.assertIsNone(fresh.written_evaluated_at)
            self.assertIsNone(fresh.written_correct_count)
            stored = written_exam_service.choices(exam.id)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0].selected_letter, kept)
            self._flip(question.image_stored_path)
            again = written_exam_service.submit(
                exam.id,
                now=moment + timedelta(seconds=1),
            )
            self.assertEqual(again, WRITTEN_FINISH_TECHNICAL)
            after = test_exam_service.get_exam(exam.id)
            assert after is not None
            self.assertEqual(after.written_result, WRITTEN_RESULT_UNRATED)
            self.assertEqual(after.written_finished_at, fresh.written_finished_at)
            self.assertEqual(after.written_technical_detail, fresh.written_technical_detail)

    def _start_and_answer(self) -> None:
        written_exam_service.start(self.exam.id, now=_STARTED)
        written_exam_service.save_choice(
            self.exam.id,
            self.question.id,
            self.answers[0].id,
            now=_STARTED + timedelta(seconds=1),
        )

    def _pass_current_exam(self) -> None:
        self._start_and_answer()
        reason = written_exam_service.submit(
            self.exam.id,
            now=_STARTED + timedelta(seconds=4),
        )
        self.assertEqual(reason, "submitted")
        fresh = self._fresh()
        self.assertEqual(fresh.written_result, WRITTEN_RESULT_PASSED)

    def _assert_technical(self, moment: datetime) -> None:
        fresh = self._fresh()
        self.assertEqual(fresh.status, EXAM_STATUS_TECHNICAL)
        self.assertEqual(fresh.written_finish_reason, WRITTEN_FINISH_TECHNICAL)
        self.assertEqual(fresh.written_result, WRITTEN_RESULT_UNRATED)
        self.assertEqual(fresh.exam_result, WRITTEN_RESULT_UNRATED)
        self.assertEqual(fresh.written_finished_at, moment)
        self.assertIsNone(fresh.written_evaluated_at)
        self.assertIsNone(fresh.written_question_count)
        self.assertIsNone(fresh.written_correct_count)
        self.assertIsNone(fresh.written_incorrect_count)
        self.assertIsNone(fresh.written_unanswered_count)
        self.assertIsNone(fresh.valid_until)
        self.assertTrue(fresh.written_technical_detail.strip())
        self.assertFalse(written_exam_service.can_continue(self.exam.id))
        self.assertFalse(is_successful_exam(fresh))
        self._assert_hashes_unchanged()

    def _break_every_slot(self) -> list:
        self._flip(self.question.image_stored_path)
        self._file(self.answers[0].image_stored_path).unlink()
        with get_session() as session:
            row = session.get(TestExamWrittenAnswer, self.answers[1].id)
            assert row is not None
            row.image_stored_path = "../mimo-uloziste/tajne.png"
            other = session.get(TestExamWrittenAnswer, self.answers[2].id)
            assert other is not None
            other.image_sha256 = ""
            session.commit()
        self.answers = test_exam_service.get_written_answers(self.question.id)
        return test_exam_service.get_written_questions(self.exam.id)

    def _flip(self, relative: str) -> None:
        path = self._file(relative)
        data = bytearray(path.read_bytes())
        data[-1] ^= 0x01
        path.write_bytes(bytes(data))

    def _restore(self, relative: str) -> None:
        self._file(relative).write_bytes(self.original[relative])

    def _file(self, relative: str) -> Path:
        path = test_exam_service.resolve_snapshot_image(relative)
        assert path is not None
        return path

    def _point_hash(self, question_id: int, digest: str) -> None:
        with get_session() as session:
            row = session.get(TestExamWrittenQuestion, question_id)
            assert row is not None
            row.image_sha256 = digest
            session.commit()

    def _assert_hashes_unchanged(self) -> None:
        question = test_exam_service.get_written_questions(self.exam.id)[0]
        if question.image_sha256:
            self.assertEqual(question.image_sha256, self.question_hash)
        for answer in test_exam_service.get_written_answers(question.id):
            if answer.image_sha256:
                self.assertEqual(answer.image_sha256, self.answer_hashes[answer.id])

    def _fresh(self) -> TestExam:
        exam = test_exam_service.get_exam(self.exam.id)
        assert exam is not None
        return exam

    def _prepare_again(self):
        return test_exam_service.prepare_exam(
            employee_id=self.employee.id,
            test_id=self.test.id,
            exam_date=date(2026, 10, 8),
            rng=_Rng(),
        )

    def _race(self, first, second) -> dict:
        barrier = threading.Barrier(2)
        box: dict = {}

        def run(name, function):
            barrier.wait(timeout=5)
            try:
                box[name] = ("ok", function())
            except Exception as exc:
                box[name] = ("err", exc)

        threads = [
            threading.Thread(target=run, args=("a", first)),
            threading.Thread(target=run, args=("b", second)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), "souběžná operace se nezavřela")
        return box

    def _assert_no_lock(self, outcome: dict) -> None:
        for name, item in outcome.items():
            if item[0] != "err":
                continue
            self.assertNotIn("locked", str(item[1]).lower(), f"{name}: {item[1]!r}")
