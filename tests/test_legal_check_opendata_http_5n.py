"""PRE-4.0-BLOCKER-5N: sdílená Session, retry Open Data a diagnostika FAILED."""

from __future__ import annotations

import importlib
import tempfile
import time as time_module
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from requests.exceptions import Timeout

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.app_runtime_service import mark_application_started

    mark_application_started()

    from core.http_safe import (
        SAFE_HTTPS_RETRYABLE_STATUSES,
        SafeHttpsError,
        parse_retry_after_seconds,
        safe_https_get,
    )
    from moduly.pravni_pozadavky.constants import (
        CHECK_RUN_COMPLETED,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        ESBIRKA_OPENDATA_ALLOWED_HOSTS,
        ESBIRKA_OPENDATA_BASE_URL,
        ESBIRKA_OPENDATA_HTTP_MAX_RETRIES,
        classify_opendata_endpoint,
        legal_document_esbirka_opendata_client,
        open_data_http_session,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        NOVELIZATION_FAILED,
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
        format_automatic_check_user_message,
        legal_check_run_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

_ACT_URL = f"{ESBIRKA_OPENDATA_BASE_URL}/2006/262"
_WORDING_URL = f"{ESBIRKA_OPENDATA_BASE_URL}/2006/262/2026-01-01"
_SPARQL_URL = "https://opendata.eselpoint.gov.cz/sparql?query=SELECT"
_ELI = "eli/cz/sb/2006/262/2026-01-01"
_TIMEOUT = 10
_MAX_BYTES = 64


class _FakeRawResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        headers: dict | None = None,
    ):
        self.status_code = status
        self.headers = headers or {}
        self._body = body
        self.closed = False

    def iter_content(self, chunk_size=8192):
        yield self._body

    def close(self) -> None:
        self.closed = True


def _request_sequence(responses: list[_FakeRawResponse]):
    queue = list(responses)
    calls: list[dict] = []

    def _request(method, url, **kwargs):
        calls.append({"method": method, "url": url, **kwargs})
        assert method == "GET"
        assert kwargs["allow_redirects"] is False
        assert kwargs["stream"] is True
        assert kwargs["verify"] is True
        if not queue:
            raise AssertionError(f"Neočekávaný request na {url}")
        return queue.pop(0)

    _request.calls = calls  # type: ignore[attr-defined]
    return _request


