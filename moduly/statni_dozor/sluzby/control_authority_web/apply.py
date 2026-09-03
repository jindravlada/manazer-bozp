"""Atomické použití vybraných změn z webové kontroly katalogu."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from moduly.statni_dozor.constants import (
    AUTHORITY_ORIGIN_WEB,
    WEB_APPLY_ACTION_CREATE,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ACTION_REACTIVATE,
    WEB_APPLY_ACTION_UPDATE,
    WEB_APPLY_ACTIONS,
    WEB_APPLY_DUPLICATE_SELECTION_MESSAGE,
    WEB_APPLY_EMPTY_FIELDS_MESSAGE,
    WEB_APPLY_EMPTY_NAME_MESSAGE,
    WEB_APPLY_ERROR_DUPLICATE_SELECTION,
    WEB_APPLY_ERROR_EMPTY_NAME,
    WEB_APPLY_ERROR_FIELDS,
    WEB_APPLY_ERROR_INVALID_ACTION,
    WEB_APPLY_ERROR_PROTECTED,
    WEB_APPLY_ERROR_SELECTION,
    WEB_APPLY_ERROR_STALE,
    WEB_APPLY_ERROR_STATUS,
    WEB_APPLY_FIELDS_MESSAGE,
    WEB_APPLY_INVALID_ACTION_MESSAGE,
    WEB_APPLY_PROTECTED_MESSAGE,
    WEB_APPLY_SELECTION_MESSAGE,
    WEB_APPLY_STALE_MESSAGE,
    WEB_APPLY_STATUS_MESSAGE,
    WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
    WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
    WEB_CHECK_ERROR_UNSUPPORTED,
    WEB_CHECK_UNSUPPORTED_MESSAGE,
    WEB_DIFF_COMPARED_FIELD_SET,
    WEB_DIFF_COMPARED_FIELDS,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_INCOMPLETE_MESSAGE,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_INACTIVE_PRESENT,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_PROTECTED,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogService,
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.catalog_snapshot_service import (
    snapshot_from_office,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    get_web_adapter_info_by_coverage,
    has_web_adapter,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverageError,
    assert_records_match_coverage,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
)

_STALE_OFFICE_FIELDS: tuple[str, ...] = (
    "id",
    "authority_id",
    "external_key",
    "name",
    "address",
    "phone",
    "email",
    "website",
    "territorial_scope",
    "office_kind",
    "source_url",
    "active",
    "origin",
    "user_edited_at",
)


@dataclass(frozen=True)
class ControlAuthorityOfficeWebApplySelection:
    """Výslovný výběr jedné změny z potvrzeného náhledu webové kontroly."""

    external_key: str
    local_id: int | None
    action: str
    selected_fields: frozenset[str] = field(default_factory=frozenset)
    confirm_protected: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "external_key", str(self.external_key or "").strip())
        object.__setattr__(self, "action", str(self.action or "").strip())
        object.__setattr__(self, "selected_fields", frozenset(self.selected_fields or ()))
        object.__setattr__(self, "confirm_protected", bool(self.confirm_protected))
        if self.local_id is not None:
            object.__setattr__(self, "local_id", int(self.local_id))


@dataclass(frozen=True)
class ControlAuthorityWebApplyResult:
    """Výsledek atomického použití vybraných webových změn."""

    authority_code: str
    applied_at: datetime
    created_ids: tuple[int, ...]
    updated_ids: tuple[int, ...]
    deactivated_ids: tuple[int, ...]
    reactivated_ids: tuple[int, ...]
    applied_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "created_ids", tuple(self.created_ids))
        object.__setattr__(self, "updated_ids", tuple(self.updated_ids))
        object.__setattr__(self, "deactivated_ids", tuple(self.deactivated_ids))
        object.__setattr__(self, "reactivated_ids", tuple(self.reactivated_ids))
        object.__setattr__(
            self,
            "applied_count",
            int(
                len(self.created_ids)
                + len(self.updated_ids)
                + len(self.deactivated_ids)
                + len(self.reactivated_ids)
            ),
        )


class ControlAuthorityWebApplyError(ValueError):
    """Doménová chyba použití vybraných webových změn katalogu."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = str(code)


