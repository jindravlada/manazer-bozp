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
    EXISTING_MEASURE_COL_ACTIVE,
    EXISTING_MEASURE_COL_DESCRIPTION,
    EXISTING_MEASURE_COL_ID,
    EXISTING_MEASURE_COL_NOTE,
    EXISTING_MEASURE_COLUMN_COUNT,
    EXISTING_MEASURE_SELECT_ASSESSMENT,
    EXISTING_MEASURE_TABLE_HEADERS,
    EXISTING_MEASURES_TITLE,
    HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
)
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
    find_identification_working_copy,
)
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    HazardExistingMeasureError,
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.ui.hazard_existing_measure_dialog import HazardExistingMeasureDialog


class HazardExistingMeasuresWidget(QWidget):
    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)

        self._on_changed = on_changed
        self._identification_id: int | None = None
        self._assessment = None
        self._read_only = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        group = QGroupBox(EXISTING_MEASURES_TITLE)
        group_layout = QVBoxLayout(group)

        self.header_label = QLabel(EXISTING_MEASURE_SELECT_ASSESSMENT)
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
        self.table.setColumnCount(EXISTING_MEASURE_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(EXISTING_MEASURE_TABLE_HEADERS)
        self.table.setColumnHidden(EXISTING_MEASURE_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_existing_measures")
        group_layout.addWidget(self.table)

        layout.addWidget(group)

        self.add_btn.clicked.connect(self.add_measure)
        self.edit_btn.clicked.connect(self.edit_selected_measure)
        self.activate_btn.clicked.connect(self.activate_selected_measure)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_measure)
        self.table.doubleClicked.connect(self.edit_selected_measure)

        self.set_assessment(None, identification_id=None, read_only=False)

    def _store(self):
        return find_identification_working_copy(self)

    def _notify_editor_dirty(self) -> None:
        window = self.window()
        update = getattr(window, "_update_save_enabled", None)
        if callable(update):
            update()

    def _assessment_header_text(self) -> str:
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
            format_exposed_target_names,
            refs_from_legacy_group_ids,
        )

        store = self._store()
        if store is not None and self._assessment is not None:
            wc_assessment = store.get_assessment(self._assessment.id)
            if wc_assessment is not None:
                refs = list(getattr(wc_assessment, "target_refs", []) or [])
                if not refs:
                    refs = refs_from_legacy_group_ids(
                        wc_assessment.exposed_group_ids,
                        legacy_single_id=wc_assessment.exposed_group_id,
                    )
                names = format_exposed_target_names(refs)
                if names:
                    return names
                if wc_assessment.exposed_group:
                    return wc_assessment.exposed_group
                return "—"
        return hazard_risk_assessment_service.get_exposed_group_display_name(self._assessment)

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
            self.header_label.setText(EXISTING_MEASURE_SELECT_ASSESSMENT)
            self.table.setRowCount(0)
            return

        self.header_label.setText(self._assessment_header_text())
        self._load_table()

    def add_measure(self) -> None:
        if not self._ensure_editable():
            return

        dialog = HazardExistingMeasureDialog(
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
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                "Vyberte existující opatření.",
            )
            return

        dialog = HazardExistingMeasureDialog(
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
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                "Vyberte existující opatření.",
            )
            return
        if measure.active:
            QMessageBox.information(
                self,
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                "Opatření je již aktivní.",
            )
            return

        store = self._store()
        try:
            if store is not None:
                store.activate_existing_measure(measure.id)
            else:
                hazard_existing_measure_service.activate_measure(measure.id)
        except HazardExistingMeasureError as error:
            QMessageBox.warning(self, HAZARD_EXISTING_MEASURE_DIALOG_TITLE, str(error))
            return
        self._notify_changed()

    def deactivate_selected_measure(self) -> None:
        if not self._ensure_editable():
            return

        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(
                self,
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                "Vyberte existující opatření.",
            )
            return
        if not measure.active:
            QMessageBox.information(
                self,
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                "Opatření je již neaktivní.",
            )
            return

        store = self._store()
        if store is not None:
            store.deactivate_existing_measure(measure.id)
        else:
            hazard_existing_measure_service.deactivate_measure(measure.id)
        self._notify_changed()

    def _notify_changed(self) -> None:
        self.refresh()
        if self._on_changed is not None:
            self._on_changed()
        self._notify_editor_dirty()

    def _ensure_editable(self) -> bool:
        if self._identification_id is None or self._assessment is None:
            QMessageBox.information(
                self,
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                EXISTING_MEASURE_SELECT_ASSESSMENT,
            )
            return False
        if self._read_only:
            QMessageBox.information(
                self,
                HAZARD_EXISTING_MEASURE_DIALOG_TITLE,
                "Existující opatření jsou u dokončené nebo archivované identifikace "
                "pouze pro čtení.",
            )
            return False
        return True

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        if self._assessment is None:
            return

        store = self._store()
        if store is not None:
            measures = store.get_existing_measures_for_assessment(
                self._assessment.id,
                include_inactive=True,
            )
        else:
            measures = hazard_existing_measure_service.get_for_assessment(
                self._assessment.id,
                include_inactive=True,
            )
        self.table.setRowCount(len(measures))
        for row_index, measure in enumerate(measures):
            self.table.setItem(
                row_index,
                EXISTING_MEASURE_COL_ID,
                QTableWidgetItem(str(measure.id)),
            )
            self.table.setItem(
                row_index,
                EXISTING_MEASURE_COL_DESCRIPTION,
                create_preview_table_item(measure.description),
            )
            self.table.setItem(
                row_index,
                EXISTING_MEASURE_COL_NOTE,
                create_preview_table_item(measure.note or ""),
            )
            self.table.setItem(
                row_index,
                EXISTING_MEASURE_COL_ACTIVE,
                QTableWidgetItem("Ano" if measure.active else "Ne"),
            )
        configure_table_columns(self.table, "hazard_existing_measures")

    def _selected_measure(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        id_item = self.table.item(selected[0].row(), EXISTING_MEASURE_COL_ID)
        if id_item is None:
            return None
        measure_id = int(id_item.text())
        store = self._store()
        if store is not None:
            for measure in store.get_existing_measures_for_assessment(
                self._assessment.id,
                include_inactive=True,
            ):
                if measure.id == measure_id:
                    return measure
            return None
        return hazard_existing_measure_service.get_by_id(measure_id)
