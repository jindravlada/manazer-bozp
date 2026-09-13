import stat
import tempfile
import unittest
from pathlib import Path

from tests.attachment_backup_test_env import (
    attachment_backup_diagnostic_service,
    attachment_service,
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


if __name__ == "__main__":
    unittest.main()
