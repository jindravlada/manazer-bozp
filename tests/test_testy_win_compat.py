"""RELEASE-4.1-WIN-FIX-1: modul Testy se na Windows neshodí při importu.

Linuxové O_DIRECTORY, O_NOFOLLOW a O_CLOEXEC v os na Windows nejsou.
Uložení podepsaného protokolu a čtení snímku musí odmítnout únik z příloh
i bez nich. Na Linuxu zůstávají dosavadní příznaky a popisovače adresářů.
"""

from __future__ import annotations

import importlib
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="testy-win-"))

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
    from moduly.testy.sluzby import test_exam_service as exam_module
    from moduly.testy.sluzby.exam_signed_protocol_service import (
        ENTITY_TYPE,
        ExamSignedProtocolError,
        exam_signed_protocol_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service


def _pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n" + marker + b"\n%%EOF\n"


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


class WindowsImportTests(unittest.TestCase):
    def test_service_imports_and_stores_without_unix_open_flags(self) -> None:
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        completed = subprocess.run(
            [sys.executable, "-c", _IMPORT_WITHOUT_UNIX_FLAGS],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + completed.stderr,
        )
        self.assertIn("ok", completed.stdout)

    def test_linux_flags_stay_available(self) -> None:
        self.assertTrue(protocol_module._directory_fds_available())
        self.assertTrue(exam_module._nofollow_available())
        self.assertEqual(
            protocol_module._dir_flags(),
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        self.assertEqual(
            protocol_module._readonly_flags(),
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        self.assertEqual(
            protocol_module._create_flags(),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        self.assertEqual(
            exam_module._snapshot_read_flags(),
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )


class DescriptorGuardTests(unittest.TestCase):
    def test_reparse_attribute_is_rejected_without_symlink_bit(self) -> None:
        class _Directory:
            st_mode = stat.S_IFDIR | 0o755

        class _Junction:
            st_mode = stat.S_IFDIR | 0o755
            st_file_attributes = 0x400

        self.assertFalse(protocol_module._is_reparse_point(_Directory()))
        self.assertTrue(protocol_module._is_reparse_point(_Junction()))
        self.assertTrue(exam_module._is_reparse_point(_Junction()))

    def test_descriptor_rejects_symlink_redirect_and_outside_file(self) -> None:
        root = _TMP / "kontrola-cesty"
        real = root / "real"
        real.mkdir(parents=True)
        link = root / "link"
        link.symlink_to(real, target_is_directory=True)
        target = link / "protokol.pdf"
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            self.assertFalse(
                protocol_module._descriptor_is_relative(fd, root, "link/protokol.pdf")
            )
            self.assertTrue(
                protocol_module._descriptor_is_relative(fd, root, "real/protokol.pdf")
            )
        finally:
            os.close(fd)

        outside = _TMP / "mimo-popisovac"
        outside.mkdir(exist_ok=True)
        foreign = outside / "cizi.pdf"
        foreign_fd = os.open(foreign, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            self.assertFalse(
                protocol_module._descriptor_is_relative(
                    foreign_fd,
                    root,
                    "real/protokol.pdf",
                )
            )
        finally:
            os.close(foreign_fd)

    def test_descriptor_accepts_file_under_symlinked_parent(self) -> None:
        real_parent = _TMP / "skutecny-rodic"
        real_parent.mkdir()
        linked_parent = _TMP / "odkaz-rodic"
        linked_parent.symlink_to(real_parent, target_is_directory=True)
        root = linked_parent / "prilohy"
        root.mkdir()
        target = root / "protokol.pdf"
        fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            self.assertTrue(
                protocol_module._descriptor_is_relative(fd, root, "protokol.pdf")
            )
        finally:
            os.close(fd)

    def test_snapshot_read_without_nofollow_rejects_symlink(self) -> None:
        payload = b"obrazek-win"
        real = _TMP / "snimek.bin"
        real.write_bytes(payload)
        link = _TMP / "snimek-odkaz.bin"
        link.symlink_to(real)
        with patch.object(exam_module, "_nofollow_available", return_value=False):
            with self.assertRaises(OSError):
                exam_module._read_snapshot_bytes(link)
            self.assertEqual(exam_module._read_snapshot_bytes(real), payload)
        self.assertEqual(real.read_bytes(), payload)
        with self.assertRaises(OSError):
            exam_module._read_snapshot_bytes(link)

    def test_source_open_without_nofollow_rejects_symlink(self) -> None:
        real = _TMP / "zdroj-win.pdf"
        real.write_bytes(_pdf_bytes(b"zdroj"))
        link = _TMP / "zdroj-odkaz.pdf"
        link.symlink_to(real)
        with patch.object(protocol_module, "_nofollow_available", return_value=False):
            with self.assertRaises(ExamSignedProtocolError):
                protocol_module._open_source_fd(link)
            fd = protocol_module._open_source_fd(real)
            os.close(fd)
        self.assertEqual(real.read_bytes(), _pdf_bytes(b"zdroj"))


class WindowsStyleStorageTests(unittest.TestCase):
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
        self.workplace = settings_service.save_workplace(name="Hala WIN")
        self.role = responsibility_role_service.create_role(name="Mistr WIN")
        self.employee = test_employee_service.create_employee(
            personal_number="00191",
            first_name="Jana",
            last_name="Malá",
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )
        self.test = self._definition("BOZP WIN")
        self.exam = self._exam()

    def test_linux_directory_fds_still_store_protocol(self) -> None:
        self.assertTrue(protocol_module._directory_fds_available())
        source = self._source("linux.pdf", b"linux")
        exam_signed_protocol_service.attach(self.exam.id, source)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"linux"))
        self.assertFalse(stored.is_symlink())
        self.assertTrue(
            stored.resolve().is_relative_to(storage_service.attachments_dir.resolve())
        )
        self._assert_outside_untouched()

    def test_path_backend_stores_replaces_and_keeps_bytes(self) -> None:
        first = self._source("prvni.pdf", b"prvni")
        second = self._source("druhy.pdf", b"druhy")
        with patch.object(protocol_module, "_directory_fds_available", return_value=False):
            first_id = exam_signed_protocol_service.attach(self.exam.id, first)
            stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
            self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
            self.assertFalse(stored.is_symlink())
            self.assertTrue(
                stored.resolve().is_relative_to(
                    storage_service.attachments_dir.resolve()
                )
            )
            second_id = exam_signed_protocol_service.replace(self.exam.id, second)
        self.assertNotEqual(second_id, first_id)
        current = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(current.read_bytes(), _pdf_bytes(b"druhy"))
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
        self._assert_outside_untouched()

    def test_path_backend_rejects_invalid_sources_and_symlink_directories(self) -> None:
        with patch.object(protocol_module, "_directory_fds_available", return_value=False):
            missing = self.files / "chybi.pdf"
            with self.assertRaises(ExamSignedProtocolError) as absent:
                exam_signed_protocol_service.attach(self.exam.id, missing)
            self.assertIn("neexistuje", str(absent.exception))

            directory = self.files / "adresar.pdf"
            directory.mkdir()
            with self.assertRaises(ExamSignedProtocolError) as folder:
                exam_signed_protocol_service.attach(self.exam.id, directory)
            self.assertIn("adresář", str(folder.exception))

            source = self._source("platny.pdf", b"platny")
            link = self.files / "odkaz.pdf"
            link.symlink_to(source)
            with self.assertRaises(ExamSignedProtocolError) as linked:
                exam_signed_protocol_service.attach(self.exam.id, link)
            self.assertIn("Symbolický odkaz", str(linked.exception))

            plain = self.files / "neni.pdf"
            plain.write_bytes(b"tohle neni pdf")
            with self.assertRaises(ExamSignedProtocolError) as invalid:
                exam_signed_protocol_service.attach(self.exam.id, plain)
            self.assertIn("platné PDF", str(invalid.exception))

            entity = storage_service.attachments_dir / ENTITY_TYPE
            entity.symlink_to(self.outside, target_is_directory=True)
            with self.assertRaises(ExamSignedProtocolError):
                exam_signed_protocol_service.attach(self.exam.id, source)
            self.assertTrue(entity.is_symlink())

            entity.unlink()
            exam_dir = entity / str(self.exam.id)
            exam_dir.mkdir(parents=True)
            exam_dir.rmdir()
            exam_dir.symlink_to(self.outside, target_is_directory=True)
            with self.assertRaises(ExamSignedProtocolError):
                exam_signed_protocol_service.attach(self.exam.id, source)
            self.assertTrue(exam_dir.is_symlink())

        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(self._attachment_count(), 0)
        self._assert_outside_untouched()

    def test_path_backend_does_not_replace_or_follow_file_symlink(self) -> None:
        fixed = "a1b2c3d4" * 4
        entity = storage_service.attachments_dir / ENTITY_TYPE
        exam_dir = entity / str(self.exam.id)
        exam_dir.mkdir(parents=True)
        link = exam_dir / f"protokol-{fixed}.pdf"
        link.symlink_to(self.outside / "unik.pdf")

        class _Identity:
            hex = fixed

        with patch.object(protocol_module, "_directory_fds_available", return_value=False):
            with patch.object(protocol_module.uuid, "uuid4", return_value=_Identity()):
                with self.assertRaises(ExamSignedProtocolError):
                    exam_signed_protocol_service.attach(
                        self.exam.id,
                        self._source("zdroj.pdf", b"zdroj"),
                    )
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.outside / "unik.pdf").exists())
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self._assert_outside_untouched()

    def test_path_backend_drops_file_when_database_or_write_fails(self) -> None:
        source = self._source("novy.pdf", b"novy")
        with patch.object(protocol_module, "_directory_fds_available", return_value=False):
            with patch.object(protocol_module.os, "write", side_effect=OSError(28, "plny disk")):
                with self.assertRaises(ExamSignedProtocolError):
                    exam_signed_protocol_service.attach(self.exam.id, source)
            self.assertEqual(self._protocol_pdfs(), [])
            with patch.object(
                exam_signed_protocol_service,
                "_link",
                side_effect=RuntimeError("databaze selhala"),
            ):
                with self.assertRaises(ExamSignedProtocolError):
                    exam_signed_protocol_service.attach(self.exam.id, source)
        self.assertEqual(self._protocol_pdfs(), [])
        self.assertEqual(self._attachment_count(), 0)
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self._assert_outside_untouched()

    def _assert_outside_untouched(self) -> None:
        canary = self.outside / "canary.txt"
        self.assertEqual(sorted(path.name for path in self.outside.iterdir()), ["canary.txt"])
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
                if not path.is_symlink() and path.suffix == ".pdf":
                    found.append(path)
        return found

    def _attachment_count(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(Attachment)
                    .where(
                        Attachment.entity_type == ENTITY_TYPE,
                        Attachment.entity_id == int(self.exam.id),
                    )
                )
                or 0
            )

    def _source(self, name: str, marker: bytes) -> Path:
        path = self.files / name
        path.write_bytes(_pdf_bytes(marker))
        return path

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


