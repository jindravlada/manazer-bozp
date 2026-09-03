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

        self.setColumnCount(12)
        self.setHorizontalHeaderLabels([
            "ID",
            "Číslo",
            "Datum prověrky",
            "Pracoviště",
            "Celkem",
            "Závady",
            "Nedostatky",
            "Porušení",
            "Neshody",
            "PKZ",
            "Ostatní",
            "Stav",
        ])

        # UX-TIP: Dlouhý význam jen v tooltipu hlavičky.
        header_col_poruseni = 7
        header_col_pkz = 9
        poruseni_header = self.horizontalHeaderItem(header_col_poruseni)
        if poruseni_header is not None:
            poruseni_header.setToolTip("Porušení předpisů")

        pkz_header = self.horizontalHeaderItem(header_col_pkz)
        if pkz_header is not None:
            pkz_header.setToolTip("Příležitosti ke zlepšení")

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

    def load_inspections(self, inspections) -> None:
        with sorting_paused(self):
            self.setRowCount(len(inspections))

            for row, inspection in enumerate(inspections):
                record_id = int(getattr(inspection, "id", 0) or 0)
                tooltip = self._inspection_tooltip(inspection)
                inspection_date = getattr(inspection, "inspection_date", None)
                status = getattr(inspection, "status", None) or ""
                number = getattr(inspection, "number", None) or "—"
                workplace = getattr(inspection, "workplace_name", None) or "—"
                total_count = getattr(inspection, "findings_total_count", None) or 0
                zavady_count = getattr(inspection, "zavady_count", None) or 0
                nedostatky_count = getattr(inspection, "nedostatky_count", None) or 0
                poruseni_predpisu_count = (
                    getattr(inspection, "poruseni_predpisu_count", None) or 0
                )
                neshody_count = getattr(inspection, "neshody_count", None) or 0
                pkz_count = getattr(inspection, "pkz_count", None) or 0
                ostatni_count = getattr(inspection, "ostatni_count", None) or 0

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
                        str(int(total_count)),
                        typed_int(int(total_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(int(zavady_count)),
                        typed_int(int(zavady_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(int(nedostatky_count)),
                        typed_int(int(nedostatky_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(int(poruseni_predpisu_count)),
                        typed_int(int(poruseni_predpisu_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(int(neshody_count)),
                        typed_int(int(neshody_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(int(pkz_count)),
                        typed_int(int(pkz_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        str(int(ostatni_count)),
                        typed_int(int(ostatni_count)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status or "—",
                        _status_sort(status) if status else typed_empty(),
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
    def _inspection_tooltip(inspection) -> str:
        total_count = int(getattr(inspection, "findings_total_count", 0) or 0)
        return format_info_card(
            title=f"Prověrka BOZP {getattr(inspection, 'number', None) or '—'}",
            rows=[
                ("Datum:", BozpInspectionTable._format_date(getattr(inspection, "inspection_date", None))),
                ("Pracoviště:", getattr(inspection, "workplace_name", None) or "—"),
                ("Celkem:", str(total_count)),
                ("Závady:", str(int(getattr(inspection, "zavady_count", 0) or 0))),
                ("Nedostatky:", str(int(getattr(inspection, "nedostatky_count", 0) or 0))),
                ("Porušení předpisů:", str(int(getattr(inspection, "poruseni_predpisu_count", 0) or 0))),
                ("Neshody:", str(int(getattr(inspection, "neshody_count", 0) or 0))),
                ("Příležitosti ke zlepšení:", str(int(getattr(inspection, "pkz_count", 0) or 0))),
                ("Ostatní:", str(int(getattr(inspection, "ostatni_count", 0) or 0))),
                ("Stav:", getattr(inspection, "status", None) or "—"),
            ],
        )
