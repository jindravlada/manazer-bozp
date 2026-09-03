"""STATE-SUPERVISION-KHS-TERRITORIAL-SEED-9A2: ověřená územní pracoviště KHS."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_MANUAL_DUPLICATE_SKIP_MESSAGE,
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    AUTHORITY_ORIGIN_MANUAL,
    KHS_AUTHORITY_CODE,
    KHS_OFFICE_EXTERNAL_KEYS,
    KHS_OFFICES_SOURCE_URL,
    OFFICE_KIND_TERRITORIAL,
    OFFICE_KIND_USER_LABELS,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ERROR_SELECTION,
    WEB_COVERAGE_ID_KHS_REGIONAL,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_seed_service import (
    control_authority_catalog_seed_service,
    load_catalog_json,
    validate_catalog,
)
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpResponse,
)

_REPO = Path(__file__).resolve().parents[1]
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "khs_mzd.html"
_TEPLICE_KEY = "khs:ustecky-kraj:teplice"
_TEPLICE_NAME = "KHS Ústeckého kraje – Územní pracoviště Teplice"
_TEPLICE_ADDRESS = "Jiřího Wolkera 1342/4, 415 01 Teplice"
_EXPECTED_COUNTS = {
    "khs:praha": 5,
    "khs:stredocesky-kraj": 10,
    "khs:jihocesky-kraj": 6,
    "khs:plzensky-kraj": 3,
    "khs:ustecky-kraj": 6,
    "khs:liberecky-kraj": 3,
    "khs:pardubicky-kraj": 3,
    "khs:kraj-vysocina": 4,
    "khs:moravskoslezsky-kraj": 5,
    "khs:zlinsky-kraj": 3,
}
_FORBIDDEN_REGIONS = (
    "khs:karlovarsky-kraj:",
    "khs:kralovehradecky-kraj:",
    "khs:jihomoravsky-kraj:",
    "khs:olomoucky-kraj:",
)
AUTHORITIES_TABLE = "control_authorities"
OFFICES_TABLE = "control_authority_offices"


def _khs_authority(raw: dict) -> dict:
    return next(item for item in raw["authorities"] if item["code"] == "khs")


def _territorial(raw: dict) -> list[dict]:
    return [
        office
        for office in _khs_authority(raw)["offices"]
        if office.get("office_kind") == OFFICE_KIND_TERRITORIAL
    ]


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


class StateSupervisionKhsTerritorialSeed9a2JsonTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = load_catalog_json()
        self.validated = validate_catalog(self.raw)
        self.territorial = _territorial(self.validated)

    def test_01_exactly_48_new_territorial_khs(self) -> None:
        self.assertEqual(len(self.territorial), 48)
        self.assertEqual(self.raw["schema_version"], 1)
        self.assertEqual(self.raw["catalog_version"], "2026-09-03")
        self.assertEqual(self.raw["verified_at"], "2026-09-03")

    def test_02_counts_by_region(self) -> None:
        found: dict[str, int] = {key: 0 for key in _EXPECTED_COUNTS}
        for office in self.territorial:
            parent = office["external_key"].rsplit(":", 1)[0]
            self.assertIn(parent, found)
            found[parent] += 1
        self.assertEqual(found, _EXPECTED_COUNTS)

    def test_03_clean_catalog_totals(self) -> None:
        authorities = self.validated["authorities"]
        self.assertEqual(len(authorities), 5)
        total = sum(len(item["offices"]) for item in authorities)
        self.assertEqual(total, 94)
        khs = _khs_authority(self.validated)
        self.assertEqual(len(khs["offices"]), 62)

    def test_04_new_keys_are_unique(self) -> None:
        keys = [office["external_key"] for office in self.territorial]
        self.assertEqual(len(keys), len(set(keys)))

    def test_05_no_collision_with_regional_keys(self) -> None:
        territorial_keys = {office["external_key"] for office in self.territorial}
        self.assertTrue(territorial_keys.isdisjoint(KHS_OFFICE_EXTERNAL_KEYS))
        for key in territorial_keys:
            self.assertEqual(key.count(":"), 2)
            self.assertTrue(key.startswith("khs:"))
            self.assertEqual(key, key.lower())
            self.assertRegex(key, r"^khs:[a-z0-9-]+:[a-z0-9-]+$")

    def test_06_all_territorial_kind(self) -> None:
        for office in self.territorial:
            self.assertEqual(office["office_kind"], OFFICE_KIND_TERRITORIAL)
            self.assertTrue(office["active"] if "active" in office else True)
            self.assertEqual(office["origin"], AUTHORITY_ORIGIN_BUNDLED)

    def test_07_required_fields_present(self) -> None:
        for office in self.territorial:
            self.assertTrue(str(office["name"]).strip())
            self.assertTrue(str(office["address"]).strip())
            self.assertTrue(str(office["source_url"]).strip())
            self.assertTrue(str(office["name"]).startswith(("KHS ", "Hygienická stanice")))
            self.assertIn("Územní pracoviště", office["name"])

    def test_08_urls_are_https(self) -> None:
        for office in self.territorial:
            self.assertTrue(str(office["source_url"]).startswith("https://"))
            self.assertTrue(str(office["website"]).startswith("https://"))

    def test_09_forbidden_regions_absent(self) -> None:
        blob = json.dumps(self.territorial, ensure_ascii=False)
        for prefix in _FORBIDDEN_REGIONS:
            self.assertNotIn(prefix, blob)

    def test_10_rokycany_absent(self) -> None:
        blob = json.dumps(self.territorial, ensure_ascii=False)
        self.assertNotIn("Rokycany", blob)
        self.assertNotIn("rokycany", blob.lower())

    def test_11_praha_vychod_zapad_absent(self) -> None:
        blob = json.dumps(self.territorial, ensure_ascii=False)
        self.assertNotIn("Praha-východ", blob)
        self.assertNotIn("Praha-západ", blob)
        self.assertNotIn("praha-vychod", blob.lower())
        self.assertNotIn("praha-zapad", blob.lower())

    def test_12_teplice_canonical_address(self) -> None:
        teplce = next(
            office for office in self.territorial if office["external_key"] == _TEPLICE_KEY
        )
        self.assertEqual(teplce["name"], _TEPLICE_NAME)
        self.assertEqual(teplce["address"], _TEPLICE_ADDRESS)
        self.assertEqual(teplce["phone"], "477 755 710")
        self.assertEqual(
            teplce["source_url"],
            "https://khsusti.cz/kontakt/pracoviste-teplice/",
        )
        self.assertNotIn("Wolkerova 4", teplce["address"])
        self.assertNotIn("416 65", teplce["address"])


_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-khs-9a2-"))
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
from PySide6.QtWidgets import QApplication

from core.database.session import get_session
from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
from moduly.statni_dozor.constants import (
    CATALOG_ROW_KIND_OFFICE,
    OFFICE_KIND_REGIONAL,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityOfficeWebApplySelection,
    ControlAuthorityWebApplyError,
    apply_authority_web_changes,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebCheckService,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    state_supervision_service,
)
from moduly.statni_dozor.ui.control_authority_office_dialog import (
    ControlAuthorityOfficeDialog,
)
from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
    StateSupervisionEditorDialog,
)

_HOME_PATCHER.stop()


def _select_id(combo, item_id) -> None:
    index = combo.findData(int(item_id))
    if index < 0:
        raise AssertionError(f"Položka {item_id} není v nabídce.")
    combo.setCurrentIndex(index)


class StateSupervisionKhsTerritorialSeed9a2RuntimeTestCase(unittest.TestCase):
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
        self.seed = control_authority_catalog_seed_service
        self.marker = uuid.uuid4().hex[:8]
        self.addCleanup(self._restore_catalog)

    def _wipe_catalog(self) -> None:
        sess = get_session()
        try:
            sess.execute(text("DELETE FROM control_authority_offices"))
            sess.execute(text("DELETE FROM control_authorities"))
            sess.commit()
        finally:
            sess.close()

    def _restore_catalog(self) -> None:
        self._wipe_catalog()
        self.seed.ensure_default_catalog()

    def _khs(self):
        authority = self.catalog.get_authority_by_code(KHS_AUTHORITY_CODE)
        assert authority is not None
        return authority

    def _territorial_offices(self):
        return [
            office
            for office in self.catalog.list_offices(
                authority_id=self._khs().id, include_inactive=True
            )
            if office.office_kind == OFFICE_KIND_TERRITORIAL
        ]

    def test_03_clean_install_has_five_authorities_and_94_offices(self) -> None:
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), 5)
        self.assertEqual(_count(self.db, OFFICES_TABLE), 94)
        self.assertEqual(len(self._territorial_offices()), 48)

    def test_13_existing_db_fills_48_gaps_in_one_commit(self) -> None:
        keys = [office.external_key for office in self._territorial_offices()]
        sess = get_session()
        try:
            for key in keys:
                sess.execute(
                    text("DELETE FROM control_authority_offices WHERE external_key = :key"),
                    {"key": key},
                )
            sess.commit()
        finally:
            sess.close()
        self.assertEqual(len(self._territorial_offices()), 0)
        before = _count(self.db, OFFICES_TABLE)
        result = self.seed.ensure_default_catalog()
        self.assertTrue(result.committed)
        self.assertEqual(result.offices_created, 48)
        self.assertEqual(_count(self.db, OFFICES_TABLE), before + 48)
        self.assertEqual(len(self._territorial_offices()), 48)

    def test_14_second_import_is_idempotent(self) -> None:
        first = self.seed.ensure_default_catalog()
        self.assertFalse(first.committed)
        self.assertEqual(first.offices_created, 0)
        second = self.seed.ensure_default_catalog()
        self.assertFalse(second.committed)
        self.assertEqual(second.offices_created, 0)
        self.assertEqual(_count(self.db, OFFICES_TABLE), 94)

    def test_15_manual_and_deactivated_are_kept(self) -> None:
        office = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        assert office is not None
        updated = self.catalog.update_office(office.id, address="Ruční adresa Teplice")
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNotNone(updated.user_edited_at)
        self.catalog.deactivate_office(office.id)
        result = self.seed.ensure_default_catalog()
        self.assertFalse(result.committed)
        reloaded = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        self.assertEqual(reloaded.address, "Ruční adresa Teplice")
        self.assertEqual(reloaded.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertFalse(reloaded.active)
        self.assertEqual(reloaded.external_key, _TEPLICE_KEY)

    def test_16_exact_manual_duplicate_is_skipped(self) -> None:
        office = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        assert office is not None
        sess = get_session()
        try:
            sess.execute(
                text("DELETE FROM control_authority_offices WHERE external_key = :key"),
                {"key": _TEPLICE_KEY},
            )
            sess.commit()
        finally:
            sess.close()
        manual = self.catalog.create_office(
            authority_id=self._khs().id,
            name=_TEPLICE_NAME,
            address=_TEPLICE_ADDRESS,
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        self.assertIsNone(manual.external_key)
        with self.assertLogs(
            "moduly.statni_dozor.sluzby.control_authority_catalog_seed_service",
            level="WARNING",
        ) as logs:
            result = self.seed.ensure_default_catalog()
        self.assertFalse(result.committed)
        self.assertEqual(result.offices_created, 0)
        reloaded = self.catalog.get_office(manual.id)
        self.assertIsNone(reloaded.external_key)
        self.assertEqual(reloaded.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNone(self.catalog.get_office_by_external_key(_TEPLICE_KEY))
        warning = AUTHORITY_CATALOG_SEED_MANUAL_DUPLICATE_SKIP_MESSAGE.format(
            name=_TEPLICE_NAME
        )
        self.assertTrue(any(warning in line for line in logs.output))

        sess = get_session()
        try:
            sess.execute(
                text("DELETE FROM control_authority_offices WHERE id = :id"),
                {"id": int(manual.id)},
            )
            sess.commit()
        finally:
            sess.close()
        other = self.catalog.create_office(
            authority_id=self._khs().id,
            name=_TEPLICE_NAME,
            address="Jiná adresa 1, Teplice",
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        self.assertIsNone(other.external_key)
        result = self.seed.ensure_default_catalog()
        self.assertTrue(result.committed)
        self.assertEqual(result.offices_created, 1)
        bundled = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        self.assertIsNotNone(bundled)
        self.assertNotEqual(int(bundled.id), int(other.id))
        self.assertIsNone(self.catalog.get_office(other.id).external_key)

    def test_17_historical_snapshot_is_kept(self) -> None:
        office = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        assert office is not None
        record = state_supervision_service.create_supervision(
            authority_name="Krajské hygienické stanice",
            authority_id=self._khs().id,
            authority_office_id=office.id,
            authority_office_name_snapshot="Historický snapshot Teplice",
            authority_address="Historická adresa",
        )
        result = self.seed.ensure_default_catalog()
        self.assertFalse(result.committed)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.authority_office_name_snapshot, "Historický snapshot Teplice")
        self.assertEqual(loaded.authority_address, "Historická adresa")
        self.assertEqual(loaded.authority_office_id, office.id)

    def test_18_regional_coverage_ignores_territorial(self) -> None:
        html = _FIXTURE.read_text(encoding="utf-8")

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            self.assertEqual(url, KHS_OFFICES_SOURCE_URL)
            return ControlAuthorityHttpResponse(
                status_code=200,
                body=html.encode("utf-8"),
                content_type="text/html",
                final_url=url,
            )

        before = _count(self.db, OFFICES_TABLE)
        result = ControlAuthorityWebCheckService(
            http_get=fake_get,
        ).check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(result.coverage.expected_external_keys, frozenset(KHS_OFFICE_EXTERNAL_KEYS))
        self.assertEqual(len(result.remote_records), 14)
        self.assertEqual(len(result.diffs), 14)
        territorial_keys = {office.external_key for office in self._territorial_offices()}
        diff_keys = {item.external_key for item in result.diffs}
        self.assertTrue(territorial_keys.isdisjoint(diff_keys))
        statuses = {item.status for item in result.diffs}
        self.assertNotIn("missing_remote", statuses)
        self.assertNotIn("protected_missing_remote", statuses)
        teplce = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        assert teplce is not None
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                result,
                [
                    ControlAuthorityOfficeWebApplySelection(
                        external_key=_TEPLICE_KEY,
                        local_id=int(teplce.id),
                        action=WEB_APPLY_ACTION_DEACTIVATE,
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_SELECTION)
        self.assertEqual(_count(self.db, OFFICES_TABLE), before)
        still = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        self.assertTrue(still.active)

    def test_19_editor_selects_teplice_and_saves_snapshot(self) -> None:
        khs = self._khs()
        teplce = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        assert teplce is not None
        offices = self.catalog.list_offices(authority_id=khs.id)
        regional = [item for item in offices if item.office_kind == OFFICE_KIND_REGIONAL]
        territorial = [item for item in offices if item.office_kind == OFFICE_KIND_TERRITORIAL]
        self.assertEqual(len(regional), 14)
        self.assertEqual(len(territorial), 48)

        dialog = StateSupervisionEditorDialog()
        _select_id(dialog.authority_combo, khs.id)
        self.assertEqual(dialog.office_combo.currentText(), "")
        self.assertIsNone(dialog.office_combo.currentData())
        office_ids = [
            dialog.office_combo.itemData(index)
            for index in range(dialog.office_combo.count())
            if dialog.office_combo.itemData(index) is not None
        ]
        self.assertEqual(len(office_ids), 62)
        teplce_index = dialog.office_combo.findText("Teplice", Qt.MatchFlag.MatchContains)
        self.assertGreater(teplce_index, 0)
        self.assertEqual(dialog.office_combo.itemData(teplce_index), teplce.id)
        usti_hits = [
            dialog.office_combo.itemText(index)
            for index in range(dialog.office_combo.count())
            if "Ústeckého" in dialog.office_combo.itemText(index)
        ]
        self.assertGreaterEqual(len(usti_hits), 7)
        _select_id(dialog.office_combo, teplce.id)
        data = dialog.get_data()
        self.assertEqual(data["authority_id"], khs.id)
        self.assertEqual(data["authority_name"], khs.name)
        self.assertEqual(data["authority_office_id"], teplce.id)
        self.assertEqual(data["authority_office_name_snapshot"], _TEPLICE_NAME)
        self.assertEqual(data["authority_address"], _TEPLICE_ADDRESS)
        self.assertTrue(dialog._editor._run_save())
        saved_id = dialog.supervision_id
        dialog.close()
        self.assertIsNotNone(saved_id)
        saved = state_supervision_service.get_supervision(int(saved_id))
        self.assertEqual(saved.authority_id, khs.id)
        self.assertEqual(saved.authority_name, khs.name)
        self.assertEqual(saved.authority_office_id, teplce.id)
        self.assertEqual(saved.authority_office_name_snapshot, _TEPLICE_NAME)
        self.assertEqual(saved.authority_address, _TEPLICE_ADDRESS)

        self.catalog.update_office(teplce.id, name="Později změněný název")
        reopened = state_supervision_service.get_supervision(saved.id)
        self.assertEqual(reopened.authority_office_name_snapshot, _TEPLICE_NAME)

    def test_20_opening_editor_does_not_write(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name="Krajské hygienické stanice",
        )
        before = record.updated_at
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog._editor.save_button.isEnabled())
        dialog.close()
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.updated_at, before)

    def test_settings_tree_filter_and_kind_label(self) -> None:
        page = NastaveniPage()
        tab = page.state_supervision_catalog_tab
        khs = self._khs()
        parent = None
        for index in range(tab.tree.topLevelItemCount()):
            item = tab.tree.topLevelItem(index)
            if item.text(0) == khs.name:
                parent = item
                break
        self.assertIsNotNone(parent)
        assert parent is not None
        self.assertEqual(parent.childCount(), 62)
        child = parent.child(0)
        self.assertEqual(child.text(1), CATALOG_ROW_KIND_OFFICE)
        tab.filter_bar.search_edit.setText("Teplice")
        tab._apply_tree_filter("Teplice")
        visible = []
        for index in range(parent.childCount()):
            item = parent.child(index)
            if not item.isHidden():
                visible.append(item.text(0))
        self.assertEqual(visible, [_TEPLICE_NAME])
        tab.filter_bar.search_edit.setText("Ústeckého")
        tab._apply_tree_filter("Ústeckého")
        visible_usti = [
            parent.child(index).text(0)
            for index in range(parent.childCount())
            if not parent.child(index).isHidden()
        ]
        self.assertGreaterEqual(len(visible_usti), 7)
        teplce = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        assert teplce is not None
        dialog = ControlAuthorityOfficeDialog(tab, office=teplce)
        kind_index = dialog.kind_combo.findData(OFFICE_KIND_TERRITORIAL)
        self.assertGreaterEqual(kind_index, 0)
        self.assertEqual(
            dialog.kind_combo.itemText(kind_index),
            OFFICE_KIND_USER_LABELS[OFFICE_KIND_TERRITORIAL],
        )
        self.assertEqual(dialog.kind_combo.itemText(kind_index), "Územní pracoviště")
        self.assertFalse(dialog._editor.is_dirty())
        dialog.close()
        page.close()

    def test_display_order_groups_under_parent(self) -> None:
        offices = self.catalog.list_offices(authority_id=self._khs().id)
        keys = [office.external_key for office in offices]
        praha = keys.index("khs:praha")
        stc = keys.index("khs:stredocesky-kraj")
        block = keys[praha + 1 : stc]
        self.assertEqual(len(block), 5)
        self.assertTrue(all(key.startswith("khs:praha:") for key in block))
        usti = keys.index("khs:ustecky-kraj")
        liberec = keys.index("khs:liberecky-kraj")
        usti_block = keys[usti + 1 : liberec]
        self.assertIn(_TEPLICE_KEY, usti_block)
        self.assertEqual(len(usti_block), 6)
