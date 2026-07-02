"""Dialog pro vytvoření nové oblasti ověření v editoru metodiky auditora."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeSectionDialog(QDialog):
    """Formulář nové oblasti ověření — ID se generuje z názvu a po vytvoření se nemění."""

    def __init__(
        self,
        *,
        existing_ids: set[str] | None = None,
        default_poradi: int = 10,
        parent=None,
    ):
        super().__init__(parent)

        self._existing_ids = set(existing_ids or [])

        self.setWindowTitle("Nová oblast ověření")
        self.resize(640, 460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setReadOnly(True)
        self._id_edit.setPlaceholderText("Vygeneruje se z názvu oblasti")

        self._nazev_edit = QLineEdit()
        self._nazev_edit.textChanged.connect(self._update_generated_id_preview)

        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(80)

        self._cil_overeni_edit = QTextEdit()
        self._cil_overeni_edit.setMinimumHeight(80)

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)
        self._poradi_spin.setValue(default_poradi)

        self._aktivni_check = QCheckBox("Oblast je aktivní")
        self._aktivni_check.setChecked(True)

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Název:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow("Cíl ověření:", self._cil_overeni_edit)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _update_generated_id_preview(self) -> None:
        nazev = self._nazev_edit.text().strip()
        if not nazev:
            self._id_edit.clear()
            self._id_edit.setPlaceholderText("Vygeneruje se z názvu oblasti")
            return
        generated = audit_knowledge_service.generate_item_id(nazev, self._existing_ids)
        self._id_edit.setText(generated)

    def _accept_if_valid(self) -> None:
        if not self.section_payload()["nazev"]:
            self._nazev_edit.setFocus()
            return
        self.accept()

    def section_payload(self) -> dict:
        return {
            "id": self._id_edit.text().strip(),
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "cil_overeni": self._cil_overeni_edit.toPlainText().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }
