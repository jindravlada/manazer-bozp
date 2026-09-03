"""STATE-SUPERVISION-AUTHORITY-WEB-COVERAGE-NAMESPACE-9A4: prefixy external_key."""

from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from moduly.statni_dozor.constants import (
    AUTHORITY_CATALOG_SEED_RELATIVE_PATH,
    AUTHORITY_ORIGIN_BUNDLED,
    AUTHORITY_ORIGIN_MANUAL,
    DU_AUTHORITY_CODE,
    KHS_AUTHORITY_CODE,
    KHS_OFFICES_SOURCE_URL,
    OFFICE_KIND_REGIONAL,
    OFFICE_KIND_TERRITORIAL,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ERROR_SELECTION,
    WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL,
    WEB_CHECK_COVERAGE_PREFIX_MESSAGE,
    WEB_CHECK_ERROR_COVERAGE_PREFIX,
    WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE,
    WEB_COVERAGE_ID_KHS_REGIONAL,
    WEB_COVERAGE_KEY_OUTSIDE_PREFIX_MESSAGE,
    WEB_COVERAGE_PREFIX_AUTHORITY_MESSAGE,
    WEB_COVERAGE_PREFIX_INVALID_MESSAGE,
    WEB_DIFF_ACTION_DEACTIVATE,
    WEB_DIFF_STATUS_IDENTITY_CONFLICT,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
)
from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityOfficeWebApplySelection,
    ControlAuthorityWebApplyError,
    apply_authority_web_changes,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    DEFAULT_WEB_ADAPTER_REGISTRY,
    ControlAuthorityWebAdapterInfo,
    ControlAuthorityWebAdapterRegistration,
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    ControlAuthorityWebCheckService,
    get_web_adapter_info,
    get_web_adapter_info_by_coverage,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverage,
    ControlAuthorityWebCoverageError,
    all_web_coverages,
    assert_records_match_coverage,
    khs_web_coverage,
    local_key_in_coverage_namespace,
    unknown_office_kind_warning,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebFetchResult,
)

_REPO = Path(__file__).resolve().parents[1]
_SEED = _REPO / AUTHORITY_CATALOG_SEED_RELATIVE_PATH
_FIXED_AT = datetime(2026, 9, 3, 12, 46, 0)
_COVERAGE_ID = "khs-territorial-usti"
_PREFIX = "khs:ustecky-kraj:"
_USTI_KEYS = (
    "khs:ustecky-kraj:decin",
    "khs:ustecky-kraj:chomutov",
    "khs:ustecky-kraj:litomerice",
    "khs:ustecky-kraj:louny",
    "khs:ustecky-kraj:most",
    "khs:ustecky-kraj:teplice",
)
_TEPLICE_KEY = "khs:ustecky-kraj:teplice"
_SVITAVY_KEY = "khs:pardubicky-kraj:svitavy"
_STARE_KEY = "khs:ustecky-kraj:stare"
_REGIONAL_USTI = "khs:ustecky-kraj"
_TEPLICE_NAME = "KHS Ústeckého kraje – Územní pracoviště Teplice"


def _usti_coverage(**overrides) -> ControlAuthorityWebCoverage:
    values = dict(
        coverage_id=_COVERAGE_ID,
        authority_code=KHS_AUTHORITY_CODE,
        covered_office_kinds=frozenset({OFFICE_KIND_TERRITORIAL}),
        covered_external_key_prefixes=frozenset({_PREFIX}),
        expected_external_keys=frozenset(_USTI_KEYS),
    )
    values.update(overrides)
    return ControlAuthorityWebCoverage(**values)


