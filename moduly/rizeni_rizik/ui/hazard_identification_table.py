from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget

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
from moduly.rizeni_rizik.constants import (
    COL_ID,
    COL_IDENTIFICATION,
    COL_OPERATION,
    COL_RESPONSIBLE_PERSON,
    COL_STARTED_AT,
    COL_STATUS,
    COL_WORKPLACE,
    COL_WORKPLACE_PART,
    COLUMN_COUNT,
    HAZARD_IDENTIFICATION_STATUSES,
    HAZARD_IDENTIFICATION_STATUS_LABELS,
    TABLE_HEADERS,
)


def _identification_status_sort(status: str):
    try:
        order = HAZARD_IDENTIFICATION_STATUSES.index(status)
    except ValueError:
        order = len(HAZARD_IDENTIFICATION_STATUSES)
    return typed_status(order, label=status or "")


class HazardIdentificationTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(COLUMN_COUNT)
        self.setHorizontalHeaderLabels(TABLE_HEADERS)
        self.setColumnHidden(COL_ID, True)
        self.setColumnHidden(COL_IDENTIFICATION, True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        enable_typed_sorting(self)

    def load_identifications(self, identifications) -> None:
        with sorting_paused(self):
            self.setRowCount(len(identifications))
            for row, identification in enumerate(identifications):
                record_id = int(identification.id)
                self.setItem(
                    row,
                    COL_ID,
                    create_typed_item(str(record_id), typed_int(record_id), stable_id=record_id),
                )
                self.setItem(
                    row,
                    COL_IDENTIFICATION,
                    create_typed_item(
                        identification.identification_number or "",
                        typed_text(identification.identification_number),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_OPERATION,
                    create_typed_item(
                        identification.operation_name or "",
                        typed_text(identification.operation_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_WORKPLACE,
                    create_typed_item(
                        identification.workplace_name or "",
                        typed_text(identification.workplace_name),
                        stable_id=record_id,
                    ),
                )
                self.setItem(
                    row,
                    COL_WORKPLACE_PART,
                    create_typed_item(
                        identification.workplace_part_name or "",
                        typed_text(identification.workplace_part_name),
                        stable_id=record_id,
                    ),
                )
                if identification.started_at is not None:
                    started_text = identification.started_at.strftime("%d.%m.%Y")
                    started_sort = typed_date(identification.started_at)
                else:
                    started_text = ""
                    started_sort = typed_empty()
                self.setItem(
                    row,
                    COL_STARTED_AT,
                    create_typed_item(started_text, started_sort, stable_id=record_id),
                )
                self.setItem(
                    row,
                    COL_RESPONSIBLE_PERSON,
                    create_typed_item(
                        identification.responsible_person_name or "",
                        typed_text(identification.responsible_person_name),
                        stable_id=record_id,
                    ),
                )
                status_label = HAZARD_IDENTIFICATION_STATUS_LABELS.get(
                    identification.status,
                    identification.status,
                )
                status_item = create_typed_item(
                    status_label,
                    _identification_status_sort(identification.status),
                    stable_id=record_id,
                )
                if not identification.active:
                    status_item.setForeground(Qt.GlobalColor.gray)
                self.setItem(row, COL_STATUS, status_item)

    def selected_identification_id(self) -> int | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.item(selected[0].row(), COL_ID)
        return int(item.text()) if item else None
