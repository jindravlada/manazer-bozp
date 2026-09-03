"""STATE-SUPERVISION-AUTHORITY-WEB-CHECK-CORE-8E0: společná read-only kontrola."""

from __future__ import annotations

import inspect
import json
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    CBU_AUTHORITY_CODE,
    CBU_OBU_CODES,
    CBU_OFFICE_EXTERNAL_KEYS,
    CBU_OFFICES_SOURCE_URL,
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    DU_OFFICES_SOURCE_URL,
    HZS_AUTHORITY_CODE,
    HZS_OFFICE_EXTERNAL_KEYS,
    HZS_OFFICES_SOURCE_URL,
    KHS_AUTHORITY_CODE,
    KHS_OFFICE_EXTERNAL_KEYS,
    KHS_OFFICES_SOURCE_URL,
    SUIP_AUTHORITY_CODE,
    SUIP_HUB_SOURCE_URL,
    SUIP_OFFICE_EXTERNAL_KEYS,
    SUIP_OIP_CODES,
    WEB_ADAPTER_ERROR_NETWORK,
    WEB_ADAPTER_NETWORK_MESSAGE,
    WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
    WEB_CHECK_ERROR_CODE_REQUIRED,
    WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    WEB_CHECK_ERROR_UNSUPPORTED,
    WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import (
    cbu_office_detail_url,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebAdapterInfo,
    ControlAuthorityWebAdapterRegistration,
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    ControlAuthorityWebCheckService,
    check_authority_web,
    get_web_adapter_info,
    has_web_adapter,
    supported_authority_codes,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityWebDiffError,
    diff_error,
)
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpResponse,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
    adapter_error,
)
from moduly.statni_dozor.sluzby.control_authority_web.suip_adapter import (
    suip_office_detail_url,
)

_REPO = Path(__file__).resolve().parents[1]
_FIXTURES = _REPO / "tests" / "fixtures" / "statni_dozor"
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_CHECK_SOURCE = (
    _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web" / "check.py"
)
_FIXED_AT = datetime(2026, 9, 3, 8, 58, 0)
_EXPECTED_COUNTS = {
    DU_AUTHORITY_CODE: 3,
    SUIP_AUTHORITY_CODE: 8,
    CBU_AUTHORITY_CODE: 7,
    KHS_AUTHORITY_CODE: 14,
    HZS_AUTHORITY_CODE: 14,
}


def _html_response(html: str, url: str) -> ControlAuthorityHttpResponse:
    return ControlAuthorityHttpResponse(
        status_code=200,
        body=html.encode("utf-8"),
        content_type="text/html",
        final_url=url,
    )


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _http_pages(html_by_url: dict[str, str]):
    calls: list[str] = []

    def fake_get(url: str) -> ControlAuthorityHttpResponse:
        calls.append(url)
        if url not in html_by_url:
            raise AssertionError(f"unexpected url {url}")
        return _html_response(html_by_url[url], url)

    return fake_get, calls


def _official_pages(code: str) -> dict[str, str]:
    if code == DU_AUTHORITY_CODE:
        return {DU_OFFICES_SOURCE_URL: _fixture("du_kontakty.html")}
    if code == KHS_AUTHORITY_CODE:
        return {KHS_OFFICES_SOURCE_URL: _fixture("khs_mzd.html")}
    if code == HZS_AUTHORITY_CODE:
        return {HZS_OFFICES_SOURCE_URL: _fixture("hzs_kraju.html")}
    if code == SUIP_AUTHORITY_CODE:
        pages = {SUIP_HUB_SOURCE_URL: _fixture("suip_kontakty_hub.html")}
        for oip in SUIP_OIP_CODES:
            pages[suip_office_detail_url(oip)] = _fixture(f"suip_{oip}.html")
        return pages
    if code == CBU_AUTHORITY_CODE:
        return {
            cbu_office_detail_url(item): _fixture(f"cbu_obu_{item}.html")
            for item in CBU_OBU_CODES
        }
    raise AssertionError(code)


