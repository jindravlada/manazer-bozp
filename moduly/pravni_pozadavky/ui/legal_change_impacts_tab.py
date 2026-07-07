from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_TYPE_LABELS, LINK_TYPE_LABELS
from moduly.pravni_pozadavky.sluzby.legal_change_impact_service import legal_change_impact_service


class LegalChangeImpactsTab(QWidget):
    def __init__(self, change_id: int | None = None):
        super().__init__()
        self.change_id = change_id

        layout = QVBoxLayout(self)

        if change_id is None:
            layout.addWidget(QLabel("Přehled dopadů bude dostupný až po uložení změny."))
            self.summary_table = None
            self.links_table = None
            return

        layout.addWidget(QLabel("Souhrn podle typu objektu"))
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Typ objektu", "Počet"])
        self.summary_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.summary_table.setSelectionMode(QTableWidget.SingleSelection)
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.summary_table.setMaximumHeight(180)
        layout.addWidget(self.summary_table)

        layout.addWidget(QLabel("Aktivní vazby"))
        self.links_table = QTableWidget()
        self.links_table.setColumnCount(4)
        self.links_table.setHorizontalHeaderLabels([
            "Typ objektu",
            "ID objektu",
            "Typ vazby",
            "Poznámka",
        ])
        self.links_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.links_table.setSelectionMode(QTableWidget.SingleSelection)
        self.links_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.links_table.verticalHeader().setVisible(False)
        self.links_table.horizontalHeader().setStretchLastSection(True)
        self.links_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.links_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.links_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.links_table, 1)

        self.refresh()

    def refresh(self) -> None:
        if self.change_id is None or self.summary_table is None or self.links_table is None:
            return

        summary = legal_change_impact_service.build_summary(self.change_id)
        if summary is None:
            self.summary_table.setRowCount(0)
            self.links_table.setRowCount(0)
            return

        sorted_counts = sorted(
            summary.counts_by_type.items(),
            key=lambda item: ENTITY_TYPE_LABELS.get(item[0], item[0]),
        )
        self.summary_table.setRowCount(len(sorted_counts))
        for row, (target_type, count) in enumerate(sorted_counts):
            self._set_item(
                self.summary_table,
                row,
                0,
                ENTITY_TYPE_LABELS.get(target_type, target_type),
            )
            self._set_item(self.summary_table, row, 1, str(count))

        self.links_table.setRowCount(len(summary.links))
        for row, link in enumerate(summary.links):
            self._set_item(
                self.links_table,
                row,
                0,
                ENTITY_TYPE_LABELS.get(link.target_type, link.target_type),
            )
            self._set_item(self.links_table, row, 1, str(link.target_id))
            self._set_item(
                self.links_table,
                row,
                2,
                LINK_TYPE_LABELS.get(link.link_type, link.link_type),
            )
            self._set_item(self.links_table, row, 3, link.note)

    def _set_item(self, table: QTableWidget, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        table.setItem(row, column, item)
