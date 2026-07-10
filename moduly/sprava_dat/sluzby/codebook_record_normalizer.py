from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Integer
from sqlalchemy.exc import SQLAlchemyError


class CodebookRecordNormalizationError(ValueError):
    """Neplatná hodnota při převodu exportovaného záznamu číselníku."""

    def __init__(self, codebook_name: str, field_name: str, value: Any, *, reason: str) -> None:
        self.codebook_name = codebook_name
        self.field_name = field_name
        self.value = value
        self.reason = reason
        super().__init__(
            f"{codebook_name}: pole {field_name} obsahuje neplatné datum „{value}“."
            if reason == "invalid_datetime"
            else f"{codebook_name}: pole {field_name} obsahuje neplatnou hodnotu „{value}“."
        )


def normalize_database_record(
    model_class: type,
    record: dict,
    *,
    codebook_name: str,
) -> dict:
    """Převede exportované hodnoty podle typů sloupců SQLAlchemy modelu."""
    normalized = dict(record)
    table = model_class.__table__

    for column in table.columns:
        field_name = column.name
        if field_name not in normalized:
            continue

        value = normalized[field_name]
        column_type = column.type

        if isinstance(column_type, DateTime):
            normalized[field_name] = _normalize_datetime_value(
                value,
                codebook_name=codebook_name,
                field_name=field_name,
                nullable=column.nullable,
            )
            if normalized[field_name] is None and field_name in normalized and not column.nullable:
                normalized.pop(field_name, None)
            continue

        if isinstance(column_type, Date):
            normalized[field_name] = _normalize_date_value(
                value,
                codebook_name=codebook_name,
                field_name=field_name,
                nullable=column.nullable,
            )
            if normalized[field_name] is None and field_name in normalized and not column.nullable:
                normalized.pop(field_name, None)
            continue

        if isinstance(column_type, Boolean) and value is not None and not isinstance(value, bool):
            normalized[field_name] = bool(value)
            continue

        if isinstance(column_type, Integer) and value is not None and value != "":
            if isinstance(value, bool):
                raise CodebookRecordNormalizationError(
                    codebook_name,
                    field_name,
                    value,
                    reason="invalid_integer",
                )
            try:
                normalized[field_name] = int(value)
            except (TypeError, ValueError) as exc:
                raise CodebookRecordNormalizationError(
                    codebook_name,
                    field_name,
                    value,
                    reason="invalid_integer",
                ) from exc

    return normalized


def _empty_value(value: Any) -> bool:
    return value is None or value == ""


def _normalize_datetime_value(
    value: Any,
    *,
    codebook_name: str,
    field_name: str,
    nullable: bool,
) -> datetime | None:
    if _empty_value(value):
        return None if nullable else None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    if not isinstance(value, str):
        raise CodebookRecordNormalizationError(
            codebook_name,
            field_name,
            value,
            reason="invalid_datetime",
        )

    text = value.strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise CodebookRecordNormalizationError(
            codebook_name,
            field_name,
            value,
            reason="invalid_datetime",
        ) from exc


def _normalize_date_value(
    value: Any,
    *,
    codebook_name: str,
    field_name: str,
    nullable: bool,
) -> date | None:
    if _empty_value(value):
        return None if nullable else None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    if not isinstance(value, str):
        raise CodebookRecordNormalizationError(
            codebook_name,
            field_name,
            value,
            reason="invalid_datetime",
        )

    text = value.strip()
    if not text:
        return None

    try:
        if "T" in text:
            return datetime.fromisoformat(text).date()
        return date.fromisoformat(text)
    except ValueError as exc:
        raise CodebookRecordNormalizationError(
            codebook_name,
            field_name,
            value,
            reason="invalid_datetime",
        ) from exc


def ensure_database_session_rollback() -> None:
    """Po chybě importu uvolní případnou rozpracovanou transakci."""
    from core.database.session import get_session

    session = get_session()
    try:
        session.rollback()
    except SQLAlchemyError:
        session.rollback()
    finally:
        session.close()
