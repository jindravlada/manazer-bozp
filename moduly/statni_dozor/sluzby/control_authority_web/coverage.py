"""Explicitní rozsah pokrytí webového adapteru kontrolního orgánu."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from moduly.statni_dozor.constants import (
    CBU_AUTHORITY_CODE,
    CBU_OFFICE_EXTERNAL_KEYS,
    DU_AUTHORITY_CODE,
    DU_OFFICE_EXTERNAL_KEYS,
    HZS_AUTHORITY_CODE,
    HZS_OFFICE_EXTERNAL_KEYS,
    KHS_AUTHORITY_CODE,
    KHS_OFFICE_EXTERNAL_KEYS,
    OFFICE_KIND_HEADQUARTERS,
    OFFICE_KIND_REGIONAL,
    OFFICE_KIND_TERRITORIAL,
    OFFICE_KINDS,
    SUIP_AUTHORITY_CODE,
    SUIP_OFFICE_EXTERNAL_KEYS,
    WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
    WEB_CHECK_COVERAGE_KIND_MESSAGE,
    WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
    WEB_CHECK_ERROR_COVERAGE_KIND,
    WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    WEB_CHECK_UNEXPECTED_COUNT_MESSAGE,
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
    WEB_DIFF_DUPLICATE_REMOTE_MESSAGE,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_MISSING_KEY_MESSAGE,
)


class ControlAuthorityWebCoverageError(ValueError):
    """Doménová chyba rozsahu nebo kontraktu webového adapteru."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


def _coverage_error(code: str, message: str) -> ControlAuthorityWebCoverageError:
    return ControlAuthorityWebCoverageError(message, code=code)


def _require_coverage_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(WEB_COVERAGE_ID_REQUIRED_MESSAGE)
    return text


def _require_authority_code(value: object) -> str:
    text = str(value or "").strip()
    if not text or text != text.casefold():
        raise ValueError(WEB_COVERAGE_AUTHORITY_CODE_INVALID_MESSAGE)
    return text


def _require_office_kinds(values: Iterable[object]) -> frozenset[str]:
    kinds = frozenset(str(item or "").strip() for item in values)
    if not kinds or any(not item for item in kinds):
        raise ValueError(WEB_COVERAGE_KINDS_REQUIRED_MESSAGE)
    unknown = kinds - OFFICE_KINDS
    if unknown:
        raise ValueError(WEB_COVERAGE_KIND_UNKNOWN_MESSAGE)
    return kinds


def _key_belongs_to_authority(key: str, authority_code: str) -> bool:
    prefix = f"{authority_code}:"
    return key.startswith(prefix) and bool(key[len(prefix) :].strip())


def _require_external_keys(
    values: Iterable[object],
    *,
    authority_code: str,
) -> frozenset[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for raw in values:
        key = str(raw or "").strip()
        if not key:
            raise ValueError(WEB_COVERAGE_KEY_INVALID_MESSAGE)
        if key in seen:
            raise ValueError(WEB_COVERAGE_KEY_INVALID_MESSAGE)
        if not _key_belongs_to_authority(key, authority_code):
            raise ValueError(WEB_COVERAGE_KEY_AUTHORITY_MESSAGE)
        seen.add(key)
        keys.append(key)
    if not keys:
        raise ValueError(WEB_COVERAGE_KEYS_REQUIRED_MESSAGE)
    return frozenset(keys)


@dataclass(frozen=True)
class ControlAuthorityWebCoverage:
    """Neměnný rozsah jedné úplné webové kontroly."""

    coverage_id: str
    authority_code: str
    covered_office_kinds: frozenset[str]
    expected_external_keys: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "coverage_id", _require_coverage_id(self.coverage_id))
        authority_code = _require_authority_code(self.authority_code)
        object.__setattr__(self, "authority_code", authority_code)
        object.__setattr__(
            self,
            "covered_office_kinds",
            _require_office_kinds(self.covered_office_kinds),
        )
        object.__setattr__(
            self,
            "expected_external_keys",
            _require_external_keys(
                self.expected_external_keys,
                authority_code=authority_code,
            ),
        )

    @property
    def expected_office_count(self) -> int:
        return len(self.expected_external_keys)


def du_web_coverage() -> ControlAuthorityWebCoverage:
    return ControlAuthorityWebCoverage(
        coverage_id=WEB_COVERAGE_ID_DU_OFFICES,
        authority_code=DU_AUTHORITY_CODE,
        covered_office_kinds=frozenset(
            {OFFICE_KIND_HEADQUARTERS, OFFICE_KIND_TERRITORIAL}
        ),
        expected_external_keys=frozenset(DU_OFFICE_EXTERNAL_KEYS),
    )


