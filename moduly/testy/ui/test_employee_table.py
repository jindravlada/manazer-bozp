"""Tabulka zaměstnanců modulu Testy."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QTableWidget

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_text,
)
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.constants import (
    COL_FIRST_NAME,
    COL_ID,
    COL_LAST_NAME,
    COL_PERSONAL_NUMBER,
    COL_ROLES,
    COL_STATUS,
    COL_WORKPLACE,
    COLUMN_HEADERS,
    STATUS_ACTIVE_LABEL,
    STATUS_INACTIVE_LABEL,
)
from moduly.testy.modely.test_employee import TestEmployee
from moduly.testy.sluzby.test_employee_service import test_employee_service

_ROLE_ID = Qt.ItemDataRole.UserRole


class TestEmployeeTable(QTableWidget):
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
        enable_typed_sorting(self)

    def selected_employee_id(self) -> int | None:
        rows = self.selectionModel().selectedRows() if self.selectionModel() else []
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

    def load_employees(self, employees: list[TestEmployee]) -> None:
        workplaces = {
            workplace.id: workplace
            for workplace in settings_service.get_workplaces(include_inactive=True)
        }
        roles = {
            role.id: role
            for role in responsibility_role_service.get_all(include_inactive=True)
        }
        with sorting_paused(self):
            self.setRowCount(len(employees))
            for row, employee in enumerate(employees):
                role_ids = test_employee_service.get_role_ids(employee.id)
                role_names = [
                    roles[role_id].name
                    for role_id in role_ids
                    if role_id in roles
                ]
                workplace = workplaces.get(employee.workplace_id)
                workplace_name = workplace.name if workplace is not None else ""
                status = (
                    STATUS_ACTIVE_LABEL if employee.active else STATUS_INACTIVE_LABEL
                )
                values = {
                    COL_ID: str(employee.id),
                    COL_PERSONAL_NUMBER: employee.personal_number,
                    COL_LAST_NAME: employee.last_name,
                    COL_FIRST_NAME: employee.first_name,
                    COL_ROLES: ", ".join(role_names),
                    COL_WORKPLACE: workplace_name,
                    COL_STATUS: status,
                }
                for column, text in values.items():
                    item = create_typed_item(
                        text,
                        typed_text(text),
                        stable_id=employee.id,
                    )
                    item.setData(_ROLE_ID, employee.id)
                    self.setItem(row, column, item)
