import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.attachment_backup_test_env import (
    BACKUP_TYPE_FULL,
    attachment_backup_diagnostic_service,
    attachment_service,
    backup_manifest_service,
    backup_service,
    session_module,
    storage_service,
)


def _ensure_workspace_writable() -> None:
    """Po obnově zálohy může být SQLite jen pro čtení – obnoví oprávnění a uzavře pool."""
    db_path = storage_service.database_path
    db_dir = db_path.parent
    if db_dir.exists():
        db_dir.chmod(
            db_dir.stat().st_mode | stat.S_IWUSR | stat.S_IWGRP | stat.S_IXUSR | stat.S_IXGRP
        )
    candidates = [db_path, *db_dir.glob("*")] if db_dir.exists() else [db_path]
    for path in candidates:
        if path.exists():
            path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IWGRP)

    import core.database.session as session_module

    session_module.engine.dispose()


class AttachmentWorkspaceDiagnosticPhase92aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._source_temp = tempfile.TemporaryDirectory()
        self._source_dir = Path(self._source_temp.name)
        self._cleanup_attachments()

    def tearDown(self) -> None:
        self._cleanup_attachments()
        self._source_temp.cleanup()

    def _ensure_db_writable(self) -> None:
        _ensure_workspace_writable()

    def _cleanup_attachments(self) -> None:
        self._ensure_db_writable()
        attachments_dir = storage_service.attachments_dir
        if attachments_dir.exists():
            import shutil

            shutil.rmtree(attachments_dir)
        storage_service.attachments_dir.mkdir(parents=True, exist_ok=True)

        from sqlalchemy import delete

        from core.models.attachment import Attachment

        try:
            with session_module.get_session() as session:
                session.execute(delete(Attachment))
                session.commit()
        except Exception:
            pass

    def test_diagnostic_reports_zero_state(self) -> None:
        diagnostic = attachment_backup_diagnostic_service.diagnose_workspace()
        self.assertEqual(diagnostic.attachments_db_count, 0)
        self.assertEqual(diagnostic.attachment_files_missing, 0)
        self.assertEqual(diagnostic.attachment_orphan_files, 0)
        self.assertEqual(diagnostic.storage_mode, "filesystem_with_db_paths")

    def test_diagnostic_detects_missing_and_orphan_files(self) -> None:
        source = self._source_dir / "existing.txt"
        source.write_text("demo", encoding="utf-8")

        attachment = attachment_service.add_file_as("task", 42, str(source), "existing.txt")
        self.assertIsNotNone(attachment)
        assert attachment is not None

        resolved = attachment_service.resolve_path(attachment)
        resolved.unlink()

        orphan = storage_service.attachment_dir("task", 99) / "orphan.txt"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("orphan", encoding="utf-8")

        diagnostic = attachment_backup_diagnostic_service.diagnose_workspace()
        self.assertEqual(diagnostic.attachments_db_count, 1)
        self.assertEqual(diagnostic.attachment_files_missing, 1)
        self.assertEqual(diagnostic.attachment_orphan_files, 1)
        self.assertGreaterEqual(len(diagnostic.directories), 1)
        self.assertTrue(
            any(item.relative_path == "prilohy" for item in diagnostic.directories)
        )


class AttachmentFullBackupPhase92aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._source_temp = tempfile.TemporaryDirectory()
        self._source_dir = Path(self._source_temp.name)
        self._cleanup_attachments()

    def tearDown(self) -> None:
        self._cleanup_attachments()
        self._source_temp.cleanup()

    def _ensure_db_writable(self) -> None:
        _ensure_workspace_writable()

    def _cleanup_attachments(self) -> None:
        self._ensure_db_writable()
        attachments_dir = storage_service.attachments_dir
        if attachments_dir.exists():
            import shutil

            shutil.rmtree(attachments_dir)
        storage_service.attachments_dir.mkdir(parents=True, exist_ok=True)

        from sqlalchemy import delete

        from core.models.attachment import Attachment

        try:
            with session_module.get_session() as session:
                session.execute(delete(Attachment))
                session.commit()
        except Exception:
            pass

    def _create_attachment(self):
        source = self._source_dir / "backup-test.txt"
        source.write_text("attachment backup test", encoding="utf-8")
        attachment = attachment_service.add_file_as("accident", 7, str(source), "backup-test.txt")
        self.assertIsNotNone(attachment)
        assert attachment is not None
        return attachment

    def test_full_backup_contains_attachment_with_relative_path(self) -> None:
        attachment = self._create_attachment()
        stored_relative = attachment.stored_path.replace("\\", "/")
        self.assertFalse(Path(stored_relative).is_absolute())

        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        zip_entry = f"prilohy/{stored_relative}"

        with zipfile.ZipFile(backup_path, "r") as zf:
            names = zf.namelist()
            self.assertIn(zip_entry, names)
            self.assertTrue(all(not name.startswith("/") for name in names))

        coverage = attachment_backup_diagnostic_service.diagnose_backup_zip(backup_path)
        self.assertTrue(coverage.zip_readable)
        self.assertTrue(coverage.zip_crc_ok)
        self.assertTrue(coverage.integrity_verified)
        self.assertGreaterEqual(coverage.attachment_files_in_zip, 1)
        self.assertIn("prilohy", coverage.version_obsah)
        self.assertTrue(coverage.manifest_reports_attachment_count)

        manifest = backup_manifest_service.build_manifest(backup_path)
        self.assertTrue(manifest.get("verified"))
        self.assertIn("attachments_db_count", manifest)
        self.assertEqual(manifest.get("backup_health"), "ok")

    def test_restore_returns_missing_attachment_file(self) -> None:
        attachment = self._create_attachment()
        resolved = attachment_service.resolve_path(attachment)
        self.assertTrue(resolved.is_file())

        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        zip_entry = f"prilohy/{attachment.stored_path.replace(chr(92), '/')}"

        resolved.unlink()
        self.assertFalse(resolved.is_file())

        backup_service.restore_backup(backup_path, restore_type=BACKUP_TYPE_FULL)
        _ensure_workspace_writable()

        self.assertTrue(resolved.is_file())
        with zipfile.ZipFile(backup_path, "r") as zf:
            self.assertEqual(
                zf.read(zip_entry).decode("utf-8"),
                "attachment backup test",
            )

        diagnostic = attachment_backup_diagnostic_service.diagnose_workspace()
        self.assertEqual(diagnostic.attachment_files_missing, 0)
        self.assertEqual(diagnostic.attachment_orphan_files, 0)

    def test_phase_summary_identifies_manifest_gap_without_breaking_backup(self) -> None:
        attachment = self._create_attachment()
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)

        summary = attachment_backup_diagnostic_service.summarize_phase_92a(backup_path=backup_path)

        self.assertTrue(summary["conclusions"]["attachments_fully_backed_up"])
        self.assertTrue(summary["conclusions"]["attachments_fully_restorable"])
        self.assertTrue(summary["backup"]["manifest_reports_attachment_count"])
        self.assertNotIn(
            "Manifest integrity neobsahuje počty příloh a fotografií.",
            summary["conclusions"]["gaps"],
        )
        self.assertGreaterEqual(len(summary["conclusions"]["covered_attachment_types"]), 3)


if __name__ == "__main__":
    unittest.main()
