"""KOORD-ULOZENI-1 – potvrzení úspěšného uložení koordinační schůzky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="koord-ulozeni-1-"))
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
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_DRAFT,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
        TAB_BASICS,
        TAB_MEASURES,
        TAB_RISK_SUBMISSIONS,
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
        CoordinationRiskSubmissionHistory,
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
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task

CONFIRMATION_TITLE = "Koordinační schůzka BOZP"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class KoordUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(CoordinationRiskSubmissionHistory))
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
            abbreviation="HL",
        )

    def _open(self) -> BozpCoordinationDialog:
        coordination = bozp_coordination_service.create_coordination(
            subject="Původní název",
            meeting_date=date(2026, 10, 14),
            place="Jednací místnost",
        )
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _tab(self, dialog: BozpCoordinationDialog, title: str) -> None:
        for index in range(dialog.tabs.count()):
            if dialog.tabs.tabText(index) == title:
                dialog.tabs.setCurrentIndex(index)
                self.app.processEvents()
                return
        raise AssertionError(title)

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.koordinace_bozp.ui.bozp_coordination_dialog._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _confirmation_boxes(self, shown: list[QMessageBox]) -> list[QMessageBox]:
        return [
            box
            for box in shown
            if box.windowTitle() == CONFIRMATION_TITLE
            and box.text() == CONFIRMATION_TEXT
        ]

    def test_successful_save_shows_confirmation(self) -> None:
        dialog = self._open()
        dialog.subject.setText("Uložený název")
        dialog.mark_dirty()
        shown = self._run(dialog.save_button.click)
        confirmations = self._confirmation_boxes(shown)
        self.assertEqual(len(confirmations), 1)
        ok_button = confirmations[0].button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")
        saved = bozp_coordination_service.get_by_id(dialog.coordination.id)
        assert saved is not None
        self.assertEqual(saved.subject, "Uložený název")
        self.assertEqual(saved.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertFalse(dialog.is_dirty())
        dialog.close()

    def test_failed_save_keeps_text_and_skips_confirmation(self) -> None:
        dialog = self._open()
        contractor = coordination_employer_service.add_participant(
            dialog.coordination.id,
            company_name="Dodavatel A s.r.o.",
            abbreviation="DA",
        )
        self._tab(dialog, TAB_RISK_SUBMISSIONS)
        tab = dialog.risk_submissions_tab
        index = tab.employer_combo.findData(contractor.id)
        self.assertGreaterEqual(index, 0)
        tab.employer_combo.setCurrentIndex(index)
        tab.risks_text.setPlainText("Text, který musí zůstat")
        tab.note.setPlainText("Poznámka, která musí zůstat")
        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_WILL_EMAIL)
        )
        warnings: list[tuple] = []

        def _warning(*args, **kwargs):
            warnings.append(args)
            return QMessageBox.StandardButton.Ok

        with patch(
            "moduly.koordinace_bozp.ui.coordination_risk_submissions_tab.QMessageBox.warning",
            side_effect=_warning,
        ):
            shown = self._run(dialog.save_button.click)
        self.assertEqual(self._confirmation_boxes(shown), [])
        self.assertTrue(warnings)
        self.assertIn("Termín doručení je povinný.", warnings[0][2])
        self.assertEqual(tab.risks_text.toPlainText(), "Text, který musí zůstat")
        self.assertEqual(tab.note.toPlainText(), "Poznámka, která musí zůstat")
        self.assertTrue(dialog.is_dirty())
        dialog.mark_clean()
        dialog.close()

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = self._open()
        self.assertFalse(dialog.is_dirty())
        shown = self._run(dialog.save_button.click)
        self.assertEqual(self._confirmation_boxes(shown), [])
        saved = bozp_coordination_service.get_by_id(dialog.coordination.id)
        assert saved is not None
        self.assertEqual(saved.subject, "Původní název")
        dialog.close()

    def test_tab_switch_does_not_confirm(self) -> None:
        dialog = self._open()
        self._tab(dialog, TAB_MEASURES)
        dialog.measures_tab.work_intent_information_text.setPlainText(
            "Rozepsaný záměr"
        )

        def switch() -> None:
            self._tab(dialog, TAB_BASICS)
            self._tab(dialog, TAB_MEASURES)

        shown = self._run(switch)
        self.assertEqual(shown, [])
        self.assertEqual(
            dialog.measures_tab.work_intent_information_text.toPlainText(),
            "Rozepsaný záměr",
        )
        dialog.mark_clean()
        dialog.measures_tab.clear_agreement_dirty()
        dialog.close()

    def test_close_meeting_does_not_confirm(self) -> None:
        dialog = self._open()
        dialog.subject.setText("Název před uzavřením")
        dialog.mark_dirty()
        with patch(
            "moduly.koordinace_bozp.ui.coordination_lifecycle_ui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            shown = self._run(dialog._close_meeting)
        self.assertEqual(self._confirmation_boxes(shown), [])
        saved = bozp_coordination_service.get_by_id(dialog.coordination.id)
        assert saved is not None
        self.assertEqual(saved.subject, "Název před uzavřením")
        self.assertEqual(saved.status, BOZP_COORDINATION_STATUS_DRAFT)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
