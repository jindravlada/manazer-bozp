from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    PERIODICITY_LABELS,
    legal_requirement_provision_label,
    legal_requirement_regulation_label,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

COL_ID = 0
COL_REGULATION = 1
COL_PROVISION = 2
COL_AREA = 3
COL_SUMMARY = 4
COL_RESPONSIBLE = 5
COL_STATUS = 6
COL_LAST_CHECK = 7
COL_NEXT_CHECK = 8
COL_PERIODICITY = 9
COLUMN_COUNT = 10


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
            "Předpis",
            "Ustanovení",
            "Oblast",
            "Požadavek",
            "Odpovědná osoba",
            "Stav plnění",
            "Poslední ověření",
            "Další ověření",
            "Periodicita",
        ])

        self.setColumnHidden(COL_ID, True)
        self.setColumnHidden(COL_AREA, True)
        self.setWordWrap(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_SUMMARY, QHeaderView.Stretch)
        for column in (
            COL_REGULATION,
            COL_PROVISION,
            COL_RESPONSIBLE,
            COL_STATUS,
            COL_LAST_CHECK,
            COL_NEXT_CHECK,
            COL_PERIODICITY,
        ):
            header.setSectionResizeMode(column, QHeaderView.Fixed)

    def clear_selection(self) -> None:
        self.clearSelection()
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.clearCurrentIndex()

    def load_requirements(self, requirements) -> None:
        self.setRowCount(len(requirements))
        today = date.today()
        sections_by_id = self._sections_by_id(requirements)

        for row, requirement in enumerate(requirements):
            section_id = requirement.source_section_id or requirement.legal_section_id
            section = sections_by_id.get(section_id) if section_id is not None else None

            self._set_item(row, COL_ID, str(requirement.id))
            self._set_item(row, COL_REGULATION, legal_requirement_regulation_label(requirement))
            self._set_item(
                row,
                COL_PROVISION,
                legal_requirement_provision_label(
                    requirement,
                    section=section,
                    sections_by_id=sections_by_id,
                ),
            )
            self._set_item(row, COL_AREA, requirement.area)
            self._set_item(row, COL_SUMMARY, requirement.requirement_summary)
            self._set_item(row, COL_RESPONSIBLE, requirement.responsible_person_name)
            self._set_item(
                row,
                COL_STATUS,
                COMPLIANCE_STATUS_LABELS.get(
                    requirement.compliance_status,
                    requirement.compliance_status,
                ),
            )
            self._set_item(row, COL_LAST_CHECK, _format_date(requirement.last_verification_date))
            self._set_item(row, COL_NEXT_CHECK, _format_date(requirement.next_verification_date))
            self._set_item(
                row,
                COL_PERIODICITY,
                PERIODICITY_LABELS.get(
                    requirement.verification_periodicity,
                    requirement.verification_periodicity,
                ),
            )

            self._apply_row_style(row, requirement, today)

    def _sections_by_id(self, requirements) -> dict:
        section_ids: set[int] = set()
        for requirement in requirements:
            section_id = requirement.source_section_id or requirement.legal_section_id
            if section_id is not None:
                section_ids.add(section_id)

        sections_by_id = {}
        pending = set(section_ids)
        while pending:
            section_id = pending.pop()
            if section_id in sections_by_id:
                continue
            section = legal_section_service.get_by_id(section_id)
            if section is None:
                continue
            sections_by_id[section_id] = section
            if section.parent_section_id is not None:
                pending.add(section.parent_section_id)
        return sections_by_id

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)

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
