"""PU-UNSAVED-1 – ochrana neuložených změn v evidenci pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
)
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-unsaved-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_dialog import (
        SAVE_CONFIRMATION_TEXT,
        SAVE_CONFIRMATION_TITLE,
        UNSAVED_CHANGES_PROMPT,
        AccidentDialog,
    )
    from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
ORIGINAL_POPIS = "Pád z žebříku"


class PuUnsaved1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(self):
        today = date.today()
        return accident_service.create_accident(
            jmeno_prijmeni="Jan Novák",
            pohlavi="Muž",
            datum_narozeni=date(1990, 1, 1),
            druh_urazu=KIND_OVER_3,
            accident_date=today - timedelta(days=20),
            accident_time="10:00",
            popis_urazoveho_deje=ORIGINAL_POPIS,
            misto_urazu="dílna",
            dpn_od=today - timedelta(days=20),
            dpn_do=today - timedelta(days=10),
            opatreni="Kontrola žebříků",
            zranena_cast_tela="Levé zápěstí",
        )

    def _open(self, accident, *, show: bool = True) -> AccidentDialog:
        accident_id = accident.id

        def persist(data: dict) -> bool:
            return accident_service.update_accident(accident_id, **data) is not None

        dialog = AccidentDialog(accident=accident, on_persist=persist)
        if show:
            dialog.show()
            self.app.processEvents()
        return dialog

    def _finish(self, dialog: AccidentDialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def _stored(self, accident_id: int):
        row = accident_service.get_by_id(accident_id)
        return (
            row.popis_urazoveho_deje,
            row.description,
            row.misto_urazu,
            row.updated_at,
        )

    def _dirty_keys(self, dialog: AccidentDialog) -> list[str]:
        from moduly.kniha_urazu.ui.accident_dialog import _normalize_snapshot

        current = _normalize_snapshot(dialog.get_data())
        base = dialog._baseline or {}
        keys = set(current) | set(base)
        return sorted(key for key in keys if current.get(key) != base.get(key))

    def _button(self, dialog: AccidentDialog, standard) -> object:
        box = dialog.findChild(QDialogButtonBox)
        self.assertIsNotNone(box)
        button = box.button(standard)
        self.assertIsNotNone(button)
        return button

    def _fill_required(self, dialog: AccidentDialog) -> None:
        podatel = dialog.tab_podatel_widget
        podatel.zapisovatel.setEditText("Eva Malá")
        podatel.vrchni_dozor_oip.setChecked(True)

        employee = dialog.tab_zamestnanec_widget
        if not employee.jmeno_prijmeni.text().strip():
            employee.jmeno_prijmeni.setText("Jan Novák")
        if not employee._pohlavi():
            employee.pohlavi_muz.setChecked(True)
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
            uraz.popis_urazoveho_deje.setPlainText(ORIGINAL_POPIS)

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

    def _click_boxes(self, action, labels: list[str]) -> list[tuple[str, str, list[str]]]:
        seen: list[tuple[str, str, list[str]]] = []
        pending = list(labels)
        state = {"failed": None, "active": True}

        def pump(attempt: int = 0) -> None:
            if not state["active"]:
                return
            boxes = [
                widget
                for widget in QApplication.topLevelWidgets()
                if isinstance(widget, QMessageBox) and widget.isVisible()
            ]
            if not boxes:
                if pending and attempt < 40:
                    QTimer.singleShot(0, lambda n=attempt + 1: pump(n))
                return
            box = boxes[-1]
            if not box.property("pu_seen"):
                box.setProperty("pu_seen", True)
                seen.append(
                    (
                        box.windowTitle(),
                        box.text(),
                        [button.text() for button in box.buttons()],
                    )
                )
            if not pending:
                return
            label = pending[0]
            button = None
            if label == "OK":
                button = box.button(QMessageBox.StandardButton.Ok)
            if button is None:
                for candidate in box.buttons():
                    if candidate.text() == label:
                        button = candidate
                        break
            if button is None:
                state["failed"] = [candidate.text() for candidate in box.buttons()]
                fallback = box.buttons()[0] if box.buttons() else None
                pending.clear()
                if fallback is not None:
                    fallback.click()
                return
            pending.pop(0)
            button.click()
            if pending:
                QTimer.singleShot(0, lambda: pump(0))

        QTimer.singleShot(0, pump)
        action()
        state["active"] = False
        self.app.processEvents()
        self.assertIsNone(state["failed"], state["failed"])
        self.assertEqual(pending, [])
        return seen

    def test_close_without_changes_skips_prompt(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        self.assertFalse(dialog._is_dirty(), self._dirty_keys(dialog))
        seen = self._click_boxes(dialog.close, [])
        self.assertEqual(seen, [])
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_new_dialog_without_edits_closes_without_prompt(self) -> None:
        dialog = AccidentDialog()
        dialog.show()
        self.app.processEvents()
        self.assertFalse(dialog._is_dirty(), self._dirty_keys(dialog))
        seen = self._click_boxes(dialog.close, [])
        self.assertEqual(seen, [])
        self.assertFalse(dialog.isVisible())
        self._finish(dialog)

    def test_whitespace_only_edit_is_not_dirty(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText(f"  {ORIGINAL_POPIS}  \n")
        self.assertFalse(dialog._is_dirty(), self._dirty_keys(dialog))
        seen = self._click_boxes(dialog.close, [])
        self.assertEqual(seen, [])
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_edited_description_asks_before_close(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Upravený popis děje.")
        seen = self._click_boxes(
            lambda: self._button(dialog, QDialogButtonBox.StandardButton.Cancel).click(),
            ["Zrušit"],
        )
        self.assertEqual(seen[0][1], UNSAVED_CHANGES_PROMPT)
        self.assertEqual(seen[0][2], ["Uložit", "Neukládat", "Zrušit"])
        self.assertTrue(dialog.isVisible())
        self.assertEqual(
            dialog.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
            "Upravený popis děje.",
        )
        self._finish(dialog)

    def test_cancel_keeps_dialog_and_database(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Rozpracovaný popis")
        self._click_boxes(dialog.close, ["Zrušit"])
        self.assertTrue(dialog.isVisible())
        self.assertEqual(
            dialog.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
            "Rozpracovaný popis",
        )
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_discard_closes_without_database_write(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Tento text se nemá uložit")
        self._click_boxes(
            lambda: self._button(dialog, QDialogButtonBox.StandardButton.Cancel).click(),
            ["Neukládat"],
        )
        self.assertFalse(dialog.isVisible())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_escape_asks_and_cancel_keeps_dialog(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Úprava před Escape")
        seen = self._click_boxes(
            lambda: QTest.keyClick(dialog, Qt.Key.Key_Escape),
            ["Zrušit"],
        )
        self.assertEqual(seen[0][1], UNSAVED_CHANGES_PROMPT)
        self.assertTrue(dialog.isVisible())
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_title_bar_close_discard_does_not_write(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Úprava před křížkem")
        seen = self._click_boxes(dialog.close, ["Neukládat"])
        self.assertEqual(seen[0][1], UNSAVED_CHANGES_PROMPT)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_failed_validation_keeps_draft_and_dialog(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Rozpracovaný popis")
        seen = self._click_boxes(
            lambda: self._button(dialog, QDialogButtonBox.StandardButton.Save).click(),
            ["OK"],
        )
        self.assertTrue(dialog.isVisible())
        self.assertEqual(
            dialog.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
            "Rozpracovaný popis",
        )
        self.assertEqual(self._stored(accident.id), before)
        self.assertTrue(any("Nelze uložit" in title for title, _text, _labels in seen))
        self.assertNotIn(SAVE_CONFIRMATION_TEXT, [text for _title, text, _labels in seen])
        self._finish(dialog)

    def test_prompt_save_failed_validation_stays_open(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Popis z dotazu")
        self._click_boxes(dialog.close, ["Uložit", "OK"])
        self.assertTrue(dialog.isVisible())
        self.assertEqual(
            dialog.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
            "Popis z dotazu",
        )
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_save_confirms_and_reopen_shows_stored_text(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self._fill_required(dialog)
        dialog.tab_uraz_widget.popis_urazoveho_deje.setPlainText("Uložený popis děje.")
        self.assertEqual(self._validation_errors(dialog), [])
        seen = self._click_boxes(
            lambda: self._button(dialog, QDialogButtonBox.StandardButton.Save).click(),
            ["OK"],
        )
        self.assertEqual(seen[0][0], SAVE_CONFIRMATION_TITLE)
        self.assertEqual(seen[0][1], SAVE_CONFIRMATION_TEXT)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = accident_service.get_by_id(accident.id)
        self.assertEqual(stored.popis_urazoveho_deje, "Uložený popis děje.")
        self.assertEqual(stored.description, "Uložený popis děje.")

        reopened = self._open(stored)
        self.assertEqual(
            reopened.tab_uraz_widget.popis_urazoveho_deje.toPlainText(),
            "Uložený popis děje.",
        )
        self.assertFalse(reopened._is_dirty(), self._dirty_keys(reopened))
        self._finish(reopened)
        self._finish(dialog)

    def test_other_editable_field_is_dirty_and_discard_does_not_write(self) -> None:
        accident = self._create()
        before = self._stored(accident.id)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.misto_urazu.setPlainText("schodiště v hale")
        self.assertTrue(dialog._is_dirty())
        seen = self._click_boxes(
            lambda: QTest.keyClick(dialog, Qt.Key.Key_Escape),
            ["Neukládat"],
        )
        self.assertEqual(seen[0][1], UNSAVED_CHANGES_PROMPT)
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self._stored(accident.id), before)
        self._finish(dialog)

    def test_page_open_persists_inside_dialog_before_close(self) -> None:
        accident = self._create()
        page = KnihaUrazuPage()

        def fake_exec(dialog: AccidentDialog) -> int:
            dialog.show()
            self.app.processEvents()
            self._fill_required(dialog)
            dialog.tab_uraz_widget.misto_urazu.setPlainText("uložené místo")
            self._click_boxes(
                lambda: self._button(dialog, QDialogButtonBox.StandardButton.Cancel).click(),
                ["Uložit", "OK"],
            )
            self.assertFalse(dialog.isVisible())
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
            reloaded = accident_service.get_by_id(accident.id)
            self.assertEqual(reloaded.misto_urazu, "uložené místo")
            return int(dialog.result())

        with patch(
            "moduly.kniha_urazu.ui.kniha_urazu_page.exec_maximized",
            side_effect=fake_exec,
        ):
            page.open_accident(accident.id)

        reopened = self._open(accident_service.get_by_id(accident.id))
        self.assertEqual(reopened.tab_uraz_widget.misto_urazu.toPlainText(), "uložené místo")
        self._finish(reopened)
        page.deleteLater()
        self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
