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
    HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
    RISK_ASSESSMENT_COL_ACTIVE,
    RISK_ASSESSMENT_COL_EVENT,
    RISK_ASSESSMENT_COL_EXPOSED_GROUP,
    RISK_ASSESSMENT_COL_HAZARD,
    RISK_ASSESSMENT_COL_ID,
    RISK_ASSESSMENT_COLUMN_COUNT,
    RISK_ASSESSMENTS_INTRO_TEXT,
    RISK_ASSESSMENT_TABLE_HEADERS,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    HazardRiskAssessmentError,
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog


class HazardRiskAssessmentsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._identification_id: int | None = None
        self._read_only = False

        layout = QVBoxLayout(self)

        intro = QLabel(RISK_ASSESSMENTS_INTRO_TEXT)
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
        self.table.setColumnCount(RISK_ASSESSMENT_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(RISK_ASSESSMENT_TABLE_HEADERS)
        self.table.setColumnHidden(RISK_ASSESSMENT_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_risk_assessments")
        layout.addWidget(self.table, 1)

        self.add_btn.clicked.connect(self.add_assessment)
        self.edit_btn.clicked.connect(self.edit_selected_assessment)
        self.activate_btn.clicked.connect(self.activate_selected_assessment)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_assessment)
        self.table.doubleClicked.connect(self.edit_selected_assessment)

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

    def add_assessment(
        self,
        *,
        default_hazard_event_id: int | None = None,
    ) -> bool:
        if not self._ensure_editable():
            return False

        dialog = HazardRiskAssessmentDialog(
            self,
            hazard_identification_id=self._identification_id,
            default_hazard_event_id=default_hazard_event_id,
        )
        if dialog.exec():
            self.refresh()
            return True
        return False

    def edit_selected_assessment(self) -> None:
        assessment = self._selected_assessment()
        if assessment is None:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Vyberte posouzení rizika.",
            )
            return

        dialog = HazardRiskAssessmentDialog(
            self,
            hazard_identification_id=self._identification_id,
            assessment=assessment,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()

    def activate_selected_assessment(self) -> None:
        if not self._ensure_editable():
            return

        assessment = self._selected_assessment()
        if assessment is None:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Vyberte posouzení rizika.",
            )
            return
        if assessment.active:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Posouzení rizika je již aktivní.",
            )
            return

        try:
            hazard_risk_assessment_service.activate_assessment(assessment.id)
        except HazardRiskAssessmentError as error:
            QMessageBox.warning(self, HAZARD_RISK_ASSESSMENT_DIALOG_TITLE, str(error))
            return
        self.refresh()

    def deactivate_selected_assessment(self) -> None:
        if not self._ensure_editable():
            return

        assessment = self._selected_assessment()
        if assessment is None:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Vyberte posouzení rizika.",
            )
            return
        if not assessment.active:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Posouzení rizika je již neaktivní.",
            )
            return

        hazard_risk_assessment_service.deactivate_assessment(assessment.id)
        self.refresh()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Nejprve uložte základní údaje identifikace.",
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_RISK_ASSESSMENT_DIALOG_TITLE,
                "Posouzení rizik je u dokončené nebo archivované identifikace "
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

        rows = hazard_risk_assessment_service.get_for_identification(
            self._identification_id,
            include_inactive=True,
        )
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            assessment = row.assessment
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_ID,
                QTableWidgetItem(str(assessment.id)),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_EXPOSED_GROUP,
                QTableWidgetItem(assessment.exposed_group),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_EVENT,
                QTableWidgetItem(row.event_name),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_HAZARD,
                QTableWidgetItem(row.hazard_name),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if assessment.active else "Ne"),
            )
        configure_table_columns(self.table, "hazard_risk_assessments")

    def _selected_assessment(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), RISK_ASSESSMENT_COL_ID)
        if id_item is None:
            return None
        return hazard_risk_assessment_service.get_by_id(int(id_item.text()))
