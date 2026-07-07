from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.constants import legal_requirement_process_label


def _process_combo_label(requirement) -> str:
    code = (requirement.process_code or "").strip()
    label = legal_requirement_process_label(requirement)
    if code and label:
        return f"{code} – {label}"
    if code:
        return code
    if label:
        return f"{label} (#{requirement.id})"
    return f"Proces #{requirement.id}"


class LegalRequirementMergeDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        processes: list | None = None,
        preselected_source_id: int | None = None,
    ):
        super().__init__(parent)
        self._processes = list(processes or [])
        self._source_requirement_id: int | None = None
        self._target_requirement_id: int | None = None

        self.setWindowTitle("Sloučit procesy")
        configure_resizable_form_dialog(self, width=620, height=260, min_width=500, min_height=220)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Zdrojový proces bude sloučen do cílového procesu. "
                "Právní podklady a související záznamy se přesunou, "
                "zdrojový proces se archivuje.",
            ),
        )

        form = QFormLayout()
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()
        self._populate_combo(self.source_combo)
        self._populate_combo(self.target_combo)

        if preselected_source_id is not None:
            index = self.source_combo.findData(preselected_source_id)
            if index >= 0:
                self.source_combo.setCurrentIndex(index)

        form.addRow("Zdrojový proces:", self.source_combo)
        form.addRow("Cílový proces:", self.target_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def source_requirement_id(self) -> int | None:
        return self._source_requirement_id

    def target_requirement_id(self) -> int | None:
        return self._target_requirement_id

    def _populate_combo(self, combo: QComboBox) -> None:
        combo.clear()
        for requirement in self._processes:
            combo.addItem(_process_combo_label(requirement), requirement.id)

    def _accept(self) -> None:
        source_id = self.source_combo.currentData()
        target_id = self.target_combo.currentData()
        if source_id is None or target_id is None:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Sloučit procesy", "Vyberte zdrojový i cílový proces.")
            return
        if source_id == target_id:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                "Sloučit procesy",
                "Zdrojový a cílový proces musí být různé.",
            )
            return

        source_label = self.source_combo.currentText()
        target_label = self.target_combo.currentText()
        from PySide6.QtWidgets import QMessageBox

        answer = QMessageBox.question(
            self,
            "Potvrzení sloučení",
            f"Opravdu sloučit proces:\n{source_label}\n\ndo procesu:\n{target_label}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self._source_requirement_id = source_id
        self._target_requirement_id = target_id
        self.accept()
