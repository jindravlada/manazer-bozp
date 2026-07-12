import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


class LegalRequirementHierarchyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

    def test_migration_adds_parent_requirement_id_column(self) -> None:
        with session_module.engine.connect() as connection:
            columns = {
                column[1]
                for column in connection.execute(
                    text("PRAGMA table_info(legal_requirements)"),
                ).fetchall()
            }
            indexes = {
                index[1]
                for index in connection.execute(
                    text("PRAGMA index_list(legal_requirements)"),
                ).fetchall()
            }

        self.assertIn("parent_requirement_id", columns)
        self.assertIn("ix_legal_requirements_parent_requirement_id", indexes)

    def test_existing_requirements_are_root_processes(self) -> None:
        created = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )

        reloaded = legal_requirement_service.repository.get_by_id(created.id)
        self.assertIsNotNone(reloaded)
        self.assertIsNone(reloaded.parent_requirement_id)

    def test_can_create_child_requirement_with_parent(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = LegalRequirement(
            title="Řízení vyhrazených elektrických zařízení",
            process_code="P-015-CHILD",
            parent_requirement_id=parent.id,
        )
        saved_child = legal_requirement_service.repository.add(child)

        reloaded = legal_requirement_service.repository.get_by_id(saved_child.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.parent_requirement_id, parent.id)

    def test_parent_children_and_child_parent_relationships(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.repository.add(
            LegalRequirement(
                title="Řízení vyhrazených elektrických zařízení",
                process_code="P-015-CHILD",
                parent_requirement_id=parent.id,
            ),
        )

        with get_session() as session:
            loaded_parent = session.scalars(
                select(LegalRequirement)
                .where(LegalRequirement.id == parent.id)
                .options(selectinload(LegalRequirement.children)),
            ).one()
            loaded_child = session.scalars(
                select(LegalRequirement)
                .where(LegalRequirement.id == child.id)
                .options(selectinload(LegalRequirement.parent)),
            ).one()

            self.assertEqual(len(loaded_parent.children), 1)
            self.assertEqual(loaded_parent.children[0].id, child.id)
            self.assertIsNotNone(loaded_child.parent)
            self.assertEqual(loaded_child.parent.id, parent.id)

    def test_list_roots_returns_only_active_root_processes(self) -> None:
        root_a = legal_requirement_service.create_requirement(
            title="Kořen A",
            process_code="P-015",
        )
        root_b = legal_requirement_service.create_requirement(
            title="Kořen B",
            process_code="P-016",
        )
        legal_requirement_service.create_requirement(
            title="Podřízený",
            process_code="P-015.1",
            parent_requirement_id=root_a.id,
        )
        archived_root = legal_requirement_service.create_requirement(
            title="Archivovaný kořen",
            process_code="P-017",
        )
        legal_requirement_service.archive_requirement(archived_root.id)

        roots = legal_requirement_service.list_roots()

        self.assertEqual([item.id for item in roots], [root_a.id, root_b.id])

    def test_list_children_returns_only_active_children_of_parent(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Kořen",
            process_code="P-015",
        )
        child_a = legal_requirement_service.create_requirement(
            title="Elektrická",
            process_code="P-015.1",
            parent_requirement_id=parent.id,
        )
        child_b = legal_requirement_service.create_requirement(
            title="Plynová",
            process_code="P-015.2",
            parent_requirement_id=parent.id,
        )
        archived_child = legal_requirement_service.create_requirement(
            title="Tlaková",
            process_code="P-015.3",
            parent_requirement_id=parent.id,
        )
        legal_requirement_service.archive_requirement(archived_child.id)

        children = legal_requirement_service.list_children(parent.id)

        self.assertEqual([item.id for item in children], [child_a.id, child_b.id])

    def test_cannot_set_parent_to_self(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Kořen",
            process_code="P-015",
        )

        with self.assertRaisesRegex(ValueError, "sám sobě"):
            legal_requirement_service.update_requirement(
                process.id,
                parent_requirement_id=process.id,
            )

    def test_cannot_create_depth_two_hierarchy(self) -> None:
        root = legal_requirement_service.create_requirement(
            title="Kořen",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Podřízený",
            process_code="P-015.1",
            parent_requirement_id=root.id,
        )

        with self.assertRaisesRegex(ValueError, "kořenový proces"):
            legal_requirement_service.create_requirement(
                title="Vnuk",
                process_code="P-016",
                parent_requirement_id=child.id,
            )

    def test_cannot_use_inactive_or_merged_parent(self) -> None:
        inactive_parent = legal_requirement_service.create_requirement(
            title="Neaktivní rodič",
            process_code="P-020",
        )
        legal_requirement_service.archive_requirement(inactive_parent.id)

        with self.assertRaisesRegex(ValueError, "není aktivní"):
            legal_requirement_service.create_requirement(
                title="Dítě neaktivního",
                process_code="P-020.1",
                parent_requirement_id=inactive_parent.id,
            )

        merge_target = legal_requirement_service.create_requirement(
            title="Cíl sloučení",
            process_code="P-021",
        )
        merged_source = legal_requirement_service.create_requirement(
            title="Zdroj sloučení",
            process_code="P-022",
        )
        legal_requirement_service.merge_process_requirements(
            merged_source.id,
            merge_target.id,
        )

        with self.assertRaisesRegex(ValueError, "Sloučený proces"):
            legal_requirement_service.create_requirement(
                title="Dítě sloučeného",
                process_code="P-022.1",
                parent_requirement_id=merged_source.id,
            )

    def test_cannot_archive_root_with_active_children(self) -> None:
        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        with self.assertRaisesRegex(ValueError, "aktivní podřízené procesy"):
            legal_requirement_service.archive_requirement(root.id)

    def test_can_archive_root_after_children_deactivated(self) -> None:
        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-016",
        )
        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )
        legal_requirement_service.archive_requirement(child.id)

        archived_root = legal_requirement_service.archive_requirement(root.id)

        self.assertIsNotNone(archived_root)
        self.assertFalse(archived_root.active)

    def test_cannot_deactivate_root_via_update_with_active_children(self) -> None:
        root = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-017",
        )
        legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=root.id,
        )

        with self.assertRaisesRegex(ValueError, "aktivní podřízené procesy"):
            legal_requirement_service.update_requirement(root.id, active=False)

    def test_first_child_gets_parent_code_suffix_one(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )

        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=parent.id,
        )

        self.assertEqual(child.process_code, "P-015.1")
        self.assertEqual(
            legal_requirement_service.allocate_child_process_code(parent.id),
            "P-015.2",
        )

    def test_second_child_gets_next_child_code(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=parent.id,
        )

        second_child = legal_requirement_service.create_requirement(
            title="Plynová zařízení",
            parent_requirement_id=parent.id,
        )

        self.assertEqual(second_child.process_code, "P-015.2")

    def test_archived_child_does_not_reuse_child_number(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        archived_child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            parent_requirement_id=parent.id,
        )
        legal_requirement_service.archive_requirement(archived_child.id)

        next_child = legal_requirement_service.create_requirement(
            title="Plynová zařízení",
            parent_requirement_id=parent.id,
        )

        self.assertEqual(archived_child.process_code, "P-015.1")
        self.assertEqual(next_child.process_code, "P-015.2")

    def test_child_code_uses_max_existing_child_number(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            process_code="P-015.1",
            parent_requirement_id=parent.id,
        )
        legal_requirement_service.create_requirement(
            title="Tlaková zařízení",
            process_code="P-015.3",
            parent_requirement_id=parent.id,
        )

        next_child = legal_requirement_service.create_requirement(
            title="Zdvihací zařízení",
            parent_requirement_id=parent.id,
        )

        self.assertEqual(next_child.process_code, "P-015.4")

    def test_root_process_code_allocation_unchanged(self) -> None:
        first = legal_requirement_service.create_requirement(title="První kořen")
        second = legal_requirement_service.create_requirement(title="Druhý kořen")

        self.assertEqual(first.process_code, "P-001")
        self.assertEqual(second.process_code, "P-002")

    def test_explicit_child_process_code_is_respected(self) -> None:
        parent = legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )

        child = legal_requirement_service.create_requirement(
            title="Elektrická zařízení",
            process_code="P-015.9",
            parent_requirement_id=parent.id,
        )

        self.assertEqual(child.process_code, "P-015.9")

        with self.assertRaisesRegex(ValueError, "již existuje"):
            legal_requirement_service.create_requirement(
                title="Duplicitní kód",
                process_code="P-015.9",
                parent_requirement_id=parent.id,
            )


if __name__ == "__main__":
    unittest.main()
