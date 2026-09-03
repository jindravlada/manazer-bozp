"""STATE-SUPERVISION-AUTHORITY-WEB-DU-8D0: read-only adapter Drážního úřadu."""

from __future__ import annotations

import inspect
import json
import os
import re
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import SSLError, Timeout

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    DU_OFFICES_SOURCE_URL,
    OFFICE_KIND_HEADQUARTERS,
    OFFICE_KIND_TERRITORIAL,
    WEB_ADAPTER_ERROR_DUPLICATE_KEY,
    WEB_ADAPTER_ERROR_HTTP,
    WEB_ADAPTER_ERROR_INCOMPLETE,
    WEB_ADAPTER_ERROR_INVALID_URL,
    WEB_ADAPTER_ERROR_NETWORK,
    WEB_ADAPTER_ERROR_TIMEOUT,
    WEB_ADAPTER_ERROR_TOO_LARGE,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML,
    WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT,
    WEB_ADAPTER_HTTP_MESSAGE,
    WEB_ADAPTER_HTTP_TIMEOUT_SECONDS,
    WEB_ADAPTER_INCOMPLETE_MESSAGE,
    WEB_ADAPTER_INVALID_URL_MESSAGE,
    WEB_ADAPTER_TIMEOUT_MESSAGE,
    WEB_ADAPTER_TOO_LARGE_MESSAGE,
    WEB_ADAPTER_UNREADABLE_HTML_MESSAGE,
    WEB_ADAPTER_UNSUPPORTED_CONTENT_MESSAGE,
)
from moduly.statni_dozor.sluzby.control_authority_web.du_adapter import (
    DU_ALLOWED_HOSTS,
    fetch_du_offices,
    parse_du_offices_html,
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
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "du_kontakty.html"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
PERSON_TITLE_RE = re.compile(
    r"\b(?:Ing|Mgr|MUDr|JUDr|PhDr|RNDr|Bc|Ph\.D|CSc|doc|prof)\b",
    re.IGNORECASE,
)


def _fixture_html() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


def _html_response(html: str, *, status: int = 200, content_type: str = "text/html; charset=UTF-8"):
    return ControlAuthorityHttpResponse(
        status_code=status,
        body=html.encode("utf-8"),
        content_type=content_type.split(";", 1)[0],
        final_url=DU_OFFICES_SOURCE_URL,
    )


class _FakeRawResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        headers: dict | None = None,
        chunks: list[bytes] | None = None,
    ):
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html; charset=UTF-8"}
        self._chunks = chunks if chunks is not None else [body]
        self.closed = False

    def iter_content(self, chunk_size=8192):
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class StateSupervisionAuthorityWebDu8d0TestCase(unittest.TestCase):
    def test_01_valid_fixture_has_three_offices_and_keys(self) -> None:
        html = _fixture_html()
        self.assertIn("https://du.gov.cz/kontakty/", html)
        self.assertIn("2026-09-03", html)
        records = parse_du_offices_html(html)
        self.assertEqual(len(records), 3)
        self.assertIsInstance(records, tuple)
        self.assertEqual(
            tuple(item.external_key for item in records),
            DU_OFFICE_EXTERNAL_KEYS,
        )
        self.assertEqual(
            [item.name for item in records],
            ["Pracoviště Praha", "Pracoviště Plzeň", "Pracoviště Olomouc"],
        )
        self.assertEqual(records[0].address, "Bělehradská 222/128, 120 00 Praha 2")
        self.assertEqual(records[1].address, "Škroupova 11, 301 36 Plzeň")
        self.assertEqual(records[2].address, "Nerudova 1, 779 00 Olomouc")
        self.assertIn("ě", records[0].address)
        self.assertIn("ň", records[1].address)
        self.assertIn("Š", records[1].address)
        self.assertNotIn("\xa0", records[0].address)
        self.assertEqual(records[0].phone, "226 523 368")
        self.assertEqual(records[1].phone, "972 524 098")
        self.assertEqual(records[2].phone, "972 741 315")
        self.assertIsNone(records[0].email)
        self.assertIsNone(records[1].email)
        self.assertIsNone(records[2].email)
        self.assertEqual(records[0].office_kind, OFFICE_KIND_HEADQUARTERS)
        self.assertEqual(records[1].office_kind, OFFICE_KIND_TERRITORIAL)
        self.assertEqual(records[2].office_kind, OFFICE_KIND_TERRITORIAL)
        self.assertEqual(records[0].authority_code, DU_AUTHORITY_CODE)
        for record in records:
            self.assertIsInstance(record, ControlAuthorityOfficeWebRecord)
            self.assertFalse(hasattr(record, "ico"))
            self.assertFalse(hasattr(record, "authority_ico"))
            self.assertNotIn("61379425", str(record))
            self.assertIsNone(record.website)
            self.assertIsNone(record.territorial_scope)
            self.assertEqual(record.source_url, DU_OFFICES_SOURCE_URL)
            blob = " ".join(
                str(value)
                for value in (
                    record.name,
                    record.address,
                    record.phone,
                    record.email,
                )
                if value
            )
            self.assertIsNone(PERSON_TITLE_RE.search(blob))

    def test_02_unique_email_only_when_in_office_table(self) -> None:
        html = _fixture_html().replace(
            "<tr><th>TELEFON</th><td><a href=\"tel:226523368\">226 523 368</a></td></tr>\n          </table>",
            "<tr><th>TELEFON</th><td><a href=\"tel:226523368\">226 523 368</a></td></tr>\n"
            "<tr><th>E-MAIL</th><td>praha@du.gov.cz</td></tr>\n          </table>",
            1,
        )
        records = parse_du_offices_html(html)
        self.assertEqual(records[0].email, "praha@du.gov.cz")
        self.assertIsNone(records[1].email)
        self.assertIsNone(records[2].email)

    def test_03_missing_praha_is_not_partial_success(self) -> None:
        html = _fixture_html().replace("PRACOVIŠTĚ PRAHA", "PRACOVIŠTĚ BRNO")
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_du_offices_html(html)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_INCOMPLETE_MESSAGE)
        self.assertNotIn("<html", str(ctx.exception))

    def test_04_missing_address_fails(self) -> None:
        html = _fixture_html().replace(
            "<tr><th>ADRESA</th><td>Bělehradská&nbsp;222/128, 120 00 Praha 2</td></tr>",
            "",
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_du_offices_html(html)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_05_duplicate_praha_fails(self) -> None:
        html = _fixture_html().replace("PRACOVIŠTĚ OLOMOUC", "PRACOVIŠTĚ PRAHA")
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_du_offices_html(html)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_DUPLICATE_KEY)

    def test_06_unknown_fourth_office_fails(self) -> None:
        extra = """
        <button id="link-0-3" class="gov-tabs__link" role="tab" aria-controls="link-0-3-tab">
          PRACOVIŠTĚ BRNO
        </button>
        """
        html = _fixture_html().replace(
            "PRACOVIŠTĚ OLOMOUC\n        </button>",
            "PRACOVIŠTĚ OLOMOUC\n        </button>" + extra,
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_du_offices_html(html)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INCOMPLETE)

    def test_07_empty_and_unreadable_html_fail(self) -> None:
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_du_offices_html("")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_UNREADABLE_HTML_MESSAGE)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            parse_du_offices_html("<html><body><p>Kontaktujte nás</p></body></html>")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNREADABLE_HTML)

    def test_08_seed_external_keys_match_adapter(self) -> None:
        payload = json.loads(_SEED.read_text(encoding="utf-8"))
        du = next(item for item in payload["authorities"] if item["code"] == "du")
        seed_keys = tuple(office["external_key"] for office in du["offices"])
        self.assertEqual(seed_keys, DU_OFFICE_EXTERNAL_KEYS)
        records = parse_du_offices_html(_fixture_html())
        self.assertEqual(tuple(item.external_key for item in records), seed_keys)

    def test_09_fetch_uses_injected_http_and_clock(self) -> None:
        fixed = datetime(2026, 9, 3, 6, 45, 0)
        calls: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            calls.append(url)
            return _html_response(_fixture_html())

        result = fetch_du_offices(http_get=fake_get, clock=lambda: fixed)
        self.assertEqual(calls, [DU_OFFICES_SOURCE_URL])
        self.assertIsInstance(result, ControlAuthorityWebFetchResult)
        self.assertIsInstance(result.records, tuple)
        self.assertEqual(result.fetched_at, fixed)
        self.assertEqual(result.authority_code, DU_AUTHORITY_CODE)
        self.assertEqual(len(result.records), 3)
        self.assertEqual(result.warnings, ())
        self.assertEqual(result.source_url, DU_OFFICES_SOURCE_URL)
        self.assertTrue(result.is_complete)

        raw = _FakeRawResponse(body=_fixture_html().encode("utf-8"))
        request = Mock(return_value=raw)
        client = ControlAuthorityHttpClient(
            request=request,
            user_agent="ManazerBOZP/test",
        )
        via_client = fetch_du_offices(http_get=client, clock=lambda: fixed)
        self.assertEqual(len(via_client.records), 3)
        kwargs = request.call_args.kwargs
        self.assertTrue(kwargs["verify"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(kwargs["timeout"], WEB_ADAPTER_HTTP_TIMEOUT_SECONDS)
        self.assertEqual(kwargs["headers"]["User-Agent"], "ManazerBOZP/test")
        self.assertNotIn("cookies", kwargs)
        self.assertNotIn("Cookie", kwargs["headers"])
        self.assertTrue(raw.closed)

    def test_10_http_errors_and_limits(self) -> None:
        client = ControlAuthorityHttpClient(request=Mock(side_effect=Timeout()))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_TIMEOUT)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_TIMEOUT_MESSAGE)

        client = ControlAuthorityHttpClient(request=Mock(side_effect=SSLError("cert")))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_NETWORK)

        client = ControlAuthorityHttpClient(
            request=Mock(side_effect=RequestsConnectionError("down"))
        )
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_NETWORK)

        huge = _FakeRawResponse(chunks=[b"x" * 200_000, b"y" * 900_000])
        client = ControlAuthorityHttpClient(request=Mock(return_value=huge), max_bytes=1000)
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_TOO_LARGE)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_TOO_LARGE_MESSAGE)
        self.assertTrue(huge.closed)
        self.assertNotIn("yyyy", str(ctx.exception))

        not_found = _FakeRawResponse(status=404, body=b"<html>missing</html>")
        client = ControlAuthorityHttpClient(request=Mock(return_value=not_found))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_HTTP)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_HTTP_MESSAGE)
        self.assertNotIn("missing", str(ctx.exception))

        server_error = _FakeRawResponse(status=500, body=b"<html>fail</html>")
        client = ControlAuthorityHttpClient(request=Mock(return_value=server_error))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_HTTP)

        json_response = _FakeRawResponse(
            body=b'{"offices":[]}',
            headers={"Content-Type": "application/json"},
        )
        client = ControlAuthorityHttpClient(request=Mock(return_value=json_response))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_UNSUPPORTED_CONTENT_MESSAGE)

    def test_11_unofficial_and_http_urls_are_rejected(self) -> None:
        called = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            return _html_response(_fixture_html())

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_du_offices(http_get=fake_get, source_url="http://du.gov.cz/kontakty/")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_INVALID_URL_MESSAGE)
        self.assertEqual(called, [])

        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            fetch_du_offices(http_get=fake_get, source_url="https://example.com/kontakty/")
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertEqual(called, [])

        client = ControlAuthorityHttpClient(request=Mock())
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get("https://example.com/", allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)

        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "https://example.com/kontakty/", "Content-Type": "text/html"},
        )
        client = ControlAuthorityHttpClient(request=Mock(return_value=redirect))
        with self.assertRaises(ControlAuthorityWebAdapterError) as ctx:
            client.get(DU_OFFICES_SOURCE_URL, allowed_hosts=DU_ALLOWED_HOSTS)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_INVALID_URL)
        self.assertTrue(redirect.closed)

    def test_12_isolation_no_db_ui_or_catalog_write(self) -> None:
        package_dir = (
            _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web"
        )
        adapter_files = {
            "__init__.py",
            "du_adapter.py",
            "http_client.py",
            "html_tree.py",
            "models.py",
        }
        sources = []
        for path in package_dir.glob("*.py"):
            if path.name not in adapter_files:
                continue
            text = path.read_text(encoding="utf-8")
            sources.append(text)
            self.assertNotIn("sqlalchemy", text)
            self.assertNotIn("PySide", text)
            self.assertNotIn("last_checked_at", text)
            self.assertNotIn("LongOperationRunner", text)
            self.assertNotIn("save_supervision", text)
            self.assertNotIn("create_office", text)
            self.assertNotIn("deactivate_office", text)
        joined = "\n".join(sources)
        self.assertNotIn("authority_office_id", joined)
        test_source = inspect.getsource(self.test_01_valid_fixture_has_three_offices_and_keys)
        self.assertNotIn("requests.get", test_source)
        parse_du_offices_html(_fixture_html())

    @unittest.skipUnless(
        os.environ.get("STATE_SUPERVISION_AUTHORITY_WEB_LIVE") == "1",
        "živé ověření webu Drážního úřadu",
    )
    def test_13_live_du_offices_optional(self) -> None:
        result = fetch_du_offices()
        self.assertEqual(len(result.records), 3)
        self.assertEqual(
            tuple(item.external_key for item in result.records),
            DU_OFFICE_EXTERNAL_KEYS,
        )


if __name__ == "__main__":
    unittest.main()
