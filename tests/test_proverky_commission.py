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

    from moduly.proverky.constants import (
        COMMISSION_DEFAULT_ROLE_INVITED,
        COMMISSION_DEFAULT_ROLE_MEMBER,
        COMMISSION_RECORD_INVITED,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_MEMBER,
        COMMISSION_RECORD_UNION,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class ProverkyCommissionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_worker(self, first_name: str, last_name: str) -> int:
        worker = settings_service.save_worker(first_name=first_name, last_name=last_name)
        return worker.id

    def _create_person(self, first_name: str, last_name: str) -> int:
        person = person_service.create_person(first_name=first_name, last_name=last_name)
        return person.id

    def test_save_and_reload_full_commission(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        member1_id = self._create_worker("Petr", "Svoboda")
        member2_id = self._create_worker("Marie", "Dvořáková")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        inspection = bozp_inspection_service.create_inspection()
        members = [
            {
                "record_type": COMMISSION_RECORD_LEADER,
                "thp_worker_id": leader_id,
                "person_id": None,
                "display_name": "Jan Novák",
                "role_text": None,
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_UNION,
                "thp_worker_id": None,
                "person_id": union_id,
                "display_name": "Lucie Horáková",
                "role_text": None,
                "display_order": 20,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": member1_id,
                "person_id": None,
                "display_name": "Petr Svoboda",
                "role_text": "Technik",
                "note_text": "BOZP specialista",
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": member2_id,
                "person_id": None,
                "display_name": "Marie Dvořáková",
                "role_text": None,
                "note_text": None,
                "display_order": 20,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_INVITED,
                "thp_worker_id": None,
                "person_id": invited_id,
                "display_name": "Tomáš Malý",
                "role_text": "Revizní technik",
                "note_text": "Externí",
                "display_order": 10,
                "active": True,
            },
        ]

        bozp_inspection_commission_service.save_members(inspection.id, members)
        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)

        self.assertEqual(len(loaded), 5)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_LEADER), 1)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_MEMBER), 2)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_INVITED), 1)
        self.assertEqual(loaded[0].display_name, "Jan Novák")

        member_records = [
            item for item in loaded if item.record_type == COMMISSION_RECORD_MEMBER
        ]
        self.assertEqual(member_records[0].role_text, "Technik")
        self.assertEqual(member_records[0].note_text, "BOZP specialista")

        invited_records = [
            item for item in loaded if item.record_type == COMMISSION_RECORD_INVITED
        ]
        self.assertEqual(invited_records[0].role_text, "Revizní technik")
        self.assertEqual(invited_records[0].note_text, "Externí")

    def test_allows_same_person_in_multiple_roles(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        union_id = self._create_person("Lucie", "Horáková")

        inspection = bozp_inspection_service.create_inspection()
        members = [
            {
                "record_type": COMMISSION_RECORD_LEADER,
                "thp_worker_id": leader_id,
                "person_id": None,
                "display_name": "Jan Novák",
                "role_text": None,
                "note_text": None,
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": leader_id,
                "person_id": None,
                "display_name": "Jan Novák",
                "role_text": COMMISSION_DEFAULT_ROLE_MEMBER,
                "note_text": "První výskyt",
                "display_order": 20,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": leader_id,
                "person_id": None,
                "display_name": "Jan Novák",
                "role_text": "Zapisovatel",
                "note_text": "Druhý výskyt",
                "display_order": 30,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_UNION,
                "thp_worker_id": None,
                "person_id": union_id,
                "display_name": "Lucie Horáková",
                "role_text": None,
                "note_text": None,
                "display_order": 40,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_INVITED,
                "thp_worker_id": None,
                "person_id": union_id,
                "display_name": "Lucie Horáková",
                "role_text": COMMISSION_DEFAULT_ROLE_INVITED,
                "note_text": "Pozvánka",
                "display_order": 50,
                "active": True,
            },
        ]

        bozp_inspection_commission_service.save_members(inspection.id, members)
        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)

        self.assertEqual(len(loaded), 5)
        leader_members = [
            item
            for item in loaded
            if item.record_type == COMMISSION_RECORD_MEMBER and item.thp_worker_id == leader_id
        ]
        self.assertEqual(len(leader_members), 2)
        self.assertEqual(leader_members[0].note_text, "První výskyt")
        self.assertEqual(leader_members[1].role_text, "Zapisovatel")
        self.assertEqual(leader_members[1].note_text, "Druhý výskyt")

        invited = [
            item for item in loaded if item.record_type == COMMISSION_RECORD_INVITED
        ]
        self.assertEqual(len(invited), 1)
        self.assertEqual(invited[0].person_id, union_id)
        self.assertEqual(invited[0].role_text, COMMISSION_DEFAULT_ROLE_INVITED)
        self.assertEqual(invited[0].note_text, "Pozvánka")

    def test_remove_member_persists(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        member_id = self._create_worker("Petr", "Svoboda")

        inspection = bozp_inspection_service.create_inspection()
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_MEMBER,
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "display_order": 10,
                    "active": True,
                },
            ],
        )

        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
            ],
        )

        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].record_type, COMMISSION_RECORD_LEADER)

    def test_rejects_two_leaders(self) -> None:
        leader1 = self._create_worker("Jan", "Novák")
        leader2 = self._create_worker("Petr", "Svoboda")
        inspection = bozp_inspection_service.create_inspection()

        with self.assertRaises(ValueError):
            bozp_inspection_commission_service.save_members(
                inspection.id,
                [
                    {
                        "record_type": COMMISSION_RECORD_LEADER,
                        "thp_worker_id": leader1,
                        "display_name": "Jan Novák",
                        "display_order": 10,
                        "active": True,
                    },
                    {
                        "record_type": COMMISSION_RECORD_LEADER,
                        "thp_worker_id": leader2,
                        "display_name": "Petr Svoboda",
                        "display_order": 20,
                        "active": True,
                    },
                ],
            )


if __name__ == "__main__":
    unittest.main()
