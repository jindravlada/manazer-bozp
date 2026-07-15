from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE,
    HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP,
    HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ID,
    HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY,
    HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COLUMN_COUNT,
    HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_TABLE_HEADERS,
    HAZARD_LIBRARY_TEMPLATE_EXISTING_MEASURES_TITLE,
    HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
    HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
    HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ID,
    HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE,
    HAZARD_LIBRARY_TEMPLATE_MEASURE_COLUMN_COUNT,
    HAZARD_LIBRARY_TEMPLATE_MEASURE_TABLE_HEADERS,
    HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
    HAZARD_LIBRARY_TEMPLATE_SELECT_ASSESSMENT,
    HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE,
    HAZARD_LIBRARY_ASSESSMENTS_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    HazardLibraryTemplateAssessmentError,
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    HazardLibraryTemplateExistingMeasureError,
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    HazardLibraryTemplateRequiredMeasureError,
    hazard_library_template_required_measure_service,
)
from moduly.rizeni_rizik.ui.hazard_library_template_assessment_dialog import (
    HazardLibraryTemplateAssessmentDialog,
)
from moduly.rizeni_rizik.ui.hazard_library_template_measure_dialog import (
    HazardLibraryTemplateMeasureDialog,
)


class _TemplateMeasuresSection(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        title: str,
        measure_type: str,
        on_changed=None,
    ):
        super().__init__(parent)
        self.measure_type = measure_type
        self._on_changed = on_changed
        self._template_id: int | None = None
        self._assessment_id: int | None = None
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)

        self.header_label = QLabel(HAZARD_LIBRARY_TEMPLATE_SELECT_ASSESSMENT)
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
        self.table.setColumnCount(HAZARD_LIBRARY_TEMPLATE_MEASURE_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(HAZARD_LIBRARY_TEMPLATE_MEASURE_TABLE_HEADERS)
        self.table.setColumnHidden(HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, f"hazard_library_template_{measure_type}_measures")
        group_layout.addWidget(self.table)

        layout.addWidget(group)

        self.add_btn.clicked.connect(self.add_measure)
        self.edit_btn.clicked.connect(self.edit_selected_measure)
        self.activate_btn.clicked.connect(self.activate_selected_measure)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_measure)
        self.table.doubleClicked.connect(self.edit_selected_measure)

    def set_assessment(
        self,
        assessment_id: int | None,
        *,
        template_id: int | None,
        read_only: bool,
    ) -> None:
        self._assessment_id = assessment_id
        self._template_id = template_id
        self._read_only = read_only
        editable = not read_only and template_id is not None and assessment_id is not None
        for button in (
            self.add_btn,
            self.edit_btn,
            self.activate_btn,
            self.deactivate_btn,
        ):
            button.setEnabled(editable)
        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if self._assessment_id is None:
            self.header_label.setText(HAZARD_LIBRARY_TEMPLATE_SELECT_ASSESSMENT)
            return

        if self.measure_type == "existing":
            measures = hazard_library_template_existing_measure_service.get_for_assessment(
                self._assessment_id,
                include_inactive=True,
            )
        else:
            measures = hazard_library_template_required_measure_service.get_for_assessment(
                self._assessment_id,
                include_inactive=True,
            )

        self.table.setRowCount(len(measures))
        for row_index, measure in enumerate(measures):
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ID,
                QTableWidgetItem(str(measure.id)),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
                create_preview_table_item(measure.description),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_NOTE,
                create_preview_table_item(measure.note),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
                QTableWidgetItem("Ano" if measure.active else "Ne"),
            )
        configure_table_columns(self.table, f"hazard_library_template_{self.measure_type}_measures")

    def _selected_measure(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ID)
        if id_item is None:
            return None
        measure_id = int(id_item.text())
        if self.measure_type == "existing":
            return hazard_library_template_existing_measure_service.get_by_id(measure_id)
        return hazard_library_template_required_measure_service.get_by_id(measure_id)

    def _ensure_editable(self) -> bool:
        if self._template_id is None or self._assessment_id is None:
            return False
        if self._read_only:
            return False
        return True

    def add_measure(self) -> None:
        if not self._ensure_editable():
            return
        dialog = HazardLibraryTemplateMeasureDialog(
            self,
            template_id=self._template_id,
            template_assessment_id=self._assessment_id,
            measure_type=self.measure_type,
        )
        if dialog.exec():
            self.refresh()
            self._notify_changed()

    def edit_selected_measure(self) -> None:
        measure = self._selected_measure()
        if measure is None:
            return
        dialog = HazardLibraryTemplateMeasureDialog(
            self,
            template_id=self._template_id,
            template_assessment_id=self._assessment_id,
            measure=measure,
            measure_type=self.measure_type,
            read_only=self._read_only,
        )
        if dialog.exec():
            self.refresh()
            self._notify_changed()

    def activate_selected_measure(self) -> None:
        if not self._ensure_editable():
            return
        measure = self._selected_measure()
        if measure is None or measure.active:
            return
        title = (
            HAZARD_LIBRARY_TEMPLATE_EXISTING_MEASURES_TITLE
            if self.measure_type == "existing"
            else HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE
        )
        try:
            if self.measure_type == "existing":
                hazard_library_template_existing_measure_service.activate_measure(measure.id)
            else:
                hazard_library_template_required_measure_service.activate_measure(measure.id)
        except (
            HazardLibraryTemplateExistingMeasureError,
            HazardLibraryTemplateRequiredMeasureError,
        ) as error:
            QMessageBox.warning(self, title, str(error))
            return
        self.refresh()
        self._notify_changed()

    def deactivate_selected_measure(self) -> None:
        if not self._ensure_editable():
            return
        measure = self._selected_measure()
        if measure is None or not measure.active:
            return
        if self.measure_type == "existing":
            hazard_library_template_existing_measure_service.deactivate_measure(measure.id)
        else:
            hazard_library_template_required_measure_service.deactivate_measure(measure.id)
        self.refresh()
        self._notify_changed()

    def _notify_changed(self) -> None:
        if self._on_changed is not None:
            self._on_changed()


class HazardLibraryTemplateAssessmentsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        template_id: int,
        template_event_id: int,
        event_name: str,
        read_only: bool = False,
        on_content_changed=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(HAZARD_LIBRARY_ASSESSMENTS_DIALOG_TITLE)
        self.resize(900, 720)

        layout = QVBoxLayout(self)
        self._panel = _HazardLibraryTemplateAssessmentsPanel(
            template_id=template_id,
            template_event_id=template_event_id,
            event_name=event_name,
            read_only=read_only,
            on_content_changed=on_content_changed,
        )
        layout.addWidget(self._panel)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def refresh(self) -> None:
        self._panel.refresh()


class _HazardLibraryTemplateAssessmentsPanel(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        template_id: int,
        template_event_id: int,
        event_name: str,
        read_only: bool = False,
        on_content_changed=None,
    ):
        super().__init__(parent)
        self.template_id = template_id
        self.template_event_id = template_event_id
        self.event_name = event_name
        self.read_only = read_only
        self._on_content_changed = on_content_changed
        self._selected_assessment_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            f"Posouzení a opatření pro událost: {event_name}"
        )
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
        self.table.setColumnCount(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_TABLE_HEADERS)
        self.table.setColumnHidden(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_library_template_assessments")
        layout.addWidget(self.table, 2)

        self.existing_measures = _TemplateMeasuresSection(
            title=HAZARD_LIBRARY_TEMPLATE_EXISTING_MEASURES_TITLE,
            measure_type="existing",
            on_changed=self._notify_content_changed,
        )
        layout.addWidget(self.existing_measures, 1)

        self.required_measures = _TemplateMeasuresSection(
            title=HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
            measure_type="required",
            on_changed=self._notify_content_changed,
        )
        layout.addWidget(self.required_measures, 1)

        self.add_btn.clicked.connect(self.add_assessment)
        self.edit_btn.clicked.connect(self.edit_selected_assessment)
        self.activate_btn.clicked.connect(self.activate_selected_assessment)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_assessment)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self.edit_selected_assessment)

        self._set_actions_enabled(not read_only)
        self.refresh()

    def refresh(self) -> None:
        rows = hazard_library_template_assessment_service.get_for_event(
            self.template_event_id,
            include_inactive=True,
        )
        self.table.setRowCount(len(rows))
        selected_row = -1
        for row_index, row in enumerate(rows):
            assessment = row.assessment
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ID,
                QTableWidgetItem(str(assessment.id)),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP,
                QTableWidgetItem(row.exposed_group_name),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY,
                QTableWidgetItem(row.severity_label),
            )
            self.table.setItem(
                row_index,
                HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE,
                QTableWidgetItem("Ano" if assessment.active else "Ne"),
            )
            if self._selected_assessment_id == assessment.id:
                selected_row = row_index

        configure_table_columns(self.table, "hazard_library_template_assessments")
        if selected_row >= 0:
            self.table.selectRow(selected_row)
        else:
            self._selected_assessment_id = None
        self._sync_measures()

    def add_assessment(self) -> None:
        if self.read_only:
            return
        dialog = HazardLibraryTemplateAssessmentDialog(
            self,
            template_id=self.template_id,
            template_event_id=self.template_event_id,
        )
        if dialog.exec():
            self.refresh()
            self._notify_content_changed()

    def edit_selected_assessment(self) -> None:
        assessment = self._selected_assessment()
        if assessment is None:
            return
        dialog = HazardLibraryTemplateAssessmentDialog(
            self,
            template_id=self.template_id,
            template_event_id=self.template_event_id,
            assessment=assessment,
            read_only=self.read_only,
        )
        if dialog.exec():
            self.refresh()
            self._notify_content_changed()

    def activate_selected_assessment(self) -> None:
        if self.read_only:
            return
        assessment = self._selected_assessment()
        if assessment is None or assessment.active:
            return
        try:
            hazard_library_template_assessment_service.activate_assessment(assessment.id)
        except HazardLibraryTemplateAssessmentError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_ASSESSMENT_DIALOG_TITLE, str(error))
            return
        self.refresh()
        self._notify_content_changed()

    def deactivate_selected_assessment(self) -> None:
        if self.read_only:
            return
        assessment = self._selected_assessment()
        if assessment is None or not assessment.active:
            return
        hazard_library_template_assessment_service.deactivate_assessment(assessment.id)
        self.refresh()
        self._notify_content_changed()

    def _set_actions_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_btn,
            self.edit_btn,
            self.activate_btn,
            self.deactivate_btn,
        ):
            button.setEnabled(enabled)

    def _on_selection_changed(self) -> None:
        assessment = self._selected_assessment()
        self._selected_assessment_id = assessment.id if assessment is not None else None
        self._sync_measures()

    def _sync_measures(self) -> None:
        self.existing_measures.set_assessment(
            self._selected_assessment_id,
            template_id=self.template_id,
            read_only=self.read_only,
        )
        self.required_measures.set_assessment(
            self._selected_assessment_id,
            template_id=self.template_id,
            read_only=self.read_only,
        )

    def _selected_assessment(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ID)
        if id_item is None:
            return None
        return hazard_library_template_assessment_service.get_by_id(int(id_item.text()))

    def _notify_content_changed(self) -> None:
        if self._on_content_changed is not None:
            self._on_content_changed()
