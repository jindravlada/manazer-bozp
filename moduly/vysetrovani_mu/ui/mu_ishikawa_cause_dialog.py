from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QTextEdit,
    QVBoxLayout,
)

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_LEVEL_LABELS,
    ISHIKAWA_LEVELS,
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_LABELS,
    ISHIKAWA_STATUSES,
)


class MuIshikawaCauseDialog(QDialog):
    def __init__(self, parent=None, cause: dict | None = None, *, title: str = "Příčina"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.category_combo = QComboBox()
        for category in ISHIKAWA_CATEGORIES:
            self.category_combo.addItem(category, category)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Popis možné příčiny")
        self.description_edit.setMinimumHeight(100)

        self.evidence_edit = QTextEdit()
        self.evidence_edit.setPlaceholderText("Důkazy / opora ve zjištěních")
        self.evidence_edit.setMinimumHeight(80)

        self.status_combo = QComboBox()
        for status in ISHIKAWA_STATUSES:
            self.status_combo.addItem(ISHIKAWA_STATUS_LABELS[status], status)

        self.level_combo = QComboBox()
        for level in ISHIKAWA_LEVELS:
            self.level_combo.addItem(ISHIKAWA_LEVEL_LABELS[level], level)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Poznámka")
        self.note_edit.setMinimumHeight(70)

        form.addRow("Kategorie:", self.category_combo)
        form.addRow("Popis možné příčiny:", self.description_edit)
        form.addRow("Důkazy / opora:", self.evidence_edit)
        form.addRow("Stav:", self.status_combo)
        form.addRow("Úroveň:", self.level_combo)
        form.addRow("Poznámka:", self.note_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if cause is not None:
            self._set_combo_text(self.category_combo, cause.get("category") or ISHIKAWA_CATEGORIES[0])
            self.description_edit.setPlainText(cause.get("description") or "")
            self.evidence_edit.setPlainText(cause.get("evidence") or "")
            self._set_combo_data(self.status_combo, cause.get("status") or ISHIKAWA_STATUS_HYPOTEZA)
            default_level = ISHIKAWA_LEVELS[0]
            self._set_combo_data(self.level_combo, cause.get("cause_level") or default_level)
            self.note_edit.setPlainText(cause.get("note") or "")

    def get_data(self) -> dict:
        return {
            "category": self.category_combo.currentData(),
            "description": self.description_edit.toPlainText().strip(),
            "evidence": self.evidence_edit.toPlainText().strip(),
            "status": self.status_combo.currentData(),
            "cause_level": self.level_combo.currentData(),
            "note": self.note_edit.toPlainText().strip(),
        }

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _set_combo_text(self, combo: QComboBox, value: str) -> None:
        index = combo.findText(value)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setCurrentIndex(0)
