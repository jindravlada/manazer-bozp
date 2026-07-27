"""UX-COORD-12c – odložené ukládání koordinátora."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-12c-"))
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
    from moduly.koordinace_bozp.constants import TAB_BASICS, TAB_COORDINATOR
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
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
        coordination_coordinator_service,
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
    from core.widgets.editor_dialog_controller import (
        EDITOR_UNSAVED_ABORT_LABEL,
        EDITOR_UNSAVED_DISCARD_LABEL,
        EDITOR_UNSAVED_PROMPT,
        EDITOR_UNSAVED_SAVE_LABEL,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord12cDeferredCoordinatorSaveTestCase(unittest.TestCase):
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

    def _setup(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-12c",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        participant = coordination_participant_service.add_manual(
            main.id,
            full_name="Jan Účastník",
            role="technik",
        )
        return coordination, main, participant

    def test_no_separate_save_button(self) -> None:
        coordination, _main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        self.assertFalse(hasattr(tab, "save_btn"))
        self.assertFalse(hasattr(tab, "save_coordinator"))
        labels = [
            btn.text()
            for btn in tab.findChildren(QPushButton)
        ]
        self.assertNotIn("Uložit koordinátora", labels)
        dialog.close()

    def test_coordinator_change_marks_dirty(self) -> None:
        coordination, _main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertFalse(dialog.is_dirty())
        tab = dialog.coordinator_tab
        tab.source_manual.setChecked(True)
        self.assertTrue(dialog.is_dirty())
        dialog.mark_clean()
        tab.full_name.textEdited.emit("Nový koordinátor")
        self.assertTrue(dialog.is_dirty())
        dialog.mark_clean()
        dialog.close()

    def test_tab_switch_keeps_working_copy(self) -> None:
        coordination, _main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        tab.source_manual.setChecked(True)
        tab.full_name.setText("Pracovní kopie")
        tab.role.setText("role WC")

        basics_index = next(
            i
            for i in range(dialog.tabs.count())
            if dialog.tabs.tabText(i) == TAB_BASICS
        )
        coord_index = next(
            i
            for i in range(dialog.tabs.count())
            if dialog.tabs.tabText(i) == TAB_COORDINATOR
        )
        dialog.tabs.setCurrentIndex(basics_index)
        dialog.tabs.setCurrentIndex(coord_index)

        self.assertEqual(tab.full_name.text(), "Pracovní kopie")
        self.assertEqual(tab.role.text(), "role WC")
        self.assertIsNone(
            coordination_coordinator_service.get_for_coordination(coordination.id)
        )
        dialog.mark_clean()
        dialog.close()

    def test_main_save_persists_coordinator(self) -> None:
        coordination, main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        tab.source_manual.setChecked(True)
        tab.full_name.setText("Uložený přes hlavní")
        tab.role.setText("koordinátor")
        self.assertTrue(dialog.is_dirty())
        self.assertTrue(dialog._save())
        self.assertFalse(dialog.is_dirty())

        loaded = coordination_coordinator_service.get_for_coordination(coordination.id)
        assert loaded is not None
        self.assertEqual(loaded.full_name, "Uložený přes hlavní")
        self.assertEqual(loaded.employer_name, main.company_name)
        dialog.close()

    def test_close_prompt_discard_does_not_save(self) -> None:
        coordination, _main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        tab.source_manual.setChecked(True)
        tab.full_name.setText("Zahodit mě")
        self.assertTrue(dialog.is_dirty())

        with patch.object(dialog, "_prompt_unsaved_close", return_value="discard"):
            dialog.reject()

        self.assertIsNone(
            coordination_coordinator_service.get_for_coordination(coordination.id)
        )

    def test_close_prompt_save_persists(self) -> None:
        coordination, main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        tab.source_manual.setChecked(True)
        tab.full_name.setText("Uložit při zavření")

        with patch.object(dialog, "_prompt_unsaved_close", return_value="save"):
            dialog.reject()

        loaded = coordination_coordinator_service.get_for_coordination(coordination.id)
        assert loaded is not None
        self.assertEqual(loaded.full_name, "Uložit při zavření")
        self.assertEqual(loaded.employer_name, main.company_name)

    def test_prompt_labels(self) -> None:
        self.assertEqual(EDITOR_UNSAVED_PROMPT, "Uložit změny před zavřením?")
        self.assertEqual(EDITOR_UNSAVED_SAVE_LABEL, "Uložit")
        self.assertEqual(EDITOR_UNSAVED_DISCARD_LABEL, "Neukládat")
        self.assertEqual(EDITOR_UNSAVED_ABORT_LABEL, "Zrušit")

        coordination, _main, _participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        with patch.object(dialog, "_prompt_unsaved_close", return_value="cancel") as prompt:
            dialog.mark_dirty()
            dialog.reject()
            prompt.assert_called_once()
            self.assertTrue(dialog.is_dirty())
        dialog.mark_clean()
        dialog.close()

    def test_saved_coordinator_reloads(self) -> None:
        coordination, main, participant = self._setup()
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=main.id,
            participant_id=participant.id,
            note="uložená poznámka",
        )
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        self.assertTrue(tab.source_participant.isChecked())
        self.assertEqual(tab.participant_combo.currentData(), participant.id)
        self.assertEqual(tab.full_name.text(), "Jan Účastník")
        self.assertEqual(tab.note.toPlainText(), "uložená poznámka")
        self.assertFalse(dialog.is_dirty())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
