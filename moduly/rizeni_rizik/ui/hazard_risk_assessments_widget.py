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
    RISK_ASSESSMENT_COL_COMPLETED_AT,
    RISK_ASSESSMENT_COL_EVENT,
    RISK_ASSESSMENT_COL_EXPOSED_GROUP,
    RISK_ASSESSMENT_COL_ID,
    RISK_ASSESSMENT_COL_INVENTORY_ITEM,
    RISK_ASSESSMENT_COL_SEVERITY,
    RISK_ASSESSMENT_COL_STATUS,
    RISK_ASSESSMENT_COLUMN_COUNT,
    RISK_ASSESSMENTS_INTRO_TEXT,
    RISK_ASSESSMENT_TABLE_HEADERS,
    format_risk_assessment_completed_at,
    format_risk_assessment_display_name,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    HazardRiskAssessmentError,
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.ui.hazard_existing_measures_widget import HazardExistingMeasuresWidget
from moduly.rizeni_rizik.ui.hazard_required_measures_widget import HazardRequiredMeasuresWidget
from moduly.rizeni_rizik.ui.hazard_risk_assessment_dialog import HazardRiskAssessmentDialog


class HazardRiskAssessmentsWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._identification_id: int | None = None
        self._read_only = False
        self._selected_assessment_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(RISK_ASSESSMENTS_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

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
        layout.addWidget(self.table, 2)

        self.existing_measures_widget = HazardExistingMeasuresWidget(
            on_changed=self._on_existing_measures_changed
        )
        layout.addWidget(self.existing_measures_widget, 1)

        self.required_measures_widget = HazardRequiredMeasuresWidget(
            on_changed=self._on_required_measures_changed
        )
        layout.addWidget(self.required_measures_widget, 1)

        self.add_btn.clicked.connect(self.add_assessment)
        self.edit_btn.clicked.connect(self.edit_selected_assessment)
        self.activate_btn.clicked.connect(self.activate_selected_assessment)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_assessment)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self.edit_selected_assessment)

        self.set_identification(None, read_only=False)

    def _store(self):
        return find_identification_working_copy(self)

    def _notify_editor_dirty(self) -> None:
        window = self.window()
        update = getattr(window, "_update_save_enabled", None)
        if callable(update):
            update()

    def _count_active_measures(self, *, existing: bool) -> dict[int, int]:
        store = self._store()
        if store is None:
            service = (
                hazard_existing_measure_service
                if existing
                else hazard_required_measure_service
            )
            return service.count_active_by_assessments(self._identification_id)
        counts: dict[int, int] = {}
        for item in store.items:
            for event in item.events:
                for assessment in event.assessments:
                    bucket = (
                        assessment.existing_measures
                        if existing
                        else assessment.required_measures
                    )
                    counts[assessment.id] = sum(1 for measure in bucket if measure.active)
        return counts

    def set_identification(
        self,
        identification_id: int | None,
        *,
        read_only: bool,
    ) -> None:
        self._identification_id = identification_id
        self._read_only = read_only
        self._selected_assessment_id = None
        self._set_actions_enabled(not read_only and identification_id is not None)
        self.existing_measures_widget.set_assessment(
            None,
            identification_id=identification_id,
            read_only=read_only,
        )
        self.required_measures_widget.set_assessment(
            None,
            identification_id=identification_id,
            read_only=read_only,
        )
        self.refresh()

    def refresh(self) -> None:
        self._load_table()
        self._sync_measures_selection()

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
            self._notify_editor_dirty()
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
            self._notify_editor_dirty()

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

        store = self._store()
        try:
            if store is not None:
                store.activate_assessment(assessment.id)
            else:
                hazard_risk_assessment_service.activate_assessment(assessment.id)
        except HazardRiskAssessmentError as error:
            QMessageBox.warning(self, HAZARD_RISK_ASSESSMENT_DIALOG_TITLE, str(error))
            return
        self.refresh()
        self._notify_editor_dirty()

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

        store = self._store()
        if store is not None:
            store.deactivate_assessment(assessment.id)
        else:
            hazard_risk_assessment_service.deactivate_assessment(assessment.id)
        self.refresh()
        self._notify_editor_dirty()

    def _on_existing_measures_changed(self) -> None:
        self._load_table()
        self._notify_editor_dirty()

    def _on_required_measures_changed(self) -> None:
        self._load_table()
        self._notify_editor_dirty()

    def _on_selection_changed(self) -> None:
        assessment = self._selected_assessment()
        self._selected_assessment_id = assessment.id if assessment is not None else None
        self._sync_measures_selection()

    def _sync_measures_selection(self) -> None:
        assessment = None
        if self._selected_assessment_id is not None:
            store = self._store()
            if store is not None:
                for row in store.list_assessment_rows(include_inactive=True):
                    if row.assessment.id == self._selected_assessment_id:
                        assessment = row.assessment
                        break
            else:
                assessment = hazard_risk_assessment_service.get_by_id(
                    self._selected_assessment_id,
                )
        self.existing_measures_widget.set_assessment(
            assessment,
            identification_id=self._identification_id,
            read_only=self._read_only,
        )
        self.required_measures_widget.set_assessment(
            assessment,
            identification_id=self._identification_id,
            read_only=self._read_only,
        )

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
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if self._identification_id is None:
            self.summary_label.setText("")
            self.table.blockSignals(False)
            return

        self._update_summary()
        existing_measure_counts = self._count_active_measures(existing=True)
        required_measure_counts = self._count_active_measures(existing=False)
        store = self._store()
        if store is not None:
            rows = store.list_assessment_rows(include_inactive=True)
        else:
            rows = hazard_risk_assessment_service.get_for_identification(
                self._identification_id,
                include_inactive=True,
            )
        self.table.setRowCount(len(rows))
        selected_row = -1
        for row_index, row in enumerate(rows):
            assessment = row.assessment
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_ID,
                QTableWidgetItem(str(assessment.id)),
            )
            display_name = format_risk_assessment_display_name(
                row.exposed_group_name,
                assessment_status_label=row.status_label,
                existing_measure_count=existing_measure_counts.get(assessment.id, 0),
                required_measure_count=required_measure_counts.get(assessment.id, 0),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_EXPOSED_GROUP,
                QTableWidgetItem(display_name),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_EVENT,
                QTableWidgetItem(row.event_name),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_INVENTORY_ITEM,
                QTableWidgetItem(row.inventory_item_name),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_SEVERITY,
                QTableWidgetItem(row.severity_label),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_STATUS,
                QTableWidgetItem(row.status_label),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_COMPLETED_AT,
                QTableWidgetItem(format_risk_assessment_completed_at(assessment.completed_at)),
            )
            self.table.setItem(
                row_index,
                RISK_ASSESSMENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if assessment.active else "Ne"),
            )
            if self._selected_assessment_id == assessment.id:
                selected_row = row_index

        configure_table_columns(self.table, "hazard_risk_assessments")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        self.table.blockSignals(False)

    def _update_summary(self) -> None:
        store = self._store()
        if store is not None:
            summary = store.get_active_status_summary()
        else:
            summary = hazard_risk_assessment_service.get_active_status_summary(
                self._identification_id,
            )
        self.summary_label.setText(
            f"Posouzení celkem: {summary['total']} | "
            f"Rozpracovaná: {summary['draft']} | "
            f"Dokončená: {summary['completed']}"
        )

    def _selected_assessment(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), RISK_ASSESSMENT_COL_ID)
        if id_item is None:
            return None
        assessment_id = int(id_item.text())
        store = self._store()
        if store is not None:
            for row in store.list_assessment_rows(include_inactive=True):
                if row.assessment.id == assessment_id:
                    return row.assessment
            return None
        return hazard_risk_assessment_service.get_by_id(assessment_id)
