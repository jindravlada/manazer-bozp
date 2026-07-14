"""Fáze R00 – hierarchický číselník provozů a pracovišť."""

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

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.sluzby.workplace_hierarchy_service import (
        WorkplaceHierarchyError,
        sort_workplaces_for_tree,
        validate_workplace_hierarchy,
        would_create_cycle,
    )


class WorkplaceHierarchyPhaseR00TestCase(unittest.TestCase):
    def setUp(self) -> None:
        for workplace in list(settings_service.get_workplaces(include_inactive=True)):
            settings_service.deactivate_workplace(workplace.id)

    def test_migration_sets_existing_items_as_operation(self) -> None:
        legacy = settings_service.save_workplace(name="Původní provoz")
        reloaded = settings_service.get_workplace_by_id(legacy.id)
        assert reloaded is not None
        self.assertEqual(reloaded.item_type, WORKPLACE_ITEM_TYPE_OPERATION)
        self.assertIsNone(reloaded.parent_id)

    def test_create_operation(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz vlečky",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
            active=True,
        )
        self.assertEqual(operation.item_type, WORKPLACE_ITEM_TYPE_OPERATION)
        self.assertIsNone(operation.parent_id)

    def test_create_workplace_under_operation(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz vlečky",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.assertEqual(workplace.parent_id, operation.id)
        self.assertEqual(workplace.item_type, WORKPLACE_ITEM_TYPE_WORKPLACE)

    def test_create_workplace_part_under_workplace(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz vlečky",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        part = settings_service.save_workplace(
            name="Výhybkové zhlaví",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=workplace.id,
        )
        self.assertEqual(part.parent_id, workplace.id)
        self.assertEqual(part.item_type, WORKPLACE_ITEM_TYPE_WORKPLACE_PART)

    def test_reject_invalid_hierarchy(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        with self.assertRaises(WorkplaceHierarchyError):
            settings_service.save_workplace(
                name="Neplatná část",
                item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
                parent_id=operation.id,
            )

        with self.assertRaises(WorkplaceHierarchyError):
            settings_service.save_workplace(
                name="Provoz bez rodiče",
                item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            )

        with self.assertRaises(WorkplaceHierarchyError):
            settings_service.save_workplace(
                name="Provoz s rodičem",
                item_type=WORKPLACE_ITEM_TYPE_OPERATION,
                parent_id=operation.id,
            )

    def test_reject_cycle(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        workplaces = settings_service.repository.get_workplaces(include_inactive=True)
        self.assertTrue(
            would_create_cycle(
                workplaces,
                workplace_id=operation.id,
                parent_id=workplace.id,
            )
        )
        with self.assertRaises(WorkplaceHierarchyError):
            settings_service.save_workplace(
                id=operation.id,
                name="Provoz A",
                item_type=WORKPLACE_ITEM_TYPE_OPERATION,
                parent_id=workplace.id,
            )

    def test_preserve_existing_id_on_update(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz původní",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        original_id = operation.id
        updated = settings_service.save_workplace(
            id=original_id,
            name="Provoz aktualizovaný",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
            note="Poznámka",
        )
        self.assertEqual(updated.id, original_id)

    def test_alphabetical_sorting_within_level(self) -> None:
        operation_b = settings_service.save_workplace(
            name="Provoz B",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        operation_a = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        settings_service.save_workplace(
            name="Zóna",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation_a.id,
        )
        settings_service.save_workplace(
            name="Areál",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation_a.id,
        )

        workplaces = settings_service.get_workplaces(include_inactive=True)
        root_names = [
            workplace.name
            for workplace in workplaces
            if workplace.parent_id is None
        ]
        self.assertEqual(root_names, ["Provoz A", "Provoz B"])

        children = [
            workplace.name
            for workplace in workplaces
            if workplace.parent_id == operation_a.id
        ]
        self.assertEqual(children, ["Areál", "Zóna"])

        ordered = sort_workplaces_for_tree(workplaces)
        self.assertEqual(
            [item.name for item in ordered[:4]],
            ["Provoz A", "Areál", "Zóna", "Provoz B"],
        )

    def test_deactivate_workplace(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.assertTrue(settings_service.deactivate_workplace(operation.id))
        reloaded = settings_service.get_workplace_by_id(operation.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)

        active = settings_service.get_workplaces(include_inactive=False)
        self.assertNotIn(operation.id, [item.id for item in active])

    def test_validate_rejects_self_parent(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplaces = settings_service.repository.get_workplaces(include_inactive=True)
        with self.assertRaises(WorkplaceHierarchyError):
            validate_workplace_hierarchy(
                workplaces,
                workplace_id=operation.id,
                item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
                parent_id=operation.id,
            )


if __name__ == "__main__":
    unittest.main()
