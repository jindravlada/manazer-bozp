"""Fáze R17d – přechod na Master katalog zdrojů rizik."""

from __future__ import annotations

import importlib
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

    from core.database.database_initializer import (
        _migrate_hazard_library_template_master_catalog,
        initialize_database,
    )

    initialize_database()

    from sqlalchemy import delete, text

    from core.database.session import get_session
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )

class HazardLibraryTemplateR17dTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

    def test_items_table_removed_after_migration(self) -> None:
        with get_session() as session:
            tables = session.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='hazard_library_template_items'"
                )
            ).fetchall()
        self.assertEqual(tables, [])

    def test_template_has_category_column(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        reloaded = hazard_library_template_service.get_by_id(template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.category, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)

    def test_events_linked_directly_to_template(self) -> None:
        template = hazard_library_template_service.create_template(name="Schodiště")
        hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Uklouznutí",
        )
        events = hazard_library_template_event_service.get_for_template(template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].template_id, template.id)

    def test_migrate_legacy_single_item(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Obecný vzor",
            description="Popis vzoru",
            note="Poznámka",
            version_number=2,
        )
        template_id = template.id

        with get_session() as session:
            session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS hazard_library_template_items (
                        id INTEGER PRIMARY KEY,
                        template_id INTEGER NOT NULL,
                        category VARCHAR(32) NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT DEFAULT '',
                        active BOOLEAN DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            session.execute(
                text(
                    """
                    INSERT INTO hazard_library_template_items (
                        template_id, category, name, description, active, sort_order
                    )
                    VALUES (:template_id, :category, 'Vrtačka', 'Popis vrtačky', 1, 1)
                    """
                ),
                {
                    "template_id": template_id,
                    "category": HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                },
            )
            item_id = int(session.execute(text("SELECT last_insert_rowid()")).scalar())
            session.execute(text("DROP TABLE IF EXISTS hazard_library_template_events"))
            session.execute(
                text(
                    """
                    CREATE TABLE hazard_library_template_events (
                        id INTEGER PRIMARY KEY,
                        template_item_id INTEGER NOT NULL,
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
            session.execute(
                text(
                    """
                    INSERT INTO hazard_library_template_events (
                        template_item_id, name, description, note, active, sort_order
                    )
                    VALUES (:item_id, 'Kontakt s rotující částí', '', 'Pozn.', 1, 1)
                    """
                ),
                {"item_id": item_id},
            )
            session.commit()

        _migrate_hazard_library_template_master_catalog()

        reloaded = hazard_library_template_service.get_by_id(template_id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Vrtačka")
        self.assertEqual(reloaded.description, "Popis vrtačky")
        self.assertEqual(reloaded.version_number, 2)
        self.assertEqual(reloaded.note, "Poznámka")

        events = hazard_library_template_event_service.get_for_template(template_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Kontakt s rotující částí")
        self.assertEqual(events[0].template_id, template_id)

        with get_session() as session:
            tables = session.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='hazard_library_template_items'"
                )
            ).fetchall()
            columns = session.execute(text("PRAGMA table_info(hazard_library_template_events)")).fetchall()
        self.assertEqual(tables, [])
        column_names = {column[1] for column in columns}
        self.assertIn("template_id", column_names)
        self.assertNotIn("template_item_id", column_names)

    def test_migrate_legacy_multiple_items_split(self) -> None:
        template = hazard_library_template_service.create_template(name="Kombinovaný vzor")
        template_id = template.id

        with get_session() as session:
            session.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS hazard_library_template_items (
                        id INTEGER PRIMARY KEY,
                        template_id INTEGER NOT NULL,
                        category VARCHAR(32) NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT DEFAULT '',
                        active BOOLEAN DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            session.execute(
                text(
                    """
                    INSERT INTO hazard_library_template_items (
                        template_id, category, name, description, active, sort_order
                    )
                    VALUES
                        (:template_id, :category, 'Vrtačka', '', 1, 1),
                        (:template_id, :category, 'Bruska', '', 1, 2)
                    """
                ),
                {
                    "template_id": template_id,
                    "category": HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                },
            )
            item_rows = session.execute(
                text(
                    "SELECT id, name FROM hazard_library_template_items "
                    "WHERE template_id = :template_id ORDER BY sort_order"
                ),
                {"template_id": template_id},
            ).fetchall()
            session.execute(text("DROP TABLE IF EXISTS hazard_library_template_events"))
            session.execute(
                text(
                    """
                    CREATE TABLE hazard_library_template_events (
                        id INTEGER PRIMARY KEY,
                        template_item_id INTEGER NOT NULL,
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
            for item_id, item_name in item_rows:
                session.execute(
                    text(
                        """
                        INSERT INTO hazard_library_template_events (
                            template_item_id, name, active, sort_order
                        )
                        VALUES (:item_id, :name, 1, 1)
                        """
                    ),
                    {"item_id": item_id, "name": f"Událost {item_name}"},
                )
            session.commit()

        _migrate_hazard_library_template_master_catalog()

        templates = hazard_library_template_service.get_all_rows(include_inactive=True)
        names = sorted(row.template.name for row in templates)
        self.assertEqual(names, ["Bruska", "Vrtačka"])

        for row in templates:
            events = hazard_library_template_event_service.get_for_template(row.template.id)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].name, f"Událost {row.template.name}")


if __name__ == "__main__":
    unittest.main()
