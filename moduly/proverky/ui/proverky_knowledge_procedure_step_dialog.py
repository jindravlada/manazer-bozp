from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box


class ProverkyKnowledgeProcedureStepDialog(QDialog):
    """Dialog pro přidání nebo úpravu kroku postupu kontroly."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        item: dict | None = None,
        existing_ids: set[str] | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(560, 280)

        self._original_id = str((item or {}).get("id") or "").strip()
        self._existing_ids = set(existing_ids or set())
        if self._original_id:
            self._existing_ids.discard(self._original_id)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setText(self._original_id)
        self._id_edit.setPlaceholderText("Automaticky z textu, pokud necháte prázdné")

        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(str((item or {}).get("text") or ""))
        self._text_edit.setMinimumHeight(120)

        self._aktivni_check = QCheckBox("Aktivní")
        self._aktivni_check.setChecked(bool((item or {}).get("aktivni", True)))

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Text kroku:", self._text_edit)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict | None:
        text = self._text_edit.toPlainText().strip()
        if not text:
            return None

        item_id = self._id_edit.text().strip() or self._original_id
        return {
            "id": item_id,
            "text": text,
            "aktivni": self._aktivni_check.isChecked(),
        }

    def _accept(self) -> None:
        data = self.get_data()
        if data is None:
            QMessageBox.warning(self, self.windowTitle(), "Text kroku je povinný.")
            return

        item_id = data["id"]
        if item_id and item_id in self._existing_ids:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Identifikátor „{item_id}“ už existuje. Zvolte jiný.",
            )
            return

        self.accept()
