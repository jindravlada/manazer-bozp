"""Fáze COORD-008 – činnosti zúčastněných zaměstnavatelů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-008-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import TAB_EMPLOYER_ACTIVITIES
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
        CoordinationEmployerActivityError,
        coordination_employer_activity_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord008TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )
        self.operation = settings_service.save_workplace(
            name="COORD008 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="COORD008 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.today = date.today()

    def _create_coordination(self):
        return bozp_coordination_service.create_coordination(
            subject="COORD-008",
            meeting_date=self.today,
        )

    def _create_participant(self, coordination_id: int):
        return coordination_employer_service.add_participant(
            coordination_id,
            company_name="Dodavatel s.r.o.",
            abbreviation="DOD",
        )

    def _create_place(self, coordination_id: int):
        return coordination_workplace_service.add(
            coordination_id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def _get_main(self, coordination_id: int):
        return coordination_employer_service.ensure_main_employer(coordination_id)

    def test_model_table(self) -> None:
        columns = _table_columns("coordination_employer_activities")
        for name in (
            "id",
            "coordination_employer_id",
            "coordination_workplace_id",
            "activity_name",
            "description",
            "planned_from",
            "planned_to",
            "note",
            "active",
            "sort_order",
        ):
            self.assertIn(name, columns)

    def test_add_activity(self) -> None:
        coordination = self._create_coordination()
        main = self._get_main(coordination.id)
        self.assertIsNotNone(main)
        activity = coordination_employer_activity_service.add(
            main.id,
            activity_name="Údržba VZT",
            description="Servis vzduchotechniky",
            planned_from=self.today,
            planned_to=self.today + timedelta(days=5),
            note="denní směna",
        )
        self.assertEqual(activity.activity_name, "Údržba VZT")
        self.assertTrue(activity.active)
        self.assertEqual(activity.coordination_employer_id, main.id)
        self.assertIsNone(activity.coordination_workplace_id)

    def test_multiple_activities_one_employer(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        first = coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Svařování",
        )
        second = coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Montáž lešení",
        )
        items = coordination_employer_activity_service.list_for_employer(contractor.id)
        self.assertEqual(len(items), 2)
        names = {item.activity_name for item in items}
        self.assertEqual(names, {"Svařování", "Montáž lešení"})
        self.assertNotEqual(first.id, second.id)

    def test_activity_linked_to_workplace(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        place = self._create_place(coordination.id)
        activity = coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Zemní práce",
            coordination_workplace_id=place.id,
        )
        self.assertEqual(activity.coordination_workplace_id, place.id)
        label = coordination_employer_activity_service.workplace_label(place.id)
        self.assertIn("COORD008", label)

    def test_duplicate_rejected(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        place = self._create_place(coordination.id)
        coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Betonáž",
            coordination_workplace_id=place.id,
        )
        with self.assertRaises(CoordinationEmployerActivityError):
            coordination_employer_activity_service.add(
                contractor.id,
                activity_name="  betonáž  ",
                coordination_workplace_id=place.id,
            )
        # stejný název na jiném místě (bez místa) je povolen
        other = coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Betonáž",
            coordination_workplace_id=None,
        )
        self.assertIsNone(other.coordination_workplace_id)

    def test_reject_inactive_workplace(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        place = self._create_place(coordination.id)
        coordination_workplace_service.deactivate(place.id)
        with self.assertRaises(CoordinationEmployerActivityError) as ctx:
            coordination_employer_activity_service.add(
                contractor.id,
                activity_name="Práce na místě",
                coordination_workplace_id=place.id,
            )
        self.assertIn("deaktivované místo", str(ctx.exception).casefold())

    def test_reject_inactive_employer(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        coordination_employer_service.deactivate(contractor.id)
        with self.assertRaises(CoordinationEmployerActivityError) as ctx:
            coordination_employer_activity_service.add(
                contractor.id,
                activity_name="Jakákoli činnost",
            )
        self.assertIn("deaktivovaného zaměstnavatele", str(ctx.exception).casefold())

    def test_period_validation(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        with self.assertRaises(CoordinationEmployerActivityError) as ctx:
            coordination_employer_activity_service.add(
                contractor.id,
                activity_name="Termín",
                planned_from=self.today + timedelta(days=10),
                planned_to=self.today,
            )
        self.assertIn("do", str(ctx.exception).casefold())

        with self.assertRaises(CoordinationEmployerActivityError):
            coordination_employer_activity_service.add(
                contractor.id,
                activity_name="",
            )

    def test_deactivate_and_reactivate(self) -> None:
        coordination = self._create_coordination()
        contractor = self._create_participant(coordination.id)
        activity = coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Revize elektro",
        )
        self.assertTrue(
            coordination_employer_activity_service.deactivate(activity.id)
        )
        reloaded = coordination_employer_activity_service.get_by_id(activity.id)
        self.assertFalse(reloaded.active)
        self.assertTrue(coordination_employer_activity_service.activate(activity.id))
        reloaded = coordination_employer_activity_service.get_by_id(activity.id)
        self.assertTrue(reloaded.active)

    def test_filter_by_employer(self) -> None:
        coordination = self._create_coordination()
        main = self._get_main(coordination.id)
        contractor = self._create_participant(coordination.id)
        coordination_employer_activity_service.add(
            main.id,
            activity_name="Činnost hlavního",
        )
        coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Činnost dodavatele",
        )
        main_items = coordination_employer_activity_service.list_for_employer(main.id)
        contractor_items = coordination_employer_activity_service.list_for_employer(
            contractor.id
        )
        self.assertEqual([item.activity_name for item in main_items], ["Činnost hlavního"])
        self.assertEqual(
            [item.activity_name for item in contractor_items],
            ["Činnost dodavatele"],
        )

    def test_ui_tab_present(self) -> None:
        coordination = self._create_coordination()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_EMPLOYER_ACTIVITIES, labels)
        self.assertFalse(dialog.employer_activities_tab.content.isHidden())


if __name__ == "__main__":
    unittest.main()
