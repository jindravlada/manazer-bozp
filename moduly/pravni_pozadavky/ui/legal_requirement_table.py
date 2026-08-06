from datetime import date

from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget

from core.widgets.info_tooltip import set_widget_tooltip
from core.widgets.text_preview import DEFAULT_TEXT_PREVIEW_LENGTH, truncate_text_preview
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
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_CASTECNE_SPLNENO,
    COMPLIANCE_NENI_RELEVANTNI,
    COMPLIANCE_NESPLNENO,
    COMPLIANCE_SPLNENO,
    COMPLIANCE_STATUS_LABELS,
    PERIODICITY_BEZ,
    PERIODICITY_CTVRTLETNE,
    PERIODICITY_DVA_ROKY,
    PERIODICITY_LABELS,
    PERIODICITY_MESICNE,
    PERIODICITY_NA_POZADANI,
    PERIODICITY_POLOLETNE,
    PERIODICITY_ROCNE,
    PERIODICITY_TRI_ROKY,
    legal_requirement_process_label,
    legal_requirement_responsible_label,
    parse_process_code,
)

COL_ID = 0
COL_CODE = 1
COL_PROCESS = 2
COL_SUMMARY = 3
COL_RESPONSIBLE = 4
COL_STATUS = 5
COL_NEXT_CHECK = 6
COL_LAST_CHECK = 7
COL_PERIODICITY = 8
COLUMN_COUNT = 9
PROCESS_NAME_PREVIEW_LENGTH = 40

COMPLIANCE_ORDER = (
    COMPLIANCE_SPLNENO,
    COMPLIANCE_CASTECNE_SPLNENO,
    COMPLIANCE_NESPLNENO,
    COMPLIANCE_NENI_RELEVANTNI,
)

PERIODICITY_ORDER = (
    PERIODICITY_MESICNE,
    PERIODICITY_CTVRTLETNE,
    PERIODICITY_POLOLETNE,
    PERIODICITY_ROCNE,
    PERIODICITY_DVA_ROKY,
    PERIODICITY_TRI_ROKY,
    PERIODICITY_NA_POZADANI,
    PERIODICITY_BEZ,
)


def _order_status(value: str, order: tuple[str, ...]):
    if not value:
        return typed_empty()
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _format_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


class LegalRequirementTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels([
            "ID",
            "Kód",
            "Proces",
            "Způsob plnění",
            "Vlastník procesu",
            "Stav plnění",
            "Další ověření",
            "Poslední ověření",
            "Periodicita",
        ])

        self.setColumnHidden(COL_ID, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_SUMMARY, QHeaderView.Stretch)
        for column in (
            COL_CODE,
            COL_PROCESS,
            COL_RESPONSIBLE,
            COL_STATUS,
            COL_NEXT_CHECK,
            COL_LAST_CHECK,
            COL_PERIODICITY,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

        enable_typed_sorting(self)

    def clear_selection(self) -> None:
        self.clearSelection()
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.clearCurrentIndex()

    def load_requirements(self, requirements) -> None:
        today = date.today()

        with sorting_paused(self):
            self.setRowCount(len(requirements))

            for row, requirement in enumerate(requirements):
                record_id = int(requirement.id)
                self.setItem(
                    row,
                    COL_ID,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    COL_CODE,
                    create_typed_item(
                        requirement.process_code,
                        self._process_code_sort(requirement.process_code),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_PROCESS,
                    self._preview_item(
                        record_id,
                        legal_requirement_process_label(requirement),
                        max_length=PROCESS_NAME_PREVIEW_LENGTH,
                    ),
                )
                self.setItem(
                    row,
                    COL_SUMMARY,
                    self._preview_item(record_id, requirement.requirement_summary),
                )
                self.setItem(
                    row,
                    COL_RESPONSIBLE,
                    create_typed_item(
                        legal_requirement_responsible_label(requirement),
                        typed_text(legal_requirement_responsible_label(requirement)),
                        stable_id=record_id,
                    ),
                )
                status_label = COMPLIANCE_STATUS_LABELS.get(
                    requirement.compliance_status,
                    requirement.compliance_status,
                )
                self.setItem(
                    row,
                    COL_STATUS,
                    create_typed_item(
                        status_label,
                        _order_status(requirement.compliance_status, COMPLIANCE_ORDER),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_LAST_CHECK,
                    create_typed_item(
                        _format_date(requirement.last_verification_date),
                        typed_date(requirement.last_verification_date),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_NEXT_CHECK,
                    create_typed_item(
                        _format_date(requirement.next_verification_date),
                        typed_date(requirement.next_verification_date),
                        stable_id=record_id,
                    ),
                )
                periodicity_label = PERIODICITY_LABELS.get(
                    requirement.verification_periodicity,
                    requirement.verification_periodicity,
                )
                self.setItem(
                    row,
                    COL_PERIODICITY,
                    create_typed_item(
                        periodicity_label,
                        _order_status(requirement.verification_periodicity, PERIODICITY_ORDER),
                        stable_id=record_id,
                    ),
                )

                self._apply_row_style(row, requirement, today)

    @staticmethod
    def _process_code_sort(code: str):
        parts = parse_process_code(code or "")
        if parts is None:
            return typed_text(code) if (code or "").strip() else typed_empty()
        return typed_int(parts.root * 10_000 + (parts.child or 0))

    def _preview_item(
        self,
        record_id: int,
        text: str,
        *,
        max_length: int = DEFAULT_TEXT_PREVIEW_LENGTH,
    ):
        full_text = text or ""
        item = create_typed_item(
            truncate_text_preview(full_text, max_length=max_length),
            typed_text(full_text),
            stable_id=record_id,
        )
        if full_text.strip():
            set_widget_tooltip(item, full_text)
        return item

    def _apply_row_style(self, row: int, requirement, today: date) -> None:
        if not requirement.active:
            color = QColor("#f0f0f0")
        elif (
            requirement.next_verification_date is not None
            and requirement.next_verification_date < today
        ):
            color = QColor("#ffe0e0")
        else:
            color = None

        if color is None:
            return

        brush = QBrush(color)
        for column in range(self.columnCount()):
            item = self.item(row, column)
            if item is not None:
                item.setBackground(brush)
