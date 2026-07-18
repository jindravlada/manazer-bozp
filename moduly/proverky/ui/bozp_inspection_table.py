from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.info_tooltip import format_info_card
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
from moduly.proverky.constants import INSPECTION_SPIS_STATUSES


def _status_sort(status: str):
    try:
        order = INSPECTION_SPIS_STATUSES.index(status)
    except ValueError:
        order = len(INSPECTION_SPIS_STATUSES)
    return typed_status(order, label=status or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class BozpInspectionTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "ID",
            "Číslo",
            "Datum prověrky",
            "Pracoviště",
            "Specialista BOZP",
            "Závady",
            "Stav",
            "Název",
        ])

        self.setColumnHidden(0, True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setMinimumSectionSize(24)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        enable_typed_sorting(self)

    def load_inspections(self, inspections) -> None:
        with sorting_paused(self):
            self.setRowCount(len(inspections))

            for row, inspection in enumerate(inspections):
                record_id = int(getattr(inspection, "id", 0) or 0)
                tooltip = self._inspection_tooltip(inspection)
                inspection_date = getattr(inspection, "inspection_date", None)
                findings_count = getattr(inspection, "findings_count", None)
                status = getattr(inspection, "status", None) or ""
                number = getattr(inspection, "number", None) or "—"
                workplace = getattr(inspection, "workplace_name", None) or "—"
                lead = getattr(inspection, "lead_inspector_name", None) or "—"
                title = getattr(inspection, "title", None) or "—"

                cells = [
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        number,
                        _text_or_empty(number),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        self._format_date(inspection_date),
                        (
                            typed_date(inspection_date)
                            if inspection_date is not None
                            else typed_empty()
                        ),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        workplace,
                        _text_or_empty(workplace),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        lead,
                        _text_or_empty(lead),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        self._format_findings_count(findings_count),
                        (
                            typed_int(int(findings_count))
                            if findings_count is not None
                            else typed_empty()
                        ),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status or "—",
                        _status_sort(status) if status else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        title,
                        _text_or_empty(title),
                        stable_id=record_id,
                    ),
                ]
                for column, item in enumerate(cells):
                    item.setToolTip(tooltip)
                    self.setItem(row, column, item)

    @staticmethod
    def _format_date(value) -> str:
        if value is None:
            return "—"
        return value.strftime("%d.%m.%Y")

    @staticmethod
    def _format_findings_count(value) -> str:
        if value is None:
            return "—"
        return str(value)

    @staticmethod
    def _inspection_tooltip(inspection) -> str:
        return format_info_card(
            title=f"Prověrka BOZP {getattr(inspection, 'number', None) or '—'}",
            rows=[
                ("Datum:", BozpInspectionTable._format_date(getattr(inspection, "inspection_date", None))),
                ("Pracoviště:", getattr(inspection, "workplace_name", None) or "—"),
                ("Specialista BOZP:", getattr(inspection, "lead_inspector_name", None) or "—"),
                ("Stav:", getattr(inspection, "status", None) or "—"),
                ("Název:", getattr(inspection, "title", None) or "—"),
            ],
        )
