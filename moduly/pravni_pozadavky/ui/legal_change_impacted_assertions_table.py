from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.pravni_pozadavky.sluzby.legal_change_impacted_assertion_service import (
    ImpactedAuditAssertion,
)


class LegalChangeImpactedAssertionsTable(QTableWidget):
    def __init__(self):
        super().__init__()

        self.setColumnCount(5)
        self.setHorizontalHeaderLabels([
            "Kód / pořadí",
            "Text auditního tvrzení",
            "Ustanovení",
            "Typ změny",
            "Řídicí proces",
        ])

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
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.setColumnWidth(0, 140)

    def load_assertions(self, assertions: list[ImpactedAuditAssertion]) -> None:
        self.setRowCount(len(assertions))

        for row, assertion in enumerate(assertions):
            self._set_item(row, 0, assertion.code_or_order_label)
            self._set_item(row, 1, assertion.text)
            self._set_item(row, 2, assertion.section_label)
            self._set_item(row, 3, assertion.change_type_label)
            self._set_item(row, 4, assertion.process_display)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
