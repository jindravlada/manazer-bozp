"""STATE-SUPERVISION-AUTHORITY-WEB-DIFF-8D1: porovnání webu s katalogem."""

from __future__ import annotations

import importlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import event

from core.services import storage_service as storage_module
from core.database import session as session_module
from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    AUTHORITY_ORIGIN_MANUAL,
    AUTHORITY_ORIGIN_WEB,
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    DU_OFFICES_SOURCE_URL,
    OFFICE_KIND_HEADQUARTERS,
    OFFICE_KIND_TERRITORIAL,
    WEB_DIFF_ACTION_CREATE,
    WEB_DIFF_ACTION_DEACTIVATE,
    WEB_DIFF_ACTION_NONE,
    WEB_DIFF_ACTION_REACTIVATE,
    WEB_DIFF_ACTION_REVIEW,
    WEB_DIFF_ACTION_UPDATE,
    WEB_DIFF_COMPARED_FIELDS,
    WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND,
    WEB_DIFF_ERROR_DUPLICATE_LOCAL,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_IDENTITY_CONFLICT,
    WEB_DIFF_STATUS_INACTIVE_PRESENT,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
    WEB_DIFF_STATUS_PROTECTED,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    ControlAuthorityCatalogSnapshotService,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityWebDiffError,
    ControlAuthorityWebDiffResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.du_adapter import (
    parse_du_offices_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebFetchResult,
)

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "du_kontakty.html"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 7, 40, 0)


def _web(
    *,
    key: str,
    name: str,
    address: str | None,
    phone: str | None = "226 523 368",
    email: str | None = None,
    website: str | None = None,
    territorial_scope: str | None = None,
    office_kind: str | None = OFFICE_KIND_HEADQUARTERS,
    authority_code: str = DU_AUTHORITY_CODE,
    source_url: str = DU_OFFICES_SOURCE_URL,
    observed_fields: frozenset[str] | None = None,
) -> ControlAuthorityOfficeWebRecord:
    return ControlAuthorityOfficeWebRecord(
        authority_code=authority_code,
        external_key=key,
        name=name,
        address=address,
        phone=phone,
        email=email,
        website=website,
        territorial_scope=territorial_scope,
        office_kind=office_kind,
        source_url=source_url,
        observed_fields=(
            observed_fields
            if observed_fields is not None
            else frozenset(WEB_DIFF_COMPARED_FIELDS)
        ),
    )


def _snap(
    *,
    office_id: int,
    key: str | None,
    name: str,
    address: str | None,
    phone: str | None = "226 523 368",
    email: str | None = None,
    website: str | None = None,
    territorial_scope: str | None = None,
    office_kind: str | None = OFFICE_KIND_HEADQUARTERS,
    active: bool = True,
    origin: str = AUTHORITY_ORIGIN_BUNDLED,
    user_edited_at: datetime | None = None,
    last_checked_at: datetime | None = None,
    authority_code: str = DU_AUTHORITY_CODE,
    authority_id: int = 50,
    source_url: str | None = DU_OFFICES_SOURCE_URL,
) -> ControlAuthorityOfficeCatalogSnapshot:
    return ControlAuthorityOfficeCatalogSnapshot(
        id=office_id,
        authority_id=authority_id,
        authority_code=authority_code,
        external_key=key,
        name=name,
        address=address,
        phone=phone,
        email=email,
        website=website,
        territorial_scope=territorial_scope,
        office_kind=office_kind,
        source_url=source_url,
        active=active,
        origin=origin,
        user_edited_at=user_edited_at,
        last_checked_at=last_checked_at,
    )


def _fetch(
    records,
    *,
    is_complete: bool = True,
    warnings: tuple[str, ...] = (),
) -> ControlAuthorityWebFetchResult:
    return ControlAuthorityWebFetchResult(
        authority_code=DU_AUTHORITY_CODE,
        source_url=DU_OFFICES_SOURCE_URL,
        fetched_at=_FIXED_AT,
        records=tuple(records),
        warnings=warnings,
        is_complete=is_complete,
    )


def _du_web_from_fixture() -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    return parse_du_offices_html(_FIXTURE.read_text(encoding="utf-8"))


