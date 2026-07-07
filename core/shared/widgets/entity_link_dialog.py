from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.shared.constants import (
    ENTITY_TYPE_LABELS,
    LINK_TYPE_LABELS,
    VALID_LINK_ENTITY_TYPES,
    VALID_LINK_TYPES,
)
from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box


class EntityLinkDialog(QDialog):
    def __init__(self, parent=None, link=None):
        super().__init__(parent)
        self.link = link

        self.setWindowTitle("Vazba" if link is None else "Upravit vazbu")
        configure_resizable_form_dialog(self, width=560, height=360, min_width=420, min_height=280)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.target_type = QComboBox()
        for key in sorted(VALID_LINK_ENTITY_TYPES, key=lambda item: ENTITY_TYPE_LABELS.get(item, item)):
            label = _entity_type_label(key)
            self.target_type.addItem(label, key)

        self.target_id = QLineEdit()
        self.target_id.setPlaceholderText("Číselné ID cílového objektu")
        self.link_type = QComboBox()
        for key in sorted(VALID_LINK_TYPES, key=lambda item: LINK_TYPE_LABELS[item]):
            self.link_type.addItem(LINK_TYPE_LABELS[key], key)
        self.note = QTextEdit()
        self.note.setMinimumHeight(80)

        form.addRow("Cílový typ entity:", self.target_type)
        form.addRow("Cílové ID:", self.target_id)
        form.addRow("Typ vazby:", self.link_type)
        form.addRow("Poznámka:", self.note)

        layout.addLayout(form)
        layout.addWidget(create_save_cancel_box(self))

        if link is not None:
            self._load_link(link)

    def _load_link(self, link) -> None:
        index = self.target_type.findData(link.target_type)
        self.target_type.setCurrentIndex(index if index >= 0 else 0)
        self.target_id.setText(str(link.target_id))
        index = self.link_type.findData(link.link_type)
        self.link_type.setCurrentIndex(index if index >= 0 else 0)
        self.note.setPlainText(link.note)

    def get_data(self) -> dict:
        target_type = self.target_type.currentData() or ""
        link_type = self.link_type.currentData() or ""
        target_id_text = self.target_id.text().strip()
        target_id = int(target_id_text) if target_id_text else 0

        return {
            "target_type": target_type,
            "target_id": target_id,
            "link_type": link_type,
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if data["target_type"] not in VALID_LINK_ENTITY_TYPES:
            QMessageBox.warning(self, "Vazba", "Vyberte cílový typ entity.")
            return
        if data["target_id"] <= 0:
            QMessageBox.warning(self, "Vazba", "Zadejte platné cílové ID.")
            return
        if data["link_type"] not in VALID_LINK_TYPES:
            QMessageBox.warning(self, "Vazba", "Vyberte typ vazby.")
            return
        super().accept()


def _entity_type_label(entity_type: str) -> str:
    return ENTITY_TYPE_LABELS.get(entity_type, entity_type)
