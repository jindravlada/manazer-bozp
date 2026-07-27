from PySide6.QtWidgets import QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_COL_DATE,
    RISK_MEASURE_REVIEW_COL_ID,
    RISK_MEASURE_REVIEW_COL_NUMBER,
    RISK_MEASURE_REVIEW_COL_OPERATION,
    RISK_MEASURE_REVIEW_COL_REVIEWER,
    RISK_MEASURE_REVIEW_COL_STATUS,
    RISK_MEASURE_REVIEW_COL_WORKPLACE,
    RISK_MEASURE_REVIEW_COL_WORKPLACE_PART,
    RISK_MEASURE_REVIEW_COLUMN_COUNT,
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_TABLE_HEADERS,
    format_risk_measure_review_status_label,
)

_STATUS_ORDER = (
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
)


def _status_sort(status: str):
    try:
        order = _STATUS_ORDER.index(status)
    except ValueError:
        order = len(_STATUS_ORDER)
    return typed_status(order, label=status or "")


class RiskMeasureReviewTable(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(RISK_MEASURE_REVIEW_COLUMN_COUNT)
        self.setHorizontalHeaderLabels(RISK_MEASURE_REVIEW_TABLE_HEADERS)
        self.setColumnHidden(RISK_MEASURE_REVIEW_COL_ID, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_reviews(self, reviews) -> None:
        with sorting_paused(self):
            self.setRowCount(len(reviews))
            for row, review in enumerate(reviews):
                record_id = int(review.id)
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_ID,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_NUMBER,
                    create_typed_item(
                        review.review_number or "",
                        typed_text(review.review_number),
                        stable_id=record_id,
                    ),
                )
                date_text = (
                    review.review_date.strftime("%d.%m.%Y") if review.review_date else ""
                )
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_DATE,
                    create_typed_item(
                        date_text,
                        typed_date(review.review_date) if review.review_date else typed_empty(),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_OPERATION,
                    create_typed_item(
                        review.operation_name or "",
                        typed_text(review.operation_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_WORKPLACE,
                    create_typed_item(
                        review.workplace_name or "",
                        typed_text(review.workplace_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_WORKPLACE_PART,
                    create_typed_item(
                        review.workplace_part_name or "",
                        typed_text(review.workplace_part_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_REVIEWER,
                    create_typed_item(
                        review.reviewer_person_name or "",
                        typed_text(review.reviewer_person_name),
                        stable_id=record_id,
                    ),
                )
                status_label = format_risk_measure_review_status_label(review.status)
                self.setItem(
                    row,
                    RISK_MEASURE_REVIEW_COL_STATUS,
                    create_typed_item(
                        status_label,
                        _status_sort(review.status),
                        stable_id=record_id,
                    ),
                )

    def selected_review_id(self) -> int | None:
        rows = self.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.item(rows[0].row(), RISK_MEASURE_REVIEW_COL_ID)
        if item is None:
            return None
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None
