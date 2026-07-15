from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns, create_preview_table_item
from moduly.rizeni_rizik.constants import (
    HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
    REQUIRED_MEASURE_COL_ACTIVE,
    REQUIRED_MEASURE_COL_DESCRIPTION,
    REQUIRED_MEASURE_COL_ID,
    REQUIRED_MEASURE_COL_NOTE,
    REQUIRED_MEASURE_COLUMN_COUNT,
    REQUIRED_MEASURE_SELECT_ASSESSMENT,
    REQUIRED_MEASURE_TABLE_HEADERS,
    REQUIRED_MEASURES_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    HazardRequiredMeasureError,
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.ui.hazard_required_measure_dialog import HazardRequiredMeasureDialog


class HazardRequiredMeasuresWidget(QWidget):
    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)

        self._on_changed = on_changed
        self._identification_id: int | None = None
        self._assessment = None
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox(REQUIRED_MEASURES_TITLE)
        group_layout = QVBoxLayout(group)

        self.header_label = QLabel(REQUIRED_MEASURE_SELECT_ASSESSMENT)
        self.header_label.setWordWrap(True)
        group_layout.addWidget(self.header_label)

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
        group_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(REQUIRED_MEASURE_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(REQUIRED_MEASURE_TABLE_HEADERS)
        self.table.setColumnHidden(REQUIRED_MEASURE_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_required_measures")
        group_layout.addWidget(self.table)

        layout.addWidget(group)

        self.add_btn.clicked.connect(self.add_measure)
        self.edit_btn.clicked.connect(self.edit_selected_measure)
        self.activate_btn.clicked.connect(self.activate_selected_measure)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_measure)
        self.table.doubleClicked.connect(self.edit_selected_measure)

        self.set_assessment(None, identification_id=None, read_only=False)

    def set_assessment(
        self,
        assessment,
        *,
        identification_id: int | None,
        read_only: bool,
    ) -> None:
        self._assessment = assessment
        self._identification_id = identification_id
        self._read_only = read_only
        editable = (
            not read_only
            and identification_id is not None
            and assessment is not None
        )
        for button in (self.add_btn, self.edit_btn, self.activate_btn, self.deactivate_btn):
            button.setEnabled(editable)
        self.refresh()

    def refresh(self) -> None:
        if self._assessment is None:
            self.header_label.setText(REQUIRED_MEASURE_SELECT_ASSESSMENT)
            self.table.setRowCount(0)
            return

        self.header_label.setText(
            hazard_risk_assessment_service.get_exposed_group_display_name(self._assessment)
        )
        self._load_table()

    def add_measure(self) -> None:
        if not self._ensure_editable():
            return

        dialog = HazardRequiredMeasureDialog(
            self,
            hazard_identification_id=self._identification_id,
            hazard_risk_assessment_id=self._assessment.id,
        )
        if dialog.exec():
            self._notify_changed()

    def edit_selected_measure(self) -> None:
        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                "Vyberte potřebné opatření.",
            )
            return

        dialog = HazardRequiredMeasureDialog(
            self,
            hazard_identification_id=self._identification_id,
            hazard_risk_assessment_id=self._assessment.id,
            measure=measure,
            read_only=self._read_only,
        )
        if dialog.exec():
            self._notify_changed()

    def activate_selected_measure(self) -> None:
        if not self._ensure_editable():
            return

        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                "Vyberte potřebné opatření.",
            )
            return
        if measure.active:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                "Opatření je již aktivní.",
            )
            return

        try:
            hazard_required_measure_service.activate_measure(measure.id)
        except HazardRequiredMeasureError as error:
            QMessageBox.warning(self, HAZARD_REQUIRED_MEASURE_DIALOG_TITLE, str(error))
            return
        self._notify_changed()

    def deactivate_selected_measure(self) -> None:
        if not self._ensure_editable():
            return

        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                "Vyberte potřebné opatření.",
            )
            return
        if not measure.active:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                "Opatření je již neaktivní.",
            )
            return

        hazard_required_measure_service.deactivate_measure(measure.id)
        self._notify_changed()

    def _notify_changed(self) -> None:
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None or self._assessment is None:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                REQUIRED_MEASURE_SELECT_ASSESSMENT,
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
                "Potřebná opatření jsou u dokončené nebo archivované identifikace "
                "pouze pro čtení.",
            )
            return False
        return True

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        if self._assessment is None:
            return

        measures = hazard_required_measure_service.get_for_assessment(
            self._assessment.id,
            include_inactive=True,
        )
        self.table.setRowCount(len(measures))
        for row_index, measure in enumerate(measures):
            self.table.setItem(
                row_index,
                REQUIRED_MEASURE_COL_ID,
                QTableWidgetItem(str(measure.id)),
            )
            self.table.setItem(
                row_index,
                REQUIRED_MEASURE_COL_DESCRIPTION,
                create_preview_table_item(measure.description),
            )
            self.table.setItem(
                row_index,
                REQUIRED_MEASURE_COL_NOTE,
                create_preview_table_item(measure.note or ""),
            )
            self.table.setItem(
                row_index,
                REQUIRED_MEASURE_COL_ACTIVE,
                QTableWidgetItem("Ano" if measure.active else "Ne"),
            )
        configure_table_columns(self.table, "hazard_required_measures")

    def _selected_measure(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), REQUIRED_MEASURE_COL_ID)
        if id_item is None:
            return None
        return hazard_required_measure_service.get_by_id(int(id_item.text()))
