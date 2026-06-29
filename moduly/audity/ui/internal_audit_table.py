from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import format_info_card


class InternalAuditTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "ID",
            "Číslo",
            "Datum auditu",
            "Pracoviště",
            "Název",
            "Stav",
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

    def load_audits(self, audits):
        self.setRowCount(len(audits))

        for row, audit in enumerate(audits):
            tooltip = self._audit_tooltip(audit)
            values = [
                str(audit.id),
                audit.number or "—",
                "" if audit.audit_date is None else audit.audit_date.strftime("%d.%m.%Y"),
                audit.workplace or "—",
                audit.title or "—",
                audit.status or "—",
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.setItem(row, column, item)

    def _audit_tooltip(self, audit) -> str:
        audit_date = "—" if audit.audit_date is None else audit.audit_date.strftime("%d.%m.%Y")

        return format_info_card(
            title=f"Interní audit {audit.number or '—'}",
            rows=[
                ("Datum auditu:", audit_date),
                ("Pracoviště:", audit.workplace or "—"),
                ("Název:", audit.title or "—"),
                ("Stav:", audit.status or "—"),
            ],
        )
