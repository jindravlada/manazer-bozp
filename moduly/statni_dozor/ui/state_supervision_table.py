"""Tabulka přehledu Státního dozoru v Agendě."""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
)

from core.theme.status_colors import (
    STATUS_DONE_BG,
    STATUS_IN_PROGRESS_BG,
    STATUS_NEUTRAL_BG,
    STATUS_WAITING_BG,
    STATUS_WARNING_BG,
)
from core.widgets.table_utils import apply_cell_tooltip
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_status,
    typed_text,
)
from moduly.statni_dozor.constants import (
    COL_STATUS,
    COLUMN_HEADERS,
    EMPTY_VALUE,
    STATE_SUPERVISION_STATUS_HINTS,
    STATE_SUPERVISION_STATUS_LABELS,
    STATE_SUPERVISION_STATUS_ORDER,
    STATUS_ANNOUNCED,
    STATUS_CANCELLED,
    STATUS_CLOSED,
    STATUS_IN_PROGRESS,
    STATUS_MEASURES_IN_PROGRESS,
    STATUS_OBJECTIONS_PERIOD,
    STATUS_PREPARATION,
    STATUS_WAITING_AUTHORITY_CONFIRMATION,
    STATUS_WAITING_PROTOCOL,
)
from moduly.statni_dozor.modely.state_supervision import StateSupervision

_ROLE_ID = Qt.ItemDataRole.UserRole
_CUBE_SIZE = 12

STATUS_CUBE_COLORS: dict[str, str] = {
    STATUS_ANNOUNCED: STATUS_WAITING_BG,
    STATUS_PREPARATION: STATUS_WARNING_BG,
    STATUS_IN_PROGRESS: STATUS_IN_PROGRESS_BG,
    STATUS_WAITING_PROTOCOL: STATUS_WAITING_BG,
    STATUS_OBJECTIONS_PERIOD: STATUS_IN_PROGRESS_BG,
    STATUS_MEASURES_IN_PROGRESS: STATUS_IN_PROGRESS_BG,
    STATUS_WAITING_AUTHORITY_CONFIRMATION: STATUS_WAITING_BG,
    STATUS_CLOSED: STATUS_DONE_BG,
    STATUS_CANCELLED: STATUS_NEUTRAL_BG,
}


def format_supervision_date(value: datetime | date | None) -> str:
    if value is None:
        return EMPTY_VALUE
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d.%m.%Y")


def display_or_dash(value: str | None) -> str:
    text = str(value or "").strip()
    return text if text else EMPTY_VALUE


def status_cube_tooltip(status: str) -> str:
    label = STATE_SUPERVISION_STATUS_LABELS.get(status, status)
    hint = STATE_SUPERVISION_STATUS_HINTS.get(status, "")
    if hint:
        return f"{label} — {hint}"
    return label


def effective_start_at(record: StateSupervision) -> datetime | None:
    return record.started_at or record.planned_start_at


def decisive_datetime(record: StateSupervision) -> datetime | None:
    return record.started_at or record.planned_start_at or record.created_at


def _color_from_role(value) -> QColor | None:
    if value is None:
        return None
    if isinstance(value, QBrush):
        color = value.color()
        return color if color.isValid() else None
    if isinstance(value, QColor):
        return value if value.isValid() else None
    color = QColor(value)
    return color if color.isValid() else None


class StatusCubeDelegate(QStyledItemDelegate):
    """Kreslí barevnou kostičku stavu; výběr řádku barvu nepřebije."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.backgroundBrush = QBrush()
        opt.text = ""
        widget = option.widget
        style = widget.style() if widget is not None else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
        else:
            super().paint(painter, option, index)

        fill = _color_from_role(index.data(Qt.ItemDataRole.BackgroundRole))
        if fill is None:
            return

        painter.save()
        rect = option.rect
        x = rect.x() + (rect.width() - _CUBE_SIZE) // 2
        y = rect.y() + (rect.height() - _CUBE_SIZE) // 2
        cube = QRect(x, y, _CUBE_SIZE, _CUBE_SIZE)
        painter.setBrush(QBrush(fill))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        ring = QColor("#ffffff") if selected or fill.lightness() < 40 else QColor("#555555")
        painter.setPen(QPen(ring, 1))
        painter.drawRect(cube)
        painter.restore()


class StateSupervisionTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        enable_typed_sorting(self)
        self.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        self.setItemDelegateForColumn(COL_STATUS, StatusCubeDelegate(self))

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def load_records(self, records: list[StateSupervision]) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(records))
            for row, record in enumerate(records):
                self._fill_row(row, record)

    def _fill_row(self, row: int, record: StateSupervision) -> None:
        record_id = int(record.id)
        status = str(record.status or "")
        status_item = create_typed_item(
            "",
            typed_status(
                _status_order(status),
                label=STATE_SUPERVISION_STATUS_LABELS.get(status, status),
            ),
            stable_id=record_id,
        )
        status_item.setData(_ROLE_ID, record_id)
        status_item.setBackground(QColor(STATUS_CUBE_COLORS.get(status, STATUS_NEUTRAL_BG)))
        status_item.setToolTip(status_cube_tooltip(status))

        authority = display_or_dash(record.authority_name)
        authority_item = create_typed_item(
            authority,
            typed_text(authority) if authority != EMPTY_VALUE else typed_empty(),
            stable_id=record_id,
        )
        apply_cell_tooltip(authority_item, record.authority_name)

        workplace = display_or_dash(record.workplace_name_snapshot)
        workplace_item = create_typed_item(
            workplace,
            typed_text(workplace) if workplace != EMPTY_VALUE else typed_empty(),
            stable_id=record_id,
        )
        if workplace != EMPTY_VALUE:
            apply_cell_tooltip(workplace_item, record.workplace_name_snapshot)

        started_at = effective_start_at(record)
        started_display = format_supervision_date(started_at)
        started_item = create_typed_item(
            started_display,
            typed_date(started_at.date() if isinstance(started_at, datetime) else started_at)
            if started_at is not None
            else typed_empty(),
            stable_id=record_id,
        )
        if record.started_at is not None:
            started_item.setToolTip(
                f"Skutečné zahájení: {format_supervision_date(record.started_at)}"
            )
        elif record.planned_start_at is not None:
            started_item.setToolTip(
                f"Plánované zahájení: {format_supervision_date(record.planned_start_at)}"
            )

        ended_display = format_supervision_date(record.ended_at)
        ended_item = create_typed_item(
            ended_display,
            typed_date(
                record.ended_at.date()
                if isinstance(record.ended_at, datetime)
                else record.ended_at
            )
            if record.ended_at is not None
            else typed_empty(),
            stable_id=record_id,
        )

        result = display_or_dash(record.result)
        result_item = create_typed_item(
            result,
            typed_text(result) if result != EMPTY_VALUE else typed_empty(),
            stable_id=record_id,
        )
        if result != EMPTY_VALUE:
            apply_cell_tooltip(result_item, record.result)

        cells = (
            status_item,
            authority_item,
            workplace_item,
            started_item,
            ended_item,
            result_item,
        )
        for column, item in enumerate(cells):
            self.setItem(row, column, item)


def _status_order(status: str) -> int:
    try:
        return STATE_SUPERVISION_STATUS_ORDER.index(status)
    except ValueError:
        return len(STATE_SUPERVISION_STATUS_ORDER)
