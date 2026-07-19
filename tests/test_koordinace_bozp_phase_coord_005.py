"""Fáze COORD-005 – koordinátor BOZP."""

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

_TMP = Path(tempfile.mkdtemp(prefix="coord-005-"))
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
    from moduly.koordinace_bozp.constants import TAB_COORDINATOR
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
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
        CoordinationCoordinatorError,
        coordination_coordinator_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord005TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationEmployerActivity))
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

    def _setup_coordination(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="COORD-005",
            meeting_date=date.today(),
        )
        main = next(
            item
            for item in coordination_employer_service.list_for_coordination(
                coordination.id
            )
            if item.is_main
        )
        other = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Partner a.s.",
            abbreviation="PART",
        )
        main_person = coordination_participant_service.add_manual(
            main.id,
            full_name="Jan Novák",
            role="Technik BOZP",
        )
        other_person = coordination_participant_service.add_manual(
            other.id,
            full_name="Petr Svoboda",
            role="Stavbyvedoucí",
        )
        return coordination, main, other, main_person, other_person

    def test_model_and_table(self) -> None:
        self.assertEqual(
            CoordinationCoordinator.__tablename__,
            "coordination_coordinators",
        )
        columns = _table_columns("coordination_coordinators")
        for name in (
            "id",
            "coordination_id",
            "employer_id",
            "participant_id",
            "note",
            "active",
            "created_at",
            "updated_at",
        ):
            self.assertIn(name, columns)

    def test_select_and_change_coordinator(self) -> None:
        coordination, main, other, main_person, other_person = self._setup_coordination()
        saved = coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=main.id,
            participant_id=main_person.id,
            note="hlavní",
        )
        self.assertEqual(saved.coordination_id, coordination.id)
        self.assertEqual(saved.employer_id, main.id)
        self.assertEqual(saved.participant_id, main_person.id)
        self.assertEqual(saved.note, "hlavní")

        changed = coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=other.id,
            participant_id=other_person.id,
            note="zástup",
        )
        self.assertEqual(changed.id, saved.id)
        self.assertEqual(changed.employer_id, other.id)
        self.assertEqual(changed.participant_id, other_person.id)
        self.assertEqual(changed.note, "zástup")

        loaded = coordination_coordinator_service.get_for_coordination(coordination.id)
        assert loaded is not None
        self.assertEqual(loaded.participant_id, other_person.id)

    def test_filter_participants_by_employer_in_ui(self) -> None:
        coordination, main, other, main_person, other_person = self._setup_coordination()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertEqual(dialog.tabs.tabText(3), TAB_COORDINATOR)
        tab = dialog.coordinator_tab
        self.assertFalse(tab.content.isHidden())

        main_index = tab.employer_combo.findData(main.id)
        other_index = tab.employer_combo.findData(other.id)
        self.assertGreaterEqual(main_index, 0)
        self.assertGreaterEqual(other_index, 0)

        tab.employer_combo.setCurrentIndex(main_index)
        participant_ids = [
            tab.participant_combo.itemData(i)
            for i in range(tab.participant_combo.count())
            if isinstance(tab.participant_combo.itemData(i), int)
        ]
        self.assertEqual(participant_ids, [main_person.id])

        tab.employer_combo.setCurrentIndex(other_index)
        participant_ids = [
            tab.participant_combo.itemData(i)
            for i in range(tab.participant_combo.count())
            if isinstance(tab.participant_combo.itemData(i), int)
        ]
        self.assertEqual(participant_ids, [other_person.id])

    def test_cannot_select_inactive_participant(self) -> None:
        coordination, main, _other, main_person, _other_person = self._setup_coordination()
        coordination_participant_service.deactivate(main_person.id)
        with self.assertRaises(CoordinationCoordinatorError):
            coordination_coordinator_service.set_coordinator(
                coordination.id,
                employer_id=main.id,
                participant_id=main_person.id,
            )

    def test_cannot_select_inactive_employer(self) -> None:
        coordination, _main, other, _main_person, other_person = self._setup_coordination()
        coordination_employer_service.deactivate(other.id)
        with self.assertRaises(CoordinationCoordinatorError):
            coordination_coordinator_service.set_coordinator(
                coordination.id,
                employer_id=other.id,
                participant_id=other_person.id,
            )

    def test_load_saved_coordinator_and_keep_on_participant_deactivate(self) -> None:
        coordination, main, _other, main_person, _other_person = self._setup_coordination()
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=main.id,
            participant_id=main_person.id,
            note="uložený",
        )
        self.assertTrue(
            coordination_coordinator_service.is_participant_coordinator(main_person.id)
        )
        coordination_participant_service.deactivate(main_person.id)

        loaded = coordination_coordinator_service.get_for_coordination(coordination.id)
        assert loaded is not None
        self.assertEqual(loaded.participant_id, main_person.id)
        self.assertTrue(loaded.active)

        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        tab.refresh()
        self.assertEqual(tab.employer_combo.currentData(), main.id)
        self.assertEqual(tab.participant_combo.currentData(), main_person.id)
        self.assertEqual(tab.note.toPlainText(), "uložený")
        self.assertFalse(tab.warning_label.isHidden())


if __name__ == "__main__":
    unittest.main()
