"""Fáze R05 – nežádoucí události."""

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
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.identified_hazard import IdentifiedHazard
    from moduly.rizeni_rizik.sluzby.hazard_event_service import (
        HazardEventError,
        hazard_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
        identified_hazard_service,
    )
    from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog
    from moduly.rizeni_rizik.ui.hazard_events_widget import HazardEventsWidget


class HazardEventPhaseR05TestCase(unittest.TestCase):
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
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.other_identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

        self.lokomotiva = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )
        self.hazard_a = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.lokomotiva.id,
            name="Pohyb kolejového vozidla",
        )
        self.hazard_b = identified_hazard_service.create_hazard(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.lokomotiva.id,
            name="Kontakt s horkým povrchem",
        )

    def test_hazard_events_table_exists(self) -> None:
        columns = _table_columns("hazard_events")
        self.assertIn("identified_hazard_id", columns)
        self.assertIn("sort_order", columns)

    def test_create_event(self) -> None:
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
            description="Popis události",
        )
        self.assertEqual(event.identified_hazard_id, self.hazard_a.id)
        self.assertTrue(event.active)

    def test_reject_empty_name(self) -> None:
        with self.assertRaises(HazardEventError):
            hazard_event_service.create_event(
                hazard_identification_id=self.identification.id,
                identified_hazard_id=self.hazard_a.id,
                name="   ",
            )

    def test_reject_active_duplicate_within_hazard(self) -> None:
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
        )
        with self.assertRaises(HazardEventError):
            hazard_event_service.create_event(
                hazard_identification_id=self.identification.id,
                identified_hazard_id=self.hazard_a.id,
                name="  sražení s osobou ",
            )

    def test_allow_same_name_on_different_hazard(self) -> None:
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_b.id,
            name="Sražení s osobou",
        )
        self.assertEqual(event.identified_hazard_id, self.hazard_b.id)

    def test_update_event(self) -> None:
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
        )
        updated = hazard_event_service.update_event(
            event.id,
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
            description="Aktualizovaný popis",
            note="Poznámka",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.description, "Aktualizovaný popis")
        self.assertEqual(updated.note, "Poznámka")

    def test_activate_and_deactivate_event(self) -> None:
        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
        )
        self.assertTrue(hazard_event_service.deactivate_event(event.id))
        reloaded = hazard_event_service.get_by_id(event.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(hazard_event_service.activate_event(event.id))
        reloaded = hazard_event_service.get_by_id(event.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_reject_hazard_from_other_identification(self) -> None:
        other_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.other_identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jiná lokomotiva",
        )
        other_hazard = identified_hazard_service.create_hazard(
            hazard_identification_id=self.other_identification.id,
            inventory_item_id=other_item.id,
            name="Jiné nebezpečí",
        )
        with self.assertRaises(HazardEventError):
            hazard_event_service.create_event(
                hazard_identification_id=self.identification.id,
                identified_hazard_id=other_hazard.id,
                name="Neplatná událost",
            )

    def test_active_event_counts_for_hazard(self) -> None:
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Sražení s osobou",
        )
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Vykolejení",
        )
        inactive = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            identified_hazard_id=self.hazard_a.id,
            name="Požár",
        )
        hazard_event_service.deactivate_event(inactive.id)

        counts = hazard_event_service.count_active_by_hazards(self.identification.id)
        self.assertEqual(counts[self.hazard_a.id], 2)
        self.assertEqual(
            hazard_event_service.count_active_for_hazard(self.hazard_a.id),
            2,
        )

    def test_create_event_from_hazard_context(self) -> None:
        dialog = HazardEventDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_identified_hazard_id=self.hazard_a.id,
        )
        self.assertEqual(dialog.hazard.currentData(), self.hazard_a.id)
        dialog.name.setText("Náraz do překážky")
        dialog.accept()

        rows = hazard_event_service.get_for_identification(self.identification.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event.name, "Náraz do překážky")
        self.assertEqual(rows[0].hazard_name, "Pohyb kolejového vozidla")

    def test_read_only_events_for_completed_identification(self) -> None:
        completed = hazard_identification_service.update_identification(
            self.identification.id,
            operation_id=self.identification.operation_id,
            workplace_id=self.identification.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        widget = HazardEventsWidget()
        widget.set_identification(completed.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
