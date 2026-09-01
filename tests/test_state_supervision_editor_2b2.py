"""STATE-SUPERVISION-EDITOR-2B2: předmět a příprava kontroly."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QTextEdit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-editor-2b2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_SAVE_AND_CLOSE,
        AUTHORITY_REQUIRED_MESSAGE,
        LABEL_INITIAL_INFORMATION,
        LABEL_PREPARATION_NOTE,
        LABEL_SUBJECT,
        TAB_ANNOUNCEMENT,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


def _count_supervisions() -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM state_supervisions").fetchone()[0])
    finally:
        conn.close()


_CZECH_SUBJECT = "Kontrola skladování chemických látek\nv provozovně Žďár."
_CZECH_INITIAL = "Inspektor se zaměří na BL a školení.\nChce ověřit evidenci."
_CZECH_PREPARATION = "Připravit BL, prezenční listiny\na doprovod mistra."


class StateSupervisionEditor2b2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.workplace = settings_service.save_workplace(
            name=f"SD-2B2-{self.marker}",
            address="Ulice 2",
            active=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def _create(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _tab_titles(self, dialog: StateSupervisionEditorDialog) -> list[str]:
        return [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]

    def test_01_three_tabs_in_order(self) -> None:
        dialog = StateSupervisionEditorDialog()
        titles = self._tab_titles(dialog)
        self.assertEqual(
            titles,
            [TAB_ANNOUNCEMENT, TAB_SUBJECT_PREPARATION, TAB_COURSE, TAB_CONCLUSION],
        )
        self.assertEqual(dialog.tabs.count(), 4)
        dialog.close()

    def test_02_three_multiline_fields(self) -> None:
        dialog = StateSupervisionEditorDialog()
        for widget, label in (
            (dialog.subject_edit, LABEL_SUBJECT),
            (dialog.initial_information_edit, LABEL_INITIAL_INFORMATION),
            (dialog.preparation_note_edit, LABEL_PREPARATION_NOTE),
        ):
            self.assertIsInstance(widget, QTextEdit, label)
            self.assertFalse(widget.acceptRichText())
            self.assertGreaterEqual(widget.minimumHeight(), 90)
            self.assertTrue(widget.lineWrapMode())
        dialog.close()

    def test_03_load_existing_texts(self) -> None:
        record = self._create(
            subject=_CZECH_SUBJECT,
            initial_information=_CZECH_INITIAL,
            preparation_note=_CZECH_PREPARATION,
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertEqual(dialog.subject_edit.toPlainText(), _CZECH_SUBJECT)
        self.assertEqual(dialog.initial_information_edit.toPlainText(), _CZECH_INITIAL)
        self.assertEqual(dialog.preparation_note_edit.toPlainText(), _CZECH_PREPARATION)
        dialog.close()

    def test_04_create_with_second_tab_texts(self) -> None:
        before = _count_supervisions()
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"KHS {self.marker}")
        dialog.workplace_selector.set_workplace_id(self.workplace.id)
        dialog.subject_edit.setPlainText(_CZECH_SUBJECT)
        dialog.initial_information_edit.setPlainText(_CZECH_INITIAL)
        dialog.preparation_note_edit.setPlainText(_CZECH_PREPARATION)
        self.assertTrue(self._save(dialog))
        self.assertEqual(_count_supervisions(), before + 1)
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.subject, _CZECH_SUBJECT)
        self.assertEqual(loaded.initial_information, _CZECH_INITIAL)
        self.assertEqual(loaded.preparation_note, _CZECH_PREPARATION)
        self.assertEqual(loaded.workplace_id, self.workplace.id)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()

    def test_05_update_existing_and_reopen(self) -> None:
        record = self._create(subject="Původní předmět")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.subject_edit.setPlainText("Upravený předmět")
        dialog.initial_information_edit.setPlainText("Nová informace od inspektora")
        dialog.preparation_note_edit.setPlainText("Zajistit doprovod")
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

        reopened = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(reopened.subject_edit.toPlainText(), "Upravený předmět")
        self.assertEqual(
            reopened.initial_information_edit.toPlainText(),
            "Nová informace od inspektora",
        )
        self.assertEqual(reopened.preparation_note_edit.toPlainText(), "Zajistit doprovod")
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.subject, "Upravený předmět")
        reopened.close()

    def test_06_empty_values_and_clear_saved_text(self) -> None:
        record = self._create(
            subject="Ke smazání",
            initial_information="Také pryč",
            preparation_note="I toto",
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.subject_edit.clear()
        dialog.initial_information_edit.setPlainText("")
        dialog.preparation_note_edit.setPlainText("   ")
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertIsNone(loaded.subject)
        self.assertIsNone(loaded.initial_information)
        self.assertIsNone(loaded.preparation_note)
        dialog.close()

        empty_new = StateSupervisionEditorDialog()
        empty_new.authority_combo.setCurrentText(f"Prázdná {self.marker}")
        self.assertTrue(self._save(empty_new))
        created = state_supervision_service.get_supervision(empty_new.supervision_id)
        self.assertIsNone(created.subject)
        self.assertIsNone(created.initial_information)
        self.assertIsNone(created.preparation_note)
        empty_new.close()

    def test_07_dirty_revert_tab_switch_and_baseline(self) -> None:
        record = self._create(subject="Baseline předmět")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.setCurrentIndex(0)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.subject_edit.setPlainText("Změna")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog.subject_edit.setPlainText("Baseline předmět")
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.preparation_note_edit.setPlainText("Nová příprava")
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.preparation_note_edit.setPlainText("Další úprava")
        self.assertTrue(dialog._editor.is_dirty())
        dialog.close()

    def test_08_save_and_close_and_discard(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        dialog.subject_edit.setPlainText("Předmět k zavření")
        self.assertEqual(dialog._save_close_btn.text(), ACTION_SAVE_AND_CLOSE)
        dialog._save_and_close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.subject, "Předmět k zavření")

        record = self._create(subject="Ponechat")
        editor = StateSupervisionEditorDialog(supervision_id=record.id)
        editor.subject_edit.setPlainText("Zahodit")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(editor._editor.request_close())
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).subject,
            "Ponechat",
        )
        editor.close()

    def test_09_save_error_keeps_texts_and_dirty(self) -> None:
        record = self._create(subject="Původní")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.subject_edit.setPlainText("Rozepsaný předmět")
        dialog.initial_information_edit.setPlainText("Rozepsaná informace")
        with patch.object(
            state_supervision_service,
            "update_supervision",
            side_effect=RuntimeError("umělá chyba"),
        ):
            with self.assertLogs(
                "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                level="ERROR",
            ):
                with patch.object(QMessageBox, "warning"):
                    self.assertFalse(self._save(dialog))
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(dialog.subject_edit.toPlainText(), "Rozepsaný předmět")
        self.assertEqual(
            dialog.initial_information_edit.toPlainText(),
            "Rozepsaná informace",
        )
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).subject,
            "Původní",
        )
        dialog.close()

    def test_10_authority_validation_still_applies(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.subject_edit.setPlainText("Bez orgánu")
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(dialog._persist())
            self.assertIn(AUTHORITY_REQUIRED_MESSAGE, warning.call_args.args)
        dialog.close()

    def test_11_agenda_still_has_four_tabs(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        page.close()


if __name__ == "__main__":
    unittest.main()
