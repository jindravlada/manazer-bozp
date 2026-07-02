"""Dialog pro vytvoření nebo editaci auditního tvrzení."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.constants import (
    CONTROL_POINT_SEVERITY_DEFAULT,
    CONTROL_POINT_SEVERITY_OPTIONS,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeAssertionDialog(QDialog):
    """Formulář auditního tvrzení — ID je při editaci read-only."""

    def __init__(
        self,
        *,
        existing_ids: set[str] | None = None,
        assertion: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._existing_ids = set(existing_ids or [])
        self._editing_id = str(assertion.get("id") or "").strip() if assertion else ""

        self.setWindowTitle(
            "Upravit auditní tvrzení" if self._editing_id else "Nové auditní tvrzení"
        )
        self.resize(640, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setReadOnly(True)
        if self._editing_id:
            self._id_edit.setText(self._editing_id)
        else:
            self._id_edit.setPlaceholderText("Vygeneruje se z textu tvrzení")

        self._text_edit = QTextEdit()
        self._text_edit.setMinimumHeight(80)
        self._text_edit.textChanged.connect(self._update_generated_id_preview)

        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(90)

        self._severity_combo = QComboBox()
        for value, label in CONTROL_POINT_SEVERITY_OPTIONS:
            self._severity_combo.addItem(label, value)

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)

        self._aktivni_check = QCheckBox("Tvrzení je aktivní")

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Text tvrzení:", self._text_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow("Závažnost:", self._severity_combo)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if assertion:
            self._text_edit.setPlainText(str(assertion.get("text") or assertion.get("nazev") or ""))
            self._popis_edit.setPlainText(str(assertion.get("popis") or ""))
            severity = audit_knowledge_service.normalize_control_point_severity(
                assertion.get("zavaznost")
            )
            severity_index = self._severity_combo.findData(severity)
            if severity_index >= 0:
                self._severity_combo.setCurrentIndex(severity_index)
            self._poradi_spin.setValue(int(assertion.get("poradi") or 0))
            self._aktivni_check.setChecked(bool(assertion.get("aktivni", True)))
        else:
            default_index = self._severity_combo.findData(CONTROL_POINT_SEVERITY_DEFAULT)
            if default_index >= 0:
                self._severity_combo.setCurrentIndex(default_index)
            self._poradi_spin.setValue(10)
            self._aktivni_check.setChecked(True)
            self._update_generated_id_preview()

    def _update_generated_id_preview(self) -> None:
        if self._editing_id:
            return
        text = self._text_edit.toPlainText().strip()
        if not text:
            self._id_edit.clear()
            self._id_edit.setPlaceholderText("Vygeneruje se z textu tvrzení")
            return
        generated = audit_knowledge_service.generate_item_id(text, self._existing_ids)
        self._id_edit.setText(generated)

    def _accept_if_valid(self) -> None:
        if not self.assertion_payload()["text"]:
            self._text_edit.setFocus()
            return
        self.accept()

    def assertion_payload(self) -> dict:
        return {
            "id": self._editing_id or self._id_edit.text().strip(),
            "text": self._text_edit.toPlainText().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "zavaznost": self._severity_combo.currentData(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }

    @property
    def editing_assertion_id(self) -> str:
        return self._editing_id
