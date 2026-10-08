"""TESTY-SEC-8: velikost a platnost nově připojovaného PDF protokolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec8-"))
_LIMIT = 20 * 1024 * 1024
_SIZE_MESSAGE = "Podepsaný protokol nesmí být větší než 20 MB."

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from sqlalchemy import delete, func, select

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from core.services.storage_service import storage_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EXAM_STATUS_COMPLETED,
        EXAMINER_MODE_NONE,
        VALIDITY_UNIT_YEARS,
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
    from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.sluzby import exam_signed_protocol_service as protocol_module
    from moduly.testy.sluzby.exam_signed_protocol_service import (
        ENTITY_TYPE,
        ExamSignedProtocolError,
        exam_signed_protocol_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service


def _pdf(body: bytes, trailing: bytes = b"\n") -> bytes:
    return b"%PDF-1.4\n" + body + b"\n%%EOF" + trailing


def _write_sized_pdf(path: Path, size: int) -> None:
    prefix = b"%PDF-1.4\n"
    suffix = b"\n%%EOF\n"
    filler = size - len(prefix) - len(suffix)
    if filler < 0:
        raise AssertionError(size)
    chunk = b"\n" * (1024 * 1024)
    with path.open("wb") as handle:
        handle.write(prefix)
        remaining = filler
        while remaining:
            piece = chunk if remaining >= len(chunk) else b"\n" * remaining
            handle.write(piece)
            remaining -= len(piece)
        handle.write(suffix)


def _wipe() -> None:
    protocol_dir = storage_service.attachments_dir / ENTITY_TYPE
    if protocol_dir.is_symlink() or protocol_dir.exists():
        _unlink_tree(protocol_dir)
    with get_session() as session:
        session.execute(delete(TestExamWrittenChoice))
        session.execute(delete(TestExamWrittenAnswer))
        session.execute(delete(TestExamWrittenQuestion))
        session.execute(delete(TestExamOralQuestion))
        session.execute(delete(TestExamExaminer))
        session.execute(delete(TestExam))
        session.execute(delete(TestExamValidityTracking))
        session.execute(delete(Attachment).where(Attachment.entity_type == ENTITY_TYPE))
        session.execute(delete(TestDefinitionWrittenTopic))
        session.execute(delete(TestDefinitionOralTopic))
        session.execute(delete(TestDefinition))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.commit()


def _unlink_tree(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        for child in list(path.iterdir()):
            _unlink_tree(child)
        path.rmdir()
        return
    if path.exists():
        path.unlink()


class SignedProtocolPdfValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()
        self.files = _TMP / "zdroje"
        if self.files.exists():
            _unlink_tree(self.files)
        self.files.mkdir()
        self.workplace = settings_service.save_workplace(name="Hala protokolů SEC8")
        self.role = responsibility_role_service.create_role(name="Mistr protokolu SEC8")
        self.employee = test_employee_service.create_employee(
            personal_number="88001",
            first_name="Jan",
            last_name="Protokol",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        self.test = self._definition()
        self.exam = self._exam()
        self.assertEqual(protocol_module._MAX_PROTOCOL_BYTES, _LIMIT)

    def test_ordinary_signed_and_revised_pdf_are_stored(self) -> None:
        ordinary = self._write("bezny.pdf", _pdf(b"bezny text protokolu"))
        signed = self._write("podpis.pdf", self._signed_pdf())
        revised = self._write("revize.pdf", self._revised_pdf())
        attachment_id = exam_signed_protocol_service.attach(self.exam.id, ordinary)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(stored.read_bytes(), ordinary.read_bytes())
        self.assertFalse(stored.is_symlink())
        replaced = exam_signed_protocol_service.replace(self.exam.id, signed)
        self.assertNotEqual(replaced, attachment_id)
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            signed.read_bytes(),
        )
        second = exam_signed_protocol_service.replace(self.exam.id, revised)
        self.assertNotEqual(second, replaced)
        current = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(current.read_bytes(), revised.read_bytes())
        self.assertIn(b"%%EOF", current.read_bytes())
        self.assertEqual(current.read_bytes().count(b"%%EOF"), 2)
        self.assertEqual(self._attachment_count(), 3)
        self.assertEqual(len(self._protocol_pdfs()), 3)

    def test_size_limit_rejects_before_copy_and_keeps_exact_boundary(self) -> None:
        exact = self.files / "hranice.pdf"
        _write_sized_pdf(exact, _LIMIT)
        self.assertEqual(exact.stat().st_size, _LIMIT)
        before = self._protocol_pdfs()
        attachment_id = exam_signed_protocol_service.attach(self.exam.id, exact)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(stored.stat().st_size, _LIMIT)
        self.assertEqual(stored.read_bytes()[:9], b"%PDF-1.4\n")
        self.assertTrue(stored.read_bytes().endswith(b"%%EOF\n"))
        self.assertEqual(
            exam_signed_protocol_service.describe(self.exam.id).attachment_id,
            attachment_id,
        )

        oversized = self.files / "velky.pdf"
        _write_sized_pdf(oversized, _LIMIT + 1)
        with self.assertRaises(ExamSignedProtocolError) as rejected:
            exam_signed_protocol_service.replace(self.exam.id, oversized)
        self.assertEqual(str(rejected.exception), _SIZE_MESSAGE)
        self.assertEqual(
            exam_signed_protocol_service.describe(self.exam.id).attachment_id,
            attachment_id,
        )
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).stat().st_size,
            _LIMIT,
        )
        self.assertEqual(len(self._protocol_pdfs()), len(before) + 1)

    def test_empty_header_missing_end_and_appended_data_are_rejected(self) -> None:
        cases = {
            "prazdny.pdf": b"",
            "hlavicka.pdf": b"tohle neni pdf\n%%EOF\n",
            "bez-konce.pdf": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n",
            "za-koncem.pdf": _pdf(b"text", b"\nATTACHED-SEC8"),
            "dlouhy-dodatek.pdf": _pdf(b"text", b"\n" + b"X" * 4096),
        }
        for name, payload in cases.items():
            source = self._write(name, payload)
            with self.assertRaises(ExamSignedProtocolError) as rejected:
                exam_signed_protocol_service.attach(self.exam.id, source)
            self.assertIn("platné PDF", str(rejected.exception))
        whitespace = self._write("mezery.pdf", _pdf(b"text", b"\r\n\n"))
        exam_signed_protocol_service.attach(self.exam.id, whitespace)
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            whitespace.read_bytes(),
        )
        self.assertEqual(self._attachment_count(), 1)
        self.assertEqual(len(self._protocol_pdfs()), 1)

    def test_growth_during_copy_cannot_bypass_limit_or_orphan_a_file(self) -> None:
        original = self._write("puvodni.pdf", _pdf(b"puvodni"))
        first_id = exam_signed_protocol_service.attach(self.exam.id, original)
        original_bytes = exam_signed_protocol_service.validated_copy_path(
            self.exam.id
        ).read_bytes()
        names_before = sorted(path.name for path in self._protocol_pdfs())
        growing = self._write("rostouci.pdf", _pdf(b"rostouci"))
        real_open = protocol_module.os.open
        real_read = protocol_module.os.read
        watched: set[int] = set()
        inflated: set[int] = set()

        def wrapped_open(path, flags, mode=0o777, *, dir_fd=None):
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            if dir_fd is None and os.fsdecode(path) == str(growing):
                watched.add(fd)
            return fd

        def wrapped_read(fd, size):
            data = real_read(fd, size)
            if fd in watched and not data and fd not in inflated:
                inflated.add(fd)
                return b"X" * (_LIMIT + 1)
            return data

        with (
            patch.object(protocol_module.os, "open", wrapped_open),
            patch.object(protocol_module.os, "read", wrapped_read),
        ):
            with self.assertRaises(ExamSignedProtocolError) as rejected:
                exam_signed_protocol_service.replace(self.exam.id, growing)
        self.assertEqual(str(rejected.exception), _SIZE_MESSAGE)
        self.assertEqual(
            exam_signed_protocol_service.describe(self.exam.id).attachment_id,
            first_id,
        )
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            original_bytes,
        )
        self.assertEqual(
            sorted(path.name for path in self._protocol_pdfs()),
            names_before,
        )
        self.assertEqual(self._attachment_count(), 1)

    def test_existing_protocol_keeps_previous_rules(self) -> None:
        legacy = _pdf(b"stary", b"\nDODATEK-SEC8")
        planted = self._plant("protokol-stary.pdf", legacy)
        before = planted.read_bytes()
        opened = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(opened.read_bytes(), before)
        self.assertEqual(planted.read_bytes(), before)
        fresh = self._exam()
        source = self._write("novy-dodatek.pdf", legacy)
        with self.assertRaises(ExamSignedProtocolError) as rejected:
            exam_signed_protocol_service.attach(fresh.id, source)
        self.assertIn("platné PDF", str(rejected.exception))
        self.assertFalse(exam_signed_protocol_service.describe(fresh.id).attached)
        self.assertEqual(planted.read_bytes(), before)
        self.assertEqual(self._protocol_pdfs(), [planted])

        huge = self._plant_sparse(self._exam(), _LIMIT + 128)
        huge_size = huge.stat().st_size
        opened_huge = exam_signed_protocol_service.validated_copy_path(
            int(huge.parent.name)
        )
        self.assertEqual(opened_huge, huge)
        self.assertEqual(huge.stat().st_size, huge_size)

    def _signed_pdf(self) -> bytes:
        return _pdf(
            b"1 0 obj\n<< /Type /Sig /Filter /Adobe.PPKLite "
            b"/ByteRange [0 32 80 16] /Contents <308201> >>\nendobj\nstartxref\n9"
        )

    def _revised_pdf(self) -> bytes:
        first = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
        second = b"2 0 obj\n<< /Prev 9 >>\nendobj\nstartxref\n40\n%%EOF\n"
        return first + second

    def _write(self, name: str, payload: bytes) -> Path:
        path = self.files / name
        path.write_bytes(payload)
        return path

    def _plant(self, name: str, payload: bytes) -> Path:
        folder = storage_service.attachments_dir / ENTITY_TYPE / str(self.exam.id)
        folder.mkdir(parents=True)
        path = folder / name
        path.write_bytes(payload)
        self._link_planted(self.exam.id, path)
        return path

    def _plant_sparse(self, exam: TestExam, size: int) -> Path:
        folder = storage_service.attachments_dir / ENTITY_TYPE / str(exam.id)
        folder.mkdir(parents=True)
        path = folder / "protokol-velky.pdf"
        marker = b"%%EOF\n"
        with path.open("wb") as handle:
            handle.write(b"%PDF-1.4\n")
            handle.seek(size - len(marker))
            handle.write(marker)
            handle.truncate(size)
        self._link_planted(exam.id, path)
        return path

    def _link_planted(self, exam_id: int, path: Path) -> None:
        relative = path.relative_to(storage_service.attachments_dir).as_posix()
        with get_session() as session:
            attachment = Attachment(
                entity_type=ENTITY_TYPE,
                entity_id=exam_id,
                original_path=path.name,
                stored_path=relative,
                filename=path.name,
            )
            session.add(attachment)
            session.flush()
            stored = session.get(TestExam, exam_id)
            assert stored is not None
            stored.signed_protocol_attachment_id = int(attachment.id)
            session.commit()

    def _protocol_pdfs(self) -> list[Path]:
        root = storage_service.attachments_dir / ENTITY_TYPE
        if not root.exists() or root.is_symlink():
            return []
        found: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not (Path(dirpath) / dirname).is_symlink()
            ]
            for name in filenames:
                path = Path(dirpath) / name
                if not path.is_symlink() and path.suffix == ".pdf":
                    found.append(path)
        return found

    def _attachment_count(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(Attachment)
                    .where(Attachment.entity_type == ENTITY_TYPE)
                )
                or 0
            )

    def _definition(self) -> TestDefinition:
        test = TestDefinition(
            name="BOZP SEC8",
            description="",
            active=True,
            uses_written=False,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
        )
        with get_session() as session:
            session.add(test)
            session.commit()
            session.refresh(test)
            session.expunge(test)
        return test

    def _exam(self) -> TestExam:
        exam = TestExam(
            employee_id=self.employee.id,
            test_definition_id=self.test.id,
            exam_date=date(2026, 6, 15),
            valid_until=date(2027, 6, 15),
            status=EXAM_STATUS_COMPLETED,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=self.employee.personal_number,
            employee_first_name=self.employee.first_name,
            employee_last_name=self.employee.last_name,
            employee_display_name=self.employee.display_name,
            employee_workplace_name=self.workplace.name,
            test_name=self.test.name,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_finished_at=datetime(2026, 6, 15, 9, 0),
            exam_result=WRITTEN_RESULT_PASSED,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam
