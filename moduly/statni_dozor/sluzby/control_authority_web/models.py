"""Společná DTO a chyby webových adapterů kontrolních orgánů."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from moduly.statni_dozor.constants import (
    WEB_ADAPTER_DUPLICATE_KEY_MESSAGE,
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
    WEB_ADAPTER_INCOMPLETE_MESSAGE,
    WEB_ADAPTER_INVALID_URL_MESSAGE,
    WEB_ADAPTER_NETWORK_MESSAGE,
    WEB_ADAPTER_TIMEOUT_MESSAGE,
    WEB_ADAPTER_TOO_LARGE_MESSAGE,
    WEB_ADAPTER_UNREADABLE_HTML_MESSAGE,
    WEB_ADAPTER_UNSUPPORTED_CONTENT_MESSAGE,
    WEB_DIFF_COMPARED_FIELD_SET,
    WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD,
    WEB_DIFF_UNKNOWN_OBSERVED_FIELD_MESSAGE,
)

_MESSAGES = {
    WEB_ADAPTER_ERROR_NETWORK: WEB_ADAPTER_NETWORK_MESSAGE,
    WEB_ADAPTER_ERROR_TIMEOUT: WEB_ADAPTER_TIMEOUT_MESSAGE,
    WEB_ADAPTER_ERROR_HTTP: WEB_ADAPTER_HTTP_MESSAGE,
    WEB_ADAPTER_ERROR_INVALID_URL: WEB_ADAPTER_INVALID_URL_MESSAGE,
    WEB_ADAPTER_ERROR_TOO_LARGE: WEB_ADAPTER_TOO_LARGE_MESSAGE,
    WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT: WEB_ADAPTER_UNSUPPORTED_CONTENT_MESSAGE,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML: WEB_ADAPTER_UNREADABLE_HTML_MESSAGE,
    WEB_ADAPTER_ERROR_INCOMPLETE: WEB_ADAPTER_INCOMPLETE_MESSAGE,
    WEB_ADAPTER_ERROR_DUPLICATE_KEY: WEB_ADAPTER_DUPLICATE_KEY_MESSAGE,
    WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD: WEB_DIFF_UNKNOWN_OBSERVED_FIELD_MESSAGE,
}


@dataclass(frozen=True)
class ControlAuthorityOfficeWebRecord:
    """Jedno pracoviště načtené z oficiálního webu kontrolního orgánu."""

    authority_code: str
    external_key: str
    name: str
    address: str | None
    phone: str | None
    email: str | None
    website: str | None
    territorial_scope: str | None
    office_kind: str | None
    source_url: str
    observed_fields: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        observed = frozenset(self.observed_fields or ())
        unknown = observed - WEB_DIFF_COMPARED_FIELD_SET
        if unknown:
            raise adapter_error(WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD)
        object.__setattr__(self, "observed_fields", observed)


@dataclass(frozen=True)
class ControlAuthorityWebFetchResult:
    """Výsledek jednoho read-only načtení adapteru."""

    authority_code: str
    source_url: str
    fetched_at: datetime
    records: tuple[ControlAuthorityOfficeWebRecord, ...]
    warnings: tuple[str, ...] = ()
    is_complete: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "is_complete", bool(self.is_complete))


class ControlAuthorityWebAdapterError(ValueError):
    """Doménová chyba načtení oficiální stránky kontrolního orgánu."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


def adapter_error(code: str) -> ControlAuthorityWebAdapterError:
    return ControlAuthorityWebAdapterError(
        _MESSAGES.get(code, WEB_ADAPTER_NETWORK_MESSAGE),
        code=code,
    )
