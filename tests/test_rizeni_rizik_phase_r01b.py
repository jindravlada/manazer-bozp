"""Fáze R01b – editor identifikace nebezpečí."""

from __future__ import annotations

import importlib
import os
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

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS,
        HAZARD_IDENTIFICATION_TABS,
        TAB_BASICS,
        TAB_INVENTORY,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        HazardIdentificationError,
        hazard_identification_service,
    )


class RizeniRizikEditorPhaseR01bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation_a = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.operation_b = settings_service.save_workplace(
            name="Provoz B",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace_a1 = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation_a.id,
        )
        self.workplace_a2 = settings_service.save_workplace(
            name="Remíza",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation_a.id,
        )
        self.workplace_b1 = settings_service.save_workplace(
            name="Sklad",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation_b.id,
        )
        self.part_a1 = settings_service.save_workplace(
            name="Výhybkové zhlaví",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace_a1.id,
        )
        self.person = person_service.create_person(first_name="Jan", last_name="Novák")

    def _create_sample(self):
        return hazard_identification_service.create_identification(
            operation_id=self.operation_a.id,
            workplace_id=self.workplace_a1.id,
            workplace_part_id=self.part_a1.id,
            responsible_person_id=self.person.id,
            started_at=date(2026, 3, 15),
            status=HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS,
            note="Poznámka",
        )

    def test_create_identification_via_service(self) -> None:
        created = self._create_sample()
        self.assertRegex(created.identification_number, r"^\d{4}-\d{4}$")
        self.assertEqual(created.operation_id, self.operation_a.id)
        self.assertEqual(created.workplace_id, self.workplace_a1.id)
        self.assertEqual(created.workplace_part_id, self.part_a1.id)
        self.assertEqual(created.responsible_person_name, "Jan Novák")
        self.assertTrue(created.active)

    def test_update_identification(self) -> None:
        created = self._create_sample()
        updated = hazard_identification_service.update_identification(
            created.id,
            operation_id=self.operation_a.id,
            workplace_id=self.workplace_a2.id,
            workplace_part_id=None,
            note="Nová poznámka",
        )
        assert updated is not None
        self.assertEqual(updated.identification_number, created.identification_number)
        self.assertEqual(updated.workplace_id, self.workplace_a2.id)
        self.assertIsNone(updated.workplace_part_id)
        self.assertEqual(updated.note, "Nová poznámka")

    def test_load_identification_into_dialog(self) -> None:
        from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog

        created = self._create_sample()
        dialog = HazardIdentificationDialog(identification=created)

        self.assertEqual(
            dialog.basics_widget.identification_number_label.text(),
            created.identification_number,
        )
        self.assertEqual(dialog.basics_widget.operation.currentData(), self.operation_a.id)
        self.assertEqual(dialog.basics_widget.workplace.currentData(), self.workplace_a1.id)
        self.assertEqual(dialog.basics_widget.workplace_part.currentData(), self.part_a1.id)
        self.assertEqual(
            dialog.basics_widget.get_data()["responsible_person_id"],
            created.responsible_person_id,
        )
        self.assertEqual(dialog.basics_widget.started_at.get_date(), date(2026, 3, 15))
        self.assertEqual(dialog.basics_widget.note.toPlainText(), "Poznámka")

    def test_dialog_has_disabled_future_tabs(self) -> None:
        from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog

        dialog = HazardIdentificationDialog()
        self.assertEqual(dialog.tabs.tabText(0), TAB_BASICS)
        self.assertEqual(dialog.tabs.tabText(1), TAB_INVENTORY)
        self.assertTrue(dialog.tabs.isTabEnabled(0))
        self.assertFalse(dialog.tabs.isTabEnabled(1))
        for index in range(2, dialog.tabs.count()):
            self.assertFalse(dialog.tabs.isTabEnabled(index))
        self.assertEqual(
            [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())],
            list(HAZARD_IDENTIFICATION_TABS),
        )

    @patch("moduly.rizeni_rizik.ui.rizeni_rizik_page.exec_maximized")
    def test_new_identification_from_page(self, mock_exec) -> None:
        from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage

        page = RizeniRizikPage()
        saved_number = {"value": ""}

        def _accept(dialog):
            dialog.basics_widget._select_combo_value(
                dialog.basics_widget.operation,
                self.operation_a.id,
            )
            dialog.basics_widget._reload_workplaces(self.operation_a.id)
            dialog.basics_widget._select_combo_value(
                dialog.basics_widget.workplace,
                self.workplace_a1.id,
            )
            with patch("moduly.rizeni_rizik.ui.hazard_identification_dialog.QMessageBox.information"):
                dialog._save_basics()
            saved_number["value"] = dialog.identification.identification_number
            dialog.accept()
            return True

        mock_exec.side_effect = _accept
        page.new_identification()

        self.assertEqual(page.table.rowCount(), 1)
        self.assertEqual(page.table.item(0, 1).text(), saved_number["value"])

    @patch("moduly.rizeni_rizik.ui.rizeni_rizik_page.exec_maximized")
    def test_edit_identification_from_page(self, mock_exec) -> None:
        from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage

        created = self._create_sample()
        page = RizeniRizikPage()
        page.table.selectRow(0)

        def _accept(dialog):
            dialog.basics_widget.note.setPlainText("Upraveno ze stránky")
            with patch("moduly.rizeni_rizik.ui.hazard_identification_dialog.QMessageBox.information"):
                dialog._save_basics()
            dialog.accept()
            return True

        mock_exec.side_effect = _accept
        page.edit_selected_identification()

        reloaded = hazard_identification_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.note, "Upraveno ze stránky")

    def test_activate_and_deactivate(self) -> None:
        created = self._create_sample()
        self.assertTrue(hazard_identification_service.deactivate(created.id))
        reloaded = hazard_identification_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(hazard_identification_service.activate(created.id))
        reloaded = hazard_identification_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_workplaces_filtered_by_operation(self) -> None:
        from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
            HazardIdentificationBasicsWidget,
        )

        widget = HazardIdentificationBasicsWidget()
        widget._select_combo_value(widget.operation, self.operation_a.id)
        widget._reload_workplaces(self.operation_a.id)

        workplace_ids = set(widget.operation_workplace_ids())
        self.assertEqual(workplace_ids, {self.workplace_a1.id, self.workplace_a2.id})
        self.assertNotIn(self.workplace_b1.id, workplace_ids)

    def test_workplace_parts_filtered_by_workplace(self) -> None:
        from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
            HazardIdentificationBasicsWidget,
        )

        widget = HazardIdentificationBasicsWidget()
        widget._reload_workplace_parts(self.workplace_a1.id)

        part_ids = set(widget.workplace_part_ids())
        self.assertEqual(part_ids, {self.part_a1.id})

    def test_reject_invalid_workplace_combination(self) -> None:
        with self.assertRaises(HazardIdentificationError):
            hazard_identification_service.create_identification(
                operation_id=self.operation_a.id,
                workplace_id=self.workplace_b1.id,
            )


if __name__ == "__main__":
    unittest.main()
