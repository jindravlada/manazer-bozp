"""STATE-SUPERVISION-AUTHORITY-WEB-KHS-8D4: read-only adapter KHS z MZD."""

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
    KHS_AUTHORITY_CODE,
    KHS_OFFICE_EXTERNAL_KEYS,
    KHS_OFFICES_SOURCE_URL,
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
from moduly.statni_dozor.sluzby.control_authority_web.khs_adapter import (
    KHS_ALLOWED_HOSTS,
    fetch_khs_offices,
    parse_khs_offices_html,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
)

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "khs_mzd.html"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 8, 32, 0)


def _fixture_html() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


def _html_response(html: str, url: str = KHS_OFFICES_SOURCE_URL) -> ControlAuthorityHttpResponse:
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
    return parse_khs_offices_html(_fixture_html(), source_url=KHS_OFFICES_SOURCE_URL)


def _seed_khs_snapshots() -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    khs = next(item for item in payload["authorities"] if item["code"] == "khs")
    snapshots = []
    for index, office in enumerate(khs["offices"], start=1):
        snapshots.append(
            ControlAuthorityOfficeCatalogSnapshot(
                id=index,
                authority_id=30,
                authority_code=KHS_AUTHORITY_CODE,
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
    return tuple(snapshots)


class StateSupervisionAuthorityWebKhs8d4TestCase(unittest.TestCase):
    def test_01_fixture_has_exactly_fourteen_stations(self) -> None:
        records = _parse_fixture()
        self.assertEqual(len(records), 14)
        self.assertEqual(
            tuple(item.external_key for item in records),
            KHS_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(records[0].name, "HS hl. m. Prahy")
        self.assertEqual(records[0].address, "Rytířská 12, 110 01 Praha 1")
        self.assertEqual(records[0].phone, "296 336 700")
        self.assertEqual(records[0].email, "podatelna@hygpraha.cz")
        self.assertEqual(records[0].website, "http://www.hygpraha.cz/")
        for record in records:
            self.assertEqual(record.authority_code, KHS_AUTHORITY_CODE)
            self.assertEqual(record.office_kind, OFFICE_KIND_REGIONAL)
            self.assertEqual(record.source_url, KHS_OFFICES_SOURCE_URL)
            self.assertTrue(
                {"name", "address", "website", "office_kind", "source_url", "phone", "email"}.issubset(
                    record.observed_fields
                )
            )
            self.assertNotIn("territorial_scope", record.observed_fields)
            self.assertIsNone(record.territorial_scope)
            self.assertIsNotNone(record.address)
            self.assertTrue(any(char.isdigit() for char in record.address or ""))

    def test_02_praha_and_stredocesky_are_distinct(self) -> None:
        records = _parse_fixture()
        praha = records[0]
        stc = records[1]
        self.assertEqual(praha.external_key, "khs:praha")
        self.assertEqual(stc.external_key, "khs:stredocesky-kraj")
        self.assertNotEqual(praha.address, stc.address)
        self.assertIn("Praha 1", praha.address or "")
        self.assertIn("Praha 2", stc.address or "")
        self.assertEqual(stc.website, "http://www.khsstc.cz/")

    def test_03_external_keys_match_seed(self) -> None:
        payload = json.loads(_SEED.read_text(encoding="utf-8"))
        khs = next(item for item in payload["authorities"] if item["code"] == "khs")
        seed_keys = tuple(
            office["external_key"]
            for office in khs["offices"]
            if office.get("office_kind") == OFFICE_KIND_REGIONAL
        )
        self.assertEqual(seed_keys, KHS_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(len(seed_keys), 14)
        self.assertEqual(tuple(item.external_key for item in _parse_fixture()), seed_keys)

    def test_04_output_order_follows_seed_not_html(self) -> None:
        html = _fixture_html()
        self.assertLess(html.find("Zlínského kraje"), html.find("HS hl. m. Prahy"))
        records = _parse_fixture()
        self.assertEqual(records[0].external_key, "khs:praha")
        self.assertEqual(records[-1].external_key, "khs:zlinsky-kraj")

    def test_05_territorial_workplace_is_not_a_station(self) -> None:
        html = _fixture_html()
        self.assertIn("Územní pracoviště Beroun", html)
        records = _parse_fixture()
        self.assertEqual(len(records), 14)
        self.assertTrue(all(item.external_key.startswith("khs:") for item in records))
        self.assertNotIn("Beroun", " ".join(item.name for item in records))

    def test_06_missing_station_fails_the_batch(self) -> None:
        html = _fixture_html().replace(
            "<tr>\n          <td>Zlínského kraje<br><a href=\"http://www.khszlin.cz/\">www.khszlin.cz</a></td>\n          <td>Havlíčkovo nábř. 600<br>760 01 Zlín</td>\n          <td>ředitel</td>\n          <td>577 006 737</td>\n          <td>podatelna@khszlin.cz</td>\n        </tr>",
            "",
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_khs_offices_html(html, source_url=KHS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_07_duplicate_station_fails(self) -> None:
        html = _fixture_html().replace(
            "Zlínského kraje",
            "HS hl. m. Prahy",
            1,
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_khs_offices_html(html, source_url=KHS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_DUPLICATE_KEY)

    def test_08_unexpected_fifteenth_station_fails(self) -> None:
        extra = """
        <tr>
          <td>Mimoňského kraje<br><a href="http://www.example.cz/">www.example.cz</a></td>
          <td>Hlavní 1<br>123 45 Mimoň</td>
          <td>ředitel</td>
          <td>111 111 111</td>
          <td>info@example.cz</td>
        </tr>
        """
        html = _fixture_html().replace("</tbody>", extra + "</tbody>")
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_khs_offices_html(html, source_url=KHS_OFFICES_SOURCE_URL)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_09_unreadable_structure_fails(self) -> None:
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_khs_offices_html(
                "<html><body><h1>Krajské hygienické stanice</h1><p>Seznam</p></body></html>",
                source_url=KHS_OFFICES_SOURCE_URL,
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    def test_10_mzd_contact_is_not_assigned(self) -> None:
        records = _parse_fixture()
        phones = {item.phone for item in records}
        emails = {item.email for item in records}
        self.assertNotIn("224 971 111", phones)
        self.assertNotIn("+420 224 971 111", phones)
        self.assertNotIn("podatelna@mzd.gov.cz", emails)
        self.assertNotIn("Palackého náměstí 375/4, 128 00 Praha 2 – Nové Město", {
            item.address for item in records
        })

    def test_11_individual_khs_websites_are_not_fetched(self) -> None:
        called: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            return _html_response(_fixture_html(), url)

        result = fetch_khs_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertEqual(called, [KHS_OFFICES_SOURCE_URL])
        self.assertTrue(result.is_complete)
        self.assertEqual(len(result.records), 14)
        self.assertTrue(any("hygpraha" in (item.website or "") for item in result.records))

    def test_12_unobserved_fields_are_not_marked(self) -> None:
        html = _fixture_html().replace(
            "<th>telefon</th>\n          <th>e-mail</th>",
            "<th>poznámka</th>",
        )
        for phone in [
            "577 006 737",
            "595 138 111",
            "585 719 111",
            "545 111 091",
            "567 564 551",
            "466 052 338",
            "495 058 111",
            "485 253 111",
            "477 755 111",
            "355 328 311",
            "377 155 111",
            "387 712 111",
            "211 154 600",
            "296&nbsp;336&nbsp;700",
        ]:
            html = html.replace(f"<td>{phone}</td>", "<td></td>")
        record = parse_khs_offices_html(html, source_url=KHS_OFFICES_SOURCE_URL)[0]
        self.assertNotIn("phone", record.observed_fields)
        self.assertIsNone(record.phone)
        self.assertNotIn("territorial_scope", record.observed_fields)

    def test_13_unobserved_none_does_not_create_field_change(self) -> None:
        records = _parse_fixture()
        snapshots = _seed_khs_snapshots()
        result = diff_control_authority_offices(
            ControlAuthorityWebFetchResult(
                authority_code=KHS_AUTHORITY_CODE,
                source_url=KHS_OFFICES_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=records,
                is_complete=True,
            ),
            snapshots,
        )
        for item in result.items:
            self.assertIsNotNone(item.remote)
            observed = item.remote.observed_fields
            self.assertNotIn("territorial_scope", observed)
            for change in item.field_changes:
                self.assertIn(change.field, observed)
            fields = {change.field for change in item.field_changes}
            self.assertNotIn("territorial_scope", fields)

    def test_14_compare_fixture_with_seed(self) -> None:
        records = _parse_fixture()
        snapshots = _seed_khs_snapshots()
        result = diff_control_authority_offices(
            ControlAuthorityWebFetchResult(
                authority_code=KHS_AUTHORITY_CODE,
                source_url=KHS_OFFICES_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=records,
                is_complete=True,
            ),
            snapshots,
        )
        self.assertEqual(tuple(item.external_key for item in result.items), KHS_OFFICE_EXTERNAL_KEYS)
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
            self.assertIn("source_url", fields)
            self.assertIn("website", fields)
            self.assertNotIn("address", fields)
            self.assertNotIn("phone", fields)
            self.assertNotIn("email", fields)
            self.assertNotIn("office_kind", fields)

    def test_15_no_db_write_and_no_network_in_regular_tests(self) -> None:
        source = (
            _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web" / "khs_adapter.py"
        ).read_text(encoding="utf-8")
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

        result = fetch_khs_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertIsInstance(result, ControlAuthorityWebFetchResult)
        self.assertTrue(result.is_complete)
        self.assertEqual(len(called), 1)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        test_source = inspect.getsource(self.test_01_fixture_has_exactly_fourteen_stations)
        self.assertNotIn("requests.get", test_source)

    def test_16_unofficial_redirect_host_is_rejected(self) -> None:
        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "https://example.com/khs"},
        )
        client = ControlAuthorityHttpClient(request=Mock(return_value=redirect))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(KHS_OFFICES_SOURCE_URL, allowed_hosts=KHS_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertTrue(redirect.closed)
        called: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            return _html_response(_fixture_html(), url)

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_khs_offices(http_get=fake_get, source_url="http://mzd.gov.cz/krajske-hygienicke-stanice/")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertEqual(called, [])

    @unittest.skipUnless(
        os.environ.get("STATE_SUPERVISION_AUTHORITY_WEB_LIVE") == "1",
        "živé ověření přehledu KHS na MZD",
    )
    def test_17_live_khs_offices_optional(self) -> None:
        result = fetch_khs_offices()
        self.assertEqual(len(result.records), 14)
        self.assertEqual(
            tuple(item.external_key for item in result.records),
            KHS_OFFICE_EXTERNAL_KEYS,
        )


if __name__ == "__main__":
    unittest.main()
