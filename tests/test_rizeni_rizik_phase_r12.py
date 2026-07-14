"""Fáze R12 – migrace: události přímo na zdroj analýzy, odstranění Nebezpečí."""

from __future__ import annotations

import importlib
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
        _migrate_hazard_events_drop_identified_hazards,
        _table_columns,
        initialize_database,
    )
    from core.database.session import get_session

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
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


class HazardEventsMigrationR12TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R12",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R12",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Petr", last_name="Migrace")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokomotiva",
        )

    def test_fresh_schema_has_inventory_item_id_no_hazards_table(self) -> None:
        event_columns = _table_columns("hazard_events")
        self.assertIn("inventory_item_id", event_columns)
        self.assertNotIn("identified_hazard_id", event_columns)
        self.assertEqual(_table_columns("identified_hazards"), set())

    def test_migration_rewires_events_and_drops_hazards(self) -> None:
        """Simuluje staré schéma a ověří převod vazby + DROP identified_hazards."""
        engine = _db_engine()
        with engine.connect() as connection:
            connection.execute(text("DROP TABLE IF EXISTS hazard_events"))
            connection.execute(text("DROP TABLE IF EXISTS identified_hazards"))
            connection.execute(
                text(
                    """
                    CREATE TABLE identified_hazards (
                        id INTEGER PRIMARY KEY,
                        hazard_identification_id INTEGER NOT NULL,
                        inventory_item_id INTEGER NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT DEFAULT '',
                        note TEXT DEFAULT '',
                        source_type VARCHAR(32) DEFAULT 'manual',
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
                    CREATE TABLE hazard_events (
                        id INTEGER PRIMARY KEY,
                        identified_hazard_id INTEGER NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT DEFAULT '',
                        note TEXT DEFAULT '',
                        active BOOLEAN DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO identified_hazards (
                        id, hazard_identification_id, inventory_item_id, name, active
                    ) VALUES (99, :hid, :iid, 'Pohyb', 1)
                    """
                ),
                {"hid": self.identification.id, "iid": self.item.id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO hazard_events (
                        id, identified_hazard_id, name, description, note,
                        active, sort_order
                    ) VALUES (7, 99, 'Sražení', '', '', 1, 1)
                    """
                )
            )
            connection.commit()

        self.assertIn("identified_hazard_id", _table_columns("hazard_events"))
        self.assertTrue(_table_columns("identified_hazards"))

        _migrate_hazard_events_drop_identified_hazards()

        event_columns = _table_columns("hazard_events")
        self.assertIn("inventory_item_id", event_columns)
        self.assertNotIn("identified_hazard_id", event_columns)
        self.assertEqual(_table_columns("identified_hazards"), set())

        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT id, inventory_item_id, name FROM hazard_events WHERE id = 7"
                )
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 7)
        self.assertEqual(row[1], self.item.id)
        self.assertEqual(row[2], "Sražení")

        # ORM služba musí událost vidět pod identifikací
        rows = hazard_event_service.get_for_identification(
            self.identification.id,
            include_inactive=False,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].event.name, "Sražení")
        self.assertEqual(rows[0].inventory_item_name, "Lokomotiva")


if __name__ == "__main__":
    unittest.main()
