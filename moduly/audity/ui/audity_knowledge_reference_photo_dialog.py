"""Dialog pro referenční fotografii oblasti ověření."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AudityKnowledgeReferencePhotoDialog(QDialog):
    """Formulář referenční fotografie — ID je při editaci read-only."""

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
        self._control_point_id = item.get("control_point_id") if item else None

        self.setWindowTitle(
            "Upravit referenční fotografii"
            if self._editing_id
            else "Nová referenční fotografie"
        )
        self.resize(680, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setReadOnly(True)
        if self._editing_id:
            self._id_edit.setText(self._editing_id)
        else:
            self._id_edit.setPlaceholderText("Vygeneruje se z názvu")

        self._nazev_edit = QLineEdit()
        self._nazev_edit.textChanged.connect(self._update_generated_id_preview)

        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(70)

        self._soubor_edit = QLineEdit()
        browse_btn = QPushButton("Vybrat…")
        browse_btn.clicked.connect(self._browse_file)
        soubor_row = QHBoxLayout()
        soubor_row.addWidget(self._soubor_edit, stretch=1)
        soubor_row.addWidget(browse_btn)

        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)

        self._aktivni_check = QCheckBox("Fotografie je aktivní")

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Název:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow("Soubor:", soubor_row)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if item:
            self._nazev_edit.setText(str(item.get("nazev") or ""))
            self._popis_edit.setPlainText(str(item.get("popis") or ""))
            self._soubor_edit.setText(str(item.get("soubor") or ""))
            self._poradi_spin.setValue(int(item.get("poradi") or 0))
            self._aktivni_check.setChecked(bool(item.get("aktivni", True)))
        else:
            self._poradi_spin.setValue(10)
            self._aktivni_check.setChecked(True)
            self._update_generated_id_preview()

    def _browse_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte referenční fotografii",
            "",
            "Obrázky (*.png *.jpg *.jpeg *.webp *.gif);;Všechny soubory (*)",
        )
        if path:
            self._soubor_edit.setText(path)

    def _update_generated_id_preview(self) -> None:
        if self._editing_id:
            return
        nazev = self._nazev_edit.text().strip()
        if not nazev:
            self._id_edit.clear()
            self._id_edit.setPlaceholderText("Vygeneruje se z názvu")
            return
        generated = audit_knowledge_service.generate_item_id(nazev, self._existing_ids)
        self._id_edit.setText(generated)

    def _accept_if_valid(self) -> None:
        payload = self.item_payload()
        if not payload["nazev"]:
            self._nazev_edit.setFocus()
            return
        if payload["aktivni"] and not payload["soubor"]:
            self._soubor_edit.setFocus()
            return
        self.accept()

    def item_payload(self) -> dict:
        payload = {
            "id": self._editing_id or self._id_edit.text().strip(),
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "soubor": self._soubor_edit.text().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }
        if self._control_point_id is not None and str(self._control_point_id).strip():
            payload["control_point_id"] = str(self._control_point_id).strip()
        return payload

    @property
    def editing_item_id(self) -> str:
        return self._editing_id
