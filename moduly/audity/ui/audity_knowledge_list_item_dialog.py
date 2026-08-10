"""Obecný dialog pro položku metodického seznamu oblasti ověření."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeListItemDialog(QDialog):
    """Formulář položky seznamu — ID je při editaci read-only."""

    def __init__(
        self,
        *,
        existing_ids: set[str] | None = None,
        item: dict | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self._existing_ids = set(existing_ids or [])
        self._editing_id = str(item.get("id") or "").strip() if item else ""

        self.setWindowTitle(
            "Upravit položku" if self._editing_id else "Nová položka"
        )
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setReadOnly(True)
        if self._editing_id:
            self._id_edit.setText(self._editing_id)
        else:
            self._id_edit.setPlaceholderText("Vygeneruje se z textu položky")

        self._text_edit = QLineEdit()
        self._text_edit.textChanged.connect(self._update_generated_id_preview)

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)

        self._aktivni_check = QCheckBox("Položka je aktivní")

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Text:", self._text_edit)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if item:
            self._text_edit.setText(str(item.get("nazev") or item.get("text") or ""))
            self._poradi_spin.setValue(int(item.get("poradi") or 0))
            self._aktivni_check.setChecked(bool(item.get("aktivni", True)))
        else:
            self._poradi_spin.setValue(10)
            self._aktivni_check.setChecked(True)
            self._update_generated_id_preview()

    def _update_generated_id_preview(self) -> None:
        if self._editing_id:
            return
        text = self._text_edit.text().strip()
        if not text:
            self._id_edit.clear()
            self._id_edit.setPlaceholderText("Vygeneruje se z textu položky")
            return
        generated = audit_knowledge_service.generate_item_id(text, self._existing_ids)
        self._id_edit.setText(generated)

    def _accept_if_valid(self) -> None:
        if not self.item_payload()["nazev"]:
            self._text_edit.setFocus()
            return
        self.accept()

    def item_payload(self) -> dict:
        return {
            "id": self._editing_id or self._id_edit.text().strip(),
            "nazev": self._text_edit.text().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }

    @property
    def editing_item_id(self) -> str:
        return self._editing_id
