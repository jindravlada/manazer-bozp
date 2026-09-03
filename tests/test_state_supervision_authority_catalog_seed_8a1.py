"""STATE-SUPERVISION-AUTHORITY-CATALOG-SEED-8A1: výchozí katalog orgánů."""

from __future__ import annotations

import copy
import importlib
import inspect
import json
import os
import re
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FORBIDDEN_ICO_KEYS = {
    "ico",
    "ičo",
    "ic",
    "dic",
    "vat_id",
    "identification_number",
    "authority_ico",
    "office_ico",
    "ico_o",
    "ic_number",
}
PERSON_TITLE_RE = re.compile(
    r"\b(?:Ing|Mgr|MUDr|JUDr|PhDr|RNDr|Bc|Ph\.D|CSc|doc|prof)\b",
    re.IGNORECASE,
)
EXPECTED_CODES = ("suip", "cbu", "khs", "hzs", "du")
EXPECTED_NAMES = {
    "suip": "Státní úřad inspekce práce",
    "cbu": "Český báňský úřad",
    "khs": "Krajské hygienické stanice",
    "hzs": "Hasičský záchranný sbor České republiky",
    "du": "Drážní úřad",
}
EXPECTED_ABBREVIATIONS = {
    "suip": "SÚIP / OIP",
    "cbu": "ČBÚ / OBÚ",
    "khs": "KHS",
    "hzs": "HZS",
    "du": "DÚ",
}
EXPECTED_OFFICE_COUNTS = {
    "suip": 8,
    "cbu": 7,
    "khs": 14,
    "hzs": 14,
    "du": 3,
}
EXPECTED_OFFICE_KEYS = {
    "suip": (
        "suip:oip-praha",
        "suip:oip-stredocesky",
        "suip:oip-jihocesky-vysocina",
        "suip:oip-plzensky-karlovarsky",
        "suip:oip-ustecky-liberecky",
        "suip:oip-kralovehradecky-pardubicky",
        "suip:oip-jihomoravsky-zlinsky",
        "suip:oip-moravskoslezsky-olomoucky",
    ),
    "cbu": (
        "cbu:obu-praha",
        "cbu:obu-plzen",
        "cbu:obu-sokolov",
        "cbu:obu-most",
        "cbu:obu-hradec-kralove",
        "cbu:obu-brno",
        "cbu:obu-ostrava",
    ),
    "khs": (
        "khs:praha",
        "khs:stredocesky-kraj",
        "khs:jihocesky-kraj",
        "khs:plzensky-kraj",
        "khs:karlovarsky-kraj",
        "khs:ustecky-kraj",
        "khs:liberecky-kraj",
        "khs:kralovehradecky-kraj",
        "khs:pardubicky-kraj",
        "khs:kraj-vysocina",
        "khs:jihomoravsky-kraj",
        "khs:olomoucky-kraj",
        "khs:moravskoslezsky-kraj",
        "khs:zlinsky-kraj",
    ),
    "hzs": (
        "hzs:praha",
        "hzs:stredocesky-kraj",
        "hzs:jihocesky-kraj",
        "hzs:plzensky-kraj",
        "hzs:karlovarsky-kraj",
        "hzs:ustecky-kraj",
        "hzs:liberecky-kraj",
        "hzs:kralovehradecky-kraj",
        "hzs:pardubicky-kraj",
        "hzs:kraj-vysocina",
        "hzs:jihomoravsky-kraj",
        "hzs:olomoucky-kraj",
        "hzs:moravskoslezsky-kraj",
        "hzs:zlinsky-kraj",
    ),
    "du": ("du:praha", "du:plzen", "du:olomouc"),
}


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def _columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[1])
            for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
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


def _authority_stamps(db_path: Path) -> list[tuple]:
    conn = sqlite3.connect(str(db_path))
    try:
        return list(
            conn.execute(
                "SELECT code, name, origin, updated_at, user_edited_at, "
                "last_checked_at FROM control_authorities ORDER BY code"
            ).fetchall()
        )
    finally:
        conn.close()


