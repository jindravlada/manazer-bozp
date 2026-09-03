"""STATE-SUPERVISION-AUTHORITY-WEB-DIFF-PRESENCE-8D1A: nezjištěné webové údaje."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    DU_AUTHORITY_CODE,
    DU_OFFICE_OBSERVED_FIELDS,
    DU_OFFICES_SOURCE_URL,
    OFFICE_KIND_HEADQUARTERS,
    WEB_DIFF_COMPARED_FIELDS,
    WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_UNCHANGED,
    WEB_DIFF_UNKNOWN_OBSERVED_FIELD_MESSAGE,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
)
from moduly.statni_dozor.sluzby.control_authority_web.du_adapter import (
    parse_du_offices_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
)

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "du_kontakty.html"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 7, 50, 0)
_OBSERVED_CORE = frozenset(
    {"name", "address", "phone", "office_kind", "source_url"}
)


def _web(
    *,
    observed_fields: frozenset[str],
    key: str = "du:praha",
    name: str = "Pracoviště Praha",
    address: str | None = "Bělehradská 222/128, 120 00 Praha 2",
    phone: str | None = "226 523 368",
    email: str | None = None,
    website: str | None = None,
    territorial_scope: str | None = None,
    office_kind: str | None = OFFICE_KIND_HEADQUARTERS,
) -> ControlAuthorityOfficeWebRecord:
    return ControlAuthorityOfficeWebRecord(
        authority_code=DU_AUTHORITY_CODE,
        external_key=key,
        name=name,
        address=address,
        phone=phone,
        email=email,
        website=website,
        territorial_scope=territorial_scope,
        office_kind=office_kind,
        source_url=DU_OFFICES_SOURCE_URL,
        observed_fields=observed_fields,
    )


def _local(
    *,
    email: str | None = "podatelna@du.gov.cz",
    website: str | None = "https://du.gov.cz/kontakty/",
    phone: str | None = "226 523 368",
    name: str = "Pracoviště Praha",
) -> ControlAuthorityOfficeCatalogSnapshot:
    return ControlAuthorityOfficeCatalogSnapshot(
        id=1,
        authority_id=50,
        authority_code=DU_AUTHORITY_CODE,
        external_key="du:praha",
        name=name,
        address="Bělehradská 222/128, 120 00 Praha 2",
        phone=phone,
        email=email,
        website=website,
        territorial_scope=None,
        office_kind=OFFICE_KIND_HEADQUARTERS,
        source_url=DU_OFFICES_SOURCE_URL,
        active=True,
        origin=AUTHORITY_ORIGIN_BUNDLED,
        user_edited_at=None,
        last_checked_at=None,
    )


def _fetch(records) -> ControlAuthorityWebFetchResult:
    return ControlAuthorityWebFetchResult(
        authority_code=DU_AUTHORITY_CODE,
        source_url=DU_OFFICES_SOURCE_URL,
        fetched_at=_FIXED_AT,
        records=tuple(records),
        is_complete=True,
    )


class StateSupervisionAuthorityWebDiffPresence8d1aTestCase(unittest.TestCase):
    def test_01_unobserved_none_email_does_not_clear_local(self) -> None:
        remote = _web(observed_fields=_OBSERVED_CORE, email=None)
        result = diff_control_authority_offices(_fetch([remote]), (_local(),))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_UNCHANGED)
        self.assertEqual(result.items[0].field_changes, ())

    def test_02_unobserved_none_website_does_not_clear_local(self) -> None:
        remote = _web(observed_fields=_OBSERVED_CORE, website=None)
        result = diff_control_authority_offices(_fetch([remote]), (_local(),))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_UNCHANGED)
        fields = tuple(change.field for change in result.items[0].field_changes)
        self.assertNotIn("website", fields)

    def test_03_observed_phone_difference_creates_change(self) -> None:
        remote = _web(observed_fields=_OBSERVED_CORE, phone="111 222 333")
        result = diff_control_authority_offices(_fetch([remote]), (_local(),))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_CHANGED)
        self.assertEqual(
            tuple(change.field for change in result.items[0].field_changes),
            ("phone",),
        )
        self.assertEqual(result.items[0].field_changes[0].new_value, "111 222 333")

    def test_04_observed_explicit_none_email_creates_change(self) -> None:
        remote = _web(
            observed_fields=_OBSERVED_CORE | {"email"},
            email=None,
        )
        result = diff_control_authority_offices(_fetch([remote]), (_local(),))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_CHANGED)
        change = result.items[0].field_changes[0]
        self.assertEqual(change.field, "email")
        self.assertEqual(change.old_value, "podatelna@du.gov.cz")
        self.assertIsNone(change.new_value)

    def test_05_unknown_observed_field_is_rejected(self) -> None:
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            _web(observed_fields=_OBSERVED_CORE | {"ico"})
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD)
        self.assertEqual(str(ctx.exception), WEB_DIFF_UNKNOWN_OBSERVED_FIELD_MESSAGE)
        self.assertNotIn("<html", str(ctx.exception))

    def test_06_du_fixture_versus_seed_only_name_changes(self) -> None:
        records = parse_du_offices_html(_FIXTURE.read_text(encoding="utf-8"))
        payload = json.loads(_SEED.read_text(encoding="utf-8"))
        du = next(item for item in payload["authorities"] if item["code"] == "du")
        snapshots = []
        for index, office in enumerate(du["offices"], start=1):
            snapshots.append(
                ControlAuthorityOfficeCatalogSnapshot(
                    id=index,
                    authority_id=50,
                    authority_code=DU_AUTHORITY_CODE,
                    external_key=office["external_key"],
                    name=office["name"],
                    address=office["address"],
                    phone=office.get("phone"),
                    email=office.get("email"),
                    website=office.get("website"),
                    territorial_scope=office.get("territorial_scope"),
                    office_kind=office["office_kind"],
                    source_url=office.get("source_url"),
                    active=True,
                    origin=office.get("origin", AUTHORITY_ORIGIN_BUNDLED),
                    user_edited_at=None,
                    last_checked_at=None,
                )
            )
        for record in records:
            self.assertEqual(record.observed_fields, DU_OFFICE_OBSERVED_FIELDS)
            self.assertTrue(record.observed_fields.isdisjoint({"email", "website", "territorial_scope"}))
        result = diff_control_authority_offices(_fetch(records), tuple(snapshots))
        self.assertEqual(result.count(WEB_DIFF_STATUS_UNCHANGED), 0)
        self.assertEqual(result.count(WEB_DIFF_STATUS_CHANGED), 3)
        for item, record in zip(result.items, records, strict=True):
            self.assertEqual(item.status, WEB_DIFF_STATUS_CHANGED)
            self.assertEqual(
                tuple(change.field for change in item.field_changes),
                ("name",),
            )
            self.assertEqual(item.remote.observed_fields, record.observed_fields)
            self.assertEqual(item.local.address, record.address)
            self.assertEqual(item.local.phone, record.phone)
            self.assertEqual(item.local.office_kind, record.office_kind)

    def test_07_unchanged_uses_only_observed_fields(self) -> None:
        remote = _web(
            observed_fields=_OBSERVED_CORE,
            email=None,
            website=None,
            territorial_scope=None,
        )
        local = _local(
            email="jiny@du.gov.cz",
            website="https://example.com/",
        )
        result = diff_control_authority_offices(_fetch([remote]), (local,))
        self.assertEqual(result.items[0].status, WEB_DIFF_STATUS_UNCHANGED)
        self.assertFalse(result.has_actionable_changes)
        self.assertEqual(set(WEB_DIFF_COMPARED_FIELDS) - _OBSERVED_CORE, {"email", "website", "territorial_scope"})

    def test_08_comparison_remains_read_only(self) -> None:
        package = _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web"
        diff_source = (package / "diff.py").read_text(encoding="utf-8")
        service_source = (package / "catalog_snapshot_service.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("INSERT", diff_source)
        self.assertNotIn("commit", diff_source)
        self.assertNotIn("create_office", diff_source)
        self.assertNotIn("update_office", service_source)
        self.assertNotIn("sess.commit", service_source)
        seed_before = _SEED.read_bytes()
        records = parse_du_offices_html(_FIXTURE.read_text(encoding="utf-8"))
        local = _local()
        before = (
            local.origin,
            local.active,
            local.user_edited_at,
            local.last_checked_at,
        )
        result = diff_control_authority_offices(_fetch(records[:1]), (local,))
        self.assertEqual(
            (
                result.items[0].local.origin,
                result.items[0].local.active,
                result.items[0].local.user_edited_at,
                result.items[0].local.last_checked_at,
            ),
            before,
        )
        self.assertEqual(_SEED.read_bytes(), seed_before)


if __name__ == "__main__":
    unittest.main()
