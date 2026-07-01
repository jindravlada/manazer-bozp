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

    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.tymy.sluzby.team_catalog_service import team_catalog_service
    from moduly.tymy.sluzby.team_service import INSPECTION_TEAM_TYPE_ID, team_service
    from moduly.tymy.testovaci_data import seed_demo_teams


class ProverkyTeamSelectionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        team_catalog_service.reload()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

        for team in team_service.get_all_teams():
            team_service.delete_team(team.id)

    def test_save_and_reload_team_id(self) -> None:
        team_ids = seed_demo_teams()
        team_id = team_ids[0]

        inspection = bozp_inspection_service.create_inspection(team_id=team_id)
        loaded = bozp_inspection_service.get_by_id(inspection.id)

        assert loaded is not None
        self.assertEqual(loaded.team_id, team_id)

        detail = team_service.get_team_detail(team_id)
        assert detail is not None
        self.assertEqual(len(detail.members), 4)

    def test_active_inspection_teams_exclude_inactive(self) -> None:
        team_ids = seed_demo_teams()
        active_team_id = team_ids[0]

        team_service.update_team(active_team_id, active=False)

        selectable = team_service.get_teams_for_selection(
            team_type_id=INSPECTION_TEAM_TYPE_ID,
        )
        self.assertEqual(selectable, [])

        selectable_with_saved = team_service.get_teams_for_selection(
            team_type_id=INSPECTION_TEAM_TYPE_ID,
            include_team_id=active_team_id,
        )
        self.assertEqual(len(selectable_with_saved), 1)
        self.assertEqual(selectable_with_saved[0].id, active_team_id)
        self.assertFalse(selectable_with_saved[0].active)

    def test_rejects_non_inspection_team_type(self) -> None:
        investigation_team = team_service.create_team(
            name="Vyšetřovací tým test",
            team_type_id="vysetrovaci_tym",
        )

        with self.assertRaises(ValueError):
            bozp_inspection_service.create_inspection(team_id=investigation_team.id)


if __name__ == "__main__":
    unittest.main()
