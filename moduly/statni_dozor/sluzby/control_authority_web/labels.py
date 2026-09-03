"""České popisky webové kontroly katalogu — bez Qt."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime

from moduly.statni_dozor.constants import (
    EMPTY_VALUE,
    OFFICE_KIND_USER_LABELS,
    WEB_ADAPTER_ERROR_DUPLICATE_KEY,
    WEB_ADAPTER_ERROR_HTTP,
    WEB_ADAPTER_ERROR_INCOMPLETE,
    WEB_ADAPTER_ERROR_INVALID_URL,
    WEB_ADAPTER_ERROR_NETWORK,
    WEB_ADAPTER_ERROR_TIMEOUT,
    WEB_ADAPTER_ERROR_TOO_LARGE,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML,
    WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT,
    WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    WEB_CHECK_ERROR_UNSUPPORTED,
    WEB_CHECK_UI_ALL_MATCH_TEXT,
    WEB_CHECK_UI_DIFFERENCES_TEXT,
    WEB_CHECK_UI_ERROR_NETWORK,
    WEB_CHECK_UI_ERROR_OTHER,
    WEB_CHECK_UI_ERROR_STRUCTURE,
    WEB_CHECK_UI_ERROR_UNSUPPORTED,
    WEB_CHECK_UI_UNKNOWN_ACTION_LABEL,
    WEB_CHECK_UI_UNKNOWN_FIELD_LABEL,
    WEB_CHECK_UI_UNKNOWN_STATUS_LABEL,
    WEB_DIFF_ACTION_USER_LABELS,
    WEB_DIFF_ERROR_DUPLICATE_REMOTE,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_ERROR_MISSING_KEY,
    WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD,
    WEB_DIFF_FIELD_USER_LABELS,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_UNCHANGED,
    WEB_DIFF_STATUS_USER_LABELS,
    WEB_DIFF_SUMMARY_CHANGED,
    WEB_DIFF_SUMMARY_MISSING,
    WEB_DIFF_SUMMARY_NEW,
    WEB_DIFF_SUMMARY_REVIEW,
    WEB_DIFF_SUMMARY_UNCHANGED,
)

logger = logging.getLogger(__name__)

_NETWORK_CODES = frozenset(
    {
        WEB_ADAPTER_ERROR_NETWORK,
        WEB_ADAPTER_ERROR_TIMEOUT,
        WEB_ADAPTER_ERROR_HTTP,
        WEB_ADAPTER_ERROR_INVALID_URL,
    }
)
_STRUCTURE_CODES = frozenset(
    {
        WEB_ADAPTER_ERROR_INCOMPLETE,
        WEB_ADAPTER_ERROR_UNREADABLE_HTML,
        WEB_ADAPTER_ERROR_UNSUPPORTED_CONTENT,
        WEB_ADAPTER_ERROR_TOO_LARGE,
        WEB_ADAPTER_ERROR_DUPLICATE_KEY,
        WEB_DIFF_ERROR_INCOMPLETE,
        WEB_DIFF_ERROR_MISSING_KEY,
        WEB_DIFF_ERROR_DUPLICATE_REMOTE,
        WEB_DIFF_ERROR_UNKNOWN_OBSERVED_FIELD,
        WEB_CHECK_ERROR_UNEXPECTED_COUNT,
    }
)


def web_diff_status_label(status: str) -> str:
    label = WEB_DIFF_STATUS_USER_LABELS.get(str(status or ""))
    if label:
        return label
    logger.warning("Neznámý stav webové kontroly: %s", status)
    return WEB_CHECK_UI_UNKNOWN_STATUS_LABEL


def web_diff_field_label(field: str) -> str:
    label = WEB_DIFF_FIELD_USER_LABELS.get(str(field or ""))
    if label:
        return label
    logger.warning("Neznámé pole webové kontroly: %s", field)
    return WEB_CHECK_UI_UNKNOWN_FIELD_LABEL


def web_diff_action_label(action: str) -> str:
    label = WEB_DIFF_ACTION_USER_LABELS.get(str(action or ""))
    if label:
        return label
    logger.warning("Neznámé doporučení webové kontroly: %s", action)
    return WEB_CHECK_UI_UNKNOWN_ACTION_LABEL


def format_web_diff_value(field: str, value: str | None) -> str:
    if value is None or str(value).strip() == "":
        return EMPTY_VALUE
    text = str(value)
    if field == "office_kind":
        return OFFICE_KIND_USER_LABELS.get(text, text)
    return text


def format_web_checked_at(value: datetime | None) -> str:
    if value is None:
        return EMPTY_VALUE
    return value.strftime("%d. %m. %Y %H:%M")


def web_check_headline(diffs: Sequence) -> str:
    if not diffs or all(getattr(item, "status", None) == WEB_DIFF_STATUS_UNCHANGED for item in diffs):
        return WEB_CHECK_UI_ALL_MATCH_TEXT
    return WEB_CHECK_UI_DIFFERENCES_TEXT


def web_check_summary_lines(diffs: Sequence) -> tuple[str, ...]:
    unchanged = 0
    changed = 0
    new = 0
    missing = 0
    review = 0
    for item in diffs:
        status = getattr(item, "status", "")
        if status == WEB_DIFF_STATUS_UNCHANGED:
            unchanged += 1
        elif status == WEB_DIFF_STATUS_CHANGED:
            changed += 1
        elif status == WEB_DIFF_STATUS_NEW:
            new += 1
        elif status == WEB_DIFF_STATUS_MISSING_REMOTE:
            missing += 1
        if bool(getattr(item, "requires_manual_review", False)):
            review += 1
    lines: list[str] = []
    if unchanged:
        lines.append(f"{WEB_DIFF_SUMMARY_UNCHANGED}: {unchanged}")
    if changed:
        lines.append(f"{WEB_DIFF_SUMMARY_CHANGED}: {changed}")
    if new:
        lines.append(f"{WEB_DIFF_SUMMARY_NEW}: {new}")
    if missing:
        lines.append(f"{WEB_DIFF_SUMMARY_MISSING}: {missing}")
    if review:
        lines.append(f"{WEB_DIFF_SUMMARY_REVIEW}: {review}")
    return tuple(lines)


def web_check_error_user_message(exc: BaseException) -> str:
    code = str(getattr(exc, "code", "") or "")
    if code == WEB_CHECK_ERROR_UNSUPPORTED:
        return WEB_CHECK_UI_ERROR_UNSUPPORTED
    if code in _NETWORK_CODES:
        return WEB_CHECK_UI_ERROR_NETWORK
    if code in _STRUCTURE_CODES:
        return WEB_CHECK_UI_ERROR_STRUCTURE
    cause = getattr(exc, "__cause__", None)
    cause_code = str(getattr(cause, "code", "") or "")
    if cause_code in _NETWORK_CODES:
        return WEB_CHECK_UI_ERROR_NETWORK
    if cause_code in _STRUCTURE_CODES:
        return WEB_CHECK_UI_ERROR_STRUCTURE
    if cause_code == WEB_CHECK_ERROR_UNSUPPORTED:
        return WEB_CHECK_UI_ERROR_UNSUPPORTED
    return WEB_CHECK_UI_ERROR_OTHER