def _seed_du_snapshots() -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    du = next(item for item in payload["authorities"] if item["code"] == "du")
    snapshots = []
    for index, office in enumerate(du["offices"], start=1):
        snapshots.append(
            _snap(
                office_id=index,
                key=office["external_key"],
                name=office["name"],
                address=office["address"],
                phone=office.get("phone"),
                email=office.get("email"),
                website=office.get("website"),
                territorial_scope=office.get("territorial_scope"),
                office_kind=office["office_kind"],
                origin=office.get("origin", AUTHORITY_ORIGIN_BUNDLED),
                source_url=office.get("source_url"),
            )
        )
    return tuple(snapshots)


def _matching_web(**overrides) -> ControlAuthorityOfficeWebRecord:
    data = dict(
        key="du:praha",
        name="Pracoviště Praha",
        address="Bělehradská 222/128, 120 00 Praha 2",
        phone="226 523 368",
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=OFFICE_KIND_HEADQUARTERS,
    )
    data.update(overrides)
    return _web(**data)


def _matching_local(**overrides) -> ControlAuthorityOfficeCatalogSnapshot:
    data = dict(
        office_id=1,
        key="du:praha",
        name="Pracoviště Praha",
        address="Bělehradská 222/128, 120 00 Praha 2",
        phone="226 523 368",
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=OFFICE_KIND_HEADQUARTERS,
    )
    data.update(overrides)
    return _snap(**data)


