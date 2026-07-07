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

    from core.shared.constants import (
        ENTITY_AUDIT,
        ENTITY_LEGAL_REQUIREMENT,
        ENTITY_RISK,
        ENTITY_TASK,
        LINK_EVIDENCE,
        LINK_RELATED,
    )
    from core.shared.sluzby.entity_link_service import entity_link_service


class EntityLinkServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.shared.modely.entity_link import EntityLink

        with get_session() as session:
            session.execute(delete(EntityLink))
            session.commit()

    def _create_requirement_link(self, requirement_id: int = 1, **kwargs):
        defaults = {
            "source_type": ENTITY_LEGAL_REQUIREMENT,
            "source_id": requirement_id,
            "target_type": ENTITY_RISK,
            "target_id": 10,
            "link_type": LINK_RELATED,
            "note": "Testovací vazba",
        }
        defaults.update(kwargs)
        return entity_link_service.create(**defaults)

    def test_create_link(self) -> None:
        link = self._create_requirement_link()

        self.assertIsNotNone(link.id)
        self.assertEqual(link.source_type, ENTITY_LEGAL_REQUIREMENT)
        self.assertEqual(link.target_type, ENTITY_RISK)
        self.assertEqual(link.link_type, LINK_RELATED)

    def test_prevent_duplicate_active_link(self) -> None:
        self._create_requirement_link()
        with self.assertRaises(ValueError):
            self._create_requirement_link()

    def test_list_for_source(self) -> None:
        first = self._create_requirement_link(target_id=11)
        second = self._create_requirement_link(target_id=12, link_type=LINK_EVIDENCE)

        links = entity_link_service.list_for_source(ENTITY_LEGAL_REQUIREMENT, 1)
        self.assertEqual(len(links), 2)
        self.assertEqual({item.id for item in links}, {first.id, second.id})

    def test_list_for_target(self) -> None:
        link = self._create_requirement_link(target_type=ENTITY_TASK, target_id=42)

        links = entity_link_service.list_for_target(ENTITY_TASK, 42)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].id, link.id)

    def test_deactivate_and_restore_link(self) -> None:
        link = self._create_requirement_link()

        deactivated = entity_link_service.deactivate(link.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_links = entity_link_service.list_for_source(ENTITY_LEGAL_REQUIREMENT, 1)
        self.assertEqual(active_links, [])

        restored = entity_link_service.restore(link.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_cannot_link_object_to_itself(self) -> None:
        with self.assertRaises(ValueError):
            entity_link_service.create(
                source_type=ENTITY_LEGAL_REQUIREMENT,
                source_id=5,
                target_type=ENTITY_LEGAL_REQUIREMENT,
                target_id=5,
            )

    def test_reverse_link_is_not_duplicate(self) -> None:
        self._create_requirement_link(
            source_type=ENTITY_LEGAL_REQUIREMENT,
            source_id=1,
            target_type=ENTITY_AUDIT,
            target_id=7,
        )
        reverse = entity_link_service.create(
            source_type=ENTITY_AUDIT,
            source_id=7,
            target_type=ENTITY_LEGAL_REQUIREMENT,
            target_id=1,
        )
        self.assertIsNotNone(reverse.id)


if __name__ == "__main__":
    unittest.main()
