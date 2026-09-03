"""STATE-SUPERVISION-AUTHORITY-WEB-HZS-8D5: read-only adapter krajských HZS."""

from __future__ import annotations

import inspect
import json
import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    HZS_AUTHORITY_CODE,
    HZS_OFFICE_EXTERNAL_KEYS,
    HZS_OFFICES_SOURCE_URL,
    HZS_REGION_SLUGS,
    OFFICE_KIND_REGIONAL,
    WEB_ADAPTER_ERROR_DUPLICATE_KEY,
    WEB_ADAPTER_ERROR_INCOMPLETE,
    WEB_ADAPTER_ERROR_INVALID_URL,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
)
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpClient,
    ControlAuthorityHttpResponse,
)
from moduly.statni_dozor.sluzby.control_authority_web.hzs_adapter import (
    HZS_ALLOWED_HOSTS,
    fetch_hzs_offices,
    hzs_office_website,
    parse_hzs_offices_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
)

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "hzs_kraju.html"
_ADAPTER = (
    _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web" / "hzs_adapter.py"
)
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 8, 41, 0)
_ZLINSKY_CARD = """    <div>
      <a class="no-underline!" href="/zlinsky-kraj">
        <div class="text-headline-s">Zlínský kraj</div>
      </a>
    </div>
"""
_PRAHA_CARD = """    <div>
      <a class="no-underline!" href="/hlavni-mesto-praha">
        <div class="text-headline-s">Hlavní město Praha</div>
      </a>
    </div>
"""


def _fixture_html() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


def _html_response(html: str, url: str = HZS_OFFICES_SOURCE_URL) -> ControlAuthorityHttpResponse:
    return ControlAuthorityHttpResponse(
        status_code=200,
        body=html.encode("utf-8"),
        content_type="text/html",
        final_url=url,
    )


class _FakeRawResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        headers: dict | None = None,
    ):
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html"}
        self.closed = False

    def iter_content(self, chunk_size=8192):
        yield from ()

    def close(self) -> None:
        self.closed = True


def _parse_fixture():
    return parse_hzs_offices_html(_fixture_html(), source_url=HZS_OFFICES_SOURCE_URL)


