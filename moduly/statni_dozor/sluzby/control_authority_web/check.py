"""Společná read-only webová kontrola katalogu kontrolních orgánů."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from urllib.parse import urlparse

from moduly.statni_dozor.constants import (
    CBU_AUTHORITY_CODE,
    CBU_OFFICES_SOURCE_URL,
    DU_AUTHORITY_CODE,
    DU_OFFICES_SOURCE_URL,
    HZS_AUTHORITY_CODE,
    HZS_OFFICES_SOURCE_URL,
    KHS_AUTHORITY_CODE,
    KHS_OFFICES_SOURCE_URL,
    SUIP_AUTHORITY_CODE,
    SUIP_HUB_SOURCE_URL,
    WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
    WEB_CHECK_CODE_REQUIRED_MESSAGE,
    WEB_CHECK_COVERAGE_LABEL_CBU_REGIONAL,
    WEB_CHECK_COVERAGE_LABEL_DU_OFFICES,
    WEB_CHECK_COVERAGE_LABEL_HZS_REGIONAL,
    WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL,
    WEB_CHECK_COVERAGE_LABEL_SUIP_REGIONAL,
    WEB_CHECK_DISPLAY_ORDER_INVALID_MESSAGE,
    WEB_CHECK_DUPLICATE_COVERAGE_MESSAGE,
    WEB_CHECK_DUPLICATE_PRIMARY_MESSAGE,
    WEB_CHECK_ERROR_ADAPTER,
    WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
    WEB_CHECK_ERROR_CODE_REQUIRED,
    WEB_CHECK_ERROR_COVERAGE_REQUIRED,
    WEB_CHECK_ERROR_UNSUPPORTED,
    WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE,
    WEB_CHECK_MISSING_PRIMARY_MESSAGE,
    WEB_CHECK_REGISTRY_COVERAGE_KEY_MESSAGE,
    WEB_CHECK_UNSUPPORTED_COVERAGE_MESSAGE,
    WEB_CHECK_UNSUPPORTED_MESSAGE,
    WEB_COVERAGE_ID_REQUIRED_MESSAGE,
    WEB_COVERAGE_KEYS_REQUIRED_MESSAGE,
    WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_INCOMPLETE_MESSAGE,
)
from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    ControlAuthorityCatalogSnapshotService,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import fetch_cbu_offices
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverage,
    ControlAuthorityWebCoverageError,
    assert_records_match_coverage,
    cbu_web_coverage,
    du_web_coverage,
    hzs_web_coverage,
    khs_web_coverage,
    suip_web_coverage,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff import (
    diff_control_authority_offices,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityWebDiffError,
    ControlAuthorityWebDiffResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.du_adapter import fetch_du_offices
from moduly.statni_dozor.sluzby.control_authority_web.http_client import (
    ControlAuthorityHttpClient,
    HttpGet,
)
from moduly.statni_dozor.sluzby.control_authority_web.hzs_adapter import fetch_hzs_offices
from moduly.statni_dozor.sluzby.control_authority_web.khs_adapter import fetch_khs_offices
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebAdapterError,
    ControlAuthorityWebFetchResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.suip_adapter import fetch_suip_offices

logger = logging.getLogger(__name__)

WebAdapterFetch = Callable[..., ControlAuthorityWebFetchResult]
SnapshotLoader = Callable[[str], tuple[ControlAuthorityOfficeCatalogSnapshot, ...]]
CompareFn = Callable[..., ControlAuthorityWebDiffResult]


@dataclass(frozen=True)
class ControlAuthorityWebAdapterInfo:
    """Veřejné metadata jednoho registrovaného webového adapteru."""

    authority_code: str
    display_name: str
    source_name: str
    source_url: str
    coverage: ControlAuthorityWebCoverage
    is_primary: bool = True
    display_order: int = 0
    coverage_label: str = ""
    expected_office_count: int = field(init=False)

    def __post_init__(self) -> None:
        coverage = self.coverage
        if coverage.authority_code != str(self.authority_code or "").strip():
            raise ValueError(WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE)
        try:
            order = int(self.display_order)
        except (TypeError, ValueError) as exc:
            raise ValueError(WEB_CHECK_DISPLAY_ORDER_INVALID_MESSAGE) from exc
        if order < 0:
            raise ValueError(WEB_CHECK_DISPLAY_ORDER_INVALID_MESSAGE)
        object.__setattr__(self, "display_order", order)
        object.__setattr__(self, "is_primary", bool(self.is_primary))
        label = str(self.coverage_label or "").strip() or str(self.display_name or "").strip()
        object.__setattr__(self, "coverage_label", label)
        object.__setattr__(
            self,
            "expected_office_count",
            int(coverage.expected_office_count),
        )


@dataclass(frozen=True)
class ControlAuthorityWebAdapterRegistration:
    """Vazba metadat adapteru na jeho fetch callable."""

    info: ControlAuthorityWebAdapterInfo
    fetch: WebAdapterFetch

    @property
    def is_primary(self) -> bool:
        return bool(self.info.is_primary)

    @property
    def coverage_id(self) -> str:
        return self.info.coverage.coverage_id


@dataclass(frozen=True)
class ControlAuthorityWebCheckResult:
    """Read-only výsledek webové kontroly jednoho kontrolního orgánu."""

    authority_code: str
    adapter_info: ControlAuthorityWebAdapterInfo
    fetched_at: datetime
    source_url: str
    remote_records: tuple[ControlAuthorityOfficeWebRecord, ...]
    diffs: tuple[ControlAuthorityOfficeDiff, ...]
    status_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...] = ()
    has_actionable_changes: bool = False
    has_conflicts: bool = False
    fetch_result: ControlAuthorityWebFetchResult | None = field(default=None)
    diff_result: ControlAuthorityWebDiffResult | None = field(default=None)
    coverage: ControlAuthorityWebCoverage | None = field(default=None)

    def __post_init__(self) -> None:
        object.__setattr__(self, "remote_records", tuple(self.remote_records))
        object.__setattr__(self, "diffs", tuple(self.diffs))
        object.__setattr__(self, "status_counts", tuple(self.status_counts))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        coverage = self.coverage
        if coverage is None:
            coverage = self.adapter_info.coverage
            object.__setattr__(self, "coverage", coverage)


class ControlAuthorityWebCheckError(ValueError):
    """Doménová chyba společné webové kontroly katalogu."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


