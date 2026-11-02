"""KÚ-01 – Uložit, Uložit a zavřít a zavření editoru pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QPushButton
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ku-editor-save-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.widgets.editor_dialog_controller import (
        EDITOR_CLOSE_LABEL,
        EDITOR_SAVE_LABEL,
        confirm_unsaved_editor_close,
    )
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_dialog import (
        SAVE_CONFIRMATION_TEXT,
        SAVE_CONFIRMATION_TITLE,
        UNSAVED_CHANGES_PROMPT,
        UNSAVED_DISCARD_LABEL,
        AccidentDialog,
        _SAVE_CLOSE_LABEL,
    )
    from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage
    from moduly.ukoly.modely.task import Task

KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
_PROMPT = "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
_INFO = "moduly.kniha_urazu.ui.accident_dialog._exec_message_box"
_WARNING = "moduly.kniha_urazu.ui.accident_dialog.QMessageBox.warning"


class KuEditorSave1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(self, **overrides):
        today = date.today()
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": KIND_OVER_3,
            "accident_date": today - timedelta(days=20),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád z žebříku",
            "misto_urazu": "dílna",
            "dpn_od": today - timedelta(days=20),
            "dpn_do": today - timedelta(days=10),
            "opatreni": "Kontrola žebříků",
            "zranena_cast_tela": "Levé zápěstí",
        }
        data.update(overrides)
        return accident_service.create_accident(**data)

    def _open_new(self) -> AccidentDialog:
        page = KnihaUrazuPage()
        dialog = AccidentDialog(on_persist=page._persist_new_accident)
        dialog._page = page
        dialog.show()
        self.app.processEvents()
        return dialog

    def _open_existing(self, accident) -> AccidentDialog:
        accident_id = accident.id

        def persist(data: dict) -> bool:
            return accident_service.update_accident(accident_id, **data) is not None

        dialog = AccidentDialog(accident=accident, on_persist=persist)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: AccidentDialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(_INFO, side_effect=_exec):
            action()
        return shown

    def _fill(self, dialog: AccidentDialog) -> None:
        podatel = dialog.tab_podatel_widget
        podatel.zapisovatel.setEditText("Eva Malá")
        podatel.vrchni_dozor_oip.setChecked(True)
        podatel.datum_zapisu.set_date_value(date.today())

        employee = dialog.tab_zamestnanec_widget
        if not employee.jmeno_prijmeni.text().strip():
            employee.jmeno_prijmeni.setText("Jan Novák")
        if not employee._pohlavi():
            employee.pohlavi_muz.setChecked(True)
        if not employee.datum_narozeni.has_date():
            employee.datum_narozeni.set_date_value(date(1990, 1, 1))
        if not employee.adresa_pobytu.toPlainText().strip():
            employee.adresa_pobytu.setPlainText("Ulice 1, Praha")
        if not employee.zdravotni_pojistovna.value().strip():
            employee.zdravotni_pojistovna.set_value("VZP")
        if not employee.vztah_k_zamestnavateli.value().strip():
            employee.vztah_k_zamestnavateli.set_value("pracovní poměr")
        if not employee.den_vzniku_pravniho_vztahu.has_date():
            employee.den_vzniku_pravniho_vztahu.set_date_value(date(2020, 1, 1))
        if not employee.druh_vykonavane_prace.value().strip():
            employee.druh_vykonavane_prace.set_value("zámečník")

        uraz = dialog.tab_uraz_widget
        if not uraz.druh_urazu.value().strip():
            uraz.druh_urazu.set_value(KIND_OVER_3)
        if dialog.accident is None:
            uraz.accident_date.set_date_iso((date.today() - timedelta(days=5)).isoformat())
        if not uraz.accident_time.text().strip():
            uraz.accident_time.setText("10:00")
        if not uraz.druh_zraneni.has_value():
            uraz.druh_zraneni.set_value("odřenina")
        if not uraz.zranena_cast_tela.has_value():
            uraz.zranena_cast_tela.set_value("Levé zápěstí")
        if not uraz.cinnost_pri_urazu.value().strip():
            uraz.cinnost_pri_urazu.set_value("údržba")
        if not uraz.misto_urazu.toPlainText().strip():
            uraz.misto_urazu.setPlainText("dílna")
        if not uraz.popis_urazoveho_deje.toPlainText().strip():
            uraz.popis_urazoveho_deje.setPlainText("Pád z žebříku")

        workplace = dialog.tab_pracoviste_widget
        if not workplace.workplace.display_text():
            workplace.workplace.set_workplace(None, "Dílna")
        if not workplace.charakteristika_pracoviste.value().strip():
            workplace.charakteristika_pracoviste.set_value("výroba")
        if not workplace.zdroj_urazu.value().strip():
            workplace.zdroj_urazu.set_value("žebřík")
        if not workplace.pricina_urazu.value().strip():
            workplace.pricina_urazu.set_value("pád")
        if not workplace._radio_value():
            workplace.uraz_pracoviste_zamestnavatele_ano.setChecked(True)

        dalsi = dialog.tab_dalsi_widget
        if not dalsi._radio_value(dalsi.kontrola_alkohol_ano, dalsi.kontrola_alkohol_ne):
            dalsi.kontrola_alkohol_ne.setChecked(True)
        if not dalsi.porusene_predpisy.toPlainText().strip():
            dalsi.porusene_predpisy.setPlainText("nebyl porušen")
        if not dalsi.opatreni.toPlainText().strip():
            dalsi.opatreni.setPlainText("Kontrola žebříků")

        svedci = dialog.tab_svedci_widget
        if not svedci.vyjadreni_svedku.toPlainText().strip():
            svedci.vyjadreni_svedku.setPlainText("bez výhrad")
        if not svedci.vyjadreni_oo.toPlainText().strip():
            svedci.vyjadreni_oo.setPlainText("seznámen")
        if not svedci.zapsal_jmeno.currentText().strip():
            svedci.zapsal_jmeno.setEditText("Vedoucí směny")
        if not svedci.zapsal_pracovni_zarazeni.text().strip():
            svedci.zapsal_pracovni_zarazeni.setText("mistr")

    def _validation_errors(self, dialog: AccidentDialog) -> list[str]:
        errors = []
        for tab_name, widget in (
            ("Zapisovatel", dialog.tab_podatel_widget),
            ("Zaměstnanec", dialog.tab_zamestnanec_widget),
            ("Údaje o úrazu", dialog.tab_uraz_widget),
            ("Pracoviště", dialog.tab_pracoviste_widget),
            ("Další údaje", dialog.tab_dalsi_widget),
            ("Svědci", dialog.tab_svedci_widget),
        ):
            if hasattr(widget, "validate"):
                for item in widget.validate():
                    errors.append(f"{tab_name}: {item}")
        return errors

    def _bypass_validation(self, dialog: AccidentDialog) -> None:
        for tab in (
            dialog.tab_podatel_widget,
            dialog.tab_zamestnanec_widget,
            dialog.tab_uraz_widget,
            dialog.tab_pracoviste_widget,
            dialog.tab_dalsi_widget,
            dialog.tab_svedci_widget,
        ):
            if hasattr(tab, "validate"):
                tab.validate = MagicMock(return_value=[])

    def test_footer_has_save_save_close_and_close(self) -> None:
        dialog = self._open_new()
        try:
            layout = dialog.layout()
            footer = layout.itemAt(layout.count() - 1).layout()
            labels = []
            for index in range(footer.count()):
                widget = footer.itemAt(index).widget()
                if isinstance(widget, QPushButton):
                    labels.append(widget.text())
            self.assertEqual(
                labels,
                [EDITOR_SAVE_LABEL, _SAVE_CLOSE_LABEL, EDITOR_CLOSE_LABEL],
            )
            self.assertLess(
                footer.indexOf(dialog._editor.save_button),
                footer.indexOf(dialog._save_close_btn),
            )
            self.assertLess(
                footer.indexOf(dialog._save_close_btn),
                footer.indexOf(dialog._editor.close_button),
            )
        finally:
            self._close(dialog)

    def test_new_save_keeps_editor_and_same_record(self) -> None:
        dialog = self._open_new()
        try:
            self._fill(dialog)
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("První zápis")
            self.assertEqual(self._validation_errors(dialog), [])
            with patch.object(
                accident_service,
                "create_accident",
                wraps=accident_service.create_accident,
            ) as create:
                shown = self._run(dialog._editor.save_button.click)
                self.assertEqual(len(shown), 1)
                self.assertEqual(shown[0].windowTitle(), SAVE_CONFIRMATION_TITLE)
                self.assertEqual(shown[0].text(), SAVE_CONFIRMATION_TEXT)
                self.assertTrue(dialog.isVisible())
                self.assertFalse(dialog._closing)
                self.assertFalse(dialog._editor.is_new)
                self.assertFalse(dialog._is_dirty())
                self.assertTrue(dialog.was_saved)
                accident_id = int(dialog.accident.id)
                self.assertEqual(
                    dialog.tab_attachments_widget.entity_id,
                    accident_id,
                )
                self.assertEqual(create.call_count, 1)

                again = self._run(dialog._editor.save_button.click)
                self.assertEqual(again, [])
                self.assertEqual(create.call_count, 1)
                self.assertEqual(dialog.accident.id, accident_id)
        finally:
            self._close(dialog)

        stored = accident_service.get_by_id(accident_id)
        assert stored is not None
        self.assertEqual(stored.popis_urazoveho_deje, "První zápis")
        matches = [
            item
            for item in accident_service.get_all()
            if item.jmeno_prijmeni == "Jan Novák"
        ]
        self.assertEqual(len(matches), 1)

    def test_new_save_and_close_creates_one_record_without_confirmation(self) -> None:
        dialog = self._open_new()
        self._fill(dialog)
        dialog.tab_zamestnanec_widget.jmeno_prijmeni.setText("Nový uzavřený")
        with patch.object(
            accident_service,
            "create_accident",
            wraps=accident_service.create_accident,
        ) as create:
            shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(create.call_count, 1)
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog.isVisible())
        matches = [
            item
            for item in accident_service.get_all()
            if item.jmeno_prijmeni == "Nový uzavřený"
        ]
        self.assertEqual(len(matches), 1)
        dialog.deleteLater()

    def test_existing_save_keeps_editor_open(self) -> None:
        accident = self._create()
        dialog = self._open_existing(accident)
        try:
            self._fill(dialog)
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Uložený popis")
            shown = self._run(dialog._editor.save_button.click)
            self.assertEqual(len(shown), 1)
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog._is_dirty())
            self.assertEqual(dialog.accident.id, accident.id)
            quiet = self._run(dialog._editor.save_button.click)
            self.assertEqual(quiet, [])
        finally:
            self._close(dialog)
        stored = accident_service.get_by_id(accident.id)
        assert stored is not None
        self.assertEqual(stored.popis_urazoveho_deje, "Uložený popis")
        self.assertEqual(
            [
                item.id
                for item in accident_service.get_all()
                if item.jmeno_prijmeni == "Jan Novák"
            ],
            [accident.id],
        )

    def test_existing_save_and_close_without_confirmation(self) -> None:
        accident = self._create()
        dialog = self._open_existing(accident)
        self._fill(dialog)
        dialog.tab_uraz_widget.misto_urazu.setPlainText("hala")
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = accident_service.get_by_id(accident.id)
        assert stored is not None
        self.assertEqual(stored.misto_urazu, "hala")
        dialog.deleteLater()

    def test_close_without_changes_skips_prompt(self) -> None:
        accident = self._create()
        before = accident.popis_urazoveho_deje
        dialog = self._open_existing(accident)
        with patch(_PROMPT) as prompt:
            shown = self._run(dialog._editor.close_button.click)
        self.assertEqual(shown, [])
        prompt.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertFalse(dialog.was_saved)
        self.assertEqual(
            accident_service.get_by_id(accident.id).popis_urazoveho_deje,
            before,
        )
        dialog.deleteLater()

    def test_discard_does_not_write_draft(self) -> None:
        accident = self._create(jmeno_prijmeni="Ponechat")
        dialog = self._open_existing(accident)
        try:
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("nemá se zapsat")
            with (
                patch(_PROMPT, return_value="discard") as prompt,
                patch.object(
                    accident_service,
                    "update_accident",
                    wraps=accident_service.update_accident,
                ) as update,
            ):
                dialog._editor.close_button.click()
            prompt.assert_called_once()
            self.assertEqual(
                prompt.call_args.kwargs.get("discard_label"),
                UNSAVED_DISCARD_LABEL,
            )
            self.assertEqual(
                prompt.call_args.kwargs.get("text"),
                UNSAVED_CHANGES_PROMPT,
            )
            update.assert_not_called()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        finally:
            if dialog.isVisible():
                self._close(dialog)
        stored = accident_service.get_by_id(accident.id)
        assert stored is not None
        self.assertEqual(stored.popis_urazoveho_deje, "Pád z žebříku")

    def test_cancel_close_keeps_editor_open(self) -> None:
        accident = self._create()
        dialog = self._open_existing(accident)
        try:
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Ještě ne")
            with patch(_PROMPT, return_value="cancel"):
                dialog._editor.close_button.click()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog._closing)
            self.assertEqual(
                dialog.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
                "Ještě ne",
            )
        finally:
            self._close(dialog)
        self.assertEqual(
            accident_service.get_by_id(accident.id).popis_urazoveho_deje,
            "Pád z žebříku",
        )

    def test_validation_and_save_errors_keep_editor_open(self) -> None:
        accident = self._create()
        dialog = self._open_existing(accident)
        try:
            dialog.tab_zamestnanec_widget.jmeno_prijmeni.clear()
            with patch(_WARNING) as warning:
                shown = self._run(dialog._editor.save_button.click)
                self.assertEqual(shown, [])
                warning.assert_called()
                self.assertIn("Nejsou vyplněny", warning.call_args.args[2])
                self.assertTrue(dialog.isVisible())
                self.assertFalse(dialog._closing)
                dialog._save_and_close()
            self.assertTrue(dialog.isVisible())
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            self._close(dialog)
        self.assertEqual(
            accident_service.get_by_id(accident.id).jmeno_prijmeni,
            "Jan Novák",
        )

        dialog = self._open_existing(accident_service.get_by_id(accident.id))
        try:
            self._bypass_validation(dialog)
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Rozepsáno")
            with (
                patch.object(
                    accident_service,
                    "update_accident",
                    side_effect=RuntimeError("db"),
                ),
                patch(_WARNING) as warning,
            ):
                shown = self._run(dialog._save_close_btn.click)
            self.assertEqual(shown, [])
            warning.assert_called()
            self.assertIn("nepodařilo uložit", warning.call_args.args[2])
            self.assertTrue(dialog.isVisible())
            self.assertEqual(
                dialog.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
                "Rozepsáno",
            )
        finally:
            self._close(dialog)
        self.assertEqual(
            accident_service.get_by_id(accident.id).popis_urazoveho_deje,
            "Pád z žebříku",
        )

    def test_prompt_save_failure_does_not_close(self) -> None:
        accident = self._create()
        dialog = self._open_existing(accident)
        try:
            dialog.tab_zamestnanec_widget.jmeno_prijmeni.clear()
            with (
                patch(_PROMPT, return_value="save"),
                patch(_WARNING) as warning,
            ):
                dialog._editor.close_button.click()
            warning.assert_called()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog._closing)
        finally:
            self._close(dialog)
        self.assertEqual(
            accident_service.get_by_id(accident.id).jmeno_prijmeni,
            "Jan Novák",
        )

    def test_repeated_save_does_not_duplicate_record(self) -> None:
        dialog = self._open_new()
        try:
            self._fill(dialog)
            dialog.tab_zamestnanec_widget.jmeno_prijmeni.setText("Jediný úraz")
            self._run(dialog._editor.save_button.click)
            accident_id = int(dialog.accident.id)
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Doplněno")
            with patch.object(
                accident_service,
                "create_accident",
                wraps=accident_service.create_accident,
            ) as create:
                self._run(dialog._editor.save_button.click)
            create.assert_not_called()
            self.assertEqual(dialog.accident.id, accident_id)
        finally:
            self._close(dialog)
        matches = [
            item
            for item in accident_service.get_all()
            if item.jmeno_prijmeni == "Jediný úraz"
        ]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, accident_id)
        self.assertEqual(matches[0].popis_urazoveho_deje, "Doplněno")

    def test_new_discard_does_not_create_record(self) -> None:
        dialog = self._open_new()
        dialog.tab_zamestnanec_widget.jmeno_prijmeni.setText("Nezakládat")
        with patch(_PROMPT, return_value="discard"):
            dialog._editor.close_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(accident_service.get_all(), [])
        dialog.deleteLater()

    def test_system_close_cancel_ignores_event(self) -> None:
        accident = self._create()
        dialog = self._open_existing(accident)
        try:
            dialog.tab_uraz_widget.misto_urazu.setPlainText("z křížku")
            event = QCloseEvent()
            with patch(_PROMPT, return_value="cancel"):
                dialog._editor.eventFilter(dialog, event)
            self.assertFalse(event.isAccepted())
            self.assertTrue(dialog.isVisible())
        finally:
            self._close(dialog)

    def test_unsaved_prompt_offers_save_discard_and_cancel(self) -> None:
        with patch(
            "core.widgets.editor_dialog_controller.QMessageBox"
        ) as mock_box_cls:
            instance = mock_box_cls.return_value
            buttons = [MagicMock(), MagicMock(), MagicMock()]
            instance.addButton.side_effect = buttons
            instance.clickedButton.return_value = buttons[1]
            decision = confirm_unsaved_editor_close(
                None,
                title=SAVE_CONFIRMATION_TITLE,
                text=UNSAVED_CHANGES_PROMPT,
                discard_label=UNSAVED_DISCARD_LABEL,
            )
        self.assertEqual(decision, "discard")
        labels = [call.args[0] for call in instance.addButton.call_args_list]
        self.assertEqual(
            labels,
            [EDITOR_SAVE_LABEL, UNSAVED_DISCARD_LABEL, "Zrušit"],
        )

    def test_page_refreshes_after_save_and_ignores_discard(self) -> None:
        page = KnihaUrazuPage()

        def save_and_close(dialog: AccidentDialog) -> int:
            dialog.show()
            self.app.processEvents()
            self._fill(dialog)
            dialog.tab_zamestnanec_widget.jmeno_prijmeni.setText("Ze seznamu")
            dialog._save_and_close()
            return int(dialog.result())

        with patch(
            "moduly.kniha_urazu.ui.kniha_urazu_page.exec_maximized",
            side_effect=save_and_close,
        ):
            page.new_accident()
        self.assertGreater(page.table.rowCount(), 0)
        stored = [
            item
            for item in accident_service.get_all()
            if item.jmeno_prijmeni == "Ze seznamu"
        ]
        self.assertEqual(len(stored), 1)

        def discard(dialog: AccidentDialog) -> int:
            dialog.show()
            self.app.processEvents()
            dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("neukládat ze seznamu")
            with patch(_PROMPT, return_value="discard"):
                dialog._editor.close_button.click()
            return int(dialog.result())

        with patch(
            "moduly.kniha_urazu.ui.kniha_urazu_page.exec_maximized",
            side_effect=discard,
        ):
            page.open_accident(stored[0].id)
        self.assertEqual(
            accident_service.get_by_id(stored[0].id).popis_urazoveho_deje,
            "Pád z žebříku",
        )
        page.deleteLater()


if __name__ == "__main__":
    unittest.main()
