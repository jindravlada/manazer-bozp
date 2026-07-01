from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import format_info_card
from moduly.audity.constants import PLANNED_MONTH_NAMES, PLANNED_MONTH_NOT_SET_LABEL


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
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

    def load_audits(self, audits) -> None:
        self.setRowCount(len(audits))

        for row, audit in enumerate(audits):
            tooltip = self._audit_tooltip(audit)
            values = [
                str(getattr(audit, "id", "")),
                getattr(audit, "number", None) or "—",
                self._format_year(getattr(audit, "year", None)),
                self._format_planned_month(getattr(audit, "planned_month", None)),
                getattr(audit, "workplace_name", None) or "—",
                self._format_date(getattr(audit, "audit_date", None)),
                getattr(audit, "status", None) or "—",
                getattr(audit, "audit_type", None) or "—",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
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
