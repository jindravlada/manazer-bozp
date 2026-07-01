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

    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.tymy.sluzby.team_catalog_service import team_catalog_service
    from moduly.tymy.sluzby.team_service import team_service
    from moduly.tymy.testovaci_data import seed_demo_teams


class ProverkyCommissionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        team_catalog_service.reload()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

        for team in team_service.get_all_teams():
            team_service.delete_team(team.id)

    def test_commission_copy_and_participation_persist(self) -> None:
        team_id = seed_demo_teams()[0]
        template = bozp_inspection_commission_service.members_from_team(team_id)
        self.assertEqual(len(template), 4)

        inspection = bozp_inspection_service.create_inspection(team_id=team_id)
        members = [dict(item) for item in template]
        members[1]["participated"] = False
        members.append(
            {
                "team_member_id": None,
                "thp_worker_id": None,
                "person_id": None,
                "person_name": "Externí revizní technik",
                "role_id": "prizvany_odbornik",
                "role_name": "Přizvaný odborník",
                "mandatory": False,
                "participated": True,
                "ad_hoc": True,
                "display_order": 100,
            }
        )

        bozp_inspection_commission_service.save_members(inspection.id, members)

        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)
        self.assertEqual(len(loaded), 5)
        self.assertFalse(loaded[1].participated)
        self.assertTrue(loaded[-1].ad_hoc)

        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        assert reloaded is not None
        self.assertEqual(reloaded.team_id, team_id)

    def test_team_template_change_does_not_alter_saved_commission(self) -> None:
        team_id = seed_demo_teams()[0]
        inspection = bozp_inspection_service.create_inspection(team_id=team_id)

        members = bozp_inspection_commission_service.members_from_team(team_id)
        members[0]["person_name"] = "Historický vedoucí komise"
        bozp_inspection_commission_service.save_members(inspection.id, members)

        detail = team_service.get_team_detail(team_id)
        assert detail is not None
        team_service.update_member(
            detail.members[0].id,
            person_name="Nový vedoucí v nastavení",
        )

        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)
        self.assertEqual(loaded[0].person_name, "Historický vedoucí komise")

    def test_reload_template_keeps_ad_hoc_members(self) -> None:
        team_ids = seed_demo_teams()
        first_team_id = team_ids[0]
        second_team_id = team_ids[1]

        current = bozp_inspection_commission_service.members_from_team(first_team_id)
        current.append(
            {
                "team_member_id": None,
                "person_name": "Přizvaný host",
                "role_id": "prizvany_odbornik",
                "role_name": "Přizvaný odborník",
                "mandatory": False,
                "participated": True,
                "ad_hoc": True,
                "display_order": 100,
            }
        )

        merged = bozp_inspection_commission_service.merge_team_template(
            current,
            second_team_id,
            keep_ad_hoc=True,
        )

        self.assertEqual(len(merged), 5)
        self.assertTrue(any(member.get("ad_hoc") for member in merged))
        self.assertTrue(all(not member.get("ad_hoc") for member in merged[:4]))


if __name__ == "__main__":
    unittest.main()
