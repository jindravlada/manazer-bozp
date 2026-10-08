"""TESTY-SEC-4: protokol PDF nesmí symlinkem opustit úložiště příloh."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="testy-sec4-"))

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
        EXAM_STATUS_PREPARED,
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


def _pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n" + marker + b"\n%%EOF\n"


def _unlink_tree(path: Path) -> None:
    """Smaže strom, ale symlink nesleduje."""
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


def _entries(root: Path) -> list[str]:
    """Názvy souborů a symlinků. Do symlinku se nesestupuje."""
    if not root.exists() or root.is_symlink():
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept: list[str] = []
        for dirname in dirnames:
            child = Path(dirpath) / dirname
            if child.is_symlink():
                found.append(str(child.relative_to(root)))
            else:
                kept.append(dirname)
        dirnames[:] = kept
        for name in filenames:
            path = Path(dirpath) / name
            found.append(str(path.relative_to(root)))
    return sorted(found)


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


class SignedProtocolStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()
        self.files = _TMP / "zdroje"
        if self.files.exists() or self.files.is_symlink():
            _unlink_tree(self.files)
        self.files.mkdir()
        self.outside = _TMP / "mimo-uloziste"
        if self.outside.is_symlink():
            self.outside.unlink()
        self.outside.mkdir(exist_ok=True)
        for child in list(self.outside.iterdir()):
            _unlink_tree(child)
        canary = self.outside / "canary.txt"
        canary.write_bytes(b"canary")
        self.canary_inode = canary.lstat().st_ino
        attachments = storage_service.attachments_dir.resolve()
        self.assertTrue(self.outside.resolve().is_relative_to(_TMP.resolve()))
        self.assertFalse(self.outside.resolve().is_relative_to(attachments))
        self.workplace = settings_service.save_workplace(name="Hala protokolů SEC4")
        self.role = responsibility_role_service.create_role(name="Mistr protokolu SEC4")
        self.employee = self._employee("00100", "Jan", "Novák")
        self.test = self._definition("BOZP")
        self.exam = self._exam(status=EXAM_STATUS_COMPLETED)
        self.prepared = self._exam(status=EXAM_STATUS_PREPARED)

    def test_attach_replace_and_detach_stay_inside_storage(self) -> None:
        first = self._source("prvni.pdf", b"prvni")
        second = self._source("druhy.pdf", b"druhy")
        first_id = exam_signed_protocol_service.attach(self.exam.id, first)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
        self.assertTrue(stored.resolve().is_relative_to(storage_service.attachments_dir.resolve()))
        self.assertFalse(stored.is_symlink())

        second_id = exam_signed_protocol_service.replace(self.exam.id, second)
        current = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertNotEqual(second_id, first_id)
        self.assertEqual(current.read_bytes(), _pdf_bytes(b"druhy"))
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
        self.assertEqual(self._attachment_count(self.exam.id), 2)
        self.assertEqual(len(self._protocol_pdfs()), 2)

        exam_signed_protocol_service.detach(self.exam.id)
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
        self.assertEqual(current.read_bytes(), _pdf_bytes(b"druhy"))
        self.assertEqual(self._attachment_count(self.exam.id), 2)
        self._assert_outside_untouched()

    def test_protocol_directory_symlink_is_not_followed(self) -> None:
        entity = storage_service.attachments_dir / ENTITY_TYPE
        entity.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(ExamSignedProtocolError):
            exam_signed_protocol_service.attach(self.exam.id, self._source("unik.pdf", b"unik"))
        self.assertTrue(entity.is_symlink())
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(self._attachment_count(self.exam.id), 0)
        self._assert_outside_untouched()

    def test_exam_directory_symlink_is_not_followed(self) -> None:
        entity = storage_service.attachments_dir / ENTITY_TYPE
        entity.mkdir()
        exam_dir = entity / str(self.exam.id)
        exam_dir.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(ExamSignedProtocolError):
            exam_signed_protocol_service.attach(self.exam.id, self._source("unik.pdf", b"unik"))
        self.assertTrue(exam_dir.is_symlink())
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(self._attachment_count(self.exam.id), 0)
        self._assert_outside_untouched()

    def test_target_file_symlink_is_not_followed_or_removed(self) -> None:
        fixed = "a1b2c3d4" * 4
        entity = storage_service.attachments_dir / ENTITY_TYPE
        exam_dir = entity / str(self.exam.id)
        exam_dir.mkdir(parents=True)
        link = exam_dir / f"protokol-{fixed}.pdf"
        link.symlink_to(self.outside / "unik.pdf")

        class _Identity:
            hex = fixed

        with patch.object(protocol_module.uuid, "uuid4", return_value=_Identity()):
            with self.assertRaises(ExamSignedProtocolError):
                exam_signed_protocol_service.attach(
                    self.exam.id, self._source("zdroj.pdf", b"zdroj")
                )
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.outside / "unik.pdf").exists())
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(self._attachment_count(self.exam.id), 0)
        self._assert_outside_untouched()

    def test_unfinished_exam_does_not_write_through_symlink(self) -> None:
        entity = storage_service.attachments_dir / ENTITY_TYPE
        entity.symlink_to(self.outside, target_is_directory=True)
        with self.assertRaises(ExamSignedProtocolError) as unfinished:
            exam_signed_protocol_service.attach(
                self.prepared.id, self._source("brzy.pdf", b"brzy")
            )
        self.assertIn("dokončené", str(unfinished.exception))
        self.assertTrue(entity.is_symlink())
        self.assertEqual(self._attachment_count(self.prepared.id), 0)
        self._assert_outside_untouched()

    def test_symlink_swap_after_directory_open_does_not_escape(self) -> None:
        swapped = {"done": False}
        real_open = os.open
        exam_name = str(self.exam.id)

        def wrapped(path, flags, mode=0o777, *, dir_fd=None):
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            if (
                not swapped["done"]
                and dir_fd is not None
                and flags & os.O_DIRECTORY
                and os.fsdecode(path) == exam_name
            ):
                swapped["done"] = True
                parent = storage_service.attachments_dir / ENTITY_TYPE
                exam_dir = parent / exam_name
                hold = parent / f"{exam_name}-odlozeno"
                os.rename(exam_dir, hold)
                os.symlink(self.outside, exam_dir, target_is_directory=True)
            return fd

        with patch.object(protocol_module.os, "open", wrapped):
            with self.assertRaises(ExamSignedProtocolError):
                exam_signed_protocol_service.attach(
                    self.exam.id, self._source("zavod.pdf", b"zavod")
                )
        self.assertTrue(swapped["done"])
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(self._attachment_count(self.exam.id), 0)
        self.assertEqual(self._protocol_pdfs(), [])
        hold = storage_service.attachments_dir / ENTITY_TYPE / f"{exam_name}-odlozeno"
        self.assertEqual(_entries(hold), [])
        self._assert_outside_untouched()

    def test_copy_failure_removes_only_the_new_file(self) -> None:
        original = self._source("prvni.pdf", b"prvni")
        exam_signed_protocol_service.attach(self.exam.id, original)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        stored_inode = stored.lstat().st_ino
        older = stored.parent / "starsi-protokol.pdf"
        older.write_bytes(_pdf_bytes(b"historie"))

        with patch.object(protocol_module.os, "write", side_effect=OSError(28, "plny disk")):
            with self.assertRaises(ExamSignedProtocolError):
                exam_signed_protocol_service.replace(
                    self.exam.id, self._source("druhy.pdf", b"druhy")
                )
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            _pdf_bytes(b"prvni"),
        )
        self.assertEqual(stored.lstat().st_ino, stored_inode)
        self.assertEqual(older.read_bytes(), _pdf_bytes(b"historie"))
        self.assertEqual(self._attachment_count(self.exam.id), 1)
        self.assertEqual(
            sorted(path.name for path in self._protocol_pdfs()),
            sorted([stored.name, older.name]),
        )
        self._assert_outside_untouched()

    def test_database_failure_keeps_original_and_drops_new_file(self) -> None:
        original = self._source("prvni.pdf", b"prvni")
        first_id = exam_signed_protocol_service.attach(self.exam.id, original)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        older = stored.parent / "starsi-protokol.pdf"
        older.write_bytes(_pdf_bytes(b"historie"))
        with patch.object(
            exam_signed_protocol_service,
            "_link",
            side_effect=RuntimeError("databaze selhala"),
        ):
            with self.assertRaises(ExamSignedProtocolError) as failed:
                exam_signed_protocol_service.replace(
                    self.exam.id, self._source("druhy.pdf", b"druhy")
                )
        self.assertIn("Původní protokol zůstal dostupný", str(failed.exception))
        self.assertEqual(
            exam_signed_protocol_service.describe(self.exam.id).attachment_id,
            first_id,
        )
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
        self.assertEqual(older.read_bytes(), _pdf_bytes(b"historie"))
        self.assertEqual(self._attachment_count(self.exam.id), 1)
        self.assertEqual(
            sorted(path.name for path in self._protocol_pdfs()),
            sorted([stored.name, older.name]),
        )
        self._assert_outside_untouched()

        other = self._exam(status=EXAM_STATUS_COMPLETED)
        with patch.object(
            exam_signed_protocol_service,
            "_link",
            side_effect=RuntimeError("databaze selhala"),
        ):
            with self.assertRaises(ExamSignedProtocolError):
                exam_signed_protocol_service.attach(
                    other.id, self._source("novy.pdf", b"novy")
                )
        self.assertEqual(self._attachment_count(other.id), 0)
        self.assertEqual(self._attachment_count(self.exam.id), 1)
        self.assertEqual(
            sorted(path.name for path in self._protocol_pdfs()),
            sorted([stored.name, older.name]),
        )

    def _assert_outside_untouched(self) -> None:
        canary = self.outside / "canary.txt"
        self.assertEqual(_entries(self.outside), ["canary.txt"])
        self.assertEqual(canary.read_bytes(), b"canary")
        self.assertEqual(canary.lstat().st_ino, self.canary_inode)

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
                if path.is_symlink() or path.suffix != ".pdf":
                    continue
                found.append(path)
        return found

    def _attachment_count(self, exam_id: int) -> int:
        with get_session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(Attachment)
                    .where(
                        Attachment.entity_type == ENTITY_TYPE,
                        Attachment.entity_id == int(exam_id),
                    )
                )
                or 0
            )

    def _source(self, name: str, marker: bytes) -> Path:
        path = self.files / name
        path.write_bytes(_pdf_bytes(marker))
        return path

    def _employee(self, number: str, first: str, last: str):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )

    def _definition(self, name: str) -> TestDefinition:
        test = TestDefinition(
            name=name,
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

    def _exam(self, *, status: str) -> TestExam:
        exam = TestExam(
            employee_id=self.employee.id,
            test_definition_id=self.test.id,
            exam_date=date(2026, 6, 15),
            valid_until=date(2027, 6, 15),
            status=status,
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
