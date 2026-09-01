"""STATE-SUPERVISION-EDITOR-2B1: ohlášení a zahájení kontroly."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMessageBox,
    QPushButton,
    QTabWidget,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="state-supervision-editor-2b1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.editor_dialog_controller import EditorDialogController
    from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
    from core.widgets.workplace_selector import WorkplaceSelector
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        ACTION_EDIT,
        ACTION_NEW,
        ACTION_SAVE_AND_CLOSE,
        AUTHORITY_REQUIRED_MESSAGE,
        AUTHORITY_SUGGESTIONS,
        COL_STATUS,
        DEFAULT_STATUS,
        DIALOG_TITLE_NEW,
        ENDED_BEFORE_STARTED_MESSAGE,
        NOTIFICATION_METHOD_DATA_BOX,
        NOTIFICATION_METHOD_EMAIL,
        NOTIFICATION_METHOD_EMPTY_LABEL,
        NOTIFICATION_METHOD_IN_PERSON,
        NOTIFICATION_METHOD_OTHER,
        NOTIFICATION_METHOD_PHONE,
        NOTIFICATION_METHOD_WRITTEN,
        STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS,
        STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER,
        STATE_SUPERVISION_STATUS_LABELS,
        STATE_SUPERVISION_STATUS_ORDER,
        STATUS_ANNOUNCED,
        STATUS_IN_PROGRESS,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab


def _count_supervisions() -> int:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM state_supervisions").fetchone()[0])
    finally:
        conn.close()


def _ids() -> list[int]:
    db = storage_module.storage_service.database_path
    conn = sqlite3.connect(str(db))
    try:
        return [
            int(row[0])
            for row in conn.execute("SELECT id FROM state_supervisions ORDER BY id")
        ]
    finally:
        conn.close()


class StateSupervisionEditor2b1TestCase(unittest.TestCase):
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
            name=f"SD-Editor-{self.marker}",
            address=f"Adresa {self.marker}",
            active=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def _create(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _visible_ids(self, tab: StateSupervisionTab) -> list[int]:
        ids = []
        for row in range(tab.table.rowCount()):
            if tab.table.isRowHidden(row):
                continue
            item = tab.table.item(row, COL_STATUS)
            ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def test_01_overview_new_edit_and_doubleclick(self) -> None:
        record = self._create()
        tab = StateSupervisionTab()
        self.assertEqual(tab.new_btn.text(), ACTION_NEW)
        self.assertEqual(tab.edit_btn.text(), ACTION_EDIT)
        self.assertFalse(tab.edit_btn.isEnabled())

        opened: list[tuple[type, int | None]] = []

        def fake_exec(dialog):
            opened.append((type(dialog), dialog.supervision_id))
            return QDialog.DialogCode.Rejected

        with patch(
            "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
            side_effect=fake_exec,
        ):
            tab.new_btn.click()
            self.assertEqual(opened[-1], (StateSupervisionEditorDialog, None))

            tab.table.select_by_id(record.id)
            self.assertTrue(tab.edit_btn.isEnabled())
            tab.edit_btn.click()
            self.assertEqual(opened[-1], (StateSupervisionEditorDialog, record.id))

            index = tab.table.model().index(tab.table.currentRow(), 0)
            tab.table.doubleClicked.emit(index)
            self.assertEqual(opened[-1], (StateSupervisionEditorDialog, record.id))

        tab.close()

    def test_02_overview_refresh_and_restore_selection(self) -> None:
        existing = self._create(authority_name=f"Existující {self.marker}")
        tab = StateSupervisionTab()
        tab.text_filter.search_edit.setText(self.marker)

        def create_via_editor(dialog):
            dialog.authority_combo.setCurrentText(f"Nová {self.marker}")
            self._save(dialog)
            return QDialog.DialogCode.Accepted

        with patch(
            "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
            side_effect=create_via_editor,
        ):
            tab.new_supervision()

        created_id = tab.table.selected_supervision_id()
        self.assertIsNotNone(created_id)
        self.assertNotEqual(created_id, existing.id)
        self.assertIn(created_id, self._visible_ids(tab))

        def edit_via_editor(dialog):
            dialog.ico_edit.setText("12345678")
            self._save(dialog)
            return QDialog.DialogCode.Accepted

        with patch(
            "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
            side_effect=edit_via_editor,
        ):
            tab.edit_selected()

        self.assertEqual(tab.table.selected_supervision_id(), created_id)
        loaded = state_supervision_service.get_supervision(created_id)
        self.assertEqual(loaded.authority_ico, "12345678")
        tab.close()

    def test_03_new_default_status_and_required_authority(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertEqual(dialog.windowTitle(), DIALOG_TITLE_NEW)
        self.assertEqual(dialog.status_combo.currentData(), STATUS_ANNOUNCED)
        self.assertEqual(dialog.status_combo.currentText(), "Ohlášena")
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertFalse(dialog._save_close_btn.isEnabled())
        self.assertEqual(dialog._save_close_btn.text(), ACTION_SAVE_AND_CLOSE)
        self.assertEqual(dialog.tabs.count(), 5)
        self.assertEqual(dialog.tabs.tabText(0), TAB_ANNOUNCEMENT)
        self.assertEqual(dialog.tabs.tabText(1), TAB_SUBJECT_PREPARATION)
        extra_titles = [
            dialog.tabs.tabText(index) for index in range(dialog.tabs.count())
        ]
        self.assertIn("Průběh kontroly", extra_titles)
        self.assertIn(TAB_CONCLUSION, extra_titles)
        self.assertIn(TAB_ATTACHMENTS, extra_titles)

        before = _count_supervisions()
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(dialog._persist())
            warning.assert_called()
            self.assertIn(AUTHORITY_REQUIRED_MESSAGE, warning.call_args.args)
        self.assertEqual(_count_supervisions(), before)
        dialog.close()

    def test_04_first_save_creates_second_updates_same_id(self) -> None:
        before = _count_supervisions()
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        self.assertTrue(dialog._editor.save_button.isEnabled())
        self.assertTrue(self._save(dialog))
        first_id = dialog.supervision_id
        self.assertIsNotNone(first_id)
        self.assertEqual(_count_supervisions(), before + 1)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.file_number_edit.setText("ČJ/2026/1")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save(dialog))
        self.assertEqual(dialog.supervision_id, first_id)
        self.assertEqual(_count_supervisions(), before + 1)
        loaded = state_supervision_service.get_supervision(first_id)
        self.assertEqual(loaded.file_number, "ČJ/2026/1")
        self.assertEqual(loaded.authority_name, f"OIP {self.marker}")
        dialog.close()

    def test_05_save_and_close_creates_one_record(self) -> None:
        before = _count_supervisions()
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"HZS {self.marker}")
        dialog._save_and_close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(_count_supervisions(), before + 1)
        self.assertEqual(_ids().count(dialog.supervision_id), 1)

    def test_06_existing_load_clean_dirty_revert_and_reopen(self) -> None:
        stamp = datetime(2026, 3, 10, 9, 15, 0)
        record = self._create(
            authority_ico="87654321",
            authority_address="Praha 1",
            workplace_id=self.workplace.id,
            status=STATUS_IN_PROGRESS,
            notification_method=NOTIFICATION_METHOD_EMAIL,
            announced_at=stamp,
            file_number="ČJ-1",
            notification_note="Původní poznámka",
            planned_start_at=datetime(2026, 4, 1, 8, 0, 0),
            planned_start_place="Vrátnice",
            planned_control_place="Výroba",
            started_at=stamp,
            ended_at=datetime(2026, 3, 10, 15, 0, 0),
            trade_union_notified_at=datetime(2026, 3, 9, 14, 0, 0),
            management_notified_at=datetime(2026, 3, 9, 15, 30, 0),
            power_of_attorney_required=True,
            power_of_attorney_note="Zmocněnec Novák",
            subject="Předmět mimo tento krok",
        )
        before = _count_supervisions()
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(_count_supervisions(), before)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertEqual(dialog.authority_combo.currentText(), record.authority_name)
        self.assertEqual(dialog.ico_edit.text(), "87654321")
        self.assertEqual(dialog.address_edit.text(), "Praha 1")
        self.assertEqual(dialog.workplace_selector.current_workplace_id(), self.workplace.id)
        self.assertEqual(dialog.status_combo.currentData(), STATUS_IN_PROGRESS)
        self.assertEqual(dialog.notification_method_combo.currentData(), NOTIFICATION_METHOD_EMAIL)
        self.assertEqual(dialog.announced_at_edit.get_datetime(), stamp)
        self.assertEqual(dialog.file_number_edit.text(), "ČJ-1")
        self.assertEqual(dialog.notification_note_edit.toPlainText(), "Původní poznámka")
        self.assertEqual(dialog.planned_start_place_edit.text(), "Vrátnice")
        self.assertEqual(dialog.planned_control_place_edit.text(), "Výroba")
        self.assertEqual(dialog.started_at_edit.get_datetime(), stamp)
        self.assertTrue(dialog.power_of_attorney_checkbox.isChecked())
        self.assertEqual(dialog.power_of_attorney_note_edit.toPlainText(), "Zmocněnec Novák")

        dialog.file_number_edit.setText("ČJ-2")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog.file_number_edit.setText("ČJ-1")
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())

        dialog.file_number_edit.setText("ČJ-uloženo")
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()

        reopened = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(reopened.file_number_edit.text(), "ČJ-uloženo")
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.subject, "Předmět mimo tento krok")
        self.assertIsNone(loaded.closed_at)
        reopened.close()

    def test_07_close_save_discard_cancel_and_error_keeps_dirty(self) -> None:
        record = self._create()
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.notification_note_edit.setPlainText("Rozepsaná změna")
        self.assertTrue(dialog._editor.is_dirty())

        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="cancel",
        ):
            self.assertFalse(dialog._editor.request_close())
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(
            state_supervision_service.get_supervision(record.id).notification_note,
            None,
        )

        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._editor.request_close())
        self.assertIsNone(
            state_supervision_service.get_supervision(record.id).notification_note
        )

        dialog.notification_note_edit.setPlainText("Změna k chybě")
        with patch.object(
            state_supervision_service,
            "update_supervision",
            side_effect=RuntimeError("umělá chyba"),
        ):
            with self.assertLogs(
                "moduly.statni_dozor.ui.state_supervision_editor_dialog",
                level="ERROR",
            ):
                with patch.object(QMessageBox, "warning") as warning:
                    self.assertFalse(self._save(dialog))
                    warning.assert_called()
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(
            dialog.notification_note_edit.toPlainText(),
            "Změna k chybě",
        )
        self.assertIsNone(
            state_supervision_service.get_supervision(record.id).notification_note
        )
        dialog.close()

        close_dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        close_dialog.file_number_edit.setText("uložit-při-zavření")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            self.assertTrue(close_dialog._editor.request_close())
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.file_number, "uložit-při-zavření")
        close_dialog.close()

    def test_08_statuses_methods_custom_authority_and_workplace(self) -> None:
        dialog = StateSupervisionEditorDialog()
        status_codes = [
            dialog.status_combo.itemData(index)
            for index in range(dialog.status_combo.count())
        ]
        self.assertEqual(status_codes, list(STATE_SUPERVISION_STATUS_ORDER))
        self.assertEqual(len(status_codes), 9)
        for status in STATE_SUPERVISION_STATUS_ORDER:
            self.assertEqual(
                dialog.status_combo.itemText(status_codes.index(status)),
                STATE_SUPERVISION_STATUS_LABELS[status],
            )

        method_codes = [
            dialog.notification_method_combo.itemData(index)
            for index in range(dialog.notification_method_combo.count())
        ]
        self.assertEqual(method_codes[0], None)
        self.assertEqual(
            dialog.notification_method_combo.itemText(0),
            NOTIFICATION_METHOD_EMPTY_LABEL,
        )
        self.assertEqual(method_codes[1:], list(STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER))
        phone_index = method_codes.index(NOTIFICATION_METHOD_PHONE)
        self.assertEqual(
            dialog.notification_method_combo.itemText(phone_index),
            STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS[NOTIFICATION_METHOD_PHONE],
        )
        self.assertEqual(
            dialog.notification_method_combo.itemText(phone_index),
            "Telefonicky",
        )
        for method in (
            NOTIFICATION_METHOD_EMAIL,
            NOTIFICATION_METHOD_DATA_BOX,
            NOTIFICATION_METHOD_WRITTEN,
            NOTIFICATION_METHOD_IN_PERSON,
            NOTIFICATION_METHOD_OTHER,
        ):
            self.assertIn(method, method_codes)

        for suggestion in AUTHORITY_SUGGESTIONS:
            self.assertGreaterEqual(dialog.authority_combo.findText(suggestion), 0)
        self.assertIsInstance(dialog.workplace_selector, WorkplaceSelector)
        self.assertTrue(dialog.authority_combo.isEditable())

        dialog.authority_combo.setCurrentText("OIP Praha – oblastní inspektorát")
        dialog.ico_edit.setText("00012345")
        dialog.address_edit.setText("Kolbenova 1, Praha")
        dialog.workplace_selector.set_workplace_id(self.workplace.id)
        dialog.notification_method_combo.setCurrentIndex(phone_index)
        dialog.notification_note_edit.setPlainText(
            "Žluťoučký kůň\núpěl ďábelské ódy."
        )
        dialog.power_of_attorney_checkbox.setChecked(True)
        dialog.power_of_attorney_note_edit.setPlainText("Připravuje právní úsek")
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.authority_name, "OIP Praha – oblastní inspektorát")
        self.assertEqual(loaded.authority_ico, "00012345")
        self.assertEqual(loaded.authority_address, "Kolbenova 1, Praha")
        self.assertEqual(loaded.workplace_id, self.workplace.id)
        self.assertEqual(loaded.workplace_name_snapshot, self.workplace.name)
        self.assertEqual(loaded.workplace_address_snapshot, self.workplace.address)
        self.assertEqual(loaded.notification_method, NOTIFICATION_METHOD_PHONE)
        self.assertIn("Žluťoučký kůň", loaded.notification_note)
        self.assertTrue(loaded.power_of_attorney_required)
        self.assertEqual(loaded.power_of_attorney_note, "Připravuje právní úsek")
        dialog.close()

        empty = StateSupervisionEditorDialog()
        empty.authority_combo.setCurrentText(f"Bez pracoviště {self.marker}")
        self.assertTrue(self._save(empty))
        loaded_empty = state_supervision_service.get_supervision(empty.supervision_id)
        self.assertIsNone(loaded_empty.workplace_id)
        self.assertEqual(loaded_empty.workplace_name_snapshot, "")
        empty.close()

    def test_09_workplace_snapshot_survives_rename(self) -> None:
        original_name = self.workplace.name
        original_address = self.workplace.address
        record = self._create(workplace_id=self.workplace.id)
        settings_service.save_workplace(
            id=self.workplace.id,
            name=f"Přejmenováno-{self.marker}",
            address="Nová adresa 99",
            active=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(dialog.workplace_selector.current_workplace_id(), self.workplace.id)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.file_number_edit.setText("po-přejmenování")
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.workplace_name_snapshot, original_name)
        self.assertEqual(loaded.workplace_address_snapshot, original_address)
        dialog.close()

    def test_10_nullable_datetime_roundtrip_clear_future_and_order(self) -> None:
        dialog = StateSupervisionEditorDialog()
        for widget in (
            dialog.announced_at_edit,
            dialog.planned_start_at_edit,
            dialog.started_at_edit,
            dialog.ended_at_edit,
            dialog.trade_union_notified_at_edit,
            dialog.management_notified_at_edit,
        ):
            self.assertIsInstance(widget, NullableDateTimeEdit)
            self.assertIsNone(widget.get_datetime())

        announced = datetime(2026, 1, 15, 8, 45, 0)
        planned = datetime(2099, 12, 31, 7, 30, 0)
        started = datetime(2026, 2, 1, 9, 0, 0)
        ended = datetime(2026, 2, 1, 16, 20, 0)
        union_at = datetime(2026, 1, 16, 10, 0, 0)
        management_at = datetime(2026, 1, 16, 11, 15, 0)
        dialog.authority_combo.setCurrentText(f"Čas {self.marker}")
        dialog.announced_at_edit.set_datetime(announced)
        dialog.planned_start_at_edit.set_datetime(planned)
        dialog.started_at_edit.set_datetime(started)
        dialog.ended_at_edit.set_datetime(ended)
        dialog.trade_union_notified_at_edit.set_datetime(union_at)
        dialog.management_notified_at_edit.set_datetime(management_at)
        self.assertTrue(self._save(dialog))
        loaded = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.announced_at, announced)
        self.assertEqual(loaded.planned_start_at, planned)
        self.assertEqual(loaded.started_at, started)
        self.assertEqual(loaded.ended_at, ended)
        self.assertEqual(loaded.trade_union_notified_at, union_at)
        self.assertEqual(loaded.management_notified_at, management_at)
        self.assertIsNone(loaded.closed_at)

        dialog.announced_at_edit.clear()
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save(dialog))
        cleared = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertIsNone(cleared.announced_at)
        self.assertEqual(cleared.planned_start_at, planned)

        dialog.ended_at_edit.set_datetime(datetime(2026, 1, 1, 8, 0, 0))
        before = _count_supervisions()
        with patch.object(QMessageBox, "warning") as warning:
            self.assertFalse(self._save(dialog))
            warning.assert_called()
            self.assertIn(ENDED_BEFORE_STARTED_MESSAGE, warning.call_args.args)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(_count_supervisions(), before)
        self.assertEqual(
            dialog.ended_at_edit.get_datetime(),
            datetime(2026, 1, 1, 8, 0, 0),
        )
        still = state_supervision_service.get_supervision(dialog.supervision_id)
        self.assertEqual(still.ended_at, ended)
        dialog.close()

    def test_11_tab_switch_and_open_do_not_dirty(self) -> None:
        record = self._create()
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.tabs.setCurrentIndex(0)
        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.setCurrentIndex(0)
        dialog.notification_method_combo.showPopup()
        dialog.notification_method_combo.hidePopup()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertNotIn("setEnabled(True)", inspect.getsource(StateSupervisionEditorDialog))
        self.assertIsInstance(dialog._editor, EditorDialogController)
        dialog.close()

    def test_12_uses_service_not_second_sql_path(self) -> None:
        source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertIn("state_supervision_service", source)
        self.assertNotIn("execute(", source)
        self.assertNotIn("LongOperationRunner", source)
        tab_source = inspect.getsource(StateSupervisionTab)
        self.assertNotIn("Odstranit", tab_source)
        self.assertNotIn("Otevřít", tab_source)

    def test_13_agenda_still_has_four_tabs(self) -> None:
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        self.assertIsInstance(page.tabs, QTabWidget)
        buttons = [button.text() for button in page.state_supervision_tab.findChildren(QPushButton)]
        self.assertIn(ACTION_NEW, buttons)
        self.assertIn(ACTION_EDIT, buttons)
        page.close()


if __name__ == "__main__":
    unittest.main()
