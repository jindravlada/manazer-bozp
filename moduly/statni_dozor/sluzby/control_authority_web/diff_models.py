"""Read-only DTO porovnání webového adapteru s katalogem."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from moduly.statni_dozor.constants import (
    WEB_DIFF_AUTHORITY_NOT_FOUND_MESSAGE,
    WEB_DIFF_DUPLICATE_LOCAL_MESSAGE,
    WEB_DIFF_DUPLICATE_REMOTE_MESSAGE,
    WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND,
    WEB_DIFF_ERROR_DUPLICATE_LOCAL,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_INCOMPLETE_MESSAGE,
    WEB_DIFF_MISSING_KEY_MESSAGE,
    WEB_DIFF_STATUSES,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
)

_MESSAGES = {
    WEB_DIFF_ERROR_INCOMPLETE: WEB_DIFF_INCOMPLETE_MESSAGE,
    WEB_DIFF_ERROR_MISSING_KEY: WEB_DIFF_MISSING_KEY_MESSAGE,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE: WEB_DIFF_DUPLICATE_REMOTE_MESSAGE,
    WEB_DIFF_ERROR_DUPLICATE_LOCAL: WEB_DIFF_DUPLICATE_LOCAL_MESSAGE,
    WEB_DIFF_ERROR_AUTHORITY_NOT_FOUND: WEB_DIFF_AUTHORITY_NOT_FOUND_MESSAGE,
}


@dataclass(frozen=True)
class ControlAuthorityOfficeCatalogSnapshot:
    """Čistý snímek místního pracoviště bez SQLAlchemy session a Qt."""

    id: int
    authority_id: int
    authority_code: str
    external_key: str | None
    name: str
    address: str | None
    phone: str | None
    email: str | None
    website: str | None
    territorial_scope: str | None
    office_kind: str | None
    source_url: str | None
    active: bool
    origin: str
    user_edited_at: datetime | None
    last_checked_at: datetime | None


@dataclass(frozen=True)
class ControlAuthorityOfficeFieldChange:
    """Jedna věcná změna sledovaného pole."""

    field: str
    old_value: str | None
    new_value: str | None


@dataclass(frozen=True)
class ControlAuthorityOfficeDiff:
    """Náhled rozdílu jednoho pracoviště. Akce se nevykonává."""

    status: str
    authority_code: str
    external_key: str | None
    local_id: int | None
    local: ControlAuthorityOfficeCatalogSnapshot | None
    remote: ControlAuthorityOfficeWebRecord | None
    field_changes: tuple[ControlAuthorityOfficeFieldChange, ...]
    recommended_action: str
    requires_manual_review: bool
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_changes", tuple(self.field_changes))


@dataclass(frozen=True)
class ControlAuthorityWebDiffResult:
    """Souhrn read-only porovnání webu s katalogem."""

    authority_code: str
    source_url: str
    fetched_at: datetime
    items: tuple[ControlAuthorityOfficeDiff, ...]
    status_counts: tuple[tuple[str, int], ...]
    warnings: tuple[str, ...]
    has_actionable_changes: bool
    has_conflicts: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "status_counts", tuple(self.status_counts))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def count(self, status: str) -> int:
        return dict(self.status_counts).get(status, 0)


class ControlAuthorityWebDiffError(ValueError):
    """Doménová chyba porovnání webu s katalogem."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


def diff_error(code: str) -> ControlAuthorityWebDiffError:
    return ControlAuthorityWebDiffError(
        _MESSAGES.get(code, WEB_DIFF_INCOMPLETE_MESSAGE),
        code=code,
    )


def empty_status_counts() -> dict[str, int]:
    return {status: 0 for status in WEB_DIFF_STATUSES}
