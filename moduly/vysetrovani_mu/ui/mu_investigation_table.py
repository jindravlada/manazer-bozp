from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import format_info_card
from moduly.vysetrovani_mu.constants import SOURCE_TYPE_LABELS


def source_type_label(source_type: str) -> str:
    return SOURCE_TYPE_LABELS.get(source_type or "", source_type or "—")


class MuInvestigationTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "ID",
            "Číslo",
            "Stav",
            "Charakter události",
            "Zdroj",
            "Zahájeno",
            "Vedoucí šetření",
            "Název / stručný popis",
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

    def load_investigations(self, investigations):
        self.setRowCount(len(investigations))

        for row, investigation in enumerate(investigations):
            tooltip = self._investigation_tooltip(investigation)
            title = investigation.title.strip() if investigation.title else ""
            short = investigation.short_description.strip() if investigation.short_description else ""
            if title and short:
                summary = title if title == short else f"{title} — {short}"
            else:
                summary = title or short or "—"

            values = [
                str(investigation.id),
                investigation.number or "—",
                investigation.status or "—",
                investigation.event_character or "—",
                self._source_display(investigation),
                "—" if investigation.started_at is None else investigation.started_at.strftime("%d.%m.%Y"),
                investigation.lead_thp_worker_name or "—",
                summary,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.setItem(row, column, item)

    def _source_display(self, investigation) -> str:
        label = source_type_label(investigation.source_type)
        source_label = (investigation.source_label or "").strip()
        if source_label:
            return f"{label} — {source_label}"
        return label

    def _investigation_tooltip(self, investigation) -> str:
        started = "—" if investigation.started_at is None else investigation.started_at.strftime("%d.%m.%Y")

        return format_info_card(
            title=f"Vyšetřování MU {investigation.number or '—'}",
            rows=[
                ("Stav:", investigation.status or "—"),
                ("Charakter události:", investigation.event_character or "—"),
                ("Zdroj:", self._source_display(investigation)),
                ("Zahájeno:", started),
                ("Vedoucí šetření:", investigation.lead_thp_worker_name or "—"),
                ("Název:", investigation.title or "—"),
            ],
            note=investigation.short_description or "",
        )
