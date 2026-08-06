from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

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
from moduly.audity.constants import (
    AUDIT_SPIS_STATUSES,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)


def _status_sort(status: str):
    try:
        order = AUDIT_SPIS_STATUSES.index(status)
    except ValueError:
        order = len(AUDIT_SPIS_STATUSES)
    return typed_status(order, label=status or "")


class AuditTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "ID",
            "Číslo auditu",
            "Rok",
            "Plánovaný měsíc",
            "Auditovaný provoz",
            "Datum auditu",
            "Stav",
            "Typ auditu",
        ])

        self.setColumnHidden(0, True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setMinimumSectionSize(24)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        enable_typed_sorting(self)

    def load_audits(self, audits) -> None:
        with sorting_paused(self):
            self.setRowCount(len(audits))

            for row, audit in enumerate(audits):
                record_id = int(getattr(audit, "id", 0) or 0)
                tooltip = self._audit_tooltip(audit)
                year = getattr(audit, "year", None)
                planned_month = getattr(audit, "planned_month", None)
                audit_date = getattr(audit, "audit_date", None)
                status = getattr(audit, "status", None) or ""
                number = getattr(audit, "number", None) or "—"
                workplace = getattr(audit, "workplace_name", None) or "—"
                audit_type = getattr(audit, "audit_type", None) or "—"

                cells = [
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        number,
                        typed_text(None if number == "—" else number),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        self._format_year(year),
                        typed_int(year) if year is not None else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        self._format_planned_month(planned_month),
                        (
                            typed_int(int(planned_month))
                            if planned_month is not None and 1 <= int(planned_month) <= 12
                            else typed_empty()
                        ),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        workplace,
                        typed_text(None if workplace == "—" else workplace),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        self._format_date(audit_date),
                        typed_date(audit_date) if audit_date is not None else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status or "—",
                        _status_sort(status) if status else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        audit_type,
                        typed_text(None if audit_type == "—" else audit_type),
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
    def _format_year(value) -> str:
        if value is None:
            return "—"
        return str(value)

    @staticmethod
    def _format_planned_month(value) -> str:
        if value is None or not 1 <= int(value) <= 12:
            return PLANNED_MONTH_NOT_SET_LABEL
        return PLANNED_MONTH_NAMES[int(value) - 1]

    @staticmethod
    def _audit_tooltip(audit) -> str:
        return format_info_card(
            title=f"Audit {getattr(audit, 'number', None) or '—'}",
            rows=[
                ("Rok:", AuditTable._format_year(getattr(audit, "year", None))),
                (
                    "Plánovaný měsíc:",
                    AuditTable._format_planned_month(getattr(audit, "planned_month", None)),
                ),
                ("Auditovaný provoz:", getattr(audit, "workplace_name", None) or "—"),
                ("Datum auditu:", AuditTable._format_date(getattr(audit, "audit_date", None))),
                ("Stav:", getattr(audit, "status", None) or "—"),
                ("Typ auditu:", getattr(audit, "audit_type", None) or "—"),
            ],
        )
