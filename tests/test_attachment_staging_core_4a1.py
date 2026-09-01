"""ATTACHMENT-STAGING-CORE-4A1: společné odložené ukládání příloh."""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete
from sqlalchemy.orm import Session

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    import core.services.attachment_service as attachment_module

    importlib.reload(attachment_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from core.models.attachment_staging import (
        AttachmentStagingError,
        AttachmentStagingState,
        PreparedAttachmentChanges,
    )
    from core.services.attachment_service import AttachmentService, attachment_service
    from core.services.storage_service import storage_service
    from core.shared.constants import VALID_ENTITY_TYPES


def _db_count() -> int:
    conn = sqlite3.connect(str(storage_service.database_path))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM attachments").fetchone()[0])
    finally:
        conn.close()


def _write(path: Path, text: str = "obsah") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class _HomeMixin(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.service = AttachmentService()
        self.sources = Path(tempfile.mkdtemp(prefix="attach-src-"))
        self._cleanup_attachments()

    def tearDown(self) -> None:
        self._cleanup_attachments()
        shutil.rmtree(self.sources, ignore_errors=True)

    def _cleanup_attachments(self) -> None:
        attachments_dir = storage_service.attachments_dir
        if attachments_dir.exists():
            shutil.rmtree(attachments_dir)
        attachments_dir.mkdir(parents=True, exist_ok=True)
        session = get_session()
        try:
            session.execute(delete(Attachment))
            session.commit()
        finally:
            session.close()

    def _source(self, name: str, text: str = "obsah") -> Path:
        return _write(self.sources / name, text)


class AttachmentStagingStateTests(_HomeMixin):
    def test_pending_add_without_entity_id(self) -> None:
        staging = AttachmentStagingState()
        source = self._source("bez-rodice.txt")
        self.assertTrue(staging.add_pending_path(source))
        self.assertEqual(staging.pending_add_paths, [str(source)])
        self.assertFalse(staging.pending_remove_ids)
        self.assertEqual(_db_count(), 0)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*")), [])

    def test_deterministic_snapshot(self) -> None:
        staging = AttachmentStagingState()
        first = self._source("a.txt")
        second = self._source("b.txt")
        staging.add_pending_path(first)
        staging.add_pending_path(second)
        staging.mark_for_removal(4)
        staging.mark_for_removal(1)
        snap = staging.snapshot()
        self.assertEqual(
            snap,
            ((str(first), str(second)), (4, 1)),
        )
        self.assertEqual(staging.snapshot(), snap)
        staging.add_pending_path(first)
        self.assertEqual(staging.snapshot(), snap)

    def test_add_and_remove_pending_path(self) -> None:
        staging = AttachmentStagingState()
        source = self._source("pracovni.pdf")
        self.assertTrue(staging.add_pending_path(source))
        self.assertTrue(staging.has_changes())
        self.assertTrue(staging.remove_pending_path(source))
        self.assertFalse(staging.has_changes())
        self.assertEqual(staging.snapshot(), ((), ()))

    def test_duplicate_source_path_is_rejected(self) -> None:
        staging = AttachmentStagingState()
        source = self._source("dup.txt")
        self.assertTrue(staging.add_pending_path(source))
        self.assertFalse(staging.add_pending_path(source))
        self.assertFalse(staging.add_pending_path(source.resolve()))
        self.assertEqual(len(staging.pending_add_paths), 1)

    def test_mark_existing_and_unmark_restore(self) -> None:
        staging = AttachmentStagingState()
        self.assertTrue(staging.mark_for_removal(12))
        self.assertFalse(staging.mark_for_removal(12))
        self.assertTrue(staging.is_marked_for_removal(12))
        self.assertEqual(staging.visible_existing_ids([10, 12, 13]), (10, 13))
        self.assertTrue(staging.unmark_for_removal(12))
        self.assertFalse(staging.is_marked_for_removal(12))
        self.assertEqual(staging.visible_existing_ids([10, 12, 13]), (10, 12, 13))

    def test_clear_does_not_write_or_copy(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("x.bin"))
        staging.mark_for_removal(3)
        with (
            patch.object(shutil, "copy2") as copy2,
            patch.object(self.service.repository, "add") as add,
            patch.object(self.service.repository, "delete") as delete,
        ):
            staging.clear()
            copy2.assert_not_called()
            add.assert_not_called()
            delete.assert_not_called()
        self.assertEqual(_db_count(), 0)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*")), [])
        self.assertFalse(staging.has_changes())


class AttachmentStagingSessionTests(_HomeMixin):
    def test_caller_owned_session_is_not_committed(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("session.txt"))
        session = get_session()
        try:
            prepared = self.service.prepare_attachment_staging(
                "task", 11, staging, session
            )
            self.assertEqual(len(prepared.created_attachments), 1)
            ident = prepared.created_attachments[0].id
            self.assertIsNotNone(ident)
            self.assertIsNotNone(session.get(Attachment, ident))
            self.assertEqual(_db_count(), 0)
            other = get_session()
            try:
                self.assertIsNone(other.get(Attachment, ident))
            finally:
                other.close()
            session.rollback()
            self.service.rollback_attachment_changes(prepared)
        finally:
            session.close()
        self.assertEqual(_db_count(), 0)

    def test_session_rollback_drops_prepared_rows(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("rollback.txt"))
        session = get_session()
        try:
            prepared = self.service.prepare_attachment_staging(
                "task", 12, staging, session
            )
            copied = list(prepared.copied_paths)
            self.assertTrue(copied[0].is_file())
            session.rollback()
            self.service.rollback_attachment_changes(prepared)
            self.assertFalse(copied[0].exists())
        finally:
            session.close()
        self.assertEqual(_db_count(), 0)
        self.assertEqual(self.service.get_for_entity("task", 12), [])

    def test_old_api_without_session_still_commits(self) -> None:
        source = self._source("okamzite.txt")
        created = self.service.add_file("task", 13, str(source))
        self.assertIsNotNone(created)
        self.assertEqual(_db_count(), 1)
        other = get_session()
        try:
            self.assertIsNotNone(other.get(Attachment, created.id))
        finally:
            other.close()

    def test_foreign_attachment_id_is_rejected(self) -> None:
        owned = self.service.add_file("task", 20, str(self._source("vlastni.txt")))
        foreign = self.service.add_file("task", 21, str(self._source("cizi.txt")))
        staging = AttachmentStagingState()
        staging.mark_for_removal(foreign.id)
        session = get_session()
        try:
            with self.assertRaisesRegex(AttachmentStagingError, "nepatří"):
                self.service.prepare_attachment_staging("task", 20, staging, session)
            session.rollback()
        finally:
            session.close()
        self.assertEqual(_db_count(), 2)
        self.assertTrue(self.service.resolve_path(owned).is_file())
        self.assertTrue(self.service.resolve_path(foreign).is_file())


class AttachmentStagingFileTests(_HomeMixin):
    def test_one_new_file(self) -> None:
        staging = AttachmentStagingState()
        source = self._source("jeden.txt", "jedna kopie")
        staging.add_pending_path(source)
        prepared = self.service.commit_attachment_staging("task", 30, staging)
        self.assertEqual(len(prepared.created_attachments), 1)
        stored = self.service.resolve_path(prepared.created_attachments[0])
        self.assertTrue(stored.is_file())
        self.assertEqual(stored.read_text(encoding="utf-8"), "jedna kopie")
        self.assertEqual(stored.parent, storage_service.attachments_dir / "task" / "30")
        self.assertEqual(_db_count(), 1)

    def test_multiple_new_files(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("prvni.txt"))
        staging.add_pending_path(self._source("druhy.txt"))
        prepared = self.service.commit_attachment_staging("task", 31, staging)
        self.assertEqual(len(prepared.created_attachments), 2)
        self.assertEqual(_db_count(), 2)
        names = {row.filename for row in prepared.created_attachments}
        self.assertEqual(names, {"prvni.txt", "druhy.txt"})

    def test_same_names_get_unique_targets(self) -> None:
        staging = AttachmentStagingState()
        left = _write(self.sources / "a" / "stejny.txt", "A")
        right = _write(self.sources / "b" / "stejny.txt", "B")
        staging.add_pending_path(left)
        staging.add_pending_path(right)
        prepared = self.service.commit_attachment_staging("task", 32, staging)
        names = [row.filename for row in prepared.created_attachments]
        self.assertEqual(names, ["stejny.txt", "stejny_2.txt"])
        self.assertEqual(
            {self.service.resolve_path(row).read_text(encoding="utf-8") for row in prepared.created_attachments},
            {"A", "B"},
        )

    def test_long_name_is_shortened(self) -> None:
        from core.services.attachment_service import _safe_filename

        long_name = ("ž" * 300) + ".txt"
        safe = _safe_filename(long_name)
        self.assertLessEqual(len(safe), 255)
        self.assertLessEqual(len(safe.encode("utf-8")), 255)
        self.assertTrue(safe.endswith(".txt"))

        staging = AttachmentStagingState()
        staging.add_pending_path(self._source(("a" * 80) + " konec.txt", "dlouhy"))
        prepared = self.service.commit_attachment_staging("task", 33, staging)
        filename = prepared.created_attachments[0].filename
        self.assertLessEqual(len(filename), 255)
        self.assertTrue(filename.endswith(".txt"))
        stored = self.service.resolve_path(prepared.created_attachments[0])
        self.assertTrue(stored.is_file())
        self.assertEqual(stored.name, filename)

    def test_diacritics_and_spaces(self) -> None:
        staging = AttachmentStagingState()
        source = self._source("zápis kontroly 1.pdf", "pdf")
        staging.add_pending_path(source)
        prepared = self.service.commit_attachment_staging("task", 34, staging)
        self.assertEqual(prepared.created_attachments[0].filename, "zápis kontroly 1.pdf")

    def test_symlink_is_rejected(self) -> None:
        real = self._source("real.txt")
        link = self.sources / "odkaz.txt"
        link.symlink_to(real)
        staging = AttachmentStagingState()
        staging.add_pending_path(link)
        session = get_session()
        try:
            with self.assertRaisesRegex(AttachmentStagingError, "Symbolický odkaz"):
                self.service.prepare_attachment_staging("task", 35, staging, session)
            session.rollback()
        finally:
            session.close()
        self.assertEqual(_db_count(), 0)

    def test_directory_is_rejected(self) -> None:
        folder = self.sources / "slozka"
        folder.mkdir()
        staging = AttachmentStagingState()
        staging.add_pending_path(folder)
        session = get_session()
        try:
            with self.assertRaisesRegex(AttachmentStagingError, "Adresář"):
                self.service.prepare_attachment_staging("task", 36, staging, session)
            session.rollback()
        finally:
            session.close()

    def test_missing_source_is_rejected(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self.sources / "neni.txt")
        session = get_session()
        try:
            with self.assertRaisesRegex(AttachmentStagingError, "neexistuje"):
                self.service.prepare_attachment_staging("task", 37, staging, session)
            session.rollback()
        finally:
            session.close()

    def test_unreadable_source_is_rejected(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root čte i soubor s chmod 000")
        source = self._source("zamceno.txt")
        source.chmod(0o000)
        staging = AttachmentStagingState()
        staging.add_pending_path(source)
        session = get_session()
        try:
            with self.assertRaisesRegex(AttachmentStagingError, "nelze číst"):
                self.service.prepare_attachment_staging("task", 38, staging, session)
            session.rollback()
        finally:
            source.chmod(0o644)
            session.close()

    def test_dangerous_entity_type_is_rejected(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("x.txt"))
        session = get_session()
        try:
            for bad in ("../task", "task/foo", "task\\foo", "..", "."):
                with self.assertRaises(AttachmentStagingError):
                    self.service.prepare_attachment_staging(bad, 39, staging, session)
            session.rollback()
        finally:
            session.close()
        self.assertEqual(list(storage_service.attachments_dir.rglob("*")), [])

    def test_target_stays_under_prilohy(self) -> None:
        staging = AttachmentStagingState()
        nested = _write(self.sources / "vnorene" / "doklad.bin", "bin")
        staging.add_pending_path(nested)
        prepared = self.service.commit_attachment_staging("task", 40, staging)
        stored = self.service.resolve_path(prepared.created_attachments[0]).resolve()
        stored.relative_to(storage_service.attachments_dir.resolve())
        self.assertEqual(prepared.created_attachments[0].filename, "doklad.bin")
        self.assertNotIn("..", prepared.created_attachments[0].stored_path)

    def test_existing_file_is_not_overwritten(self) -> None:
        target_dir = storage_service.attachment_dir("task", 41)
        existing = target_dir / "protokol.txt"
        existing.write_text("puvodni", encoding="utf-8")
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("protokol.txt", "novy"))
        prepared = self.service.commit_attachment_staging("task", 41, staging)
        self.assertEqual(existing.read_text(encoding="utf-8"), "puvodni")
        self.assertEqual(prepared.created_attachments[0].filename, "protokol_2.txt")
        self.assertEqual(
            self.service.resolve_path(prepared.created_attachments[0]).read_text(
                encoding="utf-8"
            ),
            "novy",
        )

    def test_empty_file_is_allowed(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("prazdny.txt", ""))
        prepared = self.service.commit_attachment_staging("task", 42, staging)
        stored = self.service.resolve_path(prepared.created_attachments[0])
        self.assertTrue(stored.is_file())
        self.assertEqual(stored.stat().st_size, 0)

    def test_source_removed_between_select_and_prepare(self) -> None:
        source = self._source("zmizi.txt")
        staging = AttachmentStagingState()
        staging.add_pending_path(source)
        source.unlink()
        session = get_session()
        try:
            with self.assertRaisesRegex(AttachmentStagingError, "neexistuje"):
                self.service.prepare_attachment_staging("task", 43, staging, session)
            session.rollback()
        finally:
            session.close()
        self.assertEqual(_db_count(), 0)
        self.assertEqual(staging.pending_add_paths, [str(source)])


class AttachmentStagingCompensationTests(_HomeMixin):
    def test_second_file_failure_cleans_first_copy(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("prvni.txt"))
        staging.add_pending_path(self._source("druhy.txt"))
        real_copy = shutil.copy2
        calls = {"n": 0}

        def flaky(src, dst, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("disk full")
            return real_copy(src, dst, *args, **kwargs)

        session = get_session()
        try:
            with patch("core.services.attachment_service.shutil.copy2", flaky):
                with self.assertRaisesRegex(OSError, "disk full"):
                    self.service.prepare_attachment_staging("task", 50, staging, session)
            session.rollback()
        finally:
            session.close()
        self.assertEqual(_db_count(), 0)
        leftover = list(storage_service.attachments_dir.rglob("*.txt"))
        self.assertEqual(leftover, [])

    def test_commit_failure_after_copy_cleans_new_files(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("po-commitu.txt"))
        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            with self.assertRaisesRegex(RuntimeError, "commit fail"):
                self.service.commit_attachment_staging("task", 51, staging)
        self.assertEqual(_db_count(), 0)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*.txt")), [])

    def test_staged_remove_rollback_keeps_file_and_row(self) -> None:
        created = self.service.add_file("task", 52, str(self._source("zustane.txt")))
        path = self.service.resolve_path(created)
        staging = AttachmentStagingState()
        staging.mark_for_removal(created.id)
        session = get_session()
        try:
            prepared = self.service.prepare_attachment_staging(
                "task", 52, staging, session
            )
            self.assertTrue(path.is_file())
            self.assertIsNone(session.get(Attachment, created.id))
            session.rollback()
            self.service.rollback_attachment_changes(prepared)
        finally:
            session.close()
        self.assertTrue(path.is_file())
        self.assertEqual(_db_count(), 1)
        loaded = self.service.get_for_entity("task", 52)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].id, created.id)

    def test_staged_remove_commit_finalize_removes_row_and_file(self) -> None:
        created = self.service.add_file("task", 53, str(self._source("zmizi.txt")))
        path = self.service.resolve_path(created)
        staging = AttachmentStagingState()
        staging.mark_for_removal(created.id)
        prepared = self.service.commit_attachment_staging("task", 53, staging)
        self.assertTrue(prepared.finalized)
        self.assertFalse(path.exists())
        self.assertEqual(_db_count(), 0)
        self.assertEqual(self.service.get_for_entity("task", 53), [])

    def test_finalize_unlink_failure_keeps_commit_and_warns(self) -> None:
        created = self.service.add_file("task", 54, str(self._source("orphan.txt")))
        path = self.service.resolve_path(created)
        staging = AttachmentStagingState()
        staging.mark_for_removal(created.id)
        session = get_session()
        try:
            prepared = self.service.prepare_attachment_staging(
                "task", 54, staging, session
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        self.assertEqual(_db_count(), 0)
        self.assertTrue(path.is_file())
        with patch.object(Path, "unlink", side_effect=OSError("denied")):
            warnings = self.service.finalize_attachment_changes(prepared)
        self.assertTrue(warnings)
        self.assertIn("denied", warnings[0])
        self.assertEqual(_db_count(), 0)
        self.assertTrue(path.is_file())

        import core.services.attachment_backup_diagnostic_service as diagnostic_module

        importlib.reload(diagnostic_module)
        diagnostic = diagnostic_module.attachment_backup_diagnostic_service.diagnose_workspace()
        self.assertGreaterEqual(diagnostic.attachment_orphan_files, 1)

    def test_rollback_cleanup_is_idempotent(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("uklid.txt"))
        session = get_session()
        try:
            prepared = self.service.prepare_attachment_staging(
                "task", 55, staging, session
            )
            copied = prepared.copied_paths[0]
            self.assertTrue(copied.is_file())
            session.rollback()
            self.service.rollback_attachment_changes(prepared)
            self.assertFalse(copied.exists())
            self.service.rollback_attachment_changes(prepared)
            self.service.rollback_attachment_changes(prepared)
        finally:
            session.close()

    def test_original_error_survives_cleanup_problem(self) -> None:
        staging = AttachmentStagingState()
        staging.add_pending_path(self._source("puvodni.txt"))
        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            with patch.object(
                self.service,
                "rollback_attachment_changes",
                side_effect=OSError("cleanup"),
            ):
                with self.assertRaisesRegex(RuntimeError, "commit fail") as ctx:
                    self.service.commit_attachment_staging("task", 56, staging)
        self.assertNotIn("cleanup", str(ctx.exception))

    def test_old_delete_does_not_unlink_file(self) -> None:
        created = self.service.add_file("task", 57, str(self._source("stary-delete.txt")))
        path = self.service.resolve_path(created)
        self.assertTrue(self.service.delete(created.id))
        self.assertEqual(_db_count(), 0)
        self.assertTrue(path.is_file())


class AttachmentStagingRegressionGuardTests(_HomeMixin):
    def test_public_api_and_old_delete_source(self) -> None:
        self.assertTrue(callable(self.service.prepare_attachment_staging))
        self.assertTrue(callable(self.service.finalize_attachment_changes))
        self.assertTrue(callable(self.service.rollback_attachment_changes))
        self.assertTrue(callable(self.service.commit_attachment_staging))
        delete_src = inspect.getsource(AttachmentService.delete)
        self.assertNotIn("unlink", delete_src)
        self.assertNotIn("prepare_attachment_staging", delete_src)
        widget_src = inspect.getsource(
            importlib.import_module("core.widgets.attachment_widget").AttachmentWidget
        )
        self.assertIn("attachment_service.add_file", widget_src)
        self.assertIn("attachment_service.delete", widget_src)
        self.assertNotIn("prepare_attachment_staging", widget_src)

    def test_state_supervision_editor_has_no_attachment_ui(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
            StateSupervisionEditorDialog,
        )

        editor = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor.count("self.tabs.addTab("), 5)
        self.assertNotIn("prepare_attachment_staging", editor)
        self.assertNotIn("AttachmentWidget", editor)

    def test_external_audits_keep_own_staging(self) -> None:
        from moduly.externi_audity.sluzby import external_audit_draft
        from moduly.externi_audity.sluzby.external_audit_service import (
            ExternalAuditService,
        )

        self.assertIsNot(external_audit_draft.AttachmentStagingState, AttachmentStagingState)
        flush = inspect.getsource(ExternalAuditService.flush_attachment_staging)
        self.assertIn("attachment_service.delete", flush)
        self.assertIn("attachment_service.add_file", flush)
        self.assertNotIn("prepare_attachment_staging", flush)
        save = inspect.getsource(ExternalAuditService.save_bundle)
        self.assertNotIn("prepare_attachment_staging", save)

    def test_valid_entity_types_unchanged_for_attachments(self) -> None:
        self.assertNotIn("attachment", VALID_ENTITY_TYPES)
        self.assertNotIn("priloha", VALID_ENTITY_TYPES)

    def test_prepared_changes_dataclass(self) -> None:
        prepared = PreparedAttachmentChanges(entity_type="task", entity_id=1)
        self.assertEqual(prepared.copied_paths, [])
        self.assertEqual(prepared.pending_unlink_paths, [])
        self.assertFalse(prepared.finalized)
        self.assertFalse(prepared.rolled_back)


if __name__ == "__main__":
    unittest.main()
