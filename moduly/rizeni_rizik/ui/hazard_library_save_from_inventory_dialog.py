from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QLineEdit,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants_library import (
    DEFAULT_HAZARD_LIBRARY_SCOPE,
    HAZARD_LIBRARY_SAVE_FROM_INVENTORY_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_import_service import (
    HazardLibraryTemplateImportError,
    HazardLibraryTemplateImportResult,
    hazard_library_template_import_service,
)


class HazardLibrarySaveFromInventoryDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        inventory_item_id: int,
        default_name: str,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.inventory_item_id = inventory_item_id
        self.result: HazardLibraryTemplateImportResult | None = None

        self.setWindowTitle(HAZARD_LIBRARY_SAVE_FROM_INVENTORY_DIALOG_TITLE)
        self.resize(640, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setText(default_name)
        self.description = QTextEdit()
        self.description.setMinimumHeight(80)
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)
        self.include_inactive = QCheckBox("Zahrnout neaktivní záznamy")
        self.include_inactive.setChecked(False)

        form.addRow("Název vzoru *:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.include_inactive)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        try:
            self.result = hazard_library_template_import_service.import_inventory_item(
                hazard_identification_id=self.hazard_identification_id,
                inventory_item_id=self.inventory_item_id,
                name=self.name.text().strip(),
                description=self.description.toPlainText().strip(),
                application_scope=DEFAULT_HAZARD_LIBRARY_SCOPE,
                note=self.note.toPlainText().strip(),
                operation_ids=[],
                include_inactive=self.include_inactive.isChecked(),
            )
        except HazardLibraryTemplateImportError as error:
            QMessageBox.warning(
                self,
                HAZARD_LIBRARY_SAVE_FROM_INVENTORY_DIALOG_TITLE,
                str(error),
            )
            return
        super().accept()
