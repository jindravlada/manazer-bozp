"""Dialog pro vytvoření nebo editaci auditního tvrzení."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.shared.verification_type import VERIFICATION_TYPE_OPTIONS
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_OPERATION,
    AUDIT_QUESTION_KIND_SYSTEM,
    AUDIT_QUESTION_KIND_UNCLASSIFIED,
    CONTROL_POINT_SEVERITY_DEFAULT,
    CONTROL_POINT_SEVERITY_OPTIONS,
    KNOWLEDGE_EDITOR_QUESTION_KIND_LABEL,
    KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED,
    QUESTION_KIND_EDITOR_OPTIONS,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind


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
        self.resize(640, 500)

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

        self._kind_combo = QComboBox()
        for value, label in QUESTION_KIND_EDITOR_OPTIONS:
            self._kind_combo.addItem(label, value)

        self._severity_combo = QComboBox()
        for value, label in CONTROL_POINT_SEVERITY_OPTIONS:
            self._severity_combo.addItem(label, value)

        self._verification_group = QButtonGroup(self)
        verification_row = QWidget()
        verification_layout = QHBoxLayout(verification_row)
        verification_layout.setContentsMargins(0, 0, 0, 0)
        verification_layout.setSpacing(16)
        self._verification_radios: dict[str, QRadioButton] = {}
        for value, label in VERIFICATION_TYPE_OPTIONS:
            radio = QRadioButton(label)
            radio.setProperty("verification_type", value)
            self._verification_group.addButton(radio)
            self._verification_radios[value] = radio
            verification_layout.addWidget(radio)
        verification_layout.addStretch()

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)

        self._aktivni_check = QCheckBox("Tvrzení je aktivní")

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Text tvrzení:", self._text_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow(KNOWLEDGE_EDITOR_QUESTION_KIND_LABEL, self._kind_combo)
        form.addRow("Závažnost:", self._severity_combo)
        form.addRow("Typ ověření:", verification_row)
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
            self._set_verification_type(
                audit_knowledge_service.normalize_verification_type(
                    assertion.get("verification_type")
                )
            )
            self._set_question_kind(interpret_question_kind(assertion.get("question_kind")))
        else:
            default_index = self._severity_combo.findData(CONTROL_POINT_SEVERITY_DEFAULT)
            if default_index >= 0:
                self._severity_combo.setCurrentIndex(default_index)
            self._poradi_spin.setValue(10)
            self._aktivni_check.setChecked(True)
            self._set_verification_type(
                audit_knowledge_service.normalize_verification_type(None)
            )
            self._set_question_kind(AUDIT_QUESTION_KIND_UNCLASSIFIED)
            self._update_generated_id_preview()

    def _set_question_kind(self, kind: str) -> None:
        index = self._kind_combo.findData(kind)
        if index < 0:
            index = self._kind_combo.findData(AUDIT_QUESTION_KIND_UNCLASSIFIED)
        if index >= 0:
            self._kind_combo.setCurrentIndex(index)

    def _current_question_kind(self) -> str:
        value = self._kind_combo.currentData()
        return interpret_question_kind(value)

    def _set_verification_type(self, verification_type: str) -> None:
        radio = self._verification_radios.get(verification_type)
        if radio is not None:
            radio.setChecked(True)
        elif self._verification_radios:
            next(iter(self._verification_radios.values())).setChecked(True)

    def _current_verification_type(self) -> str:
        checked = self._verification_group.checkedButton()
        value = checked.property("verification_type") if checked is not None else None
        return audit_knowledge_service.normalize_verification_type(value)

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
        kind = self._current_question_kind()
        if kind not in (AUDIT_QUESTION_KIND_SYSTEM, AUDIT_QUESTION_KIND_OPERATION):
            QMessageBox.warning(self, self.windowTitle(), KNOWLEDGE_EDITOR_QUESTION_KIND_REQUIRED)
            self._kind_combo.setFocus()
            return
        self.accept()

    def assertion_payload(self) -> dict:
        return {
            "id": self._editing_id or self._id_edit.text().strip(),
            "text": self._text_edit.toPlainText().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "question_kind": self._current_question_kind(),
            "zavaznost": self._severity_combo.currentData(),
            "verification_type": self._current_verification_type(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }

    @property
    def editing_assertion_id(self) -> str:
        return self._editing_id
