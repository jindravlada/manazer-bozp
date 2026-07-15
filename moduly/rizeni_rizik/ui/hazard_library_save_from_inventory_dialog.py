from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QLineEdit,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants_library import (
    DEFAULT_HAZARD_LIBRARY_SCOPE,
    HAZARD_LIBRARY_SAVE_FROM_INVENTORY_DIALOG_TITLE,
    HAZARD_LIBRARY_SCOPE_LABELS,
    HAZARD_LIBRARY_SCOPE_SELECTED,
    HAZARD_LIBRARY_SCOPES,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_import_service import (
    HazardLibraryTemplateImportError,
    HazardLibraryTemplateImportResult,
    hazard_library_template_import_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
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
        self.resize(640, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setText(default_name)
        self.description = QTextEdit()
        self.description.setMinimumHeight(80)
        self.application_scope = QComboBox()
        for scope in HAZARD_LIBRARY_SCOPES:
            self.application_scope.addItem(HAZARD_LIBRARY_SCOPE_LABELS[scope], scope)
        manual_index = self.application_scope.findData(DEFAULT_HAZARD_LIBRARY_SCOPE)
        if manual_index >= 0:
            self.application_scope.setCurrentIndex(manual_index)
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)
        self.include_inactive = QCheckBox("Zahrnout neaktivní záznamy")
        self.include_inactive.setChecked(False)

        form.addRow("Název vzoru *:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("Rozsah použití *:", self.application_scope)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.include_inactive)

        layout.addLayout(form)

        self.operations_label = QLabel("Vybrané provozy:")
        self.operations_list = QListWidget()
        self.operations_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.operations_list.setMinimumHeight(140)
        layout.addWidget(self.operations_label)
        layout.addWidget(self.operations_list)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.application_scope.currentIndexChanged.connect(self._update_operations_enabled)
        self._load_operations()
        self._update_operations_enabled()

    def _load_operations(self) -> None:
        self.operations_list.clear()
        for operation in hazard_library_template_service.get_active_operations():
            item = QListWidgetItem(operation.name)
            item.setData(256, operation.id)
            self.operations_list.addItem(item)

    def _update_operations_enabled(self) -> None:
        selected_scope = self.application_scope.currentData()
        enabled = selected_scope == HAZARD_LIBRARY_SCOPE_SELECTED
        self.operations_label.setEnabled(enabled)
        self.operations_list.setEnabled(enabled)
        if not enabled:
            self.operations_list.clearSelection()

    def _selected_operation_ids(self) -> list[int]:
        return [
            item.data(256)
            for item in self.operations_list.selectedItems()
            if item.data(256) is not None
        ]

    def accept(self) -> None:
        try:
            self.result = hazard_library_template_import_service.import_inventory_item(
                hazard_identification_id=self.hazard_identification_id,
                inventory_item_id=self.inventory_item_id,
                name=self.name.text().strip(),
                description=self.description.toPlainText().strip(),
                application_scope=self.application_scope.currentData(),
                note=self.note.toPlainText().strip(),
                operation_ids=self._selected_operation_ids(),
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