def _check_error(code: str, message: str) -> ControlAuthorityWebCheckError:
    return ControlAuthorityWebCheckError(message, code=code)


def _https_source_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise _check_error(WEB_CHECK_ERROR_UNSUPPORTED, WEB_CHECK_CODE_REQUIRED_MESSAGE)
    return str(url).strip()


def build_web_adapter_registry(
    entries: Mapping[str, ControlAuthorityWebAdapterRegistration]
    | Sequence[ControlAuthorityWebAdapterRegistration],
) -> Mapping[str, ControlAuthorityWebAdapterRegistration]:
    """Sestaví registr klíčovaný unikátním coverage_id."""
    if isinstance(entries, Mapping):
        pairs: tuple[tuple[str | None, ControlAuthorityWebAdapterRegistration], ...] = tuple(
            (str(key), item) for key, item in entries.items()
        )
    else:
        pairs = tuple((None, item) for item in entries)

    mapping: dict[str, ControlAuthorityWebAdapterRegistration] = {}
    primary_by_authority: dict[str, ControlAuthorityWebAdapterRegistration] = {}
    authorities: set[str] = set()
    for provided_key, registration in pairs:
        if not isinstance(registration, ControlAuthorityWebAdapterRegistration):
            raise ValueError(WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE)
        info = registration.info
        coverage = info.coverage
        coverage_id = coverage.coverage_id
        if provided_key is not None and provided_key not in {
            coverage_id,
            info.authority_code,
        }:
            raise ValueError(WEB_CHECK_REGISTRY_COVERAGE_KEY_MESSAGE)
        if coverage_id in mapping:
            raise ValueError(WEB_CHECK_DUPLICATE_COVERAGE_MESSAGE)
        if not coverage.authority_code:
            raise ValueError(WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE)
        if not coverage.expected_external_keys:
            raise ValueError(WEB_COVERAGE_KEYS_REQUIRED_MESSAGE)
        authorities.add(info.authority_code)
        if info.is_primary:
            if info.authority_code in primary_by_authority:
                raise ValueError(WEB_CHECK_DUPLICATE_PRIMARY_MESSAGE)
            primary_by_authority[info.authority_code] = registration
        mapping[coverage_id] = registration

    missing_primary = authorities - set(primary_by_authority)
    if missing_primary:
        raise ValueError(WEB_CHECK_MISSING_PRIMARY_MESSAGE)
    return MappingProxyType(mapping)


