from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from core.widgets.info_tooltip import format_info_card


class ControlTable(QTableWidget):
    LEGACY_DEFECT_MAP = {
        "Bez závad": "NE",
        "Se závadami": "ANO",
        "Neprovedena": "NE",
    }

    def __init__(self):
        super().__init__()

        self.setColumnCount(8)
        self.setHorizontalHeaderLabels([
            "ID",
            "Datum",
            "Kontrolní list",
            "THP pracovník",
            "Pracoviště",
            "Závada",
            "SD",
            "Poznámka",
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

    def load_controls(self, controls):
        self.setRowCount(len(controls))

        for row, control in enumerate(controls):
            tooltip = self._control_tooltip(control)
            note_preview = self._note_preview(control.note)

            values = [
                str(control.id),
                "" if control.inspection_date is None else control.inspection_date.strftime("%d.%m.%Y"),
                control.title or "—",
                control.inspector_name or "—",
                control.workplace_name or "—",
                self._defect_display(control.result),
                control.sd_reference or "—",
                note_preview,
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.setItem(row, column, item)

    def _defect_display(self, result: str) -> str:
        if result in ("ANO", "NE"):
            return result
        return self.LEGACY_DEFECT_MAP.get(result or "", result or "—")

    def _note_preview(self, note: str, max_len: int = 80) -> str:
        text = (note or "").strip()
        if not text:
            return "—"
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"

    def _control_tooltip(self, control) -> str:
        inspection_date = (
            "—" if control.inspection_date is None else control.inspection_date.strftime("%d.%m.%Y")
        )

        rows = [
            ("Datum kontroly:", inspection_date),
            ("Kontrolní list:", control.title or "—"),
            ("THP pracovník:", control.inspector_name or "—"),
            ("Pracoviště:", control.workplace_name or "—"),
            ("Závada:", self._defect_display(control.result)),
            ("SD:", control.sd_reference or "—"),
        ]

        return format_info_card(
            title=f"Kontrola:\n{control.title or '—'}",
            rows=rows,
            note=control.note or "",
        )
