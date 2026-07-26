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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.proverky.constants import (
    CONTROL_POINT_SEVERITY_OPTIONS,
    VERIFICATION_TYPE_OPTIONS,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service


class ProverkyKnowledgeListItemDialog(QDialog):
    """Dialog pro přidání nebo úpravu položky znalostní karty."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        item: dict | None = None,
        existing_ids: set[str] | None = None,
        include_zavaznost: bool = False,
        include_verification_type: bool = False,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(560, 420 if include_verification_type else 360)

        self._original_id = str((item or {}).get("id") or "").strip()
        self._existing_ids = set(existing_ids or set())
        if self._original_id:
            self._existing_ids.discard(self._original_id)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(10)

        self._id_edit = QLineEdit()
        self._id_edit.setText(self._original_id)
        self._id_edit.setPlaceholderText("Automaticky z názvu, pokud necháte prázdné")

        self._nazev_edit = QLineEdit()
        self._nazev_edit.setText(str((item or {}).get("nazev") or ""))

        self._popis_edit = QTextEdit()
        self._popis_edit.setPlainText(str((item or {}).get("popis") or ""))
        self._popis_edit.setMinimumHeight(120)

        self._aktivni_check = QCheckBox("Aktivní")
        self._aktivni_check.setChecked(bool((item or {}).get("aktivni", True)))

        self._zavaznost_combo: QComboBox | None = None
        if include_zavaznost:
            self._zavaznost_combo = QComboBox()
            for value, label in CONTROL_POINT_SEVERITY_OPTIONS:
                self._zavaznost_combo.addItem(label, value)
            current = proverky_knowledge_service.normalize_control_point_severity(
                (item or {}).get("zavaznost")
            )
            index = self._zavaznost_combo.findData(current)
            if index >= 0:
                self._zavaznost_combo.setCurrentIndex(index)

        self._verification_group: QButtonGroup | None = None
        verification_host: QWidget | None = None
        if include_verification_type:
            verification_host = QWidget()
            verification_layout = QHBoxLayout(verification_host)
            verification_layout.setContentsMargins(0, 0, 0, 0)
            self._verification_group = QButtonGroup(self)
            current_type = proverky_knowledge_service.normalize_verification_type(
                (item or {}).get("verification_type")
            )
            for value, label in VERIFICATION_TYPE_OPTIONS:
                radio = QRadioButton(label)
                radio.setProperty("verification_type", value)
                self._verification_group.addButton(radio)
                verification_layout.addWidget(radio)
                if value == current_type:
                    radio.setChecked(True)
            if self._verification_group.checkedButton() is None:
                self._verification_group.buttons()[0].setChecked(True)
            verification_layout.addStretch()

        form.addRow("Identifikátor:", self._id_edit)
        form.addRow("Název:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        if self._zavaznost_combo is not None:
            form.addRow("Závažnost:", self._zavaznost_combo)
        if verification_host is not None:
            form.addRow("Typ ověření:", verification_host)
        form.addRow("", self._aktivni_check)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict | None:
        nazev = self._nazev_edit.text().strip()
        if not nazev:
            return None

        item_id = self._id_edit.text().strip() or self._original_id

        data = {
            "id": item_id,
            "nazev": nazev,
            "popis": self._popis_edit.toPlainText().strip(),
            "aktivni": self._aktivni_check.isChecked(),
        }
        if self._zavaznost_combo is not None:
            data["zavaznost"] = proverky_knowledge_service.normalize_control_point_severity(
                self._zavaznost_combo.currentData()
            )
        if self._verification_group is not None:
            checked = self._verification_group.checkedButton()
            value = checked.property("verification_type") if checked is not None else None
            data["verification_type"] = proverky_knowledge_service.normalize_verification_type(
                value
            )
        return data

    def _accept(self) -> None:
        data = self.get_data()
        if data is None:
            QMessageBox.warning(self, self.windowTitle(), "Název položky je povinný.")
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