_IMPORT_WITHOUT_UNIX_FLAGS = r"""
import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

root = Path(tempfile.mkdtemp(prefix="testy-win-import-"))
for name in ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC"):
    if hasattr(os, name):
        delattr(os, name)

with patch.object(Path, "home", return_value=root):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    import moduly.testy.sluzby.exam_signed_protocol_service as protocol
    import moduly.testy.sluzby.test_exam_service as exams

    assert protocol._directory_fds_available() is False
    assert exams._nofollow_available() is False
    created = protocol._create_flags()
    assert created & os.O_CREAT
    assert created & os.O_EXCL
    assert created & os.O_WRONLY

    attachments = storage_module.storage_service.attachments_dir
    outside = root / "mimo"
    outside.mkdir()
    canary = outside / "canary.txt"
    canary.write_bytes(b"canary")
    source = root / "zdroj.pdf"
    source.write_bytes(b"%PDF-1.4\nwin\n%%EOF\n")
    checked = protocol._require_source_pdf(source)
    stored = protocol.ExamSignedProtocolService()._copy_into_storage(7, checked)
    try:
        protocol._assert_stored_pdf(stored)
        fd = stored.directory.open_read(stored.name)
        try:
            data = os.read(fd, 100)
        finally:
            os.close(fd)
        assert data.startswith(b"%PDF-"), data
        full = attachments / stored.relative
        assert full.is_file()
        assert not full.is_symlink()
        assert full.resolve().is_relative_to(attachments.resolve())
    finally:
        stored.close()

    entity = attachments / protocol.ENTITY_TYPE
    if entity.is_symlink():
        entity.unlink()
    elif entity.exists():
        import shutil

        shutil.rmtree(entity)
    entity.symlink_to(outside, target_is_directory=True)
    try:
        protocol.ExamSignedProtocolService()._copy_into_storage(8, checked)
    except protocol.ExamSignedProtocolError:
        pass
    else:
        raise SystemExit("symlink directory was accepted")
    assert canary.read_bytes() == b"canary"
    assert sorted(item.name for item in outside.iterdir()) == ["canary.txt"]

    try:
        protocol._require_source_pdf(root / "chybi.pdf")
    except protocol.ExamSignedProtocolError as exc:
        assert "neexistuje" in str(exc)
    else:
        raise SystemExit("missing file accepted")

    link = root / "odkaz.pdf"
    link.symlink_to(source)
    try:
        protocol._require_source_pdf(link)
    except protocol.ExamSignedProtocolError as exc:
        assert "Symbolick" in str(exc)
    else:
        raise SystemExit("symlink source accepted")

    try:
        protocol._require_source_pdf(outside)
    except protocol.ExamSignedProtocolError as exc:
        assert "adres" in str(exc)
    else:
        raise SystemExit("directory accepted")

    for bad in ("../unik.pdf", "a/b.pdf", "a\\b.pdf", "a\x00b.pdf", "", ".", ".."):
        try:
            protocol._safe_component(bad)
        except protocol.ExamSignedProtocolError:
            pass
        else:
            raise SystemExit("bad component accepted: " + bad)

    image = root / "obrazek.bin"
    image.write_bytes(b"obrazek")
    image_link = root / "obrazek-odkaz.bin"
    image_link.symlink_to(image)
    try:
        exams._read_snapshot_bytes(image_link)
    except OSError:
        pass
    else:
        raise SystemExit("snapshot symlink was read")
    assert exams._read_snapshot_bytes(image) == b"obrazek"
    assert image.read_bytes() == b"obrazek"

print("ok")
"""
