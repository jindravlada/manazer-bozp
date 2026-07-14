"""Fáze R02 – inventura pracoviště."""

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

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORIES,
        HAZARD_INVENTORY_CATEGORY_ACTIVITY,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        HAZARD_INVENTORY_CATEGORY_LABELS,
        HAZARD_INVENTORY_CATEGORY_OTHER,
        HAZARD_INVENTORY_CATEGORY_TRANSPORT,
        is_identification_inventory_read_only,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        HazardInventoryItemError,
        hazard_inventory_item_service,
    )


class HazardInventoryPhaseR02TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification_a = hazard_identification_service.create_identification(
            title="Identifikace A",
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.identification_b = hazard_identification_service.create_identification(
            title="Identifikace B",
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

    def test_inventory_table_exists(self) -> None:
        columns = _table_columns("hazard_inventory_items")
        self.assertIn("hazard_identification_id", columns)
        self.assertIn("category", columns)
        self.assertIn("sort_order", columns)

    def test_create_item_for_each_category(self) -> None:
        created_ids = []
        for index, category in enumerate(HAZARD_INVENTORY_CATEGORIES, start=1):
            item = hazard_inventory_item_service.create_item(
                hazard_identification_id=self.identification_a.id,
                category=category,
                name=f"Položka {index}",
            )
            self.assertEqual(item.category, category)
            created_ids.append(item.id)

        loaded = hazard_inventory_item_service.get_for_identification(self.identification_a.id)
        self.assertEqual(len(loaded), len(HAZARD_INVENTORY_CATEGORIES))
        self.assertEqual({item.id for item in loaded}, set(created_ids))

    def test_items_are_separated_by_identification(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Pila",
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_b.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Pila",
        )

        items_a = hazard_inventory_item_service.get_for_identification(self.identification_a.id)
        items_b = hazard_inventory_item_service.get_for_identification(self.identification_b.id)
        self.assertEqual(len(items_a), 1)
        self.assertEqual(len(items_b), 1)
        self.assertNotEqual(items_a[0].id, items_b[0].id)

    def test_update_item(self) -> None:
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Původní",
            description="Popis",
        )
        updated = hazard_inventory_item_service.update_item(
            item.id,
            category=HAZARD_INVENTORY_CATEGORY_ACTIVITY,
            name="Upravená",
            description="Nový popis",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.category, HAZARD_INVENTORY_CATEGORY_ACTIVITY)
        self.assertEqual(updated.name, "Upravená")
        self.assertEqual(updated.description, "Nový popis")

    def test_activate_and_deactivate_item(self) -> None:
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Bruska",
        )
        self.assertTrue(hazard_inventory_item_service.deactivate_item(item.id))
        reloaded = hazard_inventory_item_service.get_by_id(item.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(hazard_inventory_item_service.activate_item(item.id))
        reloaded = hazard_inventory_item_service.get_by_id(item.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_reject_empty_name(self) -> None:
        with self.assertRaises(HazardInventoryItemError):
            hazard_inventory_item_service.create_item(
                hazard_identification_id=self.identification_a.id,
                category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                name="   ",
            )

    def test_reject_active_duplicate_in_same_category(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Vrtačka",
        )
        with self.assertRaises(HazardInventoryItemError):
            hazard_inventory_item_service.create_item(
                hazard_identification_id=self.identification_a.id,
                category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                name="  vrtačka  ",
            )

    def test_allow_same_name_in_different_category(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Pohyblivá plošina",
        )
        other = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_ACTIVITY,
            name="Pohyblivá plošina",
        )
        self.assertEqual(other.category, HAZARD_INVENTORY_CATEGORY_ACTIVITY)

    def test_active_counts_by_category(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="A1",
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="A2",
        )
        inactive = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="A3",
        )
        hazard_inventory_item_service.deactivate_item(inactive.id)
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_ACTIVITY,
            name="B1",
        )

        counts = hazard_inventory_item_service.count_active_by_category(self.identification_a.id)
        self.assertEqual(counts[HAZARD_INVENTORY_CATEGORY_EQUIPMENT], 2)
        self.assertEqual(counts[HAZARD_INVENTORY_CATEGORY_ACTIVITY], 1)
        self.assertEqual(counts[HAZARD_INVENTORY_CATEGORY_OTHER], 0)

    def test_inventory_widget_shows_category_counts(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Soustruh",
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Fréza",
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_TRANSPORT,
            name="VZV",
        )

        from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget

        widget = HazardInventoryWidget()
        widget.set_identification(self.identification_a.id, read_only=False)
        equipment_label = HAZARD_INVENTORY_CATEGORY_LABELS[HAZARD_INVENTORY_CATEGORY_EQUIPMENT]
        transport_label = HAZARD_INVENTORY_CATEGORY_LABELS[HAZARD_INVENTORY_CATEGORY_TRANSPORT]

        labels = [widget.category_list.item(row).text() for row in range(widget.category_list.count())]
        self.assertIn(f"{equipment_label} (2)", labels)
        self.assertIn(f"{transport_label} (1)", labels)

    def test_read_only_mode_for_completed_identification(self) -> None:
        self.assertTrue(is_identification_inventory_read_only(HAZARD_IDENTIFICATION_STATUS_COMPLETED))

        completed = hazard_identification_service.update_identification(
            self.identification_a.id,
            title=self.identification_a.title,
            operation_id=self.identification_a.operation_id,
            workplace_id=self.identification_a.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget

        widget = HazardInventoryWidget()
        widget.set_identification(completed.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
