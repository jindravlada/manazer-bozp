"""Fáze R15 – sloučení Analýzy pracoviště a Nežádoucích událostí."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
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
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_IDENTIFICATION_VISIBLE_TABS,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        INVENTORY_COL_NAME,
        ITEM_EVENT_COL_NAME,
        ITEM_EVENT_TABLE_HEADERS,
        TAB_EVENTS,
        TAB_INVENTORY,
        TAB_RISK_ASSESSMENT,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget


class WorkplaceAnalysisEventsMergeR15TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R15",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R15",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.item_a = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Portálový jeřáb",
        )
        self.item_b = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Vozík",
        )
        self.event_a1 = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_a.id,
            name="Pád břemene",
        )
        self.event_a2 = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_a.id,
            name="Přiražení",
        )
        self.event_b1 = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_b.id,
            name="Převrácení",
        )

    def test_events_tab_removed_from_dialog(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertEqual(labels, list(HAZARD_IDENTIFICATION_VISIBLE_TABS))
        self.assertNotIn(TAB_EVENTS, labels)
        self.assertEqual(dialog.tabs.tabText(2), TAB_INVENTORY)
        self.assertEqual(dialog.tabs.tabText(3), TAB_RISK_ASSESSMENT)
        self.assertFalse(hasattr(dialog, "events_widget"))
        self.assertIs(dialog.tabs.widget(2), dialog.inventory_widget)

    def test_events_filtered_by_selected_item(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)

        widget._selected_item_id = self.item_a.id
        widget._load_events_table()
        names_a = {
            widget.events_table.item(row, ITEM_EVENT_COL_NAME).text()
            for row in range(widget.events_table.rowCount())
        }
        self.assertEqual(names_a, {"Pád břemene", "Přiražení"})
        self.assertEqual(
            [
                widget.events_table.horizontalHeaderItem(column).text()
                for column in range(widget.events_table.columnCount())
            ],
            ITEM_EVENT_TABLE_HEADERS,
        )

        widget._selected_item_id = self.item_b.id
        widget._selected_event_id = None
        widget._load_events_table()
        names_b = {
            widget.events_table.item(row, ITEM_EVENT_COL_NAME).text()
            for row in range(widget.events_table.rowCount())
        }
        self.assertEqual(names_b, {"Převrácení"})

    def test_changing_item_selection_reloads_events(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget.refresh()

        # Vybrat řádek položky A
        for row in range(widget.table.rowCount()):
            if str(self.item_a.id) == widget.table.item(row, 0).text():
                widget.table.selectRow(row)
                break
        self.assertEqual(widget._selected_item_id, self.item_a.id)
        self.assertEqual(widget.events_table.rowCount(), 2)

        for row in range(widget.table.rowCount()):
            if str(self.item_b.id) == widget.table.item(row, 0).text():
                widget.table.selectRow(row)
                break
        self.assertEqual(widget._selected_item_id, self.item_b.id)
        self.assertEqual(widget.events_table.rowCount(), 1)
        self.assertEqual(
            widget.events_table.item(0, ITEM_EVENT_COL_NAME).text(),
            "Převrácení",
        )

    def test_new_event_prefilled_with_selected_source(self) -> None:
        dialog = HazardEventDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_inventory_item_id=self.item_a.id,
        )
        self.assertEqual(dialog.inventory_item.currentData(), self.item_a.id)
        # Při editaci lze zdroj změnit – nabídka jen z aktuální identifikace
        option_ids = {
            dialog.inventory_item.itemData(index)
            for index in range(dialog.inventory_item.count())
        }
        self.assertEqual(option_ids, {self.item_a.id, self.item_b.id})

    def test_event_count_updates_on_item_display(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget.refresh()

        names = [
            widget.table.item(row, INVENTORY_COL_NAME).text()
            for row in range(widget.table.rowCount())
        ]
        self.assertTrue(any("Portálový jeřáb — 2 událostí" == name for name in names))
        self.assertTrue(any("Vozík — 1 událost" == name for name in names))

        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_b.id,
            name="Sjetí z rampy",
        )
        widget.refresh()
        names = [
            widget.table.item(row, INVENTORY_COL_NAME).text()
            for row in range(widget.table.rowCount())
        ]
        self.assertTrue(any("Vozík — 2 událostí" == name for name in names))

    def test_event_buttons_require_item_selection(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)
        self.assertIsNone(widget._selected_item_id)
        self.assertFalse(widget.add_event_btn.isEnabled())

        widget._selected_item_id = self.item_a.id
        widget._update_event_actions_for_selection()
        self.assertTrue(widget.add_event_btn.isEnabled())
        self.assertEqual(
            [
                widget.add_event_btn.text(),
                widget.edit_event_btn.text(),
                widget.activate_event_btn.text(),
                widget.deactivate_event_btn.text(),
            ],
            ["Přidat událost", "Upravit", "Aktivovat", "Deaktivovat"],
        )


if __name__ == "__main__":
    unittest.main()
