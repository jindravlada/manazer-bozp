"""Dialog pro položku seznamu s popisem (postup kontroly)."""

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
from core.widgets.editor_dialog_controller import EditorDialogController
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeDescribedListItemDialog(QDialog):
    """Formulář kroku postupu kontroly — ID je při editaci read-only."""

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
            "Upravit krok postupu" if self._editing_id else "Nový krok postupu"
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
            self._id_edit.setPlaceholderText("Vygeneruje se z názvu kroku")

        self._nazev_edit = QLineEdit()
        self._nazev_edit.textChanged.connect(self._update_generated_id_preview)

        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(90)

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)

        self._aktivni_check = QCheckBox("Krok je aktivní")

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Název kroku:", self._nazev_edit)
        form.addRow("Popis kroku:", self._popis_edit)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        is_new = not bool(self._editing_id)
        buttons = create_save_cancel_box(self, is_new=is_new)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=is_new,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self.item_payload)
        self._editor.install_auto_dirty_tracking()

        if item:
            self._nazev_edit.setText(str(item.get("nazev") or item.get("text") or ""))
            self._popis_edit.setPlainText(str(item.get("popis") or ""))
            self._poradi_spin.setValue(int(item.get("poradi") or 0))
            self._aktivni_check.setChecked(bool(item.get("aktivni", True)))
        else:
            self._poradi_spin.setValue(10)
            self._aktivni_check.setChecked(True)
            self._update_generated_id_preview()

        self._editor.capture_baseline()

    def _update_generated_id_preview(self) -> None:
        if self._editing_id:
            return
        nazev = self._nazev_edit.text().strip()
        if not nazev:
            self._id_edit.clear()
            self._id_edit.setPlaceholderText("Vygeneruje se z názvu kroku")
            return
        generated = audit_knowledge_service.generate_item_id(nazev, self._existing_ids)
        self._id_edit.setText(generated)

    def accept(self) -> None:
        if not self.item_payload()["nazev"]:
            self._nazev_edit.setFocus()
            return
        super().accept()

    def item_payload(self) -> dict:
        return {
            "id": self._editing_id or self._id_edit.text().strip(),
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }

    @property
    def editing_item_id(self) -> str:
        return self._editing_id
