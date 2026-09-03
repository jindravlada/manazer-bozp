"""Čisté porovnání webového výsledku s katalogovými snapshoty."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from moduly.statni_dozor.constants import (
    AUTHORITY_ORIGIN_MANUAL,
    WEB_CHECK_COVERAGE_KIND_MESSAGE,
    WEB_CHECK_ERROR_COVERAGE_KIND,
    WEB_DIFF_ACTION_CREATE,
    WEB_DIFF_ACTION_DEACTIVATE,
    WEB_DIFF_ACTION_NONE,
    WEB_DIFF_ACTION_REACTIVATE,
    WEB_DIFF_ACTION_REVIEW,
    WEB_DIFF_ACTION_UPDATE,
    WEB_DIFF_COMPARED_FIELDS,
    WEB_DIFF_ERROR_DUPLICATE_LOCAL,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_REASON_CHANGED,
    WEB_DIFF_REASON_DUPLICATE_ADDRESS,
    WEB_DIFF_REASON_DUPLICATE_CITY_SCOPE,
    WEB_DIFF_REASON_DUPLICATE_NAME,
    WEB_DIFF_REASON_IDENTITY,
    WEB_DIFF_REASON_INACTIVE,
    WEB_DIFF_REASON_MISSING,
    WEB_DIFF_REASON_NEW,
    WEB_DIFF_REASON_PROTECTED,
    WEB_DIFF_REASON_PROTECTED_MISSING,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_IDENTITY_CONFLICT,
    WEB_DIFF_STATUS_INACTIVE_PRESENT,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
    WEB_DIFF_STATUS_PROTECTED,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
    WEB_DIFF_STATUS_UNCHANGED,
    WEB_DIFF_STATUSES,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import (
    ControlAuthorityWebCoverage,
    ControlAuthorityWebCoverageError,
    local_kind_covered,
    local_kind_unknown,
    unknown_office_kind_warning,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityOfficeFieldChange,
    ControlAuthorityWebDiffResult,
    diff_error,
    empty_status_counts,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
    ControlAuthorityWebFetchResult,
)

logger = logging.getLogger(__name__)

_POSTAL_PREFIX = re.compile(r"^\d{3}\s+\d{2}\s+")
_URL_FIELDS = frozenset({"website", "source_url"})
_CONFLICT_STATUSES = frozenset(
    {
        WEB_DIFF_STATUS_IDENTITY_CONFLICT,
        WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
    }
)


def _collapse_space(value: str | None) -> str:
    if value is None:
        return ""
    text = (
        str(value)
        .replace("\xa0", " ")
        .replace("\u202f", " ")
        .replace("\u2009", " ")
    )
    return " ".join(text.split())


def _norm_text(value: str | None) -> str:
    return _collapse_space(value).casefold()


def _norm_phone(value: str | None) -> str:
    return "".join(_collapse_space(value).split())


def _norm_url(value: str | None) -> str:
    text = _norm_text(value)
    if not text:
        return ""
    return text.rstrip("/")


def _city_from_address(value: str | None) -> str:
    text = _collapse_space(value)
    if not text:
        return ""
    last = text.split(",")[-1].strip()
    last = _POSTAL_PREFIX.sub("", last)
    return _norm_text(last)


def _original(record, field: str) -> str | None:
    value = getattr(record, field)
    if value is None:
        return None
    return str(value)


def _values_equal(field: str, old: str | None, new: str | None) -> bool:
    if field == "phone":
        return _norm_phone(old) == _norm_phone(new)
    if field in _URL_FIELDS:
        return _norm_url(old) == _norm_url(new)
    return _norm_text(old) == _norm_text(new)


def _field_changes(
    local: ControlAuthorityOfficeCatalogSnapshot,
    remote: ControlAuthorityOfficeWebRecord,
) -> tuple[ControlAuthorityOfficeFieldChange, ...]:
    changes: list[ControlAuthorityOfficeFieldChange] = []
    observed = frozenset(remote.observed_fields)
    for field in WEB_DIFF_COMPARED_FIELDS:
        if field not in observed:
            continue
        old = _original(local, field)
        new = _original(remote, field)
        if not _values_equal(field, old, new):
            changes.append(
                ControlAuthorityOfficeFieldChange(
                    field=field,
                    old_value=old,
                    new_value=new,
                )
            )
    return tuple(changes)


def _is_protected(snapshot: ControlAuthorityOfficeCatalogSnapshot) -> bool:
    return (
        snapshot.origin == AUTHORITY_ORIGIN_MANUAL
        or snapshot.user_edited_at is not None
    )


def _duplicate_candidate(
    remote: ControlAuthorityOfficeWebRecord,
    locals_same_authority: Sequence[ControlAuthorityOfficeCatalogSnapshot],
) -> tuple[ControlAuthorityOfficeCatalogSnapshot, str] | None:
    remote_name = _norm_text(remote.name)
    remote_address = _norm_text(remote.address)
    remote_city = _city_from_address(remote.address)
    remote_scope = _norm_text(remote.territorial_scope)
    found: list[tuple[ControlAuthorityOfficeCatalogSnapshot, str]] = []
    for local in locals_same_authority:
        local_name = _norm_text(local.name)
        local_address = _norm_text(local.address)
        if remote_name and local_name and remote_name == local_name:
            found.append((local, WEB_DIFF_REASON_DUPLICATE_NAME))
            continue
        if remote_address and local_address and remote_address == local_address:
            found.append((local, WEB_DIFF_REASON_DUPLICATE_ADDRESS))
            continue
        if (
            remote_city
            and remote_scope
            and remote_city == _city_from_address(local.address)
            and remote_scope == _norm_text(local.territorial_scope)
        ):
            found.append((local, WEB_DIFF_REASON_DUPLICATE_CITY_SCOPE))
    if not found:
        return None
    return min(found, key=lambda item: (item[0].id, item[0].name))


def _index_local_keys(
    snapshots: Sequence[ControlAuthorityOfficeCatalogSnapshot],
) -> dict[str, ControlAuthorityOfficeCatalogSnapshot]:
    indexed: dict[str, ControlAuthorityOfficeCatalogSnapshot] = {}
    for snapshot in snapshots:
        key = (snapshot.external_key or "").strip()
        if not key:
            continue
        if key in indexed:
            logger.error("Duplicitní local external_key %s", key)
            raise diff_error(WEB_DIFF_ERROR_DUPLICATE_LOCAL)
        indexed[key] = snapshot
    return indexed


def _index_remote_keys(
    records: Sequence[ControlAuthorityOfficeWebRecord],
) -> dict[str, ControlAuthorityOfficeWebRecord]:
    indexed: dict[str, ControlAuthorityOfficeWebRecord] = {}
    for record in records:
        key = (record.external_key or "").strip()
        if not key:
            logger.error("Webový záznam pracoviště nemá external_key.")
            raise diff_error(WEB_DIFF_ERROR_MISSING_KEY)
        if key in indexed:
            logger.error("Duplicitní remote external_key %s", key)
            raise diff_error(WEB_DIFF_ERROR_DUPLICATE_REMOTE)
        indexed[key] = record
    return indexed


def _paired_diff(
    local: ControlAuthorityOfficeCatalogSnapshot,
    remote: ControlAuthorityOfficeWebRecord,
) -> ControlAuthorityOfficeDiff:
    if local.authority_code != remote.authority_code:
        return ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_IDENTITY_CONFLICT,
            authority_code=remote.authority_code,
            external_key=remote.external_key,
            local_id=local.id,
            local=local,
            remote=remote,
            field_changes=(),
            recommended_action=WEB_DIFF_ACTION_REVIEW,
            requires_manual_review=True,
            reason=WEB_DIFF_REASON_IDENTITY,
        )
    changes = _field_changes(local, remote)
    if not local.active:
        return ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_INACTIVE_PRESENT,
            authority_code=remote.authority_code,
            external_key=remote.external_key,
            local_id=local.id,
            local=local,
            remote=remote,
            field_changes=changes,
            recommended_action=WEB_DIFF_ACTION_REACTIVATE,
            requires_manual_review=True,
            reason=WEB_DIFF_REASON_INACTIVE,
        )
    if not changes:
        return ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_UNCHANGED,
            authority_code=remote.authority_code,
            external_key=remote.external_key,
            local_id=local.id,
            local=local,
            remote=remote,
            field_changes=(),
            recommended_action=WEB_DIFF_ACTION_NONE,
            requires_manual_review=False,
            reason="",
        )
    if _is_protected(local):
        return ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_PROTECTED,
            authority_code=remote.authority_code,
            external_key=remote.external_key,
            local_id=local.id,
            local=local,
            remote=remote,
            field_changes=changes,
            recommended_action=WEB_DIFF_ACTION_REVIEW,
            requires_manual_review=True,
            reason=WEB_DIFF_REASON_PROTECTED,
        )
    return ControlAuthorityOfficeDiff(
        status=WEB_DIFF_STATUS_CHANGED,
        authority_code=remote.authority_code,
        external_key=remote.external_key,
        local_id=local.id,
        local=local,
        remote=remote,
        field_changes=changes,
        recommended_action=WEB_DIFF_ACTION_UPDATE,
        requires_manual_review=False,
        reason=WEB_DIFF_REASON_CHANGED,
    )


def _observed_kind_matches_coverage(
    remote: ControlAuthorityOfficeWebRecord,
    coverage: ControlAuthorityWebCoverage,
) -> None:
    observed = frozenset(remote.observed_fields or ())
    if "office_kind" not in observed:
        return
    kind = str(remote.office_kind or "").strip()
    if kind not in coverage.covered_office_kinds:
        raise ControlAuthorityWebCoverageError(
            WEB_CHECK_COVERAGE_KIND_MESSAGE,
            code=WEB_CHECK_ERROR_COVERAGE_KIND,
        )


def _missing_diff(
    local: ControlAuthorityOfficeCatalogSnapshot,
) -> ControlAuthorityOfficeDiff:
    protected = _is_protected(local)
    return ControlAuthorityOfficeDiff(
        status=(
            WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE
            if protected
            else WEB_DIFF_STATUS_MISSING_REMOTE
        ),
        authority_code=local.authority_code,
        external_key=local.external_key,
        local_id=local.id,
        local=local,
        remote=None,
        field_changes=(),
        recommended_action=(
            WEB_DIFF_ACTION_REVIEW if protected else WEB_DIFF_ACTION_DEACTIVATE
        ),
        requires_manual_review=True,
        reason=(
            WEB_DIFF_REASON_PROTECTED_MISSING if protected else WEB_DIFF_REASON_MISSING
        ),
    )


def _new_or_duplicate_diff(
    remote: ControlAuthorityOfficeWebRecord,
    locals_same_authority: Sequence[ControlAuthorityOfficeCatalogSnapshot],
) -> ControlAuthorityOfficeDiff:
    duplicate = _duplicate_candidate(remote, locals_same_authority)
    if duplicate is not None:
        local, reason = duplicate
        return ControlAuthorityOfficeDiff(
            status=WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
            authority_code=remote.authority_code,
            external_key=remote.external_key,
            local_id=local.id,
            local=local,
            remote=remote,
            field_changes=(),
            recommended_action=WEB_DIFF_ACTION_REVIEW,
            requires_manual_review=True,
            reason=reason,
        )
    return ControlAuthorityOfficeDiff(
        status=WEB_DIFF_STATUS_NEW,
        authority_code=remote.authority_code,
        external_key=remote.external_key,
        local_id=None,
        local=None,
        remote=remote,
        field_changes=(),
        recommended_action=WEB_DIFF_ACTION_CREATE,
        requires_manual_review=False,
        reason=WEB_DIFF_REASON_NEW,
    )


def diff_control_authority_offices(
    fetch_result: ControlAuthorityWebFetchResult,
    snapshots: Sequence[ControlAuthorityOfficeCatalogSnapshot],
    coverage: ControlAuthorityWebCoverage | None = None,
) -> ControlAuthorityWebDiffResult:
    """Porovná úplný webový výsledek s čistými katalogovými snapshoty."""
    if not fetch_result.is_complete:
        logger.error(
            "Odmítnut neúplný webový výsledek orgánu %s.",
            fetch_result.authority_code,
        )
        raise diff_error(WEB_DIFF_ERROR_INCOMPLETE)

    if coverage is not None:
        for remote in fetch_result.records:
            _observed_kind_matches_coverage(remote, coverage)

    remote_by_key = _index_remote_keys(fetch_result.records)
    local_by_key = _index_local_keys(snapshots)
    same_authority = tuple(
        item
        for item in snapshots
        if item.authority_code == fetch_result.authority_code
    )
    items: list[ControlAuthorityOfficeDiff] = []
    matched_local_ids: set[int] = set()
    warnings: list[str] = list(fetch_result.warnings)

    for remote in fetch_result.records:
        local = local_by_key.get(remote.external_key)
        if local is None:
            items.append(_new_or_duplicate_diff(remote, same_authority))
            continue
        paired = _paired_diff(local, remote)
        items.append(paired)
        matched_local_ids.add(local.id)

    for local in same_authority:
        key = (local.external_key or "").strip()
        if not key:
            continue
        if key in remote_by_key:
            continue
        if local.id in matched_local_ids:
            continue
        if coverage is None:
            continue
        if local_kind_unknown(local.office_kind):
            warning = unknown_office_kind_warning(local.name)
            if warning not in warnings:
                warnings.append(warning)
            continue
        if not local_kind_covered(local.office_kind, coverage):
            continue
        items.append(_missing_diff(local))

    counts = empty_status_counts()
    for item in items:
        if item.status not in WEB_DIFF_STATUSES:
            logger.error("Neznámý status porovnání %s", item.status)
            continue
        counts[item.status] += 1
    has_actionable = any(item.recommended_action != WEB_DIFF_ACTION_NONE for item in items)
    has_conflicts = any(item.status in _CONFLICT_STATUSES for item in items)
    return ControlAuthorityWebDiffResult(
        authority_code=fetch_result.authority_code,
        source_url=fetch_result.source_url,
        fetched_at=fetch_result.fetched_at,
        items=tuple(items),
        status_counts=tuple((status, counts[status]) for status in WEB_DIFF_STATUSES),
        warnings=tuple(warnings),
        has_actionable_changes=has_actionable,
        has_conflicts=has_conflicts,
    )
