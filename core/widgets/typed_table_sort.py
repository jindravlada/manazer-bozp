"""Společné typované řazení QTableWidget (UX-TABLE-1a).

Použití::

    from core.widgets.typed_table_sort import (
        create_typed_item,
        enable_typed_sorting,
        typed_bool,
        typed_date,
        typed_status,
    )

    enable_typed_sorting(table)
    table.setItem(0, 0, create_typed_item("12. 7. 2026", typed_date(date(2026, 7, 12))))
    table.setItem(0, 1, create_typed_item("Kritické", typed_status(0)))

Řadicí klíč je v ``TYPED_SORT_ROLE``; zobrazený text slouží jen uživateli.
Prázdné hodnoty jsou vždy na konci (vzestupně i sestupně).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from core.utils.czech_sort import czech_sort_key

# Vyhrazená role pro typovaný klíč (mimo běžné UserRole s ID řádku).
TYPED_SORT_ROLE = int(Qt.ItemDataRole.UserRole) + 32
TYPED_SORT_STABLE_ROLE = int(Qt.ItemDataRole.UserRole) + 33

_MISSING = object()


class SortKind(str, Enum):
    EMPTY = "empty"
    TEXT = "text"
    INT = "int"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"
    BOOL = "bool"
    STATUS = "status"


@dataclass(frozen=True)
class TypedSortValue:
    """Typovaný řadicí klíč oddělený od zobrazeného textu."""

    kind: SortKind
    payload: Any = None


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def typed_empty() -> TypedSortValue:
    return TypedSortValue(SortKind.EMPTY)


def typed_text(value: str | None) -> TypedSortValue:
    if is_blank(value):
        return typed_empty()
    return TypedSortValue(SortKind.TEXT, str(value))


def typed_int(value: int | None) -> TypedSortValue:
    if value is None:
        return typed_empty()
    return TypedSortValue(SortKind.INT, int(value))


def typed_float(value: float | int | None) -> TypedSortValue:
    if value is None:
        return typed_empty()
    return TypedSortValue(SortKind.FLOAT, float(value))


def typed_date(value: date | None) -> TypedSortValue:
    if value is None:
        return typed_empty()
    if isinstance(value, datetime):
        value = value.date()
    return TypedSortValue(SortKind.DATE, value)


def typed_datetime(value: datetime | None) -> TypedSortValue:
    if value is None:
        return typed_empty()
    return TypedSortValue(SortKind.DATETIME, value)


def typed_bool(value: bool | None) -> TypedSortValue:
    if value is None:
        return typed_empty()
    return TypedSortValue(SortKind.BOOL, bool(value))


def typed_status(order: int | None, *, label: str = "") -> TypedSortValue:
    """Explicitní pořadí stavu (menší číslo = dříve při vzestupu)."""
    if order is None:
        return typed_empty()
    return TypedSortValue(SortKind.STATUS, (int(order), str(label or "")))


def coerce_typed_sort_value(value: Any) -> TypedSortValue:
    """Převede běžnou Python hodnotu na TypedSortValue."""
    if isinstance(value, TypedSortValue):
        return value
    if is_blank(value):
        return typed_empty()
    if isinstance(value, bool):
        return typed_bool(value)
    if isinstance(value, int):
        return typed_int(value)
    if isinstance(value, float):
        return typed_float(value)
    if isinstance(value, datetime):
        return typed_datetime(value)
    if isinstance(value, date):
        return typed_date(value)
    return typed_text(str(value))


def _comparable_payload(sort_value: TypedSortValue) -> Any:
    if sort_value.kind == SortKind.EMPTY:
        return None
    if sort_value.kind == SortKind.TEXT:
        return czech_sort_key(sort_value.payload)
    if sort_value.kind == SortKind.BOOL:
        return 0 if not sort_value.payload else 1
    if sort_value.kind == SortKind.STATUS:
        return sort_value.payload
    if sort_value.kind == SortKind.DATE:
        return sort_value.payload.toordinal()
    if sort_value.kind == SortKind.DATETIME:
        return sort_value.payload.timestamp()
    return sort_value.payload


def _kind_rank(kind: SortKind) -> int:
    order = (
        SortKind.BOOL,
        SortKind.INT,
        SortKind.FLOAT,
        SortKind.DATE,
        SortKind.DATETIME,
        SortKind.STATUS,
        SortKind.TEXT,
        SortKind.EMPTY,
    )
    try:
        return order.index(kind)
    except ValueError:
        return len(order)


def compare_typed_sort_values(
    left: TypedSortValue,
    right: TypedSortValue,
    *,
    ascending: bool,
) -> int:
    """
    Vrátí -1 / 0 / 1.
    Prázdné hodnoty jsou vždy poslední bez ohledu na směr.
    """
    left_empty = left.kind == SortKind.EMPTY
    right_empty = right.kind == SortKind.EMPTY
    if left_empty and right_empty:
        return 0
    if left_empty or right_empty:
        if ascending:
            return 1 if left_empty else -1
        return -1 if left_empty else 1

    if left.kind != right.kind:
        rank = _kind_rank(left.kind) - _kind_rank(right.kind)
        return -1 if rank < 0 else 1

    left_payload = _comparable_payload(left)
    right_payload = _comparable_payload(right)
    if left_payload == right_payload:
        return 0
    return -1 if left_payload < right_payload else 1


class TypedSortTableWidgetItem(QTableWidgetItem):
    """QTableWidgetItem s typovaným klíčem a prázdnými hodnotami vždy na konci."""

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        if not isinstance(other, QTableWidgetItem):
            return NotImplemented

        ascending = True
        table = self.tableWidget()
        if table is not None:
            ascending = (
                table.horizontalHeader().sortIndicatorOrder()
                == Qt.SortOrder.AscendingOrder
            )

        left_raw = self.data(TYPED_SORT_ROLE)
        right_raw = other.data(TYPED_SORT_ROLE)
        left = (
            coerce_typed_sort_value(left_raw)
            if left_raw is not None
            else coerce_typed_sort_value(self.text())
        )
        right = (
            coerce_typed_sort_value(right_raw)
            if right_raw is not None
            else coerce_typed_sort_value(other.text())
        )

        result = compare_typed_sort_values(left, right, ascending=ascending)
        if result != 0:
            return result < 0

        left_stable = self.data(TYPED_SORT_STABLE_ROLE)
        right_stable = other.data(TYPED_SORT_STABLE_ROLE)
        if left_stable is None:
            left_stable = self.row()
        if right_stable is None:
            right_stable = other.row()
        if left_stable == right_stable:
            return False
        # Tie-break podle směru tak, aby nižší stable_id zůstalo „dříve“
        # i po invertování porovnání při sestupu.
        if ascending:
            return left_stable < right_stable
        return left_stable > right_stable


def create_typed_item(
    display_text: str | None,
    sort_value: Any = _MISSING,
    *,
    stable_id: int | None = None,
) -> TypedSortTableWidgetItem:
    """
    Vytvoří buňku se zobrazeným textem a typovaným řadicím klíčem.

    - Bez ``sort_value``: klíč se odvodí ze zobrazeného textu.
    - ``sort_value=None`` / prázdný text: prázdná hodnota (vždy na konci).
    - ``sort_value`` může být ``TypedSortValue`` nebo str/int/float/bool/date/datetime.
    """
    text = "" if display_text is None else str(display_text)
    item = TypedSortTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if sort_value is _MISSING:
        typed = coerce_typed_sort_value(display_text)
    else:
        typed = coerce_typed_sort_value(sort_value)
    item.setData(TYPED_SORT_ROLE, typed)
    if stable_id is not None:
        item.setData(TYPED_SORT_STABLE_ROLE, int(stable_id))
    return item


def set_typed_sort_value(item: QTableWidgetItem, sort_value: Any) -> None:
    """Nastaví typovaný klíč na existující položku."""
    item.setData(TYPED_SORT_ROLE, coerce_typed_sort_value(sort_value))


def set_typed_stable_id(item: QTableWidgetItem, stable_id: int) -> None:
    item.setData(TYPED_SORT_STABLE_ROLE, int(stable_id))


def enable_typed_sorting(table: QTableWidget) -> None:
    """Zapne standardní řazení hlavičkou (1. klik ↑, 2. klik ↓)."""
    table.setSortingEnabled(True)
    header = table.horizontalHeader()
    header.setSortIndicatorShown(True)
