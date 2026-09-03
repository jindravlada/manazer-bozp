"""STATE-SUPERVISION-AUTHORITY-SELECTION-UI-8C1: výběr orgánu a pracoviště."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QFormLayout, QMessageBox, QSizePolicy

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-selection-ui-8c1-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
from core.database.database_initializer import initialize_database

initialize_database()

from core.widgets.info_tooltip import wrap_tooltip_text
from moduly.statni_dozor.constants import (
    CATALOG_UNAVAILABLE_EDITOR_TEXT,
    LABEL_AUTHORITY,
    LABEL_AUTHORITY_ADDRESS,
    LABEL_AUTHORITY_OFFICE,
    LABEL_STATUS,
    LABEL_WORKPLACE,
    OFFICE_CATALOG_TOOLTIP,
    TAB_ANNOUNCEMENT,
    TAB_ATTACHMENTS,
    TAB_CONCLUSION,
    TAB_COURSE,
    TAB_SUBJECT_PREPARATION,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    StateSupervisionError,
    state_supervision_service,
)
from moduly.statni_dozor.ui.control_authority_selector import (
    ControlAuthorityOfficeSelector,
    ControlAuthoritySelector,
    authority_display_label,
)
from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
    StateSupervisionEditorDialog,
    _EDITOR_FIELDS,
)
from moduly.statni_dozor.ui.state_supervision_tab import StateSupervisionTab

_HOME_PATCHER.stop()


def _select_id(combo, item_id) -> None:
    index = combo.findData(int(item_id))
    if index < 0:
        raise AssertionError(f"Položka {item_id} není v nabídce.")
    combo.setCurrentIndex(index)


def _combo_ids(combo) -> list[int]:
    values: list[int] = []
    for index in range(combo.count()):
        data = combo.itemData(index)
        if isinstance(data, int):
            values.append(int(data))
    return values


class StateSupervisionAuthoritySelectionUi8c1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_HOME)
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
        self.catalog = control_authority_catalog_service
        self.service = state_supervision_service
        self._warn = patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok)
        self._warn.start()

    def tearDown(self) -> None:
        self._warn.stop()

    def _authority(self, *, suffix: str = "", **fields):
        return self.catalog.create_authority(
            code=f"ui8c1-{suffix or self.marker}-{uuid.uuid4().hex[:4]}",
            name=fields.pop("name", f"Orgán {self.marker}{suffix}"),
            **fields,
        )

    def _office(self, authority_id: int, *, suffix: str = "", **fields):
        return self.catalog.create_office(
            authority_id=authority_id,
            name=fields.pop("name", f"Pracoviště {self.marker}{suffix}"),
            **fields,
        )

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def test_01_header_order_selectors_and_no_ico(self) -> None:
        dialog = StateSupervisionEditorDialog()
        host = dialog.authority_combo.parent()
        form = None
        for index in range(host.layout().count()):
            item = host.layout().itemAt(index)
            if isinstance(item.layout(), QFormLayout):
                form = item.layout()
                break
        self.assertIsInstance(form, QFormLayout)
        labels = [
            form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text()
            for row in range(form.rowCount())
        ]
        self.assertEqual(
            labels,
            [
                f"{LABEL_AUTHORITY}:",
                f"{LABEL_AUTHORITY_OFFICE}:",
                f"{LABEL_AUTHORITY_ADDRESS}:",
                f"{LABEL_WORKPLACE}:",
                f"{LABEL_STATUS}:",
            ],
        )
        self.assertIsInstance(dialog.authority_combo, ControlAuthoritySelector)
        self.assertIsInstance(dialog.office_combo, ControlAuthorityOfficeSelector)
        self.assertTrue(dialog.authority_combo.isEditable())
        self.assertTrue(dialog.office_combo.isEditable())
        self.assertFalse(hasattr(dialog, "ico_edit"))
        self.assertNotIn("authority_ico", _EDITOR_FIELDS)
        self.assertNotIn("authority_ico", inspect.getsource(dialog.get_data))
        self.assertEqual(
            dialog.office_combo.toolTip(),
            wrap_tooltip_text(OFFICE_CATALOG_TOOLTIP),
        )
        self.assertEqual(
            [
                dialog.tabs.tabText(i)
                for i in range(dialog.tabs.count())
            ],
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        dialog.close()

    def test_02_catalog_authority_filters_own_active_offices_without_autoselect(self) -> None:
        first = self._authority(suffix="-a", abbreviation="A1")
        second = self._authority(suffix="-b", abbreviation="A2")
        own_a = self._office(first.id, suffix="-a1", address="Adresa A1")
        own_b = self._office(first.id, suffix="-a2", address="Adresa A2")
        other = self._office(second.id, suffix="-b1", address="Cizí adresa")
        inactive = self._office(first.id, suffix="-off", address="Neaktivní")
        self.catalog.deactivate_office(inactive.id)

        dialog = StateSupervisionEditorDialog()
        authority_index = dialog.authority_combo.findData(first.id)
        self.assertGreaterEqual(authority_index, 0)
        self.assertEqual(
            dialog.authority_combo.itemData(authority_index, Qt.ItemDataRole.UserRole),
            first.id,
        )
        self.assertEqual(
            dialog.authority_combo.itemText(authority_index),
            authority_display_label(first),
        )
        _select_id(dialog.authority_combo, first.id)
        self.assertEqual(dialog.office_combo.currentText(), "")
        self.assertIsNone(dialog.office_combo.currentData())
        self.assertEqual(dialog.get_data()["authority_office_id"], None)
        office_ids = _combo_ids(dialog.office_combo)
        self.assertEqual(set(office_ids), {own_a.id, own_b.id})
        self.assertNotIn(other.id, office_ids)
        self.assertNotIn(inactive.id, office_ids)
        office_index = dialog.office_combo.findData(own_a.id)
        self.assertEqual(
            dialog.office_combo.itemData(office_index, Qt.ItemDataRole.UserRole),
            own_a.id,
        )
        dialog.close()

        empty = self._authority(suffix="-empty")
        dialog = StateSupervisionEditorDialog()
        _select_id(dialog.authority_combo, empty.id)
        self.assertEqual(_combo_ids(dialog.office_combo), [])
        self.assertEqual(dialog.office_combo.currentText(), "")
        self.assertIsNone(dialog.get_data()["authority_office_id"])
        dialog.close()

    def test_03_catalog_office_prefills_snapshot_and_address_not_contacts(self) -> None:
        authority = self._authority(abbreviation="OA")
        office = self._office(
            authority.id,
            address="Kladenská 1",
            phone="111",
            email="a@example.test",
            website="https://example.test",
            territorial_scope="Praha",
        )
        dialog = StateSupervisionEditorDialog()
        _select_id(dialog.authority_combo, authority.id)
        _select_id(dialog.office_combo, office.id)
        data = dialog.get_data()
        self.assertEqual(data["authority_id"], authority.id)
        self.assertEqual(data["authority_name"], authority.name)
        self.assertEqual(data["authority_office_id"], office.id)
        self.assertEqual(data["authority_office_name_snapshot"], office.name)
        self.assertEqual(data["authority_address"], "Kladenská 1")
        self.assertNotIn("authority_ico", data)
        self.assertNotIn("phone", data)
        self.assertNotIn("email", data)
        self.assertNotIn("website", data)
        tooltip = dialog.office_combo.itemData(
            dialog.office_combo.findData(office.id),
            Qt.ItemDataRole.ToolTipRole,
        )
        self.assertIn("Kladenská 1", str(tooltip))
        self.assertIn("Praha", str(tooltip))
        self.assertTrue(self._save(dialog))
        loaded = self.service.get_supervision(dialog.supervision_id)
        self.assertEqual(loaded.authority_id, authority.id)
        self.assertEqual(loaded.authority_name, authority.name)
        self.assertEqual(loaded.authority_office_id, office.id)
        self.assertEqual(loaded.authority_office_name_snapshot, office.name)
        self.assertEqual(loaded.authority_address, "Kladenská 1")
        self.assertIsNone(loaded.authority_ico)
        dialog.close()

    def test_04_manual_authority_and_office_do_not_create_catalog_rows(self) -> None:
        before_auth = len(self.catalog.list_authorities(include_inactive=True))
        before_off = len(self.catalog.list_offices(include_inactive=True))
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"Ruční orgán {self.marker}")
        self.assertEqual(_combo_ids(dialog.office_combo), [])
        dialog.office_combo.setCurrentText(f"Ruční pracoviště {self.marker}")
        dialog.address_edit.setText("Ruční adresa")
        data = dialog.get_data()
        self.assertIsNone(data["authority_id"])
        self.assertEqual(data["authority_name"], f"Ruční orgán {self.marker}")
        self.assertIsNone(data["authority_office_id"])
        self.assertEqual(
            data["authority_office_name_snapshot"],
            f"Ruční pracoviště {self.marker}",
        )
        self.assertTrue(self._save(dialog))
        loaded = self.service.get_supervision(dialog.supervision_id)
        self.assertIsNone(loaded.authority_id)
        self.assertIsNone(loaded.authority_office_id)
        self.assertEqual(loaded.authority_office_name_snapshot, f"Ruční pracoviště {self.marker}")
        self.assertEqual(
            len(self.catalog.list_authorities(include_inactive=True)),
            before_auth,
        )
        self.assertEqual(
            len(self.catalog.list_offices(include_inactive=True)),
            before_off,
        )
        dialog.close()

    def test_05_catalog_authority_with_manual_office(self) -> None:
        authority = self._authority()
        self._office(authority.id, suffix="-cat")
        dialog = StateSupervisionEditorDialog()
        _select_id(dialog.authority_combo, authority.id)
        dialog.office_combo.setCurrentText(f"Vlastní OIP {self.marker}")
        data = dialog.get_data()
        self.assertEqual(data["authority_id"], authority.id)
        self.assertIsNone(data["authority_office_id"])
        self.assertEqual(
            data["authority_office_name_snapshot"],
            f"Vlastní OIP {self.marker}",
        )
        dialog.close()

    def test_06_group_change_clears_foreign_office_keeps_edited_address(self) -> None:
        first = self._authority(suffix="-g1")
        second = self._authority(suffix="-g2")
        office = self._office(first.id, address="Katalogová adresa")
        other = self._office(second.id, address="Jiná adresa")
        dialog = StateSupervisionEditorDialog()
        _select_id(dialog.authority_combo, first.id)
        _select_id(dialog.office_combo, office.id)
        self.assertEqual(dialog.address_edit.text(), "Katalogová adresa")
        dialog.address_edit.setText("Ručně upravená adresa")
        _select_id(dialog.authority_combo, second.id)
        self.assertEqual(dialog.office_combo.currentText(), "")
        self.assertIsNone(dialog.get_data()["authority_office_id"])
        self.assertNotIn(office.id, _combo_ids(dialog.office_combo))
        self.assertIn(other.id, _combo_ids(dialog.office_combo))
        self.assertEqual(dialog.address_edit.text(), "Ručně upravená adresa")
        dialog.close()

        dialog = StateSupervisionEditorDialog()
        _select_id(dialog.authority_combo, first.id)
        _select_id(dialog.office_combo, office.id)
        _select_id(dialog.authority_combo, second.id)
        self.assertEqual(dialog.address_edit.text(), "")
        self.assertIsNone(dialog.get_data()["authority_office_name_snapshot"])
        dialog.close()

    def test_07_legacy_open_is_clean_and_keeps_hidden_ico(self) -> None:
        record = self.service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="87654321",
            authority_address="Historická adresa",
        )
        before = record.updated_at
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        self.assertEqual(dialog.authority_combo.currentText(), f"OIP {self.marker}")
        self.assertEqual(dialog.office_combo.currentText(), "")
        self.assertEqual(dialog.address_edit.text(), "Historická adresa")
        self.assertIsNone(dialog.get_data()["authority_id"])
        self.assertIsNone(dialog.get_data()["authority_office_id"])
        dialog.file_number_edit.setText("ČJ-legacy")
        self.assertTrue(self._save(dialog))
        dialog.close()
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_ico, "87654321")
        self.assertIsNone(loaded.authority_id)
        self.assertIsNone(loaded.authority_office_name_snapshot)
        self.assertEqual(loaded.file_number, "ČJ-legacy")
        self.assertNotEqual(loaded.updated_at, before)
        found = self.service.list_supervisions(query="87654321")
        self.assertIn(record.id, [item.id for item in found])

    def test_08_missing_and_inactive_catalog_keep_ids_and_snapshots(self) -> None:
        authority = self._authority(name=f"Zmizelý {self.marker}")
        office = self._office(authority.id, name=f"Zmizelé pracoviště {self.marker}")
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_id=office.id,
            authority_office_name_snapshot=office.name,
            authority_address="Původní adresa",
        )
        db = storage_module.storage_service.database_path
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "UPDATE state_supervisions SET authority_id = ?, authority_office_id = ? WHERE id = ?",
                (9_991_001, 9_991_002, record.id),
            )
            conn.commit()
        finally:
            conn.close()
        ghost = self.service.get_supervision(record.id)
        dialog = StateSupervisionEditorDialog(supervision_id=ghost.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(dialog.authority_combo.currentText(), authority.name)
        self.assertEqual(dialog.office_combo.currentText(), office.name)
        self.assertEqual(dialog.get_data()["authority_id"], 9_991_001)
        self.assertEqual(dialog.get_data()["authority_office_id"], 9_991_002)
        dialog.file_number_edit.setText("ponechat-vazbu")
        self.assertTrue(self._save(dialog))
        dialog.close()
        loaded = self.service.get_supervision(record.id)
        self.assertEqual(loaded.authority_id, 9_991_001)
        self.assertEqual(loaded.authority_office_id, 9_991_002)
        self.assertEqual(loaded.authority_name, authority.name)
        self.assertEqual(loaded.authority_office_name_snapshot, office.name)

        live = self._authority(name=f"Neaktivní {self.marker}")
        live_office = self._office(live.id, name=f"Neaktivní pracoviště {self.marker}")
        stored = self.service.create_supervision(
            authority_name=live.name,
            authority_id=live.id,
            authority_office_id=live_office.id,
            authority_office_name_snapshot=live_office.name,
        )
        self.catalog.deactivate_office(live_office.id)
        self.catalog.deactivate_authority(live.id)
        dialog = StateSupervisionEditorDialog(supervision_id=stored.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(dialog.authority_combo.currentText(), live.name)
        self.assertEqual(dialog.office_combo.currentText(), live_office.name)
        self.assertEqual(dialog.get_data()["authority_id"], live.id)
        self.assertEqual(dialog.get_data()["authority_office_id"], live_office.id)
        self.assertNotIn(live.id, _combo_ids(dialog.authority_combo))
        self.assertNotIn(live_office.id, _combo_ids(dialog.office_combo))
        dialog.close()

    def test_09_renamed_catalog_keeps_snapshot_until_explicit_reselect(self) -> None:
        authority = self._authority(name=f"Původní název {self.marker}", abbreviation="PN")
        office = self._office(authority.id, name=f"Původní pracoviště {self.marker}")
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_id=office.id,
            authority_office_name_snapshot=office.name,
            authority_address="Adresa snapshot",
        )
        self.catalog.update_authority(authority.id, name=f"Nový název {self.marker}")
        self.catalog.update_office(office.id, name=f"Nové pracoviště {self.marker}")
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(dialog.authority_combo.currentText(), f"Původní název {self.marker}")
        self.assertEqual(dialog.office_combo.currentText(), f"Původní pracoviště {self.marker}")
        self.assertEqual(dialog.get_data()["authority_name"], f"Původní název {self.marker}")
        self.assertEqual(
            dialog.get_data()["authority_office_name_snapshot"],
            f"Původní pracoviště {self.marker}",
        )
        _select_id(dialog.authority_combo, authority.id)
        _select_id(dialog.office_combo, office.id)
        self.assertEqual(dialog.get_data()["authority_name"], f"Nový název {self.marker}")
        self.assertEqual(
            dialog.get_data()["authority_office_name_snapshot"],
            f"Nové pracoviště {self.marker}",
        )
        dialog.close()

    def test_10_open_does_not_write_and_matching_catalog_is_clean(self) -> None:
        authority = self._authority(abbreviation="CL")
        office = self._office(authority.id, address="Katalog 1")
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_id=office.id,
            authority_office_name_snapshot=office.name,
            authority_address=office.address,
        )
        before = (
            record.authority_name,
            record.authority_id,
            record.authority_office_id,
            record.authority_office_name_snapshot,
            record.updated_at,
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(
            dialog.authority_combo.currentText(),
            authority_display_label(authority),
        )
        self.assertEqual(dialog.office_combo.currentText(), office.name)
        dialog.authority_combo.showPopup()
        dialog.authority_combo.hidePopup()
        dialog.office_combo.showPopup()
        dialog.office_combo.hidePopup()
        self.assertFalse(dialog._editor.is_dirty())
        _select_id(dialog.authority_combo, authority.id)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()
        reopened = self.service.get_supervision(record.id)
        self.assertEqual(
            (
                reopened.authority_name,
                reopened.authority_id,
                reopened.authority_office_id,
                reopened.authority_office_name_snapshot,
                reopened.updated_at,
            ),
            before,
        )

    def test_11_dirty_save_revert_and_three_save_paths(self) -> None:
        authority = self._authority(suffix="-d1")
        other = self._authority(suffix="-d2")
        office = self._office(authority.id, address="Dirty adresa")
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
        )
        refreshes: list[int] = []
        dialog = StateSupervisionEditorDialog(
            supervision_id=record.id,
            on_saved=lambda sid: refreshes.append(int(sid)),
        )
        self.assertFalse(dialog._editor.save_button.isEnabled())
        _select_id(dialog.authority_combo, other.id)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        _select_id(dialog.authority_combo, authority.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.office_combo.setCurrentText("Ruční dirty")
        self.assertTrue(dialog._editor.is_dirty())
        dialog.office_combo.setCurrentText("")
        self.assertFalse(dialog._editor.is_dirty())
        dialog.address_edit.setText("Jiná adresa")
        self.assertTrue(dialog._editor.is_dirty())
        dialog.address_edit.setText("")
        self.assertFalse(dialog._editor.is_dirty())
        _select_id(dialog.office_combo, office.id)
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(refreshes, [record.id])
        dialog.close()

        refreshes.clear()
        dialog = StateSupervisionEditorDialog(
            supervision_id=record.id,
            on_saved=lambda sid: refreshes.append(int(sid)),
        )
        dialog.address_edit.setText("Uložit a zavřít")
        dialog._save_and_close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(refreshes, [record.id])
        self.assertEqual(
            self.service.get_supervision(record.id).authority_address,
            "Uložit a zavřít",
        )

        refreshes.clear()
        dialog = StateSupervisionEditorDialog(
            supervision_id=record.id,
            on_saved=lambda sid: refreshes.append(int(sid)),
        )
        dialog.address_edit.setText("Přes prompt")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            dialog._editor._handle_close_clicked()
        self.assertEqual(refreshes, [record.id])
        self.assertEqual(
            self.service.get_supervision(record.id).authority_address,
            "Přes prompt",
        )

    def test_12_bundle_error_keeps_working_state_catalog_error_allows_manual(self) -> None:
        authority = self._authority()
        record = self.service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
        )
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        dialog.office_combo.setCurrentText("Rozpracované")
        dialog.address_edit.setText("Rozpracovaná adresa")
        with patch.object(
            self.service,
            "save_supervision_bundle",
            side_effect=StateSupervisionError("bundle selhal"),
        ):
            self.assertFalse(self._save(dialog))
        self.assertTrue(dialog._editor.is_dirty())
        self.assertEqual(dialog.get_data()["authority_office_name_snapshot"], "Rozpracované")
        self.assertEqual(dialog.address_edit.text(), "Rozpracovaná adresa")
        dialog.close()

        with patch.object(
            self.catalog,
            "list_authorities",
            side_effect=RuntimeError("catalog down"),
        ):
            broken = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(broken.catalog_warning_label.isHidden())
        self.assertIn(CATALOG_UNAVAILABLE_EDITOR_TEXT, broken.catalog_warning_label.text())
        self.assertEqual(broken.authority_combo.currentText(), authority.name)
        broken.authority_combo.setCurrentText(f"Ručně po chybě {self.marker}")
        broken.office_combo.setCurrentText("Ruční pracoviště po chybě")
        self.assertIsNone(broken.get_data()["authority_id"])
        self.assertEqual(
            broken.get_data()["authority_name"],
            f"Ručně po chybě {self.marker}",
        )
        self.assertNotIn("AUTHORITY_SUGGESTIONS", inspect.getsource(StateSupervisionEditorDialog))
        broken.close()

    def test_13_layout_1600_and_1920_and_suggestions_removed(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.show()
        self._app.processEvents()
        for width, height in ((1600, 900), (1920, 1080)):
            dialog.resize(width, height)
            self._app.processEvents()
            self.assertEqual(
                dialog.authority_combo.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Expanding,
            )
            self.assertEqual(
                dialog.office_combo.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Expanding,
            )
            self.assertEqual(
                dialog.address_edit.sizePolicy().horizontalPolicy(),
                QSizePolicy.Policy.Expanding,
            )
            self.assertEqual(dialog.authority_combo.width(), dialog.office_combo.width())
            self.assertEqual(dialog.office_combo.width(), dialog.address_edit.width())
            self.assertGreaterEqual(dialog.authority_combo.width(), 500)
        dialog.close()
        import moduly.statni_dozor.constants as constants_module

        self.assertFalse(hasattr(constants_module, "AUTHORITY_SUGGESTIONS"))
        tab_source = inspect.getsource(StateSupervisionTab)
        self.assertIn("authority_name", tab_source)
        self.assertNotIn("authority_office_name_snapshot", tab_source)


if __name__ == "__main__":
    unittest.main()