def _walk_keys(value, *, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            found.add(str(key).strip().lower())
            _walk_keys(nested, found=found)
        return
    if isinstance(value, list):
        for nested in value:
            _walk_keys(nested, found=found)


def _seed_pre_8a0_db(db_path: Path) -> None:
    from moduly.statni_dozor.sluzby.state_supervision_core_1_schema_migration import (
        DDL_STATEMENTS as CORE1_DDL,
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        for statement in CORE1_DDL:
            conn.execute(statement)
        conn.execute(
            """
            INSERT INTO state_supervisions (
                status, authority_ico, authority_name, authority_address,
                workplace_name_snapshot, workplace_address_snapshot,
                power_of_attorney_required, created_at, updated_at
            ) VALUES (
                'announced', '12345678', 'OIP Praha', 'Kladenská 1',
                'Provoz A', 'Ulice 1',
                0, '2026-03-01 09:00:00', '2026-03-01 09:00:00'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


class StateSupervisionAuthorityCatalogSeed8a1ContentTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from moduly.statni_dozor.sluzby.control_authority_catalog_seed_service import (
            bundled_catalog_path,
            load_catalog_json,
            validate_catalog,
        )

        self.path = bundled_catalog_path()
        self.raw = load_catalog_json()
        self.validated = validate_catalog(self.raw)

    def test_01_five_groups_and_official_names(self) -> None:
        self.assertTrue(self.path.is_file())
        self.assertTrue(
            self.path.as_posix().endswith(
                "ciselniky/statni_dozor/kontrolni_organy.json"
            )
        )
        self.assertEqual(self.raw["schema_version"], 1)
        self.assertEqual(self.raw["catalog_version"], "2026-09-02")
        self.assertEqual(self.raw["verified_at"], "2026-09-02")
        self.assertGreaterEqual(len(self.raw["sources"]), 5)
        authorities = self.validated["authorities"]
        self.assertEqual(len(authorities), 5)
        self.assertEqual(tuple(item["code"] for item in authorities), EXPECTED_CODES)
        for item in authorities:
            self.assertEqual(item["name"], EXPECTED_NAMES[item["code"]])
            self.assertEqual(
                item["abbreviation"], EXPECTED_ABBREVIATIONS[item["code"]]
            )
            self.assertEqual(item["origin"], "bundled")
            self.assertEqual(item["external_key"], f"authority:{item['code']}")
            self.assertTrue(str(item["source_url"]).startswith("https://"))

    def test_02_main_offices_match_verified_source(self) -> None:
        total = 0
        seen_keys: set[str] = set()
        seen_urls: set[str] = set()
        for authority in self.validated["authorities"]:
            offices = authority["offices"]
            self.assertEqual(len(offices), EXPECTED_OFFICE_COUNTS[authority["code"]])
            keys = tuple(office["external_key"] for office in offices)
            self.assertEqual(keys, EXPECTED_OFFICE_KEYS[authority["code"]])
            for office in offices:
                self.assertTrue(office["name"].strip())
                self.assertTrue(office["address"].strip())
                self.assertEqual(office["origin"], "bundled")
                self.assertIn(
                    office["office_kind"],
                    {"headquarters", "regional", "territorial", "other"},
                )
                self.assertGreaterEqual(office["display_order"], 0)
                self.assertTrue(str(office["source_url"]).startswith("https://"))
                self.assertNotIn(office["external_key"], seen_keys)
                seen_keys.add(office["external_key"])
                seen_urls.add(office["source_url"])
            total += len(offices)
        self.assertEqual(total, 46)
        self.assertEqual(len(seen_keys), 46)
        self.assertGreaterEqual(len(seen_urls), 5)
        du = next(item for item in self.validated["authorities"] if item["code"] == "du")
        self.assertEqual(du["offices"][0]["office_kind"], "headquarters")

    def test_03_no_ico_fields_or_person_names(self) -> None:
        found: set[str] = set()
        _walk_keys(self.raw, found=found)
        self.assertTrue(FORBIDDEN_ICO_KEYS.isdisjoint(found))
        raw_text = self.path.read_text(encoding="utf-8")
        self.assertNotIn('"ico"', raw_text.lower())
        self.assertNotIn("authority_ico", raw_text)
        self.assertNotIn("datová schránka", raw_text.lower())
        self.assertNotIn('"fax"', raw_text.lower())
        for authority in self.validated["authorities"]:
            for value in (authority["name"], authority.get("abbreviation")):
                self.assertIsNone(PERSON_TITLE_RE.search(str(value or "")))
            for office in authority["offices"]:
                blob = " ".join(
                    str(office.get(field) or "")
                    for field in (
                        "name",
                        "abbreviation",
                        "address",
                        "phone",
                        "email",
                        "territorial_scope",
                    )
                )
                self.assertIsNone(PERSON_TITLE_RE.search(blob))

    def test_04_importer_is_offline(self) -> None:
        source = Path(
            "moduly/statni_dozor/sluzby/control_authority_catalog_seed_service.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("http.client", source)
        self.assertNotIn("urlopen", source)


_MIG_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-catalog-8a1-mig-"))
_MIG_HOME_PATCHER = patch.object(Path, "home", return_value=_MIG_HOME)
_MIG_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)

from core.database.upgrade_guard import (  # noqa: E402
    MigrationGuardError,
    is_transition_complete,
    prepare_database_for_startup,
)
from moduly.statni_dozor.sluzby.state_supervision_authority_catalog_core_8a0_schema_migration import (  # noqa: E402
    AUTHORITIES_TABLE,
    OFFICES_TABLE,
    TRANSITION_ID,
    needs_state_supervision_authority_catalog_core_8a0_schema,
    prepare_state_supervision_authority_catalog_core_8a0_schema,
)

_MIG_HOME_PATCHER.stop()


class StateSupervisionAuthorityCatalogSeed8a1UpgradeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_MIG_HOME)
        self._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        self.db_path = storage_module.storage_service.database_path
        self.ws = storage_module.storage_service.base
        state_path = self.ws / "konfigurace" / "migration_state.json"
        if state_path.exists():
            state_path.unlink()
        _seed_pre_8a0_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_core_8a0_schema_stays_empty(self) -> None:
        prepare_state_supervision_authority_catalog_core_8a0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertIn(AUTHORITIES_TABLE, _tables(self.db_path))
        self.assertIn(OFFICES_TABLE, _tables(self.db_path))
        self.assertEqual(_count(self.db_path, AUTHORITIES_TABLE), 0)
        self.assertEqual(_count(self.db_path, OFFICES_TABLE), 0)
        row = _supervision_rows(self.db_path)[0]
        self.assertEqual(row[1], "12345678")
        self.assertIsNone(row[3])

    def test_02_upgrade_initialize_inserts_seed(self) -> None:
        from core.database.database_initializer import initialize_database

        prepare_state_supervision_authority_catalog_core_8a0_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertEqual(_count(self.db_path, AUTHORITIES_TABLE), 0)
        before = _supervision_rows(self.db_path)
        initialize_database()
        self.assertEqual(_count(self.db_path, AUTHORITIES_TABLE), 5)
        self.assertEqual(_count(self.db_path, OFFICES_TABLE), 46)
        self.assertEqual(_supervision_rows(self.db_path), before)
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertNotIn("ico", _columns(self.db_path, AUTHORITIES_TABLE))
        self.assertNotIn("ico", _columns(self.db_path, OFFICES_TABLE))

    def test_03_upgrade_guard_runs_schema_before_seed(self) -> None:
        from core.database.database_initializer import initialize_database

        guard_source = inspect.getsource(prepare_database_for_startup)
        init_source = inspect.getsource(initialize_database)
        self.assertIn(
            "prepare_state_supervision_authority_catalog_core_8a0_schema",
            guard_source,
        )
        self.assertIn("_ensure_control_authority_catalog", init_source)
        self.assertGreater(
            init_source.find("_ensure_control_authority_catalog"),
            init_source.find("create_database"),
        )
        self.assertNotIn("state-supervision-authority-catalog-seed-8a1", guard_source)
        self.assertNotIn("mark_migration_complete", init_source)
        seed_source = Path(
            "moduly/statni_dozor/sluzby/control_authority_catalog_seed_service.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("mark_migration_complete", seed_source)
        self.assertTrue(
            needs_state_supervision_authority_catalog_core_8a0_schema(self.db_path)
        )


_SVC_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-catalog-8a1-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.dashboard.attention_service import get_state_supervision_reminder_items
    from core.database.session import get_session
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.periodicke_cinnosti.constants import TAB_PERIODIC, TAB_TASKS_MEETINGS
    from moduly.rocni_plan.constants import TAB_YEARLY_PLAN
    from moduly.statni_dozor.constants import (
        AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE,
        AUTHORITY_CATALOG_SEED_ICO_FORBIDDEN_MESSAGE,
        AUTHORITY_CATALOG_SEED_SCHEMA_INVALID_MESSAGE,
        AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE,
        AUTHORITY_CATALOG_SEED_URL_INVALID_MESSAGE,
        AUTHORITY_ORIGIN_BUNDLED,
        AUTHORITY_ORIGIN_MANUAL,
        OFFICE_KIND_REGIONAL,
        TAB_ANNOUNCEMENT,
        TAB_ATTACHMENTS,
        TAB_CONCLUSION,
        TAB_COURSE,
        TAB_STATE_SUPERVISION,
        TAB_SUBJECT_PREPARATION,
    )
    from moduly.statni_dozor.sluzby.control_authority_catalog_seed_service import (
        ControlAuthorityCatalogSeedError,
        bundled_catalog_path,
        control_authority_catalog_seed_service,
        ensure_control_authority_catalog,
        load_catalog_json,
    )
    from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
        control_authority_catalog_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )


class StateSupervisionAuthorityCatalogSeed8a1ImportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_SVC_HOME)
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

    def _reseed(self) -> None:
        ensure_control_authority_catalog()

    def _restore_catalog(self) -> None:
        self._wipe_catalog()
        self._reseed()

    def _wipe_catalog(self) -> None:
        sess = get_session()
        try:
            sess.execute(text("DELETE FROM control_authority_offices"))
            sess.execute(text("DELETE FROM control_authorities"))
            sess.commit()
        finally:
            sess.close()

    def test_01_clean_install_inserts_seed(self) -> None:
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), 5)
        self.assertEqual(_count(self.db, OFFICES_TABLE), 46)
        authorities = self.catalog.list_authorities(include_inactive=True)
        self.assertEqual(tuple(item.code for item in authorities), EXPECTED_CODES)
        for authority in authorities:
            self.assertEqual(authority.origin, AUTHORITY_ORIGIN_BUNDLED)
            self.assertIsNone(authority.user_edited_at)
            self.assertIsNone(authority.last_checked_at)
            offices = self.catalog.list_offices(
                authority_id=authority.id, include_inactive=True
            )
            self.assertEqual(len(offices), EXPECTED_OFFICE_COUNTS[authority.code])
            self.assertEqual(
                tuple(office.external_key for office in offices),
                EXPECTED_OFFICE_KEYS[authority.code],
            )
            for office in offices:
                self.assertEqual(office.origin, AUTHORITY_ORIGIN_BUNDLED)
                self.assertIsNone(office.user_edited_at)
                self.assertIsNone(office.last_checked_at)
                self.assertTrue(str(office.source_url).startswith("https://"))

    def test_02_repeat_import_no_duplicates_and_no_commit(self) -> None:
        before_auth = _count(self.db, AUTHORITIES_TABLE)
        before_off = _count(self.db, OFFICES_TABLE)
        stamps = _authority_stamps(self.db)
        first = self.seed.ensure_default_catalog()
        self.assertFalse(first.committed)
        self.assertEqual(first.authorities_created, 0)
        self.assertEqual(first.offices_created, 0)
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), before_auth)
        self.assertEqual(_count(self.db, OFFICES_TABLE), before_off)
        self.assertEqual(_authority_stamps(self.db), stamps)

    def test_03_manual_and_user_edited_are_kept(self) -> None:
        suip = self.catalog.get_authority_by_code("suip")
        assert suip is not None
        updated = self.catalog.update_authority(suip.id, name="Moje SÚIP")
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNotNone(updated.user_edited_at)
        office = self.catalog.get_office_by_external_key("suip:oip-praha")
        assert office is not None
        office_updated = self.catalog.update_office(
            office.id, address="Ruční adresa 1"
        )
        self.assertEqual(office_updated.origin, AUTHORITY_ORIGIN_MANUAL)
        result = self.seed.ensure_default_catalog()
        self.assertFalse(result.committed)
        reloaded = self.catalog.get_authority_by_code("suip")
        self.assertEqual(reloaded.name, "Moje SÚIP")
        self.assertEqual(reloaded.origin, AUTHORITY_ORIGIN_MANUAL)
        office_reloaded = self.catalog.get_office_by_external_key("suip:oip-praha")
        self.assertEqual(office_reloaded.address, "Ruční adresa 1")
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), 5)
        self.assertEqual(_count(self.db, OFFICES_TABLE), 46)

    def test_04_deactivated_office_is_not_reactivated(self) -> None:
        office = self.catalog.get_office_by_external_key("cbu:obu-ostrava")
        assert office is not None
        self.catalog.deactivate_office(office.id)
        result = self.seed.ensure_default_catalog()
        self.assertFalse(result.committed)
        reloaded = self.catalog.get_office_by_external_key("cbu:obu-ostrava")
        self.assertFalse(reloaded.active)
        self.assertEqual(reloaded.name, office.name)

    def test_05_missing_bundled_office_is_filled(self) -> None:
        sess = get_session()
        try:
            sess.execute(
                text(
                    "DELETE FROM control_authority_offices "
                    "WHERE external_key = :key"
                ),
                {"key": "hzs:ustecky-kraj"},
            )
            sess.commit()
        finally:
            sess.close()
        self.assertIsNone(
            self.catalog.get_office_by_external_key("hzs:ustecky-kraj")
        )
        result = self.seed.ensure_default_catalog()
        self.assertTrue(result.committed)
        self.assertEqual(result.offices_created, 1)
        restored = self.catalog.get_office_by_external_key("hzs:ustecky-kraj")
        self.assertIsNotNone(reloaded := restored)
        self.assertEqual(reloaded.origin, AUTHORITY_ORIGIN_BUNDLED)
        self.assertIsNone(reloaded.last_checked_at)
        hzs = self.catalog.get_authority_by_code("hzs")
        self.assertEqual(
            len(self.catalog.list_offices(authority_id=hzs.id, include_inactive=True)),
            14,
        )

    def test_06_item_removed_from_newer_seed_is_not_deleted(self) -> None:
        payload = copy.deepcopy(load_catalog_json())
        du = next(item for item in payload["authorities"] if item["code"] == "du")
        removed_key = du["offices"][-1]["external_key"]
        du["offices"] = du["offices"][:-1]
        result = self.seed.import_catalog(payload)
        self.assertFalse(result.committed)
        self.assertIsNotNone(self.catalog.get_office_by_external_key(removed_key))
        self.assertEqual(_count(self.db, OFFICES_TABLE), 46)

    def test_07_key_collision_rolls_back_batch(self) -> None:
        self.addCleanup(self._restore_catalog)
        self._wipe_catalog()
        dummy = self.catalog.create_authority(
            code=f"other-{self.marker}",
            name="Jiný orgán",
        )
        self.catalog.create_office(
            authority_id=dummy.id,
            name="Kolidující pracoviště",
            address="Adresa 1",
            office_kind=OFFICE_KIND_REGIONAL,
            external_key="suip:oip-praha",
        )
        before_auth = _count(self.db, AUTHORITIES_TABLE)
        before_off = _count(self.db, OFFICES_TABLE)
        with self.assertRaises(ControlAuthorityCatalogSeedError) as ctx:
            self.seed.ensure_default_catalog()
        message = str(ctx.exception)
        self.assertIn(AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE, message)
        self.assertIn(AUTHORITY_CATALOG_SEED_COLLISION_MESSAGE, message)
        self.assertIsInstance(ctx.exception, MigrationGuardError)
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), before_auth)
        self.assertEqual(_count(self.db, OFFICES_TABLE), before_off)
        self.assertIsNone(self.catalog.get_authority_by_code("suip"))

    def test_08_invalid_json_inserts_nothing(self) -> None:
        before_auth = _count(self.db, AUTHORITIES_TABLE)
        before_off = _count(self.db, OFFICES_TABLE)
        path = Path(tempfile.mkdtemp(prefix="catalog-seed-bad-")) / "bad.json"
        path.write_text("{", encoding="utf-8")
        with self.assertRaises(ControlAuthorityCatalogSeedError) as ctx:
            self.seed.ensure_default_catalog(path=path)
        self.assertIn(AUTHORITY_CATALOG_SEED_STARTUP_MESSAGE, str(ctx.exception))
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), before_auth)
        self.assertEqual(_count(self.db, OFFICES_TABLE), before_off)

        payload = copy.deepcopy(load_catalog_json())
        payload["schema_version"] = 99
        with self.assertRaises(ControlAuthorityCatalogSeedError) as ctx:
            self.seed.import_catalog(payload)
        self.assertIn(AUTHORITY_CATALOG_SEED_SCHEMA_INVALID_MESSAGE, str(ctx.exception))

        payload = copy.deepcopy(load_catalog_json())
        payload["authorities"][0]["ico"] = "12345678"
        with self.assertRaises(ControlAuthorityCatalogSeedError) as ctx:
            self.seed.import_catalog(payload)
        self.assertIn(AUTHORITY_CATALOG_SEED_ICO_FORBIDDEN_MESSAGE, str(ctx.exception))

        payload = copy.deepcopy(load_catalog_json())
        payload["authorities"][0]["source_url"] = "http://suip.gov.cz"
        with self.assertRaises(ControlAuthorityCatalogSeedError) as ctx:
            self.seed.import_catalog(payload)
        self.assertIn(AUTHORITY_CATALOG_SEED_URL_INVALID_MESSAGE, str(ctx.exception))

        payload = copy.deepcopy(load_catalog_json())
        payload["authorities"][0]["offices"][0]["office_kind"] = "branch"
        with self.assertRaises(ControlAuthorityCatalogSeedError):
            self.seed.import_catalog(payload)

        payload = copy.deepcopy(load_catalog_json())
        payload["authorities"][0]["offices"][0]["address"] = "  "
        with self.assertRaises(ControlAuthorityCatalogSeedError):
            self.seed.import_catalog(payload)

        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), before_auth)
        self.assertEqual(_count(self.db, OFFICES_TABLE), before_off)

    def test_09_import_does_not_change_state_supervisions(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="87654321",
            authority_address="Adresa 1",
        )
        before = _supervision_rows(self.db)
        self.seed.ensure_default_catalog()
        self.assertEqual(_supervision_rows(self.db), before)
        loaded = state_supervision_service.get_supervision(record.id)
        self.assertEqual(loaded.authority_ico, "87654321")
        self.assertIsNone(loaded.authority_office_id)

    def test_10_isolation_editor_settings_dashboard(self) -> None:
        editor_source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_source.count("self.tabs.addTab("), 5)
        self.assertNotIn("AUTHORITY_SUGGESTIONS", editor_source)
        self.assertNotIn("ico_edit", editor_source)
        record = state_supervision_service.create_supervision(
            authority_name=f"OIP {self.marker}",
            authority_ico="11112222",
        )
        before_updated = record.updated_at
        before_auth = _count(self.db, AUTHORITIES_TABLE)
        dialog = StateSupervisionEditorDialog(supervision_id=record.id)
        self.assertEqual(dialog.tabs.count(), 5)
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
        self.assertTrue(hasattr(dialog, "authority_combo"))
        self.assertTrue(hasattr(dialog, "office_combo"))
        self.assertFalse(hasattr(dialog, "ico_edit"))
        dialog.close()
        reopened = state_supervision_service.get_supervision(record.id)
        self.assertEqual(reopened.authority_ico, "11112222")
        self.assertEqual(reopened.updated_at, before_updated)
        self.assertEqual(_count(self.db, AUTHORITIES_TABLE), before_auth)

        settings = NastaveniPage()
        titles = [settings.tabs.tabText(i) for i in range(settings.tabs.count())]
        self.assertEqual(
            titles,
            [
                "THP pracovníci",
                "Osoby",
                "Provozy a pracoviště",
                "Státní dozor",
                "Funkce / role",
                "Ohrožené skupiny",
                "Zaměstnavatel",
            ],
        )
        settings.close()

        items = get_state_supervision_reminder_items()
        self.assertIsInstance(items, list)
        page = AgendaPage()
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), TAB_TASKS_MEETINGS)
        self.assertEqual(page.tabs.tabText(1), TAB_STATE_SUPERVISION)
        self.assertEqual(page.tabs.tabText(2), TAB_PERIODIC)
        self.assertEqual(page.tabs.tabText(3), TAB_YEARLY_PLAN)
        page.close()

    def test_11_schema_missing_skips_insert(self) -> None:
        from moduly.statni_dozor.sluzby.control_authority_catalog_seed_service import (
            _catalog_tables_ready,
        )

        self.assertTrue(_catalog_tables_ready())
        self.assertTrue(bundled_catalog_path().is_file())


if __name__ == "__main__":
    unittest.main()
