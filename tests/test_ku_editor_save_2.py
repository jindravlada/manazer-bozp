"""KÚ-02 – Uložit, Uložit a zavřít a zavření editoru ohlašovacích povinností."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QRadioButton
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ku-editor-save-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.widgets.editor_dialog_controller import EDITOR_CLOSE_LABEL, EDITOR_SAVE_LABEL
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import (
        SAVE_CONFIRMATION_TEXT,
        SAVE_CONFIRMATION_TITLE,
        UNSAVED_CHANGES_PROMPT,
        UNSAVED_DISCARD_LABEL,
        SetreniDialog,
        _SAVE_CLOSE_LABEL,
    )
    from moduly.ukoly.modely.task import Task

KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
_PROMPT = "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close"
_INFO = "moduly.kniha_urazu.ui.setreni.setreni_dialog._exec_message_box"
_WARNING = "moduly.kniha_urazu.ui.setreni.setreni_dialog.QMessageBox.warning"
_SAVE = (
    "moduly.kniha_urazu.ui.setreni.setreni_dialog."
    "investigation_service.save_zajisteni_dukazu"
)


class KuEditorSave2TestCase(unittest.TestCase):
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

    def _open(self, accident) -> SetreniDialog:
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        dialog.show()
        self.app.processEvents()
        return dialog

    def _close(self, dialog: SetreniDialog) -> None:
        dialog._closing = True
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def _raw(self, accident_id: int) -> str:
        investigation = investigation_service.get_or_create(accident_id)
        return getattr(investigation, "zajisteni_dukazu_json", "") or ""

    def _saved(self, accident_id: int) -> dict:
        raw = self._raw(accident_id)
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _notice(self, dialog: SetreniDialog) -> dict:
        candidates = list(dialog.admin_ohlaseni_rows) + list(dialog._admin_all_zaslani_rows())
        for row in candidates:
            if not dialog._admin_row_relevant(row):
                continue
            if row.get("upresneni") is None or row.get("datum") is None or row.get("cas") is None:
                continue
            return row
        self.fail("editor nemá žádné viditelné oznámení")

    def _fill_notice(self, dialog: SetreniDialog, *, note: str, when: date) -> str:
        row = self._notice(dialog)
        key = row["key"]
        dialog._set_date_widget(row["datum"], when)
        row["cas"].setText("08:30")
        method = self._choose_method(dialog, row)
        row["upresneni"].setText(note)
        dialog.admin_duvod_pozde.setText("pozdní ohlášení směny")
        row["_expected_method"] = method
        return key

    def _choose_method(self, dialog: SetreniDialog, row: dict) -> str:
        box = row.get("zpusob")
        if box is None:
            return ""
        labels = [button.text() for button in box.findChildren(QRadioButton)]
        if not labels:
            return ""
        choice = "E-mail" if "E-mail" in labels else labels[0]
        dialog._set_radio_choice(box, choice)
        return choice

    def _saved_notice(self, accident_id: int, key: str) -> dict:
        data = self._saved(accident_id)
        for bucket in ("admin_ohlaseni", "admin_zaslani"):
            for row in data.get(bucket) or []:
                if row.get("key") == key:
                    return row
        return {}

    def _assert_unique_notices(self, accident_id: int) -> None:
        data = self._saved(accident_id)
        for bucket in ("admin_ohlaseni", "admin_zaslani"):
            keys = [row.get("key") for row in data.get(bucket) or [] if row.get("key")]
            self.assertEqual(keys, list(dict.fromkeys(keys)), bucket)

    def _task_titles(self) -> list[str]:
        with get_session() as session:
            return [row.title for row in session.query(Task).all()]

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(_INFO, side_effect=_exec):
            action()
        return shown

    def test_footer_and_save_keeps_editor_open(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        try:
            self.assertEqual(dialog._editor.save_button.text(), EDITOR_SAVE_LABEL)
            self.assertEqual(dialog._save_close_btn.text(), _SAVE_CLOSE_LABEL)
            self.assertEqual(dialog._editor.close_button.text(), EDITOR_CLOSE_LABEL)
            when = date.today() - timedelta(days=12)
            key = self._fill_notice(dialog, note="datová zpráva", when=when)
            shown = self._run(dialog._editor.save_button.click)
            self.assertTrue(dialog.isVisible())
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertTrue(dialog.was_saved)
            self.assertEqual(len(shown), 1)
            self.assertEqual(shown[0].windowTitle(), SAVE_CONFIRMATION_TITLE)
            self.assertEqual(shown[0].text(), SAVE_CONFIRMATION_TEXT)
            saved = self._saved_notice(accident.id, key)
            self.assertEqual(saved.get("datum"), when.isoformat())
            self.assertEqual(saved.get("cas"), "08:30")
            self.assertEqual(saved.get("upresneni"), "datová zpráva")
            self.assertEqual(self._saved(accident.id).get("admin_duvod_pozde"), "pozdní ohlášení směny")
        finally:
            self._close(dialog)

    def test_save_and_close_closes_only_after_success(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        when = date.today() - timedelta(days=11)
        key = self._fill_notice(dialog, note="odesláno poště", when=when)
        shown = self._run(dialog._save_close_btn.click)
        self.assertEqual(shown, [])
        self.assertFalse(dialog.isVisible())
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertTrue(dialog.was_saved)
        saved = self._saved_notice(accident.id, key)
        self.assertEqual(saved.get("upresneni"), "odesláno poště")
        self.assertEqual(saved.get("datum"), when.isoformat())
        dialog.deleteLater()

    def test_close_without_changes_does_not_prompt_or_write(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        before = self._raw(accident.id)
        with patch(_PROMPT) as prompt:
            dialog._editor.close_button.click()
        prompt.assert_not_called()
        self.assertFalse(dialog.isVisible())
        self.assertFalse(dialog.was_saved)
        self.assertEqual(self._raw(accident.id), before)
        dialog.deleteLater()

    def test_close_with_unsaved_changes_can_save(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        when = date.today() - timedelta(days=9)
        key = self._fill_notice(dialog, note="uložit při zavření", when=when)
        with patch(_PROMPT, return_value="save") as prompt, patch(_INFO) as info:
            dialog._editor.close_button.click()
        info.assert_not_called()
        self.assertEqual(prompt.call_args.kwargs["text"], UNSAVED_CHANGES_PROMPT)
        self.assertEqual(prompt.call_args.kwargs["discard_label"], UNSAVED_DISCARD_LABEL)
        self.assertFalse(dialog.isVisible())
        self.assertTrue(dialog.was_saved)
        self.assertEqual(self._saved_notice(accident.id, key).get("upresneni"), "uložit při zavření")
        dialog.deleteLater()

    def test_cancel_close_keeps_editor_open(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        try:
            before = self._raw(accident.id)
            self._fill_notice(dialog, note="zatím ne", when=date.today() - timedelta(days=8))
            with patch(_PROMPT, return_value="cancel"):
                dialog._editor.close_button.click()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.was_saved)
            self.assertEqual(self._raw(accident.id), before)

            event = QKeyEvent(
                QEvent.Type.KeyPress,
                Qt.Key.Key_Escape,
                Qt.KeyboardModifier.NoModifier,
            )
            with patch(_PROMPT, return_value="cancel") as prompt:
                handled = dialog._editor.eventFilter(dialog, event)
            prompt.assert_called_once()
            self.assertTrue(handled)
            self.assertTrue(dialog.isVisible())
            self.assertEqual(self._raw(accident.id), before)
        finally:
            self._close(dialog)

    def test_discard_drops_changes(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        before = self._raw(accident.id)
        self._fill_notice(dialog, note="zahodit", when=date.today() - timedelta(days=7))
        with patch(_PROMPT, return_value="discard"):
            dialog._editor.close_button.click()
        self.assertFalse(dialog.isVisible())
        self.assertFalse(dialog.was_saved)
        self.assertEqual(self._raw(accident.id), before)
        dialog.deleteLater()

        dialog = self._open(accident)
        self._fill_notice(dialog, note="křížek zahodí", when=date.today() - timedelta(days=6))
        event = QCloseEvent()
        with patch(_PROMPT, return_value="discard"):
            dialog._editor.eventFilter(dialog, event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(self._raw(accident.id), before)
        self._close(dialog)

    def test_save_error_keeps_editor_open(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        try:
            before = self._raw(accident.id)
            self._fill_notice(dialog, note="chyba zápisu", when=date.today() - timedelta(days=5))
            with (
                patch(_SAVE, side_effect=RuntimeError("disk")),
                patch(_WARNING) as warning,
            ):
                self._run(dialog._editor.save_button.click)
            warning.assert_called_once()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.was_saved)
            self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
            self.assertEqual(self._raw(accident.id), before)

            with (
                patch(_PROMPT, return_value="save"),
                patch(_SAVE, side_effect=RuntimeError("disk")),
                patch(_WARNING) as warning,
            ):
                dialog._save_close_btn.click()
            warning.assert_called_once()
            self.assertTrue(dialog.isVisible())
            self.assertFalse(dialog.was_saved)
            self.assertEqual(self._raw(accident.id), before)
        finally:
            self._close(dialog)

    def test_repeated_save_does_not_duplicate(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        try:
            when = date.today() - timedelta(days=4)
            key = self._fill_notice(dialog, note="první zápis", when=when)
            real_save = investigation_service.save_zajisteni_dukazu
            calls: list[int] = []

            def wrapped(*args, **kwargs):
                calls.append(1)
                return real_save(*args, **kwargs)

            with patch(_SAVE, side_effect=wrapped):
                self._run(dialog._editor.save_button.click)
                self.assertEqual(len(calls), 1)
                self._run(dialog._editor.save_button.click)
                self.assertEqual(len(calls), 1)
                titles = self._task_titles()
                row = self._notice_by_key(dialog, key)
                row["upresneni"].setText("druhý zápis")
                self._run(dialog._editor.save_button.click)
                self.assertEqual(len(calls), 2)

            self._assert_unique_notices(accident.id)
            self.assertEqual(self._saved_notice(accident.id, key).get("upresneni"), "druhý zápis")
            self.assertEqual(self._task_titles(), titles)
            self.assertEqual(len(titles), len(set(titles)))
        finally:
            self._close(dialog)

    def test_reopen_keeps_individual_notice_fields(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        when = date.today() - timedelta(days=3)
        key = self._fill_notice(dialog, note="podklady odeslány", when=when)
        method = self._notice_by_key(dialog, key).get("_expected_method", "")
        self._run(dialog._save_and_close)
        self.assertFalse(dialog.isVisible())
        dialog.deleteLater()

        again = self._open(accident)
        try:
            row = self._notice_by_key(again, key)
            self.assertEqual(again._date_to_json(row["datum"]), when.isoformat())
            self.assertEqual(row["cas"].text(), "08:30")
            self.assertEqual(row["upresneni"].text(), "podklady odeslány")
            if method:
                self.assertEqual(again._radio_choice_value(row["zpusob"]), method)
            self.assertEqual(again.admin_duvod_pozde.text(), "pozdní ohlášení směny")
            self.assertFalse(again._is_dirty())
        finally:
            self._close(again)

    def _notice_by_key(self, dialog: SetreniDialog, key: str) -> dict:
        for row in list(dialog.admin_ohlaseni_rows) + list(dialog._admin_all_zaslani_rows()):
            if row.get("key") == key:
                return row
        self.fail(f"oznámení {key} po znovuotevření chybí")
