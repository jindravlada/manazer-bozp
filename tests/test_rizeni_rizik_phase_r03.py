"""Fáze R03 – analýza inventury."""

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
        HAZARD_INVENTORY_CATEGORY_ACTIVITY,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
        HAZARD_INVENTORY_CATEGORY_PERSON,
        HAZARD_INVENTORY_CATEGORY_SUBSTANCE,
        HAZARD_INVENTORY_RELATION_ACTIVITY,
        HAZARD_INVENTORY_RELATION_PERSON,
        HAZARD_INVENTORY_RELATION_SUBSTANCE,
        HAZARD_INVENTORY_RELATION_ENVIRONMENT,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_inventory_relation import HazardInventoryRelation
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_relation_service import (
        HazardInventoryRelationError,
        hazard_inventory_relation_service,
    )


class HazardInventoryRelationPhaseR03TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardInventoryRelation))
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
        self.udrzba = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_ACTIVITY,
            name="Údržba",
        )
        self.nafta = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_SUBSTANCE,
            name="Motorová nafta",
        )
        self.strojvedouci = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_PERSON,
            name="Strojvedoucí",
        )
        self.posunovac = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_PERSON,
            name="Posunovač",
        )
        self.noc = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_a.id,
            category=HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
            name="Práce v noci",
        )

    def test_relations_table_exists(self) -> None:
        columns = _table_columns("hazard_inventory_relations")
        self.assertIn("source_item_id", columns)
        self.assertIn("target_item_id", columns)
        self.assertIn("relation_type", columns)

    def test_create_relation_between_items_same_identification(self) -> None:
        relation = hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.posun.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
            note="Běžný provoz",
        )
        self.assertEqual(relation.source_item_id, self.lokomotiva.id)
        self.assertEqual(relation.target_item_id, self.posun.id)
        self.assertTrue(relation.active)

    def test_practical_example_relations(self) -> None:
        pairs = [
            (self.posun.id, HAZARD_INVENTORY_RELATION_ACTIVITY),
            (self.udrzba.id, HAZARD_INVENTORY_RELATION_ACTIVITY),
            (self.nafta.id, HAZARD_INVENTORY_RELATION_SUBSTANCE),
            (self.strojvedouci.id, HAZARD_INVENTORY_RELATION_PERSON),
            (self.posunovac.id, HAZARD_INVENTORY_RELATION_PERSON),
            (self.noc.id, HAZARD_INVENTORY_RELATION_ENVIRONMENT),
        ]

        for target_id, relation_type in pairs:
            hazard_inventory_relation_service.create_relation(
                hazard_identification_id=self.identification_a.id,
                source_item_id=self.lokomotiva.id,
                target_item_id=target_id,
                relation_type=relation_type,
            )

        self.assertEqual(
            hazard_inventory_relation_service.count_active_for_source(self.lokomotiva.id),
            6,
        )

    def test_reject_self_relation(self) -> None:
        with self.assertRaises(HazardInventoryRelationError):
            hazard_inventory_relation_service.create_relation(
                hazard_identification_id=self.identification_a.id,
                source_item_id=self.lokomotiva.id,
                target_item_id=self.lokomotiva.id,
                relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
            )

    def test_reject_relation_across_identifications(self) -> None:
        other_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification_b.id,
            category=HAZARD_INVENTORY_CATEGORY_ACTIVITY,
            name="Posun",
        )
        with self.assertRaises(HazardInventoryRelationError):
            hazard_inventory_relation_service.create_relation(
                hazard_identification_id=self.identification_a.id,
                source_item_id=self.lokomotiva.id,
                target_item_id=other_item.id,
                relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
            )

    def test_reject_active_duplicate(self) -> None:
        hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.posun.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        with self.assertRaises(HazardInventoryRelationError):
            hazard_inventory_relation_service.create_relation(
                hazard_identification_id=self.identification_a.id,
                source_item_id=self.lokomotiva.id,
                target_item_id=self.posun.id,
                relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
            )

    def test_target_candidates_filtered_by_relation_type(self) -> None:
        activity_candidates = hazard_inventory_relation_service.get_target_candidates(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        person_candidates = hazard_inventory_relation_service.get_target_candidates(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            relation_type=HAZARD_INVENTORY_RELATION_PERSON,
        )

        self.assertEqual({item.id for item in activity_candidates}, {self.posun.id, self.udrzba.id})
        self.assertEqual(
            {item.id for item in person_candidates},
            {self.strojvedouci.id, self.posunovac.id},
        )

    def test_exclude_source_from_target_candidates(self) -> None:
        candidates = hazard_inventory_relation_service.get_target_candidates(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.posun.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        self.assertNotIn(self.posun.id, {item.id for item in candidates})

    def test_update_relation_note(self) -> None:
        relation = hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.posun.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        updated = hazard_inventory_relation_service.update_relation(
            relation.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
            target_item_id=self.posun.id,
            note="Aktualizovaná poznámka",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.note, "Aktualizovaná poznámka")

    def test_activate_and_deactivate_relation(self) -> None:
        relation = hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.posun.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        self.assertTrue(hazard_inventory_relation_service.deactivate_relation(relation.id))
        reloaded = hazard_inventory_relation_service.get_by_id(relation.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        self.assertTrue(hazard_inventory_relation_service.activate_relation(relation.id))
        reloaded = hazard_inventory_relation_service.get_by_id(relation.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)

    def test_active_relation_counts(self) -> None:
        hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.posun.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.udrzba.id,
            relation_type=HAZARD_INVENTORY_RELATION_ACTIVITY,
        )
        inactive = hazard_inventory_relation_service.create_relation(
            hazard_identification_id=self.identification_a.id,
            source_item_id=self.lokomotiva.id,
            target_item_id=self.nafta.id,
            relation_type=HAZARD_INVENTORY_RELATION_SUBSTANCE,
        )
        hazard_inventory_relation_service.deactivate_relation(inactive.id)

        counts = hazard_inventory_relation_service.count_active_by_source_items(
            self.identification_a.id
        )
        self.assertEqual(counts[self.lokomotiva.id], 2)

    def test_read_only_analysis_for_completed_identification(self) -> None:
        completed = hazard_identification_service.update_identification(
            self.identification_a.id,
            operation_id=self.identification_a.operation_id,
            workplace_id=self.identification_a.workplace_id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        assert completed is not None

        from moduly.rizeni_rizik.ui.hazard_inventory_analysis_widget import (
            HazardInventoryAnalysisWidget,
        )

        widget = HazardInventoryAnalysisWidget()
        widget.set_source_item(
            self.lokomotiva,
            identification_id=completed.id,
            read_only=True,
        )
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
