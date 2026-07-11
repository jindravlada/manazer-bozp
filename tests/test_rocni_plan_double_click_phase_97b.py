"""Fáze 97b – dvojklik v Plánu kontrol (Roční plán) otevře prověrku."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_STATUS_PROBIHA,
        INSPECTION_TYPE_RADNA,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.rocni_plan_dialog import RocniPlanDialog


class RocniPlanDoubleClickPhase97bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_plan_with_two_rows(self) -> tuple[RocniPlanDialog, int, int]:
        workplace_a = settings_service.save_workplace(name="Hala A")
        workplace_b = settings_service.save_workplace(name="Hala B")
        first = bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=3,
            workplace_id=workplace_a.id,
            workplace_name=workplace_a.name,
            inspection_type=INSPECTION_TYPE_RADNA,
        )
        second = bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=5,
            workplace_id=workplace_b.id,
            workplace_name=workplace_b.name,
            inspection_type=INSPECTION_TYPE_RADNA,
        )
        dialog = RocniPlanDialog(year=2026)
        self.assertEqual(dialog.table.rowCount(), 2)
        return dialog, first.id, second.id

    def test_open_button_exists_and_shares_method(self) -> None:
        dialog = RocniPlanDialog(year=2026)
        self.assertEqual(dialog.open_btn.text(), "Otevřít")
        self.assertTrue(callable(dialog.open_selected_inspection))
        self.assertTrue(callable(dialog._on_row_double_clicked))
        # Dvojklik i tlačítko sdílejí open_selected_inspection.
        with patch.object(dialog, "open_selected_inspection") as mock_shared:
            dialog.open_btn.click()
            mock_shared.assert_called()
            mock_shared.reset_mock()
            dialog._on_row_double_clicked(dialog.table.model().index(0, 0))
            # Prázdná tabulka → dvojklik nic nevolá.
            mock_shared.assert_not_called()

    def test_double_click_opens_correct_inspection(self) -> None:
        dialog, first_id, second_id = self._create_plan_with_two_rows()
        # Řádky jsou seřazené podle měsíce: březen (first), květen (second).
        with patch.object(dialog, "open_inspection") as mock_open:
            index = dialog.table.model().index(0, 1)
            dialog._on_row_double_clicked(index)
            mock_open.assert_called_once_with(first_id)

        with patch.object(dialog, "open_inspection") as mock_open:
            index = dialog.table.model().index(1, 2)
            dialog._on_row_double_clicked(index)
            mock_open.assert_called_once_with(second_id)

    def test_double_click_uses_clicked_row_not_previous_selection(self) -> None:
        dialog, first_id, second_id = self._create_plan_with_two_rows()
        dialog.table.selectRow(0)
        self.assertEqual(dialog._selected_inspection_id(), first_id)

        with patch.object(dialog, "open_inspection") as mock_open:
            index = dialog.table.model().index(1, 0)
            dialog._on_row_double_clicked(index)
            mock_open.assert_called_once_with(second_id)
            self.assertEqual(dialog._selected_inspection_id(), second_id)

    def test_open_button_uses_same_open_selected_inspection(self) -> None:
        dialog, first_id, _second_id = self._create_plan_with_two_rows()
        dialog.table.selectRow(0)

        with patch.object(dialog, "open_inspection") as mock_open:
            dialog.open_btn.click()
            mock_open.assert_called_once_with(first_id)

        with patch.object(dialog, "open_selected_inspection") as mock_shared:
            index = dialog.table.model().index(0, 0)
            dialog._on_row_double_clicked(index)
            mock_shared.assert_called_once_with()

    def test_double_click_outside_row_does_nothing(self) -> None:
        dialog, _first_id, _second_id = self._create_plan_with_two_rows()
        with patch.object(dialog, "open_inspection") as mock_open:
            dialog._on_row_double_clicked(QModelIndex())
            mock_open.assert_not_called()

        with patch.object(dialog, "open_selected_inspection") as mock_shared:
            dialog._on_row_double_clicked(QModelIndex())
            mock_shared.assert_not_called()

    @patch("moduly.proverky.ui.rocni_plan_dialog.exec_maximized", return_value=True)
    def test_table_refreshes_after_editor_closes(self, _mock_exec) -> None:
        workplace = settings_service.save_workplace(name="Původní provoz")
        inspection = bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=4,
            inspection_date=date(2026, 4, 10),
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            inspection_type=INSPECTION_TYPE_RADNA,
        )
        dialog = RocniPlanDialog(year=2026)
        self.assertEqual(dialog.table.item(0, 1).text(), "Původní provoz")
        self.assertEqual(dialog.table.item(0, 3).text(), INSPECTION_STATUS_PLANOVANO)

        updated_workplace = settings_service.save_workplace(name="Nový provoz")
        fake_dialog = MagicMock()
        fake_dialog.get_data.return_value = {
            "year": 2026,
            "planned_month": 4,
            "inspection_date": date(2026, 4, 22),
            "started_at": date(2026, 4, 20),
            "finished_at": None,
            "inspection_type": INSPECTION_TYPE_RADNA,
            "workplace_id": updated_workplace.id,
            "workplace_name": updated_workplace.name,
            "title": "",
            "silne_stranky": "",
            "doporuceni_vedouciho": "",
            "commission_members": [],
        }

        with patch(
            "moduly.proverky.ui.rocni_plan_dialog.BozpInspectionDialog",
            return_value=fake_dialog,
        ), patch(
            "moduly.proverky.ui.rocni_plan_dialog.bozp_inspection_commission_service.save_members"
        ):
            dialog.open_inspection(inspection.id)

        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.workplace_name, "Nový provoz")
        self.assertEqual(reloaded.inspection_date, date(2026, 4, 22))
        self.assertEqual(reloaded.status, INSPECTION_STATUS_PROBIHA)

        self.assertEqual(dialog.table.item(0, 1).text(), "Nový provoz")
        self.assertEqual(dialog.table.item(0, 2).text(), "22.04.2026")
        self.assertEqual(dialog.table.item(0, 3).text(), INSPECTION_STATUS_PROBIHA)


if __name__ == "__main__":
    unittest.main()
