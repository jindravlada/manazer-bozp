"""STATE-SUPERVISION-AUTHORITY-WEB-SUIP-8D2: read-only adapter OIP."""

from __future__ import annotations

import inspect
import json
import os
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    OFFICE_KIND_REGIONAL,
    SUIP_AUTHORITY_CODE,
    SUIP_HUB_SOURCE_URL,
    SUIP_OFFICE_EXTERNAL_KEYS,
    SUIP_OIP_CODES,
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
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.suip_adapter import (
    SUIP_ALLOWED_HOSTS,
    fetch_suip_offices,
    parse_suip_hub_html,
    parse_suip_office_html,
    suip_office_detail_url,
)

_REPO = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO / "tests" / "fixtures" / "statni_dozor"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 8, 6, 0)
PERSON_TITLE_RE = re.compile(
    r"\b(?:Ing|Mgr|MUDr|JUDr|PhDr|RNDr|Bc|Ph\.D|CSc|doc|prof)\b",
    re.IGNORECASE,
)


def _hub_html() -> str:
    return (_FIXTURES / "suip_kontakty_hub.html").read_text(encoding="utf-8")


def _office_html(code: str) -> str:
    return (_FIXTURES / f"suip_{code}.html").read_text(encoding="utf-8")


def _html_response(html: str, url: str) -> ControlAuthorityHttpResponse:
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


def _parse_all_offices() -> tuple[ControlAuthorityOfficeWebRecord, ...]:
    records = [
        parse_suip_office_html(
            _office_html(code),
            oip_code=code,
            source_url=suip_office_detail_url(code),
        )
        for code in SUIP_OIP_CODES
    ]
    return tuple(records)


