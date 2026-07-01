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

    from moduly.audity.constants import (
        COMMISSION_DUPLICATE_PERSON_MESSAGE,
        COMMISSION_RECORD_INVITED,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_MEMBER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        COMMISSION_REQUIRES_LEADER_MESSAGE,
        COMMISSION_REQUIRES_UNION_MESSAGE,
        COMMISSION_REQUIRES_WORKPLACE_MESSAGE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AudityCommissionTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_worker(self, first_name: str, last_name: str) -> int:
        worker = settings_service.save_worker(first_name=first_name, last_name=last_name)
        return worker.id

    def _create_person(self, first_name: str, last_name: str) -> int:
        person = person_service.create_person(first_name=first_name, last_name=last_name)
        return person.id

    def _core_team_payload(
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
                "display_name": "Vedoucí auditor",
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_WORKPLACE,
                "thp_worker_id": workplace_id,
                "person_id": None,
                "display_name": "Zástupce auditovaného provozu",
                "display_order": 15,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_UNION,
                "thp_worker_id": None,
                "person_id": union_id,
                "display_name": "Zástupce odborové organizace",
                "display_order": 20,
                "active": True,
            },
        ]

    def _leader_and_auditors_payload(
        self,
        leader_id: int,
        workplace_id: int,
        union_id: int,
        *,
        auditor_ids: list[int] | None = None,
    ) -> list[dict]:
        members = self._core_team_payload(leader_id, workplace_id, union_id)
        for index, auditor_id in enumerate(auditor_ids or [], start=1):
            members.append(
                {
                    "record_type": COMMISSION_RECORD_MEMBER,
                    "thp_worker_id": auditor_id,
                    "person_id": None,
                    "display_name": f"Auditor {index}",
                    "display_order": 30 + index * 10,
                    "active": True,
                }
            )
        return members

    def _assert_rejects_duplicates(self, members: list[dict]) -> None:
        audit = audit_service.create_audit()
        with self.assertRaises(ValueError) as context:
            audit_commission_service.save_members(audit.id, members)
        self.assertEqual(str(context.exception), COMMISSION_DUPLICATE_PERSON_MESSAGE)

    def test_save_and_reload_full_team(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        auditor1_id = self._create_worker("Petr", "Svoboda")
        auditor2_id = self._create_worker("Marie", "Dvořáková")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        audit = audit_service.create_audit()
        members = [
            *self._core_team_payload(leader_id, workplace_id, union_id),
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": auditor1_id,
                "person_id": None,
                "display_name": "Petr Svoboda",
                "role_text": "Interní auditor",
                "note_text": "Kvalita",
                "display_order": 30,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_MEMBER,
                "thp_worker_id": auditor2_id,
                "person_id": None,
                "display_name": "Marie Dvořáková",
                "display_order": 40,
                "active": True,
            },
            {
                "record_type": COMMISSION_RECORD_INVITED,
                "thp_worker_id": None,
                "person_id": invited_id,
                "display_name": "Tomáš Malý",
                "role_text": "Externí odborník",
                "display_order": 50,
                "active": True,
            },
        ]

        audit_commission_service.save_members(audit.id, members)
        loaded = audit_commission_service.get_for_audit(audit.id)

        self.assertEqual(len(loaded), 6)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_LEADER), 1)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_WORKPLACE), 1)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_MEMBER), 2)
        self.assertEqual(sum(1 for item in loaded if item.record_type == COMMISSION_RECORD_INVITED), 1)

    def test_rejects_missing_leader(self) -> None:
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        audit = audit_service.create_audit()

        with self.assertRaises(ValueError) as context:
            audit_commission_service.save_members(
                audit.id,
                [
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

        self.assertEqual(str(context.exception), COMMISSION_REQUIRES_LEADER_MESSAGE)

    def test_rejects_missing_workplace(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        union_id = self._create_person("Lucie", "Horáková")
        audit = audit_service.create_audit()

        with self.assertRaises(ValueError) as context:
            audit_commission_service.save_members(
                audit.id,
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

        self.assertEqual(str(context.exception), COMMISSION_REQUIRES_WORKPLACE_MESSAGE)

    def test_rejects_missing_union(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        audit = audit_service.create_audit()

        with self.assertRaises(ValueError) as context:
            audit_commission_service.save_members(
                audit.id,
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

        self.assertEqual(str(context.exception), COMMISSION_REQUIRES_UNION_MESSAGE)

    def test_rejects_leader_as_workplace_rep(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        union_id = self._create_person("Lucie", "Horáková")
        audit = audit_service.create_audit()

        with self.assertRaises(ValueError) as context:
            audit_commission_service.save_members(
                audit.id,
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

    def test_rejects_leader_as_auditor(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        self._assert_rejects_duplicates(
            self._leader_and_auditors_payload(
                leader_id,
                workplace_id,
                union_id,
                auditor_ids=[leader_id],
            )
        )

    def test_rejects_workplace_as_auditor(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        self._assert_rejects_duplicates(
            self._leader_and_auditors_payload(
                leader_id,
                workplace_id,
                union_id,
                auditor_ids=[workplace_id],
            )
        )

    def test_rejects_duplicate_auditor(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        auditor_id = self._create_worker("Petr", "Svoboda")
        self._assert_rejects_duplicates(
            self._leader_and_auditors_payload(
                leader_id,
                workplace_id,
                union_id,
                auditor_ids=[auditor_id, auditor_id],
            )
        )

    def test_rejects_union_as_invited(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")

        self._assert_rejects_duplicates(
            [
                *self._core_team_payload(leader_id, workplace_id, union_id),
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
            ]
        )

    def test_rejects_duplicate_invited(self) -> None:
        leader_id = self._create_worker("Jan", "Novák")
        workplace_id = self._create_worker("Eva", "Králová")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        self._assert_rejects_duplicates(
            [
                *self._core_team_payload(leader_id, workplace_id, union_id),
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
        auditor_id = self._create_worker("Petr", "Svoboda")
        union_id = self._create_person("Lucie", "Horáková")
        invited_id = self._create_person("Tomáš", "Malý")

        audit = audit_service.create_audit()
        members = [
            *self._leader_and_auditors_payload(
                leader_id,
                workplace_id,
                union_id,
                auditor_ids=[auditor_id],
            ),
            {
                "record_type": COMMISSION_RECORD_INVITED,
                "person_id": invited_id,
                "display_name": "Tomáš Malý",
                "display_order": 50,
                "active": True,
            },
        ]

        audit_commission_service.save_members(audit.id, members)
        loaded = audit_commission_service.get_for_audit(audit.id)

        self.assertEqual(len(loaded), 5)


if __name__ == "__main__":
    unittest.main()
