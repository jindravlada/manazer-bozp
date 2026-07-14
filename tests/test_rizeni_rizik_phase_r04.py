"""Fáze R04 – evidence nebezpečí."""

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
        DEFAULT_IDENTIFIED_HAZARD_SOURCE,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_ACTIVITY,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        IDENTIFIED_HAZARD_SOURCE_MANUAL,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
        IdentifiedHazardError,
        identified_hazard_service,
    )
    from moduly.rizeni_rizik.ui.identified_hazard_dialog import IdentifiedHazardDialog
    from moduly.rizeni_rizik.ui.identified_hazards_widget import IdentifiedHazardsWidget


class IdentifiedHazardPhaseR04TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(IdentifiedHazard))
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
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.identification_b = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

        self.lokomotiva = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        self.posun = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_ACTIVITY,
            name="Posun",
        )

    def test_identified_hazards_table_exists(self) -> None:
        columns = _table_columns("identified_hazards")
        self.assertIn("inventory_item_id", columns)
        self.assertIn("source_type", columns)

    def test_create_manual_hazard(self) -> None:
        hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
            description="Riziko při údržbě",
        )
        self.assertEqual(hazard.inventory_item_id, self.lokomotiva.id)
        self.assertEqual(hazard.source_type, DEFAULT_IDENTIFIED_HAZARD_SOURCE)
        self.assertTrue(hazard.active)

    def test_reject_inventory_item_from_other_identification(self) -> None:
        other_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_b.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jiná lokomotiva",
        )
        with self.assertRaises(IdentifiedHazardError):
            identified_hazard_service.create_hazard(
                hazard_identification_id=self.identification_a.id,
                inventory_item_id=other_item.id,
                name="Nebezpečí",
            )

    def test_reject_empty_name(self) -> None:
        with self.assertRaises(IdentifiedHazardError):
            identified_hazard_service.create_hazard(
                hazard_identification_id=self.identification_a.id,
                inventory_item_id=self.lokomotiva.id,
                name="   ",
            )

    def test_reject_active_duplicate_on_same_inventory_item(self) -> None:
        identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
        )
        with self.assertRaises(IdentifiedHazardError):
            identified_hazard_service.create_hazard(
                hazard_identification_id=self.identification_a.id,
                inventory_item_id=self.lokomotiva.id,
                name="  pád z výšky ",
            )

    def test_allow_same_name_on_different_inventory_item(self) -> None:
        identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
        )
        hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.posun.id,
            name="Pád z výšky",
        )
        self.assertEqual(hazard.inventory_item_id, self.posun.id)

    def test_update_hazard(self) -> None:
        hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
        )
        updated = identified_hazard_service.update_hazard(
            hazard.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
            description="Aktualizovaný popis",
            note="Poznámka",
            source_type=IDENTIFIED_HAZARD_SOURCE_MANUAL,
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.description, "Aktualizovaný popis")
        self.assertEqual(updated.note, "Poznámka")

    def test_activate_and_deactivate_hazard(self) -> None:
        hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
        )
        self.assertTrue(identified_hazard_service.deactivate_hazard(hazard.id))
        reloaded = identified_hazard_service.get_by_id(hazard.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(identified_hazard_service.activate_hazard(hazard.id))
        reloaded = identified_hazard_service.get_by_id(hazard.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_inventory_item_candidates_filtered_by_identification(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_b.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Cizí položka",
        )
        candidates = identified_hazard_service.get_inventory_item_candidates(
            self.identification_a.id
        )
        self.assertEqual({item.id for item in candidates}, {self.lokomotiva.id, self.posun.id})

    def test_active_hazard_counts_for_inventory_item(self) -> None:
        identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pád z výšky",
        )
        identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Popálení",
        )
        inactive = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification_a.id,
            inventory_item_id=self.lokomotiva.id,
            name="Střet",
        )
        identified_hazard_service.deactivate_hazard(inactive.id)

        counts = identified_hazard_service.count_active_by_inventory_items(
            self.identification_a.id
        )
        self.assertEqual(counts[self.lokomotiva.id], 2)
        self.assertEqual(
            identified_hazard_service.count_active_for_inventory_item(self.lokomotiva.id),
            2,
        )

    def test_create_hazard_from_inventory_context(self) -> None:
        dialog = IdentifiedHazardDialog(
            None,
            hazard_identification_id=self.identification_a.id,
            default_inventory_item_id=self.lokomotiva.id,
        )
        self.assertEqual(dialog.inventory_item.currentData(), self.lokomotiva.id)
        dialog.name.setText("Střet s vozidlem")
        dialog.accept()

        hazards = identified_hazard_service.get_for_identification(self.identification_a.id)
        self.assertEqual(len(hazards), 1)
        self.assertEqual(hazards[0].hazard.name, "Střet s vozidlem")

    def test_read_only_hazards_for_completed_identification(self) -> None:
        completed = hazard_identification_service.update_identification(
            self.identification_a.id,
            operation_id=self.identification_a.operation_id,
            workplace_id=self.identification_a.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        widget = IdentifiedHazardsWidget()
        widget.set_identification(completed.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
