"""HOTFIX R17d.1 – idempotence migrace Master katalogu."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())


def _reload_database_modules():
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _is_hazard_library_master_catalog_migration_complete,
        _migrate_hazard_library_template_master_catalog,
        initialize_database,
    )

    return initialize_database, _migrate_hazard_library_template_master_catalog, (
        _is_hazard_library_master_catalog_migration_complete
    )


with patch.object(Path, "home", return_value=_TMP):
    initialize_database, _migrate_hazard_library_template_master_catalog, (
        _is_hazard_library_master_catalog_migration_complete
    ) = _reload_database_modules()
    initialize_database()

    from sqlalchemy import delete, text

    from core.database.session import get_session
    from moduly.nastaveni.sluzby.settings_service import settings_service
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryMasterCatalogMigrationR17d1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

    def _create_legacy_single_item_schema(self, *, template_id: int, item_id: int) -> None:
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
                        id, template_id, category, name, description, active, sort_order
                    )
                    VALUES (
                        :item_id, :template_id, :category, 'Vrtačka', 'Popis vrtačky', 1, 1
                    )
                    """
                ),
                {
                    "item_id": item_id,
                    "template_id": template_id,
                    "category": HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                },
            )
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
                        id, template_item_id, name, description, note, active, sort_order
                    )
                    VALUES (1, :item_id, 'Kontakt s rotující částí', '', 'Pozn.', 1, 1)
                    """
                ),
                {"item_id": item_id},
            )
            session.commit()

    def _assert_master_catalog_complete(self) -> None:
        self.assertTrue(_is_hazard_library_master_catalog_migration_complete())
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

    def test_first_run_on_legacy_database(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Obecný vzor",
            description="Popis vzoru",
            note="Poznámka",
            version_number=2,
        )
        self._create_legacy_single_item_schema(template_id=template.id, item_id=10)

        _migrate_hazard_library_template_master_catalog()
        self._assert_master_catalog_complete()

        reloaded = hazard_library_template_service.get_by_id(template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Vrtačka")
        events = hazard_library_template_event_service.get_for_template(template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].template_id, template.id)

    def test_second_run_is_idempotent(self) -> None:
        template = hazard_library_template_service.create_template(name="Obecný vzor")
        self._create_legacy_single_item_schema(template_id=template.id, item_id=11)

        _migrate_hazard_library_template_master_catalog()
        _migrate_hazard_library_template_master_catalog()

        self._assert_master_catalog_complete()
        events = hazard_library_template_event_service.get_for_template(template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Kontakt s rotující částí")

    def test_completed_database_without_items_table(self) -> None:
        template = hazard_library_template_service.create_template(name="Hotový zdroj")
        hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Uklouznutí",
        )
        self.assertTrue(_is_hazard_library_master_catalog_migration_complete())

        _migrate_hazard_library_template_master_catalog()

        events = hazard_library_template_event_service.get_for_template(template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].template_id, template.id)

    def test_partial_migration_with_items_already_dropped(self) -> None:
        template = hazard_library_template_service.create_template(name="Částečně migrovaný")
        template_id = template.id

        with get_session() as session:
            session.execute(text("DROP TABLE IF EXISTS hazard_library_template_events"))
            session.execute(
                text(
                    """
                    CREATE TABLE hazard_library_template_events (
                        id INTEGER PRIMARY KEY,
                        template_item_id INTEGER NOT NULL,
                        template_id INTEGER,
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
                        id, template_item_id, template_id, name, active, sort_order
                    )
                    VALUES (1, 99, :template_id, 'Zachovaná událost', 1, 1)
                    """
                ),
                {"template_id": template_id},
            )
            session.commit()

        _migrate_hazard_library_template_master_catalog()
        self._assert_master_catalog_complete()

        events = hazard_library_template_event_service.get_for_template(template_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Zachovaná událost")
        self.assertEqual(events[0].template_id, template_id)

    def test_partial_migration_fills_only_missing_template_id(self) -> None:
        template = hazard_library_template_service.create_template(name="Částečně převedený")
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
                        id, template_id, category, name, active, sort_order
                    )
                    VALUES (20, :template_id, :category, 'Vrtačka', 1, 1)
                    """
                ),
                {
                    "template_id": template_id,
                    "category": HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
                },
            )
            session.execute(text("DROP TABLE IF EXISTS hazard_library_template_events"))
            session.execute(
                text(
                    """
                    CREATE TABLE hazard_library_template_events (
                        id INTEGER PRIMARY KEY,
                        template_item_id INTEGER NOT NULL,
                        template_id INTEGER,
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
                        id, template_item_id, template_id, name, active, sort_order
                    )
                    VALUES
                        (1, 20, :template_id, 'Již převedená', 1, 1),
                        (2, 20, NULL, 'Doplnit vazbu', 1, 2)
                    """
                ),
                {"template_id": template_id},
            )
            session.commit()

        _migrate_hazard_library_template_master_catalog()

        with get_session() as session:
            rows = session.execute(
                text(
                    """
                    SELECT id, template_id, name
                    FROM hazard_library_template_events
                    ORDER BY id
                    """
                )
            ).fetchall()
        self.assertEqual(
            rows,
            [
                (1, template_id, "Již převedená"),
                (2, template_id, "Doplnit vazbu"),
            ],
        )

    def test_preserves_assessments_and_measures(self) -> None:
        template = hazard_library_template_service.create_template(name="Zdroj s obsahem")
        self._create_legacy_single_item_schema(template_id=template.id, item_id=12)
        group = ensure_exposed_group("Zaměstnanci")

        _migrate_hazard_library_template_master_catalog()

        event = hazard_library_template_event_service.get_for_template(template.id)[0]
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=group.id,
            severity="moderate",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Doplnit zábradlí",
        )

        _migrate_hazard_library_template_master_catalog()

        reloaded_event = hazard_library_template_event_service.get_by_id(event.id)
        reloaded_assessment = hazard_library_template_assessment_service.get_by_id(assessment.id)
        assert reloaded_event is not None
        assert reloaded_assessment is not None
        self.assertEqual(reloaded_event.template_id, template.id)
        self.assertEqual(reloaded_assessment.template_event_id, event.id)

        existing = hazard_library_template_existing_measure_service.get_for_assessment(assessment.id)
        required = hazard_library_template_required_measure_service.get_for_assessment(assessment.id)
        self.assertEqual(len(existing), 1)
        self.assertEqual(len(required), 1)

    def test_initialize_database_twice_without_error(self) -> None:
        template = hazard_library_template_service.create_template(name="Dvojité spuštění")
        self._create_legacy_single_item_schema(template_id=template.id, item_id=13)

        initialize_database()
        initialize_database()

        self._assert_master_catalog_complete()
        events = hazard_library_template_event_service.get_for_template(template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].template_id, template.id)


if __name__ == "__main__":
    unittest.main()
