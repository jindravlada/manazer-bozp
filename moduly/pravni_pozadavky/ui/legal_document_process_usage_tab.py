from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.constants import (
    DEFAULT_DOCUMENT_USAGE_FILTER,
    FILTER_DOCUMENT_USAGE_ALL,
    FILTER_DOCUMENT_USAGE_ASSIGNED,
    FILTER_DOCUMENT_USAGE_UNASSIGNED,
)
from moduly.pravni_pozadavky.sluzby.legal_document_process_usage_service import (
    DocumentSectionProcessUsageEntry,
    legal_document_process_usage_service,
)


class LegalDocumentProcessUsageTab(QWidget):
    """Read-only přehled použití ustanovení předpisu v řídicích procesech."""

    def __init__(self, document_id: int | None = None, parent=None):
        super().__init__(parent)
        self.document_id = document_id
        self._rows: list[DocumentSectionProcessUsageEntry] = []

        layout = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Zobrazit:"))
        self.usage_filter = QComboBox()
        self.usage_filter.addItems([
            FILTER_DOCUMENT_USAGE_ALL,
            FILTER_DOCUMENT_USAGE_ASSIGNED,
            FILTER_DOCUMENT_USAGE_UNASSIGNED,
        ])
        self.usage_filter.setCurrentText(DEFAULT_DOCUMENT_USAGE_FILTER)
        filters.addWidget(self.usage_filter)
        filters.addStretch()
        layout.addLayout(filters)

        self.empty_label = QLabel("Právní předpis nemá dostupné aktuální znění.")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tree, 1)

        self.usage_filter.currentIndexChanged.connect(self._reload_tree)
        self.refresh()

    def refresh(self) -> None:
        if self.document_id is None:
            self._rows = []
            self.empty_label.setText("Přehled bude dostupný po uložení právního předpisu.")
            self.empty_label.setVisible(True)
            self.tree.setVisible(False)
            self.tree.clear()
            return

        self._rows = legal_document_process_usage_service.list_process_usage_for_document(
            self.document_id,
        )
        has_rows = bool(self._rows)
        self.empty_label.setText(
            "Právní předpis nemá dostupné aktuální znění."
            if not has_rows
            else "",
        )
        self.empty_label.setVisible(not has_rows)
        self.tree.setVisible(has_rows)
        self._reload_tree()

    def _reload_tree(self) -> None:
        self.tree.clear()
        if not self._rows:
            return

        filter_mode = self.usage_filter.currentText()
        for row in self._rows:
            if filter_mode == FILTER_DOCUMENT_USAGE_ASSIGNED and not row.is_assigned:
                continue
            if filter_mode == FILTER_DOCUMENT_USAGE_UNASSIGNED and row.is_assigned:
                continue

            section_item = QTreeWidgetItem([row.provision_label])
            section_font = QFont(section_item.font(0))
            section_font.setBold(True)
            section_item.setFont(0, section_font)
            section_item.setData(0, Qt.ItemDataRole.UserRole, row.section_id)
            self.tree.addTopLevelItem(section_item)

            if row.processes:
                for process in row.processes:
                    child = QTreeWidgetItem([process.display_label])
                    child.setData(0, Qt.ItemDataRole.UserRole, process.requirement_id)
                    section_item.addChild(child)
            else:
                child = QTreeWidgetItem(["Nepřiřazeno"])
                section_item.addChild(child)

            section_item.setExpanded(True)
