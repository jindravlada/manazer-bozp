"""Tabulka seznamu smluv OZO."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_text,
)
from moduly.smlouvy_ozo.constants import (
    COL_EMPLOYER,
    COL_ICO,
    COL_ID,
    COL_NUMBER,
    COL_STATUS,
    COL_VALID_FROM,
    COL_VALID_TO,
    COLUMN_HEADERS,
    format_date,
    format_valid_to,
    status_label,
)
from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract
from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service

_ROLE_ID = Qt.ItemDataRole.UserRole


class OzoContractTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(len(COLUMN_HEADERS))
        self.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setColumnHidden(COL_ID, True)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(
            COL_EMPLOYER, QHeaderView.ResizeMode.Stretch
        )
        enable_typed_sorting(self)

    def clear_selection(self) -> None:
        self.clearSelection()
        self.setCurrentCell(-1, -1)

    def selected_contract_id(self) -> int | None:
        rows = self.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.item(rows[0].row(), COL_ID)
        if item is None:
            return None
        raw = item.data(_ROLE_ID)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def load_contracts(
        self,
        contracts: list[OzoContract],
        *,
        today: date | None = None,
    ) -> None:
        with sorting_paused(self):
            self.setRowCount(0)
            self.setRowCount(len(contracts))
            for row, contract in enumerate(contracts):
                sid = contract.id
                id_item = create_typed_item(
                    str(sid),
                    typed_text(str(sid)),
                    stable_id=sid,
                )
                id_item.setData(_ROLE_ID, sid)
                self.setItem(row, COL_ID, id_item)

                self.setItem(
                    row,
                    COL_EMPLOYER,
                    create_typed_item(
                        contract.employer_name or "—",
                        typed_text(contract.employer_name or ""),
                        stable_id=sid,
                    ),
                )
                self.setItem(
                    row,
                    COL_ICO,
                    create_typed_item(
                        (contract.ico or "").strip() or "—",
                        typed_text(contract.ico or ""),
                        stable_id=sid,
                    ),
                )
                self.setItem(
                    row,
                    COL_NUMBER,
                    create_typed_item(
                        (contract.contract_number or "").strip() or "—",
                        typed_text(contract.contract_number or ""),
                        stable_id=sid,
                    ),
                )
                from_text = format_date(contract.valid_from)
                self.setItem(
                    row,
                    COL_VALID_FROM,
                    create_typed_item(
                        from_text,
                        typed_date(contract.valid_from)
                        if contract.valid_from
                        else typed_empty(),
                        stable_id=sid,
                    ),
                )
                to_text = format_valid_to(
                    indefinite=bool(contract.indefinite),
                    valid_to=contract.valid_to,
                )
                self.setItem(
                    row,
                    COL_VALID_TO,
                    create_typed_item(
                        to_text,
                        typed_date(contract.valid_to)
                        if contract.valid_to and not contract.indefinite
                        else typed_empty(),
                        stable_id=sid,
                    ),
                )
                status = ozo_contract_service.status_for(contract, today=today)
                label = status_label(status)
                self.setItem(
                    row,
                    COL_STATUS,
                    create_typed_item(label, typed_text(label), stable_id=sid),
                )
