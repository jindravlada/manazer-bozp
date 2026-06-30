from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_LEVEL_LABELS,
    ISHIKAWA_LEVELS,
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_LABELS,
    ISHIKAWA_STATUSES,
    ishikawa_factors_for_category,
)


class MuIshikawaCauseDialog(QDialog):
    def __init__(self, parent=None, cause: dict | None = None, *, title: str = "Příčina"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(640, 680)

        self._factor_checkboxes: list[QCheckBox] = []

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.category_combo = QComboBox()
        for category in ISHIKAWA_CATEGORIES:
            self.category_combo.addItem(category, category)

        factors_group = QGroupBox("Typické faktory")
        factors_group_layout = QVBoxLayout(factors_group)
        self.factors_scroll = QScrollArea()
        self.factors_scroll.setWidgetResizable(True)
        self.factors_scroll.setMaximumHeight(220)
        self.factors_container = QWidget()
        self.factors_layout = QVBoxLayout(self.factors_container)
        self.factors_layout.setContentsMargins(0, 0, 0, 0)
        self.factors_scroll.setWidget(self.factors_container)
        factors_group_layout.addWidget(self.factors_scroll)

        self.custom_factor_edit = QLineEdit()
        self.custom_factor_edit.setPlaceholderText("Doplňte faktor mimo checklist")

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
        form.addRow("", factors_group)
        form.addRow("Vlastní faktor:", self.custom_factor_edit)
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

        self.category_combo.currentIndexChanged.connect(self._on_category_changed)

        saved_factors: list[str] = []
        self.category_combo.blockSignals(True)
        if cause is not None:
            self._set_combo_text(self.category_combo, cause.get("category") or ISHIKAWA_CATEGORIES[0])
            saved_factors = list(cause.get("factors") or [])
            self.custom_factor_edit.setText(cause.get("custom_factor") or "")
            self.description_edit.setPlainText(cause.get("description") or "")
            self.evidence_edit.setPlainText(cause.get("evidence") or "")
            self._set_combo_data(self.status_combo, cause.get("status") or ISHIKAWA_STATUS_HYPOTEZA)
            default_level = ISHIKAWA_LEVELS[0]
            self._set_combo_data(self.level_combo, cause.get("cause_level") or default_level)
            self.note_edit.setPlainText(cause.get("note") or "")

        self._rebuild_factor_checkboxes(saved_factors)
        self.category_combo.blockSignals(False)

    def get_data(self) -> dict:
        return {
            "category": self.category_combo.currentData(),
            "factors": [checkbox.text() for checkbox in self._factor_checkboxes if checkbox.isChecked()],
            "custom_factor": self.custom_factor_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "evidence": self.evidence_edit.toPlainText().strip(),
            "status": self.status_combo.currentData(),
            "cause_level": self.level_combo.currentData(),
            "note": self.note_edit.toPlainText().strip(),
        }

    def _on_category_changed(self) -> None:
        self._rebuild_factor_checkboxes()

    def _rebuild_factor_checkboxes(self, saved_factors: list[str] | None = None) -> None:
        selected = set(saved_factors or [])
        if saved_factors is None:
            selected = {checkbox.text() for checkbox in self._factor_checkboxes if checkbox.isChecked()}

        while self.factors_layout.count():
            item = self.factors_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._factor_checkboxes = []
        category = self.category_combo.currentData() or ISHIKAWA_CATEGORIES[0]
        for factor in ishikawa_factors_for_category(category):
            checkbox = QCheckBox(factor)
            if factor in selected:
                checkbox.setChecked(True)
            self.factors_layout.addWidget(checkbox)
            self._factor_checkboxes.append(checkbox)

        self.factors_layout.addStretch()

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
