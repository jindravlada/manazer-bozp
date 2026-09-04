"""AUDIT-PROGRAM-ODT-EXPORT-2: po exportu otevřít ODT ve výchozí aplikaci."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp(prefix="audit-program-odt-export-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    import core.services.editable_catalog_service as editable_catalog_module

    importlib.reload(editable_catalog_module)

    from moduly.audity.constants import (
        AUDIT_PROGRAM_EXPORT_PLAN_OPEN_FAILED,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_plan_export_service import (
        audit_program_plan_export_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AuditProgramOdtExportOpenTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        self._workplace = settings_service.save_workplace(name="Provoz Export 2")

    def _create_program_with_visit(self):
        program = audit_program_service.create_program(
            name="ZX-ZF",
            date_from=date(2026, 1, 1),
            date_to=date(2029, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._workplace.id,
            workplace_name=self._workplace.name,
            audit_interval_months=12,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace.id,
            planned_year=2026,
            planned_month=3,
        )
        return program

    def _create_dialog(self, program_id: int) -> AuditProgramManagerDialog:
        dialog = AuditProgramManagerDialog()
        dialog._reload_program_list(select_program_id=program_id)
        QApplication.processEvents()
        return dialog

    def test_successful_export_opens_local_file_once(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        target = Path(tempfile.mkdtemp()) / "plan.odt"

        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.QFileDialog.getSaveFileName",
            return_value=(str(target), "Dokument ODT (*.odt)"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open:
            dialog._export_plan()

        mock_open.assert_called_once()
        opened = Path(mock_open.call_args.args[0]).resolve()
        self.assertEqual(opened, target.resolve())
        self.assertTrue(opened.exists())
        with zipfile.ZipFile(opened) as zin:
            self.assertIn("content.xml", zin.namelist())
        self.assertEqual(mock_open.call_args.kwargs.get("show_error"), False)

    def test_cancel_dialog_does_not_open(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open, patch.object(
            audit_program_plan_export_service,
            "generate_for_program",
            side_effect=AssertionError("zrušený dialog nesmí exportovat"),
        ):
            dialog._export_plan()
        mock_open.assert_not_called()

    def test_export_error_does_not_open(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        target = Path(tempfile.mkdtemp()) / "plan.odt"
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.QFileDialog.getSaveFileName",
            return_value=(str(target), "Dokument ODT (*.odt)"),
        ), patch.object(
            audit_program_plan_export_service,
            "generate_for_program",
            side_effect=RuntimeError("export selhal"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.warning",
        ) as mock_warn:
            dialog._export_plan()
        mock_open.assert_not_called()
        self.assertFalse(target.exists())
        mock_warn.assert_called_once()
        self.assertIn("Plán se nepodařilo exportovat", mock_warn.call_args.args[2])

    def test_open_error_keeps_odt_and_shows_message(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        target = Path(tempfile.mkdtemp()) / "plan.odt"
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.QFileDialog.getSaveFileName",
            return_value=(str(target), "Dokument ODT (*.odt)"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            side_effect=OSError("nelze otevřít"),
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.warning",
        ) as mock_warn:
            dialog._export_plan()

        mock_open.assert_called_once()
        self.assertTrue(target.exists())
        with zipfile.ZipFile(target) as zin:
            self.assertIn("content.xml", zin.namelist())
        mock_warn.assert_called_once()
        message = mock_warn.call_args.args[2]
        self.assertIn(AUDIT_PROGRAM_EXPORT_PLAN_OPEN_FAILED, message)
        self.assertIn(str(target), message)


if __name__ == "__main__":
    unittest.main()
