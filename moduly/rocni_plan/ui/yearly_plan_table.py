"""Tabulka položek Ročního plánu – celoroční pohled."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
)

from core.widgets.typed_table_sort import create_typed_item, sorting_paused, typed_text
from moduly.rocni_plan.constants import (
    COL_ID,
    COL_LINK,
    COL_NOTE,
    COL_SOURCE,
    COL_STATUS,
    COL_TITLE,
    COLUMN_HEADERS,
    ROW_KIND_MANUAL,
    ROW_KIND_PERIODIC,
    format_processed_at,
    month_label,
    status_label,
)
from moduly.rocni_plan.modely.yearly_plan_row import YearlyPlanRow

# Stejné barvy jako aktivní položka levého menu (MainWindow._SIDEBAR_ACTIVE_STYLE).
_MONTH_HEADER_BG = QColor("#E3F2FD")
_MONTH_HEADER_BORDER = QColor("#93c5fd")

_ROLE_PLAN_ITEM_ID = Qt.ItemDataRole.UserRole
_ROLE_KIND = Qt.ItemDataRole.UserRole + 1
_ROLE_ACTIVITY_ID = Qt.ItemDataRole.UserRole + 2
_ROLE_DISPLAY_STATUS = Qt.ItemDataRole.UserRole + 3
_ROLE_SLOT_YEAR = Qt.ItemDataRole.UserRole + 4
_ROLE_SLOT_MONTH = Qt.ItemDataRole.UserRole + 5
_ROLE_IS_RECURRING = Qt.ItemDataRole.UserRole + 6
_ROLE_IS_MONTH_HEADER = Qt.ItemDataRole.UserRole + 7
_ROLE_HEADER_MONTH = Qt.ItemDataRole.UserRole + 8
_ROLE_HEADER_NAME = Qt.ItemDataRole.UserRole + 9
_ROLE_HEADER_SUMMARY = Qt.ItemDataRole.UserRole + 10

_HEADER_NAME_GAP = "   "


@dataclass(frozen=True)
class YearlyPlanMonthSection:
    month: int
    rows: list[YearlyPlanRow]
    summary: dict[str, int]
    processed_at: object | None = None


def format_month_header_parts(
    month: int,
    summary: dict[str, int],
    *,
    processed_at=None,
) -> tuple[str, str]:
    """Vrátí (název měsíce, souhrn). Název se zobrazuje tučně, souhrn normálně."""
    name = month_label(month).capitalize()
    parts = [
        "Celkem: {total}   Splněno: {done}   Řeší se: {in_progress}   "
        "Resty: {rest}   Zrušeno: {cancelled}".format(**summary),
    ]
    if processed_at is not None:
        parts.append(f"Zpracováno: {format_processed_at(processed_at)}")
    return name, _HEADER_NAME_GAP.join(parts)


def format_month_header_text(
    month: int,
    summary: dict[str, int],
    *,
    processed_at=None,
) -> str:
    name, rest = format_month_header_parts(
        month, summary, processed_at=processed_at
    )
    if rest:
        return f"{name}{_HEADER_NAME_GAP}{rest}"
    return name


class _MonthHeaderDelegate(QStyledItemDelegate):
    """Světle modré pozadí a modrý rámeček; tučný jen název měsíce."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        if not index.data(_ROLE_IS_MONTH_HEADER):
            super().paint(painter, option, index)
            return
        painter.save()
        painter.fillRect(option.rect, _MONTH_HEADER_BG)
        pen = QPen(_MONTH_HEADER_BORDER, 2)
        painter.setPen(pen)
        painter.drawRect(option.rect.adjusted(1, 1, -2, -2))

        name = str(index.data(_ROLE_HEADER_NAME) or "")
        summary = str(index.data(_ROLE_HEADER_SUMMARY) or "")
        if not name and not summary:
            text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
            if _HEADER_NAME_GAP in text:
                name, summary = text.split(_HEADER_NAME_GAP, 1)
            else:
                name = text

        painter.setPen(option.palette.color(QPalette.ColorRole.Text))
        text_rect = option.rect.adjusted(8, 0, -8, 0)
        align = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        x = text_rect.left()

        if name:
            bold_font = QFont(option.font)
            bold_font.setBold(True)
            painter.setFont(bold_font)
            name_width = painter.fontMetrics().horizontalAdvance(name)
            name_rect = QRect(x, text_rect.top(), name_width, text_rect.height())
            painter.drawText(name_rect, align, name)
            x += name_width

        if summary:
            normal_font = QFont(option.font)
            normal_font.setBold(False)
            painter.setFont(normal_font)
            gap = painter.fontMetrics().horizontalAdvance(_HEADER_NAME_GAP)
            summary_rect = QRect(
                x + gap,
                text_rect.top(),
                max(0, text_rect.right() - (x + gap) + 1),
                text_rect.height(),
            )
            painter.drawText(summary_rect, align, summary)

        painter.restore()


class YearlyPlanTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._month_header_rows: dict[int, int] = {}
        self.setColumnCount(len(COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        # Zebra ručně po měsících (Base / AlternateBase jako u Koordinace BOZP).
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(COL_ID, True)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        self.setSortingEnabled(False)
        self.setItemDelegate(_MonthHeaderDelegate(self))

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def month_header_row(self, month: int) -> int | None:
        return self._month_header_rows.get(int(month))

    def scroll_to_month(self, month: int) -> None:
        row = self.month_header_row(month)
        if row is None:
            return
        item = self.item(row, COL_SOURCE)
        if item is None:
            item = self.item(row, COL_TITLE)
        if item is not None:
            self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtTop)

    def header_text_for_month(self, month: int) -> str:
        row = self.month_header_row(month)
        if row is None:
            return ""
        item = self.item(row, COL_SOURCE)
        return item.text() if item is not None else ""

        """Po filtru ponechá viditelný řádek měsíce, pokud má viditelné položky."""
        header_rows = sorted(self._month_header_rows.values())
        for index, header_row in enumerate(header_rows):
            end = (
                header_rows[index + 1]
                if index + 1 < len(header_rows)
                else self.rowCount()
            )
            has_visible_item = False
            for row in range(header_row + 1, end):
                if not self.isRowHidden(row):
                    has_visible_item = True
                    break
            # Prázdný měsíc: při aktivním filtru skryj header, jinak vždy ukazuj.
            # (volající nastaví filter; bez filtru jsou všechny řádky vidět)
            if has_visible_item:
                self.setRowHidden(header_row, False)

    def _selected_id_item(self):
        rows = self.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        return self.item(rows[0].row(), COL_ID)

    def selected_is_month_header(self) -> bool:
        item = self._selected_id_item()
        if item is None:
            return False
        return bool(item.data(_ROLE_IS_MONTH_HEADER))

    def selected_item_id(self) -> int | None:
        """ID ruční položky / definice, nebo None u Periodické činnosti."""
        item = self._selected_id_item()
        if item is None or item.data(_ROLE_IS_MONTH_HEADER):
            return None
        if item.data(_ROLE_KIND) != ROW_KIND_MANUAL:
            return None
        raw = item.data(_ROLE_PLAN_ITEM_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def selected_activity_id(self) -> int | None:
        item = self._selected_id_item()
        if item is None or item.data(_ROLE_IS_MONTH_HEADER):
            return None
        if item.data(_ROLE_KIND) != ROW_KIND_PERIODIC:
            return None
        raw = item.data(_ROLE_ACTIVITY_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def selected_kind(self) -> str | None:
        item = self._selected_id_item()
        if item is None or item.data(_ROLE_IS_MONTH_HEADER):
            return None
        kind = item.data(_ROLE_KIND)
        return str(kind) if kind else None

    def selected_is_periodic(self) -> bool:
        return self.selected_kind() == ROW_KIND_PERIODIC

    def selected_is_manual(self) -> bool:
        return self.selected_kind() == ROW_KIND_MANUAL

    def selected_is_recurring(self) -> bool:
        item = self._selected_id_item()
        if item is None:
            return False
        return bool(item.data(_ROLE_IS_RECURRING))

    def selected_slot_year_month(self) -> tuple[int, int] | None:
        item = self._selected_id_item()
        if item is None or item.data(_ROLE_IS_MONTH_HEADER):
            return None
        year = item.data(_ROLE_SLOT_YEAR)
        month = item.data(_ROLE_SLOT_MONTH)
        try:
            return int(year), int(month)
        except (TypeError, ValueError):
            return None

    def load_year_sections(self, sections: list[YearlyPlanMonthSection]) -> None:
        palette = self.palette()
        base_brush = QBrush(palette.color(QPalette.ColorRole.Base))
        alt_brush = QBrush(palette.color(QPalette.ColorRole.AlternateBase))
        header_brush = QBrush(_MONTH_HEADER_BG)

        with sorting_paused(self):
            self.clearSpans()
            self._month_header_rows = {}
            self.setRowCount(0)

            total_rows = sum(1 + len(section.rows) for section in sections)
            self.setRowCount(total_rows)
            row_index = 0

            for section in sections:
                self._month_header_rows[int(section.month)] = row_index
                name, summary_text = format_month_header_parts(
                    section.month,
                    section.summary,
                    processed_at=section.processed_at,
                )
                self._fill_month_header_row(
                    row_index,
                    month=section.month,
                    name=name,
                    summary=summary_text,
                    brush=header_brush,
                )
                row_index += 1

                for item_offset, plan_row in enumerate(section.rows):
                    brush = base_brush if item_offset % 2 == 0 else alt_brush
                    self._fill_item_row(row_index, plan_row, brush=brush)
                    row_index += 1

    def load_rows(self, rows: list[YearlyPlanRow]) -> None:
        """Zpětná kompatibilita – jeden měsíc jako jedna sekce."""
        from moduly.rocni_plan.sluzby.yearly_plan_service import yearly_plan_service

        summary = yearly_plan_service.month_summary(rows)
        month = 1
        if rows and rows[0].slot_month is not None:
            month = int(rows[0].slot_month)
        self.load_year_sections(
            [YearlyPlanMonthSection(month=month, rows=rows, summary=summary)]
        )

    def _fill_month_header_row(
        self,
        row_index: int,
        *,
        month: int,
        name: str,
        summary: str,
        brush: QBrush,
    ) -> None:
        display = f"{name}{_HEADER_NAME_GAP}{summary}" if summary else name
        no_flags = Qt.ItemFlag.NoItemFlags
        for column in range(self.columnCount()):
            if column == COL_SOURCE:
                item = QTableWidgetItem(display)
            else:
                item = QTableWidgetItem("")
            item.setFlags(no_flags)
            item.setBackground(brush)
            item.setData(_ROLE_IS_MONTH_HEADER, True)
            item.setData(_ROLE_HEADER_MONTH, month)
            item.setData(_ROLE_HEADER_NAME, name)
            item.setData(_ROLE_HEADER_SUMMARY, summary)
            if column == COL_ID:
                item.setData(_ROLE_SLOT_MONTH, month)
            self.setItem(row_index, column, item)
        # Text přes Zdroj–Poznámka (COL_TITLE je Stretch – span začíná u Zdroje).
        self.setSpan(row_index, COL_SOURCE, 1, 5)

    def _fill_item_row(
        self,
        row_index: int,
        plan_row: YearlyPlanRow,
        *,
        brush: QBrush,
    ) -> None:
        if plan_row.plan_item_id is not None:
            stable_id = (
                int(plan_row.plan_item_id) * 100_000
                + (plan_row.slot_year or 0) * 12
                + (plan_row.slot_month or 0)
            )
            id_text = str(plan_row.plan_item_id)
        else:
            stable_id = 1_000_000_000 + (plan_row.activity_id or 0)
            id_text = f"P{plan_row.activity_id or 0}"

        id_item = create_typed_item(
            id_text,
            typed_text(id_text),
            stable_id=stable_id,
        )
        id_item.setData(_ROLE_PLAN_ITEM_ID, plan_row.plan_item_id)
        id_item.setData(_ROLE_KIND, plan_row.kind)
        id_item.setData(_ROLE_ACTIVITY_ID, plan_row.activity_id)
        id_item.setData(_ROLE_SLOT_YEAR, plan_row.slot_year)
        id_item.setData(_ROLE_SLOT_MONTH, plan_row.slot_month)
        id_item.setData(_ROLE_IS_RECURRING, bool(plan_row.is_recurring))
        id_item.setData(_ROLE_IS_MONTH_HEADER, False)
        id_item.setBackground(brush)
        self.setItem(row_index, COL_ID, id_item)

        cells = [
            (COL_SOURCE, plan_row.source_label or "—"),
            (COL_TITLE, (plan_row.title or "").strip() or "—"),
            (COL_STATUS, status_label(plan_row.display_status)),
            (COL_LINK, plan_row.link_text or "—"),
            (COL_NOTE, (plan_row.note or "").strip() or "—"),
        ]
        for column, value in cells:
            item = create_typed_item(value, typed_text(value), stable_id=stable_id)
            item.setBackground(brush)
            item.setData(_ROLE_IS_MONTH_HEADER, False)
            if column == COL_STATUS:
                item.setData(_ROLE_DISPLAY_STATUS, plan_row.display_status)
            self.setItem(row_index, column, item)