class StateSupervisionAuthorityWebDiff8d1TestCase(unittest.TestCase):
    def test_01_unchanged_and_counts(self) -> None:
        remote = _matching_web()
        result = diff_control_authority_offices(
            _fetch([remote]),
            (_matching_local(),),
        )
        self.assertEqual(len(result.items), 1)
        item = result.items[0]
        self.assertEqual(item.status, WEB_DIFF_STATUS_UNCHANGED)
        self.assertEqual(item.recommended_action, WEB_DIFF_ACTION_NONE)
        self.assertFalse(item.requires_manual_review)
        self.assertEqual(item.field_changes, ())
        self.assertEqual(result.count(WEB_DIFF_STATUS_UNCHANGED), 1)
        self.assertFalse(result.has_actionable_changes)
        self.assertFalse(result.has_conflicts)
        self.assertEqual(result.fetched_at, _FIXED_AT)
        self.assertIsInstance(result, ControlAuthorityWebDiffResult)
        self.assertIsInstance(item, ControlAuthorityOfficeDiff)
        self.assertFalse(hasattr(item, "ico"))
        self.assertNotIn("sqlalchemy", type(item.local).__module__)

    def test_02_normalization_whitespace_nbsp_url_phone_empty(self) -> None:
        local = _matching_local(
            name="  Pracoviště\xa0Praha  ",
            address="Bělehradská  222/128, 120 00 Praha 2",
            phone="226523368",
            email="",
            website="https://du.gov.cz/kontakty",
            source_url="https://du.gov.cz/kontakty/",
        )
        remote = _matching_web(
            name="Pracoviště Praha",
            address="Bělehradská 222/128, 120 00 Praha 2",
            phone="226 523 368",
            email=None,
            website="https://du.gov.cz/kontakty/",
            source_url="https://du.gov.cz/kontakty",
        )
        result = diff_control_authority_offices(_fetch([remote]), (local,))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_UNCHANGED)
        self.assertEqual(result.items[0].field_changes, ())

    def test_03_field_by_field_changes(self) -> None:
        cases = {
            "name": "Pracoviště Praha - Vinohrady",
            "address": "Jiná 1, 120 00 Praha 2",
            "phone": "111 222 333",
            "email": "praha@du.gov.cz",
            "website": "https://du.gov.cz/jine/",
            "territorial_scope": "Praha",
            "office_kind": OFFICE_KIND_TERRITORIAL,
            "source_url": "https://du.gov.cz/kontakty/praha/",
        }
        for field, new_value in cases.items():
            with self.subTest(field=field):
                remote = _matching_web(**{field: new_value})
                result = diff_control_authority_offices(
                    _fetch([remote]),
                    (_matching_local(),),
                )
                item = result.items[0]
                self.assertEqual(item.status, WEB_DIFF_STATUS_CHANGED)
                self.assertEqual(item.recommended_action, WEB_DIFF_ACTION_UPDATE)
                self.assertFalse(item.requires_manual_review)
                self.assertEqual(tuple(change.field for change in item.field_changes), (field,))
                self.assertEqual(item.field_changes[0].new_value, new_value)
        self.assertEqual(set(WEB_DIFF_COMPARED_FIELDS), set(cases))

    def test_04_prague_address_single_field_change(self) -> None:
        remote = _matching_web(address="Wilsonova 8, 120 00 Praha 2")
        result = diff_control_authority_offices(
            _fetch([remote]),
            (_matching_local(),),
        )
        changes = result.items[0].field_changes
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].field, "address")
        self.assertEqual(changes[0].old_value, "Bělehradská 222/128, 120 00 Praha 2")
        self.assertEqual(changes[0].new_value, "Wilsonova 8, 120 00 Praha 2")

    def test_05_new_office(self) -> None:
        remote = _matching_web(key="du:brno", name="Pracoviště Brno", address="Nádražní 1")
        result = diff_control_authority_offices(_fetch([remote]), ())
        item = result.items[0]
        self.assertEqual(item.status, WEB_DIFF_STATUS_NEW)
        self.assertEqual(item.recommended_action, WEB_DIFF_ACTION_CREATE)
        self.assertIsNone(item.local_id)
        self.assertTrue(result.has_actionable_changes)

    def test_06_possible_duplicate_by_name_address_and_city_scope(self) -> None:
        local = _matching_local()
        praha = _matching_web()
        by_name = _matching_web(
            key="du:brno",
            name=local.name,
            address="Nádražní 1, 602 00 Brno",
        )
        result = diff_control_authority_offices(_fetch([praha, by_name]), (local,))
        item = next(
            row for row in result.items if row.status == WEB_DIFF_STATUS_POSSIBLE_DUPLICATE
        )
        self.assertEqual(item.recommended_action, WEB_DIFF_ACTION_REVIEW)
        self.assertTrue(item.requires_manual_review)
        self.assertEqual(item.local_id, local.id)
        self.assertEqual(item.external_key, "du:brno")
        self.assertTrue(result.has_conflicts)
        self.assertEqual(result.count(WEB_DIFF_STATUS_UNCHANGED), 1)

        by_address = _matching_web(
            key="du:brno",
            name="Pracoviště Brno",
            address=local.address,
        )
        result = diff_control_authority_offices(_fetch([praha, by_address]), (local,))
        self.assertEqual(result.count(WEB_DIFF_STATUS_POSSIBLE_DUPLICATE), 1)

        local_scope = _matching_local(territorial_scope="Hlavní město Praha")
        praha_scope = _matching_web(territorial_scope="Hlavní město Praha")
        by_city = _matching_web(
            key="du:brno",
            name="Pracoviště Brno",
            address="Vinohradská 1, 120 00 Praha 2",
            territorial_scope="Hlavní město Praha",
        )
        result = diff_control_authority_offices(
            _fetch([praha_scope, by_city]),
            (local_scope,),
        )
        self.assertEqual(result.count(WEB_DIFF_STATUS_POSSIBLE_DUPLICATE), 1)

    def test_07_protected_manual_and_user_edited(self) -> None:
        remote = _matching_web(name="Nový název")
        manual = _matching_local(origin=AUTHORITY_ORIGIN_MANUAL)
        result = diff_control_authority_offices(_fetch([remote]), (manual,))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_PROTECTED)
        self.assertEqual(result.items[0].recommended_action, WEB_DIFF_ACTION_REVIEW)
        self.assertTrue(result.items[0].requires_manual_review)
        self.assertEqual(result.items[0].field_changes[0].field, "name")

        edited = _matching_local(
            origin=AUTHORITY_ORIGIN_WEB,
            user_edited_at=datetime(2026, 9, 1, 12, 0, 0),
        )
        result = diff_control_authority_offices(_fetch([remote]), (edited,))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_PROTECTED)

    def test_08_missing_remote_complete_only(self) -> None:
        praha = _matching_web()
        olomouc = _matching_local(
            office_id=3,
            key="du:olomouc",
            name="Pracoviště Olomouc",
            address="Nerudova 1, 779 00 Olomouc",
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        result = diff_control_authority_offices(
            _fetch([praha]),
            (_matching_local(), olomouc),
        )
        statuses = tuple(item.status for item in result.items)
        self.assertIn(WEB_DIFF_STATUS_MISSING_REMOTE, statuses)
        missing = next(
            item for item in result.items if item.status == WEB_DIFF_STATUS_MISSING_REMOTE
        )
        self.assertEqual(missing.external_key, "du:olomouc")
        self.assertEqual(missing.recommended_action, WEB_DIFF_ACTION_DEACTIVATE)
        self.assertTrue(missing.requires_manual_review)

        with self.assertRaises(ControlAuthorityWebDiffError) as ctx:
            diff_control_authority_offices(
                _fetch([praha], is_complete=False),
                (_matching_local(), olomouc),
            )
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_INCOMPLETE)

    def test_09_protected_missing_and_manual_without_key(self) -> None:
        praha = _matching_web()
        protected = _matching_local(
            office_id=3,
            key="du:olomouc",
            name="Pracoviště Olomouc",
            address="Nerudova 1",
            origin=AUTHORITY_ORIGIN_MANUAL,
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        manual_no_key = _matching_local(
            office_id=9,
            key=None,
            name="Ruční pobočka",
            address="Nádražní 5",
            origin=AUTHORITY_ORIGIN_MANUAL,
        )
        result = diff_control_authority_offices(
            _fetch([praha]),
            (_matching_local(), protected, manual_no_key),
        )
        statuses = {item.status: item for item in result.items}
        self.assertIn(WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE, statuses)
        self.assertEqual(
            statuses[WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE].recommended_action,
            WEB_DIFF_ACTION_REVIEW,
        )
        self.assertNotIn(
            "Ruční pobočka",
            [item.local.name for item in result.items if item.local is not None and item.remote is None],
        )
        self.assertEqual(len(result.items), 2)

    def test_10_inactive_present(self) -> None:
        remote = _matching_web(address="Wilsonova 8, 120 00 Praha 2")
        local = _matching_local(active=False)
        result = diff_control_authority_offices(_fetch([remote]), (local,))
        item = result.items[0]
        self.assertEqual(item.status, WEB_DIFF_STATUS_INACTIVE_PRESENT)
        self.assertEqual(item.recommended_action, WEB_DIFF_ACTION_REACTIVATE)
        self.assertTrue(item.requires_manual_review)
        self.assertEqual(item.field_changes[0].field, "address")

    def test_11_identity_and_duplicate_keys(self) -> None:
        remote = _matching_web()
        other = _matching_local(authority_code="suip", authority_id=1)
        result = diff_control_authority_offices(_fetch([remote]), (other,))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_IDENTITY_CONFLICT)
        self.assertEqual(result.items[0].recommended_action, WEB_DIFF_ACTION_REVIEW)
        self.assertTrue(result.has_conflicts)

        with self.assertRaises(ControlAuthorityWebDiffError) as ctx:
            diff_control_authority_offices(
                _fetch([remote, _matching_web()]),
                (_matching_local(),),
            )
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_DUPLICATE_REMOTE)

        with self.assertRaises(ControlAuthorityWebDiffError) as ctx:
            diff_control_authority_offices(
                _fetch([remote]),
                (_matching_local(), _matching_local(office_id=2)),
            )
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_DUPLICATE_LOCAL)

        with self.assertRaises(ControlAuthorityWebDiffError) as ctx:
            diff_control_authority_offices(
                ControlAuthorityWebFetchResult(
                    authority_code=DU_AUTHORITY_CODE,
                    source_url=DU_OFFICES_SOURCE_URL,
                    fetched_at=_FIXED_AT,
                    records=(
                        ControlAuthorityOfficeWebRecord(
                            authority_code=DU_AUTHORITY_CODE,
                            external_key="",
                            name="X",
                            address="Y",
                            phone=None,
                            email=None,
                            website=None,
                            territorial_scope=None,
                            office_kind=None,
                            source_url=DU_OFFICES_SOURCE_URL,
                        ),
                    ),
                    is_complete=True,
                ),
                (),
            )
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_MISSING_KEY)

    def test_12_du_fixture_versus_seed(self) -> None:
        records = _du_web_from_fixture()
        snapshots = _seed_du_snapshots()
        self.assertEqual(tuple(item.external_key for item in records), DU_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(tuple(item.external_key for item in snapshots), DU_OFFICE_EXTERNAL_KEYS)
        result = diff_control_authority_offices(_fetch(records), snapshots)
        self.assertEqual(result.count(WEB_DIFF_STATUS_UNCHANGED), 0)
        self.assertEqual(result.count(WEB_DIFF_STATUS_CHANGED), 3)
        self.assertEqual(result.count(WEB_DIFF_STATUS_NEW), 0)
        self.assertEqual(result.count(WEB_DIFF_STATUS_MISSING_REMOTE), 0)
        for item in result.items:
            self.assertEqual(item.status, WEB_DIFF_STATUS_CHANGED)
            fields = tuple(change.field for change in item.field_changes)
            self.assertEqual(fields, ("name",))
            self.assertNotIn("email", fields)
            self.assertNotIn("website", fields)
            self.assertNotIn("territorial_scope", fields)
            self.assertNotIn("display_order", fields)
            self.assertNotIn("origin", fields)
            self.assertNotIn("last_checked_at", fields)
            self.assertFalse(hasattr(item.local, "ico"))
            self.assertFalse(hasattr(item.remote, "ico"))

    def test_13_isolation_no_sqlalchemy_in_comparator(self) -> None:
        package = _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web"
        diff_source = (package / "diff.py").read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", diff_source)
        self.assertNotIn("PySide", diff_source)
        self.assertNotIn("create_office", diff_source)
        self.assertNotIn("update_office", diff_source)
        self.assertNotIn("deactivate", diff_source)
        service_source = (package / "catalog_snapshot_service.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("sess.commit", service_source)
        self.assertNotIn("session.commit", service_source)
        self.assertNotIn("flush(", service_source)
        self.assertNotIn("create_office", service_source)
        self.assertNotIn("update_office", service_source)
        self.assertNotIn("reactivate", service_source)
        seed_before = _SEED.read_bytes()
        diff_control_authority_offices(_fetch(_du_web_from_fixture()), _seed_du_snapshots())
        self.assertEqual(_SEED.read_bytes(), seed_before)


class StateSupervisionAuthorityWebDiff8d1CatalogLoadTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home_dir = Path(tempfile.mkdtemp(prefix="state-supervision-web-diff-8d1-"))
        cls._home = patch.object(Path, "home", return_value=cls._home_dir)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        from core.database.database_initializer import initialize_database

        initialize_database()
        cls.service = ControlAuthorityCatalogSnapshotService()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def _table_dump(self) -> tuple:
        db = storage_module.storage_service.database_path
        conn = sqlite3.connect(str(db))
        try:
            authorities = conn.execute(
                "SELECT id, code, origin, active, last_checked_at, user_edited_at "
                "FROM control_authorities ORDER BY id"
            ).fetchall()
            offices = conn.execute(
                "SELECT id, external_key, origin, active, last_checked_at, user_edited_at "
                "FROM control_authority_offices ORDER BY id"
            ).fetchall()
            supervisions = conn.execute(
                "SELECT id, authority_office_id FROM state_supervisions ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        return authorities, offices, supervisions

    def test_01_batch_load_and_no_write(self) -> None:
        statements: list[str] = []

        def _capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(str(statement))

        engine = session_module.engine
        event.listen(engine, "before_cursor_execute", _capture)
        before = self._table_dump()
        seed_before = _SEED.read_bytes()
        try:
            snapshots = self.service.load_office_snapshots("du")
        finally:
            event.remove(engine, "before_cursor_execute", _capture)
        self.assertEqual(len(snapshots), 3)
        self.assertEqual(
            tuple(item.external_key for item in snapshots),
            DU_OFFICE_EXTERNAL_KEYS,
        )
        selects = [
            item for item in statements if item.lstrip().upper().startswith("SELECT")
        ]
        self.assertEqual(len(selects), 2)
        self.assertFalse(
            any(
                item.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                for item in statements
            )
        )
        for snapshot in snapshots:
            self.assertIsInstance(snapshot, ControlAuthorityOfficeCatalogSnapshot)
            self.assertIsNone(snapshot.last_checked_at)
            self.assertFalse(hasattr(snapshot, "ico"))

        result = self.service.compare_web_result(_fetch(_du_web_from_fixture()))
        self.assertEqual(result.count(WEB_DIFF_STATUS_CHANGED), 3)
        self.assertEqual(self._table_dump(), before)
        self.assertEqual(_SEED.read_bytes(), seed_before)

    def test_02_missing_authority(self) -> None:
        with self.assertRaises(ControlAuthorityWebDiffError) as ctx:
            self.service.load_office_snapshots("neexistuje")
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND)


if __name__ == "__main__":
    unittest.main()