class LegalCheckOpenDataHttp5NTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()
        legal_document_esbirka_opendata_client.bind_http_session(None)
        legal_document_esbirka_opendata_client._sleep = lambda _seconds: None
        self.addCleanup(lambda: legal_document_esbirka_opendata_client.bind_http_session(None))
        self.addCleanup(
            lambda: setattr(legal_document_esbirka_opendata_client, "_sleep", time_module.sleep)
        )

    def _create_document(self, *, number: str = "262", year: int = 2006, short_title: str = "ZP"):
        checksum = legal_document_esbirka_opendata_client.build_version_checksum(_ELI)
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number=number,
            year=year,
            short_title=short_title,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=checksum,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            section_number="1",
            title="§ 1",
            text="Původní znění",
            sort_order=1,
        )
        return document, version

    def _seed_completed_run(self) -> None:
        legal_check_run_service.create(
            title="Historická kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            status=CHECK_RUN_COMPLETED,
            documents_checked_count=1,
            changes_found_count=0,
        )

    def test_classify_endpoints(self) -> None:
        self.assertEqual(classify_opendata_endpoint(_ACT_URL), "act")
        self.assertEqual(classify_opendata_endpoint(_WORDING_URL), "wording")
        self.assertEqual(classify_opendata_endpoint(_SPARQL_URL), "sparql")
        self.assertEqual(SAFE_HTTPS_RETRYABLE_STATUSES, frozenset({429, 503}))
        self.assertEqual(ESBIRKA_OPENDATA_HTTP_MAX_RETRIES, 3)

    def test_one_session_for_whole_check_run(self) -> None:
        self._create_document(number="262", short_title="ZP")
        self._create_document(number="390", year=2021, short_title="NV")
        self._seed_completed_run()
        sessions: list[object] = []
        created: list[object] = []

        class _TrackingSession:
            def __init__(self) -> None:
                created.append(self)
                self.closed = False

            def request(self, *args, **kwargs):
                raise AssertionError("request má jít přes safe_https_get")

            def close(self) -> None:
                self.closed = True

        def _get(url, **kwargs):
            sessions.append(kwargs.get("session"))
            raise SafeHttpsError("Vypršel časový limit spojení.", kind="timeout")

        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.requests.Session",
            _TrackingSession,
        ), patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            side_effect=_get,
        ):
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].closed)
        self.assertGreaterEqual(len(sessions), 2)
        self.assertTrue(all(item is created[0] for item in sessions))
        self.assertEqual(result.failed_count, 2)
        self.assertEqual(result.documents_checked_count, 0)
        self.assertIn("kind=timeout", result.run.note or "")
        self.assertIn("endpoint=act", result.run.note or "")
        self.assertIn("ZP", result.run.note or "")
        message = format_automatic_check_user_message(result)
        self.assertIn("kind=timeout", message)
        self.assertIn("endpoint=act", message)

    def test_retry_429_then_success(self) -> None:
        slept: list[float] = []
        first = _FakeRawResponse(status=429, headers={"Retry-After": "2"})
        second = _FakeRawResponse(status=200, body=b'{"ok":true}')
        request = _request_sequence([first, second])
        result = safe_https_get(
            _ACT_URL,
            allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
            timeout=_TIMEOUT,
            max_bytes=1024,
            request=request,
            max_retries=3,
            sleep=slept.append,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.body, b'{"ok":true}')
        self.assertEqual(slept, [2.0])
        self.assertTrue(first.closed)
        self.assertTrue(second.closed)
        self.assertEqual(len(request.calls), 2)

    def test_retry_after_http_date_is_capped(self) -> None:
        waited = parse_retry_after_seconds(
            {"Retry-After": "3600"},
            maximum=30,
        )
        self.assertEqual(waited, 30.0)

    def test_retry_503_then_success(self) -> None:
        slept: list[float] = []
        first = _FakeRawResponse(status=503, body=b"busy")
        second = _FakeRawResponse(status=200, body=b'{"ok":true}')
        result = safe_https_get(
            _ACT_URL,
            allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
            timeout=_TIMEOUT,
            max_bytes=1024,
            request=_request_sequence([first, second]),
            max_retries=3,
            sleep=slept.append,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(slept), 1)
        self.assertGreater(slept[0], 0)

    def test_retry_timeout_then_success(self) -> None:
        slept: list[float] = []
        success = _FakeRawResponse(status=200, body=b'{"ok":true}')
        calls = {"count": 0}

        def _request(method, url, **kwargs):
            assert kwargs["verify"] is True
            assert kwargs["allow_redirects"] is False
            calls["count"] += 1
            if calls["count"] == 1:
                raise Timeout()
            return success

        result = safe_https_get(
            _ACT_URL,
            allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
            timeout=_TIMEOUT,
            max_bytes=1024,
            request=_request,
            max_retries=3,
            sleep=slept.append,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(calls["count"], 2)
        self.assertEqual(len(slept), 1)

    def test_no_retry_on_ordinary_4xx(self) -> None:
        slept: list[float] = []
        for status in (400, 401, 403, 404):
            with self.subTest(status=status):
                slept.clear()
                response = _FakeRawResponse(status=status, body=b"no")
                result = safe_https_get(
                    _ACT_URL,
                    allowed_hosts=ESBIRKA_OPENDATA_ALLOWED_HOSTS,
                    timeout=_TIMEOUT,
                    max_bytes=1024,
                    request=_request_sequence([response]),
                    max_retries=3,
                    sleep=slept.append,
                )
                self.assertEqual(result.status_code, status)
                self.assertEqual(slept, [])
                self.assertTrue(response.closed)

    def test_diagnostics_include_endpoint_and_status(self) -> None:
        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 429, "body": b"", "final_url": _ACT_URL},
            )(),
        ):
            with self.assertRaises(ValueError) as act_error:
                legal_document_esbirka_opendata_client.fetch_latest_wording(
                    year=2006,
                    number="262",
                )
        self.assertIn("kind=http_status", str(act_error.exception))
        self.assertIn("status=429", str(act_error.exception))
        self.assertIn("endpoint=act", str(act_error.exception))

        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            side_effect=SafeHttpsError("Vypršel časový limit spojení.", kind="timeout"),
        ):
            with self.assertRaises(ValueError) as wording_error:
                legal_document_esbirka_opendata_client.fetch_wording_fragments(_ELI)
        self.assertIn("kind=timeout", str(wording_error.exception))
        self.assertIn("status=-", str(wording_error.exception))
        self.assertIn("endpoint=wording", str(wording_error.exception))

        with patch(
            "moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client.safe_https_get",
            return_value=type(
                "R",
                (),
                {"status_code": 503, "body": b"", "final_url": _SPARQL_URL},
            )(),
        ):
            with self.assertRaises(ValueError) as sparql_error:
                legal_document_esbirka_opendata_client.fetch_wording_fragment_contents(_ELI)
        self.assertIn("kind=http_status", str(sparql_error.exception))
        self.assertIn("status=503", str(sparql_error.exception))
        self.assertIn("endpoint=sparql", str(sparql_error.exception))

    def test_retry_exhaustion_is_failed_without_mutating_data(self) -> None:
        document, version = self._create_document()
        original_checksum = version.checksum
        run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))
        calls: list[str] = []
        slept: list[float] = []

        def _always_429(method, url, **kwargs):
            assert kwargs["verify"] is True
            assert kwargs["allow_redirects"] is False
            calls.append(url)
            return _FakeRawResponse(status=429, headers={"Retry-After": "1"})

        legal_document_esbirka_opendata_client._sleep = slept.append
        with patch("core.http_safe.requests.request", side_effect=_always_429):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(result.status, NOVELIZATION_FAILED)
        self.assertIsNone(result.change)
        self.assertIn("kind=http_status", result.error or "")
        self.assertIn("status=429", result.error or "")
        self.assertIn("endpoint=act", result.error or "")
        self.assertEqual(
            legal_document_version_service.get_by_id(version.id).checksum,
            original_checksum,
        )
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])
        self.assertEqual(len(calls), ESBIRKA_OPENDATA_HTTP_MAX_RETRIES + 1)
        self.assertEqual(slept, [1.0] * ESBIRKA_OPENDATA_HTTP_MAX_RETRIES)

    def test_open_data_session_context_restores_previous(self) -> None:
        previous = object()
        legal_document_esbirka_opendata_client.bind_http_session(previous)  # type: ignore[arg-type]
        with open_data_http_session() as session:
            self.assertIs(legal_document_esbirka_opendata_client.http_session, session)
            self.assertIsNot(session, previous)
        self.assertIs(legal_document_esbirka_opendata_client.http_session, previous)


if __name__ == "__main__":
    unittest.main()
