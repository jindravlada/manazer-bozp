"""Fáze COORD-003 – účastníci koordinační schůzky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-003-"))
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
    from moduly.koordinace_bozp.constants import (
        COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
        COORDINATION_PARTICIPANT_SOURCE_MANUAL,
        PART_COL_FULL_NAME,
        PARTICIPANT_TABLE_HEADERS,
        TAB_BASICS,
        TAB_EMPLOYERS,
        TAB_PARTICIPANTS,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        CoordinationParticipantError,
        coordination_participant_service,
        snapshot_from_employee,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord003TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha 1",
            nace="",
        )
        self.worker = settings_service.save_worker(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            title_after="",
            position="Bezpečnostní technik",
            phone="+420111222333",
            email="jan.novak@example.com",
            performs_controls=True,
        )

    def _create_coordination(self, subject: str = "COORD-003"):
        return bozp_coordination_service.create_coordination(
            subject=subject,
            meeting_date=date.today(),
        )

    def _main_employer(self, coordination_id: int):
        employers = coordination_employer_service.list_for_coordination(coordination_id)
        return next(item for item in employers if item.is_main)

    def test_model_and_table(self) -> None:
        self.assertEqual(
            CoordinationParticipant.__tablename__,
            "coordination_participants",
        )
        columns = _table_columns("coordination_participants")
        for name in (
            "id",
            "coordination_employer_id",
            "person_source_type",
            "employee_id",
            "full_name",
            "role",
            "phone",
            "email",
            "note",
            "active",
            "sort_order",
            "created_at",
            "updated_at",
        ):
            self.assertIn(name, columns)

    def test_add_internal_participant_and_prefill_snapshot(self) -> None:
        coordination = self._create_coordination("Interní")
        main = self._main_employer(coordination.id)
        snapshot = snapshot_from_employee(self.worker.id)
        self.assertEqual(snapshot["full_name"], self.worker.display_name)
        self.assertEqual(snapshot["role"], "Bezpečnostní technik")
        self.assertEqual(snapshot["phone"], "+420111222333")
        self.assertEqual(snapshot["email"], "jan.novak@example.com")

        participant = coordination_participant_service.add_from_employee(
            main.id,
            self.worker.id,
        )
        self.assertEqual(participant.person_source_type, COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE)
        self.assertEqual(participant.employee_id, self.worker.id)
        self.assertEqual(participant.full_name, self.worker.display_name)
        self.assertEqual(participant.role, "Bezpečnostní technik")
        self.assertEqual(participant.phone, "+420111222333")
        self.assertEqual(participant.email, "jan.novak@example.com")
        self.assertEqual(participant.coordination_employer_id, main.id)

        settings_service.save_worker(
            id=self.worker.id,
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            title_after="",
            position="Změněná funkce",
            phone="+420999888777",
            email="zmena@example.com",
            performs_controls=True,
        )
        reloaded = coordination_participant_service.get_by_id(participant.id)
        assert reloaded is not None
        self.assertEqual(reloaded.role, "Bezpečnostní technik")
        self.assertEqual(reloaded.phone, "+420111222333")
        self.assertEqual(reloaded.email, "jan.novak@example.com")

    def test_add_manual_participant_bound_to_employer(self) -> None:
        coordination = self._create_coordination("Ruční")
        main = self._main_employer(coordination.id)
        other = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Stavex a.s.",
            abbreviation="STAVEX",
        )
        participant = coordination_participant_service.add_manual(
            other.id,
            full_name="Petr Svoboda",
            role="Stavbyvedoucí",
            phone="777111222",
            email="petr@stavex.cz",
        )
        self.assertEqual(participant.person_source_type, COORDINATION_PARTICIPANT_SOURCE_MANUAL)
        self.assertIsNone(participant.employee_id)
        self.assertEqual(participant.coordination_employer_id, other.id)
        self.assertEqual(participant.full_name, "Petr Svoboda")

        main_list = coordination_participant_service.list_for_employer(main.id)
        other_list = coordination_participant_service.list_for_employer(other.id)
        self.assertEqual(main_list, [])
        self.assertEqual(len(other_list), 1)
        self.assertEqual(other_list[0].id, participant.id)

        with self.assertRaises(CoordinationParticipantError):
            coordination_participant_service.add_from_employee(other.id, self.worker.id)

    def test_duplicate_name_forbidden(self) -> None:
        coordination = self._create_coordination("Duplicita")
        main = self._main_employer(coordination.id)
        coordination_participant_service.add_manual(
            main.id,
            full_name="Jan  Novák",
        )
        with self.assertRaises(CoordinationParticipantError):
            coordination_participant_service.add_manual(
                main.id,
                full_name=" jan novák ",
            )

    def test_deactivate_and_reactivate(self) -> None:
        coordination = self._create_coordination("Aktivace")
        main = self._main_employer(coordination.id)
        participant = coordination_participant_service.add_manual(
            main.id,
            full_name="Eva Králová",
        )
        self.assertTrue(coordination_participant_service.deactivate(participant.id))
        reloaded = coordination_participant_service.get_by_id(participant.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)
        active_only = coordination_participant_service.list_for_employer(
            main.id,
            include_inactive=False,
        )
        self.assertEqual(active_only, [])
        self.assertTrue(coordination_participant_service.activate(participant.id))
        again = coordination_participant_service.get_by_id(participant.id)
        assert again is not None
        self.assertTrue(again.active)

    def test_cannot_add_to_inactive_employer(self) -> None:
        coordination = self._create_coordination("Neaktivní firma")
        other = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dočasná firma",
            abbreviation="DOC",
        )
        coordination_employer_service.deactivate(other.id)
        with self.assertRaises(CoordinationParticipantError):
            coordination_participant_service.add_manual(
                other.id,
                full_name="Někdo Jiný",
            )

    def test_participants_kept_when_employer_deactivated(self) -> None:
        coordination = self._create_coordination("Zachování")
        other = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Partner",
            abbreviation="PART",
        )
        participant = coordination_participant_service.add_manual(
            other.id,
            full_name="Martin Černý",
            role="Koordinátor stavby",
        )
        coordination_employer_service.deactivate(other.id)
        reloaded = coordination_participant_service.get_by_id(participant.id)
        assert reloaded is not None
        self.assertTrue(reloaded.active)
        self.assertEqual(reloaded.full_name, "Martin Černý")
        listed = coordination_participant_service.list_for_employer(other.id)
        self.assertEqual(len(listed), 1)

    def test_ui_filters_by_selected_employer(self) -> None:
        coordination = self._create_coordination("UI filtr")
        main = self._main_employer(coordination.id)
        other = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Beta s.r.o.",
            abbreviation="BETA",
        )
        coordination_participant_service.add_manual(main.id, full_name="Hlavní Osoba")
        coordination_participant_service.add_manual(other.id, full_name="Cizí Osoba")

        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertEqual(dialog.tabs.tabText(0), TAB_BASICS)
        self.assertEqual(dialog.tabs.tabText(1), TAB_EMPLOYERS)
        self.assertEqual(dialog.tabs.tabText(2), TAB_PARTICIPANTS)

        tab = dialog.participants_tab
        self.assertFalse(tab.content.isHidden())
        self.assertEqual(
            [tab.table.horizontalHeaderItem(i).text() for i in range(6)],
            PARTICIPANT_TABLE_HEADERS,
        )

        main_index = tab.employer_combo.findData(main.id)
        other_index = tab.employer_combo.findData(other.id)
        self.assertGreaterEqual(main_index, 0)
        self.assertGreaterEqual(other_index, 0)

        tab.employer_combo.setCurrentIndex(main_index)
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.item(0, PART_COL_FULL_NAME).text(), "Hlavní Osoba")

        tab.employer_combo.setCurrentIndex(other_index)
        self.assertEqual(tab.table.rowCount(), 1)
        self.assertEqual(tab.table.item(0, PART_COL_FULL_NAME).text(), "Cizí Osoba")

        new_dialog = BozpCoordinationDialog(None)
        self.assertTrue(new_dialog.participants_tab.content.isHidden())


if __name__ == "__main__":
    unittest.main()
