from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QTableWidget

from core.widgets.table_utils import apply_cell_tooltip
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUSES,
    COL_ID,
    COL_MEETING_DATE,
    COL_NUMBER,
    COL_PBP,
    COL_PLACE,
    COL_STATUS,
    COL_SUBJECT,
    COL_VALIDITY,
    COLUMN_COUNT,
    TABLE_HEADERS,
)
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    normalize_coordination_status,
    status_label,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import (
    PbpFreshnessCache,
    pbp_freshness_color,
    pbp_freshness_sort_order,
)
from moduly.koordinace_bozp.sluzby.coordination_validity import (
    coordination_validity_color,
    coordination_validity_label,
    coordination_validity_sort_order,
    coordination_validity_state,
)


def _status_sort(status: str):
    normalized = normalize_coordination_status(status)
    try:
        order = BOZP_COORDINATION_STATUSES.index(normalized)
    except ValueError:
        order = len(BOZP_COORDINATION_STATUSES)
    return typed_status(order, label=status_label(normalized))


class BozpCoordinationTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.setColumnHidden(COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        enable_typed_sorting(self)

    def load_coordinations(
        self,
        coordinations,
        *,
        today=None,
        pbp_cache: PbpFreshnessCache | None = None,
    ) -> None:
        freshness_cache = pbp_cache or PbpFreshnessCache()
        with sorting_paused(self):
            self.setRowCount(len(coordinations))
            for row, item in enumerate(coordinations):
                record_id = int(item.id)
                label = status_label(item.status)
                display_status = label if item.active else f"{label} (neaktivní)"
                validity_state = coordination_validity_state(item.valid_to, today=today)
                validity_label = coordination_validity_label(item.valid_to, today=today)
                freshness = freshness_cache.evaluate(item, today=today)
                self.setItem(
                    row,
                    COL_ID,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    COL_NUMBER,
                    create_typed_item(
                        item.coordination_number or "",
                        typed_text(item.coordination_number),
                        stable_id=record_id,
                    ),
                )
                meeting = item.meeting_date
                meeting_text = meeting.strftime("%d.%m.%Y") if meeting else ""
                self.setItem(
                    row,
                    COL_MEETING_DATE,
                    create_typed_item(
                        meeting_text,
                        typed_date(meeting),
                        stable_id=record_id,
                    ),
                )
                place_text = item.place or ""
                place_item = create_typed_item(
                    place_text,
                    typed_text(item.place),
                    stable_id=record_id,
                )
                apply_cell_tooltip(place_item, place_text)
                self.setItem(row, COL_PLACE, place_item)
                subject_text = item.subject or ""
                subject_item = create_typed_item(
                    subject_text,
                    typed_text(item.subject),
                    stable_id=record_id,
                )
                apply_cell_tooltip(subject_item, subject_text)
                self.setItem(row, COL_SUBJECT, subject_item)
                status_item = create_typed_item(
                    display_status,
                    _status_sort(item.status),
                    stable_id=record_id,
                )
                if not item.active:
                    status_item.setData(Qt.ItemDataRole.UserRole + 1, False)
                self.setItem(row, COL_STATUS, status_item)

                validity_item = create_typed_item(
                    validity_label,
                    typed_status(
                        coordination_validity_sort_order(validity_state),
                        label=validity_label,
                    ),
                    stable_id=record_id,
                )
                validity_item.setForeground(
                    QBrush(QColor(coordination_validity_color(validity_state)))
                )
                validity_item.setData(Qt.ItemDataRole.UserRole, validity_state)
                self.setItem(row, COL_VALIDITY, validity_item)

                pbp_item = create_typed_item(
                    freshness.label,
                    typed_status(
                        pbp_freshness_sort_order(freshness.state),
                        label=freshness.label,
                    ),
                    stable_id=record_id,
                )
                pbp_item.setForeground(QBrush(QColor(pbp_freshness_color(freshness.state))))
                pbp_item.setToolTip(freshness.tooltip)
                pbp_item.setData(Qt.ItemDataRole.UserRole, freshness.state)
                self.setItem(row, COL_PBP, pbp_item)

    def selected_coordination_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), COL_ID)
        if item is None:
            return None
        return int(item.text())

    def clear_selection(self) -> None:
        self.clearSelection()
