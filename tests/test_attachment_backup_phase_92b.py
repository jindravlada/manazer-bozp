import importlib
import json
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from PySide6.QtWidgets import QApplication

from tests.attachment_backup_test_env import (
    BACKUP_TYPE_FULL,
    attachment_backup_diagnostic_service,
    attachment_service,
    backup_manifest_service,
    backup_service,
    control_result_photo_service,
    session_module,
    storage_service,
)
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BackupRecord,
    data_management_settings_service,
)
from moduly.sprava_dat.sluzby.data_management_status_service import (
    data_management_status_service,
)
from moduly.sprava_dat.ui.manifest_presenter import (
    STATUS_OK,
    STATUS_WARNING,
    rows_from_backup_manifest,
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

        control_results_dir = storage_service.base / "control_results"
        if control_results_dir.exists():
            import shutil

            shutil.rmtree(control_results_dir)
        control_results_dir.mkdir(parents=True, exist_ok=True)

        from sqlalchemy import delete

        from core.models.attachment import Attachment
        from core.shared.modely.control_result import ControlResult

        try:
            with session_module.get_session() as session:
                session.execute(delete(Attachment))
                session.execute(delete(ControlResult))
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

    def test_complete_attachments_backup_health_ok(self) -> None:
        self._create_attachment()
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)

        self.assertTrue(manifest["verified"])
        self.assertEqual(manifest["backup_health"], "ok")
        self.assertEqual(manifest["attachment_files_missing"], 0)
        self.assertEqual(manifest["attachments_complete"], True)

        labels = {row[0]: row[2] for row in rows_from_backup_manifest(manifest)}
        self.assertEqual(labels["Ověření zálohy"], STATUS_OK)

    def test_missing_attachment_marks_backup_with_warning(self) -> None:
        attachment = self._create_attachment()
        resolved = attachment_service.resolve_path(attachment)
        resolved.unlink()

        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)

        self.assertTrue(manifest["verified"])
        self.assertEqual(manifest["backup_health"], "warning")
        self.assertEqual(manifest["attachment_files_missing"], 1)
        self.assertTrue(manifest["attachment_warnings"])
        self.assertIn("evidovaných příloh", manifest["attachment_warnings"][0])

        labels = {row[0]: row[2] for row in rows_from_backup_manifest(manifest)}
        self.assertEqual(labels["Ověření zálohy"], STATUS_WARNING)
        self.assertNotEqual(labels["Ověření zálohy"], STATUS_OK)

    def test_missing_control_result_photo_marks_warning(self) -> None:
        relative_photo = control_result_photo_service.relative_photo_path(
            "audit",
            1,
            area_id="area1",
            section_id="section1",
            control_point_id="cp1",
        )
        photo_path = control_result_photo_service.absolute_photo_path(relative_photo)
        photo_path.parent.mkdir(parents=True, exist_ok=True)
        photo_path.write_bytes(b"demo")

        from core.database.session import get_session
        from core.shared.constants import CONTROL_RESULT_VYHOVUJE
        from core.shared.modely.control_result import ControlResult

        with get_session() as session:
            session.add(
                ControlResult(
                    entity_type="audit",
                    entity_id=1,
                    source_area_id="area1",
                    source_area_label="Oblast 1",
                    source_section_id="section1",
                    source_section_label="Sekce 1",
                    source_control_point_id="cp1",
                    source_control_point_label="KB 1",
                    result=CONTROL_RESULT_VYHOVUJE,
                    photo_path=relative_photo,
                )
            )
            session.commit()

        photo_path.unlink()

        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)

        self.assertTrue(manifest["verified"])
        self.assertEqual(manifest["backup_health"], "warning")
        self.assertEqual(manifest["control_result_photos_missing"], 1)
        self.assertTrue(any("fotografií kontrolních bodů" in item for item in manifest["attachment_warnings"]))

    def test_orphan_file_is_backed_up_and_reported_as_warning_only(self) -> None:
        orphan = storage_service.attachment_dir("task", 99) / "orphan.txt"
        orphan.write_text("orphan", encoding="utf-8")
        self.assertTrue(orphan.is_file())

        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)

        zip_entry = "prilohy/task/99/orphan.txt"
        with zipfile.ZipFile(backup_path, "r") as zf:
            self.assertIn(zip_entry, zf.namelist())

        self.assertEqual(manifest["backup_health"], "ok")
        self.assertEqual(manifest["attachment_orphan_files"], 1)
        self.assertTrue(any("bez odpovídajícího DB záznamu" in item for item in manifest["attachment_warnings"]))

        labels = {row[0]: row[2] for row in rows_from_backup_manifest(manifest)}
        self.assertEqual(labels["Ověření zálohy"], STATUS_OK)
        self.assertEqual(labels["Soubory příloh bez DB záznamu"], "Upozornění")

    def test_manifest_overview_contains_attachment_counts(self) -> None:
        self._create_attachment()
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)
        row_labels = [row[0] for row in rows_from_backup_manifest(manifest)]

        for expected in (
            "Přílohy evidované v DB",
            "Přílohy nalezené",
            "Chybějící přílohy",
            "Soubory příloh bez DB záznamu",
            "Fotografie kontrolních bodů evidované",
            "Fotografie nalezené",
            "Chybějící fotografie",
            "Referenční fotografie metodik",
            "Generované exporty",
            "Adresář control_results",
        ):
            self.assertIn(expected, row_labels)

    def test_version_json_contains_control_results(self) -> None:
        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        with zipfile.ZipFile(backup_path, "r") as zf:
            version_info = json.loads(zf.read(backup_service.VERSION_FILE).decode("utf-8"))

        self.assertIn("control_results", version_info["obsah"])

    def test_summary_shows_backup_warning_status(self) -> None:
        attachment = self._create_attachment()
        resolved = attachment_service.resolve_path(attachment)
        resolved.unlink()

        backup_path = backup_service.create_backup(backup_type=BACKUP_TYPE_FULL)
        manifest = backup_manifest_service.build_manifest(backup_path)
        data_management_settings_service.save_last_backup(
            BackupRecord(
                created_at="2026-07-10T12:00:00",
                path=str(backup_path),
                manifest=manifest,
                backup_type=BACKUP_TYPE_FULL,
            )
        )

        self.assertEqual(data_management_status_service.backup_status_text(), "vytvořena s upozorněním")
        status, warnings = data_management_status_service.compute_status()
        self.assertEqual(status, "Vyžaduje pozornost")
        self.assertTrue(any("neobsahuje všechny evidované přílohy" in item for item in warnings))

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
