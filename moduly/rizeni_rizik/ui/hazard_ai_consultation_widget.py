from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import (
    AI_CONSULTATION_DIALOG_TITLE,
    AI_CONSULTATION_EXPORT_BUTTON,
    AI_CONSULTATION_INCLUDE_RESPONSIBLE_PERSON,
    AI_CONSULTATION_INTRO_TEXT,
    AI_EXPORT_COL_ASSESSMENT_COUNT,
    AI_EXPORT_COL_EVENT_COUNT,
    AI_EXPORT_COL_EXPORTED_AT,
    AI_EXPORT_COL_FILENAME,
    AI_EXPORT_COL_HAZARD_COUNT,
    AI_EXPORT_COL_ID,
    AI_EXPORT_COL_ITEM_COUNT,
    AI_EXPORT_COL_SCHEMA_VERSION,
    AI_EXPORT_COLUMN_COUNT,
    AI_EXPORT_TABLE_HEADERS,
)
from moduly.rizeni_rizik.sluzby.hazard_ai_export_service import (
    HazardAiExportError,
    hazard_ai_export_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)


class HazardAiExportOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(AI_CONSULTATION_DIALOG_TITLE)
        self.resize(420, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.include_responsible_person = QCheckBox(AI_CONSULTATION_INCLUDE_RESPONSIBLE_PERSON)
        self.include_responsible_person.setChecked(False)
        form.addRow("", self.include_responsible_person)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Pokračovat")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_include_responsible_person(self) -> bool:
        return self.include_responsible_person.isChecked()


class HazardAiConsultationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._identification_id: int | None = None

        layout = QVBoxLayout(self)

        intro = QLabel(AI_CONSULTATION_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        toolbar = QHBoxLayout()
        self.export_btn = QPushButton(AI_CONSULTATION_EXPORT_BUTTON)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        layout.addWidget(QLabel("Dosud vytvořené exporty:"))

        self.table = QTableWidget()
        self.table.setColumnCount(AI_EXPORT_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(AI_EXPORT_TABLE_HEADERS)
        self.table.setColumnHidden(AI_EXPORT_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        configure_table_columns(self.table, "hazard_ai_exports")
        layout.addWidget(self.table)

        self.export_btn.clicked.connect(self.export_package)
        self.set_identification(None)

    def set_identification(self, identification_id: int | None) -> None:
        self._identification_id = identification_id
        self.export_btn.setEnabled(identification_id is not None)
        self.refresh()

    def refresh(self) -> None:
        self._load_table()

    def export_package(self) -> bool:
        if self._identification_id is None:
            QMessageBox.information(
                self,
                AI_CONSULTATION_DIALOG_TITLE,
                "Export je možné provést až po prvním uložení identifikace.",
            )
            return False

        identification = hazard_identification_service.get_by_id(self._identification_id)
        if identification is None:
            QMessageBox.warning(
                self,
                AI_CONSULTATION_DIALOG_TITLE,
                "Identifikace nebezpečí neexistuje.",
            )
            return False

        options = HazardAiExportOptionsDialog(self)
        if not options.exec():
            return False

        exported_at = datetime.now()
        default_name = hazard_ai_export_service.default_export_filename(
            identification.identification_number,
            exported_at,
        )
        target, _selected_filter = QFileDialog.getSaveFileName(
            self,
            AI_CONSULTATION_DIALOG_TITLE,
            default_name,
            "ZIP soubory (*.zip)",
        )
        if not target:
            return False

        target_path = Path(target)
        if target_path.suffix.lower() != ".zip":
            target_path = target_path.with_suffix(".zip")

        try:
            result = hazard_ai_export_service.export_consultation_package(
                self._identification_id,
                target_path,
                include_responsible_person=options.get_include_responsible_person(),
            )
        except HazardAiExportError as error:
            QMessageBox.warning(self, AI_CONSULTATION_DIALOG_TITLE, str(error))
            return False

        self.refresh()
        QMessageBox.information(
            self,
            AI_CONSULTATION_DIALOG_TITLE,
            (
                f"Export byl vytvořen:\n{result.file_path}\n\n"
                f"Položky analýzy: {result.item_count}\n"
                f"Nebezpečí: {result.hazard_count}\n"
                f"Nežádoucí události: {result.event_count}\n"
                f"Posouzení rizik: {result.assessment_count}\n"
                f"Existující opatření: {result.existing_measure_count}\n"
                f"Potřebná opatření: {result.required_measure_count}"
            ),
        )
        return True

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        if self._identification_id is None:
            return

        rows = hazard_ai_export_service.get_for_identification(self._identification_id)
        self.table.setRowCount(len(rows))
        for row_index, export in enumerate(rows):
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_ID,
                QTableWidgetItem(str(export.id)),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_EXPORTED_AT,
                QTableWidgetItem(export.exported_at.strftime("%d.%m.%Y %H:%M")),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_SCHEMA_VERSION,
                QTableWidgetItem(export.schema_version),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_FILENAME,
                QTableWidgetItem(Path(export.file_path).name),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_ITEM_COUNT,
                QTableWidgetItem(str(export.item_count)),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_HAZARD_COUNT,
                QTableWidgetItem(str(export.hazard_count)),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_EVENT_COUNT,
                QTableWidgetItem(str(export.event_count)),
            )
            self.table.setItem(
                row_index,
                AI_EXPORT_COL_ASSESSMENT_COUNT,
                QTableWidgetItem(str(export.assessment_count)),
            )

        configure_table_columns(self.table, "hazard_ai_exports")
