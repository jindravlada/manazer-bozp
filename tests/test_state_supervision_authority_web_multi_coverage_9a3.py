"""STATE-SUPERVISION-AUTHORITY-WEB-MULTI-COVERAGE-9A3: více rozsahů jednoho orgánu."""

from __future__ import annotations

import inspect
import json
import unittest
from datetime import datetime
from pathlib import Path

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    CBU_AUTHORITY_CODE,
    CBU_OBU_CODES,
    CBU_OFFICES_SOURCE_URL,
    DU_AUTHORITY_CODE,
    DU_OFFICES_SOURCE_URL,
    HZS_AUTHORITY_CODE,
    HZS_OFFICES_SOURCE_URL,
    KHS_AUTHORITY_CODE,
    KHS_OFFICES_SOURCE_URL,
    OFFICE_KIND_REGIONAL,
    OFFICE_KIND_TERRITORIAL,
    SUIP_AUTHORITY_CODE,
    SUIP_HUB_SOURCE_URL,
    SUIP_OIP_CODES,
    WEB_ADAPTER_ERROR_NETWORK,
    WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
    WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL,
    WEB_CHECK_DUPLICATE_COVERAGE_MESSAGE,
    WEB_CHECK_DUPLICATE_PRIMARY_MESSAGE,
    WEB_CHECK_ERROR_COVERAGE_REQUIRED,
    WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE,
    WEB_CHECK_MISSING_PRIMARY_MESSAGE,
    WEB_CHECK_REGISTRY_COVERAGE_KEY_MESSAGE,
    WEB_COVERAGE_ID_CBU_REGIONAL,
    WEB_COVERAGE_ID_DU_OFFICES,
    WEB_COVERAGE_ID_HZS_REGIONAL,
    WEB_COVERAGE_ID_KHS_REGIONAL,
    WEB_COVERAGE_ID_SUIP_REGIONAL,
    WEB_COVERAGE_KEYS_REQUIRED_MESSAGE,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import (
    cbu_office_detail_url,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    DEFAULT_WEB_ADAPTER_REGISTRY,
    ControlAuthorityWebAdapterInfo,
    ControlAuthorityWebAdapterRegistration,
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckService,
    build_web_adapter_registry,
    check_authority_web,
    check_authority_web_coverage,
    get_web_adapter_info,
    get_web_adapter_info_by_coverage,
    has_web_adapter,
    list_web_adapter_infos,
    supported_authority_codes,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverage,
    du_web_coverage,
    khs_web_coverage,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
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
_TAB_SOURCE = (
    _REPO / "moduly" / "statni_dozor" / "ui" / "control_authority_catalog_tab.py"
)
_FIXED_AT = datetime(2026, 9, 3, 12, 0, 0)
_PRIMARY_COVERAGE_IDS = (
    WEB_COVERAGE_ID_DU_OFFICES,
    WEB_COVERAGE_ID_SUIP_REGIONAL,
    WEB_COVERAGE_ID_CBU_REGIONAL,
    WEB_COVERAGE_ID_KHS_REGIONAL,
    WEB_COVERAGE_ID_HZS_REGIONAL,
)
_SECONDARY_COVERAGE_ID = "khs-territorial-test"
_TEPLICE_KEY = "khs:ustecky-kraj:teplice"
_LOUNY_KEY = "khs:ustecky-kraj:louny"


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
                last_checked_at=None,
            )
        )
    return tuple(snapshots)


class _FakeSnapshotService:
    def __init__(self, snapshots=()):
        self.calls: list[str] = []
        self.snapshots = tuple(snapshots)

    def load_office_snapshots(self, authority_code: str):
        self.calls.append(authority_code)
        return self.snapshots


class _SpyFetch:
    def __init__(self, result=None, *, error: Exception | None = None):
        self.calls: list[tuple] = []
        self.result = result
        self.error = error

    def __call__(self, *, http_get=None, clock=None):
        self.calls.append((http_get, clock))
        if self.error is not None:
            raise self.error
        return self.result


def _web_record(*, authority_code: str, key: str, office_kind: str):
    return ControlAuthorityOfficeWebRecord(
        authority_code=authority_code,
        external_key=key,
        name=f"Web {key}",
        address="Ulice 1",
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=office_kind,
        source_url="https://example.gov.cz/",
        observed_fields=frozenset({"name", "source_url"}),
    )


def _fetch_result(coverage: ControlAuthorityWebCoverage, *, keys=None):
    used = tuple(keys) if keys is not None else tuple(sorted(coverage.expected_external_keys))
    kind = next(iter(coverage.covered_office_kinds))
    return ControlAuthorityWebFetchResult(
        authority_code=coverage.authority_code,
        source_url="https://example.gov.cz/",
        fetched_at=_FIXED_AT,
        records=tuple(
            _web_record(
                authority_code=coverage.authority_code,
                key=key,
                office_kind=kind,
            )
            for key in used
        ),
        is_complete=True,
    )


def _local(*, office_id: int, key: str, office_kind: str, name: str | None = None):
    return ControlAuthorityOfficeCatalogSnapshot(
        id=office_id,
        authority_id=1,
        authority_code=KHS_AUTHORITY_CODE,
        external_key=key,
        name=name or f"Místní {key}",
        address="Ulice 1",
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=office_kind,
        source_url=None,
        active=True,
        origin=AUTHORITY_ORIGIN_BUNDLED,
        user_edited_at=None,
        last_checked_at=None,
    )


def _primary_khs_info() -> ControlAuthorityWebAdapterInfo:
    return ControlAuthorityWebAdapterInfo(
        authority_code=KHS_AUTHORITY_CODE,
        display_name="Krajské hygienické stanice",
        source_name="Ministerstvo zdravotnictví – Krajské hygienické stanice",
        source_url=KHS_OFFICES_SOURCE_URL,
        coverage=khs_web_coverage(),
        is_primary=True,
        display_order=40,
        coverage_label=WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL,
    )


def _secondary_coverage() -> ControlAuthorityWebCoverage:
    return ControlAuthorityWebCoverage(
        coverage_id=_SECONDARY_COVERAGE_ID,
        authority_code=KHS_AUTHORITY_CODE,
        covered_office_kinds=frozenset({OFFICE_KIND_TERRITORIAL}),
        expected_external_keys=frozenset({_TEPLICE_KEY}),
        covered_external_key_prefixes=frozenset(),
    )


def _secondary_info() -> ControlAuthorityWebAdapterInfo:
    return ControlAuthorityWebAdapterInfo(
        authority_code=KHS_AUTHORITY_CODE,
        display_name="Krajské hygienické stanice",
        source_name="KHS Ústeckého kraje",
        source_url="https://khsusti.cz/kontakt/pracoviste-teplice/",
        coverage=_secondary_coverage(),
        is_primary=False,
        display_order=41,
        coverage_label="KHS Ústeckého kraje – územní pracoviště",
    )


class StateSupervisionAuthorityWebMultiCoverageRegistry9a3TestCase(unittest.TestCase):
    def test_01_five_authority_codes_remain(self) -> None:
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

    def test_02_each_authority_has_exactly_one_primary(self) -> None:
        infos = list_web_adapter_infos()
        self.assertEqual(len(infos), 5)
        primaries = [item for item in infos if item.is_primary]
        self.assertEqual(len(primaries), 5)
        self.assertEqual(
            tuple(item.authority_code for item in primaries),
            supported_authority_codes(),
        )
        for info in primaries:
            self.assertTrue(info.is_primary)
            self.assertEqual(
                get_web_adapter_info(info.authority_code).coverage.coverage_id,
                info.coverage.coverage_id,
            )

    def test_03_registry_is_keyed_by_unique_coverage_id(self) -> None:
        self.assertEqual(tuple(DEFAULT_WEB_ADAPTER_REGISTRY), _PRIMARY_COVERAGE_IDS)
        self.assertEqual(len(DEFAULT_WEB_ADAPTER_REGISTRY), 5)
        self.assertEqual(len(set(DEFAULT_WEB_ADAPTER_REGISTRY)), 5)
        for coverage_id, registration in DEFAULT_WEB_ADAPTER_REGISTRY.items():
            self.assertEqual(registration.coverage_id, coverage_id)
            self.assertEqual(registration.info.coverage.coverage_id, coverage_id)

    def test_04_listing_all_adapters_is_deterministic(self) -> None:
        first = list_web_adapter_infos()
        second = list_web_adapter_infos()
        self.assertEqual(
            tuple(item.coverage.coverage_id for item in first),
            _PRIMARY_COVERAGE_IDS,
        )
        self.assertEqual(
            tuple(item.coverage.coverage_id for item in first),
            tuple(item.coverage.coverage_id for item in second),
        )

    def test_05_khs_listing_returns_only_regional(self) -> None:
        infos = list_web_adapter_infos("khs")
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(infos[0].coverage_label, WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL)
        self.assertTrue(infos[0].is_primary)
        self.assertEqual(list_web_adapter_infos("  KHS "), infos)
        self.assertEqual(list_web_adapter_infos("neexistuje"), ())
        self.assertEqual(list_web_adapter_infos(""), ())
        self.assertEqual(list_web_adapter_infos("   "), ())

    def test_06_unknown_coverage_id_is_rejected(self) -> None:
        with self.assertRaises(ControlAuthorityWebCheckError) as empty:
            get_web_adapter_info_by_coverage("  ")
        self.assertEqual(empty.exception.code, WEB_CHECK_ERROR_COVERAGE_REQUIRED)
        with self.assertRaises(ControlAuthorityWebCheckError) as unknown:
            get_web_adapter_info_by_coverage("khs-territorial-usti")
        self.assertEqual(unknown.exception.code, WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE)
        self.assertIn("khs-territorial-usti", str(unknown.exception))

    def test_07_duplicate_coverage_id_is_rejected(self) -> None:
        info = _primary_khs_info()

        def fetch(*, http_get=None, clock=None):
            raise AssertionError("fetch")

        with self.assertRaises(ValueError) as ctx:
            build_web_adapter_registry(
                (
                    ControlAuthorityWebAdapterRegistration(info=info, fetch=fetch),
                    ControlAuthorityWebAdapterRegistration(info=info, fetch=fetch),
                )
            )
        self.assertEqual(str(ctx.exception), WEB_CHECK_DUPLICATE_COVERAGE_MESSAGE)

    def test_08_two_primaries_for_same_authority_are_rejected(self) -> None:
        primary = _primary_khs_info()
        other = ControlAuthorityWebAdapterInfo(
            authority_code=KHS_AUTHORITY_CODE,
            display_name="Krajské hygienické stanice",
            source_name="Jiný zdroj",
            source_url="https://khsusti.cz/",
            coverage=_secondary_coverage(),
            is_primary=True,
            display_order=41,
        )

        def fetch(*, http_get=None, clock=None):
            raise AssertionError("fetch")

        with self.assertRaises(ValueError) as ctx:
            build_web_adapter_registry(
                (
                    ControlAuthorityWebAdapterRegistration(info=primary, fetch=fetch),
                    ControlAuthorityWebAdapterRegistration(info=other, fetch=fetch),
                )
            )
        self.assertEqual(str(ctx.exception), WEB_CHECK_DUPLICATE_PRIMARY_MESSAGE)

    def test_09_authority_without_primary_is_rejected(self) -> None:
        def fetch(*, http_get=None, clock=None):
            raise AssertionError("fetch")

        with self.assertRaises(ValueError) as ctx:
            build_web_adapter_registry(
                (
                    ControlAuthorityWebAdapterRegistration(
                        info=_secondary_info(),
                        fetch=fetch,
                    ),
                )
            )
        self.assertEqual(str(ctx.exception), WEB_CHECK_MISSING_PRIMARY_MESSAGE)

    def test_10_adapter_coverage_authority_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as mismatch:
            ControlAuthorityWebAdapterInfo(
                authority_code=KHS_AUTHORITY_CODE,
                display_name="Krajské hygienické stanice",
                source_name="Kontakty Drážního úřadu",
                source_url=DU_OFFICES_SOURCE_URL,
                coverage=du_web_coverage(),
            )
        self.assertEqual(str(mismatch.exception), WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE)
        with self.assertRaises(ValueError) as keys:
            ControlAuthorityWebCoverage(
                coverage_id=_SECONDARY_COVERAGE_ID,
                authority_code=KHS_AUTHORITY_CODE,
                covered_office_kinds=frozenset({OFFICE_KIND_TERRITORIAL}),
                expected_external_keys=frozenset(),
            )
        self.assertEqual(str(keys.exception), WEB_COVERAGE_KEYS_REQUIRED_MESSAGE)
        khs = _primary_khs_info()

        def fetch(*, http_get=None, clock=None):
            raise AssertionError("fetch")

        with self.assertRaises(ValueError) as keyed:
            build_web_adapter_registry(
                {
                    _SECONDARY_COVERAGE_ID: ControlAuthorityWebAdapterRegistration(
                        info=khs,
                        fetch=fetch,
                    )
                }
            )
        self.assertEqual(str(keyed.exception), WEB_CHECK_REGISTRY_COVERAGE_KEY_MESSAGE)


