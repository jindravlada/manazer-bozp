import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from core.widgets.dialog_utils import exec_maximized, prepare_work_dialog_maximized
from moduly.audity.ui.audit_dialog import AuditDialog
from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog
from moduly.nastaveni.ui.thp_worker_dialog import ThpWorkerDialog
from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog


class DialogWindowUtilsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_prepare_work_dialog_maximized_sets_window_state(self) -> None:
        dialog = QDialog()
        dialog.setMinimumSize(640, 480)

        prepare_work_dialog_maximized(dialog)
        QApplication.processEvents()

        self.assertTrue(dialog.windowState() & Qt.WindowState.WindowMaximized)

    def test_exec_maximized_calls_prepare_and_exec(self) -> None:
        dialog = QDialog()
        with (
            patch(
                "core.widgets.dialog_utils.prepare_work_dialog_maximized"
            ) as mock_prepare,
            patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected) as mock_exec,
        ):
            result = exec_maximized(dialog)

        mock_prepare.assert_called_once_with(dialog)
        mock_exec.assert_called_once()
        self.assertEqual(result, QDialog.DialogCode.Rejected)

    def test_bozp_inspection_dialog_opens_via_helper(self) -> None:
        dialog = BozpInspectionDialog()
        with (
            patch.object(dialog, "showMaximized") as mock_show,
            patch.object(QDialog, "exec", return_value=0),
        ):
            exec_maximized(dialog)

        mock_show.assert_called_once()

    def test_audit_dialog_opens_via_helper(self) -> None:
        dialog = AuditDialog()
        with (
            patch.object(dialog, "showMaximized") as mock_show,
            patch.object(QDialog, "exec", return_value=0),
        ):
            exec_maximized(dialog)

        mock_show.assert_called_once()

    def test_audit_program_manager_dialog_opens_via_helper(self) -> None:
        dialog = AuditProgramManagerDialog()
        with (
            patch.object(dialog, "showMaximized") as mock_show,
            patch.object(QDialog, "exec", return_value=0),
        ):
            exec_maximized(dialog)

        mock_show.assert_called_once()

    def test_knowledge_editor_opens_via_helper(self) -> None:
        dialog = AudityKnowledgeEditorDialog()
        with (
            patch.object(dialog, "showMaximized") as mock_show,
            patch.object(QDialog, "exec", return_value=0),
        ):
            exec_maximized(dialog)

        mock_show.assert_called_once()

    def test_small_dialog_is_not_maximized_by_default(self) -> None:
        dialog = ThpWorkerDialog()
        with patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            with patch.object(dialog, "showMaximized") as mock_show:
                dialog.exec()

        mock_show.assert_not_called()


if __name__ == "__main__":
    unittest.main()