def _default_registry() -> Mapping[str, ControlAuthorityWebAdapterRegistration]:
    registry = build_web_adapter_registry(
        (
            ControlAuthorityWebAdapterRegistration(
                info=ControlAuthorityWebAdapterInfo(
                    authority_code=DU_AUTHORITY_CODE,
                    display_name="Drážní úřad",
                    source_name="Kontakty Drážního úřadu",
                    source_url=_https_source_url(DU_OFFICES_SOURCE_URL),
                    coverage=du_web_coverage(),
                    is_primary=True,
                    display_order=10,
                    coverage_label=WEB_CHECK_COVERAGE_LABEL_DU_OFFICES,
                ),
                fetch=fetch_du_offices,
            ),
            ControlAuthorityWebAdapterRegistration(
                info=ControlAuthorityWebAdapterInfo(
                    authority_code=SUIP_AUTHORITY_CODE,
                    display_name="Státní úřad inspekce práce",
                    source_name="Kontakty oblastních inspektorátů práce",
                    source_url=_https_source_url(SUIP_HUB_SOURCE_URL),
                    coverage=suip_web_coverage(),
                    is_primary=True,
                    display_order=20,
                    coverage_label=WEB_CHECK_COVERAGE_LABEL_SUIP_REGIONAL,
                ),
                fetch=fetch_suip_offices,
            ),
            ControlAuthorityWebAdapterRegistration(
                info=ControlAuthorityWebAdapterInfo(
                    authority_code=CBU_AUTHORITY_CODE,
                    display_name="Český báňský úřad",
                    source_name="Obvodní báňské úřady",
                    source_url=_https_source_url(CBU_OFFICES_SOURCE_URL),
                    coverage=cbu_web_coverage(),
                    is_primary=True,
                    display_order=30,
                    coverage_label=WEB_CHECK_COVERAGE_LABEL_CBU_REGIONAL,
                ),
                fetch=fetch_cbu_offices,
            ),
            ControlAuthorityWebAdapterRegistration(
                info=ControlAuthorityWebAdapterInfo(
                    authority_code=KHS_AUTHORITY_CODE,
                    display_name="Krajské hygienické stanice",
                    source_name="Ministerstvo zdravotnictví – Krajské hygienické stanice",
                    source_url=_https_source_url(KHS_OFFICES_SOURCE_URL),
                    coverage=khs_web_coverage(),
                    is_primary=True,
                    display_order=40,
                    coverage_label=WEB_CHECK_COVERAGE_LABEL_KHS_REGIONAL,
                ),
                fetch=fetch_khs_offices,
            ),
            ControlAuthorityWebAdapterRegistration(
                info=ControlAuthorityWebAdapterInfo(
                    authority_code=HZS_AUTHORITY_CODE,
                    display_name="Hasičský záchranný sbor České republiky",
                    source_name="HZS krajů",
                    source_url=_https_source_url(HZS_OFFICES_SOURCE_URL),
                    coverage=hzs_web_coverage(),
                    is_primary=True,
                    display_order=50,
                    coverage_label=WEB_CHECK_COVERAGE_LABEL_HZS_REGIONAL,
                ),
                fetch=fetch_hzs_offices,
            ),
        )
    )
    primary_codes = tuple(
        item.info.authority_code for item in registry.values() if item.info.is_primary
    )
    if primary_codes != (
        DU_AUTHORITY_CODE,
        SUIP_AUTHORITY_CODE,
        CBU_AUTHORITY_CODE,
        KHS_AUTHORITY_CODE,
        HZS_AUTHORITY_CODE,
    ):
        raise RuntimeError("Registr webových adapterů nemá očekávané pořadí kódů.")
    return registry


DEFAULT_WEB_ADAPTER_REGISTRY = _default_registry()