def _seed_snapshots(authority_code: str) -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    authority = next(item for item in payload["authorities"] if item["code"] == authority_code)
    checked = datetime(2026, 1, 1, 12, 0, 0)
    snapshots = []
    for index, office in enumerate(authority["offices"], start=1):
        snapshots.append(
            ControlAuthorityOfficeCatalogSnapshot(
                id=index,
                authority_id=100,
                authority_code=authority_code,
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
                last_checked_at=checked,
            )
        )
    return tuple(snapshots)


class _FakeSnapshotService:
    def __init__(
        self,
        snapshots: tuple[ControlAuthorityOfficeCatalogSnapshot, ...] | None = None,
        *,
        error: Exception | None = None,
    ):
        self.calls: list[str] = []
        self.snapshots = snapshots
        self.error = error

    def load_office_snapshots(self, authority_code: str):
        self.calls.append(authority_code)
        if self.error is not None:
            raise self.error
        return self.snapshots or ()


def _web_record(
    *,
    authority_code: str,
    key: str,
    name: str = "Pracoviště",
    observed: frozenset[str] | None = None,
) -> ControlAuthorityOfficeWebRecord:
    return ControlAuthorityOfficeWebRecord(
        authority_code=authority_code,
        external_key=key,
        name=name,
        address="Ulice 1, 110 00 Praha 1",
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind="regional",
        source_url="https://example.gov.cz/",
        observed_fields=observed or frozenset({"name", "office_kind", "source_url"}),
    )


def _fetch_result(
    records,
    *,
    authority_code: str = DU_AUTHORITY_CODE,
    is_complete: bool = True,
    warnings: tuple[str, ...] = (),
    source_url: str = DU_OFFICES_SOURCE_URL,
) -> ControlAuthorityWebFetchResult:
    return ControlAuthorityWebFetchResult(
        authority_code=authority_code,
        source_url=source_url,
        fetched_at=_FIXED_AT,
        records=tuple(records),
        warnings=warnings,
        is_complete=is_complete,
    )


def _service_with_fetch(
    fetch,
    *,
    snapshots=None,
    info=None,
    compare=None,
):
    info = info or ControlAuthorityWebAdapterInfo(
        authority_code=DU_AUTHORITY_CODE,
        display_name="Drážní úřad",
        source_name="Kontakty Drážního úřadu",
        source_url=DU_OFFICES_SOURCE_URL,
        expected_office_count=3,
    )
    registry = {
        info.authority_code: ControlAuthorityWebAdapterRegistration(info=info, fetch=fetch)
    }
    return ControlAuthorityWebCheckService(
        registry=registry,
        snapshot_service=_FakeSnapshotService(snapshots or _seed_snapshots(info.authority_code)),
        clock=lambda: _FIXED_AT,
        compare=compare,
    )


