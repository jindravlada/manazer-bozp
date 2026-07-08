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


if __name__ == "__main__":
    unittest.main()
