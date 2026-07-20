"""UX-COORD-12b – stručné označení zaměstnavatele v činnostech."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-12b-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import ACT_COL_EMPLOYER
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
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
        coordination_employer_activity_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        default_abbreviation,
        employer_short_label,
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.ui.coordination_employer_activities_tab import (
        CoordinationEmployerActivitiesTab,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord12bActivityEmployerShortTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

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

    def test_manual_abbreviation_has_priority(self) -> None:
        employer = SimpleNamespace(
            abbreviation="ZX-ZF",
            company_name="ZX - Zkušební firma, a.s.",
            active=True,
        )
        self.assertEqual(employer_short_label(employer), "ZX-ZF")

    def test_empty_manual_uses_automatic(self) -> None:
        name = "ZX - Zkušební firma, a.s."
        employer = SimpleNamespace(
            abbreviation="",
            company_name=name,
            active=True,
        )
        self.assertEqual(employer_short_label(employer), default_abbreviation(name))
        self.assertNotIn(" – ", employer_short_label(employer))
        self.assertNotEqual(employer_short_label(employer), name)

    def test_without_abbreviation_shows_name(self) -> None:
        employer = SimpleNamespace(
            abbreviation="",
            company_name="Dodavatel Alfa s.r.o.",
            active=True,
        )
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_employer_service.default_abbreviation",
            return_value="",
        ):
            self.assertEqual(
                employer_short_label(employer),
                "Dodavatel Alfa s.r.o.",
            )

    def test_activities_table_short_label_and_full_name_tooltip(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12b",
            meeting_date=date.today(),
        )
        coordination_employer_service.ensure_main_employer(coordination.id)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="ZX - Zkušební firma, a.s.",
            abbreviation="ZX-ZF",
        )
        coordination_employer_activity_service.add(
            contractor.id,
            activity_name="Montáž",
        )

        tab = CoordinationEmployerActivitiesTab(None, coordination_id=coordination.id)
        self.assertEqual(tab.table.rowCount(), 1)
        cell = tab.table.item(0, ACT_COL_EMPLOYER)
        self.assertEqual(cell.text(), "ZX-ZF")
        self.assertNotIn(" – ", cell.text())
        self.assertNotIn("Zkušební firma", cell.text())
        self.assertEqual(
            cell.toolTip(),
            "ZX - Zkušební firma, a.s.",
        )
        tab.close()

    def test_shared_helper_same_for_participants_and_activities(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12b shared",
            meeting_date=date.today(),
        )
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel Beta s.r.o.",
            abbreviation="BET",
        )
        via_activity = coordination_employer_activity_service.employer_label(
            contractor.id
        )
        via_participant = coordination_participant_service.employer_short_label(
            contractor.id
        )
        via_helper = employer_short_label(
            coordination_employer_service.get_by_id(contractor.id)
        )
        self.assertEqual(via_activity, "BET")
        self.assertEqual(via_participant, "BET")
        self.assertEqual(via_helper, "BET")


if __name__ == "__main__":
    unittest.main()