def _seed_hzs_snapshots() -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    hzs = next(item for item in payload["authorities"] if item["code"] == "hzs")
    snapshots = []
    for index, office in enumerate(hzs["offices"], start=1):
        snapshots.append(
            ControlAuthorityOfficeCatalogSnapshot(
                id=index,
                authority_id=40,
                authority_code=HZS_AUTHORITY_CODE,
                external_key=office["external_key"],
                name=office["name"],
                address=office.get("address"),
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
    return tuple(snapshots)


class StateSupervisionAuthorityWebHzs8d5TestCase(unittest.TestCase):
    def test_01_fixture_has_exactly_fourteen_regional_hzs(self) -> None:
        records = _parse_fixture()
        self.assertEqual(len(records), 14)
        self.assertEqual(
            tuple(item.external_key for item in records),
            HZS_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(records[0].name, "Hlavní město Praha")
        self.assertEqual(records[1].name, "Středočeský kraj")
        self.assertEqual(records[-1].name, "Zlínský kraj")
        self.assertEqual(records[9].name, "Kraj Vysočina")
        self.assertEqual(records[0].website, hzs_office_website("hlavni-mesto-praha"))
        self.assertEqual(records[9].website, hzs_office_website("vysocina-kraj"))
        for record, slug in zip(records, HZS_REGION_SLUGS, strict=True):
            self.assertEqual(record.authority_code, HZS_AUTHORITY_CODE)
            self.assertEqual(record.office_kind, OFFICE_KIND_REGIONAL)
            self.assertEqual(record.source_url, HZS_OFFICES_SOURCE_URL)
            self.assertEqual(record.website, hzs_office_website(slug))
            self.assertEqual(
                record.observed_fields,
                frozenset({"name", "website", "office_kind", "source_url"}),
            )
            self.assertIsNone(record.address)
            self.assertIsNone(record.phone)
            self.assertIsNone(record.email)
            self.assertIsNone(record.territorial_scope)
            self.assertNotIn("address", record.observed_fields)
            self.assertNotIn("phone", record.observed_fields)
            self.assertNotIn("email", record.observed_fields)
            self.assertNotIn("territorial_scope", record.observed_fields)

    def test_02_praha_and_stredocesky_are_distinct(self) -> None:
        records = _parse_fixture()
        praha = records[0]
        stc = records[1]
        self.assertEqual(praha.external_key, "hzs:praha")
        self.assertEqual(stc.external_key, "hzs:stredocesky-kraj")
        self.assertNotEqual(praha.name, stc.name)
        self.assertNotEqual(praha.website, stc.website)
        self.assertEqual(praha.website, "https://hzscr.gov.cz/hlavni-mesto-praha")
        self.assertEqual(stc.website, "https://hzscr.gov.cz/stredocesky-kraj")

    def test_03_external_keys_match_seed(self) -> None:
        payload = json.loads(_SEED.read_text(encoding="utf-8"))
        hzs = next(item for item in payload["authorities"] if item["code"] == "hzs")
        seed_keys = tuple(office["external_key"] for office in hzs["offices"])
        self.assertEqual(seed_keys, HZS_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(len(seed_keys), 14)
        self.assertEqual(tuple(item.external_key for item in _parse_fixture()), seed_keys)

    def test_04_output_order_follows_seed_not_html(self) -> None:
        html = _fixture_html()
        self.assertLess(html.find("Zlínský kraj"), html.find("Hlavní město Praha"))
        self.assertLess(html.find('href="/zlinsky-kraj"'), html.find('href="/hlavni-mesto-praha"'))
        records = _parse_fixture()
        self.assertEqual(records[0].external_key, "hzs:praha")
        self.assertEqual(records[1].external_key, "hzs:stredocesky-kraj")
        self.assertEqual(records[-1].external_key, "hzs:zlinsky-kraj")
        self.assertEqual(
            tuple(item.external_key for item in records),
            HZS_OFFICE_EXTERNAL_KEYS,
        )

    def test_05_general_directorate_is_not_an_office(self) -> None:
        html = _fixture_html()
        self.assertIn("generální ředitelství HZS ČR", html)
        self.assertIn("Kloknerova 26", html)
        records = _parse_fixture()
        self.assertEqual(len(records), 14)
        names = " ".join(item.name for item in records)
        self.assertNotIn("generální", names.casefold())
        self.assertNotIn("Generální", " ".join(item.name for item in records))
        self.assertTrue(all(item.external_key.startswith("hzs:") for item in records))
        self.assertNotIn("hzs:gr", [item.external_key for item in records])
        self.assertNotIn("Kloknerova 26, 148 01 Praha 414", {item.address for item in records})
        self.assertNotIn("+420 950 819 782", {item.phone for item in records})
        self.assertNotIn("grh.podatelna@hzscr.cz", {item.email for item in records})

    def test_06_territorial_office_and_station_are_not_added(self) -> None:
        html = _fixture_html()
        self.assertIn("Územní odbor Sokolov", html)
        self.assertIn("Hasičská stanice Holešovice", html)
        self.assertIn("/karlovarsky-kraj/uzemni-odbory", html)
        records = _parse_fixture()
        self.assertEqual(len(records), 14)
        names = " ".join(item.name for item in records)
        self.assertNotIn("Sokolov", names)
        self.assertNotIn("stanice", names.casefold())
        self.assertNotIn("územní odbor", names.casefold())
        websites = {item.website for item in records}
        self.assertNotIn("https://hzscr.gov.cz/karlovarsky-kraj/uzemni-odbory", websites)

    def test_07_director_contact_is_not_office_contact(self) -> None:
        html = _fixture_html()
        self.assertIn("jan.novak@hzscr.cz", html)
        self.assertIn("+420 950 850 099", html)
        records = _parse_fixture()
        self.assertEqual(len(records), 14)
        self.assertNotIn("jan.novak@hzscr.cz", {item.email for item in records})
        self.assertNotIn("+420 950 850 099", {item.phone for item in records})
        self.assertTrue(all(item.phone is None for item in records))
        self.assertTrue(all(item.email is None for item in records))

    def test_08_missing_region_fails_the_batch(self) -> None:
        html = _fixture_html().replace(_ZLINSKY_CARD, "")
        self.assertNotIn("Zlínský kraj", html)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_hzs_offices_html(html, source_url=HZS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_09_duplicate_region_fails(self) -> None:
        html = _fixture_html().replace(
            _ZLINSKY_CARD,
            _ZLINSKY_CARD + _PRAHA_CARD,
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_hzs_offices_html(html, source_url=HZS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_DUPLICATE_KEY)

    def test_10_unexpected_fifteenth_region_fails(self) -> None:
        extra = """
    <div>
      <a class="no-underline!" href="/mimonsky-kraj">
        <div class="text-headline-s">Mimoňský kraj</div>
      </a>
    </div>
"""
        html = _fixture_html().replace("</div>\n  </div>\n  <section>", extra + "</div>\n  </div>\n  <section>")
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_hzs_offices_html(html, source_url=HZS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_11_unreadable_structure_fails(self) -> None:
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_hzs_offices_html(
                "<html><body><h1>HZS krajů</h1><p>Seznam</p></body></html>",
                source_url=HZS_OFFICES_SOURCE_URL,
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    def test_12_observed_fields_contain_only_documented_values(self) -> None:
        records = _parse_fixture()
        allowed = {"name", "website", "office_kind", "source_url"}
        for record in records:
            self.assertEqual(record.observed_fields, frozenset(allowed))
            self.assertIsNotNone(record.name)
            self.assertIsNotNone(record.website)
            self.assertIsNotNone(record.office_kind)
            self.assertIsNotNone(record.source_url)

    def test_13_unobserved_none_does_not_create_field_change(self) -> None:
        records = _parse_fixture()
        snapshots = _seed_hzs_snapshots()
        result = diff_control_authority_offices(
            ControlAuthorityWebFetchResult(
                authority_code=HZS_AUTHORITY_CODE,
                source_url=HZS_OFFICES_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=records,
                is_complete=True,
            ),
            snapshots,
        )
        for item in result.items:
            self.assertIsNotNone(item.remote)
            observed = item.remote.observed_fields
            for change in item.field_changes:
                self.assertIn(change.field, observed)
            fields = {change.field for change in item.field_changes}
            self.assertNotIn("address", fields)
            self.assertNotIn("phone", fields)
            self.assertNotIn("email", fields)
            self.assertNotIn("territorial_scope", fields)

    def test_14_prague_address_comes_from_source_not_seed(self) -> None:
        source = _ADAPTER.read_text(encoding="utf-8")
        self.assertNotIn("Argentinská", source)
        self.assertNotIn("1630/34a", source)
        records = _parse_fixture()
        praha = records[0]
        self.assertEqual(praha.external_key, "hzs:praha")
        self.assertIsNone(praha.address)
        self.assertNotIn("address", praha.observed_fields)
        self.assertNotIn("Argentinská", " ".join(item.address or "" for item in records))
        html = _fixture_html()
        self.assertIn("Argentinská 1630/34a", html)

    def test_15_compare_fixture_with_seed(self) -> None:
        records = _parse_fixture()
        snapshots = _seed_hzs_snapshots()
        result = diff_control_authority_offices(
            ControlAuthorityWebFetchResult(
                authority_code=HZS_AUTHORITY_CODE,
                source_url=HZS_OFFICES_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=records,
                is_complete=True,
            ),
            snapshots,
        )
        self.assertEqual(tuple(item.external_key for item in result.items), HZS_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(result.count(WEB_DIFF_STATUS_NEW), 0)
        self.assertEqual(len(result.items), 14)
        changed_fields: dict[str, set[str]] = {}
        for item in result.items:
            self.assertIn(item.status, {WEB_DIFF_STATUS_UNCHANGED, WEB_DIFF_STATUS_CHANGED})
            fields = {change.field for change in item.field_changes}
            if fields:
                changed_fields[item.external_key] = fields
        self.assertEqual(result.count(WEB_DIFF_STATUS_CHANGED), 14)
        for fields in changed_fields.values():
            self.assertIn("name", fields)
            self.assertIn("website", fields)
            self.assertIn("source_url", fields)
            self.assertNotIn("address", fields)
            self.assertNotIn("phone", fields)
            self.assertNotIn("email", fields)
            self.assertNotIn("office_kind", fields)
            self.assertNotIn("territorial_scope", fields)

    def test_16_no_db_write_and_no_network_in_regular_tests(self) -> None:
        source = _ADAPTER.read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("PySide", source)
        self.assertNotIn("create_office", source)
        self.assertNotIn("sess.commit", source)
        self.assertNotIn("INSERT", source)
        self.assertNotIn("UPDATE", source)
        self.assertNotIn("last_checked_at", source)
        seed_before = _SEED.read_bytes()
        called: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            return _html_response(_fixture_html(), url)

        result = fetch_hzs_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertIsInstance(result, ControlAuthorityWebFetchResult)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.fetched_at, _FIXED_AT)
        self.assertEqual(result.source_url, HZS_OFFICES_SOURCE_URL)
        self.assertEqual(called, [HZS_OFFICES_SOURCE_URL])
        self.assertEqual(len(called), 1)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        test_source = inspect.getsource(self.test_01_fixture_has_exactly_fourteen_regional_hzs)
        self.assertNotIn("requests.get", test_source)

    def test_17_unofficial_redirect_host_is_rejected(self) -> None:
        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "https://example.com/hzs"},
        )
        client = ControlAuthorityHttpClient(request=Mock(return_value=redirect))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(HZS_OFFICES_SOURCE_URL, allowed_hosts=HZS_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertTrue(redirect.closed)
        called: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            return _html_response(_fixture_html(), url)

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_hzs_offices(http_get=fake_get, source_url="http://hzscr.gov.cz/hzs-kraju")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertEqual(called, [])

    def test_18_identity_conflict_between_name_and_link_fails(self) -> None:
        html = _fixture_html().replace(
            'href="/hlavni-mesto-praha"',
            'href="/stredocesky-kraj"',
            1,
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_hzs_offices_html(html, source_url=HZS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    @unittest.skipUnless(
        os.environ.get("STATE_SUPERVISION_AUTHORITY_WEB_LIVE") == "1",
        "živé ověření přehledu krajských HZS",
    )
    def test_19_live_hzs_offices_optional(self) -> None:
        result = fetch_hzs_offices()
        self.assertEqual(len(result.records), 14)
        self.assertEqual(
            tuple(item.external_key for item in result.records),
            HZS_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(result.records[0].external_key, "hzs:praha")
        self.assertEqual(result.records[1].external_key, "hzs:stredocesky-kraj")
        self.assertNotEqual(result.records[0].website, result.records[1].website)


if __name__ == "__main__":
    unittest.main()