def _seed_suip_snapshots() -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    suip = next(item for item in payload["authorities"] if item["code"] == "suip")
    snapshots = []
    for index, office in enumerate(suip["offices"], start=1):
        snapshots.append(
            ControlAuthorityOfficeCatalogSnapshot(
                id=index,
                authority_id=10,
                authority_code=SUIP_AUTHORITY_CODE,
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


def _fetch_pages(html_by_url: dict[str, str]):
    calls: list[str] = []

    def fake_get(url: str) -> ControlAuthorityHttpResponse:
        calls.append(url)
        if url not in html_by_url:
            raise AssertionError(f"unexpected url {url}")
        return _html_response(html_by_url[url], url)

    return fake_get, calls


def _official_pages() -> dict[str, str]:
    pages = {SUIP_HUB_SOURCE_URL: _hub_html()}
    for code in SUIP_OIP_CODES:
        pages[suip_office_detail_url(code)] = _office_html(code)
    return pages


class StateSupervisionAuthorityWebSuip8d2TestCase(unittest.TestCase):
    def test_01_fixture_has_exactly_eight_oip(self) -> None:
        records = _parse_all_offices()
        self.assertEqual(len(records), 8)
        self.assertEqual(
            tuple(item.external_key for item in records),
            SUIP_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(
            [item.name for item in records],
            [
                "Oblastní inspektorát práce pro hlavní město Prahu",
                "Oblastní inspektorát práce pro Středočeský kraj",
                "Oblastní inspektorát práce pro Jihočeský kraj a Vysočinu",
                "Oblastní inspektorát práce pro Plzeňský kraj a Karlovarský kraj",
                "Oblastní inspektorát práce pro Ústecký kraj a Liberecký kraj",
                "Oblastní inspektorát práce pro Královéhradecký kraj a Pardubický kraj",
                "Oblastní inspektorát práce pro Jihomoravský kraj a Zlínský kraj",
                "Oblastní inspektorát práce pro Moravskoslezský kraj a Olomoucký kraj",
            ],
        )
        self.assertEqual(records[0].address, "Kladenská 103/105, 160 00 Praha 6")
        self.assertEqual(records[2].address, "Vodní 1629/21, 370 06 České Budějovice")
        self.assertEqual(records[7].address, "Živičná 1123/2, 702 00 Ostrava")
        for record, code in zip(records, SUIP_OIP_CODES, strict=True):
            self.assertEqual(record.authority_code, SUIP_AUTHORITY_CODE)
            self.assertEqual(record.office_kind, OFFICE_KIND_REGIONAL)
            self.assertIn("address", record.observed_fields)
            self.assertIn("name", record.observed_fields)
            self.assertIn("phone", record.observed_fields)
            self.assertIn("email", record.observed_fields)
            self.assertIn("website", record.observed_fields)
            self.assertIn("office_kind", record.observed_fields)
            self.assertIn("source_url", record.observed_fields)
            self.assertNotIn("territorial_scope", record.observed_fields)
            self.assertFalse(hasattr(record, "ico"))
            self.assertNotIn("75046962", str(record).replace(" ", ""))
            self.assertNotIn("750 46 962", str(record))
            self.assertIsNone(PERSON_TITLE_RE.search(record.name))
            self.assertEqual(record.website, f"https://suip.gov.cz/web/{code}")
            self.assertEqual(record.source_url, suip_office_detail_url(code))

        self.assertEqual(records[0].phone, "+420 950 179 310")
        self.assertEqual(records[1].phone, "+420 950 179 400")
        self.assertEqual(records[0].email, "praha@suip.gov.cz")
        self.assertEqual(records[2].email, "budejovice@suip.gov.cz")
        self.assertEqual(records[6].email, "brno@suip.gov.cz")
        self.assertNotIn("Jihlava", records[2].address)
        self.assertNotIn("Olomouc", records[7].address)

    def test_02_external_keys_match_seed(self) -> None:
        payload = json.loads(_SEED.read_text(encoding="utf-8"))
        suip = next(item for item in payload["authorities"] if item["code"] == "suip")
        seed_keys = tuple(office["external_key"] for office in suip["offices"])
        self.assertEqual(seed_keys, SUIP_OFFICE_EXTERNAL_KEYS)
        records = _parse_all_offices()
        self.assertEqual(tuple(item.external_key for item in records), seed_keys)

    def test_03_hub_order_does_not_define_identity(self) -> None:
        codes = parse_suip_hub_html(_hub_html())
        self.assertEqual(codes, SUIP_OIP_CODES)
        reversed_hub = _hub_html().replace("/web/oip03", "/tmp/oip03").replace(
            "/web/oip10", "/web/oip03"
        ).replace("/tmp/oip03", "/web/oip10")
        self.assertEqual(parse_suip_hub_html(reversed_hub), SUIP_OIP_CODES)
        oip10 = parse_suip_office_html(
            _office_html("oip10"),
            oip_code="oip10",
            source_url=suip_office_detail_url("oip10"),
        )
        self.assertEqual(oip10.external_key, "suip:oip-moravskoslezsky-olomoucky")

    def test_04_regional_office_is_not_ninth_oip(self) -> None:
        html = _office_html("oip05")
        self.assertIn("Regionální kancelář v Jihlavě", html)
        record = parse_suip_office_html(
            _office_html("oip05"),
            oip_code="oip05",
            source_url=suip_office_detail_url("oip05"),
        )
        self.assertEqual(record.external_key, "suip:oip-jihocesky-vysocina")
        records = _parse_all_offices()
        self.assertEqual(len(records), 8)
        fake_get, calls = _fetch_pages(_official_pages())
        result = fetch_suip_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertTrue(result.is_complete)
        self.assertEqual(len(result.records), 8)
        self.assertEqual(len(calls), 9)

    def test_05_missing_oip_is_not_partial_success(self) -> None:
        hub = _hub_html().replace("/web/oip10", "/web/suip")
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_suip_hub_html(hub)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)
        pages = _official_pages()
        pages[SUIP_HUB_SOURCE_URL] = hub
        fake_get, _calls = _fetch_pages(pages)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_suip_offices(http_get=fake_get)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_06_duplicate_or_unexpected_oip_fails(self) -> None:
        extra = _hub_html().replace(
            'href="/web/oip10">OIP Moravskoslezský kraj a Olomoucký kraj</a>',
            'href="/web/oip10">OIP Ostrava</a></li><li><a href="/web/oip11">OIP Extra</a>',
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_suip_hub_html(extra)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)
        first = parse_suip_office_html(
            _office_html("oip03"),
            oip_code="oip03",
            source_url=suip_office_detail_url("oip03"),
        )
        from moduly.statni_dozor.sluzby.control_authority_web import suip_adapter

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            suip_adapter._complete_suip_records([first, first])
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_DUPLICATE_KEY)

    def test_07_missing_address_is_incomplete(self) -> None:
        html = _office_html("oip03").replace(
            "Kladenská 103/105<br> 160 00 Praha 6",
            "",
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_suip_office_html(
                html,
                oip_code="oip03",
                source_url=suip_office_detail_url("oip03"),
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_08_unreadable_structure_fails(self) -> None:
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_suip_hub_html("<html><body><p>Kontakty</p></body></html>")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_suip_office_html(
                "<html><body><h4>Kontakty</h4><p>Praha</p></body></html>",
                oip_code="oip03",
                source_url=suip_office_detail_url("oip03"),
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    def test_09_unobserved_fields_are_not_marked(self) -> None:
        html = (
            _office_html("oip03")
            .replace(
                '<a href="mailto:epodatelna.praha@suip.gov.cz">epodatelna.praha@suip.gov.cz</a>',
                "",
            )
            .replace(
                '<a href="mailto:praha@suip.gov.cz">praha@suip.gov.cz</a>',
                "",
            )
            .replace(
                '<h4>4.5 Adresa internetových stránek</h4>\n  <p><a href="/web/oip03">http://suip.gov.cz/web/oip03</a></p>',
                "",
            )
        )
        record = parse_suip_office_html(
            html,
            oip_code="oip03",
            source_url=suip_office_detail_url("oip03"),
        )
        self.assertNotIn("email", record.observed_fields)
        self.assertIsNone(record.email)
        self.assertNotIn("website", record.observed_fields)
        self.assertIsNone(record.website)
        self.assertNotIn("territorial_scope", record.observed_fields)
        self.assertIsNone(record.territorial_scope)

    def test_10_unofficial_redirect_host_is_rejected(self) -> None:
        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "https://example.com/kontakty-1"},
        )
        client = ControlAuthorityHttpClient(request=Mock(return_value=redirect))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(SUIP_HUB_SOURCE_URL, allowed_hosts=SUIP_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertTrue(redirect.closed)
        called: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            return _html_response(_hub_html(), url)

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_suip_offices(http_get=fake_get, source_url="http://suip.gov.cz/kontakty-1")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertEqual(called, [])
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_suip_offices(
                http_get=fake_get,
                source_url="https://example.com/kontakty-1",
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertEqual(called, [])

    def test_11_compare_fixture_with_seed(self) -> None:
        records = _parse_all_offices()
        snapshots = _seed_suip_snapshots()
        result = diff_control_authority_offices(
            ControlAuthorityWebFetchResult(
                authority_code=SUIP_AUTHORITY_CODE,
                source_url=SUIP_HUB_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=records,
                is_complete=True,
            ),
            snapshots,
        )
        self.assertEqual(tuple(item.external_key for item in result.items), SUIP_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(result.count(WEB_DIFF_STATUS_NEW), 0)
        self.assertEqual(len(result.items), 8)
        for item in result.items:
            self.assertIsNotNone(item.remote)
            observed = item.remote.observed_fields
            self.assertNotIn("territorial_scope", observed)
            for change in item.field_changes:
                self.assertIn(change.field, observed)
            self.assertIn(item.status, {WEB_DIFF_STATUS_UNCHANGED, WEB_DIFF_STATUS_CHANGED})
        self.assertEqual(result.count(WEB_DIFF_STATUS_UNCHANGED), 8)
        self.assertEqual(result.count(WEB_DIFF_STATUS_CHANGED), 0)

    def test_12_no_db_write_and_no_network_in_regular_tests(self) -> None:
        package = (
            _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web"
        )
        source = (package / "suip_adapter.py").read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("PySide", source)
        self.assertNotIn("create_office", source)
        self.assertNotIn("sess.commit", source)
        self.assertNotIn("last_checked_at", source)
        seed_before = _SEED.read_bytes()
        fake_get, calls = _fetch_pages(_official_pages())
        result = fetch_suip_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertIsInstance(result, ControlAuthorityWebFetchResult)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.fetched_at, _FIXED_AT)
        self.assertEqual(len(calls), 9)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        test_source = inspect.getsource(self.test_01_fixture_has_exactly_eight_oip)
        self.assertNotIn("requests.get", test_source)

    @unittest.skipUnless(
        os.environ.get("STATE_SUPERVISION_AUTHORITY_WEB_LIVE") == "1",
        "živé ověření webu SÚIP",
    )
    def test_13_live_suip_offices_optional(self) -> None:
        result = fetch_suip_offices()
        self.assertEqual(len(result.records), 8)
        self.assertEqual(
            tuple(item.external_key for item in result.records),
            SUIP_OFFICE_EXTERNAL_KEYS,
        )


if __name__ == "__main__":
    unittest.main()
