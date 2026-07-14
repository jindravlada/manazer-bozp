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
    HAZARD_COL_ACTIVE,
    HAZARD_COL_ID,
    HAZARD_COL_INVENTORY_CATEGORY,
    HAZARD_COL_INVENTORY_ITEM,
    HAZARD_COL_NAME,
    HAZARD_COL_SOURCE,
    HAZARD_COLUMN_COUNT,
    HAZARDS_INTRO_TEXT,
    HAZARD_TABLE_HEADERS,
    IDENTIFIED_HAZARD_DIALOG_TITLE,
    format_hazard_display_name,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
    IdentifiedHazardError,
    identified_hazard_service,
)
from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog
from moduly.rizeni_rizik.ui.identified_hazard_dialog import IdentifiedHazardDialog


class IdentifiedHazardsWidget(QWidget):
    def __init__(self, parent=None, on_event_saved=None):
        super().__init__(parent)

        self._on_event_saved = on_event_saved
        self._identification_id: int | None = None
        self._read_only = False
        self._selected_hazard_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(HAZARDS_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        self.add_event_btn = QPushButton("Přidat nežádoucí událost")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addWidget(self.add_event_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(HAZARD_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(HAZARD_TABLE_HEADERS)
        self.table.setColumnHidden(HAZARD_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "identified_hazards")
        layout.addWidget(self.table, 1)

        self.add_btn.clicked.connect(self.add_hazard)
        self.edit_btn.clicked.connect(self.edit_selected_hazard)
        self.activate_btn.clicked.connect(self.activate_selected_hazard)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_hazard)
        self.add_event_btn.clicked.connect(self.add_event_for_selected_hazard)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self.edit_selected_hazard)

        self.set_identification(None, read_only=False)

    def set_identification(
        self,
        identification_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._identification_id = identification_id
        self._read_only = read_only
        self._selected_hazard_id = None
        self._set_actions_enabled(not read_only and identification_id is not None)
        self.refresh()

    def refresh(self) -> None:
        self._load_table()

    def add_hazard(
        self,
        *,
        default_inventory_item_id: int | None = None,
    ) -> bool:
        if not self._ensure_editable():
            return False

        dialog = IdentifiedHazardDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_inventory_item_id=default_inventory_item_id,
        )
        if dialog.exec():
            self.refresh()
            return True
        return False

    def edit_selected_hazard(self) -> None:
        hazard = self._selected_hazard()
        if hazard is None:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Vyberte nebezpečí.",
            )
            return

        dialog = IdentifiedHazardDialog(
            self,
            hazard_identification_id=self._identification_id,
            hazard=hazard,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()

    def add_event_for_selected_hazard(self) -> None:
        if not self._ensure_editable():
            return

        hazard = self._selected_hazard()
        if hazard is None:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Vyberte nebezpečí.",
            )
            return

        dialog = HazardEventDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_identified_hazard_id=hazard.id,
        )
        if dialog.exec():
            self._notify_event_saved()
            self.refresh()

    def activate_selected_hazard(self) -> None:
        if not self._ensure_editable():
            return

        hazard = self._selected_hazard()
        if hazard is None:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Vyberte nebezpečí.",
            )
            return
        if hazard.active:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Nebezpečí je již aktivní.",
            )
            return

        try:
            identified_hazard_service.activate_hazard(hazard.id)
        except IdentifiedHazardError as error:
            QMessageBox.warning(self, IDENTIFIED_HAZARD_DIALOG_TITLE, str(error))
            return
        self.refresh()

    def deactivate_selected_hazard(self) -> None:
        if not self._ensure_editable():
            return

        hazard = self._selected_hazard()
        if hazard is None:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Vyberte nebezpečí.",
            )
            return
        if not hazard.active:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Nebezpečí je již neaktivní.",
            )
            return

        identified_hazard_service.deactivate_hazard(hazard.id)
        self.refresh()

    def _notify_event_saved(self) -> None:
        if self._on_event_saved is not None:
            self._on_event_saved()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                IDENTIFIED_HAZARD_DIALOG_TITLE,
                "Nebezpečí je u dokončené nebo archivované identifikace pouze pro čtení.",
            )
            return False
        return True

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_btn,
            self.edit_btn,
            self.activate_btn,
            self.deactivate_btn,
            self.add_event_btn,
        ):
            button.setEnabled(enabled)

    def _load_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._identification_id is None:
            self.table.blockSignals(False)
            return

        event_counts = hazard_event_service.count_active_by_hazards(self._identification_id)
        rows = identified_hazard_service.get_for_identification(
            self._identification_id,
            include_inactive=True,
        )
        self.table.setRowCount(len(rows))
        selected_row = -1
        for row_index, row in enumerate(rows):
            hazard = row.hazard
            self.table.setItem(row_index, HAZARD_COL_ID, QTableWidgetItem(str(hazard.id)))
            display_name = format_hazard_display_name(
                hazard.name,
                event_count=event_counts.get(hazard.id, 0),
            )
            self.table.setItem(row_index, HAZARD_COL_NAME, QTableWidgetItem(display_name))
            self.table.setItem(
                row_index,
                HAZARD_COL_INVENTORY_ITEM,
                QTableWidgetItem(row.inventory_item_name),
            )
            self.table.setItem(
                row_index,
                HAZARD_COL_INVENTORY_CATEGORY,
                QTableWidgetItem(row.inventory_item_category_label),
            )
            self.table.setItem(
                row_index,
                HAZARD_COL_SOURCE,
                QTableWidgetItem(row.source_type_label),
            )
            self.table.setItem(
                row_index,
                HAZARD_COL_ACTIVE,
                QTableWidgetItem("Ano" if hazard.active else "Ne"),
            )
            if self._selected_hazard_id == hazard.id:
                selected_row = row_index

        configure_table_columns(self.table, "identified_hazards")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)

    def _on_selection_changed(self) -> None:
        hazard = self._selected_hazard()
        self._selected_hazard_id = hazard.id if hazard is not None else None

    def _selected_hazard(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), HAZARD_COL_ID)
        if id_item is None:
            return None
        return identified_hazard_service.get_by_id(int(id_item.text()))
