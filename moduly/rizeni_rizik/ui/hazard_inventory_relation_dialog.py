from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORY_LABELS,
    HAZARD_INVENTORY_RELATION_TYPES,
    HAZARD_INVENTORY_RELATION_TYPE_LABELS,
    INVENTORY_RELATION_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_relation_service import (
    HazardInventoryRelationError,
    hazard_inventory_relation_service,
)


class HazardInventoryRelationDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        hazard_identification_id: int,
        source_item,
        relation=None,
        read_only: bool = False,
    ):
        super().__init__(parent)

        self.hazard_identification_id = hazard_identification_id
        self.source_item = source_item
        self.relation = relation
        self.read_only = read_only

        self.setWindowTitle(INVENTORY_RELATION_DIALOG_TITLE)
        self.resize(560, 380)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        source_label = (
            f"{source_item.name} "
            f"({HAZARD_INVENTORY_CATEGORY_LABELS.get(source_item.category, source_item.category)})"
        )
        self.source_display = QLineEdit(source_label)
        self.source_display.setReadOnly(True)

        self.relation_type = QComboBox()
        for relation_type in HAZARD_INVENTORY_RELATION_TYPES:
            self.relation_type.addItem(
                HAZARD_INVENTORY_RELATION_TYPE_LABELS[relation_type],
                relation_type,
            )

        self.target_item = QComboBox()
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(80)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Zdrojová položka:", self.source_display)
        form.addRow("Typ souvislosti *:", self.relation_type)
        form.addRow("Související položka *:", self.target_item)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.relation_type.currentIndexChanged.connect(self._refresh_target_items)

        if relation is not None:
            self._select_combo_value(self.relation_type, relation.relation_type)
            self._refresh_target_items(preserve_target_id=relation.target_item_id)
            self.note.setPlainText(relation.note or "")
            self.active_checkbox.setChecked(bool(relation.active))
        else:
            self._refresh_target_items()

        if read_only:
            self.relation_type.setEnabled(False)
            self.target_item.setEnabled(False)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
            if save_button is not None:
                save_button.setEnabled(False)

    def _refresh_target_items(self, *, preserve_target_id: int | None = None) -> None:
        relation_type = self.relation_type.currentData()
        candidates = hazard_inventory_relation_service.get_target_candidates(
            hazard_identification_id=self.hazard_identification_id,
            source_item_id=self.source_item.id,
            relation_type=relation_type,
        )

        self.target_item.blockSignals(True)
        self.target_item.clear()
        for candidate in candidates:
            self.target_item.addItem(candidate.name, candidate.id)

        if preserve_target_id is not None:
            self._select_combo_value(self.target_item, preserve_target_id)
        elif self.target_item.count() > 0:
            self.target_item.setCurrentIndex(0)
        else:
            self.target_item.setCurrentIndex(-1)
        self.target_item.blockSignals(False)

    @staticmethod
    def _select_combo_value(combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else -1)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        target_item_id = self.target_item.currentData()
        if target_item_id is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                INVENTORY_RELATION_DIALOG_TITLE,
                "Vyberte související položku.",
            )
            return

        data = self.get_data()
        try:
            if self.relation is None:
                hazard_inventory_relation_service.create_relation(
                    hazard_identification_id=self.hazard_identification_id,
                    source_item_id=self.source_item.id,
                    **data,
                )
            else:
                hazard_inventory_relation_service.update_relation(
                    self.relation.id,
                    **data,
                )
        except HazardInventoryRelationError as error:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, INVENTORY_RELATION_DIALOG_TITLE, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "relation_type": self.relation_type.currentData(),
            "target_item_id": self.target_item.currentData(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
        }
