"""TESTY-14: podepsaný protokol připojený k dokončené zkoušce."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox
from sqlalchemy import delete, func, select, text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-14-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_test_exam_tables,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from core.backup import BACKUP_EXTENSION, create_instance_backup, restore_instance_backup
    from core.database.session import dispose_database_engine, get_session
    from core.models.attachment import Attachment
    from core.services.storage_service import storage_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        EXAM_PROTOCOL_ACTION_ATTACH,
        EXAM_PROTOCOL_ACTION_OPEN,
        EXAM_PROTOCOL_ACTION_REMOVE,
        EXAM_PROTOCOL_ACTION_REPLACE,
        EXAM_PROTOCOL_ATTACHED,
        EXAM_PROTOCOL_MISSING,
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
    from moduly.testy.sluzby.exam_signed_protocol_service import (
        ENTITY_TYPE,
        ExamSignedProtocolError,
        exam_signed_protocol_service,
    )
    from moduly.testy.sluzby.test_employee_service import test_employee_service
    from moduly.testy.sluzby.test_exam_service import test_exam_service
    from moduly.testy.ui.test_exam_detail_dialog import TestExamDetailDialog


def _pdf_bytes(marker: bytes) -> bytes:
    return b"%PDF-1.4\n" + marker + b"\n%%EOF\n"


def _wipe() -> None:
    protocol_dir = storage_service.attachments_dir / ENTITY_TYPE
    if protocol_dir.exists():
        shutil.rmtree(protocol_dir)
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


class SignedProtocolServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.files = Path(tempfile.mkdtemp(prefix="testy-14-src-"))
        self.workplace = settings_service.save_workplace(name="Hala protokolů")
        self.role = responsibility_role_service.create_role(name="Mistr protokolu")
        self.employee = self._employee("00100", "Jan", "Novák")
        self.other = self._employee("00200", "Eva", "Malá")
        self.test = self._definition("BOZP")
        self.exam = self._exam(self.employee, status=EXAM_STATUS_COMPLETED)
        self.other_exam = self._exam(self.other, status=EXAM_STATUS_COMPLETED)
        self.prepared = self._exam(self.employee, status=EXAM_STATUS_PREPARED)

    def tearDown(self) -> None:
        shutil.rmtree(self.files, ignore_errors=True)

    def test_attach_valid_pdf_keeps_history_and_survives_source_removal(self) -> None:
        source = self.files / "protokol.pdf"
        source.write_bytes(_pdf_bytes(b"prvni"))
        before = self._signature(self.exam.id)
        attachment_id = exam_signed_protocol_service.attach(self.exam.id, source)
        source.unlink()
        state = exam_signed_protocol_service.describe(self.exam.id)
        self.assertTrue(state.attached)
        self.assertEqual(state.attachment_id, attachment_id)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"prvni"))
        self.assertNotEqual(stored, source)
        self.assertTrue(str(stored).startswith(str(storage_service.attachments_dir)))
        self.assertEqual(self._signature(self.exam.id), before)
        self.assertEqual(self._attachment_count(self.exam.id), 1)

    def test_invalid_pdf_and_unfinished_exam_are_rejected(self) -> None:
        fake = self.files / "protokol.pdf"
        fake.write_bytes("tohle neni pdf, jen pripona".encode())
        with self.assertRaises(ExamSignedProtocolError) as invalid:
            exam_signed_protocol_service.attach(self.exam.id, fake)
        self.assertIn("platné PDF", str(invalid.exception))
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertEqual(self._attachment_count(self.exam.id), 0)

        header_only = self.files / "neuplny.pdf"
        header_only.write_bytes(b"%PDF-1.4\nbez konce")
        with self.assertRaises(ExamSignedProtocolError):
            exam_signed_protocol_service.attach(self.exam.id, header_only)

        missing = self.files / "chybi.pdf"
        with self.assertRaises(ExamSignedProtocolError) as absent:
            exam_signed_protocol_service.attach(self.exam.id, missing)
        self.assertIn("neexistuje", str(absent.exception))

        valid = self.files / "hotovo.pdf"
        valid.write_bytes(_pdf_bytes(b"nedokoncena"))
        with self.assertRaises(ExamSignedProtocolError) as unfinished:
            exam_signed_protocol_service.attach(self.prepared.id, valid)
        self.assertIn("dokončené", str(unfinished.exception))
        self.assertEqual(self._attachment_count(self.prepared.id), 0)
        self.assertFalse((storage_service.attachments_dir / ENTITY_TYPE).exists())

    def test_replace_keeps_old_file_and_failed_replace_keeps_current(self) -> None:
        first = self.files / "prvni.pdf"
        second = self.files / "druhy.pdf"
        first.write_bytes(_pdf_bytes(b"prvni"))
        second.write_bytes(_pdf_bytes(b"druhy"))
        before = self._signature(self.exam.id)
        first_id = exam_signed_protocol_service.attach(self.exam.id, first)
        first_path = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        first_bytes = first_path.read_bytes()

        with patch.object(
            exam_signed_protocol_service,
            "_link",
            side_effect=RuntimeError("databaze selhala"),
        ):
            with self.assertRaises(ExamSignedProtocolError) as failed:
                exam_signed_protocol_service.replace(self.exam.id, second)
        self.assertIn("Původní protokol zůstal dostupný", str(failed.exception))
        self.assertEqual(
            exam_signed_protocol_service.describe(self.exam.id).attachment_id,
            first_id,
        )
        self.assertEqual(first_path.read_bytes(), first_bytes)
        self.assertEqual(self._attachment_count(self.exam.id), 1)

        second_id = exam_signed_protocol_service.replace(self.exam.id, second)
        self.assertNotEqual(second_id, first_id)
        current = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertEqual(current.read_bytes(), _pdf_bytes(b"druhy"))
        self.assertEqual(first_path.read_bytes(), first_bytes)
        self.assertTrue(first_path.is_file())
        self.assertEqual(self._attachment_count(self.exam.id), 2)
        self.assertEqual(self._signature(self.exam.id), before)

    def test_detach_clears_link_and_keeps_file_and_history(self) -> None:
        source = self.files / "protokol.pdf"
        source.write_bytes(_pdf_bytes(b"odebrat"))
        before = self._signature(self.exam.id)
        exam_signed_protocol_service.attach(self.exam.id, source)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        exam_signed_protocol_service.detach(self.exam.id)
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertTrue(stored.is_file())
        self.assertEqual(stored.read_bytes(), _pdf_bytes(b"odebrat"))
        self.assertEqual(self._attachment_count(self.exam.id), 1)
        self.assertIsNone(test_exam_service.get_exam(self.exam.id).signed_protocol_attachment_id)
        self.assertEqual(self._signature(self.exam.id), before)
        with self.assertRaises(ExamSignedProtocolError) as missing:
            exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertIn("není připojen", str(missing.exception))

    def test_protocols_of_different_exams_stay_separate(self) -> None:
        left = self.files / "levy.pdf"
        right = self.files / "pravy.pdf"
        left.write_bytes(_pdf_bytes(b"levy"))
        right.write_bytes(_pdf_bytes(b"pravy"))
        exam_signed_protocol_service.attach(self.exam.id, left)
        exam_signed_protocol_service.attach(self.other_exam.id, right)
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            _pdf_bytes(b"levy"),
        )
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.other_exam.id).read_bytes(),
            _pdf_bytes(b"pravy"),
        )
        exam_signed_protocol_service.detach(self.exam.id)
        self.assertFalse(exam_signed_protocol_service.describe(self.exam.id).attached)
        self.assertTrue(exam_signed_protocol_service.describe(self.other_exam.id).attached)

    def test_missing_or_damaged_copy_is_reported(self) -> None:
        source = self.files / "protokol.pdf"
        source.write_bytes(_pdf_bytes(b"otevrit"))
        exam_signed_protocol_service.attach(self.exam.id, source)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        stored.write_bytes(b"poskozeno")
        with self.assertRaises(ExamSignedProtocolError) as damaged:
            exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertIn("poškozený", str(damaged.exception))
        self.assertTrue(exam_signed_protocol_service.describe(self.exam.id).attached)
        stored.unlink()
        with self.assertRaises(ExamSignedProtocolError) as missing:
            exam_signed_protocol_service.validated_copy_path(self.exam.id)
        self.assertIn("nebyl nalezen", str(missing.exception))

    def test_existing_database_receives_protocol_column(self) -> None:
        with get_session() as session:
            session.execute(text(
                "ALTER TABLE test_exams DROP COLUMN signed_protocol_attachment_id"
            ))
            session.commit()
        self.assertNotIn("signed_protocol_attachment_id", _table_columns("test_exams"))
        _ensure_test_exam_tables()
        self.assertIn("signed_protocol_attachment_id", _table_columns("test_exams"))
        loaded = test_exam_service.get_exam(self.exam.id)
        self.assertEqual(loaded.exam_result, WRITTEN_RESULT_PASSED)
        self.assertIsNone(loaded.signed_protocol_attachment_id)

    def test_protocol_is_in_backup_and_restore(self) -> None:
        source = self.files / "zaloha.pdf"
        source.write_bytes(_pdf_bytes(b"zaloha"))
        before = self._signature(self.exam.id)
        attachment_id = exam_signed_protocol_service.attach(self.exam.id, source)
        stored = exam_signed_protocol_service.validated_copy_path(self.exam.id)
        settings = _TMP / "protocol-settings.json"
        settings.write_text("{}", encoding="utf-8")
        package = _TMP / f"protokol{BACKUP_EXTENSION}"
        if package.exists():
            package.unlink()
        create_instance_backup(
            package,
            workspace_root=storage_service.base,
            database_path=storage_service.database_path,
            settings_path=settings,
        )
        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
            matched = [name for name in names if name.endswith(stored.name)]
            self.assertEqual(len(matched), 1)
            self.assertEqual(archive.read(matched[0]), _pdf_bytes(b"zaloha"))

        stored.write_bytes(b"zmeneno po zaloze")
        with get_session() as session:
            row = session.get(TestExam, self.exam.id)
            row.signed_protocol_attachment_id = None
            row.exam_result = "failed"
            session.commit()
        restore_instance_backup(
            package,
            workspace_root=storage_service.base,
            settings_path=settings,
        )
        dispose_database_engine()
        restored = test_exam_service.get_exam(self.exam.id)
        self.assertEqual(restored.signed_protocol_attachment_id, attachment_id)
        self.assertEqual(self._signature(self.exam.id), before)
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            _pdf_bytes(b"zaloha"),
        )

    def _signature(self, exam_id: int):
        exam = test_exam_service.get_exam(exam_id)
        return (
            exam.status,
            exam.exam_result,
            exam.valid_until,
            exam.written_finished_at,
            exam.exam_date,
        )

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

    def _employee(self, number, first, last):
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

    def _exam(self, employee, *, status: str) -> TestExam:
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=self.test.id,
            exam_date=date(2026, 6, 15),
            valid_until=date(2027, 6, 15),
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_display_name=employee.display_name,
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


class SignedProtocolDialogTests(unittest.TestCase):
    _employee = SignedProtocolServiceTests._employee
    _definition = SignedProtocolServiceTests._definition
    _exam = SignedProtocolServiceTests._exam

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        SignedProtocolServiceTests.setUp(self)

    def tearDown(self) -> None:
        SignedProtocolServiceTests.tearDown(self)

    def _signature(self, exam_id: int):
        return SignedProtocolServiceTests._signature(self, exam_id)

    def _attachment_count(self, exam_id: int) -> int:
        return SignedProtocolServiceTests._attachment_count(self, exam_id)

    def test_dialog_actions_follow_state_and_do_not_change_results(self) -> None:
        source = self.files / "dialog.pdf"
        replacement = self.files / "nahrada.pdf"
        source.write_bytes(_pdf_bytes(b"dialog"))
        replacement.write_bytes(_pdf_bytes(b"nahrada"))
        before = self._signature(self.exam.id)

        prepared = TestExamDetailDialog(exam_id=self.prepared.id)
        self.assertEqual(prepared.protocol_status.text(), EXAM_PROTOCOL_MISSING)
        self.assertFalse(prepared.protocol_attach_btn.isEnabled())
        self.assertFalse(prepared.protocol_open_btn.isEnabled())
        self.assertFalse(prepared.protocol_replace_btn.isEnabled())
        self.assertFalse(prepared.protocol_remove_btn.isEnabled())
        prepared.deleteLater()

        dialog = TestExamDetailDialog(exam_id=self.exam.id)
        self.assertEqual(dialog.protocol_box.title(), "Podepsaný protokol")
        self.assertEqual(dialog.protocol_attach_btn.text(), EXAM_PROTOCOL_ACTION_ATTACH)
        self.assertEqual(dialog.protocol_open_btn.text(), EXAM_PROTOCOL_ACTION_OPEN)
        self.assertEqual(dialog.protocol_replace_btn.text(), EXAM_PROTOCOL_ACTION_REPLACE)
        self.assertEqual(dialog.protocol_remove_btn.text(), EXAM_PROTOCOL_ACTION_REMOVE)
        self.assertTrue(dialog.protocol_attach_btn.isEnabled())
        self.assertFalse(dialog.protocol_open_btn.isEnabled())

        with patch.object(
            QFileDialog,
            "getOpenFileName",
            return_value=(str(source), "PDF (*.pdf)"),
        ):
            dialog.protocol_attach_btn.click()
        self.assertEqual(dialog.protocol_status.text(), EXAM_PROTOCOL_ATTACHED)
        self.assertFalse(dialog.protocol_attach_btn.isEnabled())
        self.assertTrue(dialog.protocol_open_btn.isEnabled())
        self.assertTrue(dialog.protocol_replace_btn.isEnabled())
        self.assertTrue(dialog.protocol_remove_btn.isEnabled())
        self.assertFalse(dialog.results_changed)

        opened: list[Path] = []

        def remember(path, **_kwargs):
            opened.append(Path(path))
            return True

        with patch(
            "moduly.testy.ui.test_exam_detail_dialog.open_local_file",
            side_effect=remember,
        ):
            dialog.protocol_open_btn.click()
        self.assertEqual(len(opened), 1)
        self.assertEqual(opened[0].read_bytes(), _pdf_bytes(b"dialog"))
        self.assertFalse(opened[0].samefile(source))

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.No,
        ):
            dialog.protocol_replace_btn.click()
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            _pdf_bytes(b"dialog"),
        )

        with (
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(
                QFileDialog,
                "getOpenFileName",
                return_value=(str(replacement), "PDF (*.pdf)"),
            ),
        ):
            dialog.protocol_replace_btn.click()
        self.assertEqual(
            exam_signed_protocol_service.validated_copy_path(self.exam.id).read_bytes(),
            _pdf_bytes(b"nahrada"),
        )

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog.protocol_remove_btn.click()
        self.assertEqual(dialog.protocol_status.text(), EXAM_PROTOCOL_MISSING)
        self.assertTrue(dialog.protocol_attach_btn.isEnabled())
        self.assertFalse(dialog.results_changed)
        self.assertEqual(self._signature(self.exam.id), before)
        self.assertEqual(self._attachment_count(self.exam.id), 2)
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
