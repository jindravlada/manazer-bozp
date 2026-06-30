from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import format_info_card


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

    def load_inspections(self, inspections) -> None:
        self.setRowCount(len(inspections))

        for row, inspection in enumerate(inspections):
            tooltip = self._inspection_tooltip(inspection)
            values = [
                str(getattr(inspection, "id", "")),
                getattr(inspection, "number", None) or "—",
                self._format_date(getattr(inspection, "inspection_date", None)),
                getattr(inspection, "workplace_name", None) or "—",
                getattr(inspection, "lead_inspector_name", None) or "—",
                self._format_findings_count(getattr(inspection, "findings_count", None)),
                getattr(inspection, "status", None) or "—",
                getattr(inspection, "title", None) or "—",
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
