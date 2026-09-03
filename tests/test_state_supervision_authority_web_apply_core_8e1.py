"""STATE-SUPERVISION-AUTHORITY-WEB-APPLY-CORE-8E1: atomické použití vybraných změn."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.database import session as session_module
from core.services import storage_service as storage_module
from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_MANUAL,
    AUTHORITY_ORIGIN_WEB,
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    DU_OFFICE_OBSERVED_FIELDS,
    DU_OFFICES_SOURCE_URL,
    OFFICE_KIND_TERRITORIAL,
    WEB_APPLY_ACTION_CREATE,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ACTION_REACTIVATE,
    WEB_APPLY_ACTION_UPDATE,
    WEB_APPLY_ERROR_DUPLICATE_SELECTION,
    WEB_APPLY_ERROR_FIELDS,
    WEB_APPLY_ERROR_INVALID_ACTION,
    WEB_APPLY_ERROR_PROTECTED,
    WEB_APPLY_ERROR_SELECTION,
    WEB_APPLY_ERROR_STALE,
    WEB_APPLY_ERROR_STATUS,
    WEB_APPLY_STALE_MESSAGE,
    WEB_DIFF_STATUS_IDENTITY_CONFLICT,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogError,
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityOfficeWebApplySelection,
    ControlAuthorityWebApplyError,
    apply_authority_web_changes,
)
from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    ControlAuthorityCatalogSnapshotService,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebCheckResult,
    get_web_adapter_info,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebFetchResult,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    state_supervision_service,
)

_REPO = Path(__file__).resolve().parents[1]
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_APPLY_SOURCE = (
    _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web" / "apply.py"
)
_FIXED_AT = datetime(2026, 9, 3, 9, 14, 0)
_NEW_KEY = "du:brno"


def _selection(
    *,
    key: str,
    action: str,
    local_id: int | None = None,
    selected_fields: frozenset[str] | None = None,
    confirm_protected: bool = False,
) -> ControlAuthorityOfficeWebApplySelection:
    return ControlAuthorityOfficeWebApplySelection(
        external_key=key,
        local_id=local_id,
        action=action,
        selected_fields=selected_fields or frozenset(),
        confirm_protected=confirm_protected,
    )


def _remote_from_office(office, *, observed=None, **overrides) -> ControlAuthorityOfficeWebRecord:
    payload = {
        "authority_code": DU_AUTHORITY_CODE,
        "external_key": office.external_key,
        "name": office.name,
        "address": office.address,
        "phone": office.phone,
        "email": office.email,
        "website": office.website,
        "territorial_scope": office.territorial_scope,
        "office_kind": office.office_kind,
        "source_url": office.source_url or DU_OFFICES_SOURCE_URL,
        "observed_fields": observed if observed is not None else DU_OFFICE_OBSERVED_FIELDS,
    }
    payload.update(overrides)
    return ControlAuthorityOfficeWebRecord(**payload)


class _ApplyCoreMixin:
    catalog = control_authority_catalog_service
    snapshots = ControlAuthorityCatalogSnapshotService()

    @classmethod
    def setUpClass(cls) -> None:
        cls._home_dir = Path(tempfile.mkdtemp(prefix="state-supervision-web-apply-8e1-"))
        cls._home = patch.object(Path, "home", return_value=cls._home_dir)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        from core.database.database_initializer import initialize_database

        initialize_database()
        cls.db = storage_module.storage_service.database_path
        conn = sqlite3.connect(str(cls.db))
        try:
            cls._office_cols = [
                str(row[1])
                for row in conn.execute("PRAGMA table_info(control_authority_offices)")
            ]
            cls._authority_cols = [
                str(row[1])
                for row in conn.execute("PRAGMA table_info(control_authorities)")
            ]
            cls._office_dump = conn.execute(
                "SELECT * FROM control_authority_offices ORDER BY id"
            ).fetchall()
            cls._authority_dump = conn.execute(
                "SELECT * FROM control_authorities ORDER BY id"
            ).fetchall()
        finally:
            conn.close()
        authority = control_authority_catalog_service.get_authority_by_code(
            DU_AUTHORITY_CODE
        )
        office = control_authority_catalog_service.get_office_by_external_key(
            "du:praha"
        )
        state_supervision_service.create_supervision(
            authority_name=authority.name,
            authority_id=authority.id,
            authority_office_id=office.id,
            authority_office_name_snapshot=office.name,
            authority_address=office.address,
        )
        conn = sqlite3.connect(str(cls.db))
        try:
            cls._supervision_dump = conn.execute(
                "SELECT * FROM state_supervisions ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.db = type(self).db
        self._restore_catalog()

    def _restore_catalog(self) -> None:
        conn = sqlite3.connect(str(self.db))
        try:
            original_ids = [row[0] for row in self._office_dump]
            placeholders = ",".join("?" * len(original_ids))
            conn.execute(
                f"DELETE FROM control_authority_offices WHERE id NOT IN ({placeholders})",
                original_ids,
            )
            office_cols = self._office_cols
            for row in self._office_dump:
                assignments = ",".join(
                    f'"{col}"=?' for col in office_cols if col != "id"
                )
                values = [
                    row[office_cols.index(col)] for col in office_cols if col != "id"
                ]
                conn.execute(
                    f"UPDATE control_authority_offices SET {assignments} WHERE id=?",
                    values + [row[0]],
                )
            authority_cols = self._authority_cols
            for row in self._authority_dump:
                assignments = ",".join(
                    f'"{col}"=?' for col in authority_cols if col != "id"
                )
                values = [
                    row[authority_cols.index(col)]
                    for col in authority_cols
                    if col != "id"
                ]
                conn.execute(
                    f"UPDATE control_authorities SET {assignments} WHERE id=?",
                    values + [row[0]],
                )
            conn.commit()
        finally:
            conn.close()


    def _office(self, key: str):
        office = self.catalog.get_office_by_external_key(key)
        self.assertIsNotNone(office)
        return office

    def _offices(self) -> dict:
        return {key: self._office(key) for key in DU_OFFICE_EXTERNAL_KEYS}

    def _authority(self):
        authority = self.catalog.get_authority_by_code(DU_AUTHORITY_CODE)
        self.assertIsNotNone(authority)
        return authority

    def _check(self, records) -> ControlAuthorityWebCheckResult:
        records = tuple(records)
        fetch = ControlAuthorityWebFetchResult(
            authority_code=DU_AUTHORITY_CODE,
            source_url=DU_OFFICES_SOURCE_URL,
            fetched_at=_FIXED_AT,
            records=records,
            is_complete=True,
        )
        info = get_web_adapter_info(DU_AUTHORITY_CODE)
        diff = diff_control_authority_offices(
            fetch,
            self.snapshots.load_office_snapshots(DU_AUTHORITY_CODE),
            info.coverage,
        )
        return ControlAuthorityWebCheckResult(
            authority_code=DU_AUTHORITY_CODE,
            adapter_info=info,
            fetched_at=_FIXED_AT,
            source_url=DU_OFFICES_SOURCE_URL,
            remote_records=records,
            diffs=diff.items,
            status_counts=diff.status_counts,
            warnings=diff.warnings,
            has_actionable_changes=diff.has_actionable_changes,
            has_conflicts=diff.has_conflicts,
            fetch_result=fetch,
            diff_result=diff,
        )

    def _matching_remotes(self, **changes_by_key):
        remotes = []
        for key in DU_OFFICE_EXTERNAL_KEYS:
            office = self._office(key)
            overrides = changes_by_key.get(key, {})
            remotes.append(_remote_from_office(office, **overrides))
        return remotes

    def _diff_for(self, check: ControlAuthorityWebCheckResult, key: str):
        matches = [item for item in check.diffs if item.external_key == key]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def _sql(self, sql: str, params=()) -> None:
        conn = sqlite3.connect(str(self.db))
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def _dump_supervisions(self) -> list:
        conn = sqlite3.connect(str(self.db))
        try:
            return list(
                conn.execute("SELECT * FROM state_supervisions ORDER BY id").fetchall()
            )
        finally:
            conn.close()

    def _dump_offices(self) -> list:
        conn = sqlite3.connect(str(self.db))
        try:
            return list(
                conn.execute(
                    "SELECT id, authority_id, external_key, name, address, phone, "
                    "email, website, territorial_scope, office_kind, source_url, "
                    "active, origin, user_edited_at, last_checked_at, created_at "
                    "FROM control_authority_offices ORDER BY id"
                ).fetchall()
            )
        finally:
            conn.close()

    def _count_commits(self, func) -> tuple[int, object]:
        commits: list[str] = []
        original = Session.commit

        def wrapped(self_session, *args, **kwargs):
            commits.append("commit")
            return original(self_session, *args, **kwargs)

        with patch.object(Session, "commit", wrapped):
            result = func()
        return len(commits), result


class StateSupervisionAuthorityWebApplyCore8e1TestCase(_ApplyCoreMixin, unittest.TestCase):
    def test_01_update_one_selected_field(self) -> None:
        offices = self._offices()
        original_address = offices["du:praha"].address
        remotes = self._matching_remotes(
            **{
                "du:praha": {
                    "name": "Drážní úřad Praha – web",
                    "address": "Jiná adresa 1, Praha",
                }
            }
        )
        check = self._check(remotes)
        praha = self._diff_for(check, "du:praha")
        result = apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=praha.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        updated = self._office("du:praha")
        self.assertEqual(result.updated_ids, (updated.id,))
        self.assertEqual(result.applied_count, 1)
        self.assertEqual(updated.name, "Drážní úřad Praha – web")
        self.assertEqual(updated.address, original_address)
        self.assertNotEqual(updated.address, "Jiná adresa 1, Praha")

    def test_02_update_multiple_fields(self) -> None:
        remotes = self._matching_remotes(
            **{
                "du:plzen": {
                    "name": "Drážní úřad Plzeň – web",
                    "address": "Nová 2, Plzeň",
                }
            }
        )
        check = self._check(remotes)
        item = self._diff_for(check, "du:plzen")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:plzen",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name", "address"}),
                )
            ],
        )
        updated = self._office("du:plzen")
        self.assertEqual(updated.name, "Drážní úřad Plzeň – web")
        self.assertEqual(updated.address, "Nová 2, Plzeň")

    def test_03_observed_explicit_none_is_saved(self) -> None:
        original = self._office("du:olomouc")
        self.assertIsNotNone(original.phone)
        remotes = self._matching_remotes(**{"du:olomouc": {"phone": None}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:olomouc")
        self.assertIn("phone", {change.field for change in item.field_changes})
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:olomouc",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"phone"}),
                )
            ],
        )
        self.assertIsNone(self._office("du:olomouc").phone)

    def test_04_unobserved_none_cannot_be_injected(self) -> None:
        original = self._office("du:praha")
        self.assertIsNotNone(original.email)
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"email"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_FIELDS)
        self.assertEqual(self._office("du:praha").email, original.email)
        self.assertEqual(self._office("du:praha").name, original.name)

    def test_05_create_new_web_office(self) -> None:
        olomouc = self._office("du:olomouc")
        remote_olomouc = _remote_from_office(olomouc)
        self._sql(
            "UPDATE control_authority_offices SET external_key=NULL, name=?, address=? WHERE id=?",
            ("Dočasně skryté Olomouc", "Skrytá 1, Olomouc", olomouc.id),
        )
        remotes = [
            _remote_from_office(self._office("du:praha")),
            _remote_from_office(self._office("du:plzen")),
            remote_olomouc,
        ]
        check = self._check(remotes)
        item = self._diff_for(check, "du:olomouc")
        result = apply_authority_web_changes(
            check,
            [_selection(key="du:olomouc", local_id=None, action=WEB_APPLY_ACTION_CREATE)],
        )
        created = self.catalog.get_office_by_external_key("du:olomouc")
        self.assertIsNotNone(created)
        self.assertEqual(result.created_ids, (created.id,))
        self.assertEqual(created.origin, AUTHORITY_ORIGIN_WEB)
        self.assertTrue(created.active)
        self.assertIsNone(created.user_edited_at)
        self.assertEqual(created.last_checked_at, _FIXED_AT)
        self.assertEqual(created.external_key, "du:olomouc")
        self.assertEqual(created.authority_id, self._authority().id)
        self.assertEqual(created.name, remote_olomouc.name)
        self.assertEqual(created.address, remote_olomouc.address)

    def test_06_explicit_deactivate_missing_remote(self) -> None:
        extra = self.catalog.create_imported_office(
            authority_id=self._authority().id,
            name="Drážní úřad – pracoviště Brno",
            origin=AUTHORITY_ORIGIN_WEB,
            address="Nádražní 1, 602 00 Brno",
            office_kind=OFFICE_KIND_TERRITORIAL,
            external_key=_NEW_KEY,
            source_url=DU_OFFICES_SOURCE_URL,
        )
        remotes = self._matching_remotes()
        check = self._check(remotes)
        item = self._diff_for(check, _NEW_KEY)
        result = apply_authority_web_changes(
            check,
            [
                _selection(
                    key=_NEW_KEY,
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_DEACTIVATE,
                )
            ],
        )
        deactivated = self.catalog.get_office(int(extra.id))
        self.assertEqual(result.deactivated_ids, (deactivated.id,))
        self.assertFalse(deactivated.active)
        self.assertEqual(deactivated.last_checked_at, _FIXED_AT)
        self.assertEqual(deactivated.external_key, _NEW_KEY)

    def test_07_explicit_reactivate_inactive_present(self) -> None:
        office = self._office("du:olomouc")
        self.catalog.deactivate_office(office.id, mark_user_edited=False)
        remotes = self._matching_remotes()
        check = self._check(remotes)
        item = self._diff_for(check, "du:olomouc")
        self.assertEqual(item.status, "inactive_present")
        result = apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:olomouc",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_REACTIVATE,
                )
            ],
        )
        restored = self._office("du:olomouc")
        self.assertEqual(result.reactivated_ids, (restored.id,))
        self.assertTrue(restored.active)
        self.assertEqual(restored.name, office.name)
        self.assertEqual(restored.address, office.address)
        self.assertEqual(restored.last_checked_at, _FIXED_AT)

    def test_08_empty_selection_writes_nothing(self) -> None:
        before_offices = self._dump_offices()
        before_authority = self._authority().last_checked_at
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název"}})
        check = self._check(remotes)
        commits, result = self._count_commits(
            lambda: apply_authority_web_changes(check, [])
        )
        self.assertEqual(result.applied_count, 0)
        self.assertEqual(commits, 0)
        self.assertEqual(self._dump_offices(), before_offices)
        self.assertEqual(self._authority().last_checked_at, before_authority)

    def test_09_unchanged_cannot_be_applied(self) -> None:
        check = self._check(self._matching_remotes())
        item = self._diff_for(check, "du:praha")
        self.assertEqual(item.status, WEB_DIFF_STATUS_UNCHANGED)
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STATUS)

    def test_10_possible_duplicate_cannot_be_applied(self) -> None:
        authority = self._authority()
        olomouc = self._office("du:olomouc")
        remote_olomouc = _remote_from_office(olomouc)
        self.catalog.create_office(
            authority_id=authority.id,
            name=olomouc.name,
            address="Jiná 9, Olomouc",
        )
        self._sql(
            "UPDATE control_authority_offices SET external_key=NULL, name=?, address=? WHERE id=?",
            ("Dočasně skryté Olomouc", "Skrytá 1, Olomouc", olomouc.id),
        )
        remotes = [
            _remote_from_office(self._office("du:praha")),
            _remote_from_office(self._office("du:plzen")),
            remote_olomouc,
        ]
        check = self._check(remotes)
        item = self._diff_for(check, "du:olomouc")
        self.assertEqual(item.status, "possible_duplicate")
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:olomouc",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_CREATE,
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STATUS)
        self.assertIsNone(self.catalog.get_office_by_external_key("du:olomouc"))

    def test_11_identity_conflict_cannot_be_applied(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        tampered = replace(
            check,
            diffs=tuple(
                replace(diff, status=WEB_DIFF_STATUS_IDENTITY_CONFLICT)
                if diff.external_key == "du:praha"
                else diff
                for diff in check.diffs
            ),
        )
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                tampered,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STATUS)

    def test_12_protected_without_confirmation_is_rejected(self) -> None:
        office = self._office("du:praha")
        self.catalog.update_office(office.id, name=office.name)
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        self.assertEqual(item.status, "protected")
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_PROTECTED)

    def test_13_protected_with_confirmation_updates_only_selected_fields(self) -> None:
        office = self._office("du:praha")
        original_address = office.address
        self.catalog.update_office(office.id, name=office.name)
        remotes = self._matching_remotes(
            **{
                "du:praha": {
                    "name": "Webový název Praha",
                    "address": "Webová adresa 1",
                }
            }
        )
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                    confirm_protected=True,
                )
            ],
        )
        updated = self._office("du:praha")
        self.assertEqual(updated.name, "Webový název Praha")
        self.assertEqual(updated.address, original_address)

    def test_14_protected_keeps_manual_origin_and_user_edited_at(self) -> None:
        office = self._office("du:praha")
        protected = self.catalog.update_office(office.id, name=office.name)
        edited_at = protected.user_edited_at
        self.assertEqual(protected.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertIsNotNone(edited_at)
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                    confirm_protected=True,
                )
            ],
        )
        updated = self._office("du:praha")
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_MANUAL)
        self.assertEqual(updated.user_edited_at, edited_at)
        self.assertEqual(updated.last_checked_at, _FIXED_AT)

    def test_15_plain_web_update_sets_origin_web(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        updated = self._office("du:praha")
        self.assertEqual(updated.origin, AUTHORITY_ORIGIN_WEB)
        self.assertIsNone(updated.user_edited_at)
        self.assertEqual(updated.last_checked_at, _FIXED_AT)

    def test_16_last_checked_at_only_on_affected_offices(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        self.assertEqual(self._office("du:praha").last_checked_at, _FIXED_AT)
        self.assertIsNone(self._office("du:plzen").last_checked_at)
        self.assertIsNone(self._office("du:olomouc").last_checked_at)

    def test_17_authority_last_checked_at_after_successful_batch(self) -> None:
        authority = self._authority()
        self.assertIsNone(authority.last_checked_at)
        origin = authority.origin
        edited = authority.user_edited_at
        name = authority.name
        abbreviation = authority.abbreviation
        website = authority.website
        source_url = authority.source_url
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        updated = self._authority()
        self.assertEqual(updated.last_checked_at, _FIXED_AT)
        self.assertEqual(updated.origin, origin)
        self.assertEqual(updated.user_edited_at, edited)
        self.assertEqual(updated.name, name)
        self.assertEqual(updated.abbreviation, abbreviation)
        self.assertEqual(updated.website, website)
        self.assertEqual(updated.source_url, source_url)


class StateSupervisionAuthorityWebApplySafety8e1TestCase(_ApplyCoreMixin, unittest.TestCase):
    def test_01_stale_name_rejects_whole_batch(self) -> None:
        remotes = self._matching_remotes(
            **{
                "du:praha": {"name": "Webový název Praha"},
                "du:plzen": {"name": "Webový název Plzeň"},
            }
        )
        check = self._check(remotes)
        praha = self._diff_for(check, "du:praha")
        plzen = self._diff_for(check, "du:plzen")
        self._sql(
            "UPDATE control_authority_offices SET name=? WHERE external_key=?",
            ("Mezitím změněný název", "du:praha"),
        )
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=praha.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    ),
                    _selection(
                        key="du:plzen",
                        local_id=plzen.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    ),
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STALE)
        self.assertIn("Spusťte kontrolu znovu", str(ctx.exception))
        self.assertEqual(self._office("du:praha").name, "Mezitím změněný název")
        self.assertNotEqual(self._office("du:plzen").name, "Webový název Plzeň")

    def test_02_stale_active_is_rejected(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        self._sql(
            "UPDATE control_authority_offices SET active=0 WHERE external_key=?",
            ("du:praha",),
        )
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STALE)
        self.assertEqual(str(ctx.exception), WEB_APPLY_STALE_MESSAGE)

    def test_03_stale_origin_and_user_edited_at_is_rejected(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        self._sql(
            "UPDATE control_authority_offices SET origin=?, user_edited_at=? "
            "WHERE external_key=?",
            (AUTHORITY_ORIGIN_MANUAL, "2026-01-02 10:00:00", "du:praha"),
        )
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STALE)

    def test_04_new_external_key_created_meanwhile_is_rejected(self) -> None:
        olomouc = self._office("du:olomouc")
        remote_olomouc = _remote_from_office(olomouc)
        self._sql(
            "UPDATE control_authority_offices SET external_key=NULL, name=?, address=? WHERE id=?",
            ("Dočasně skryté Olomouc", "Skrytá 1, Olomouc", olomouc.id),
        )
        remotes = [
            _remote_from_office(self._office("du:praha")),
            _remote_from_office(self._office("du:plzen")),
            remote_olomouc,
        ]
        check = self._check(remotes)
        self.catalog.create_imported_office(
            authority_id=self._authority().id,
            name="Mezitím založené Olomouc",
            origin=AUTHORITY_ORIGIN_WEB,
            external_key="du:olomouc",
        )
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [_selection(key="du:olomouc", local_id=None, action=WEB_APPLY_ACTION_CREATE)],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_STALE)
        self.assertEqual(
            self.catalog.get_office_by_external_key("du:olomouc").name,
            "Mezitím založené Olomouc",
        )

    def test_05_second_row_error_rolls_back_first(self) -> None:
        remotes = self._matching_remotes(
            **{
                "du:praha": {"name": "Webový název Praha"},
                "du:plzen": {"name": "Webový název Plzeň"},
            }
        )
        check = self._check(remotes)
        praha = self._diff_for(check, "du:praha")
        plzen = self._diff_for(check, "du:plzen")
        original_praha = self._office("du:praha").name
        original_plzen = self._office("du:plzen").name
        calls = {"n": 0}
        original = self.catalog.update_imported_office

        def boom(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise ControlAuthorityCatalogError("druhý řádek selhal")
            return original(*args, **kwargs)

        with patch.object(self.catalog, "update_imported_office", boom):
            with self.assertRaises(ControlAuthorityCatalogError) as ctx:
                apply_authority_web_changes(
                    check,
                    [
                        _selection(
                            key="du:praha",
                            local_id=praha.local_id,
                            action=WEB_APPLY_ACTION_UPDATE,
                            selected_fields=frozenset({"name"}),
                        ),
                        _selection(
                            key="du:plzen",
                            local_id=plzen.local_id,
                            action=WEB_APPLY_ACTION_UPDATE,
                            selected_fields=frozenset({"name"}),
                        ),
                    ],
                )
        self.assertEqual(str(ctx.exception), "druhý řádek selhal")
        self.assertEqual(self._office("du:praha").name, original_praha)
        self.assertEqual(self._office("du:plzen").name, original_plzen)

    def test_06_foreign_local_id_is_rejected(self) -> None:
        foreign = self.catalog.get_office_by_external_key("suip:oip-praha")
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=foreign.id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_SELECTION)
        self.assertNotEqual(self._office("du:praha").name, "Webový název Praha")

    def test_07_duplicate_selection_is_rejected(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        selection = _selection(
            key="du:praha",
            local_id=item.local_id,
            action=WEB_APPLY_ACTION_UPDATE,
            selected_fields=frozenset({"name"}),
        )
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(check, [selection, selection])
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_DUPLICATE_SELECTION)

    def test_08_foreign_selected_field_is_rejected(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"display_order"}),
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_FIELDS)

    def test_09_arbitrary_new_value_cannot_be_injected(self) -> None:
        fields = ControlAuthorityOfficeWebApplySelection.__dataclass_fields__
        self.assertNotIn("new_value", fields)
        self.assertNotIn("name", fields)
        self.assertNotIn("address", fields)
        self.assertNotIn("website", fields)
        signature = inspect.signature(apply_authority_web_changes)
        self.assertNotIn("new_value", signature.parameters)
        self.assertNotIn("name", signature.parameters)
        self.assertNotIn("address", signature.parameters)
        self.assertNotIn("external_key", signature.parameters)
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        self.assertEqual(self._office("du:praha").name, "Webový název Praha")
        self.assertNotEqual(self._office("du:praha").name, "Podstrčený název")

    def test_10_exactly_one_commit(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        commits, result = self._count_commits(
            lambda: apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        )
        self.assertEqual(commits, 1)
        self.assertEqual(result.applied_count, 1)

    def test_11_no_physical_delete(self) -> None:
        from sqlalchemy import event

        statements: list[str] = []

        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(str(statement))

        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        engine = session_module.engine
        event.listen(engine, "before_cursor_execute", capture)
        try:
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        self.assertFalse(
            any(item.lstrip().upper().startswith("DELETE") for item in statements)
        )

    def test_12_state_supervisions_and_snapshots_unchanged(self) -> None:
        before = self._dump_supervisions()
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        self.assertEqual(self._dump_supervisions(), before)
        self.assertEqual(before, self._supervision_dump)

    def test_13_seed_json_unchanged(self) -> None:
        seed_before = _SEED.read_bytes()
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        apply_authority_web_changes(
            check,
            [
                _selection(
                    key="du:praha",
                    local_id=item.local_id,
                    action=WEB_APPLY_ACTION_UPDATE,
                    selected_fields=frozenset({"name"}),
                )
            ],
        )
        self.assertEqual(_SEED.read_bytes(), seed_before)

    def test_14_no_http_during_apply(self) -> None:
        source = _APPLY_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("http_get", source)
        self.assertNotIn("requests", source)
        self.assertNotIn("fetch_du_offices", source)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("PySide", source)
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        with (
            patch(
                "moduly.statni_dozor.sluzby.control_authority_web.du_adapter.fetch_du_offices"
            ) as fetch_du,
            patch(
                "moduly.statni_dozor.sluzby.control_authority_web.check.check_authority_web"
            ) as check_web,
        ):
            apply_authority_web_changes(
                check,
                [
                    _selection(
                        key="du:praha",
                        local_id=item.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset({"name"}),
                    )
                ],
            )
        fetch_du.assert_not_called()
        check_web.assert_not_called()

    def test_15_none_and_review_are_not_apply_actions(self) -> None:
        remotes = self._matching_remotes(**{"du:praha": {"name": "Webový název Praha"}})
        check = self._check(remotes)
        item = self._diff_for(check, "du:praha")
        for action in ("none", "review", "delete"):
            with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
                apply_authority_web_changes(
                    check,
                    [
                        _selection(
                            key="du:praha",
                            local_id=item.local_id,
                            action=action,
                            selected_fields=frozenset({"name"}),
                        )
                    ],
                )
            self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_INVALID_ACTION)


if __name__ == "__main__":
    unittest.main()