def _apply_error(code: str, message: str) -> ControlAuthorityWebApplyError:
    return ControlAuthorityWebApplyError(message, code=code)


def _empty_result(
    check_result: ControlAuthorityWebCheckResult,
) -> ControlAuthorityWebApplyResult:
    return ControlAuthorityWebApplyResult(
        authority_code=check_result.authority_code,
        applied_at=check_result.fetched_at,
        created_ids=(),
        updated_ids=(),
        deactivated_ids=(),
        reactivated_ids=(),
        applied_count=0,
    )


def _diff_key(diff: ControlAuthorityOfficeDiff) -> tuple[str, int | None]:
    return (str(diff.external_key or "").strip(), diff.local_id)


def _selection_key(
    selection: ControlAuthorityOfficeWebApplySelection,
) -> tuple[str, int | None]:
    return (selection.external_key, selection.local_id)


def _changed_fields(diff: ControlAuthorityOfficeDiff) -> dict[str, str | None]:
    return {change.field: change.new_value for change in diff.field_changes}


def _is_protected_status(status: str) -> bool:
    return status in {
        WEB_DIFF_STATUS_PROTECTED,
        WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
    }


def _snapshot_stale(
    office,
    snapshot: ControlAuthorityOfficeCatalogSnapshot,
    authority_code: str,
) -> bool:
    current = snapshot_from_office(office, authority_code)
    for name in _STALE_OFFICE_FIELDS:
        if getattr(current, name) != getattr(snapshot, name):
            return True
    if snapshot.updated_at is not None and current.updated_at != snapshot.updated_at:
        return True
    return False