def _usti_info(coverage: ControlAuthorityWebCoverage | None = None):
    used = coverage or _usti_coverage()
    return ControlAuthorityWebAdapterInfo(
        authority_code=KHS_AUTHORITY_CODE,
        display_name="Krajské hygienické stanice",
        source_name="KHS Ústeckého kraje – územní pracoviště",
        source_url="https://khsusti.cz/",
        coverage=used,
        is_primary=False,
        display_order=41,
        coverage_label="Územní pracoviště Ústeckého kraje",
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


def _remote(
    *,
    key: str,
    name: str | None = None,
    office_kind: str | None = OFFICE_KIND_TERRITORIAL,
    address: str | None = "Ulice 1",
):
    return ControlAuthorityOfficeWebRecord(
        authority_code=KHS_AUTHORITY_CODE,
        external_key=key,
        name=name or f"Web {key}",
        address=address,
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=office_kind,
        source_url="https://example.gov.cz/",
        observed_fields=frozenset({"name", "source_url"}),
    )


def _local(
    *,
    office_id: int,
    key: str | None,
    office_kind: str | None = OFFICE_KIND_TERRITORIAL,
    name: str | None = None,
    origin: str = AUTHORITY_ORIGIN_BUNDLED,
    authority_code: str = KHS_AUTHORITY_CODE,
    address: str | None = "Ulice 1",
):
    return ControlAuthorityOfficeCatalogSnapshot(
        id=office_id,
        authority_id=1,
        authority_code=authority_code,
        external_key=key,
        name=name or f"Místní {key or office_id}",
        address=address,
        phone=None,
        email=None,
        website=None,
        territorial_scope=None,
        office_kind=office_kind,
        source_url=None,
        active=True,
        origin=origin,
        user_edited_at=None,
        last_checked_at=None,
    )


def _fetch(records, *, is_complete: bool = True):
    return ControlAuthorityWebFetchResult(
        authority_code=KHS_AUTHORITY_CODE,
        source_url="https://example.gov.cz/",
        fetched_at=_FIXED_AT,
        records=tuple(records),
        is_complete=is_complete,
    )


def _usti_remotes(keys=_USTI_KEYS):
    return tuple(_remote(key=key) for key in keys)


def _usti_locals(keys=_USTI_KEYS, *, start: int = 1):
    return tuple(
        _local(office_id=index, key=key, office_kind=OFFICE_KIND_TERRITORIAL)
        for index, key in enumerate(keys, start=start)
    )


def _diff(coverage=None, remotes=None, snapshots=None):
    used = coverage or _usti_coverage()
    return diff_control_authority_offices(
        _fetch(remotes if remotes is not None else _usti_remotes()),
        snapshots if snapshots is not None else _usti_locals(),
        used,
    )


def _missing_keys(result) -> frozenset[str]:
    items = getattr(result, "items", None)
    if items is None:
        items = result.diffs
    return frozenset(
        item.external_key
        for item in items
        if item.status
        in {WEB_DIFF_STATUS_MISSING_REMOTE, WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE}
    )


def _seed_khs_snapshots() -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
    payload = json.loads(_SEED.read_text(encoding="utf-8"))
    authority = next(item for item in payload["authorities"] if item["code"] == "khs")
    snapshots = []
    for index, office in enumerate(authority["offices"], start=1):
        snapshots.append(
            ControlAuthorityOfficeCatalogSnapshot(
                id=index,
                authority_id=100,
                authority_code=KHS_AUTHORITY_CODE,
                external_key=office.get("external_key"),
                name=office["name"],
                address=office.get("address"),
                phone=office.get("phone"),
                email=office.get("email"),
                website=office.get("website"),
                territorial_scope=office.get("territorial_scope"),
                office_kind=office.get("office_kind"),
                source_url=office.get("source_url"),
                active=True,
                origin=office.get("origin", AUTHORITY_ORIGIN_BUNDLED),
                user_edited_at=None,
                last_checked_at=None,
            )
        )
    return tuple(snapshots)


def _territorial_keys(snapshots) -> tuple[str, ...]:
    return tuple(
        item.external_key
        for item in snapshots
        if item.office_kind == OFFICE_KIND_TERRITORIAL and item.external_key
    )


class _FakeSnapshots:
    def __init__(self, snapshots=()):
        self.snapshots = tuple(snapshots)
        self.calls: list[str] = []

    def load_office_snapshots(self, authority_code: str):
        self.calls.append(authority_code)
        return self.snapshots


class _SpyFetch:
    def __init__(self, result=None):
        self.calls: list[tuple] = []
        self.result = result

    def __call__(self, *, http_get=None, clock=None):
        self.calls.append((http_get, clock))
        return self.result


class StateSupervisionAuthorityWebCoverageNamespaceDto9a4TestCase(unittest.TestCase):
    def test_01_existing_coverages_keep_empty_prefixes(self) -> None:
        found = {item.coverage_id: item for item in all_web_coverages()}
        self.assertEqual(len(found), 5)
        for item in found.values():
            self.assertEqual(item.covered_external_key_prefixes, frozenset())
            info = get_web_adapter_info(item.authority_code)
            self.assertEqual(info.coverage.covered_external_key_prefixes, frozenset())
            looked = get_web_adapter_info_by_coverage(item.coverage_id)
            self.assertEqual(looked.coverage.covered_external_key_prefixes, frozenset())
            self.assertEqual(info.coverage, item)
        self.assertNotIn(_COVERAGE_ID, DEFAULT_WEB_ADAPTER_REGISTRY)
        with self.assertRaises(ControlAuthorityWebCheckError) as ctx:
            get_web_adapter_info_by_coverage(_COVERAGE_ID)
        self.assertEqual(ctx.exception.code, WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE)

    def test_11_expected_key_outside_prefix_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _usti_coverage(
                expected_external_keys=frozenset({*_USTI_KEYS, _SVITAVY_KEY})
            )
        self.assertEqual(str(ctx.exception), WEB_COVERAGE_KEY_OUTSIDE_PREFIX_MESSAGE)

    def test_12_prefix_without_trailing_colon_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _usti_coverage(covered_external_key_prefixes=frozenset({"khs:ustecky-kraj"}))
        self.assertEqual(str(ctx.exception), WEB_COVERAGE_PREFIX_INVALID_MESSAGE)
        with self.assertRaises(ValueError) as upper:
            _usti_coverage(
                covered_external_key_prefixes=frozenset({"KHS:ustecky-kraj:"})
            )
        self.assertEqual(str(upper.exception), WEB_COVERAGE_PREFIX_INVALID_MESSAGE)
        with self.assertRaises(ValueError) as padded:
            _usti_coverage(
                covered_external_key_prefixes=frozenset({" khs:ustecky-kraj:"})
            )
        self.assertEqual(str(padded.exception), WEB_COVERAGE_PREFIX_INVALID_MESSAGE)

    def test_13_prefix_of_another_authority_is_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _usti_coverage(
                covered_external_key_prefixes=frozenset({"hzs:ustecky-kraj:"})
            )
        self.assertEqual(str(ctx.exception), WEB_COVERAGE_PREFIX_AUTHORITY_MESSAGE)

    def test_prefix_helpers_use_colon_boundary(self) -> None:
        coverage = _usti_coverage()
        self.assertTrue(local_key_in_coverage_namespace(_TEPLICE_KEY, coverage))
        self.assertTrue(local_key_in_coverage_namespace(_STARE_KEY, coverage))
        self.assertFalse(local_key_in_coverage_namespace(_SVITAVY_KEY, coverage))
        self.assertFalse(local_key_in_coverage_namespace(_REGIONAL_USTI, coverage))
        self.assertTrue(local_key_in_coverage_namespace(_TEPLICE_KEY, khs_web_coverage()))


class StateSupervisionAuthorityWebCoverageNamespaceDiff9a4TestCase(unittest.TestCase):
    def test_01_usti_coverage_compares_six_territorial_offices(self) -> None:
        result = _diff()
        self.assertEqual(frozenset(item.external_key for item in result.items), frozenset(_USTI_KEYS))
        self.assertEqual(_missing_keys(result), frozenset())
        self.assertEqual(result.warnings, ())

    def test_02_missing_teplice_remote_is_missing_remote(self) -> None:
        remotes = _usti_remotes(key for key in _USTI_KEYS if key != _TEPLICE_KEY)
        result = _diff(remotes=remotes)
        self.assertEqual(_missing_keys(result), frozenset({_TEPLICE_KEY}))
        missing = next(item for item in result.items if item.external_key == _TEPLICE_KEY)
        self.assertEqual(missing.status, WEB_DIFF_STATUS_MISSING_REMOTE)

    def test_03_protected_teplice_missing_remote_is_protected(self) -> None:
        snapshots = tuple(
            _local(
                office_id=index,
                key=key,
                origin=AUTHORITY_ORIGIN_MANUAL if key == _TEPLICE_KEY else AUTHORITY_ORIGIN_BUNDLED,
            )
            for index, key in enumerate(_USTI_KEYS, start=1)
        )
        remotes = _usti_remotes(key for key in _USTI_KEYS if key != _TEPLICE_KEY)
        result = _diff(remotes=remotes, snapshots=snapshots)
        self.assertEqual(_missing_keys(result), frozenset({_TEPLICE_KEY}))
        missing = next(item for item in result.items if item.external_key == _TEPLICE_KEY)
        self.assertEqual(missing.status, WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE)

    def test_04_svitavy_is_not_in_usti_diff(self) -> None:
        snapshots = _usti_locals() + (
            _local(office_id=99, key=_SVITAVY_KEY, office_kind=OFFICE_KIND_TERRITORIAL),
        )
        remotes = _usti_remotes(key for key in _USTI_KEYS if key != _TEPLICE_KEY)
        result = _diff(remotes=remotes, snapshots=snapshots)
        keys = {item.external_key for item in result.items}
        self.assertNotIn(_SVITAVY_KEY, keys)
        self.assertIn(_TEPLICE_KEY, keys)

    def test_05_other_territorial_offices_are_not_missing(self) -> None:
        snapshots = _seed_khs_snapshots()
        territorial = _territorial_keys(snapshots)
        self.assertEqual(len(territorial), 48)
        other = tuple(key for key in territorial if not key.startswith(_PREFIX))
        self.assertEqual(len(other), 42)
        result = _diff(snapshots=snapshots)
        keys = {item.external_key for item in result.items}
        self.assertEqual(keys, frozenset(_USTI_KEYS))
        self.assertEqual(_missing_keys(result), frozenset())
        for key in other:
            self.assertNotIn(key, keys)

    def test_06_old_usti_office_is_missing(self) -> None:
        snapshots = _usti_locals() + (
            _local(office_id=99, key=_STARE_KEY, office_kind=OFFICE_KIND_TERRITORIAL),
        )
        result = _diff(snapshots=snapshots)
        self.assertEqual(_missing_keys(result), frozenset({_STARE_KEY}))

    def test_07_regional_usti_is_outside_territorial_namespace(self) -> None:
        snapshots = _usti_locals() + (
            _local(
                office_id=99,
                key=_REGIONAL_USTI,
                office_kind=OFFICE_KIND_REGIONAL,
                name="KHS Ústeckého kraje",
            ),
        )
        result = _diff(snapshots=snapshots)
        keys = {item.external_key for item in result.items}
        self.assertNotIn(_REGIONAL_USTI, keys)
        self.assertEqual(_missing_keys(result), frozenset())

    def test_08_manual_without_key_is_not_missing(self) -> None:
        snapshots = _usti_locals() + (
            _local(
                office_id=99,
                key=None,
                name="Ruční Ústí",
                office_kind=OFFICE_KIND_TERRITORIAL,
                origin=AUTHORITY_ORIGIN_MANUAL,
            ),
        )
        result = _diff(snapshots=snapshots)
        self.assertEqual(_missing_keys(result), frozenset())
        self.assertNotIn(
            "Ruční Ústí",
            [item.local.name for item in result.items if item.local],
        )

    def test_09_unknown_kind_in_prefix_warns_and_skips(self) -> None:
        unknown = _local(
            office_id=99,
            key="khs:ustecky-kraj:neznamy",
            name="KHS bez druhu",
            office_kind=None,
        )
        foreign_unknown = _local(
            office_id=100,
            key="khs:pardubicky-kraj:neznamy",
            name="KHS cizí bez druhu",
            office_kind="krajska",
        )
        result = _diff(snapshots=_usti_locals() + (unknown, foreign_unknown))
        self.assertEqual(_missing_keys(result), frozenset())
        self.assertEqual(result.warnings, (unknown_office_kind_warning("KHS bez druhu"),))
        self.assertNotIn(
            unknown_office_kind_warning("KHS cizí bez druhu"),
            result.warnings,
        )

    def test_10_remote_key_outside_prefix_is_rejected_even_with_same_count(self) -> None:
        keys = tuple(key if key != _TEPLICE_KEY else _SVITAVY_KEY for key in _USTI_KEYS)
        records = _usti_remotes(keys)
        coverage = _usti_coverage()
        with self.assertRaises(ControlAuthorityWebCoverageError) as contract:
            assert_records_match_coverage(
                records,
                coverage,
                fetch_authority_code=KHS_AUTHORITY_CODE,
            )
        self.assertEqual(contract.exception.code, WEB_CHECK_ERROR_COVERAGE_PREFIX)
        self.assertEqual(str(contract.exception), WEB_CHECK_COVERAGE_PREFIX_MESSAGE)
        with self.assertRaises(ControlAuthorityWebCoverageError) as compared:
            diff_control_authority_offices(_fetch(records), _usti_locals(), coverage)
        self.assertEqual(compared.exception.code, WEB_CHECK_ERROR_COVERAGE_PREFIX)

    def test_14_same_city_in_another_prefix_is_not_merged(self) -> None:
        teplice_address = "Jiřího Wolkera 1342/4, 415 01 Teplice"
        teplice_remote = _remote(
            key=_TEPLICE_KEY,
            name=_TEPLICE_NAME,
            address=teplice_address,
        )
        remotes = tuple(
            teplice_remote if key == _TEPLICE_KEY else _remote(key=key)
            for key in _USTI_KEYS
        )
        locals_without_teplice = _usti_locals(
            key for key in _USTI_KEYS if key != _TEPLICE_KEY
        )
        svitavy = _local(
            office_id=99,
            key=_SVITAVY_KEY,
            office_kind=OFFICE_KIND_TERRITORIAL,
            name=_TEPLICE_NAME,
            address=teplice_address,
        )
        result = _diff(remotes=remotes, snapshots=locals_without_teplice + (svitavy,))
        duplicate = next(
            item for item in result.items if item.status == WEB_DIFF_STATUS_POSSIBLE_DUPLICATE
        )
        self.assertEqual(duplicate.external_key, _TEPLICE_KEY)
        self.assertEqual(duplicate.local.external_key, _SVITAVY_KEY)
        self.assertEqual(svitavy.external_key, _SVITAVY_KEY)
        self.assertNotIn(_SVITAVY_KEY, _missing_keys(result))
        paired = _diff(
            remotes=remotes,
            snapshots=_usti_locals()
            + (
                _local(
                    office_id=99,
                    key=_SVITAVY_KEY,
                    office_kind=OFFICE_KIND_TERRITORIAL,
                    name=_TEPLICE_NAME,
                    address=teplice_address,
                ),
            ),
        )
        teplice = next(item for item in paired.items if item.external_key == _TEPLICE_KEY)
        self.assertNotEqual(teplice.status, WEB_DIFF_STATUS_POSSIBLE_DUPLICATE)
        self.assertEqual(teplice.local.external_key, _TEPLICE_KEY)
        self.assertNotIn(_SVITAVY_KEY, {item.external_key for item in paired.items})

    def test_exact_key_identity_conflict_stays_an_error(self) -> None:
        foreign = _local(
            office_id=50,
            key=_TEPLICE_KEY,
            authority_code=DU_AUTHORITY_CODE,
            office_kind=OFFICE_KIND_TERRITORIAL,
        )
        snapshots = _usti_locals(key for key in _USTI_KEYS if key != _TEPLICE_KEY) + (
            foreign,
        )
        result = _diff(snapshots=snapshots)
        conflict = next(item for item in result.items if item.external_key == _TEPLICE_KEY)
        self.assertEqual(conflict.status, WEB_DIFF_STATUS_IDENTITY_CONFLICT)


class StateSupervisionAuthorityWebCoverageNamespaceApply9a4TestCase(unittest.TestCase):
    def _check(self, *, diffs=None, remotes=None, coverage=None):
        used = coverage or _usti_coverage()
        records = remotes if remotes is not None else _usti_remotes()
        fetch = _fetch(records)
        info = _usti_info(used)
        if diffs is None:
            diff = diff_control_authority_offices(fetch, _usti_locals(), used)
            items = diff.items
            counts = diff.status_counts
            warnings = diff.warnings
            diff_result = diff
        else:
            items = tuple(diffs)
            counts = ()
            warnings = ()
            diff_result = None
        return ControlAuthorityWebCheckResult(
            authority_code=KHS_AUTHORITY_CODE,
            adapter_info=info,
            fetched_at=_FIXED_AT,
            source_url="https://example.gov.cz/",
            remote_records=records,
            diffs=items,
            status_counts=counts,
            warnings=warnings,
            has_actionable_changes=True,
            has_conflicts=False,
            fetch_result=fetch,
            diff_result=diff_result,
            coverage=used,
        )

    def test_15_apply_rejects_selection_outside_coverage(self) -> None:
        svitavy = _local(office_id=99, key=_SVITAVY_KEY)
        check = self._check()
        info = check.adapter_info
        with patch(
            "moduly.statni_dozor.sluzby.control_authority_web.apply.get_web_adapter_info_by_coverage",
            return_value=info,
        ):
            with self.assertRaises(ControlAuthorityWebApplyError) as missing:
                apply_authority_web_changes(
                    check,
                    [
                        ControlAuthorityOfficeWebApplySelection(
                            external_key=_SVITAVY_KEY,
                            local_id=int(svitavy.id),
                            action=WEB_APPLY_ACTION_DEACTIVATE,
                        )
                    ],
                )
        self.assertEqual(missing.exception.code, WEB_APPLY_ERROR_SELECTION)

        tampered_diff = ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_MISSING_REMOTE,
            authority_code=KHS_AUTHORITY_CODE,
            external_key=_SVITAVY_KEY,
            local_id=svitavy.id,
            local=svitavy,
            remote=None,
            field_changes=(),
            recommended_action=WEB_DIFF_ACTION_DEACTIVATE,
            requires_manual_review=True,
            reason="injected",
        )
        tampered = self._check(diffs=check.diffs + (tampered_diff,))
        with patch(
            "moduly.statni_dozor.sluzby.control_authority_web.apply.get_web_adapter_info_by_coverage",
            return_value=info,
        ):
            with self.assertRaises(ControlAuthorityWebApplyError) as injected:
                apply_authority_web_changes(
                    tampered,
                    [
                        ControlAuthorityOfficeWebApplySelection(
                            external_key=_SVITAVY_KEY,
                            local_id=int(svitavy.id),
                            action=WEB_APPLY_ACTION_DEACTIVATE,
                        )
                    ],
                )
        self.assertEqual(injected.exception.code, WEB_APPLY_ERROR_SELECTION)


