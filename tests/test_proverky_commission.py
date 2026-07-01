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
        COMMISSION_DUPLICATE_PERSON_MESSAGE,
        COMMISSION_RECORD_INVITED,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_MEMBER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
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

    def _core_commission_payload(
        self,
        leader_id: int,
        workplace_id: int,
        union_id: int,
    ) -> list[dict]:
        return [
            {
                "record_type": COMMISSION_RECORD_LEADER,
                "thp_worker_id": leader_id,
                "person_id": None,
                "display_name": "Vedoucí",
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_WORKPLACE,
                "thp_worker_id": workplace_id,
                "person_id": None,
                "display_name": "Zástupce pracoviště",
                "display_order": 15,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_UNION,
                "thp_worker_id": None,
                "person_id": union_id,
                "display_name": "Zástupce odborů",
                "display_order": 20,
                "active": True,
            },
        ]

    def test_save_and_reload_full_commission(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        member1_id = self._create_worker("Petr", "Svoboda")
        member2_id = self._create_worker("Marie", "Dvořáková")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        inspection = bozp_inspection_service.create_inspection()
        members = [
            *self._core_commission_payload(leader_id, workplace_id, union_id),
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": member1_id,
                "person_id": None,
                "display_name": "Petr Svoboda",
                "role_text": "Technik",
                "note_text": "BOZP specialista",
                "display_order": 30,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": member2_id,
                "person_id": None,
                "display_name": "Marie Dvořáková",
                "role_text": None,
                "note_text": None,
                "display_order": 40,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_INVITED,
                "thp_worker_id": None,
                "person_id": invited_id,
                "display_name": "Tomáš Malý",
                "role_text": "Revizní technik",
                "note_text": "Externí",
                "display_order": 50,
                "active": True,
            },
        ]

        bozp_inspection_commission_service.save_members(inspection.id, members)
        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)

        self.assertEqual(len(loaded), 6)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_LEADER), 1)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_WORKPLACE), 1)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_MEMBER), 2)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_INVITED), 1)

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

    def _leader_and_members_payload(
        self,
        leader_id: int,
        workplace_id: int,
        union_id: int,
        *,
        member_ids: list[int] | None = None,
    ) -> list[dict]:
        members = self._core_commission_payload(leader_id, workplace_id, union_id)
        for index, member_id in enumerate(member_ids or [], start=1):
            members.append(
                {
                    "record_type": COMMISSION_RECORD_MEMBER,
                    "thp_worker_id": member_id,
                    "person_id": None,
                    "display_name": f"Člen {index}",
                    "display_order": 30 + index * 10,
                    "active": True,
                }
            )
        return members

    def _union_and_invited_payload(
        self,
        union_id: int,
        *,
        invited_ids: list[int] | None = None,
    ) -> list[dict]:
        members = [
            {
                "record_type": COMMISSION_RECORD_UNION,
                "thp_worker_id": None,
                "person_id": union_id,
                "display_name": "Zástupce",
                "display_order": 20,
                "active": True,
            },
        ]
        for index, invited_id in enumerate(invited_ids or [], start=1):
            members.append(
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "thp_worker_id": None,
                    "person_id": invited_id,
                    "display_name": f"Přizvaný {index}",
                    "display_order": index * 10,
                    "active": True,
                }
            )
        return members

    def _assert_rejects_duplicates(self, members: list[dict]) -> None:
        inspection = bozp_inspection_service.create_inspection()
        with self.assertRaises(ValueError) as context:
            bozp_inspection_commission_service.save_members(inspection.id, members)
        self.assertEqual(str(context.exception), COMMISSION_DUPLICATE_PERSON_MESSAGE)

    def test_rejects_leader_as_workplace_rep(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        union_id = self._create_person("Lucie", "Horáková")
        inspection = bozp_inspection_service.create_inspection()

        with self.assertRaises(ValueError) as context:
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
                        "record_type": COMMISSION_RECORD_WORKPLACE,
                        "thp_worker_id": leader_id,
                        "display_name": "Jan Novák",
                        "display_order": 15,
                        "active": True,
                    },
                    {
                        "record_type": COMMISSION_RECORD_UNION,
                        "person_id": union_id,
                        "display_name": "Lucie Horáková",
                        "display_order": 20,
                        "active": True,
                    },
                ],
            )

        self.assertEqual(str(context.exception), COMMISSION_DUPLICATE_PERSON_MESSAGE)

    def test_rejects_leader_as_member(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        self._assert_rejects_duplicates(
            self._leader_and_members_payload(
                leader_id,
                workplace_id,
                union_id,
                member_ids=[leader_id],
            )
        )

    def test_rejects_workplace_as_member(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        self._assert_rejects_duplicates(
            self._leader_and_members_payload(
                leader_id,
                workplace_id,
                union_id,
                member_ids=[workplace_id],
            )
        )

    def test_rejects_union_as_invited(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")

        self._assert_rejects_duplicates(
            [
                *self._core_commission_payload(leader_id, workplace_id, union_id),
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
            ]
        )

    def test_rejects_duplicate_member(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        member_id = self._create_worker("Petr", "Svoboda")
        self._assert_rejects_duplicates(
            self._leader_and_members_payload(
                leader_id,
                workplace_id,
                union_id,
                member_ids=[member_id, member_id],
            )
        )

    def test_rejects_duplicate_invited(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        self._assert_rejects_duplicates(
            [
                *self._core_commission_payload(leader_id, workplace_id, union_id),
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "person_id": invited_id,
                    "display_name": "Tomáš Malý",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "person_id": invited_id,
                    "display_name": "Tomáš Malý",
                    "display_order": 40,
                    "active": True,
                },
            ]
        )

    def test_allows_different_persons(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        member_id = self._create_worker("Petr", "Svoboda")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        inspection = bozp_inspection_service.create_inspection()
        members = [
            *self._leader_and_members_payload(
                leader_id,
                workplace_id,
                union_id,
                member_ids=[member_id],
            ),
            {
                "record_type": COMMISSION_RECORD_INVITED,
                "person_id": invited_id,
                "display_name": "Tomáš Malý",
                "display_order": 50,
                "active": True,
            },
        ]

        bozp_inspection_commission_service.save_members(inspection.id, members)
        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)

        self.assertEqual(len(loaded), 5)

    def test_remove_member_persists(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        member_id = self._create_worker("Petr", "Svoboda")

        inspection = bozp_inspection_service.create_inspection()
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                *self._core_commission_payload(leader_id, workplace_id, union_id),
                {
                    "record_type": COMMISSION_RECORD_MEMBER,
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "display_order": 30,
                    "active": True,
                },
            ],
        )

        bozp_inspection_commission_service.save_members(
            inspection.id,
            self._core_commission_payload(leader_id, workplace_id, union_id),
        )

        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)
        self.assertEqual(len(loaded), 3)
        self.assertEqual(
            {item.record_type for item in loaded},
            {
                COMMISSION_RECORD_LEADER,
                COMMISSION_RECORD_WORKPLACE,
                COMMISSION_RECORD_UNION,
            },
        )

    def test_rejects_two_leaders(self) -> None:
        leader1 = self._create_worker("Jan", "Novák")
        leader2 = self._create_worker("Petr", "Svoboda")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
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
                    {
                        "record_type": COMMISSION_RECORD_WORKPLACE,
                        "thp_worker_id": workplace_id,
                        "display_name": "Eva Králová",
                        "display_order": 15,
                        "active": True,
                    },
                    {
                        "record_type": COMMISSION_RECORD_UNION,
                        "person_id": union_id,
                        "display_name": "Lucie Horáková",
                        "display_order": 20,
                        "active": True,
                    },
                ],
            )

    def test_rejects_missing_workplace(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        union_id = self._create_person("Lucie", "Horáková")
        inspection = bozp_inspection_service.create_inspection()

        with self.assertRaises(ValueError) as context:
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
                        "record_type": COMMISSION_RECORD_UNION,
                        "person_id": union_id,
                        "display_name": "Lucie Horáková",
                        "display_order": 20,
                        "active": True,
                    },
                ],
            )
        self.assertIn("zástupce pracoviště", str(context.exception).lower())

    def test_rejects_missing_union(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        inspection = bozp_inspection_service.create_inspection()

        with self.assertRaises(ValueError) as context:
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
                        "record_type": COMMISSION_RECORD_WORKPLACE,
                        "thp_worker_id": workplace_id,
                        "display_name": "Eva Králová",
                        "display_order": 15,
                        "active": True,
                    },
                ],
            )
        self.assertIn("odborové organizace", str(context.exception).lower())


if __name__ == "__main__":
    unittest.main()
