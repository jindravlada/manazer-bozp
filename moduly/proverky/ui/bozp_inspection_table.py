import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QPalette
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

COL_NUMBER = 1
_INSPECTION_NUMBER_RE = re.compile(r"^(\d+)/(\d+)$")
_NUMBER_SORT_YEAR_FACTOR = 1_000_000


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


def inspection_number_sort_value(number: str | None):
    """Složený klíč: rok, pak číselné pořadí. Neplatné/prázdné → empty."""
    raw = str(number or "").strip()
    if not raw or raw == "—":
        return typed_empty()
    match = _INSPECTION_NUMBER_RE.fullmatch(raw)
    if match is None:
        return typed_empty()
    sequence = int(match.group(1))
    year = int(match.group(2))
    return typed_int(year * _NUMBER_SORT_YEAR_FACTOR + sequence)

def _apply_count_emphasis(item, value: int) -> None:
    """
    Nenápadné zvýraznění počtů:
    - 0: běžné písmo + lehce šedá barva (secondary/disabled text)
    - >0: tučné písmo
    """
    font = item.font()
    font.setBold(value > 0)
    item.setFont(font)
    if value == 0:
        secondary = QPalette().color(QPalette.Disabled, QPalette.Text)
        item.setForeground(QBrush(secondary))


class BozpInspectionTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(14)
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
            "Pozorování",
            "Zjištění",
            "PKZ",
            "Ostatní",
            "Stav",
        ])

        # UX-TIP: Dlouhý význam jen v tooltipu hlavičky.
        header_col_poruseni = 7
        header_col_pkz = 11
        header_col_ostatni = 12
        poruseni_header = self.horizontalHeaderItem(header_col_poruseni)
        if poruseni_header is not None:
            poruseni_header.setToolTip("Porušení předpisů")

        pkz_header = self.horizontalHeaderItem(header_col_pkz)
        if pkz_header is not None:
            pkz_header.setToolTip("Příležitosti ke zlepšení")

        ostatni_header = self.horizontalHeaderItem(header_col_ostatni)
        if ostatni_header is not None:
            ostatni_header.setToolTip("Jiné nebo historické druhy zjištění")

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
        self.sortItems(COL_NUMBER, Qt.SortOrder.AscendingOrder)

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
                pozorovani_count = getattr(inspection, "pozorovani_count", None) or 0
                zjisteni_count = getattr(inspection, "zjisteni_count", None) or 0
                pkz_count = getattr(inspection, "pkz_count", None) or 0
                ostatni_count = getattr(inspection, "ostatni_count", None) or 0

                total_item = create_typed_item(
                    str(int(total_count)),
                    typed_int(int(total_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(total_item, int(total_count))

                zavady_item = create_typed_item(
                    str(int(zavady_count)),
                    typed_int(int(zavady_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(zavady_item, int(zavady_count))

                nedostatky_item = create_typed_item(
                    str(int(nedostatky_count)),
                    typed_int(int(nedostatky_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(nedostatky_item, int(nedostatky_count))

                poruseni_item = create_typed_item(
                    str(int(poruseni_predpisu_count)),
                    typed_int(int(poruseni_predpisu_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(poruseni_item, int(poruseni_predpisu_count))

                neshody_item = create_typed_item(
                    str(int(neshody_count)),
                    typed_int(int(neshody_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(neshody_item, int(neshody_count))

                pozorovani_item = create_typed_item(
                    str(int(pozorovani_count)),
                    typed_int(int(pozorovani_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(pozorovani_item, int(pozorovani_count))

                zjisteni_item = create_typed_item(
                    str(int(zjisteni_count)),
                    typed_int(int(zjisteni_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(zjisteni_item, int(zjisteni_count))

                pkz_item = create_typed_item(
                    str(int(pkz_count)),
                    typed_int(int(pkz_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(pkz_item, int(pkz_count))

                ostatni_item = create_typed_item(
                    str(int(ostatni_count)),
                    typed_int(int(ostatni_count)),
                    stable_id=record_id,
                )
                _apply_count_emphasis(ostatni_item, int(ostatni_count))

                cells = [
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        number,
                        inspection_number_sort_value(number),
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
                    total_item,
                    zavady_item,
                    nedostatky_item,
                    poruseni_item,
                    neshody_item,
                    pozorovani_item,
                    zjisteni_item,
                    pkz_item,
                    ostatni_item,
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
                ("Pozorování:", str(int(getattr(inspection, "pozorovani_count", 0) or 0))),
                ("Zjištění:", str(int(getattr(inspection, "zjisteni_count", 0) or 0))),
                ("Příležitosti ke zlepšení:", str(int(getattr(inspection, "pkz_count", 0) or 0))),
                ("Ostatní:", str(int(getattr(inspection, "ostatni_count", 0) or 0))),
                ("Stav:", getattr(inspection, "status", None) or "—"),
            ],
        )
