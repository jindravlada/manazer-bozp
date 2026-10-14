"""OZO-ULOZENI-1 – potvrzení úspěšného uložení ve Smlouvách OZO."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="ozo-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.smlouvy_ozo.constants import VALID_FROM_REQUIRED_MESSAGE
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
        qualification_certificate_service,
    )
    from moduly.smlouvy_ozo.ui.ozo_contract_dialog import OzoContractDialog
    from moduly.smlouvy_ozo.ui.ozo_historical_period_dialog import (
        OzoHistoricalPeriodDialog,
    )
    from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog
    from moduly.smlouvy_ozo.ui.qualification_certificate_dialog import (
        QualificationCertificateDialog,
    )

CONFIRMATION_TITLE = "Smlouvy OZO"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class OzoUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.smlouvy_ozo.ui.save_confirmation._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _assert_confirmation(self, shown: list[QMessageBox]) -> None:
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")

    def _close(self, dialog) -> None:
        dialog._editor._closing = True
        dialog.close()

    def _fill_contract(self, dialog: OzoContractDialog, name: str) -> None:
        dialog.employer_name.setText(name)
        dialog.valid_from.set_date_value(date(2026, 1, 1))
        dialog.valid_to.set_date_value(date(2026, 12, 31))

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = OzoContractDialog()
        dialog.show()
        self._fill_contract(dialog, "Uložená firma")
        dialog.note.setPlainText("uložená poznámka")
        shown = self._run(dialog._editor.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog.isHidden())
        contract_id = dialog.contract.id
        self._close(dialog)

        reopened = OzoContractDialog(contract=ozo_contract_service.get_by_id(contract_id))
        reopened.show()
        self.assertEqual(reopened.employer_name.text(), "Uložená firma")
        self.assertEqual(reopened.note.toPlainText(), "uložená poznámka")
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = OzoContractDialog()
        dialog.show()
        self._fill_contract(dialog, "Jedna změna")
        first = self._run(dialog._editor.save_button.click)
        self._assert_confirmation(first)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        second = self._run(dialog._editor.save_button.click)
        self.assertEqual(second, [])
        direct = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(direct, [])
        self.assertEqual(dialog.employer_name.text(), "Jedna změna")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = OzoContractDialog()
        dialog.show()
        dialog.employer_name.setText("Rozepsaná firma")
        dialog.note.setPlainText("rozepsaná poznámka")
        with patch(
            "moduly.smlouvy_ozo.ui.ozo_contract_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(VALID_FROM_REQUIRED_MESSAGE, warn.call_args.args[2])
        self.assertEqual(dialog.employer_name.text(), "Rozepsaná firma")
        self.assertEqual(dialog.note.toPlainText(), "rozepsaná poznámka")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertIsNone(dialog.contract)
        self._close(dialog)

    def test_other_actions_do_not_confirm(self) -> None:
        dialog = OzoContractDialog()
        dialog.show()
        self._fill_contract(dialog, "Přímé uložení")
        dialog.note.setPlainText("bez tlačítka")
        shown = self._run(lambda: self.assertTrue(dialog._save()))
        self.assertEqual(shown, [])
        stored = ozo_contract_service.get_by_id(dialog.contract.id)
        assert stored is not None
        self.assertEqual(stored.note, "bez tlačítka")
        self._close(dialog)

        dialog = OzoContractDialog()
        dialog.show()
        self._fill_contract(dialog, "Uložit při zavření")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(lambda: self.assertTrue(dialog._editor.request_close()))
        self.assertEqual(shown, [])
        stored = ozo_contract_service.get_by_id(dialog.contract.id)
        assert stored is not None
        self.assertEqual(stored.employer_name, "Uložit při zavření")
        self._close(dialog)

        person = OzoPersonDialog()
        person.show()
        person.last_name.setText("Jen záložka")
        shown = self._run(lambda: person.tabs.setCurrentIndex(1))
        self.assertEqual(shown, [])
        self.assertIsNone(ozo_person_service.get())
        self.assertEqual(person.last_name.text(), "Jen záložka")
        self._close(person)

    def test_person_certificate_and_history_confirm_changed_save(self) -> None:
        person = OzoPersonDialog()
        person.show()
        person.last_name.setText("Novák")
        person.note.setPlainText("poznámka osoby")
        shown = self._run(person._editor.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(person.isHidden())
        self._close(person)
        again = OzoPersonDialog()
        again.show()
        self.assertEqual(again.last_name.text(), "Novák")
        self.assertEqual(again.note.toPlainText(), "poznámka osoby")
        self._close(again)

        certificate = QualificationCertificateDialog()
        certificate.show()
        certificate.name.setText("Svářeč")
        certificate.indefinite_checkbox.setChecked(True)
        shown = self._run(certificate._editor.save_button.click)
        self._assert_confirmation(shown)
        certificate_id = certificate.certificate.id
        self._close(certificate)
        reopened = QualificationCertificateDialog(
            certificate=qualification_certificate_service.get_by_id(certificate_id),
        )
        reopened.show()
        self.assertEqual(reopened.name.text(), "Svářeč")
        self.assertTrue(reopened.indefinite_checkbox.isChecked())
        self._close(reopened)

        historical = OzoHistoricalPeriodDialog()
        historical.show()
        historical.exam_date.set_date_value(date(2020, 5, 1))
        historical.note.setPlainText("historická poznámka")
        shown = self._run(historical._editor.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(historical.isHidden())
        periods = ozo_person_service.list_periods(ozo_person_service.get())
        notes = [period.note for period in periods]
        self.assertIn("historická poznámka", notes)
        self._close(historical)
