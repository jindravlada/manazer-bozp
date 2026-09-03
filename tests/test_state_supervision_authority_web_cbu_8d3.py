"""STATE-SUPERVISION-AUTHORITY-WEB-CBU-8D3: read-only adapter OBÚ."""

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
    CBU_AUTHORITY_CODE,
    CBU_OFFICE_EXTERNAL_KEYS,
    CBU_OFFICES_SOURCE_URL,
    CBU_OBU_CODES,
    OFFICE_KIND_TERRITORIAL,
    WEB_ADAPTER_ERROR_DUPLICATE_KEY,
    WEB_ADAPTER_ERROR_INCOMPLETE,
    WEB_ADAPTER_ERROR_INVALID_URL,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import (
    CBU_ALLOWED_HOSTS,
    cbu_office_detail_url,
    fetch_cbu_offices,
    parse_cbu_office_html,
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

_REPO = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO / "tests" / "fixtures" / "statni_dozor"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 8, 22, 0)


def _office_html(code: str) -> str:
    return (_FIXTURES / f"cbu_obu_{code}.html").read_text(encoding="utf-8")


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
    return tuple(
        parse_cbu_office_html(
            _office_html(code),
            office_code=code,
            source_url=cbu_office_detail_url(code),
        )
        for code in CBU_OBU_CODES
    )