class StateSupervisionAuthorityWebMultiCoverageCompat9a3TestCase(unittest.TestCase):
    def test_01_check_by_authority_delegates_to_primary_coverage(self) -> None:
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(_fetch_result(_secondary_coverage()))
        service = ControlAuthorityWebCheckService(
            registry=(
                ControlAuthorityWebAdapterRegistration(
                    info=_primary_khs_info(),
                    fetch=primary,
                ),
                ControlAuthorityWebAdapterRegistration(
                    info=_secondary_info(),
                    fetch=secondary,
                ),
            ),
            snapshot_service=_FakeSnapshotService(),
            clock=lambda: _FIXED_AT,
        )
        result = service.check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(primary.calls), 1)
        self.assertEqual(secondary.calls, [])
        by_coverage = service.check_authority_web_coverage(WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(by_coverage.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(primary.calls), 2)

    def test_02_get_web_adapter_info_returns_primary(self) -> None:
        info = get_web_adapter_info("  Khs ")
        self.assertTrue(info.is_primary)
        self.assertEqual(info.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(info.coverage_label, WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL)
        self.assertNotEqual(info.coverage.coverage_id, info.coverage_label)

    def test_03_has_web_adapter_khs_stays_true(self) -> None:
        self.assertTrue(has_web_adapter("khs"))
        self.assertTrue(has_web_adapter("KHS"))
        self.assertFalse(has_web_adapter(_SECONDARY_COVERAGE_ID))

    def test_04_ui_still_starts_one_authority_check(self) -> None:
        source = _TAB_SOURCE.read_text(encoding="utf-8")
        self.assertIn("check_authority_web", source)
        self.assertNotIn("check_authority_web_coverage", source)
        self.assertNotIn("list_web_adapter_infos", source)
        preview = inspect.getsource(
            __import__(
                "moduly.statni_dozor.ui.control_authority_catalog_tab",
                fromlist=["_run_control_authority_web_check"],
            )._run_control_authority_web_check
        )
        self.assertIn("check_authority_web(", preview)
        self.assertNotIn("check_authority_web_coverage", preview)

    def test_05_five_adapters_keep_the_same_diff_results(self) -> None:
        for code in supported_authority_codes():
            fake_get, calls = _http_pages(_official_pages(code))
            snapshots = _FakeSnapshotService(_seed_snapshots(code))
            service = ControlAuthorityWebCheckService(
                snapshot_service=snapshots,
                http_get=fake_get,
                clock=lambda: _FIXED_AT,
            )
            by_code = service.check_authority_web(code)
            by_coverage = service.check_authority_web_coverage(
                get_web_adapter_info(code).coverage.coverage_id
            )
            self.assertEqual(by_code.coverage.coverage_id, by_coverage.coverage.coverage_id)
            self.assertEqual(
                tuple(item.external_key for item in by_code.remote_records),
                tuple(item.external_key for item in by_coverage.remote_records),
            )
            self.assertEqual(by_code.status_counts, by_coverage.status_counts)
            self.assertEqual(len(by_code.remote_records), get_web_adapter_info(code).expected_office_count)
            self.assertTrue(calls)

    def test_06_no_extra_http_and_no_db_write(self) -> None:
        source = _CHECK_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("sess.commit", source)
        self.assertNotIn("last_checked_at", source)
        seed_before = _SEED.read_bytes()
        fake_get, calls = _http_pages(_official_pages(KHS_AUTHORITY_CODE))
        service = ControlAuthorityWebCheckService(
            snapshot_service=_FakeSnapshotService(_seed_snapshots(KHS_AUTHORITY_CODE)),
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        )
        result = service.check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], KHS_OFFICES_SOURCE_URL)
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(result.remote_records), 14)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        self.assertNotIn(_TEPLICE_KEY, {item.external_key for item in result.diffs})