class StateSupervisionAuthorityWebCoverageNamespaceIntegration9a4TestCase(unittest.TestCase):
    def test_secondary_usti_ignores_other_territorial_and_skips_primary(self) -> None:
        snapshots = _seed_khs_snapshots()
        territorial = _territorial_keys(snapshots)
        self.assertEqual(len(territorial), 48)
        other = [key for key in territorial if not key.startswith(_PREFIX)]
        self.assertEqual(len(other), 42)
        coverage = _usti_coverage()
        remotes = []
        for snapshot in snapshots:
            if snapshot.external_key in coverage.expected_external_keys:
                remotes.append(
                    _remote(key=snapshot.external_key, name=snapshot.name)
                )
        self.assertEqual(len(remotes), 6)
        primary = _SpyFetch(_fetch(_usti_remotes()))
        secondary = _SpyFetch(_fetch(remotes))
        seed_before = _SEED.read_bytes()
        service = ControlAuthorityWebCheckService(
            registry=(
                ControlAuthorityWebAdapterRegistration(
                    info=_primary_khs_info(),
                    fetch=primary,
                ),
                ControlAuthorityWebAdapterRegistration(
                    info=_usti_info(coverage),
                    fetch=secondary,
                ),
            ),
            snapshot_service=_FakeSnapshots(snapshots),
            clock=lambda: _FIXED_AT,
        )
        result = service.check_authority_web_coverage(_COVERAGE_ID)
        self.assertEqual(result.coverage.coverage_id, _COVERAGE_ID)
        self.assertEqual(
            result.coverage.covered_external_key_prefixes,
            frozenset({_PREFIX}),
        )
        self.assertEqual(result.adapter_info.coverage.covered_external_key_prefixes, frozenset({_PREFIX}))
        self.assertEqual(len(secondary.calls), 1)
        self.assertEqual(primary.calls, [])
        keys = {item.external_key for item in result.diffs}
        self.assertEqual(keys, frozenset(_USTI_KEYS))
        self.assertEqual(_missing_keys(result), frozenset())
        for key in other:
            self.assertNotIn(key, keys)
        self.assertNotIn(_REGIONAL_USTI, keys)
        self.assertEqual(get_web_adapter_info(KHS_AUTHORITY_CODE).coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(_SEED.read_bytes(), seed_before)
        self.assertNotIn(_COVERAGE_ID, DEFAULT_WEB_ADAPTER_REGISTRY)

    def test_check_authority_web_still_uses_primary(self) -> None:
        coverage = _usti_coverage()
        primary = _SpyFetch(
            ControlAuthorityWebFetchResult(
                authority_code=KHS_AUTHORITY_CODE,
                source_url=KHS_OFFICES_SOURCE_URL,
                fetched_at=_FIXED_AT,
                records=tuple(
                    _remote(key=key, office_kind=OFFICE_KIND_REGIONAL)
                    for key in khs_web_coverage().expected_external_keys
                ),
                is_complete=True,
            )
        )
        secondary = _SpyFetch(_fetch(_usti_remotes()))
        service = ControlAuthorityWebCheckService(
            registry=(
                ControlAuthorityWebAdapterRegistration(
                    info=_primary_khs_info(),
                    fetch=primary,
                ),
                ControlAuthorityWebAdapterRegistration(
                    info=_usti_info(coverage),
                    fetch=secondary,
                ),
            ),
            snapshot_service=_FakeSnapshots(_seed_khs_snapshots()),
            clock=lambda: _FIXED_AT,
        )
        result = service.check_authority_web(KHS_AUTHORITY_CODE)
        self.assertEqual(result.coverage.coverage_id, WEB_COVERAGE_ID_KHS_REGIONAL)
        self.assertEqual(len(primary.calls), 1)
        self.assertEqual(secondary.calls, [])
        self.assertEqual(
            frozenset(item.external_key for item in result.remote_records),
            khs_web_coverage().expected_external_keys,
        )
