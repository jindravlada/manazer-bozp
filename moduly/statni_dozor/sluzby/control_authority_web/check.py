"""Společná read-only webová kontrola katalogu kontrolních orgánů."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from urllib.parse import urlparse

from moduly.statni_dozor.constants import (
    CBU_AUTHORITY_CODE,
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
    WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
    WEB_CHECK_CODE_REQUIRED_MESSAGE,
    WEB_CHECK_ERROR_ADAPTER,
    WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
    WEB_CHECK_ERROR_CODE_REQUIRED,
    WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    WEB_CHECK_ERROR_UNSUPPORTED,
    WEB_CHECK_UNEXPECTED_COUNT_MESSAGE,
    WEB_CHECK_UNSUPPORTED_MESSAGE,
    WEB_DIFF_DUPLICATE_REMOTE_MESSAGE,
    WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_INCOMPLETE_MESSAGE,
    WEB_DIFF_MISSING_KEY_MESSAGE,
)
from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    ControlAuthorityCatalogSnapshotService,
)
from moduly.statni_dozor.sluzby.control_authority_web.cbu_adapter import fetch_cbu_offices
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
CompareFn = Callable[
    [ControlAuthorityWebFetchResult, tuple[ControlAuthorityOfficeCatalogSnapshot, ...]],
    ControlAuthorityWebDiffResult,
]


@dataclass(frozen=True)
class ControlAuthorityWebAdapterInfo:
    """Veřejné metadata jednoho registrovaného webového adapteru."""

    authority_code: str
    display_name: str
    source_name: str
    source_url: str
    expected_office_count: int


@dataclass(frozen=True)
class ControlAuthorityWebAdapterRegistration:
    """Vazba metadat adapteru na jeho fetch callable."""

    info: ControlAuthorityWebAdapterInfo
    fetch: WebAdapterFetch


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "remote_records", tuple(self.remote_records))
        object.__setattr__(self, "diffs", tuple(self.diffs))
        object.__setattr__(self, "status_counts", tuple(self.status_counts))
        object.__setattr__(self, "warnings", tuple(self.warnings))


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


def _default_registry() -> Mapping[str, ControlAuthorityWebAdapterRegistration]:
    entries = (
        ControlAuthorityWebAdapterRegistration(
            info=ControlAuthorityWebAdapterInfo(
                authority_code=DU_AUTHORITY_CODE,
                display_name="Drážní úřad",
                source_name="Kontakty Drážního úřadu",
                source_url=_https_source_url(DU_OFFICES_SOURCE_URL),
                expected_office_count=len(DU_OFFICE_EXTERNAL_KEYS),
            ),
            fetch=fetch_du_offices,
        ),
        ControlAuthorityWebAdapterRegistration(
            info=ControlAuthorityWebAdapterInfo(
                authority_code=SUIP_AUTHORITY_CODE,
                display_name="Státní úřad inspekce práce",
                source_name="Kontakty oblastních inspektorátů práce",
                source_url=_https_source_url(SUIP_HUB_SOURCE_URL),
                expected_office_count=len(SUIP_OFFICE_EXTERNAL_KEYS),
            ),
            fetch=fetch_suip_offices,
        ),
        ControlAuthorityWebAdapterRegistration(
            info=ControlAuthorityWebAdapterInfo(
                authority_code=CBU_AUTHORITY_CODE,
                display_name="Český báňský úřad",
                source_name="Obvodní báňské úřady",
                source_url=_https_source_url(CBU_OFFICES_SOURCE_URL),
                expected_office_count=len(CBU_OFFICE_EXTERNAL_KEYS),
            ),
            fetch=fetch_cbu_offices,
        ),
        ControlAuthorityWebAdapterRegistration(
            info=ControlAuthorityWebAdapterInfo(
                authority_code=KHS_AUTHORITY_CODE,
                display_name="Krajské hygienické stanice",
                source_name="Ministerstvo zdravotnictví – Krajské hygienické stanice",
                source_url=_https_source_url(KHS_OFFICES_SOURCE_URL),
                expected_office_count=len(KHS_OFFICE_EXTERNAL_KEYS),
            ),
            fetch=fetch_khs_offices,
        ),
        ControlAuthorityWebAdapterRegistration(
            info=ControlAuthorityWebAdapterInfo(
                authority_code=HZS_AUTHORITY_CODE,
                display_name="Hasičský záchranný sbor České republiky",
                source_name="HZS krajů",
                source_url=_https_source_url(HZS_OFFICES_SOURCE_URL),
                expected_office_count=len(HZS_OFFICE_EXTERNAL_KEYS),
            ),
            fetch=fetch_hzs_offices,
        ),
    )
    mapping = {item.info.authority_code: item for item in entries}
    if tuple(mapping) != (
        DU_AUTHORITY_CODE,
        SUIP_AUTHORITY_CODE,
        CBU_AUTHORITY_CODE,
        KHS_AUTHORITY_CODE,
        HZS_AUTHORITY_CODE,
    ):
        raise RuntimeError("Registr webových adapterů nemá očekávané pořadí kódů.")
    return MappingProxyType(mapping)


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
        registry: Mapping[str, ControlAuthorityWebAdapterRegistration] | None = None,
        snapshot_service: ControlAuthorityCatalogSnapshotService | SnapshotLoader | None = None,
        http_get: HttpGet | ControlAuthorityHttpClient | None = None,
        clock: Callable[[], datetime] | None = None,
        compare: CompareFn | None = None,
    ):
        self._registry = registry or DEFAULT_WEB_ADAPTER_REGISTRY
        self._snapshot_service = snapshot_service or ControlAuthorityCatalogSnapshotService()
        self._http_get = http_get
        self._clock = clock
        self._compare = compare or diff_control_authority_offices

    def supported_authority_codes(self) -> tuple[str, ...]:
        return tuple(self._registry)

    def has_web_adapter(self, authority_code: str) -> bool:
        if not isinstance(authority_code, str):
            return False
        code = authority_code.strip().casefold()
        return bool(code) and code in self._registry

    def get_web_adapter_info(
        self, authority_code: str
    ) -> ControlAuthorityWebAdapterInfo:
        return self._resolve_registration(authority_code).info

    def check_authority_web(
        self,
        authority_code: str,
        *,
        http_get: HttpGet | ControlAuthorityHttpClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> ControlAuthorityWebCheckResult:
        registration = self._resolve_registration(authority_code)
        info = registration.info
        snapshots = self._load_snapshots(info.authority_code)
        fetch_result = self._fetch_remote(
            registration,
            http_get=http_get if http_get is not None else self._http_get,
            clock=clock if clock is not None else self._clock,
        )
        self._assert_fetch_contract(fetch_result, info)
        try:
            diff_result = self._compare(fetch_result, snapshots)
        except (ControlAuthorityWebAdapterError, ControlAuthorityWebDiffError) as exc:
            logger.error("Porovnání webu s katalogem selhalo pro orgán %s.", info.authority_code)
            raise _wrap_domain_error(exc) from exc
        return ControlAuthorityWebCheckResult(
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
        )

    def _resolve_registration(
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
        registration = self._registry.get(code)
        if registration is None:
            raise _check_error(
                WEB_CHECK_ERROR_UNSUPPORTED,
                WEB_CHECK_UNSUPPORTED_MESSAGE.format(code=original),
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
        except (ControlAuthorityWebAdapterError, ControlAuthorityWebDiffError) as exc:
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
        except (ControlAuthorityWebAdapterError, ControlAuthorityWebDiffError) as exc:
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
        if len(records) != int(info.expected_office_count):
            logger.error(
                "Adapter %s vrátil %s pracovišť, očekáváno %s.",
                info.authority_code,
                len(records),
                info.expected_office_count,
            )
            raise _check_error(
                WEB_CHECK_ERROR_UNEXPECTED_COUNT,
                WEB_CHECK_UNEXPECTED_COUNT_MESSAGE,
            )
        seen: set[str] = set()
        for record in records:
            if record.authority_code != info.authority_code:
                raise _check_error(
                    WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
                    WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
                )
            key = str(record.external_key or "").strip()
            if not key:
                raise _check_error(
                    WEB_DIFF_ERROR_MISSING_KEY, WEB_DIFF_MISSING_KEY_MESSAGE
                )
            if key in seen:
                raise _check_error(
                    WEB_DIFF_ERROR_DUPLICATE_REMOTE, WEB_DIFF_DUPLICATE_REMOTE_MESSAGE
                )
            seen.add(key)


_DEFAULT_SERVICE = ControlAuthorityWebCheckService()


def supported_authority_codes() -> tuple[str, ...]:
    return _DEFAULT_SERVICE.supported_authority_codes()


def has_web_adapter(authority_code: str) -> bool:
    return _DEFAULT_SERVICE.has_web_adapter(authority_code)


def get_web_adapter_info(authority_code: str) -> ControlAuthorityWebAdapterInfo:
    return _DEFAULT_SERVICE.get_web_adapter_info(authority_code)


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
