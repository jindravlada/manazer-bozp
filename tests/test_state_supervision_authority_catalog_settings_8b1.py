"""STATE-SUPERVISION-AUTHORITY-CATALOG-SETTINGS-8B1: správa v Nastavení."""

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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

EXPECTED_TAB_TITLES = [
    "THP pracovníci",
    "Osoby",
    "Provozy a pracoviště",
    "Státní dozor",
    "Funkce / role",
    "Ohrožené skupiny",
    "Zaměstnavatel",
]


def _authority_stamps(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        return list(
            conn.execute(
                "SELECT id, code, name, origin, external_key, updated_at, "
                "user_edited_at FROM control_authorities ORDER BY id"
            ).fetchall()
        )
    finally:
        conn.close()


def _supervision_rows(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        return list(
            conn.execute(
                "SELECT id, authority_ico, authority_name, authority_office_id, "
                "updated_at FROM state_supervisions ORDER BY id"
            ).fetchall()
        )
    finally:
        conn.close()


_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-catalog-8b1-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
from core.database.database_initializer import initialize_database

initialize_database()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from core.widgets.filter_bar import FilterBar
from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
from moduly.statni_dozor.constants import (
    AUTHORITY_ORIGIN_BUNDLED,
    AUTHORITY_ORIGIN_MANUAL,
    AUTHORITY_ORIGIN_WEB,
    CATALOG_FILTER_EMPTY_TEXT,
    CATALOG_LOAD_ERROR_TEXT,
    CATALOG_NEW_AUTHORITY_LABEL,
    CATALOG_NEW_OFFICE_LABEL,
    CATALOG_ROW_KIND_AUTHORITY,
    CATALOG_ROW_KIND_OFFICE,
    OFFICE_KIND_REGIONAL,
    TAB_ANNOUNCEMENT,
    TAB_ATTACHMENTS,
    TAB_CONCLUSION,
    TAB_COURSE,
    TAB_SUBJECT_PREPARATION,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogError,
    control_authority_catalog_service,
    slugify_authority_code,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    state_supervision_service,
)
from moduly.statni_dozor.ui.control_authority_catalog_tab import (
    ControlAuthorityCatalogTab,
)
from moduly.statni_dozor.ui.control_authority_dialog import ControlAuthorityDialog
from moduly.statni_dozor.ui.control_authority_office_dialog import (
    ControlAuthorityOfficeDialog,
)
from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
    StateSupervisionEditorDialog,
)

_HOME_PATCHER.stop()


class StateSupervisionAuthorityCatalogSettings8b1TestCase(unittest.TestCase):
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
        self.db = storage_module.storage_service.database_path
        self.catalog = control_authority_catalog_service
        self.marker = uuid.uuid4().hex[:8]
        self.page = NastaveniPage()
        self.tab: ControlAuthorityCatalogTab = self.page.state_supervision_catalog_tab
        self._warn = patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok)
        self._warn.start()

    def tearDown(self) -> None:
        self._warn.stop()
        self.page.close()

    def _select_kind(self, kind: str, record_id: int) -> None:
        self.tab._restore_selection(kind, record_id)
        self.tab.update_buttons()

    def _authority_item(self, code: str):
        authority = self.catalog.get_authority_by_code(code)
        if authority is None:
            return None
        for index in range(self.tab.tree.topLevelItemCount()):
            item = self.tab.tree.topLevelItem(index)
            if (
                item.data(0, Qt.ItemDataRole.UserRole) == authority.id
                and item.data(0, Qt.ItemDataRole.UserRole + 1) == "authority"
            ):
                return item
        return None

    def _visible_office_key(self, external_key: str) -> int | None:
        office = self.catalog.get_office_by_external_key(external_key)
        if office is None:
            return None
        for index in range(self.tab.tree.topLevelItemCount()):
            parent = self.tab.tree.topLevelItem(index)
            if parent.isHidden():
                continue
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.isHidden():
                    continue
                if child.data(0, Qt.ItemDataRole.UserRole) == office.id:
                    return int(office.id)
        return None

    def test_01_settings_tab_order_and_tree(self) -> None:
        titles = [self.page.tabs.tabText(i) for i in range(self.page.tabs.count())]
        self.assertEqual(titles, EXPECTED_TAB_TITLES)
        index = self.page.tabs.indexOf(self.page.workers_tab)
        self.assertEqual(index, 0)
        catalog_index = self.page.tabs.indexOf(self.tab)
        self.assertEqual(catalog_index, 3)
        self.assertEqual(self.page.tabs.tabText(catalog_index), "Státní dozor")
        self.assertEqual(self.tab.tree.topLevelItemCount(), 5)
        office_count = sum(
            self.tab.tree.topLevelItem(i).childCount()
            for i in range(self.tab.tree.topLevelItemCount())
        )
        self.assertEqual(office_count, 46)
        parent = self.tab.tree.topLevelItem(0)
        self.assertEqual(parent.text(1), CATALOG_ROW_KIND_AUTHORITY)
        self.assertGreater(parent.childCount(), 0)
        self.assertEqual(parent.child(0).text(1), CATALOG_ROW_KIND_OFFICE)
        self.assertFalse(self.tab.show_inactive.isChecked())
        self.assertIsInstance(self.tab.filter_bar, FilterBar)
        self.assertEqual(self.tab.new_authority_button.text(), CATALOG_NEW_AUTHORITY_LABEL)
        self.assertEqual(self.tab.new_office_button.text(), CATALOG_NEW_OFFICE_LABEL)
        source = inspect.getsource(ControlAuthorityCatalogTab)
        self.assertNotIn("ico_edit", source)
        self.assertNotIn("IČ", source)
        self.assertNotIn("Zkontrolovat na webu", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("urlopen", source)

    def test_02_search_parent_child_and_inactive(self) -> None:
        office = self.catalog.get_office_by_external_key("suip:oip-praha")
        assert office is not None
        self.tab.filter_bar.search_edit.setText("oip praha")
        parent = self._authority_item("suip")
        self.assertIsNotNone(parent)
        assert parent is not None
        self.assertFalse(parent.isHidden())
        matching_children = [
            parent.child(i)
            for i in range(parent.childCount())
            if not parent.child(i).isHidden()
        ]
        self.assertTrue(matching_children)
        self.assertTrue(
            any("Prahu" in child.text(0) for child in matching_children)
        )

        self.tab.filter_bar.search_edit.setText("suip")
        parent = self._authority_item("suip")
        self.assertIsNotNone(parent)
        assert parent is not None
        self.assertFalse(parent.isHidden())
        visible_children = [
            parent.child(i)
            for i in range(parent.childCount())
            if not parent.child(i).isHidden()
        ]
        self.assertEqual(len(visible_children), 8)

        self.tab.filter_bar.search_edit.clear()
        self.catalog.deactivate_office(office.id)
        self.tab.refresh()
        self.assertIsNone(self._visible_office_key("suip:oip-praha"))
        self.tab.show_inactive.setChecked(True)
        self.assertIsNotNone(self._visible_office_key("suip:oip-praha"))
        self.catalog.reactivate_office(office.id)
        self.tab.show_inactive.setChecked(False)

        self.tab.filter_bar.search_edit.setText("xyz-neexistuje")
        self.assertIn(CATALOG_FILTER_EMPTY_TEXT, self.tab.status_label.text())

    def test_03_open_search_select_do_not_write(self) -> None:
        stamps = _authority_stamps(self.db)
        self.tab.filter_bar.search_edit.setText("khs")
        self.tab.tree.setCurrentItem(self.tab.tree.topLevelItem(2))
        self.tab.filter_bar.search_edit.clear()
        self.page.tabs.setCurrentWidget(self.tab)
        self.assertEqual(_authority_stamps(self.db), stamps)

    def test_04_create_authority_stable_code_and_collision(self) -> None:
        self.assertEqual(slugify_authority_code("SÚIP"), "suip")
        code = self.catalog.allocate_unique_authority_code("SÚIP")
        self.assertEqual(code, "suip-2")
        dialog = ControlAuthorityDialog(self.tab, on_catalog_changed=self.tab._on_catalog_changed)
        dialog.name_edit.setText(f"Nový orgán {self.marker}")
        self.assertTrue(dialog._persist())
        created = next(
            item
            for item in self.catalog.list_authorities(include_inactive=True)
            if self.marker in item.name
        )
        self.assertEqual(created.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertTrue(created.code)
        self.assertEqual(created.code, created.code.lower())
        first_code = created.code
        duplicate = ControlAuthorityDialog(
            self.tab, on_catalog_changed=self.tab._on_catalog_changed
        )
        duplicate.name_edit.setText(created.name)
        self.assertTrue(duplicate._persist())
        codes = [
            item.code
            for item in self.catalog.list_authorities(include_inactive=True)
            if item.name == created.name
        ]
        self.assertEqual(len(codes), 2)
        self.assertNotEqual(codes[0], codes[1])
        self.assertIn(first_code, codes)
        dialog.close()
        duplicate.close()

    def test_05_create_office_under_selected_and_validate(self) -> None:
        suip = self.catalog.get_authority_by_code("suip")
        assert suip is not None
        self._select_kind("authority", int(suip.id))
        self.assertTrue(self.tab.new_office_button.isEnabled())
        dialog = ControlAuthorityOfficeDialog(
            self.tab,
            preselected_authority_id=self.tab._preselected_authority_id(),
            on_catalog_changed=self.tab._on_catalog_changed,
        )
        self.assertEqual(dialog.authority_combo.currentData(), suip.id)
        empty = ControlAuthorityOfficeDialog(self.tab)
        self.assertIsNone(empty.authority_combo.currentData())
        self.assertFalse(empty._persist())
        dialog.name_edit.setText(f"Územní pracoviště {self.marker}")
        dialog.address_edit.setText("Testovací 1")
        dialog.phone_edit.setText("123")
        dialog.email_edit.setText("test@example.com")
        index = dialog.kind_combo.findData(OFFICE_KIND_REGIONAL)
        dialog.kind_combo.setCurrentIndex(index)
        self.assertTrue(dialog._persist())
        created = None
        for office in self.catalog.list_offices(authority_id=suip.id, include_inactive=True):
            if self.marker in office.name:
                created = office
                break
        self.assertIsNotNone(created)
        assert created is not None
        self.assertEqual(created.authority_id, suip.id)
        self.assertEqual(created.office_kind, OFFICE_KIND_REGIONAL)
        dialog.close()
        empty.close()

    def test_06_dirty_baseline_cancel_and_persistence_error(self) -> None:
        suip = self.catalog.get_authority_by_code("suip")
        assert suip is not None
        origin = suip.origin
        external_key = suip.external_key
        dialog = ControlAuthorityDialog(self.tab, authority=suip)
        dialog.show()
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.name_edit.setText("Změněný SÚIP")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertTrue(dialog._editor.save_button.isEnabled())
        dialog.name_edit.setText(suip.name)
        self.assertFalse(dialog._editor.is_dirty())
        dialog.name_edit.setText("Změněný SÚIP")
        with patch.object(
            self.catalog,
            "update_authority",
            side_effect=ControlAuthorityCatalogError("uložení selhalo"),
        ):
            self.assertFalse(dialog._persist())
        self.assertTrue(dialog.isVisible())
        self.assertTrue(dialog._editor.is_dirty())
        reloaded = self.catalog.get_authority(suip.id)
        self.assertEqual(reloaded.origin, origin)
        self.assertEqual(reloaded.external_key, external_key)
        dialog._editor.force_close()

        new_dialog = ControlAuthorityDialog(self.tab)
        new_dialog.name_edit.setText("Dočasný")
        new_dialog.close()
        self.assertIsNone(
            next(
                (
                    item
                    for item in self.catalog.list_authorities(include_inactive=True)
                    if item.name == "Dočasný"
                ),
                None,
            )
        )

    def test_07_manual_edit_keeps_key_open_does_not_change_origin(self) -> None:
        suip = self.catalog.get_authority_by_code("suip")
        assert suip is not None
        key = suip.external_key
        dialog = ControlAuthorityDialog(self.tab, authority=suip)
        dialog.show()
        dialog.close()
        unchanged = self.catalog.get_authority(suip.id)
        self.assertEqual(unchanged.origin, AUTHORITY_ORIGIN_BUNDLED)
        self.assertEqual(unchanged.external_key, key)

        web = self.catalog.create_imported_authority(
            code=f"web-{self.marker}",
            name=f"Web orgán {self.marker}",
            origin=AUTHORITY_ORIGIN_WEB,
            external_key=f"web:{self.marker}",
        )
        edit = ControlAuthorityDialog(
            self.tab,
            authority=web,
            on_catalog_changed=self.tab._on_catalog_changed,
        )
        edit.abbreviation_edit.setText("WEB")
        self.assertTrue(edit._persist())
        updated = self.catalog.get_authority(web.id)
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertEqual(updated.external_key, f"web:{self.marker}")
        self.assertIsNotNone(updated.user_edited_at)
        edit.close()

        bundled_edit = ControlAuthorityDialog(
            self.tab,
            authority=self.catalog.get_authority_by_code("cbu"),
            on_catalog_changed=self.tab._on_catalog_changed,
        )
        cbu = self.catalog.get_authority_by_code("cbu")
        key_cbu = cbu.external_key
        bundled_edit.website_edit.setText("https://cbu.gov.cz")
        self.assertTrue(bundled_edit._persist())
        cbu2 = self.catalog.get_authority_by_code("cbu")
        self.assertEqual(cbu2.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertEqual(cbu2.external_key, key_cbu)
        bundled_edit.close()

    def test_08_deactivate_reactivate_no_cascade(self) -> None:
        office = self.catalog.get_office_by_external_key("khs:praha")
        suip = self.catalog.get_authority_by_code("suip")
        assert office is not None and suip is not None
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="11112222",
        )
        before = _supervision_rows(self.db)
        self._select_kind("office", int(office.id))
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.tab.toggle_selected_active()
        reloaded = self.catalog.get_office(office.id)
        self.assertFalse(reloaded.active)
        parent = self.catalog.get_authority(office.authority_id)
        self.assertTrue(parent.active)
        self._select_kind("office", int(office.id))
        self.tab.show_inactive.setChecked(True)
        self._select_kind("office", int(office.id))
        self.assertEqual(self.tab.toggle_active_button.text(), "Aktivovat")
        self.tab.toggle_selected_active()
        self.assertTrue(self.catalog.get_office(office.id).active)

        self._select_kind("authority", int(suip.id))
        self.assertEqual(self.tab.toggle_active_button.text(), "Deaktivovat")
        self.assertFalse(self.tab.toggle_active_button.isEnabled())
        self.assertTrue(
            self.catalog.get_office_by_external_key("suip:oip-stredocesky").active
        )

        inactive_parent = self.catalog.create_authority(
            code=f"off-{self.marker}",
            name=f"Neaktivní {self.marker}",
        )
        self.catalog.deactivate_authority(inactive_parent.id)
        child = self.catalog.create_office(
            authority_id=inactive_parent.id,
            name=f"Potomek {self.marker}",
            active=False,
        )
        self.tab.show_inactive.setChecked(True)
        self._select_kind("office", int(child.id))
        self.assertFalse(self.tab.toggle_active_button.isEnabled())
        self.assertEqual(_supervision_rows(self.db), before)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.authority_ico, "11112222")

    def test_09_load_error_keeps_other_tabs(self) -> None:
        with patch.object(
            self.catalog,
            "list_authorities",
            side_effect=RuntimeError("catalog down"),
        ):
            self.tab.refresh()
        self.assertIn(CATALOG_LOAD_ERROR_TEXT, self.tab.status_label.text())
        titles = [self.page.tabs.tabText(i) for i in range(self.page.tabs.count())]
        self.assertEqual(titles, EXPECTED_TAB_TITLES)
        self.assertTrue(hasattr(self.page, "worker_table"))
        self.assertTrue(hasattr(self.page, "person_table"))
        self.assertTrue(hasattr(self.page, "workplace_tree"))

    def test_10_layout_and_editor_regression(self) -> None:
        self.page.tabs.setCurrentWidget(self.tab)
        for width, height in ((1600, 900), (1920, 1080)):
            self.page.resize(width, height)
            self.page.show()
            self._app.processEvents()
            self.assertGreaterEqual(self.tab.tree.width(), 900)
            self.assertGreaterEqual(self.tab.tree.height(), 350)
            self.assertEqual(self.tab.tree.columnCount(), 6)

        editor_source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_source.count("self.tabs.addTab("), 5)
        self.assertNotIn("AUTHORITY_SUGGESTIONS", editor_source)
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="99887766",
        )
        before = record.updated_at
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],
            [
                TAB_ANNOUNCEMENT,
                TAB_SUBJECT_PREPARATION,
                TAB_COURSE,
                TAB_CONCLUSION,
                TAB_ATTACHMENTS,
            ],
        )
        self.assertTrue(hasattr(dialog, "office_combo"))
        self.assertFalse(hasattr(dialog, "ico_edit"))
        dialog.close()
        reopened = state_supervision_service.get_supervision(record.id)
        self.assertEqual(reopened.authority_ico, "99887766")
        self.assertEqual(reopened.updated_at, before)

    def test_11_refresh_error_after_save_does_not_resave(self) -> None:
        dialog = ControlAuthorityDialog(
            self.tab, on_catalog_changed=self.tab._on_catalog_changed
        )
        dialog.name_edit.setText(f"Refresh {self.marker}")
        with patch.object(
            dialog,
            "_on_catalog_changed",
            side_effect=RuntimeError("refresh fail"),
        ):
            self.assertTrue(dialog._editor._run_save())
        self.assertFalse(dialog._editor.is_dirty())
        saved = next(
            item
            for item in self.catalog.list_authorities(include_inactive=True)
            if item.name == f"Refresh {self.marker}"
        )
        self.assertEqual(saved.origin, AUTHORITY_ORIGIN_MANUAL)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
