from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box


class ProverkyKnowledgeReferencePhotoDialog(QDialog):
    """Dialog pro úpravu metadat referenční fotografie."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        item: dict | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(560, 320)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self._nazev_edit = QLineEdit()
        self._nazev_edit.setText(str((item or {}).get("nazev") or ""))

        self._popis_edit = QTextEdit()
        self._popis_edit.setPlainText(str((item or {}).get("popis") or ""))
        self._popis_edit.setMinimumHeight(120)

        form.addRow("Název:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict | None:
        nazev = self._nazev_edit.text().strip()
        if not nazev:
            return None

        return {
            "nazev": nazev,
            "popis": self._popis_edit.toPlainText().strip(),
        }

    def _accept(self) -> None:
        if self.get_data() is None:
            QMessageBox.warning(self, self.windowTitle(), "Název fotografie je povinný.")
            return
        self.accept()
