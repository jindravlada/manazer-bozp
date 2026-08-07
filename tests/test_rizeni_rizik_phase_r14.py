"""Fáze R14 – odstranění souvislostí z analýzy pracoviště."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _db_engine,
        _migrate_drop_hazard_inventory_relations,
        _table_columns,
        initialize_database,
    )
    from core.database.session import get_session

    initialize_database()

    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        INVENTORY_ADD_NEW_BUTTON,
        format_inventory_item_display_name,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )


class HazardInventoryRelationsRemovalR14TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R14",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R14",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Anna", last_name="R14")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        self.item_a = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb",
        )
        self.item_b = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Vozík",
        )

    def test_fresh_schema_has_no_relations_table(self) -> None:
        self.assertEqual(_table_columns("hazard_inventory_relations"), set())
        self.assertTrue(_table_columns("hazard_inventory_items"))

    def test_migration_drops_relations_table_only(self) -> None:
        engine = _db_engine()
        with engine.connect() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS hazard_inventory_relations (
                        id INTEGER PRIMARY KEY,
                        hazard_identification_id INTEGER NOT NULL,
                        source_item_id INTEGER NOT NULL,
                        target_item_id INTEGER NOT NULL,
                        relation_type VARCHAR(64) NOT NULL,
                        note TEXT DEFAULT '',
                        active BOOLEAN DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO hazard_inventory_relations (
                        id, hazard_identification_id, source_item_id, target_item_id,
                        relation_type, active
                    ) VALUES (1, :hid, :src, :tgt, 'uses', 1)
                    """
                ),
                {
                    "hid": self.identification.id,
                    "src": self.item_a.id,
                    "tgt": self.item_b.id,
                },
            )
            connection.commit()

        self.assertTrue(_table_columns("hazard_inventory_relations"))
        item_columns_before = _table_columns("hazard_inventory_items")

        _migrate_drop_hazard_inventory_relations()

        self.assertEqual(_table_columns("hazard_inventory_relations"), set())
        self.assertEqual(_table_columns("hazard_inventory_items"), item_columns_before)

        items = hazard_inventory_item_service.get_for_identification(
            self.identification.id,
            include_inactive=True,
        )
        self.assertEqual({item.name for item in items}, {"Jeřáb", "Vozík"})

    def test_display_name_without_relations(self) -> None:
        self.assertEqual(format_inventory_item_display_name("Jeřáb"), "Jeřáb")
        self.assertEqual(
            format_inventory_item_display_name("Jeřáb", event_count=2),
            "Jeřáb — 2 událostí",
        )
        self.assertNotIn("souvislost", format_inventory_item_display_name("Jeřáb", event_count=1))

    def test_workplace_analysis_without_relations_panel(self) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget

        app = QApplication.instance() or QApplication([])
        widget = HazardInventoryWidget()
        widget.set_identification(self.identification.id, read_only=False)

        self.assertTrue(hasattr(widget, "category_list"))
        self.assertTrue(hasattr(widget, "table"))
        self.assertEqual(
            [widget.add_btn.text(), widget.edit_btn.text(), widget.activate_btn.text(),
             widget.deactivate_btn.text()],
            [INVENTORY_ADD_NEW_BUTTON, "Upravit", "Aktivovat", "Deaktivovat"],
        )
        self.assertEqual(widget.add_event_btn.text(), "Přidat událost")
        self.assertTrue(hasattr(widget, "events_table"))
        self.assertFalse(hasattr(widget, "analysis_panel"))
        self.assertFalse(hasattr(widget, "relation_table"))

        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_a.id,
            name="Pád břemene",
        )
        widget.refresh()
        names = [
            widget.table.item(row, 1).text()
            for row in range(widget.table.rowCount())
        ]
        self.assertTrue(any("Jeřáb" in name and "událost" in name for name in names))
        self.assertFalse(any("souvislost" in name.casefold() for name in names))
        widget.deleteLater()
        del app

    def test_ai_export_without_relations(self) -> None:
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item_a.id,
            name="Pád břemene",
        )
        content = hazard_identification_peer_review_provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(export_scope="full"),
        )
        self.assertEqual(content.batch_count, 1)
        batch = content.batches[0]
        for node in batch.zadani_json["workplace_analysis"]:
            self.assertNotIn("relations", node)
            payload = json.dumps(node, ensure_ascii=False).casefold()
            self.assertNotIn("souvislost", payload)
            self.assertNotIn("relation", payload)

        data_text = batch.data_text.casefold()
        self.assertNotIn("souvislost", data_text)
        self.assertIn("zdroj analýzy", data_text)
        self.assertIn("událost", data_text)

        schema_text = json.dumps(batch.schema_json, ensure_ascii=False).casefold()
        prompt_text = batch.prompt_text.casefold()
        self.assertNotIn("souvislost", schema_text)
        self.assertNotIn("souvislost", prompt_text)

        # Import: návrhy v oblasti Souvislostí se nezařazují
        from core.ai_oponentni.types import AiProposal

        outcome = hazard_identification_peer_review_provider._apply_one(
            self.identification.id,
            AiProposal(
                area="Souvislost",
                name="Jeřáb používá vozík",
                parent_export_id="ITEM-001",
                reasoning="test",
            ),
            content.export_id_map,
        )
        self.assertEqual(outcome, "unassigned")


if __name__ == "__main__":
    unittest.main()