class StateSupervisionAuthorityWebCheckCore8e0TestCase(unittest.TestCase):
    def test_01_registry_has_exactly_five_codes(self) -> None:
        codes = supported_authority_codes()
        self.assertEqual(
            codes,
            (
                DU_AUTHORITY_CODE,
                SUIP_AUTHORITY_CODE,
                CBU_AUTHORITY_CODE,
                KHS_AUTHORITY_CODE,
                HZS_AUTHORITY_CODE,
            ),
        )
        self.assertEqual(len(codes), 5)
        self.assertEqual(len(set(codes)), 5)

    def test_02_expected_office_counts(self) -> None:
        for code, count in _EXPECTED_COUNTS.items():
            info = get_web_adapter_info(code)
            self.assertEqual(info.expected_office_count, count)

    def test_03_adapter_metadata_are_complete_https(self) -> None:
        for code in supported_authority_codes():
            info = get_web_adapter_info(code)
            self.assertEqual(info.authority_code, code)
            self.assertTrue(info.display_name.strip())
            self.assertTrue(info.source_name.strip())
            self.assertTrue(info.source_url.startswith("https://"))
            self.assertGreater(info.expected_office_count, 0)

    def test_04_trim_and_lowercase_authority_code(self) -> None:
        self.assertTrue(has_web_adapter("  DU  "))
        self.assertTrue(has_web_adapter("Khs"))
        info = get_web_adapter_info("  HZS ")
        self.assertEqual(info.authority_code, HZS_AUTHORITY_CODE)
        fake_get, calls = _http_pages(_official_pages(DU_AUTHORITY_CODE))
        snapshots = _FakeSnapshotService(_seed_snapshots(DU_AUTHORITY_CODE))
        result = ControlAuthorityWebCheckService(
            snapshot_service=snapshots,
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        ).check_authority_web(" Du ")
        self.assertEqual(result.authority_code, DU_AUTHORITY_CODE)
        self.assertEqual(snapshots.calls, [DU_AUTHORITY_CODE])
        self.assertTrue(calls)

    def test_05_unknown_and_empty_codes_are_rejected(self) -> None:
        self.assertFalse(has_web_adapter(""))
        self.assertFalse(has_web_adapter("   "))
        self.assertFalse(has_web_adapter("moje-firma"))
        self.assertFalse(has_web_adapter(None))  # type: ignore[arg-type]
        with self.assertRaises(ControlAuthorityWebCheckError) as empty_ctx:
            get_web_adapter_info("  ")
        self.assertEqual(empty_ctx.exception.code, WEB_CHECK_ERROR_CODE_REQUIRED)
        with self.assertRaises(ControlAuthorityWebCheckError) as unknown_ctx:
            get_web_adapter_info("neexistuje")
        self.assertEqual(unknown_ctx.exception.code, WEB_CHECK_ERROR_UNSUPPORTED)
        self.assertIn("neexistuje", str(unknown_ctx.exception))

    def test_06_adapter_is_not_selected_by_authority_name(self) -> None:
        self.assertFalse(has_web_adapter("Drážní úřad"))
        self.assertFalse(has_web_adapter("authority:du"))
        self.assertFalse(has_web_adapter(DU_OFFICES_SOURCE_URL))
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            check_authority_web("Drážní úřad")
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_UNSUPPORTED)
        self.assertIn("Drážní úřad", str(ctx.exception))

    def test_07_manual_authority_without_adapter_has_clear_error(self) -> None:
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            check_authority_web("moje-suip")
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_UNSUPPORTED)
        self.assertEqual(
            str(ctx.exception),
            "Pro kontrolní orgán „moje-suip“ není dostupná webová kontrola.",
        )

    def test_08_successful_check_for_each_registered_adapter(self) -> None:
        for code in supported_authority_codes():
            fake_get, calls = _http_pages(_official_pages(code))
            snapshots = _FakeSnapshotService(_seed_snapshots(code))
            result = ControlAuthorityWebCheckService(
                snapshot_service=snapshots,
                http_get=fake_get,
                clock=lambda: _FIXED_AT,
            ).check_authority_web(code)
            self.assertIsInstance(result, ControlAuthorityWebCheckResult)
            self.assertEqual(result.authority_code, code)
            self.assertEqual(len(result.remote_records), _EXPECTED_COUNTS[code])
            self.assertEqual(result.fetched_at, _FIXED_AT)
            self.assertTrue(result.source_url.startswith("https://"))
            self.assertEqual(snapshots.calls, [code])
            self.assertTrue(calls)
            self.assertIsNotNone(result.diff_result)
            self.assertEqual(result.diffs, result.diff_result.items)

    def test_09_local_snapshot_is_loaded_once(self) -> None:
        fake_get, _calls = _http_pages(_official_pages(DU_AUTHORITY_CODE))
        snapshots = _FakeSnapshotService(_seed_snapshots(DU_AUTHORITY_CODE))
        ControlAuthorityWebCheckService(
            snapshot_service=snapshots,
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        ).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(snapshots.calls, [DU_AUTHORITY_CODE])

    def test_10_missing_local_authority_stops_before_http(self) -> None:
        called: list[str] = []

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            called.append(url)
            raise AssertionError("HTTP must not run")

        snapshots = _FakeSnapshotService(
            error=diff_error(WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND)
        )
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            ControlAuthorityWebCheckService(
                snapshot_service=snapshots,
                http_get=fake_get,
                clock=lambda: _FIXED_AT,
            ).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND)
        self.assertIsInstance(ctx.exception.__cause__, ControlAuthorityWebDiffError)
        self.assertEqual(called, [])
        self.assertEqual(snapshots.calls, [DU_AUTHORITY_CODE])

    def test_11_incomplete_result_is_rejected(self) -> None:
        records = [
            _web_record(authority_code=DU_AUTHORITY_CODE, key=key)
            for key in DU_OFFICE_EXTERNAL_KEYS
        ]

        def fetch(*, http_get=None, clock=None):
            return _fetch_result(records, is_complete=False)

        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            _service_with_fetch(fetch).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_INCOMPLETE)

    def test_12_wrong_count_with_complete_flag_is_rejected(self) -> None:
        records = [
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:praha"),
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:plzen"),
        ]

        def fetch(*, http_get=None, clock=None):
            return _fetch_result(records, is_complete=True)

        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            _service_with_fetch(fetch).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_UNEXPECTED_COUNT)

    def test_13_remote_authority_code_mismatch_is_rejected(self) -> None:
        records = [
            _web_record(authority_code="suip", key=key)
            for key in DU_OFFICE_EXTERNAL_KEYS
        ]

        def fetch(*, http_get=None, clock=None):
            return _fetch_result(records, authority_code="suip", is_complete=True)

        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            _service_with_fetch(fetch).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_AUTHORITY_MISMATCH)

        def fetch_record_mismatch(*, http_get=None, clock=None):
            mixed = [
                _web_record(authority_code=DU_AUTHORITY_CODE, key="du:praha"),
                _web_record(authority_code="suip", key="du:plzen"),
                _web_record(authority_code=DU_AUTHORITY_CODE, key="du:olomouc"),
            ]
            return _fetch_result(mixed, authority_code=DU_AUTHORITY_CODE)

        with self.assertRaises(ControlAuthorityWebCheckError) as mixed_ctx:
            _service_with_fetch(fetch_record_mismatch).check_authority_web(
                DU_AUTHORITY_CODE
            )
        self.assertEqual(mixed_ctx.exception.code, WEB_CHECK_ERROR_AUTHORITY_MISMATCH)

    def test_14_duplicate_or_empty_external_key_is_rejected(self) -> None:
        duplicate = [
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:praha"),
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:praha"),
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:olomouc"),
        ]

        def fetch_dup(*, http_get=None, clock=None):
            return _fetch_result(duplicate)

        with self.assertRaises(ControlAuthorityWebCheckError) as dup_ctx:
            _service_with_fetch(fetch_dup).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(dup_ctx.exception.code, WEB_DIFF_ERROR_DUPLICATE_REMOTE)

        empty = [
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:praha"),
            _web_record(authority_code=DU_AUTHORITY_CODE, key="  "),
            _web_record(authority_code=DU_AUTHORITY_CODE, key="du:olomouc"),
        ]

        def fetch_empty(*, http_get=None, clock=None):
            return _fetch_result(empty)

        with self.assertRaises(ControlAuthorityWebCheckError) as empty_ctx:
            _service_with_fetch(fetch_empty).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(empty_ctx.exception.code, WEB_DIFF_ERROR_MISSING_KEY)

    def test_15_adapter_error_is_propagated_safely(self) -> None:
        def fetch(*, http_get=None, clock=None):
            raise adapter_error(WEB_ADAPTER_ERROR_NETWORK)

        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            _service_with_fetch(fetch).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_NETWORK)
        self.assertEqual(str(ctx.exception), WEB_ADAPTER_NETWORK_MESSAGE)
        self.assertIsInstance(ctx.exception.__cause__, ControlAuthorityWebAdapterError)
        self.assertNotIn("Traceback", str(ctx.exception))
        self.assertNotIn("<html", str(ctx.exception))

    def test_16_diff_statuses_match_direct_comparator(self) -> None:
        fake_get, _calls = _http_pages(_official_pages(KHS_AUTHORITY_CODE))
        snaps = _seed_snapshots(KHS_AUTHORITY_CODE)
        service = ControlAuthorityWebCheckService(
            snapshot_service=_FakeSnapshotService(snaps),
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        )
        result = service.check_authority_web(KHS_AUTHORITY_CODE)
        direct = diff_control_authority_offices(result.fetch_result, snaps)
        self.assertEqual(result.status_counts, direct.status_counts)
        self.assertEqual(result.has_actionable_changes, direct.has_actionable_changes)
        self.assertEqual(result.has_conflicts, direct.has_conflicts)
        self.assertEqual(
            tuple(item.status for item in result.diffs),
            tuple(item.status for item in direct.items),
        )
        self.assertGreaterEqual(result.status_counts, ())
        self.assertIn(
            result.diff_result.count(WEB_DIFF_STATUS_CHANGED)
            + result.diff_result.count(WEB_DIFF_STATUS_UNCHANGED),
            range(0, 15),
        )

    def test_17_adapter_and_comparator_warnings_are_kept(self) -> None:
        records = [
            _web_record(authority_code=DU_AUTHORITY_CODE, key=key)
            for key in DU_OFFICE_EXTERNAL_KEYS
        ]

        def fetch(*, http_get=None, clock=None):
            return _fetch_result(records, warnings=("varování adapteru",))

        def compare(fetch_result, snapshots):
            original = diff_control_authority_offices(fetch_result, snapshots)
            return replace(original, warnings=original.warnings + ("varování comparatoru",))

        result = _service_with_fetch(fetch, compare=compare).check_authority_web(
            DU_AUTHORITY_CODE
        )
        self.assertIn("varování adapteru", result.warnings)
        self.assertIn("varování comparatoru", result.warnings)

    def test_18_result_dto_has_no_sqlalchemy_session(self) -> None:
        fake_get, _calls = _http_pages(_official_pages(DU_AUTHORITY_CODE))
        result = ControlAuthorityWebCheckService(
            snapshot_service=_FakeSnapshotService(_seed_snapshots(DU_AUTHORITY_CODE)),
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        ).check_authority_web(DU_AUTHORITY_CODE)
        stack = [result]
        seen_ids: set[int] = set()
        while stack:
            current = stack.pop()
            if id(current) in seen_ids:
                continue
            seen_ids.add(id(current))
            self.assertNotIsInstance(current, Session)
            self.assertNotIn("sqlalchemy", type(current).__module__)
            if hasattr(current, "__dict__"):
                stack.extend(current.__dict__.values())
            elif isinstance(current, tuple):
                stack.extend(current)
            elif isinstance(current, dict):
                stack.extend(current.values())

    def test_19_no_catalog_write_and_timestamps_stay(self) -> None:
        source = _CHECK_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("PySide", source)
        self.assertNotIn("sess.commit", source)
        self.assertNotIn("INSERT", source)
        self.assertNotIn("UPDATE", source)
        self.assertNotIn("DELETE", source)
        self.assertNotIn("last_checked_at", source)
        self.assertNotIn("user_edited_at", source)
        seed_before = _SEED.read_bytes()
        snaps = _seed_snapshots(DU_AUTHORITY_CODE)
        fake_get, _calls = _http_pages(_official_pages(DU_AUTHORITY_CODE))
        result = ControlAuthorityWebCheckService(
            snapshot_service=_FakeSnapshotService(snaps),
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        ).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        self.assertEqual(len(snaps), 3)
        for snapshot in snaps:
            self.assertEqual(snapshot.origin, AUTHORITY_ORIGIN_BUNDLED)
            self.assertTrue(snapshot.active)
            self.assertIsNone(snapshot.user_edited_at)
            self.assertEqual(snapshot.last_checked_at, datetime(2026, 1, 1, 12, 0, 0))
        for item in result.diffs:
            if item.local is not None:
                self.assertEqual(item.local.last_checked_at, datetime(2026, 1, 1, 12, 0, 0))
                self.assertEqual(item.local.origin, AUTHORITY_ORIGIN_BUNDLED)
                self.assertTrue(item.local.active)
        test_source = inspect.getsource(self.test_08_successful_check_for_each_registered_adapter)
        self.assertNotIn("requests.get", test_source)


if __name__ == "__main__":
    unittest.main()
