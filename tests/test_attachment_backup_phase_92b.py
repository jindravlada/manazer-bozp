import os
import stat
import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from tests.attachment_backup_test_env import (
    attachment_backup_diagnostic_service,
    attachment_service,
    session_module,
    storage_service,
)
from core.backup.constants import BACKUP_EXTENSION
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BACKUP_TYPE_INSTANCE,
    BackupRecord,
    data_management_settings_service,
)
from moduly.sprava_dat.sluzby.data_management_status_service import (
    data_management_status_service,
)
from moduly.sprava_dat.ui.summary_tab import SummaryTab


def _ensure_workspace_writable() -> None:
    db_path = storage_service.database_path
    db_dir = db_path.parent
    if db_dir.exists():
        db_dir.chmod(
            db_dir.stat().st_mode | stat.S_IWUSR | stat.S_IWGRP | stat.S_IXUSR | stat.S_IXGRP
        )
    for path in [db_path, *db_dir.glob("*")] if db_dir.exists() else [db_path]:
        if path.exists():
            path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IWGRP)
    session_module.engine.dispose()


class AttachmentBackupPhase92bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._source_temp = tempfile.TemporaryDirectory()
        self._source_dir = Path(self._source_temp.name)
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()
        self._cleanup_attachments()

    def tearDown(self) -> None:
        self._cleanup_attachments()
        self._source_temp.cleanup()

    def _cleanup_attachments(self) -> None:
        _ensure_workspace_writable()
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

    def _create_attachment(self, *, entity_type: str = "accident", entity_id: int = 7) -> object:
        source = self._source_dir / "backup-test.txt"
        source.write_text("attachment backup test", encoding="utf-8")
        attachment = attachment_service.add_file_as(
            entity_type,
            entity_id,
            str(source),
            "backup-test.txt",
        )
        self.assertIsNotNone(attachment)
        assert attachment is not None
        return attachment

    def test_summary_shows_backup_warning_status(self) -> None:
        mb_path = storage_service.backups_dir / f"warning{BACKUP_EXTENSION}"
        mb_path.parent.mkdir(parents=True, exist_ok=True)
        mb_path.write_bytes(b"placeholder")
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T12:00:00",
                path=str(mb_path),
                manifest={
                    "verified": True,
                    "backup_health": "warning",
                    "attachment_warnings": [
                        "Záloha byla vytvořena, ale 1 evidovaných příloh nebylo na disku nalezeno."
                    ],
                },
                backup_type=BACKUP_TYPE_INSTANCE,
            )
        )

        self.assertEqual(
            data_management_status_service.backup_status_text(),
            "vytvořena s upozorněním",
        )
        status, warnings = data_management_status_service.compute_status()
        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(
            any("neobsahuje všechny evidované přílohy" in item for item in warnings)
        )

        tab = SummaryTab(navigate_callback=lambda _tab: None)
        tab.refresh()
        self.assertIn("vytvořena s upozorněním", tab.backup_summary_label.text())

    def test_attachment_diagnostic_is_read_only(self) -> None:
        self._create_attachment()
        before = attachment_backup_diagnostic_service.diagnose_workspace()
        after = attachment_backup_diagnostic_service.diagnose_workspace()

        self.assertEqual(before.attachments_db_count, after.attachments_db_count)
        self.assertEqual(before.attachment_files_found, after.attachment_files_found)
        self.assertEqual(before.attachment_orphan_files, after.attachment_orphan_files)

        report = attachment_backup_diagnostic_service.format_workspace_report(after)
        self.assertIn("Evidované v DB", report)
        self.assertIn("Používané adresáře", report)


if __name__ == "__main__":
    unittest.main()
