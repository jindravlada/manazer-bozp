"""INSPECTION-UX-2 – tisk zpráv z hlavního seznamu prověrek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="inspection-ux-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.proverky.constants import (
        INSPECTION_DETAILED_REPORT_BUTTON_LABEL,
        INSPECTION_PROTOCOL_BUTTON_LABEL,
        INSPECTION_STATUS_DOKONCENO,
        YEAR_FILTER_VSE,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.proverky_page import ProverkyPage


class InspectionUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_page(self) -> ProverkyPage:
        page = ProverkyPage()
        page.status_filter.setCurrentText("Vše")
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        return page

    def test_toolbar_has_export_actions_disabled_without_selection(self) -> None:
        page = self._create_page()
        self.assertEqual(page.protocol_btn.text(), INSPECTION_PROTOCOL_BUTTON_LABEL)
        self.assertEqual(
            page.detailed_report_btn.text(), INSPECTION_DETAILED_REPORT_BUTTON_LABEL
        )
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())

    def test_export_actions_disabled_for_in_progress_inspection(self) -> None:
        planned = bozp_inspection_service.create_inspection()
        in_progress = bozp_inspection_service.create_inspection(
            started_at=date(2026, 3, 1)
        )
        page = self._create_page()
        by_id = {
            int(page.table.item(row, 0).text()): row
            for row in range(page.table.rowCount())
        }

        page.table.selectRow(by_id[planned.id])
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())

        page.table.selectRow(by_id[in_progress.id])
        self.assertFalse(page.protocol_btn.isEnabled())
        self.assertFalse(page.detailed_report_btn.isEnabled())

    def test_export_actions_enabled_for_completed_inspection(self) -> None:
        completed = bozp_inspection_service.create_inspection(
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )
        page = self._create_page()
        page.table.selectRow(0)

        self.assertEqual(completed.status, INSPECTION_STATUS_DOKONCENO)
        self.assertTrue(page.protocol_btn.isEnabled())
        self.assertTrue(page.detailed_report_btn.isEnabled())

    @patch(
        "moduly.proverky.ui.proverky_page.protokol_proverky_service.open_for_inspection"
    )
    def test_export_selected_protocol_from_main_list(self, mock_open) -> None:
        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )
        page = self._create_page()
        page.table.selectRow(0)

        page.export_selected_protocol()

        mock_open.assert_called_once()
        self.assertEqual(mock_open.call_args.args[0].id, inspection.id)

    @patch(
        "moduly.proverky.ui.proverky_page.protokol_proverky_service.open_detailed_report_for_inspection"
    )
    def test_export_selected_detailed_report_from_main_list(self, mock_open) -> None:
        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 20),
        )
        page = self._create_page()
        page.table.selectRow(0)

        page.export_selected_detailed_report()

        mock_open.assert_called_once()
        self.assertEqual(mock_open.call_args.args[0].id, inspection.id)

    def test_context_menu_policy_enabled(self) -> None:
        from PySide6.QtCore import Qt

        page = self._create_page()
        self.assertEqual(
            page.table.contextMenuPolicy(),
            Qt.ContextMenuPolicy.CustomContextMenu,
        )


if __name__ == "__main__":
    unittest.main()