class ControlAuthorityWebApplyService:
    """Použije jen výslovně vybrané změny z potvrzeného výsledku kontroly."""

    def __init__(self, catalog: ControlAuthorityCatalogService | None = None):
        self.catalog = catalog or control_authority_catalog_service

    def apply_authority_web_changes(
        self,
        check_result: ControlAuthorityWebCheckResult,
        selections: Sequence[ControlAuthorityOfficeWebApplySelection],
    ) -> ControlAuthorityWebApplyResult:
        chosen = tuple(selections)
        if not chosen:
            return _empty_result(check_result)

        self._validate_check_result(check_result)
        planned = self._validate_selections(check_result, chosen)

        created_ids: list[int] = []
        updated_ids: list[int] = []
        deactivated_ids: list[int] = []
        reactivated_ids: list[int] = []
        fetched_at = check_result.fetched_at

        with self.catalog.repository.session() as (sess, owns):
            authority = self._require_authority(check_result.authority_code, session=sess)
            self._assert_fresh_preview(authority, planned, session=sess)
            try:
                for selection, diff in planned:
                    office_id = self._apply_item(
                        authority,
                        selection,
                        diff,
                        fetched_at=fetched_at,
                        session=sess,
                    )
                    if selection.action == WEB_APPLY_ACTION_CREATE:
                        created_ids.append(office_id)
                    elif selection.action == WEB_APPLY_ACTION_UPDATE:
                        updated_ids.append(office_id)
                    elif selection.action == WEB_APPLY_ACTION_DEACTIVATE:
                        deactivated_ids.append(office_id)
                    elif selection.action == WEB_APPLY_ACTION_REACTIVATE:
                        reactivated_ids.append(office_id)
                sess.flush()
                self.catalog.update_imported_authority(
                    int(authority.id),
                    last_checked_at=fetched_at,
                    session=sess,
                )
                sess.flush()
                result = ControlAuthorityWebApplyResult(
                    authority_code=check_result.authority_code,
                    applied_at=fetched_at,
                    created_ids=tuple(sorted(created_ids)),
                    updated_ids=tuple(sorted(updated_ids)),
                    deactivated_ids=tuple(sorted(deactivated_ids)),
                    reactivated_ids=tuple(sorted(reactivated_ids)),
                    applied_count=0,
                )
                if owns:
                    sess.commit()
            except Exception:
                if owns:
                    sess.rollback()
                raise
        return result

    def _validate_check_result(self, check_result: ControlAuthorityWebCheckResult) -> None:
        code = str(check_result.authority_code or "").strip()
        if not code or not has_web_adapter(code):
            raise _apply_error(
                WEB_CHECK_ERROR_UNSUPPORTED,
                WEB_CHECK_UNSUPPORTED_MESSAGE.format(
                    code=code or check_result.authority_code
                ),
            )
        coverage = check_result.coverage
        if coverage is None:
            coverage = check_result.adapter_info.coverage
        try:
            info = get_web_adapter_info_by_coverage(coverage.coverage_id)
        except ControlAuthorityWebCheckError as exc:
            raise _apply_error(exc.code, str(exc)) from exc
        if check_result.fetched_at is None:
            raise _apply_error(WEB_DIFF_ERROR_INCOMPLETE, WEB_DIFF_INCOMPLETE_MESSAGE)
        fetch_result = check_result.fetch_result
        if fetch_result is None or not fetch_result.is_complete:
            raise _apply_error(WEB_DIFF_ERROR_INCOMPLETE, WEB_DIFF_INCOMPLETE_MESSAGE)
        if (
            fetch_result.authority_code != info.authority_code
            or check_result.authority_code != info.authority_code
            or coverage != info.coverage
            or check_result.adapter_info.coverage != info.coverage
        ):
            raise _apply_error(
                WEB_CHECK_ERROR_AUTHORITY_MISMATCH,
                WEB_CHECK_AUTHORITY_MISMATCH_MESSAGE,
            )
        records = tuple(check_result.remote_records)
        if tuple(fetch_result.records) != records:
            raise _apply_error(WEB_DIFF_ERROR_INCOMPLETE, WEB_DIFF_INCOMPLETE_MESSAGE)
        try:
            assert_records_match_coverage(
                records,
                coverage,
                fetch_authority_code=fetch_result.authority_code,
            )
        except ControlAuthorityWebCoverageError as exc:
            raise _apply_error(exc.code, str(exc)) from exc
        for diff in check_result.diffs:
            if diff.authority_code != info.authority_code:
                raise _apply_error(
                    WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE
                )

    def _validate_selections(
        self,
        check_result: ControlAuthorityWebCheckResult,
        selections: tuple[ControlAuthorityOfficeWebApplySelection, ...],
    ) -> tuple[tuple[ControlAuthorityOfficeWebApplySelection, ControlAuthorityOfficeDiff], ...]:
        diffs_by_key: dict[tuple[str, int | None], ControlAuthorityOfficeDiff] = {}
        for diff in check_result.diffs:
            key = _diff_key(diff)
            if key in diffs_by_key:
                raise _apply_error(
                    WEB_APPLY_ERROR_DUPLICATE_SELECTION,
                    WEB_APPLY_DUPLICATE_SELECTION_MESSAGE,
                )
            diffs_by_key[key] = diff

        planned: list[tuple[ControlAuthorityOfficeWebApplySelection, ControlAuthorityOfficeDiff]] = []
        seen_keys: set[tuple[str, int | None]] = set()
        for selection in selections:
            key = _selection_key(selection)
            if not selection.external_key:
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            if key in seen_keys:
                raise _apply_error(
                    WEB_APPLY_ERROR_DUPLICATE_SELECTION,
                    WEB_APPLY_DUPLICATE_SELECTION_MESSAGE,
                )
            seen_keys.add(key)
            diff = diffs_by_key.get(key)
            if diff is None:
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            if (
                selection.action == WEB_APPLY_ACTION_CREATE
                and (
                    check_result.coverage is None
                    or selection.external_key
                    not in check_result.coverage.expected_external_keys
                )
            ):
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            self._validate_action(selection, diff)
            planned.append((selection, diff))
        return tuple(planned)

    def _validate_action(
        self,
        selection: ControlAuthorityOfficeWebApplySelection,
        diff: ControlAuthorityOfficeDiff,
    ) -> None:
        if selection.action not in WEB_APPLY_ACTIONS:
            raise _apply_error(
                WEB_APPLY_ERROR_INVALID_ACTION, WEB_APPLY_INVALID_ACTION_MESSAGE
            )
        status = diff.status
        if selection.action == WEB_APPLY_ACTION_CREATE:
            if status != WEB_DIFF_STATUS_NEW:
                raise _apply_error(WEB_APPLY_ERROR_STATUS, WEB_APPLY_STATUS_MESSAGE)
            if diff.remote is None:
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            name = str(diff.remote.name or "").strip()
            if not name:
                raise _apply_error(WEB_APPLY_ERROR_EMPTY_NAME, WEB_APPLY_EMPTY_NAME_MESSAGE)
            return
        if selection.action == WEB_APPLY_ACTION_UPDATE:
            if status == WEB_DIFF_STATUS_PROTECTED:
                if not selection.confirm_protected:
                    raise _apply_error(
                        WEB_APPLY_ERROR_PROTECTED, WEB_APPLY_PROTECTED_MESSAGE
                    )
            elif status != WEB_DIFF_STATUS_CHANGED:
                raise _apply_error(WEB_APPLY_ERROR_STATUS, WEB_APPLY_STATUS_MESSAGE)
            self._validate_selected_fields(selection, diff)
            if diff.local is None or diff.local_id is None or diff.remote is None:
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            return
        if selection.action == WEB_APPLY_ACTION_DEACTIVATE:
            if status == WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE:
                if not selection.confirm_protected:
                    raise _apply_error(
                        WEB_APPLY_ERROR_PROTECTED, WEB_APPLY_PROTECTED_MESSAGE
                    )
            elif status != WEB_DIFF_STATUS_MISSING_REMOTE:
                raise _apply_error(WEB_APPLY_ERROR_STATUS, WEB_APPLY_STATUS_MESSAGE)
            if diff.local is None or diff.local_id is None:
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            return
        if status != WEB_DIFF_STATUS_INACTIVE_PRESENT:
            raise _apply_error(WEB_APPLY_ERROR_STATUS, WEB_APPLY_STATUS_MESSAGE)
        if diff.local is None or diff.local_id is None:
            raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)

    def _validate_selected_fields(
        self,
        selection: ControlAuthorityOfficeWebApplySelection,
        diff: ControlAuthorityOfficeDiff,
    ) -> None:
        if not selection.selected_fields:
            raise _apply_error(WEB_APPLY_ERROR_FIELDS, WEB_APPLY_EMPTY_FIELDS_MESSAGE)
        allowed = set(_changed_fields(diff))
        if not selection.selected_fields <= allowed:
            raise _apply_error(WEB_APPLY_ERROR_FIELDS, WEB_APPLY_FIELDS_MESSAGE)
        if not selection.selected_fields <= WEB_DIFF_COMPARED_FIELD_SET:
            raise _apply_error(WEB_APPLY_ERROR_FIELDS, WEB_APPLY_FIELDS_MESSAGE)

    def _require_authority(self, authority_code: str, *, session):
        authority = self.catalog.get_authority_by_code(authority_code, session=session)
        if authority is None:
            raise _apply_error(WEB_APPLY_ERROR_STALE, WEB_APPLY_STALE_MESSAGE)
        return authority

    def _assert_fresh_preview(self, authority, planned, *, session) -> None:
        for selection, diff in planned:
            if selection.action == WEB_APPLY_ACTION_CREATE:
                existing = self.catalog.get_office_by_external_key(
                    selection.external_key, session=session
                )
                if existing is not None:
                    raise _apply_error(WEB_APPLY_ERROR_STALE, WEB_APPLY_STALE_MESSAGE)
                continue
            if diff.local is None or diff.local_id is None:
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            office = self.catalog.get_office(int(diff.local_id), session=session)
            if office is None:
                raise _apply_error(WEB_APPLY_ERROR_STALE, WEB_APPLY_STALE_MESSAGE)
            if int(office.authority_id) != int(authority.id):
                raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
            if int(office.id) != int(diff.local.id):
                raise _apply_error(WEB_APPLY_ERROR_STALE, WEB_APPLY_STALE_MESSAGE)
            if _snapshot_stale(office, diff.local, authority.code):
                raise _apply_error(WEB_APPLY_ERROR_STALE, WEB_APPLY_STALE_MESSAGE)

    def _apply_item(
        self,
        authority,
        selection: ControlAuthorityOfficeWebApplySelection,
        diff: ControlAuthorityOfficeDiff,
        *,
        fetched_at: datetime,
        session,
    ) -> int:
        if selection.action == WEB_APPLY_ACTION_CREATE:
            return self._apply_create(
                authority, diff.remote, fetched_at=fetched_at, session=session
            )
        if selection.action == WEB_APPLY_ACTION_UPDATE:
            return self._apply_update(
                selection, diff, fetched_at=fetched_at, session=session
            )
        if selection.action == WEB_APPLY_ACTION_DEACTIVATE:
            saved = self.catalog.deactivate_office(
                int(diff.local_id),
                last_checked_at=fetched_at,
                mark_user_edited=False,
                session=session,
            )
            return int(saved.id)
        saved = self.catalog.reactivate_office(
            int(diff.local_id),
            last_checked_at=fetched_at,
            mark_user_edited=False,
            session=session,
        )
        return int(saved.id)

    def _apply_create(
        self,
        authority,
        remote: ControlAuthorityOfficeWebRecord | None,
        *,
        fetched_at: datetime,
        session,
    ) -> int:
        if remote is None:
            raise _apply_error(WEB_APPLY_ERROR_SELECTION, WEB_APPLY_SELECTION_MESSAGE)
        name = str(remote.name or "").strip()
        if not name:
            raise _apply_error(WEB_APPLY_ERROR_EMPTY_NAME, WEB_APPLY_EMPTY_NAME_MESSAGE)
        values: dict[str, str | None] = {"name": name}
        for field_name in WEB_DIFF_COMPARED_FIELDS:
            if field_name == "name":
                continue
            if field_name in remote.observed_fields:
                values[field_name] = getattr(remote, field_name)
        existing = self.catalog.get_office_by_external_key(
            remote.external_key, session=session
        )
        if existing is not None:
            raise _apply_error(WEB_APPLY_ERROR_STALE, WEB_APPLY_STALE_MESSAGE)
        saved = self.catalog.create_imported_office(
            authority_id=int(authority.id),
            name=name,
            origin=AUTHORITY_ORIGIN_WEB,
            address=values.get("address"),
            phone=values.get("phone"),
            email=values.get("email"),
            website=values.get("website"),
            territorial_scope=values.get("territorial_scope"),
            office_kind=values.get("office_kind"),
            active=True,
            external_key=remote.external_key,
            source_url=values.get("source_url"),
            last_checked_at=fetched_at,
            session=session,
        )
        return int(saved.id)

    def _apply_update(
        self,
        selection: ControlAuthorityOfficeWebApplySelection,
        diff: ControlAuthorityOfficeDiff,
        *,
        fetched_at: datetime,
        session,
    ) -> int:
        changes = _changed_fields(diff)
        field_values = {name: changes[name] for name in selection.selected_fields}
        kwargs: dict = {}
        if not _is_protected_status(diff.status):
            kwargs["origin"] = AUTHORITY_ORIGIN_WEB
            kwargs["user_edited_at"] = None
        saved = self.catalog.update_imported_office(
            int(diff.local_id),
            last_checked_at=fetched_at,
            field_values=field_values,
            session=session,
            **kwargs,
        )
        return int(saved.id)


_DEFAULT_SERVICE = ControlAuthorityWebApplyService()


def apply_authority_web_changes(
    check_result: ControlAuthorityWebCheckResult,
    selections: Sequence[ControlAuthorityOfficeWebApplySelection],
    *,
    catalog: ControlAuthorityCatalogService | None = None,
) -> ControlAuthorityWebApplyResult:
    if catalog is None:
        return _DEFAULT_SERVICE.apply_authority_web_changes(check_result, selections)
    return ControlAuthorityWebApplyService(catalog=catalog).apply_authority_web_changes(
        check_result, selections
    )
