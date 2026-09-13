"""AUDIT-PROGRAM-ODT-PREVIEW-3: plán otevřít z dočasného ODT bez dialogu uložení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFileDialog

_TMP = Path(tempfile.mkdtemp(prefix="audit-program-odt-preview-3-"))
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

    from core.services.storage_service import storage_service
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


REPO_EXPORT = Path(__file__).resolve().parents[1] / "export"


class AuditProgramOdtPreview3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        self._workplace = settings_service.save_workplace(name="Provoz Preview 3")

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
            planned_month=9,
        )
        return program

    def _create_dialog(self, program_id: int) -> AuditProgramManagerDialog:
        dialog = AuditProgramManagerDialog()
        dialog._reload_program_list(select_program_id=program_id)
        QApplication.processEvents()
        return dialog

    def _export_snapshot(self) -> set[str]:
        paths: set[str] = set()
        exports = storage_service.exports_dir
        if exports.exists():
            paths.update(str(path.resolve()) for path in exports.glob("*.odt"))
        if REPO_EXPORT.exists():
            paths.update(str(path.resolve()) for path in REPO_EXPORT.glob("*.odt"))
        return paths

    def test_preview_skips_file_dialog_writes_temp_odt_and_opens_once(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        before_export = self._export_snapshot()
        temp_dir = Path(tempfile.gettempdir()).resolve()

        with patch.object(
            QFileDialog,
            "getSaveFileName",
            side_effect=AssertionError("QFileDialog se nesmí zobrazit"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open:
            dialog._export_plan()

        mock_open.assert_called_once()
        opened = Path(mock_open.call_args.args[0]).resolve()
        self.assertTrue(opened.exists())
        self.assertEqual(opened.parent, temp_dir)
        self.assertIn("Plan_internich_auditu_", opened.name)
        self.assertTrue(opened.name.startswith("manazer-bozp-"))
        self.assertTrue(opened.suffix.lower() == ".odt")
        with zipfile.ZipFile(opened) as zin:
            self.assertIn("content.xml", zin.namelist())
            self.assertEqual(
                zin.read("mimetype").decode("ascii"),
                "application/vnd.oasis.opendocument.text",
            )
        self.assertTrue(opened.exists())
        self.assertEqual(self._export_snapshot(), before_export)
        self.assertNotIn(str(opened), before_export)

    def test_export_error_does_not_open(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        with patch.object(
            audit_program_plan_export_service,
            "generate_preview_for_program",
            side_effect=RuntimeError("export selhal"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.warning",
        ):
            dialog._export_plan()
        mock_open.assert_not_called()

    def test_open_error_keeps_temp_file_and_shows_path(self) -> None:
        program = self._create_program_with_visit()
        dialog = self._create_dialog(program.id)
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=False,
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.warning",
        ) as mock_warn:
            dialog._export_plan()

        mock_open.assert_called_once()
        opened = Path(mock_open.call_args.args[0])
        self.assertTrue(opened.exists())
        message = mock_warn.call_args.args[2]
        self.assertIn(AUDIT_PROGRAM_EXPORT_PLAN_OPEN_FAILED, message)
        self.assertIn(str(opened), message)


if __name__ == "__main__":
    unittest.main()
