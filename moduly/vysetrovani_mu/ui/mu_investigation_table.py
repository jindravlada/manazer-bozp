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
from moduly.vysetrovani_mu.constants import (
    MU_STATUS_DOKONCENO,
    MU_STATUS_ODLOZENO,
    MU_STATUS_PROBIHA,
    SOURCE_TYPE_LABELS,
)
from moduly.vysetrovani_mu.sluzby.mu_number_utils import mu_number_sort_key

_MU_STATUS_ORDER = (
    MU_STATUS_PROBIHA,
    MU_STATUS_DOKONCENO,
    MU_STATUS_ODLOZENO,
)


def source_type_label(source_type: str) -> str:
    return SOURCE_TYPE_LABELS.get(source_type or "", source_type or "—")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


def _order_status(value: str, order: tuple[str, ...]):
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _mu_number_typed(number: str):
    year, sequence = mu_number_sort_key(number or "")
    if year == 0 and sequence == 0 and not (number or "").strip():
        return typed_empty()
    if year == 0 and sequence == 0:
        return typed_text(number)
    return typed_int(year * 100_000 + sequence)


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
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        enable_typed_sorting(self)

    def load_investigations(self, investigations):
        with sorting_paused(self):
            self.setRowCount(len(investigations))

            for row, investigation in enumerate(investigations):
                record_id = int(investigation.id)
                tooltip = self._investigation_tooltip(investigation)
                title = investigation.title.strip() if investigation.title else ""
                short = investigation.short_description.strip() if investigation.short_description else ""
                if title and short:
                    summary = title if title == short else f"{title} — {short}"
                else:
                    summary = title or short or "—"
                number = investigation.number or "—"
                status = investigation.status or "—"
                character = investigation.event_character or "—"
                source = self._source_display(investigation)
                started = (
                    "—"
                    if investigation.started_at is None
                    else investigation.started_at.strftime("%d.%m.%Y")
                )
                lead = investigation.lead_thp_worker_name or "—"

                cells = [
                    create_typed_item(
                        str(record_id),
                        typed_int(record_id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        number,
                        _mu_number_typed(None if number == "—" else number),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status,
                        _order_status(investigation.status or "", _MU_STATUS_ORDER)
                        if investigation.status
                        else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(character, _text_or_empty(character), stable_id=record_id),
                    create_typed_item(source, _text_or_empty(source), stable_id=record_id),
                    create_typed_item(
                        started,
                        typed_date(investigation.started_at)
                        if investigation.started_at is not None
                        else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(lead, _text_or_empty(lead), stable_id=record_id),
                    create_typed_item(
                        summary,
                        typed_text(title or short or ""),
                        stable_id=record_id,
                    ),
                ]

                for column, item in enumerate(cells):
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
