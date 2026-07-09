from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.shared.constants import ENTITY_LEGAL_REQUIREMENT, LINK_TYPE_LABELS, VALID_LINK_TYPES
from core.widgets.dialog_utils import add_save_cancel_footer, configure_resizable_form_dialog
from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service

_PROCESS_TARGET_EMPTY = "— vyberte cílový proces —"


class LegalRequirementProcessLinkDialog(QDialog):
    def __init__(self, parent=None, link=None, source_id: int | None = None):
        super().__init__(parent)
        self.link = link
        self.source_id = source_id

        self.setWindowTitle("Vazba procesu" if link is None else "Upravit vazbu procesu")
        configure_resizable_form_dialog(self, width=560, height=360, min_width=420, min_height=280)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.target_process = QComboBox()
        self.link_type = QComboBox()
        for key in sorted(VALID_LINK_TYPES, key=lambda item: LINK_TYPE_LABELS[item]):
            self.link_type.addItem(LINK_TYPE_LABELS[key], key)
        self.note = QTextEdit()
        self.note.setMinimumHeight(80)

        form.addRow("Cílový proces:", self.target_process)
        form.addRow("Typ vazby:", self.link_type)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)
        add_save_cancel_footer(layout, self)

        selected_id = link.target_id if link is not None else None
        self._populate_target_process_combo(selected_id)
        if link is not None:
            index = self.link_type.findData(link.link_type)
            self.link_type.setCurrentIndex(index if index >= 0 else 0)
            self.note.setPlainText(link.note)

    def _populate_target_process_combo(self, selected_id: int | None) -> None:
        self.target_process.blockSignals(True)
        try:
            self.target_process.clear()
            self.target_process.addItem(_PROCESS_TARGET_EMPTY)
            self.target_process.setItemData(0, None, Qt.ItemDataRole.UserRole)

            selected_in_list = False
            for process in legal_requirement_service.list_active_processes():
                if self.source_id is not None and process.id == self.source_id:
                    continue
                index = self.target_process.count()
                self.target_process.addItem(legal_requirement_merged_target_label(process))
                self.target_process.setItemData(index, process.id, Qt.ItemDataRole.UserRole)
                if selected_id == process.id:
                    selected_in_list = True

            if selected_id is not None and not selected_in_list:
                requirement = legal_requirement_service.get_by_id(selected_id)
                if requirement is not None:
                    index = self.target_process.count()
                    self.target_process.addItem(legal_requirement_merged_target_label(requirement))
                    self.target_process.setItemData(index, requirement.id, Qt.ItemDataRole.UserRole)

            target_index = 0
            for index in range(self.target_process.count()):
                if self.target_process.itemData(index, Qt.ItemDataRole.UserRole) == selected_id:
                    target_index = index
                    break
            self.target_process.setCurrentIndex(target_index)
        finally:
            self.target_process.blockSignals(False)

    def get_data(self) -> dict:
        target_id = self.target_process.currentData(Qt.ItemDataRole.UserRole)
        link_type = self.link_type.currentData() or ""

        return {
            "target_type": ENTITY_LEGAL_REQUIREMENT,
            "target_id": int(target_id) if target_id is not None else 0,
            "link_type": link_type,
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if data["target_id"] <= 0:
            QMessageBox.warning(self, "Vazba procesu", "Vyberte cílový proces.")
            return
        if data["link_type"] not in VALID_LINK_TYPES:
            QMessageBox.warning(self, "Vazba procesu", "Vyberte typ vazby.")
            return
        super().accept()
