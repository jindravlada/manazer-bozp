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
from moduly.audity.constants import (
    AUDIT_SPIS_STATUSES,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)

COL_ID = 0
COL_NUMBER = 1
COL_YEAR = 2
COL_PLANNED_MONTH = 3
COL_WORKPLACE = 4
COL_AUDIT_DATE = 5
COL_FINDINGS_TOTAL = 6
COL_ZAVADY = 7
COL_NEDOSTATKY = 8
COL_PORUSENI = 9
COL_NESHODY = 10
COL_POZOROVANI = 11
COL_ZJISTENI = 12
COL_PKZ = 13
COL_OSTATNI = 14
COL_STATUS = 15
COL_AUDIT_TYPE = 16


def _status_sort(status: str):
    try:
        order = AUDIT_SPIS_STATUSES.index(status)
    except ValueError:
        order = len(AUDIT_SPIS_STATUSES)
    return typed_status(order, label=status or "")


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


def _count_item(value: int, record_id: int):
    count = int(value or 0)
    item = create_typed_item(
        str(count),
        typed_int(count),
        stable_id=record_id,
    )
    _apply_count_emphasis(item, count)
    return item


class AuditTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(17)
        self.setHorizontalHeaderLabels([
            "ID",
            "Číslo auditu",
            "Rok",
            "Plánovaný měsíc",
            "Auditovaný provoz",
            "Plánované datum",
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
            "Typ auditu",
        ])

        poruseni_header = self.horizontalHeaderItem(COL_PORUSENI)
        if poruseni_header is not None:
            poruseni_header.setToolTip("Porušení předpisů")

        pkz_header = self.horizontalHeaderItem(COL_PKZ)
        if pkz_header is not None:
            pkz_header.setToolTip("Příležitosti ke zlepšení")

        ostatni_header = self.horizontalHeaderItem(COL_OSTATNI)
        if ostatni_header is not None:
            ostatni_header.setToolTip(
                "Zahrnuje ostatní, příčinné a historické druhy zjištění."
            )

        self.setColumnHidden(COL_ID, True)
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
                total_count = getattr(audit, "findings_total_count", None) or 0
                zavady_count = getattr(audit, "zavady_count", None) or 0
                nedostatky_count = getattr(audit, "nedostatky_count", None) or 0
                poruseni_count = getattr(audit, "poruseni_count", None) or 0
                neshody_count = getattr(audit, "neshody_count", None) or 0
                pozorovani_count = getattr(audit, "pozorovani_count", None) or 0
                zjisteni_count = getattr(audit, "zjisteni_count", None) or 0
                pkz_count = getattr(audit, "pkz_count", None) or 0
                ostatni_count = getattr(audit, "ostatni_count", None) or 0

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
                    _count_item(total_count, record_id),
                    _count_item(zavady_count, record_id),
                    _count_item(nedostatky_count, record_id),
                    _count_item(poruseni_count, record_id),
                    _count_item(neshody_count, record_id),
                    _count_item(pozorovani_count, record_id),
                    _count_item(zjisteni_count, record_id),
                    _count_item(pkz_count, record_id),
                    _count_item(ostatni_count, record_id),
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
                ("Plánované datum:", AuditTable._format_date(getattr(audit, "audit_date", None))),
                ("Celkem:", str(int(getattr(audit, "findings_total_count", 0) or 0))),
                ("Závady:", str(int(getattr(audit, "zavady_count", 0) or 0))),
                ("Nedostatky:", str(int(getattr(audit, "nedostatky_count", 0) or 0))),
                ("Porušení předpisů:", str(int(getattr(audit, "poruseni_count", 0) or 0))),
                ("Neshody:", str(int(getattr(audit, "neshody_count", 0) or 0))),
                ("Pozorování:", str(int(getattr(audit, "pozorovani_count", 0) or 0))),
                ("Zjištění:", str(int(getattr(audit, "zjisteni_count", 0) or 0))),
                ("Příležitosti ke zlepšení:", str(int(getattr(audit, "pkz_count", 0) or 0))),
                ("Ostatní:", str(int(getattr(audit, "ostatni_count", 0) or 0))),
                ("Stav:", getattr(audit, "status", None) or "—"),
                ("Typ auditu:", getattr(audit, "audit_type", None) or "—"),
            ],
        )
