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

    from moduly.tymy.serializace import team_detail_to_dict, teams_to_json
    from moduly.tymy.sluzby.team_catalog_service import team_catalog_service
    from moduly.tymy.sluzby.team_service import team_service
    from moduly.tymy.testovaci_data import seed_demo_teams


class TeamModuleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        team_catalog_service.reload()

    def setUp(self) -> None:
        for team in team_service.get_all_teams():
            team_service.delete_team(team.id)

    def test_catalogs_contain_defaults(self) -> None:
        types = team_catalog_service.get_team_types()
        roles = team_catalog_service.get_team_roles()

        self.assertGreaterEqual(len(types), 4)
        self.assertGreaterEqual(len(roles), 5)
        self.assertIsNotNone(team_catalog_service.get_team_type_by_id("proverkova_komise"))
        self.assertIsNotNone(team_catalog_service.get_team_role_by_id("vedouci_tymu"))

    def test_create_team_with_multiple_members_and_roles(self) -> None:
        team_ids = seed_demo_teams()
        self.assertEqual(len(team_ids), 2)

        detail = team_service.get_team_detail(team_ids[0])
        assert detail is not None

        self.assertEqual(detail.team.name, "Výrobní prověrková komise")
        self.assertEqual(detail.team.team_type_id, "proverkova_komise")
        self.assertEqual(len(detail.members), 4)

        role_ids = {member.role_id for member in detail.members}
        self.assertIn("vedouci_tymu", role_ids)
        self.assertIn("clen", role_ids)
        self.assertIn("prizvany_odbornik", role_ids)

        mandatory = [member for member in detail.members if member.mandatory]
        self.assertEqual(len(mandatory), 2)

        investigation = team_service.get_team_detail(team_ids[1])
        assert investigation is not None
        self.assertEqual(investigation.team.team_type_id, "vysetrovaci_tym")
        self.assertEqual(len(investigation.members), 4)

    def test_serialization_roundtrip_fields(self) -> None:
        team_ids = seed_demo_teams()
        details = [
            detail
            for team_id in team_ids
            if (detail := team_service.get_team_detail(team_id)) is not None
        ]

        payload = teams_to_json(details)
        self.assertIn("Výrobní prověrková komise", payload)
        self.assertIn("Vyšetřovací tým PÚ", payload)

        first = team_detail_to_dict(details[0])
        self.assertEqual(first["team_type_id"], "proverkova_komise")
        self.assertEqual(len(first["members"]), 4)
        self.assertTrue(all(member["person_name"] for member in first["members"]))

    def test_delete_team_removes_members(self) -> None:
        team_ids = seed_demo_teams()
        team_id = team_ids[0]

        self.assertTrue(team_service.delete_team(team_id))
        self.assertIsNone(team_service.get_team_detail(team_id))


if __name__ == "__main__":
    unittest.main()
