"""STATE-SUPERVISION-AUTHORITY-WEB-COVERAGE-9A1: bezpečné rozsahy webových adapterů."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    AUTHORITY_ORIGIN_MANUAL,
    AUTHORITY_ORIGIN_WEB,
    CBU_AUTHORITY_CODE,
    CBU_OFFICE_EXTERNAL_KEYS,
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    HZS_AUTHORITY_CODE,
    HZS_OFFICE_EXTERNAL_KEYS,
    KHS_AUTHORITY_CODE,
    KHS_OFFICE_EXTERNAL_KEYS,
    KHS_OFFICES_SOURCE_URL,
    OFFICE_KIND_HEADQUARTERS,
    OFFICE_KIND_REGIONAL,
    OFFICE_KIND_TERRITORIAL,
    SUIP_AUTHORITY_CODE,
    SUIP_OFFICE_EXTERNAL_KEYS,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ERROR_SELECTION,
    WEB_CHECK_ERROR_COVERAGE_KIND,
    WEB_CHECK_ERROR_COVERAGE_KIND,
    WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    WEB_CHECK_UI_WARNINGS_TITLE,
    WEB_COVERAGE_AUTHORITY_CODE_INVALID_MESSAGE,
    WEB_COVERAGE_ID_CBU_REGIONAL,
    WEB_COVERAGE_ID_DU_OFFICES,
    WEB_COVERAGE_ID_HZS_REGIONAL,
    WEB_COVERAGE_ID_KHS_REGIONAL,
    WEB_COVERAGE_ID_REQUIRED_MESSAGE,
    WEB_COVERAGE_ID_SUIP_REGIONAL,
    WEB_COVERAGE_KEY_AUTHORITY_MESSAGE,
    WEB_COVERAGE_KEY_INVALID_MESSAGE,
    WEB_COVERAGE_KEYS_REQUIRED_MESSAGE,
    WEB_COVERAGE_KIND_UNKNOWN_MESSAGE,
    WEB_COVERAGE_KINDS_REQUIRED_MESSAGE,
    WEB_COVERAGE_UNKNOWN_KIND_WARNING,
    WEB_DIFF_ACTION_UPDATE,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityOfficeWebApplySelection,
    ControlAuthorityWebApplyError,
    apply_authority_web_changes,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebAdapterRegistration,
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    ControlAuthorityWebCheckService,
    get_web_adapter_info,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverage,
    ControlAuthorityWebCoverageError,
    all_web_coverages,
    cbu_web_coverage,
    coverage_for_authority,
    du_web_coverage,
    hzs_web_coverage,
    khs_web_coverage,
    suip_web_coverage,
    unknown_office_kind_warning,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityOfficeFieldChange,
)
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpResponse,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebFetchResult,
)

_REPO = Path(__file__).resolve().parents[1]
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXTURE = _REPO / "tests" / "fixtures" / "statni_dozor" / "khs_mzd.html"
_COVERAGE_SOURCE = (
    _REPO / "moduly" / "statni_dozor" / "sluzby" / "control_authority_web" / "coverage.py"
)
_FIXED_AT = datetime(2026, 9, 3, 11, 20, 0)
_TEPLICE_KEY = "khs:ustecky-kraj:teplice"
_TEPLICE_NAME = "KHS Ústeckého kraje – Územní pracoviště Teplice"
_EXTRA_KEYS = {
    DU_AUTHORITY_CODE: "du:brno",
    SUIP_AUTHORITY_CODE: "suip:oip-navic",
    CBU_AUTHORITY_CODE: "cbu:obu-navic",
    KHS_AUTHORITY_CODE: "khs:navic",
    HZS_AUTHORITY_CODE: "hzs:navic",
}
_COVERAGES = (
    du_web_coverage(),
    suip_web_coverage(),
    cbu_web_coverage(),
    khs_web_coverage(),
    hzs_web_coverage(),
)
_SEED_KEYS = {
    DU_AUTHORITY_CODE: DU_OFFICE_EXTERNAL_KEYS,
    SUIP_AUTHORITY_CODE: SUIP_OFFICE_EXTERNAL_KEYS,
    CBU_AUTHORITY_CODE: CBU_OFFICE_EXTERNAL_KEYS,
    KHS_AUTHORITY_CODE: KHS_OFFICE_EXTERNAL_KEYS,
    HZS_AUTHORITY_CODE: HZS_OFFICE_EXTERNAL_KEYS,
}


def _remote(
    *,
    authority_code: str,
    key: str,
    name: str | None = None,
    office_kind: str | None = None,
    observed: frozenset[str] | None = None,
) -> ControlAuthorityOfficeWebRecord:
    return ControlAuthorityOfficeWebRecord(
        authority_code=authority_code,
        external_key=key,
        name=name or f"Pracoviště {key}",
        address="Ulice 1, 110 00 Praha 1",
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=office_kind,
        source_url="https://example.gov.cz/",
        observed_fields=observed or frozenset({"name", "source_url"}),
    )


def _local(
    *,
    office_id: int,
    authority_code: str,
    key: str | None,
    name: str | None = None,
    office_kind: str | None = OFFICE_KIND_REGIONAL,
    origin: str = AUTHORITY_ORIGIN_BUNDLED,
    user_edited_at: datetime | None = None,
) -> ControlAuthorityOfficeCatalogSnapshot:
    return ControlAuthorityOfficeCatalogSnapshot(
        id=office_id,
        authority_id=1,
        authority_code=authority_code,
        external_key=key,
        name=name or f"Místní {key or office_id}",
        address="Ulice 1",
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=office_kind,
        source_url=None,
        active=True,
        origin=origin,
        user_edited_at=user_edited_at,
        last_checked_at=None,
    )


def _fetch(records, *, authority_code: str, is_complete: bool = True):
    return ControlAuthorityWebFetchResult(
        authority_code=authority_code,
        source_url="https://example.gov.cz/",
        fetched_at=_FIXED_AT,
        records=tuple(records),
        is_complete=is_complete,
    )


def _records_for(coverage: ControlAuthorityWebCoverage, keys=None):
    ordered = keys if keys is not None else _SEED_KEYS[coverage.authority_code]
    return tuple(
        _remote(authority_code=coverage.authority_code, key=key) for key in ordered
    )


def _matching_locals(coverage: ControlAuthorityWebCoverage, *, kind: str):
    return tuple(
        _local(
            office_id=index,
            authority_code=coverage.authority_code,
            key=key,
            name=f"Pracoviště {key}",
            office_kind=kind,
        )
        for index, key in enumerate(_SEED_KEYS[coverage.authority_code], start=1)
    )


class _FakeSnapshots:
    def __init__(self, snapshots=()):
        self.snapshots = tuple(snapshots)
        self.calls: list[str] = []

    def load_office_snapshots(self, authority_code: str):
        self.calls.append(authority_code)
        return self.snapshots


def _compare_spy():
    state = {"called": False}

    def compare(fetch_result, snapshots, coverage=None):
        state["called"] = True
        raise AssertionError("porovnání se nesmí spustit")

    return compare, state


def _missing_statuses(result):
    items = getattr(result, "items", None)
    if items is None:
        items = result.diffs
    return tuple(
        item.status
        for item in items
        if item.status
        in {WEB_DIFF_STATUS_MISSING_REMOTE, WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE}
    )


class StateSupervisionAuthorityWebCoverageDto9a1TestCase(unittest.TestCase):
    def test_01_existing_coverages_share_seed_keys(self) -> None:
        expected = {
            WEB_COVERAGE_ID_DU_OFFICES: (
                DU_AUTHORITY_CODE,
                frozenset({OFFICE_KIND_HEADQUARTERS, OFFICE_KIND_TERRITORIAL}),
                frozenset(DU_OFFICE_EXTERNAL_KEYS),
            ),
            WEB_COVERAGE_ID_SUIP_REGIONAL: (
                SUIP_AUTHORITY_CODE,
                frozenset({OFFICE_KIND_REGIONAL}),
                frozenset(SUIP_OFFICE_EXTERNAL_KEYS),
            ),
            WEB_COVERAGE_ID_CBU_REGIONAL: (
                CBU_AUTHORITY_CODE,
                frozenset({OFFICE_KIND_TERRITORIAL}),
                frozenset(CBU_OFFICE_EXTERNAL_KEYS),
            ),
            WEB_COVERAGE_ID_KHS_REGIONAL: (
                KHS_AUTHORITY_CODE,
                frozenset({OFFICE_KIND_REGIONAL}),
                frozenset(KHS_OFFICE_EXTERNAL_KEYS),
            ),
            WEB_COVERAGE_ID_HZS_REGIONAL: (
                HZS_AUTHORITY_CODE,
                frozenset({OFFICE_KIND_REGIONAL}),
                frozenset(HZS_OFFICE_EXTERNAL_KEYS),
            ),
        }
        found = {item.coverage_id: item for item in all_web_coverages()}
        self.assertEqual(set(found), set(expected))
        for coverage_id, (code, kinds, keys) in expected.items():
            item = found[coverage_id]
            self.assertEqual(item.authority_code, code)
            self.assertEqual(item.covered_office_kinds, kinds)
            self.assertEqual(item.expected_external_keys, keys)
            self.assertEqual(item.expected_office_count, len(keys))
            self.assertFalse(hasattr(item, "ico"))
            info = get_web_adapter_info(code)
            self.assertEqual(info.coverage, item)
            self.assertEqual(info.coverage.coverage_id, coverage_id)
            self.assertNotEqual(info.coverage.coverage_id, info.display_name)
            self.assertNotIn(info.display_name.casefold(), coverage_id)

    def test_02_dto_rejects_invalid_values(self) -> None:
        valid = dict(
            coverage_id="khs-regional",
            authority_code=KHS_AUTHORITY_CODE,
            covered_office_kinds=frozenset({OFFICE_KIND_REGIONAL}),
            expected_external_keys=frozenset(KHS_OFFICE_EXTERNAL_KEYS),
        )
        with self.assertRaises(ValueError) as empty_id:
            ControlAuthorityWebCoverage(**{**valid, "coverage_id": "  "})
        self.assertEqual(str(empty_id.exception), WEB_COVERAGE_ID_REQUIRED_MESSAGE)
        with self.assertRaises(ValueError) as upper:
            ControlAuthorityWebCoverage(**{**valid, "authority_code": "KHS"})
        self.assertEqual(str(upper.exception), WEB_COVERAGE_AUTHORITY_CODE_INVALID_MESSAGE)
        with self.assertRaises(ValueError) as kinds:
            ControlAuthorityWebCoverage(**{**valid, "covered_office_kinds": frozenset()})
        self.assertEqual(str(kinds.exception), WEB_COVERAGE_KINDS_REQUIRED_MESSAGE)
        with self.assertRaises(ValueError) as unknown:
            ControlAuthorityWebCoverage(
                **{**valid, "covered_office_kinds": frozenset({"krajska"})}
            )
        self.assertEqual(str(unknown.exception), WEB_COVERAGE_KIND_UNKNOWN_MESSAGE)
        with self.assertRaises(ValueError) as keys:
            ControlAuthorityWebCoverage(
                **{**valid, "expected_external_keys": frozenset()}
            )
        self.assertEqual(str(keys.exception), WEB_COVERAGE_KEYS_REQUIRED_MESSAGE)
        with self.assertRaises(ValueError) as empty_key:
            ControlAuthorityWebCoverage(
                **{**valid, "expected_external_keys": ("khs:praha", "  ")}
            )
        self.assertEqual(str(empty_key.exception), WEB_COVERAGE_KEY_INVALID_MESSAGE)
        with self.assertRaises(ValueError) as foreign:
            ControlAuthorityWebCoverage(
                **{**valid, "expected_external_keys": ("khs:praha", "du:praha")}
            )
        self.assertEqual(str(foreign.exception), WEB_COVERAGE_KEY_AUTHORITY_MESSAGE)

    def test_03_coverage_module_has_no_qt_sqlalchemy_or_ico(self) -> None:
        source = _COVERAGE_SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("sqlalchemy", source)
        self.assertNotIn("PySide", source)
        self.assertNotIn("ico", source.casefold())
        self.assertIsNone(coverage_for_authority("Drážní úřad"))
        self.assertEqual(coverage_for_authority(" KHS "), khs_web_coverage())


class StateSupervisionAuthorityWebCoverageDiff9a1TestCase(unittest.TestCase):
    def test_01_khs_territorial_is_out_of_scope(self) -> None:
        coverage = khs_web_coverage()
        remotes = _records_for(coverage)
        snapshots = _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (
            _local(
                office_id=99,
                authority_code=KHS_AUTHORITY_CODE,
                key=_TEPLICE_KEY,
                name=_TEPLICE_NAME,
                office_kind=OFFICE_KIND_TERRITORIAL,
            ),
        )
        result = diff_control_authority_offices(
            _fetch(remotes, authority_code=KHS_AUTHORITY_CODE),
            snapshots,
            coverage,
        )
        self.assertEqual(_missing_statuses(result), ())
        self.assertNotIn(_TEPLICE_KEY, {item.external_key for item in result.items})
        self.assertEqual(result.count(WEB_DIFF_STATUS_MISSING_REMOTE), 0)
        self.assertEqual(result.warnings, ())

    def test_02_hzs_territorial_is_out_of_scope(self) -> None:
        coverage = hzs_web_coverage()
        extra = _local(
            office_id=99,
            authority_code=HZS_AUTHORITY_CODE,
            key="hzs:ustecky-kraj:teplice",
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=HZS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (extra,),
            coverage,
        )
        self.assertEqual(_missing_statuses(result), ())
        self.assertNotIn(extra.external_key, {item.external_key for item in result.items})

    def test_03_suip_territorial_is_out_of_scope(self) -> None:
        coverage = suip_web_coverage()
        extra = _local(
            office_id=99,
            authority_code=SUIP_AUTHORITY_CODE,
            key="suip:oip-praha:kladno",
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=SUIP_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (extra,),
            coverage,
        )
        self.assertEqual(_missing_statuses(result), ())
        self.assertNotIn(extra.external_key, {item.external_key for item in result.items})

    def test_04_unmatched_regional_is_missing_remote(self) -> None:
        coverage = khs_web_coverage()
        extra = _local(
            office_id=99,
            authority_code=KHS_AUTHORITY_CODE,
            key="khs:navic",
            office_kind=OFFICE_KIND_REGIONAL,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=KHS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (extra,),
            coverage,
        )
        missing = [item for item in result.items if item.status == WEB_DIFF_STATUS_MISSING_REMOTE]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0].external_key, "khs:navic")
        self.assertTrue(result.has_actionable_changes)

    def test_05_protected_unmatched_regional_is_protected_missing(self) -> None:
        coverage = khs_web_coverage()
        extra = _local(
            office_id=99,
            authority_code=KHS_AUTHORITY_CODE,
            key="khs:navic",
            office_kind=OFFICE_KIND_REGIONAL,
            origin=AUTHORITY_ORIGIN_MANUAL,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=KHS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (extra,),
            coverage,
        )
        protected = [
            item
            for item in result.items
            if item.status == WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE
        ]
        self.assertEqual(len(protected), 1)
        self.assertEqual(protected[0].external_key, "khs:navic")

    def test_06_unknown_office_kind_warns_and_skips(self) -> None:
        coverage = khs_web_coverage()
        unknown = _local(
            office_id=99,
            authority_code=KHS_AUTHORITY_CODE,
            key="khs:bez-druhu",
            name="KHS bez druhu",
            office_kind=None,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=KHS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (unknown,),
            coverage,
        )
        self.assertEqual(_missing_statuses(result), ())
        self.assertEqual(result.warnings, (unknown_office_kind_warning("KHS bez druhu"),))
        self.assertEqual(
            result.warnings[0],
            WEB_COVERAGE_UNKNOWN_KIND_WARNING.format(name="KHS bez druhu"),
        )
        empty = _local(
            office_id=100,
            authority_code=KHS_AUTHORITY_CODE,
            key="khs:prazdny-druh",
            name="KHS prázdný",
            office_kind="  ",
        )
        weird = _local(
            office_id=101,
            authority_code=KHS_AUTHORITY_CODE,
            key="khs:neznamy-druh",
            name="KHS neznámý",
            office_kind="krajska",
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=KHS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (empty, weird),
            coverage,
        )
        self.assertEqual(_missing_statuses(result), ())
        self.assertIn(unknown_office_kind_warning("KHS prázdný"), result.warnings)
        self.assertIn(unknown_office_kind_warning("KHS neznámý"), result.warnings)

    def test_07_manual_without_key_stays_out_of_missing(self) -> None:
        coverage = khs_web_coverage()
        manual = _local(
            office_id=99,
            authority_code=KHS_AUTHORITY_CODE,
            key=None,
            name="Ruční KHS",
            office_kind=OFFICE_KIND_REGIONAL,
            origin=AUTHORITY_ORIGIN_MANUAL,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=KHS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (manual,),
            coverage,
        )
        self.assertEqual(_missing_statuses(result), ())
        self.assertNotIn("Ruční KHS", [item.local.name for item in result.items if item.local])

    def test_08_same_key_compares_even_if_local_is_territorial(self) -> None:
        coverage = khs_web_coverage()
        remotes = [
            _remote(
                authority_code=KHS_AUTHORITY_CODE,
                key=key,
                name=f"Pracoviště {key}",
                office_kind=OFFICE_KIND_REGIONAL,
                observed=frozenset({"name", "office_kind"}),
            )
            for key in KHS_OFFICE_EXTERNAL_KEYS
        ]
        snapshots = []
        for index, key in enumerate(KHS_OFFICE_EXTERNAL_KEYS, start=1):
            kind = (
                OFFICE_KIND_TERRITORIAL
                if key == "khs:ustecky-kraj"
                else OFFICE_KIND_REGIONAL
            )
            snapshots.append(
                _local(
                    office_id=index,
                    authority_code=KHS_AUTHORITY_CODE,
                    key=key,
                    office_kind=kind,
                    name=f"Pracoviště {key}",
                )
            )
        result = diff_control_authority_offices(
            _fetch(remotes, authority_code=KHS_AUTHORITY_CODE),
            snapshots,
            coverage,
        )
        matched = next(item for item in result.items if item.external_key == "khs:ustecky-kraj")
        self.assertEqual(matched.local_id, snapshots[5].id)
        self.assertIsNotNone(matched.remote)
        self.assertEqual(matched.status, WEB_DIFF_STATUS_CHANGED)
        self.assertEqual(tuple(change.field for change in matched.field_changes), ("office_kind",))

    def test_09_observed_kind_outside_coverage_is_contract_error(self) -> None:
        coverage = khs_web_coverage()
        remotes = [
            _remote(
                authority_code=KHS_AUTHORITY_CODE,
                key=key,
                office_kind=(
                    OFFICE_KIND_TERRITORIAL
                    if key == "khs:praha"
                    else OFFICE_KIND_REGIONAL
                ),
                observed=frozenset({"name", "office_kind", "source_url"}),
            )
            for key in KHS_OFFICE_EXTERNAL_KEYS
        ]
        with self.assertRaises(ControlAuthorityWebCoverageError) as ctx:
            diff_control_authority_offices(
                _fetch(remotes, authority_code=KHS_AUTHORITY_CODE),
                _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL),
                coverage,
            )
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_COVERAGE_KIND)

    def test_10_without_coverage_never_emits_missing_remote(self) -> None:
        coverage = khs_web_coverage()
        extra = _local(
            office_id=99,
            authority_code=KHS_AUTHORITY_CODE,
            key="khs:navic",
            office_kind=OFFICE_KIND_REGIONAL,
        )
        result = diff_control_authority_offices(
            _fetch(_records_for(coverage), authority_code=KHS_AUTHORITY_CODE),
            _matching_locals(coverage, kind=OFFICE_KIND_REGIONAL) + (extra,),
            None,
        )
        self.assertEqual(_missing_statuses(result), ())


class StateSupervisionAuthorityWebCoverageKeys9a1TestCase(unittest.TestCase):
    def _check(self, coverage: ControlAuthorityWebCoverage, records, *, compare=None):
        fetch_result = _fetch(records, authority_code=coverage.authority_code)

        def fetch(*, http_get=None, clock=None):
            return fetch_result

        info = get_web_adapter_info(coverage.authority_code)
        return ControlAuthorityWebCheckService(
            registry={
                coverage.authority_code: ControlAuthorityWebAdapterRegistration(
                    info=info,
                    fetch=fetch,
                )
            },
            snapshot_service=_FakeSnapshots(),
            clock=lambda: _FIXED_AT,
            compare=compare,
        ).check_authority_web(coverage.authority_code)

    def test_01_exact_keys_pass_for_each_adapter(self) -> None:
        for coverage in _COVERAGES:
            with self.subTest(coverage_id=coverage.coverage_id):
                result = self._check(coverage, _records_for(coverage))
                self.assertEqual(result.coverage, coverage)
                self.assertEqual(
                    frozenset(item.external_key for item in result.remote_records),
                    coverage.expected_external_keys,
                )
                self.assertEqual(result.adapter_info.expected_office_count, len(coverage.expected_external_keys))

    def test_02_missing_extra_swap_duplicate_fail_before_diff(self) -> None:
        seed_before = _SEED.read_bytes()
        for coverage in _COVERAGES:
            keys = list(_SEED_KEYS[coverage.authority_code])
            extra = _EXTRA_KEYS[coverage.authority_code]
            cases = {
                "missing": keys[:-1],
                "extra": keys + [extra],
                "swap": keys[:-1] + [extra],
                "duplicate": keys[:-1] + [keys[0]],
            }
            for label, used in cases.items():
                with self.subTest(coverage_id=coverage.coverage_id, case=label):
                    compare, state = _compare_spy()
                    with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
                        self._check(
                            coverage,
                            _records_for(coverage, used),
                            compare=compare,
                        )
                    self.assertFalse(state["called"])
                    if label == "duplicate":
                        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_DUPLICATE_REMOTE)
                    else:
                        self.assertEqual(
                            ctx.exception.code, WEB_CHECK_ERROR_UNEXPECTED_COUNT
                        )
                    self.assertEqual(_SEED.read_bytes(), seed_before)

    def test_03_incomplete_flag_fails_before_diff(self) -> None:
        coverage = du_web_coverage()
        fetch_result = _fetch(
            _records_for(coverage),
            authority_code=DU_AUTHORITY_CODE,
            is_complete=False,
        )

        def fetch(*, http_get=None, clock=None):
            return fetch_result

        compare, state = _compare_spy()
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            ControlAuthorityWebCheckService(
                registry={
                    DU_AUTHORITY_CODE: ControlAuthorityWebAdapterRegistration(
                        info=get_web_adapter_info(DU_AUTHORITY_CODE),
                        fetch=fetch,
                    )
                },
                snapshot_service=_FakeSnapshots(),
                clock=lambda: _FIXED_AT,
                compare=compare,
            ).check_authority_web(DU_AUTHORITY_CODE)
        self.assertEqual(ctx.exception.code, WEB_DIFF_ERROR_INCOMPLETE)
        self.assertFalse(state["called"])


class StateSupervisionAuthorityWebCoverageKhsRegression9a1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home_dir = Path(tempfile.mkdtemp(prefix="state-supervision-web-coverage-9a1-"))
        cls._home = patch.object(Path, "home", return_value=cls._home_dir)
        cls._home.start()
        import core.services.storage_service as storage_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        import core.database.session as session_module

        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        from core.database.database_initializer import initialize_database

        initialize_database()
        cls.storage = storage_module
        cls.session_module = session_module
        cls.catalog = control_authority_catalog_service
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def _dump(self):
        db = self.storage.storage_service.database_path
        conn = sqlite3.connect(str(db))
        try:
            return (
                conn.execute(
                    "SELECT id, code, origin, active, last_checked_at, user_edited_at "
                    "FROM control_authorities ORDER BY id"
                ).fetchall(),
                conn.execute(
                    "SELECT id, external_key, office_kind, origin, active, "
                    "last_checked_at, user_edited_at FROM control_authority_offices ORDER BY id"
                ).fetchall(),
            )
        finally:
            conn.close()

    def test_01_teplice_territorial_is_not_offered_for_deactivation(self) -> None:
        from moduly.statni_dozor.ui.control_authority_web_preview_dialog import (
            ControlAuthorityWebPreviewDialog,
        )

        authority = self.catalog.get_authority_by_code(KHS_AUTHORITY_CODE)
        self.assertIsNotNone(authority)
        teplce = self.catalog.get_office_by_external_key(_TEPLICE_KEY)
        self.assertIsNotNone(teplce)
        assert teplce is not None
        self.assertEqual(teplce.name, _TEPLICE_NAME)
        self.assertEqual(teplce.office_kind, OFFICE_KIND_TERRITORIAL)
        before = self._dump()
        html = _FIXTURE.read_text(encoding="utf-8")

        def fake_get(url: str) -> ControlAuthorityHttpResponse:
            self.assertEqual(url, KHS_OFFICES_SOURCE_URL)
            return ControlAuthorityHttpResponse(
                status_code=200,
                body=html.encode("utf-8"),
                content_type="text/html",
                final_url=url,
            )

        result = ControlAuthorityWebCheckService(
            http_get=fake_get,
            clock=lambda: _FIXED_AT,
        ).check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(result.diffs), 14)
        self.assertEqual(
            frozenset(item.external_key for item in result.diffs),
            frozenset(KHS_OFFICE_EXTERNAL_KEYS),
        )
        self.assertNotIn(_TEPLICE_KEY, {item.external_key for item in result.diffs})
        self.assertEqual(_missing_statuses(result.diff_result), ())
        dialog = ControlAuthorityWebPreviewDialog(None, result)
        texts = []
        for index in range(dialog.tree.topLevelItemCount()):
            item = dialog.tree.topLevelItem(index)
            texts.append(item.text(1))
        self.assertTrue(texts)
        self.assertFalse(any("Teplice" in text for text in texts))
        self.assertNotIn(_TEPLICE_NAME, texts)
        headers = [dialog.tree.headerItem().text(index) for index in range(dialog.tree.columnCount())]
        self.assertNotIn("coverage_id", headers)
        self.assertNotIn(WEB_COVERAGE_ID_KHS_REGIONAL, " ".join(headers))
        dialog.close()
        with self.assertRaises(ControlAuthorityWebApplyError) as ctx:
            apply_authority_web_changes(
                result,
                [
                    ControlAuthorityOfficeWebApplySelection(
                        external_key=_TEPLICE_KEY,
                        local_id=int(teplce.id),
                        action=WEB_APPLY_ACTION_DEACTIVATE,
                    )
                ],
            )
        self.assertEqual(ctx.exception.code, WEB_APPLY_ERROR_SELECTION)
        self.assertEqual(self._dump(), before)
        still = self.catalog.get_office(int(teplce.id))
        self.assertIsNotNone(still)
        self.assertTrue(still.active)
        self.assertEqual(still.external_key, _TEPLICE_KEY)
        self.assertEqual(still.office_kind, OFFICE_KIND_TERRITORIAL)

    def test_02_unknown_kind_warning_uses_existing_section(self) -> None:
        from moduly.statni_dozor.ui.control_authority_web_preview_dialog import (
            ControlAuthorityWebPreviewDialog,
        )

        warning = unknown_office_kind_warning("KHS bez druhu")
        info = get_web_adapter_info(DU_AUTHORITY_CODE)
        local = _local(
            office_id=11,
            authority_code=DU_AUTHORITY_CODE,
            key="du:praha",
            office_kind=OFFICE_KIND_HEADQUARTERS,
        )
        remote = _remote(
            authority_code=DU_AUTHORITY_CODE,
            key="du:praha",
            name="Drážní úřad Praha",
            office_kind=OFFICE_KIND_HEADQUARTERS,
        )
        diff = ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_CHANGED,
            authority_code=DU_AUTHORITY_CODE,
            external_key="du:praha",
            local_id=local.id,
            local=local,
            remote=remote,
            field_changes=(ControlAuthorityOfficeFieldChange("name", "A", "B"),),
            recommended_action=WEB_DIFF_ACTION_UPDATE,
            requires_manual_review=False,
            reason="",
        )
        dialog = ControlAuthorityWebPreviewDialog(
            None,
            ControlAuthorityWebCheckResult(
                authority_code=DU_AUTHORITY_CODE,
                adapter_info=info,
                fetched_at=_FIXED_AT,
                source_url=info.source_url,
                remote_records=(remote,),
                diffs=(diff,),
                status_counts=(),
                warnings=(warning,),
            ),
        )
        self.assertEqual(dialog.warnings_box.title(), WEB_CHECK_UI_WARNINGS_TITLE)
        self.assertFalse(dialog.warnings_box.isHidden())
        self.assertEqual(dialog.warnings_label.text(), warning)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