def suip_web_coverage() -> ControlAuthorityWebCoverage:
    return ControlAuthorityWebCoverage(
        coverage_id=WEB_COVERAGE_ID_SUIP_REGIONAL,
        authority_code=SUIP_AUTHORITY_CODE,
        covered_office_kinds=frozenset({OFFICE_KIND_REGIONAL}),
        expected_external_keys=frozenset(SUIP_OFFICE_EXTERNAL_KEYS),
    )


def cbu_web_coverage() -> ControlAuthorityWebCoverage:
    return ControlAuthorityWebCoverage(
        coverage_id=WEB_COVERAGE_ID_CBU_REGIONAL,
        authority_code=CBU_AUTHORITY_CODE,
        covered_office_kinds=frozenset({OFFICE_KIND_TERRITORIAL}),
        expected_external_keys=frozenset(CBU_OFFICE_EXTERNAL_KEYS),
    )


def khs_web_coverage() -> ControlAuthorityWebCoverage:
    return ControlAuthorityWebCoverage(
        coverage_id=WEB_COVERAGE_ID_KHS_REGIONAL,
        authority_code=KHS_AUTHORITY_CODE,
        covered_office_kinds=frozenset({OFFICE_KIND_REGIONAL}),
        expected_external_keys=frozenset(KHS_OFFICE_EXTERNAL_KEYS),
    )


def hzs_web_coverage() -> ControlAuthorityWebCoverage:
    return ControlAuthorityWebCoverage(
        coverage_id=WEB_COVERAGE_ID_HZS_REGIONAL,
        authority_code=HZS_AUTHORITY_CODE,
        covered_office_kinds=frozenset({OFFICE_KIND_REGIONAL}),
        expected_external_keys=frozenset(HZS_OFFICE_EXTERNAL_KEYS),
    )


def all_web_coverages() -> tuple[ControlAuthorityWebCoverage, ...]:
    return (
        du_web_coverage(),
        suip_web_coverage(),
        cbu_web_coverage(),
        khs_web_coverage(),
        hzs_web_coverage(),
    )


def coverage_for_authority(authority_code: str) -> ControlAuthorityWebCoverage | None:
    code = str(authority_code or "").strip().casefold()
    if not code:
        return None
    mapping = {item.authority_code: item for item in all_web_coverages()}
    return mapping.get(code)


def normalized_office_kind(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text not in OFFICE_KINDS:
        return None
    return text


def unknown_office_kind_warning(name: object) -> str:
    label = str(name or "").strip() or "bez názvu"
    return WEB_COVERAGE_UNKNOWN_KIND_WARNING.format(name=label)


def local_kind_covered(
    office_kind: object,
    coverage: ControlAuthorityWebCoverage,
) -> bool:
    kind = normalized_office_kind(office_kind)
    if kind is None:
        return False
    return kind in coverage.covered_office_kinds


def local_kind_unknown(office_kind: object) -> bool:
    text = str(office_kind or "").strip()
    if not text:
        return True
    return text not in OFFICE_KINDS


def remote_external_keys(records: Sequence) -> frozenset[str]:
    return frozenset(str(record.external_key or "").strip() for record in records)


def assert_records_match_coverage(
    records: Sequence,
    coverage: ControlAuthorityWebCoverage,
    *,
    fetch_authority_code: str,
) -> None:
    """Ověří, že úplný remote výsledek přesně odpovídá deklarovanému rozsahu."""
    fetch_code = str(fetch_authority_code or "").strip()
    if fetch_code != coverage.authority_code:
        raise _coverage_error(
            WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
            WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
        )
    seen: set[str] = set()
    for record in records:
        if str(record.authority_code or "").strip() != coverage.authority_code:
            raise _coverage_error(
                WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
                WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
            )
        key = str(record.external_key or "").strip()
        if not key:
            raise _coverage_error(
                WEB_DIFF_ERROR_MISSING_KEY, WEB_DIFF_MISSING_KEY_MESSAGE
            )
        if key in seen:
            raise _coverage_error(
                WEB_DIFF_ERROR_DUPLICATE_REMOTE, WEB_DIFF_DUPLICATE_REMOTE_MESSAGE
            )
        seen.add(key)
        observed = frozenset(getattr(record, "observed_fields", ()) or ())
        if "office_kind" in observed:
            kind = str(record.office_kind or "").strip()
            if kind not in coverage.covered_office_kinds:
                raise _coverage_error(
                    WEB_CHECK_ERROR_COVERAGE_KIND,
                    WEB_CHECK_COVERAGE_KIND_MESSAGE,
                )
    if frozenset(seen) != coverage.expected_external_keys:
        raise _coverage_error(
            WEB_CHECK_ERROR_UNEXPECTED_COUNT,
            WEB_CHECK_UNEXPECTED_COUNT_MESSAGE,
        )
