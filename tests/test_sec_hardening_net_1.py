"""SEC-HARDENING-NET-1: HTTPS allowlist, redirecty a limit těla pro ARES a e-Sbírku."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.http_safe import SafeHttpsError, safe_https_get
from core.services.ares_service import (
    ARES_ALLOWED_HOSTS,
    ARES_MAX_RESPONSE_BYTES,
    ares_service,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
    ESBIRKA_ALLOWED_HOSTS,
    legal_document_esbirka_client,
)

_ARES_URL = f"{ares_service.BASE_URL}/12345678"
_ESBIRKA_URL = "https://www.esbirka.cz/cs/390-2021"
_ALLOWED = frozenset({"ares.gov.cz"})
_TIMEOUT = 10
_MAX_BYTES = 64


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
        self.headers = headers or {}
        self._chunks = chunks if chunks is not None else [body]
        self.closed = False
        self.iter_calls = 0

    def iter_content(self, chunk_size=8192):
        self.iter_calls += 1
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


def _request_sequence(responses: list[_FakeRawResponse]):
    queue = list(responses)

    def _request(method, url, **kwargs):
        assert method == "GET"
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        assert kwargs["verify"] is True
        if not queue:
            raise AssertionError(f"Neočekávaný request na {url}")
        return queue.pop(0)

    return _request


class SecHardeningNet1TestCase(unittest.TestCase):
    def test_a_valid_https_allowed_host_succeeds(self) -> None:
        body = b'{"ok": true}'
        response = _FakeRawResponse(body=body, headers={"Content-Length": str(len(body))})
        result = safe_https_get(
            _ARES_URL,
            allowed_hosts=_ALLOWED,
            timeout=_TIMEOUT,
            max_bytes=_MAX_BYTES,
            request=_request_sequence([response]),
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, body)
        self.assertTrue(response.closed)

    def test_b_http_is_rejected(self) -> None:
        request = Mock(side_effect=AssertionError("request se nesmí volat"))
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                "http://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/12345678",
                allowed_hosts=_ALLOWED,
                timeout=_TIMEOUT,
                max_bytes=_MAX_BYTES,
                request=request,
            )
        self.assertEqual(str(context.exception), "Neplatná adresa služby.")
        request.assert_not_called()

    def test_c_redirect_to_allowed_https_host_succeeds(self) -> None:
        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/12345678"},
        )
        final = _FakeRawResponse(body=b"ok")
        result = safe_https_get(
            "https://ares.gov.cz/old",
            allowed_hosts=_ALLOWED,
            timeout=_TIMEOUT,
            max_bytes=_MAX_BYTES,
            request=_request_sequence([redirect, final]),
        )
        self.assertEqual(result.body, b"ok")
        self.assertEqual(result.final_url, _ARES_URL)
        self.assertTrue(redirect.closed)
        self.assertTrue(final.closed)

    def test_d_redirect_to_disallowed_host_is_rejected(self) -> None:
        redirect = _FakeRawResponse(
            status=302,
            headers={"Location": "https://evil.example/steal"},
        )
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                "https://ares.gov.cz/old",
                allowed_hosts=_ALLOWED,
                timeout=_TIMEOUT,
                max_bytes=_MAX_BYTES,
                request=_request_sequence([redirect]),
            )
        self.assertEqual(str(context.exception), "Neplatná adresa služby.")
        self.assertTrue(redirect.closed)

    def test_e_redirect_to_http_is_rejected(self) -> None:
        redirect = _FakeRawResponse(
            status=301,
            headers={"Location": "http://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/1"},
        )
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                "https://ares.gov.cz/old",
                allowed_hosts=_ALLOWED,
                timeout=_TIMEOUT,
                max_bytes=_MAX_BYTES,
                request=_request_sequence([redirect]),
            )
        self.assertEqual(str(context.exception), "Neplatná adresa služby.")

    def test_f_too_many_redirects_are_rejected(self) -> None:
        responses = [
            _FakeRawResponse(
                status=302,
                headers={"Location": f"https://ares.gov.cz/hop/{index}"},
            )
            for index in range(6)
        ]
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                "https://ares.gov.cz/start",
                allowed_hosts=_ALLOWED,
                timeout=_TIMEOUT,
                max_bytes=_MAX_BYTES,
                request=_request_sequence(responses),
            )
        self.assertEqual(str(context.exception), "Překročen počet přesměrování.")

    def test_g_content_length_over_limit_does_not_read_body(self) -> None:
        response = _FakeRawResponse(
            body=b"x" * 100,
            headers={"Content-Length": "1000"},
        )
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                _ARES_URL,
                allowed_hosts=_ALLOWED,
                timeout=_TIMEOUT,
                max_bytes=_MAX_BYTES,
                request=_request_sequence([response]),
            )
        self.assertEqual(str(context.exception), "Odpověď je příliš velká.")
        self.assertEqual(response.iter_calls, 0)
        self.assertTrue(response.closed)

    def test_h_missing_content_length_stream_over_limit_is_rejected(self) -> None:
        response = _FakeRawResponse(chunks=[b"a" * 40, b"b" * 40])
        with self.assertRaises(SafeHttpsError) as context:
            safe_https_get(
                _ARES_URL,
                allowed_hosts=_ALLOWED,
                timeout=_TIMEOUT,
                max_bytes=_MAX_BYTES,
                request=_request_sequence([response]),
            )
        self.assertEqual(str(context.exception), "Odpověď je příliš velká.")
        self.assertTrue(response.closed)

    def test_i_response_at_and_under_limit_succeeds(self) -> None:
        exact = _FakeRawResponse(body=b"x" * _MAX_BYTES)
        under = _FakeRawResponse(body=b"ok")
        exact_result = safe_https_get(
            _ARES_URL,
            allowed_hosts=_ALLOWED,
            timeout=_TIMEOUT,
            max_bytes=_MAX_BYTES,
            request=_request_sequence([exact]),
        )
        under_result = safe_https_get(
            _ARES_URL,
            allowed_hosts=_ALLOWED,
            timeout=_TIMEOUT,
            max_bytes=_MAX_BYTES,
            request=_request_sequence([under]),
        )
        self.assertEqual(len(exact_result.body), _MAX_BYTES)
        self.assertEqual(under_result.body, b"ok")

    def test_j_ares_non_numeric_ico_rejected_before_request(self) -> None:
        with patch("core.http_safe.requests.request") as request_mock:
            with self.assertRaises(ValueError) as context:
                ares_service.find_by_ico("abc")
        self.assertEqual(str(context.exception), "IČO smí obsahovat pouze číslice.")
        request_mock.assert_not_called()

    def test_k_ares_ico_longer_than_8_digits_rejected_before_request(self) -> None:
        with patch("core.http_safe.requests.request") as request_mock:
            with self.assertRaises(ValueError) as context:
                ares_service.find_by_ico("123456789")
        self.assertEqual(str(context.exception), "IČO smí obsahovat nejvýše 8 číslic.")
        request_mock.assert_not_called()

    def test_l_esbirka_non_numeric_number_rejected_before_request(self) -> None:
        with patch("core.http_safe.requests.request") as request_mock:
            with self.assertRaises(ValueError) as context:
                legal_document_esbirka_client.fetch_full_text_html(
                    year=2006,
                    number="262a",
                )
        self.assertEqual(
            str(context.exception),
            "Číslo předpisu smí obsahovat pouze číslice.",
        )
        request_mock.assert_not_called()

    def test_esbirka_non_numeric_year_rejected_before_request(self) -> None:
        with patch("core.http_safe.requests.request") as request_mock:
            with self.assertRaises(ValueError) as context:
                legal_document_esbirka_client.fetch_full_text_html(
                    year="20a6",
                    number="262",
                )
        self.assertEqual(str(context.exception), "Rok musí být číslo.")
        request_mock.assert_not_called()

    def test_m_ares_and_esbirka_parsing_still_works(self) -> None:
        payload = {
            "ico": "12345678",
            "obchodniJmeno": "Firma s.r.o.",
            "sidlo": {
                "nazevUlice": "Hlavní",
                "cisloDomovni": "1",
                "nazevObce": "Praha",
                "psc": "11000",
            },
            "czNace": [],
        }
        body = json.dumps(payload).encode("utf-8")
        with patch(
            "core.services.ares_service.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 200, "body": body, "final_url": _ARES_URL},
            )(),
        ):
            data = ares_service.find_by_ico("12345678")
        self.assertEqual(data["ico"], "12345678")
        self.assertEqual(data["name"], "Firma s.r.o.")
        self.assertEqual(data["address"], "Hlavní 1, 11000 Praha")

        fixture = (
            Path(__file__).resolve().parent / "data" / "sample_esbirka_390_2021.html"
        )
        html = fixture.read_text(encoding="utf-8")
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {
                    "status_code": 200,
                    "body": html.encode("utf-8"),
                    "final_url": _ESBIRKA_URL,
                },
            )(),
        ):
            fetched = legal_document_esbirka_client.fetch_full_text_html(
                year=2021,
                number="390",
            )
        self.assertEqual(
            legal_document_esbirka_client.extract_title(fetched),
            "Nařízení vlády o bližších podmínkách poskytování osobních ochranných "
            "pracovních prostředků, mycích, čisticích a dezinfekčních prostředků",
        )
        text = legal_document_esbirka_client.html_to_text(fetched)
        self.assertIn("390", text)

    def test_ip_localhost_and_file_urls_are_rejected(self) -> None:
        request = Mock(side_effect=AssertionError("request se nesmí volat"))
        for url in (
            "https://127.0.0.1/x",
            "https://localhost/x",
            "file:///etc/passwd",
        ):
            with self.assertRaises(SafeHttpsError):
                safe_https_get(
                    url,
                    allowed_hosts=frozenset({"localhost", "127.0.0.1"}),
                    timeout=_TIMEOUT,
                    max_bytes=_MAX_BYTES,
                    request=request,
                )
        request.assert_not_called()

    def test_ares_short_ico_is_kept(self) -> None:
        captured: list[str] = []

        def _capture(method, url, **kwargs):
            captured.append(url)
            return _FakeRawResponse(body=b'{"ico":"123","obchodniJmeno":"X","sidlo":{},"czNace":[]}')

        with patch("core.http_safe.requests.request", side_effect=_capture):
            data = ares_service.find_by_ico("123")
        self.assertTrue(captured[0].endswith("/123"))
        self.assertEqual(data["ico"], "123")

    def test_esbirka_hosts_and_ares_hosts(self) -> None:
        self.assertEqual(ARES_ALLOWED_HOSTS, frozenset({"ares.gov.cz"}))
        self.assertEqual(ESBIRKA_ALLOWED_HOSTS, frozenset({"www.esbirka.cz"}))
        self.assertEqual(ARES_MAX_RESPONSE_BYTES, 1_048_576)


if __name__ == "__main__":
    unittest.main()
