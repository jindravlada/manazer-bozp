from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_TYPE_LABELS, LINK_TYPE_LABELS
from core.shared.sluzby.entity_link_service import entity_link_service
from core.shared.widgets.entity_link_dialog import EntityLinkDialog
from core.widgets.dialog_utils import exec_maximized


class EntityLinksWidget(QWidget):
    def __init__(
        self,
        source_type: str,
        source_id: int | None = None,
        parent=None,
        link_dialog_class=None,
    ):
        super().__init__(parent)
        self.source_type = source_type
        self.source_id = source_id
        self.link_dialog_class = link_dialog_class or EntityLinkDialog

        layout = QVBoxLayout(self)

        if source_id is None:
            layout.addWidget(QLabel("Vazby lze přidat až po uložení záznamu."))
            self.table = None
            self.add_btn = None
            self.edit_btn = None
            self.toggle_btn = None
            return

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat vazbu")
        self.edit_btn = QPushButton("Upravit")
        self.toggle_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Typ cíle",
            "ID cíle",
            "Typ vazby",
            "Poznámka",
            "Aktivní",
        ])
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)

        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_link)
        self.edit_btn.clicked.connect(self.edit_selected_link)
        self.toggle_btn.clicked.connect(self.toggle_selected_link)
        self.table.doubleClicked.connect(self.edit_selected_link)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        if self.table is None or self.source_id is None:
            return

        links = entity_link_service.list_for_source(
            self.source_type,
            self.source_id,
            include_inactive=True,
        )
        self.table.setRowCount(len(links))

        for row, link in enumerate(links):
            self._set_item(row, 0, str(link.id))
            self._set_item(row, 1, ENTITY_TYPE_LABELS.get(link.target_type, link.target_type))
            self._set_item(row, 2, str(link.target_id))
            self._set_item(row, 3, LINK_TYPE_LABELS.get(link.link_type, link.link_type))
            self._set_item(row, 4, link.note)
            self._set_item(row, 5, "Ano" if link.active else "Ne")

            if not link.active:
                brush = QBrush(QColor("#f0f0f0"))
                for column in range(self.table.columnCount()):
                    item = self.table.item(row, column)
                    if item is not None:
                        item.setBackground(brush)

        self._update_action_buttons()

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, column, item)

    def _selected_link_id(self) -> int | None:
        if self.table is None:
            return None
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _selected_link(self):
        link_id = self._selected_link_id()
        if link_id is None:
            return None
        return entity_link_service.get_by_id(link_id)

    def _update_action_buttons(self) -> None:
        if self.toggle_btn is None:
            return
        link = self._selected_link()
        if link is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not link.active else "Deaktivovat")

    def _create_link_dialog(self, link=None):
        kwargs = {}
        if link is not None:
            kwargs["link"] = link
        if self.link_dialog_class is not EntityLinkDialog:
            kwargs["source_id"] = self.source_id
        return self.link_dialog_class(self, **kwargs)

    def add_link(self) -> None:
        if self.source_id is None:
            return

        dialog = self._create_link_dialog()
        if not exec_maximized(dialog):
            return

        try:
            entity_link_service.create(
                source_type=self.source_type,
                source_id=self.source_id,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Vazby", str(exc))
            return

        self.refresh()

    def edit_selected_link(self) -> None:
        link = self._selected_link()
        if link is None:
            QMessageBox.information(self, "Vazby", "Vyberte vazbu.")
            return

        dialog = self._create_link_dialog(link=link)
        if not exec_maximized(dialog):
            return

        try:
            entity_link_service.update(
                link.id,
                source_type=self.source_type,
                source_id=self.source_id,
                active=link.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Vazby", str(exc))
            return

        self.refresh()

    def toggle_selected_link(self) -> None:
        link = self._selected_link()
        if link is None:
            QMessageBox.information(self, "Vazby", "Vyberte vazbu.")
            return

        if link.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat vazbu",
                "Opravdu deaktivovat vybranou vazbu?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                entity_link_service.deactivate(link.id)
                self.refresh()
            return

        try:
            entity_link_service.restore(link.id)
        except ValueError as exc:
            QMessageBox.warning(self, "Vazby", str(exc))
            return
        self.refresh()
