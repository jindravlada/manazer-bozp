import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication, QDialog, QPushButton

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.backup_service import BACKUP_TYPE_FULL, backup_service
    from moduly.dashboard.ui.complete_backup_dialog import (
        ACTION_GO_TO_SPRAVA_DAT,
        ACTION_PROCEED,
        BACKUP_DIALOG_TEXT,
        BACKUP_DIALOG_TITLE,
        RESTORE_DIALOG_TEXT,
        RESTORE_DIALOG_TITLE,
        CompleteBackupConfirmDialog,
        CompleteRestoreConfirmDialog,
    )
    from moduly.dashboard.ui.dashboard_page import DashboardPage
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        BackupRecord,
        data_management_settings_service,
    )
    from moduly.sprava_dat.ui.sprava_dat_page import SpravaDatPage
    from moduly.sprava_dat.ui.tab_constants import TAB_BACKUP


class DashboardBackupRestorePhase88TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        settings_path = data_management_settings_service.settings_path()
        if settings_path.exists():
            settings_path.unlink()

        self.open_sprava_dat = MagicMock()
        self.refresh_sprava_dat = MagicMock()
        self.dashboard = DashboardPage(
            open_sprava_dat_callback=self.open_sprava_dat,
            refresh_sprava_dat_callback=self.refresh_sprava_dat,
        )

    def _dialog_buttons(self, dialog) -> dict[str, QPushButton]:
        return {button.text(): button for button in dialog.findChildren(QPushButton)}

    def test_backup_button_has_no_dropdown_menu(self) -> None:
        backup_buttons = [
            button
            for button in self.dashboard.findChildren(QPushButton)
            if button.text() == "💾 Záloha"
        ]
        self.assertEqual(len(backup_buttons), 1)
        self.assertIsNone(backup_buttons[0].menu())

    def test_restore_button_has_no_dropdown_menu(self) -> None:
        restore_buttons = [
            button
            for button in self.dashboard.findChildren(QPushButton)
            if button.text() == "♻ Obnova"
        ]
        self.assertEqual(len(restore_buttons), 1)
        self.assertIsNone(restore_buttons[0].menu())

    def test_backup_dialog_has_three_choices(self) -> None:
        dialog = CompleteBackupConfirmDialog()
        buttons = self._dialog_buttons(dialog)
        message = dialog.layout().itemAt(0).widget()

        self.assertEqual(dialog.windowTitle(), BACKUP_DIALOG_TITLE)
        self.assertEqual(message.text(), BACKUP_DIALOG_TEXT)
        self.assertIn("*.mbbackup", message.text())
        self.assertIn("Vytvořit zálohu", buttons)
        self.assertIn("Přejít na Správu dat", buttons)
        self.assertIn("Zrušit", buttons)

    def test_restore_dialog_mentions_mbbackup(self) -> None:
        dialog = CompleteRestoreConfirmDialog()
        message = dialog.layout().itemAt(0).widget()
        buttons = self._dialog_buttons(dialog)

        self.assertEqual(dialog.windowTitle(), RESTORE_DIALOG_TITLE)
        self.assertIn("*.mbbackup", message.text())
        self.assertEqual(message.text(), RESTORE_DIALOG_TEXT)
        self.assertIn("Obnovit ze zálohy", buttons)

    def test_cancel_does_not_run_backup(self) -> None:
        with patch(
            "moduly.dashboard.ui.dashboard_page.CompleteBackupConfirmDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_cls.return_value = mock_dialog

            with patch(
                "moduly.dashboard.ui.dashboard_page.instance_backup_workflow_service.create_instance_backup_ui"
            ) as mock_create:
                self.dashboard._show_backup_dialog()

        mock_create.assert_not_called()
        self.refresh_sprava_dat.assert_not_called()

    def test_proceed_backup_uses_shared_workflow_service(self) -> None:
        with patch(
            "moduly.dashboard.ui.dashboard_page.CompleteBackupConfirmDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.action = ACTION_PROCEED
            mock_dialog_cls.return_value = mock_dialog

            with patch(
                "moduly.dashboard.ui.dashboard_page.instance_backup_workflow_service.create_instance_backup_ui",
                return_value=True,
            ) as mock_create:
                self.dashboard._show_backup_dialog()

        mock_create.assert_called_once_with(self.dashboard)
        self.refresh_sprava_dat.assert_called_once()

    def test_go_to_sprava_dat_from_backup_opens_backup_tab(self) -> None:
        with patch(
            "moduly.dashboard.ui.dashboard_page.CompleteBackupConfirmDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.action = ACTION_GO_TO_SPRAVA_DAT
            mock_dialog_cls.return_value = mock_dialog

            with patch(
                "moduly.dashboard.ui.dashboard_page.instance_backup_workflow_service.create_instance_backup_ui"
            ) as mock_create:
                self.dashboard._show_backup_dialog()

        mock_create.assert_not_called()
        self.open_sprava_dat.assert_called_once_with(TAB_BACKUP)

    def test_proceed_restore_uses_shared_workflow_service(self) -> None:
        with patch(
            "moduly.dashboard.ui.dashboard_page.CompleteRestoreConfirmDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.action = ACTION_PROCEED
            mock_dialog_cls.return_value = mock_dialog

            with patch(
                "moduly.dashboard.ui.dashboard_page.instance_backup_workflow_service.restore_instance_backup_ui",
                return_value=True,
            ) as mock_restore:
                self.dashboard._show_restore_dialog()

        mock_restore.assert_called_once_with(self.dashboard)
        self.refresh_sprava_dat.assert_called_once()

    def test_cancel_does_not_run_restore(self) -> None:
        with patch(
            "moduly.dashboard.ui.dashboard_page.CompleteRestoreConfirmDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Rejected
            mock_dialog_cls.return_value = mock_dialog

            with patch(
                "moduly.dashboard.ui.dashboard_page.instance_backup_workflow_service.restore_instance_backup_ui"
            ) as mock_restore:
                self.dashboard._show_restore_dialog()

        mock_restore.assert_not_called()
        self.refresh_sprava_dat.assert_not_called()

    def test_dashboard_backup_calls_mbbackup_workflow(self) -> None:
        sprava_page = SpravaDatPage()

        with patch(
            "moduly.dashboard.ui.dashboard_page.CompleteBackupConfirmDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
            mock_dialog.action = ACTION_PROCEED
            mock_dialog_cls.return_value = mock_dialog

            with patch(
                "moduly.dashboard.ui.dashboard_page.instance_backup_workflow_service.create_instance_backup_ui",
                return_value=True,
            ) as mock_create:
                dashboard = DashboardPage(
                    refresh_sprava_dat_callback=sprava_page.refresh_backup_status
                )
                dashboard._show_backup_dialog()

        mock_create.assert_called_once()
        self.assertTrue(hasattr(sprava_page.backup_tab, "create_mbbackup_button"))

    def test_workflow_service_persists_backup_record(self) -> None:
        from moduly.sprava_dat.sluzby.full_backup_workflow_service import full_backup_workflow_service

        target = storage_module.storage_service.backups_dir / "workflow-shared.zip"
        widget = DashboardPage()

        with patch(
            "moduly.sprava_dat.sluzby.full_backup_workflow_service.QFileDialog.getSaveFileName",
            return_value=(str(target), ""),
        ):
            with patch("moduly.sprava_dat.sluzby.full_backup_workflow_service.QMessageBox.information"):
                self.assertTrue(full_backup_workflow_service.create_full_backup(widget))

        record = data_management_settings_service.get_last_backup()
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.backup_type, BACKUP_TYPE_FULL)
        self.assertTrue(record.manifest.get("verified"))


if __name__ == "__main__":
    unittest.main()
