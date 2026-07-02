"""Dialog pro vytvoření nového řídicího procesu v editoru metodiky auditora."""

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
from moduly.audity.constants import (
    GUIDE_LABEL_EXPECTED_OUTPUT,
    GUIDE_LABEL_UCEL,
    GUIDE_LABEL_WHY_IMPORTANT,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeProcessCreateDialog(QDialog):
    """Formulář nového řídicího procesu — ID se generuje z názvu a po vytvoření se nemění."""

    def __init__(
        self,
        *,
        existing_ids: set[str] | None = None,
        default_poradi: int = 10,
        parent=None,
    ):
        super().__init__(parent)

        self._existing_ids = set(existing_ids or [])

        self.setWindowTitle("Nový řídicí proces")
        self.resize(680, 560)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setReadOnly(True)
        self._id_edit.setPlaceholderText("Vygeneruje se z názvu procesu")

        self._nazev_edit = QLineEdit()
        self._nazev_edit.textChanged.connect(self._update_generated_id_preview)

        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(70)

        self._ucel_edit = QTextEdit()
        self._ucel_edit.setMinimumHeight(70)

        self._proc_je_dulezity_edit = QTextEdit()
        self._proc_je_dulezity_edit.setMinimumHeight(70)

        self._ocekavany_vystup_edit = QTextEdit()
        self._ocekavany_vystup_edit.setMinimumHeight(70)

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)
        self._poradi_spin.setValue(default_poradi)

        self._aktivni_check = QCheckBox("Proces je aktivní")
        self._aktivni_check.setChecked(True)

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Název procesu:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow(f"{GUIDE_LABEL_UCEL}:", self._ucel_edit)
        form.addRow(f"{GUIDE_LABEL_WHY_IMPORTANT}:", self._proc_je_dulezity_edit)
        form.addRow(f"{GUIDE_LABEL_EXPECTED_OUTPUT}:", self._ocekavany_vystup_edit)
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
            self._id_edit.setPlaceholderText("Vygeneruje se z názvu procesu")
            return
        generated = audit_knowledge_service.generate_item_id(nazev, self._existing_ids)
        self._id_edit.setText(generated)

    def _accept_if_valid(self) -> None:
        if not self.process_payload()["nazev"]:
            self._nazev_edit.setFocus()
            return
        self.accept()

    def process_payload(self) -> dict:
        return {
            "id": self._id_edit.text().strip(),
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "ucel_procesu": self._ucel_edit.toPlainText().strip(),
            "proc_je_dulezity": self._proc_je_dulezity_edit.toPlainText().strip(),
            "ocekavany_vystup": self._ocekavany_vystup_edit.toPlainText().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }
