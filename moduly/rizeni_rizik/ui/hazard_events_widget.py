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

from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import (
    EVENT_COL_ACTIVE,
    EVENT_COL_HAZARD,
    EVENT_COL_ID,
    EVENT_COL_INVENTORY_ITEM,
    EVENT_COL_NAME,
    EVENT_COLUMN_COUNT,
    EVENTS_INTRO_TEXT,
    EVENT_TABLE_HEADERS,
    HAZARD_EVENT_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventError,
    hazard_event_service,
)
from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog


class HazardEventsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._identification_id: int | None = None
        self._read_only = False

        layout = QVBoxLayout(self)

        intro = QLabel(EVENTS_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(EVENT_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(EVENT_TABLE_HEADERS)
        self.table.setColumnHidden(EVENT_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_events")
        layout.addWidget(self.table, 1)

        self.add_btn.clicked.connect(self.add_event)
        self.edit_btn.clicked.connect(self.edit_selected_event)
        self.activate_btn.clicked.connect(self.activate_selected_event)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_event)
        self.table.doubleClicked.connect(self.edit_selected_event)

        self.set_identification(None, read_only=False)

    def set_identification(
        self,
        identification_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._identification_id = identification_id
        self._read_only = read_only
        self._set_actions_enabled(not read_only and identification_id is not None)
        self.refresh()

    def refresh(self) -> None:
        self._load_table()

    def add_event(
        self,
        *,
        default_identified_hazard_id: int | None = None,
    ) -> bool:
        if not self._ensure_editable():
            return False

        dialog = HazardEventDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_identified_hazard_id=default_identified_hazard_id,
        )
        if dialog.exec():
            self.refresh()
            return True
        return False

    def edit_selected_event(self) -> None:
        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Vyberte nežádoucí událost.",
            )
            return

        dialog = HazardEventDialog(
            self,
            hazard_identification_id=self._identification_id,
            event=event,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()

    def activate_selected_event(self) -> None:
        if not self._ensure_editable():
            return

        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Vyberte nežádoucí událost.",
            )
            return
        if event.active:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již aktivní.",
            )
            return

        try:
            hazard_event_service.activate_event(event.id)
        except HazardEventError as error:
            QMessageBox.warning(self, HAZARD_EVENT_DIALOG_TITLE, str(error))
            return
        self.refresh()

    def deactivate_selected_event(self) -> None:
        if not self._ensure_editable():
            return

        event = self._selected_event()
        if event is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Vyberte nežádoucí událost.",
            )
            return
        if not event.active:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Nežádoucí událost je již neaktivní.",
            )
            return

        hazard_event_service.deactivate_event(event.id)
        self.refresh()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_EVENT_DIALOG_TITLE,
                "Nežádoucí události jsou u dokončené nebo archivované identifikace "
                "pouze pro čtení.",
            )
            return False
        return True

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (self.add_btn, self.edit_btn, self.activate_btn, self.deactivate_btn):
            button.setEnabled(enabled)

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        if self._identification_id is None:
            return

        rows = hazard_event_service.get_for_identification(
            self._identification_id,
            include_inactive=True,
        )
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            event = row.event
            self.table.setItem(row_index, EVENT_COL_ID, QTableWidgetItem(str(event.id)))
            self.table.setItem(row_index, EVENT_COL_NAME, QTableWidgetItem(event.name))
            self.table.setItem(row_index, EVENT_COL_HAZARD, QTableWidgetItem(row.hazard_name))
            self.table.setItem(
                row_index,
                EVENT_COL_INVENTORY_ITEM,
                QTableWidgetItem(row.inventory_item_name),
            )
            self.table.setItem(
                row_index,
                EVENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if event.active else "Ne"),
            )
        configure_table_columns(self.table, "hazard_events")

    def _selected_event(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), EVENT_COL_ID)
        if id_item is None:
            return None
        return hazard_event_service.get_by_id(int(id_item.text()))
