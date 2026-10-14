"""KOORD-PREDANI-ULOZENI-1 – potvrzení uložení předání rizik."""

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

_TMP = Path(tempfile.mkdtemp(prefix="koord-predani-ulozeni-1-"))
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
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task

CONFIRMATION_TITLE = "Koordinační schůzka BOZP"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class KoordPredaniUlozeni1SaveConfirmationTestCase(unittest.TestCase):
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
            subject="Schůzka předání",
            meeting_date=date(2026, 10, 14),
            place="Jednací místnost",
        )
        self.supplier_a = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel A s.r.o.",
            abbreviation="DA",
        )
        self.supplier_b = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel B s.r.o.",
            abbreviation="DB",
        )
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        dialog.show()
        self.app.processEvents()
        self._tab(dialog, TAB_RISK_SUBMISSIONS)
        return dialog

    def _tab(self, dialog: BozpCoordinationDialog, title: str) -> None:
        for index in range(dialog.tabs.count()):
            if dialog.tabs.tabText(index) == title:
                dialog.tabs.setCurrentIndex(index)
                self.app.processEvents()
                return
        raise AssertionError(title)

    def _select(self, dialog: BozpCoordinationDialog, employer_id: int):
        tab = dialog.risk_submissions_tab
        index = tab.employer_combo.findData(employer_id)
        self.assertGreaterEqual(index, 0)
        tab.employer_combo.setCurrentIndex(index)
        self.app.processEvents()
        return tab

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with (
            patch(
                "moduly.koordinace_bozp.ui.coordination_risk_submissions_tab._exec_message_box",
                side_effect=_exec,
            ),
            patch(
                "moduly.koordinace_bozp.ui.bozp_coordination_dialog._exec_message_box",
                side_effect=_exec,
            ),
        ):
            action()
        return shown

    def _confirmations(self, shown: list[QMessageBox]) -> list[QMessageBox]:
        return [
            box
            for box in shown
            if box.windowTitle() == CONFIRMATION_TITLE and box.text() == CONFIRMATION_TEXT
        ]

    def _assert_confirmation(self, shown: list[QMessageBox]) -> None:
        confirmations = self._confirmations(shown)
        self.assertEqual(len(confirmations), 1)
        box = confirmations[0]
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")

    def _close(self, dialog: BozpCoordinationDialog) -> None:
        dialog.mark_clean()
        dialog._closing = True
        dialog.close()

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_a.id)
        tab.note.setPlainText("uložená poznámka A")
        tab.risks_text.setPlainText("uložený text rizik A")
        shown = self._run(tab.save_btn.click)
        self._assert_confirmation(shown)
        self.assertFalse(tab.submission_is_dirty())
        self.assertFalse(dialog.isHidden())
        self.assertEqual(tab.employer_combo.currentData(), self.supplier_a.id)
        coordination_id = dialog.coordination.id
        self._close(dialog)

        reopened = BozpCoordinationDialog(
            None,
            coordination=bozp_coordination_service.get_by_id(coordination_id),
        )
        reopened.show()
        self.app.processEvents()
        self._tab(reopened, TAB_RISK_SUBMISSIONS)
        tab = self._select(reopened, self.supplier_a.id)
        self.assertEqual(tab.note.toPlainText(), "uložená poznámka A")
        self.assertEqual(tab.risks_text.toPlainText(), "uložený text rizik A")
        stored = coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        assert stored is not None
        self.assertEqual(stored.coordination_employer_id, self.supplier_a.id)
        self.assertEqual(stored.note, "uložená poznámka A")
        self.assertIsNone(
            coordination_risk_submission_service.get_for_employer(self.supplier_b.id)
        )
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_a.id)
        tab.note.setPlainText("jedna změna")
        first = self._run(tab.save_btn.click)
        self._assert_confirmation(first)
        second = self._run(tab.save_btn.click)
        self.assertEqual(self._confirmations(second), [])
        self.assertEqual(tab.note.toPlainText(), "jedna změna")
        stored = coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        assert stored is not None
        self.assertEqual(stored.note, "jedna změna")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_a.id)
        tab.risks_text.setPlainText("rozepsaný text")
        tab.note.setPlainText("rozepsaná poznámka")
        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_WILL_EMAIL)
        )
        with patch(
            "moduly.koordinace_bozp.ui.coordination_risk_submissions_tab.QMessageBox.warning",
        ) as warn:
            shown = self._run(tab.save_btn.click)
        self.assertEqual(self._confirmations(shown), [])
        warn.assert_called_once()
        self.assertIn("Termín doručení je povinný.", warn.call_args.args[2])
        self.assertEqual(tab.risks_text.toPlainText(), "rozepsaný text")
        self.assertEqual(tab.note.toPlainText(), "rozepsaná poznámka")
        self.assertEqual(
            tab.submission_method.currentData(),
            RISK_SUBMISSION_STATUS_WILL_EMAIL,
        )
        self.assertTrue(tab.submission_is_dirty())
        self.assertFalse(dialog.isHidden())
        self.assertIsNone(
            coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        )
        self._close(dialog)

    def test_supplier_switch_does_not_confirm_and_keeps_assignment(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_a.id)
        tab.note.setPlainText("poznámka dodavatele A")
        shown = self._run(
            lambda: tab.employer_combo.setCurrentIndex(
                tab.employer_combo.findData(self.supplier_b.id)
            )
        )
        self.assertEqual(self._confirmations(shown), [])
        self.assertEqual(tab.employer_combo.currentData(), self.supplier_b.id)
        self.assertEqual(tab.note.toPlainText(), "")
        stored_a = coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        assert stored_a is not None
        self.assertEqual(stored_a.coordination_employer_id, self.supplier_a.id)
        self.assertEqual(stored_a.note, "poznámka dodavatele A")
        self.assertIsNone(
            coordination_risk_submission_service.get_for_employer(self.supplier_b.id)
        )
        self._close(dialog)

    def test_tab_switch_does_not_save_or_confirm(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_a.id)
        tab.note.setPlainText("jen v záložce")

        def switch() -> None:
            self._tab(dialog, TAB_BASICS)
            self._tab(dialog, TAB_RISK_SUBMISSIONS)

        shown = self._run(switch)
        self.assertEqual(self._confirmations(shown), [])
        self.assertEqual(tab.note.toPlainText(), "jen v záložce")
        self.assertTrue(tab.submission_is_dirty())
        self.assertIsNone(
            coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        )
        self._close(dialog)

    def test_main_save_does_not_duplicate_confirmation(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_b.id)
        tab.note.setPlainText("uloženo hlavním tlačítkem")
        shown = self._run(dialog.save_button.click)
        self._assert_confirmation(shown)
        stored = coordination_risk_submission_service.get_for_employer(self.supplier_b.id)
        assert stored is not None
        self.assertEqual(stored.coordination_employer_id, self.supplier_b.id)
        self.assertEqual(stored.note, "uloženo hlavním tlačítkem")
        self.assertIsNone(
            coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        )
        self._close(dialog)

    def test_close_meeting_does_not_confirm(self) -> None:
        dialog = self._open()
        tab = self._select(dialog, self.supplier_a.id)
        tab.note.setPlainText("uloženo uzavřením")
        with patch(
            "moduly.koordinace_bozp.ui.coordination_lifecycle_ui.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            shown = self._run(dialog._close_meeting)
        self.assertEqual(self._confirmations(shown), [])
        stored = coordination_risk_submission_service.get_for_employer(self.supplier_a.id)
        assert stored is not None
        self.assertEqual(stored.note, "uloženo uzavřením")
        self.assertEqual(stored.coordination_employer_id, self.supplier_a.id)
        saved = bozp_coordination_service.get_by_id(dialog.coordination.id)
        assert saved is not None
        self.assertEqual(saved.status, BOZP_COORDINATION_STATUS_DRAFT)
        self._close(dialog)