def _unique_warnings(*groups: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for group in groups:
        for item in group:
            text = str(item)
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
    return tuple(ordered)


def _wrap_domain_error(exc: BaseException) -> ControlAuthorityWebCheckError:
    if isinstance(exc, ControlAuthorityWebCheckError):
        return exc
    if isinstance(exc, ControlAuthorityWebAdapterError):
        wrapped = _check_error(exc.code or WEB_CHECK_ERROR_ADAPTER, str(exc))
        wrapped.__cause__ = exc
        return wrapped
    if isinstance(exc, ControlAuthorityWebCoverageError):
        wrapped = _check_error(exc.code, str(exc))
        wrapped.__cause__ = exc
        return wrapped
    if isinstance(exc, ControlAuthorityWebDiffError):
        wrapped = _check_error(exc.code, str(exc))
        wrapped.__cause__ = exc
        return wrapped
    wrapped = _check_error(WEB_CHECK_ERROR_ADAPTER, WEB_DIFF_INCOMPLETE_MESSAGE)
    wrapped.__cause__ = exc
    return wrapped


class ControlAuthorityWebCheckService:
    """Orchestruje read-only načtení adapteru a porovnání s katalogem."""

    def __init__(
        self,
        *,
        registry: Mapping[str, ControlAuthorityWebAdapterRegistration]
        | Sequence[ControlAuthorityWebAdapterRegistration]
        | None = None,
        snapshot_service: ControlAuthorityCatalogSnapshotService | SnapshotLoader | None = None,
        http_get: HttpGet | ControlAuthorityHttpClient | None = None,
        clock: Callable[[], datetime] | None = None,
        compare: CompareFn | None = None,
    ):
        self._registry = (
            DEFAULT_WEB_ADAPTER_REGISTRY
            if registry is None
            else build_web_adapter_registry(registry)
        )
        self._primary_by_authority = MappingProxyType(
            {
                item.info.authority_code: item
                for item in self._registry.values()
                if item.info.is_primary
            }
        )
        self._snapshot_service = snapshot_service or ControlAuthorityCatalogSnapshotService()
        self._http_get = http_get
        self._clock = clock
        self._compare = compare or diff_control_authority_offices

    def supported_authority_codes(self) -> tuple[str, ...]:
        return tuple(self._primary_by_authority)

    def has_web_adapter(self, authority_code: str) -> bool:
        if not isinstance(authority_code, str):
            return False
        code = authority_code.strip().casefold()
        return bool(code) and code in self._primary_by_authority

    def get_web_adapter_info(
        self, authority_code: str
    ) -> ControlAuthorityWebAdapterInfo:
        return self._resolve_primary(authority_code).info

    def list_web_adapter_infos(
        self, authority_code: str | None = None
    ) -> tuple[ControlAuthorityWebAdapterInfo, ...]:
        if authority_code is None:
            ordered: list[ControlAuthorityWebAdapterInfo] = []
            for code in self.supported_authority_codes():
                ordered.extend(self._infos_for_authority(code))
            return tuple(ordered)
        if not isinstance(authority_code, str):
            return ()
        code = authority_code.strip().casefold()
        if not code:
            return ()
        return tuple(self._infos_for_authority(code))

    def get_web_adapter_info_by_coverage(
        self, coverage_id: str
    ) -> ControlAuthorityWebAdapterInfo:
        return self._resolve_coverage(coverage_id).info

    def check_authority_web(
        self,
        authority_code: str,
        *,
        http_get: HttpGet | ControlAuthorityHttpClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> ControlAuthorityWebCheckResult:
        return self._check_registration(
            self._resolve_primary(authority_code),
            http_get=http_get,
            clock=clock,
        )

    def check_authority_web_coverage(
        self,
        coverage_id: str,
        *,
        http_get: HttpGet | ControlAuthorityHttpClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> ControlAuthorityWebCheckResult:
        return self._check_registration(
            self._resolve_coverage(coverage_id),
            http_get=http_get,
            clock=clock,
        )

    def _infos_for_authority(self, authority_code: str) -> list[ControlAuthorityWebAdapterInfo]:
        infos = [
            item.info
            for item in self._registry.values()
            if item.info.authority_code == authority_code
        ]
        infos.sort(
            key=lambda item: (
                0 if item.is_primary else 1,
                item.display_order,
                item.coverage.coverage_id,
            )
        )
        return infos

    def _check_registration(
        self,
        registration: ControlAuthorityWebAdapterRegistration,
        *,
        http_get: HttpGet | ControlAuthorityHttpClient | None,
        clock: Callable[[], datetime] | None,
    ) -> ControlAuthorityWebCheckResult:
        info = registration.info
        snapshots = self._load_snapshots(info.authority_code)
        fetch_result = self._fetch_remote(
            registration,
            http_get=http_get if http_get is not None else self._http_get,
            clock=clock if clock is not None else self._clock,
        )
        self._assert_fetch_contract(fetch_result, info)
        try:
            diff_result = self._compare(fetch_result, snapshots, info.coverage)
        except (
            ControlAuthorityWebAdapterError,
            ControlAuthorityWebCoverageError,
            ControlAuthorityWebDiffError,
        ) as exc:
            logger.error(
                "Porovnání webu s katalogem selhalo pro rozsah %s.",
                info.coverage.coverage_id,
            )
            raise _wrap_domain_error(exc) from exc
        result = ControlAuthorityWebCheckResult(
            authority_code=info.authority_code,
            adapter_info=info,
            fetched_at=fetch_result.fetched_at,
            source_url=fetch_result.source_url,
            remote_records=fetch_result.records,
            diffs=diff_result.items,
            status_counts=diff_result.status_counts,
            warnings=_unique_warnings(fetch_result.warnings, diff_result.warnings),
            has_actionable_changes=bool(diff_result.has_actionable_changes),
            has_conflicts=bool(diff_result.has_conflicts),
            fetch_result=fetch_result,
            diff_result=diff_result,
            coverage=info.coverage,
        )
        if result.coverage is None or result.coverage.coverage_id != info.coverage.coverage_id:
            raise _check_error(
                WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE,
                WEB_CHECK_REGISTRY_COVERAGE_KEY_MESSAGE,
            )
        return result

    def _resolve_primary(
        self, authority_code: object
    ) -> ControlAuthorityWebAdapterRegistration:
        if not isinstance(authority_code, str):
            raise _check_error(
                WEB_CHECK_ERROR_CODE_REQUIRED, WEB_CHECK_CODE_REQUIRED_MESSAGE
            )
        original = authority_code.strip()
        if not original:
            raise _check_error(
                WEB_CHECK_ERROR_CODE_REQUIRED, WEB_CHECK_CODE_REQUIRED_MESSAGE
            )
        code = original.casefold()
        registration = self._primary_by_authority.get(code)
        if registration is None:
            raise _check_error(
                WEB_CHECK_ERROR_UNSUPPORTED,
                WEB_CHECK_UNSUPPORTED_MESSAGE.format(code=original),
            )
        return registration

    def _resolve_coverage(
        self, coverage_id: object
    ) -> ControlAuthorityWebAdapterRegistration:
        if not isinstance(coverage_id, str):
            raise _check_error(
                WEB_CHECK_ERROR_COVERAGE_REQUIRED, WEB_COVERAGE_ID_REQUIRED_MESSAGE
            )
        original = coverage_id.strip()
        if not original:
            raise _check_error(
                WEB_CHECK_ERROR_COVERAGE_REQUIRED, WEB_COVERAGE_ID_REQUIRED_MESSAGE
            )
        registration = self._registry.get(original)
        if registration is None:
            raise _check_error(
                WEB_CHECK_ERROR_UNSUPPORTED_COVERAGE,
                WEB_CHECK_UNSUPPORTED_COVERAGE_MESSAGE.format(coverage_id=original),
            )
        return registration

    def _load_snapshots(
        self, authority_code: str
    ) -> tuple[ControlAuthorityOfficeCatalogSnapshot, ...]:
        try:
            if hasattr(self._snapshot_service, "load_office_snapshots"):
                snapshots = self._snapshot_service.load_office_snapshots(authority_code)
            else:
                snapshots = self._snapshot_service(authority_code)
        except (
            ControlAuthorityWebAdapterError,
            ControlAuthorityWebCoverageError,
            ControlAuthorityWebDiffError,
        ) as exc:
            logger.error("Místní katalog orgánu %s se nepodařilo načíst.", authority_code)
            raise _wrap_domain_error(exc) from exc
        return tuple(snapshots)

    def _fetch_remote(
        self,
        registration: ControlAuthorityWebAdapterRegistration,
        *,
        http_get: HttpGet | ControlAuthorityHttpClient | None,
        clock: Callable[[], datetime] | None,
    ) -> ControlAuthorityWebFetchResult:
        try:
            return registration.fetch(http_get=http_get, clock=clock)
        except (
            ControlAuthorityWebAdapterError,
            ControlAuthorityWebCoverageError,
            ControlAuthorityWebDiffError,
        ) as exc:
            logger.error(
                "Webový adapter orgánu %s selhal.",
                registration.info.authority_code,
            )
            raise _wrap_domain_error(exc) from exc

    def _assert_fetch_contract(
        self,
        fetch_result: ControlAuthorityWebFetchResult,
        info: ControlAuthorityWebAdapterInfo,
    ) -> None:
        if fetch_result.authority_code != info.authority_code:
            logger.error(
                "Adapter %s vrátil authority_code %s.",
                info.authority_code,
                fetch_result.authority_code,
            )
            raise _check_error(
                WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
                WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
            )
        if not fetch_result.is_complete:
            logger.error("Neúplný výsledek adapteru %s.", info.authority_code)
            raise _check_error(WEB_DIFF_ERROR_INCOMPLETE, WEB_DIFF_INCOMPLETE_MESSAGE)
        records = tuple(fetch_result.records)
        try:
            assert_records_match_coverage(
                records,
                info.coverage,
                fetch_authority_code=fetch_result.authority_code,
            )
        except ControlAuthorityWebCoverageError as exc:
            logger.error(
                "Adapter %s nesplnil kontrakt rozsahu %s.",
                info.authority_code,
                info.coverage.coverage_id,
            )
            raise _check_error(exc.code, str(exc)) from exc


_DEFAULT_SERVICE = ControlAuthorityWebCheckService()


def supported_authority_codes() -> tuple[str, ...]:
    return _DEFAULT_SERVICE.supported_authority_codes()


def has_web_adapter(authority_code: str) -> bool:
    return _DEFAULT_SERVICE.has_web_adapter(authority_code)


def get_web_adapter_info(authority_code: str) -> ControlAuthorityWebAdapterInfo:
    return _DEFAULT_SERVICE.get_web_adapter_info(authority_code)


def list_web_adapter_infos(
    authority_code: str | None = None,
) -> tuple[ControlAuthorityWebAdapterInfo, ...]:
    return _DEFAULT_SERVICE.list_web_adapter_infos(authority_code)


def get_web_adapter_info_by_coverage(coverage_id: str) -> ControlAuthorityWebAdapterInfo:
    return _DEFAULT_SERVICE.get_web_adapter_info_by_coverage(coverage_id)


def check_authority_web(
    authority_code: str,
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
    snapshot_service: ControlAuthorityCatalogSnapshotService | SnapshotLoader | None = None,
) -> ControlAuthorityWebCheckResult:
    if snapshot_service is None and http_get is None and clock is None:
        return _DEFAULT_SERVICE.check_authority_web(authority_code)
    service = ControlAuthorityWebCheckService(
        snapshot_service=snapshot_service,
        http_get=http_get,
        clock=clock,
    )
    return service.check_authority_web(authority_code)


def check_authority_web_coverage(
    coverage_id: str,
    *,
    http_get: HttpGet | ControlAuthorityHttpClient | None = None,
    clock: Callable[[], datetime] | None = None,
    snapshot_service: ControlAuthorityCatalogSnapshotService | SnapshotLoader | None = None,
) -> ControlAuthorityWebCheckResult:
    if snapshot_service is None and http_get is None and clock is None:
        return _DEFAULT_SERVICE.check_authority_web_coverage(coverage_id)
    service = ControlAuthorityWebCheckService(
        snapshot_service=snapshot_service,
        http_get=http_get,
        clock=clock,
    )
    return service.check_authority_web_coverage(coverage_id)