class StateSupervisionAuthorityWebMultiCoverageSecond9a3TestCase(unittest.TestCase):
    def _service(self, *, primary: _SpyFetch, secondary: _SpyFetch, snapshots=()):
        return ControlAuthorityWebCheckService(
            registry=(
                ControlAuthorityWebAdapterRegistration(
                    info=_primary_khs_info(),
                    fetch=primary,
                ),
                ControlAuthorityWebAdapterRegistration(
                    info=_secondary_info(),
                    fetch=secondary,
                ),
            ),
            snapshot_service=_FakeSnapshotService(snapshots),
            clock=lambda: _FIXED_AT,
        )

    def test_01_both_coverages_are_listed_for_khs(self) -> None:
        service = self._service(
            primary=_SpyFetch(_fetch_result(khs_web_coverage())),
            secondary=_SpyFetch(_fetch_result(_secondary_coverage())),
        )
        infos = service.list_web_adapter_infos(KHS_AUTHORITY_CODE)
        self.assertEqual(
            tuple(item.coverage.coverage_id for item in infos),
            (WEB_COVERAGE_ID_KHS_REGIONAL, _SECONDARY_COVERAGE_ID),
        )
        self.assertTrue(infos[0].is_primary)
        self.assertFalse(infos[1].is_primary)
        self.assertEqual(service.supported_authority_codes(), (KHS_AUTHORITY_CODE,))
        self.assertEqual(
            service.get_web_adapter_info(KHS_AUTHORITY_CODE).coverage.coverage_id,
            WEB_COVERAGE_ID_KHS_REGIONAL,
        )

    def test_02_authority_check_runs_only_primary(self) -> None:
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(_fetch_result(_secondary_coverage()))
        result = self._service(primary=primary, secondary=secondary).check_authority_web(
            KHS_AUTHORITY_CODE
        )
        self.assertEqual(len(primary.calls), 1)
        self.assertEqual(secondary.calls, [])
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(result.remote_records), 14)

    def test_03_coverage_check_runs_only_secondary(self) -> None:
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(_fetch_result(_secondary_coverage()))
        result = self._service(
            primary=primary,
            secondary=secondary,
        ).check_authority_web_coverage(_SECONDARY_COVERAGE_ID)
        self.assertEqual(len(secondary.calls), 1)
        self.assertEqual(primary.calls, [])
        self.assertEqual(result.coverage.coverage_id, _SECONDARY_COVERAGE_ID)
        self.assertEqual(len(result.remote_records), 1)
        self.assertEqual(result.remote_records[0].external_key, _TEPLICE_KEY)

    def test_04_secondary_failure_does_not_affect_primary(self) -> None:
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(error=adapter_error(WEB_ADAPTER_ERROR_NETWORK))
        service = self._service(primary=primary, secondary=secondary)
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            service.check_authority_web_coverage(_SECONDARY_COVERAGE_ID)
        self.assertEqual(ctx.exception.code, WEB_ADAPTER_ERROR_NETWORK)
        result = service.check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(result.remote_records), 14)
        self.assertEqual(len(primary.calls), 1)

    def test_05_expected_keys_are_checked_independently(self) -> None:
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(
            _fetch_result(_secondary_coverage(), keys=(_TEPLICE_KEY, _LOUNY_KEY))
        )
        service = self._service(primary=primary, secondary=secondary)
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            service.check_authority_web_coverage(_SECONDARY_COVERAGE_ID)
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_UNEXPECTED_COUNT)
        ok = service.check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(ok.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(ok.remote_records), 14)

    def test_06_secondary_missing_remote_uses_only_its_keys_and_kinds(self) -> None:
        snapshots = (
            _local(office_id=1, key="khs:ustecky-kraj", office_kind=OFFICE_KIND_REGIONAL),
            _local(office_id=2, key=_TEPLICE_KEY, office_kind=OFFICE_KIND_TERRITORIAL),
            _local(office_id=3, key=_LOUNY_KEY, office_kind=OFFICE_KIND_TERRITORIAL),
        )
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(_fetch_result(_secondary_coverage()))
        result = self._service(
            primary=primary,
            secondary=secondary,
            snapshots=snapshots,
        ).check_authority_web_coverage(_SECONDARY_COVERAGE_ID)
        keys = {item.external_key: item.status for item in result.diffs}
        self.assertEqual(keys.get(_LOUNY_KEY), WEB_DIFF_STATUS_MISSING_REMOTE)
        self.assertNotIn("khs:ustecky-kraj", keys)
        self.assertNotIn(
            WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
            {item.status for item in result.diffs},
        )
        self.assertEqual(result.coverage.expected_external_keys, frozenset({_TEPLICE_KEY}))

    def test_07_results_are_not_merged_into_authority_complete(self) -> None:
        primary = _SpyFetch(_fetch_result(khs_web_coverage()))
        secondary = _SpyFetch(_fetch_result(_secondary_coverage()))
        service = self._service(primary=primary, secondary=secondary)
        primary_result = service.check_authority_web(KHS_AUTHORITY_CODE)
        secondary_result = service.check_authority_web_coverage(_SECONDARY_COVERAGE_ID)
        self.assertEqual(primary_result.adapter_info.expected_office_count, 14)
        self.assertEqual(secondary_result.adapter_info.expected_office_count, 1)
        self.assertNotEqual(
            frozenset(item.external_key for item in primary_result.remote_records),
            frozenset(item.external_key for item in secondary_result.remote_records),
        )
        self.assertTrue(primary_result.fetch_result.is_complete)
        self.assertTrue(secondary_result.fetch_result.is_complete)
        self.assertIsNone(getattr(primary_result, "all_coverages", None))


if __name__ == "__main__":
    unittest.main()
