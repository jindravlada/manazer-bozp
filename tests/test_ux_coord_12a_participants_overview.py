"""UX-COORD-12a – společný přehled účastníků schůzky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QHeaderView, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-12a-"))
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
    from core.widgets.table_selection import find_table_row_by_id
    from moduly.koordinace_bozp.constants import (
        PART_COL_ACTIVE,
        PART_COL_EMAIL,
        PART_COL_EMPLOYER,
        PART_COL_FULL_NAME,
        PART_COL_PHONE,
        PART_COL_ROLE,
        PARTICIPANT_TABLE_HEADERS,
    )
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
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import (
        BozpCoordinationDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_participant_dialog import (
        CoordinationParticipantDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_participants_tab import (
        CoordinationParticipantsTab,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord12aParticipantsOverviewTestCase(unittest.TestCase):
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

    def test_table_shows_all_employers_participants(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12a",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel Alfa s.r.o.",
            abbreviation="ALF",
        )
        coordination_participant_service.add_manual(
            main.id,
            full_name="Adam Hlavní",
            role="ředitel",
        )
        coordination_participant_service.add_manual(
            contractor.id,
            full_name="Boris Dodavatel",
            role="technik",
        )

        items = coordination_participant_service.list_for_coordination(coordination.id)
        self.assertEqual(len(items), 2)

        tab = CoordinationParticipantsTab(None, coordination_id=coordination.id)
        self.assertFalse(hasattr(tab, "employer_combo"))
        self.assertEqual(tab.findChildren(QComboBox), [])
        self.assertEqual(tab.table.rowCount(), 2)
        self.assertEqual(
            [tab.table.horizontalHeaderItem(i).text() for i in range(7)],
            PARTICIPANT_TABLE_HEADERS,
        )
        employer_cells = {
            tab.table.item(row, PART_COL_EMPLOYER).text()
            for row in range(tab.table.rowCount())
        }
        # Jen zkratka, ne zkratka i název současně.
        self.assertIn("ALF", employer_cells)
        self.assertFalse(any(" – " in text for text in employer_cells))
        tab.close()

    def test_add_dialog_requires_employer_default(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12a add",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel s.r.o.",
            abbreviation="DOD",
        )
        dialog = CoordinationParticipantDialog(
            None,
            coordination_id=coordination.id,
        )
        self.assertIsInstance(dialog.employer, QComboBox)
        self.assertEqual(dialog.employer.currentData(), contractor.id)
        self.assertTrue(dialog.employer.isEnabled())
        data = dialog.get_data()
        self.assertEqual(data["coordination_employer_id"], contractor.id)
        dialog.close()

        only_main = CoordinationParticipantDialog(
            None,
            coordination_id=coordination.id,
            default_employer_id=main.id,
        )
        self.assertEqual(only_main.employer.currentData(), main.id)
        only_main.close()

    def test_edit_dialog_keeps_employer(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12a edit",
            meeting_date=date.today(),
        )
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel s.r.o.",
            abbreviation="DOD",
        )
        participant = coordination_participant_service.add_manual(
            contractor.id,
            full_name="Karel Technik",
            role="stavbyvedoucí",
        )
        dialog = CoordinationParticipantDialog(
            None,
            participant=participant,
            coordination_id=coordination.id,
        )
        self.assertEqual(dialog.employer.currentData(), contractor.id)
        self.assertFalse(dialog.employer.isEnabled())
        updated_data = dialog.get_data()
        self.assertNotIn("coordination_employer_id", updated_data)
        coordination_participant_service.update_participant(
            participant.id,
            **updated_data,
        )
        reloaded = coordination_participant_service.get_by_id(participant.id)
        assert reloaded is not None
        self.assertEqual(reloaded.coordination_employer_id, contractor.id)
        dialog.close()

    def test_selection_and_deactivate(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12a nav",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        first = coordination_participant_service.add_manual(
            main.id, full_name="První Osoba"
        )
        second = coordination_participant_service.add_manual(
            main.id, full_name="Druhá Osoba"
        )
        tab = CoordinationParticipantsTab(None, coordination_id=coordination.id)
        tab.refresh(select_id=second.id, ensure_visible=True)
        self.assertEqual(tab.table.selected_participant_id(), second.id)

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            tab.deactivate_selected_participant()
        self.assertEqual(tab.table.selected_participant_id(), second.id)
        self.assertFalse(
            coordination_participant_service.get_by_id(second.id).active
        )
        self.assertIsNotNone(find_table_row_by_id(tab.table, first.id))

        header = tab.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(PART_COL_FULL_NAME),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(PART_COL_ROLE),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(PART_COL_EMAIL),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (PART_COL_EMPLOYER, PART_COL_PHONE, PART_COL_ACTIVE):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Interactive,
            )
        tab.close()

    def test_dialog_tab_has_no_employer_combo(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12a tab",
            meeting_date=date.today(),
        )
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.participants_tab
        self.assertFalse(hasattr(tab, "employer_combo"))
        self.assertEqual(tab.findChildren(QComboBox), [])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