def _seed_cbu_snapshots() -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    cbu = next(item for item in payload["authorities"] if item["code"] == "cbu")
    snapshots = []
    for index, office in enumerate(cbu["offices"], start=1):
        snapshots.append(
            ControlAuthorityOfficeCatalogSnapshot(
                id=index,
                authority_id=20,
                authority_code=CBU_AUTHORITY_CODE,
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


def _official_pages() -> dict[str, str]:
    return {cbu_office_detail_url(code): _office_html(code) for code in CBU_OBU_CODES}


def _fetch_pages(html_by_url: dict[str, str]):
    calls: list[str] = []

    def fake_get(url: str) -> ControlAuthorityHttpResponse:
        calls.append(url)
        if url not in html_by_url:
            raise AssertionError(f"unexpected url {url}")
        return _html_response(html_by_url[url], url)

    return fake_get, calls


class StateSupervisionAuthorityWebCbu8d3TestCase(unittest.TestCase):
    def test_01_fixture_has_exactly_seven_obu(self) -> None:
        records = _parse_all_offices()
        self.assertEqual(len(records), 7)
        self.assertEqual(
            tuple(item.external_key for item in records),
            CBU_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(
            [item.name for item in records],
            [
                "Obvodní báňský úřad pro území Hlavního města Prahy a kraje Středočeského",
                "Obvodní báňský úřad pro území krajů Plzeňského a Jihočeského",
                "Obvodní báňský úřad pro území kraje Karlovarského",
                "Obvodní báňský úřad pro území kraje Ústeckého",
                "Obvodní báňský úřad pro území krajů Královéhradeckého, Pardubického, Libereckého a Vysočina",
                "Obvodní báňský úřad pro území krajů Jihomoravského a Zlínského",
                "Obvodní báňský úřad pro území krajů Moravskoslezského a Olomouckého",
            ],
        )
        self.assertEqual(records[0].address, "Kozí 4, 110 01 Praha 1 – Staré Město")
        self.assertEqual(records[1].address, "Hřímalého 2730/11, 301 00 Plzeň")
        self.assertEqual(records[4].address, "Wonkova 1142, 500 02 Hradec Králové")
        self.assertEqual(records[6].address, "Veleslavínova 18, 702 00 Ostrava")
        self.assertNotIn("BOX", records[0].address)
        self.assertNotIn("BOX", records[6].address)
        self.assertEqual(records[0].phone, "221 775 372")
        self.assertEqual(records[0].email, "podatelna.obupraha@cbu.gov.cz")
        self.assertNotEqual(records[0].phone, "221 775 373")
        self.assertNotEqual(records[0].email, "jan.novak@cbu.gov.cz")
        for record, code in zip(records, CBU_OBU_CODES, strict=True):
            self.assertEqual(record.authority_code, CBU_AUTHORITY_CODE)
            self.assertEqual(record.office_kind, OFFICE_KIND_TERRITORIAL)
            self.assertEqual(record.website, cbu_office_detail_url(code))
            self.assertEqual(record.source_url, cbu_office_detail_url(code))
            self.assertTrue(
                {
                    "name",
                    "address",
                    "phone",
                    "email",
                    "website",
                    "office_kind",
                    "source_url",
                }.issubset(record.observed_fields)
            )
            self.assertNotIn("territorial_scope", record.observed_fields)
            self.assertIsNone(record.territorial_scope)
            self.assertFalse(hasattr(record, "ico"))
            self.assertNotIn("00025844", str(record).replace(" ", ""))
            self.assertNotIn("000 25 844", str(record))

    def test_02_external_keys_match_seed(self) -> None:
        payload = json.loads(_SEED.read_text(encoding="utf-8"))
        cbu = next(item for item in payload["authorities"] if item["code"] == "cbu")
        seed_keys = tuple(office["external_key"] for office in cbu["offices"])
        self.assertEqual(seed_keys, CBU_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(len(cbu["offices"]), 7)
        records = _parse_all_offices()
        self.assertEqual(tuple(item.external_key for item in records), seed_keys)

    def test_03_output_order_follows_seed_not_html(self) -> None:
        reversed_codes = tuple(reversed(CBU_OBU_CODES))
        parsed = [
            parse_cbu_office_html(
                _office_html(code),
                office_code=code,
                source_url=cbu_office_detail_url(code),
            )
            for code in reversed_codes
        ]
        self.assertEqual(parsed[0].external_key, "cbu:obu-ostrava")
        fake_get, calls = _fetch_pages(_official_pages())
        result = fetch_cbu_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertEqual(
            tuple(item.external_key for item in result.records),
            CBU_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(calls, [cbu_office_detail_url(code) for code in CBU_OBU_CODES])

    def test_04_cbu_headquarters_is_not_an_office(self) -> None:
        html = _office_html("praha")
        self.assertIn("Český báňský úřad", html)
        record = parse_cbu_office_html(
            html,
            office_code="praha",
            source_url=cbu_office_detail_url("praha"),
        )
        self.assertEqual(record.external_key, "cbu:obu-praha")
        result = fetch_cbu_offices(http_get=_fetch_pages(_official_pages())[0])
        self.assertEqual(len(result.records), 7)
        self.assertTrue(all(item.external_key.startswith("cbu:obu-") for item in result.records))
        self.assertNotIn("cbu:cbu", [item.external_key for item in result.records])

    def test_05_former_liberec_is_not_an_office(self) -> None:
        html = _office_html("praha")
        self.assertIn("/obu/liberec", html)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_cbu_office_html(
                html,
                office_code="liberec",
                source_url="https://cbu.gov.cz/obu/liberec",
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)
        hk = parse_cbu_office_html(
            _office_html("hk"),
            office_code="hk",
            source_url=cbu_office_detail_url("hk"),
        )
        self.assertEqual(hk.external_key, "cbu:obu-hradec-kralove")
        self.assertIn("Libereckého", hk.name)
        result = fetch_cbu_offices(http_get=_fetch_pages(_official_pages())[0])
        keys = [item.external_key for item in result.records]
        self.assertNotIn("cbu:obu-liberec", keys)
        self.assertEqual(len(result.records), 7)

    def test_06_staff_contacts_are_not_office_contacts(self) -> None:
        record = parse_cbu_office_html(
            _office_html("praha"),
            office_code="praha",
            source_url=cbu_office_detail_url("praha"),
        )
        self.assertEqual(record.phone, "221 775 372")
        self.assertEqual(record.email, "podatelna.obupraha@cbu.gov.cz")
        self.assertNotIn("721 331 369", record.phone or "")
        self.assertNotEqual(record.email, "podatelna@cbu.gov.cz")
        self.assertNotEqual(record.email, "jan.novak@cbu.gov.cz")

    def test_07_missing_office_fails_the_batch(self) -> None:
        pages = _official_pages()
        pages[cbu_office_detail_url("ostrava")] = "<html><body><p>OBÚ</p></body></html>"
        fake_get, calls = _fetch_pages(pages)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_cbu_offices(http_get=fake_get)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)
        self.assertEqual(len(calls), 7)
        from moduly.statni_dozor.sluzby.control_authority_web import cbu_adapter

        six = list(_parse_all_offices())[:-1]
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            cbu_adapter._complete_cbu_records(six)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_08_duplicate_key_fails(self) -> None:
        first = parse_cbu_office_html(
            _office_html("praha"),
            office_code="praha",
            source_url=cbu_office_detail_url("praha"),
        )
        from moduly.statni_dozor.sluzby.control_authority_web import cbu_adapter

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            cbu_adapter._complete_cbu_records([first, first])
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_DUPLICATE_KEY)

    def test_09_missing_address_is_incomplete(self) -> None:
        html = _office_html("praha").replace(
            "Kozí 4, 110 01 Praha 1 – Staré Město<br>",
            "",
        ).replace(
            "P.O. BOX 10 (Jindřišská 909/14, 110 00 Praha 1)<br>",
            "",
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_cbu_office_html(
                html,
                office_code="praha",
                source_url=cbu_office_detail_url("praha"),
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_10_unreadable_structure_fails(self) -> None:
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_cbu_office_html(
                "<html><body><h1>Obvodní báňský úřad v Praze</h1></body></html>",
                office_code="praha",
                source_url=cbu_office_detail_url("praha"),
            )
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    def test_11_unobserved_fields_are_not_marked(self) -> None:
        html = (
            _office_html("praha")
            .replace(
                '<a href="mailto:podatelna.obupraha@cbu.gov.cz">podatelna.obupraha@cbu.gov.cz</a>',
                "",
            )
            .replace("Tel.: 221 775 372<br>", "")
        )
        record = parse_cbu_office_html(
            html,
            office_code="praha",
            source_url=cbu_office_detail_url("praha"),
        )
        self.assertNotIn("email", record.observed_fields)
        self.assertIsNone(record.email)
        self.assertNotIn("phone", record.observed_fields)
        self.assertIsNone(record.phone)
        self.assertNotIn("territorial_scope", record.observed_fields)
        self.assertIsNone(record.territorial_scope)

    def test_12_unofficial_redirect_host_is_rejected(self) -> None:
        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "https://example.com/obu/praha"},
        )
        client = ControlAuthorityHttpClient(request=Mock(return_value=redirect))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(cbu_office_detail_url("praha"), allowed_hosts=CBU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertTrue(redirect.closed)

    def test_13_compare_fixture_with_seed(self) -> None:
        records = _parse_all_offices()
        snapshots = _seed_cbu_snapshots()
        result = diff_control_authority_offices(
            ControlAuthorityWebFetchResult(
                authority_code=CBU_AUTHORITY_CODE,
                source_url=CBU_OFFICES_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=records,
                is_complete=True,
            ),
            snapshots,
        )
        self.assertEqual(tuple(item.external_key for item in result.items), CBU_OFFICE_EXTERNAL_KEYS)
        self.assertEqual(result.count(WEB_DIFF_STATUS_NEW), 0)
        self.assertEqual(len(result.items), 7)
        for item in result.items:
            self.assertIsNotNone(item.remote)
            observed = item.remote.observed_fields
            self.assertNotIn("territorial_scope", observed)
            for change in item.field_changes:
                self.assertIn(change.field, observed)
            self.assertIn(item.status, {WEB_DIFF_STATUS_UNCHANGED, WEB_DIFF_STATUS_CHANGED})
        self.assertEqual(result.count(WEB_DIFF_STATUS_UNCHANGED), 7)
        self.assertEqual(result.count(WEB_DIFF_STATUS_CHANGED), 0)

    def test_14_no_db_write_and_no_network_in_regular_tests(self) -> None:
        source = (
            _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web" / "cbu_adapter.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("PySide", source)
        self.assertNotIn("create_office", source)
        self.assertNotIn("sess.commit", source)
        self.assertNotIn("INSERT", source)
        self.assertNotIn("UPDATE", source)
        self.assertNotIn("last_checked_at", source)
        seed_before = _SEED.read_bytes()
        fake_get, calls = _fetch_pages(_official_pages())
        result = fetch_cbu_offices(http_get=fake_get, clock=lambda: _FIXED_AT)
        self.assertIsInstance(result, ControlAuthorityWebFetchResult)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.fetched_at, _FIXED_AT)
        self.assertEqual(result.source_url, CBU_OFFICES_SOURCE_URL)
        self.assertEqual(len(calls), 7)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        test_source = inspect.getsource(self.test_01_fixture_has_exactly_seven_obu)
        self.assertNotIn("requests.get", test_source)

    @unittest.skipUnless(
        os.environ.get("STATE_SUPERVISION_AUTHORITY_WEB_LIVE") == "1",
        "živé ověření webu ČBÚ",
    )
    def test_15_live_cbu_offices_optional(self) -> None:
        result = fetch_cbu_offices()
        self.assertEqual(len(result.records), 7)
        self.assertEqual(
            tuple(item.external_key for item in result.records),
            CBU_OFFICE_EXTERNAL_KEYS,
        )


if __name__ == "__main__":
    unittest.main()
