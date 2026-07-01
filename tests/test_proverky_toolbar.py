import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.proverky.constants import (
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_TYPE_MIMORADNA,
        INSPECTION_TYPE_RADNA,
        ROCNI_ZPRAVA_TOOLTIP,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class ProverkyToolbarTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def test_toolbar_buttons_state(self) -> None:
        from moduly.proverky.ui.proverky_page import ProverkyPage

        page = ProverkyPage()

        self.assertTrue(page.plan_btn.isEnabled())
        self.assertFalse(page.report_btn.isEnabled())
        self.assertEqual(page.report_btn.toolTip(), ROCNI_ZPRAVA_TOOLTIP)
        self.assertTrue(page.new_btn.isEnabled())
        self.assertTrue(page.edit_btn.isEnabled())
        self.assertTrue(page.delete_btn.isEnabled())
        self.assertTrue(page.knowledge_editor_btn.isEnabled())

    def test_get_for_year_filters_and_sorts(self) -> None:
        workplace_a = settings_service.save_workplace(name="Hala A")
        workplace_b = settings_service.save_workplace(name="Hala B")

        bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=5,
            workplace_id=workplace_a.id,
            workplace_name=workplace_a.name,
            inspection_type=INSPECTION_TYPE_RADNA,
        )
        bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=3,
            inspection_date=date(2026, 3, 15),
            workplace_id=workplace_b.id,
            workplace_name=workplace_b.name,
            inspection_type=INSPECTION_TYPE_MIMORADNA,
            started_at=date(2026, 3, 10),
        )
        bozp_inspection_service.create_inspection(
            year=2025,
            planned_month=6,
            workplace_name="Stará hala",
        )

        results = bozp_inspection_service.get_for_year(2026)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].planned_month, 3)
        self.assertEqual(results[1].planned_month, 5)

    def test_annual_plan_dialog_shows_columns_and_data(self) -> None:
        from moduly.proverky.ui.rocni_plan_dialog import RocniPlanDialog

        workplace = settings_service.save_workplace(name="Sklad C")
        bozp_inspection_service.create_inspection(
            year=2026,
            planned_month=4,
            inspection_date=date(2026, 4, 20),
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            inspection_type=INSPECTION_TYPE_RADNA,
        )

        dialog = RocniPlanDialog(year=2026)

        self.assertEqual(
            [
                dialog.table.horizontalHeaderItem(column).text()
                for column in range(dialog.table.columnCount())
            ],
            ["Měsíc", "Pracoviště", "Datum prověrky", "Stav", "Typ prověrky"],
        )
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertEqual(dialog.table.item(0, 0).text(), "duben")
        self.assertEqual(dialog.table.item(0, 1).text(), "Sklad C")
        self.assertEqual(dialog.table.item(0, 2).text(), "20.04.2026")
        self.assertEqual(dialog.table.item(0, 3).text(), INSPECTION_STATUS_PLANOVANO)
        self.assertEqual(dialog.table.item(0, 4).text(), INSPECTION_TYPE_RADNA)

    @patch("moduly.proverky.ui.proverky_page.exec_maximized")
    def test_show_annual_plan_opens_dialog_for_selected_year(self, mock_exec) -> None:
        from moduly.proverky.ui.proverky_page import ProverkyPage

        page = ProverkyPage()
        page.show_annual_plan()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertEqual(dialog.windowTitle(), "Roční plán prověrek BOZP")
        self.assertEqual(dialog._year, date.today().year)

    def test_annual_plan_empty_year_message(self) -> None:
        from moduly.proverky.ui.rocni_plan_dialog import RocniPlanDialog

        dialog = RocniPlanDialog(year=2026)

        self.assertEqual(dialog.table.rowCount(), 0)
        self.assertIn("2026", dialog.summary_label.text())
        self.assertIn("žádné prověrky", dialog.summary_label.text())


if __name__ == "__main__":
    unittest.main()
