from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_LEVEL_LABELS,
    ISHIKAWA_LEVELS,
    ISHIKAWA_OTHER_FACTOR,
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_LABELS,
    ISHIKAWA_STATUSES,
    ishikawa_factors_for_category,
    ishikawa_question_for_category,
)
from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service


class MuIshikawaCauseDialog(QDialog):
    def __init__(self, parent=None, cause: dict | None = None, *, title: str = "Příčina"):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.resize(680, 720)

        self._factor_radios: list[QRadioButton] = []
        self._factor_button_group = QButtonGroup(self)
        self._factor_button_group.setExclusive(True)
        self._pending_custom_factor = ""

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.category_combo = QComboBox()
        for category in ISHIKAWA_CATEGORIES:
            self.category_combo.addItem(category, category)

        self.question_label = QLabel("—")
        self.question_label.setWordWrap(True)
        self.question_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        factors_group = QGroupBox("Typický faktor")
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
        self.custom_factor_edit.setPlaceholderText("Doplňte faktor mimo číselník")

        self.add_to_catalog_btn = QPushButton("Přidat do číselníku")
        self.add_to_catalog_btn.clicked.connect(self._add_custom_factor_to_catalog)

        custom_factor_row = QHBoxLayout()
        custom_factor_row.addWidget(self.custom_factor_edit, stretch=1)
        custom_factor_row.addWidget(self.add_to_catalog_btn)
        self._custom_factor_row_widget = QWidget()
        self._custom_factor_row_widget.setLayout(custom_factor_row)

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
        form.addRow("Otázka při šetření:", self.question_label)
        form.addRow("", factors_group)
        self._custom_factor_label = QLabel("Vlastní faktor:")
        form.addRow(self._custom_factor_label, self._custom_factor_row_widget)
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
        self._factor_button_group.buttonClicked.connect(self._update_custom_factor_visibility)
        self.custom_factor_edit.textChanged.connect(self._update_add_to_catalog_state)

        saved_factor = ""
        self.category_combo.blockSignals(True)
        if cause is not None:
            self._set_combo_text(self.category_combo, cause.get("category") or ISHIKAWA_CATEGORIES[0])
            saved_factor = self._factor_from_cause(cause)
            self._pending_custom_factor = (cause.get("custom_factor") or "").strip()
            if saved_factor == ISHIKAWA_OTHER_FACTOR:
                self.custom_factor_edit.setText(self._pending_custom_factor)
            self.description_edit.setPlainText(cause.get("description") or "")
            self.evidence_edit.setPlainText(cause.get("evidence") or "")
            self._set_combo_data(self.status_combo, cause.get("status") or ISHIKAWA_STATUS_HYPOTEZA)
            default_level = ISHIKAWA_LEVELS[0]
            self._set_combo_data(self.level_combo, cause.get("cause_level") or default_level)
            self.note_edit.setPlainText(cause.get("note") or "")

        self._update_question_label()
        self._rebuild_factor_radios(saved_factor)
        self.category_combo.blockSignals(False)
        self._update_custom_factor_visibility()

    def get_data(self) -> dict:
        factor = self._selected_factor()
        custom_factor = self.custom_factor_edit.text().strip()
        if factor != ISHIKAWA_OTHER_FACTOR:
            custom_factor = ""

        return {
            "category": self.category_combo.currentData(),
            "factor": factor,
            "custom_factor": custom_factor,
            "description": self.description_edit.toPlainText().strip(),
            "evidence": self.evidence_edit.toPlainText().strip(),
            "status": self.status_combo.currentData(),
            "cause_level": self.level_combo.currentData(),
            "note": self.note_edit.toPlainText().strip(),
        }

    def _factor_from_cause(self, cause: dict) -> str:
        factor = str(cause.get("factor") or "").strip()
        if factor:
            return factor

        old_factors = cause.get("factors") or []
        if old_factors:
            return str(old_factors[0]).strip()
        return ""

    def _selected_factor(self) -> str:
        button = self._factor_button_group.checkedButton()
        if button is None:
            return ""
        return button.text()

    def _current_category(self) -> str:
        return self.category_combo.currentData() or ISHIKAWA_CATEGORIES[0]

    def _on_category_changed(self) -> None:
        self._update_question_label()
        self._rebuild_factor_radios()

    def _update_question_label(self) -> None:
        self.question_label.setText(ishikawa_question_for_category(self._current_category()))

    def _rebuild_factor_radios(self, saved_factor: str | None = None) -> None:
        selected = saved_factor if saved_factor is not None else self._selected_factor()

        while self.factors_layout.count():
            item = self.factors_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                self._factor_button_group.removeButton(widget)
                widget.deleteLater()

        self._factor_radios = []
        category = self._current_category()
        available_factors = ishikawa_factors_for_category(category)

        if selected and selected not in available_factors and selected != ISHIKAWA_OTHER_FACTOR:
            if not self.custom_factor_edit.text().strip():
                self.custom_factor_edit.setText(selected)
            selected = ISHIKAWA_OTHER_FACTOR

        for factor in available_factors:
            radio = QRadioButton(factor)
            self._factor_button_group.addButton(radio)
            self.factors_layout.addWidget(radio)
            self._factor_radios.append(radio)

        if selected:
            for radio in self._factor_radios:
                if radio.text() == selected:
                    radio.setChecked(True)
                    break

        if selected == ISHIKAWA_OTHER_FACTOR and self._pending_custom_factor:
            self.custom_factor_edit.setText(self._pending_custom_factor)
            self._pending_custom_factor = ""

        self.factors_layout.addStretch()
        self._update_custom_factor_visibility()

    def _update_custom_factor_visibility(self) -> None:
        is_other = self._selected_factor() == ISHIKAWA_OTHER_FACTOR
        self._custom_factor_row_widget.setVisible(is_other)
        if hasattr(self, "_custom_factor_label"):
            self._custom_factor_label.setVisible(is_other)
        if not is_other:
            self.custom_factor_edit.clear()
        self._update_add_to_catalog_state()

    def _update_add_to_catalog_state(self) -> None:
        is_other = self._selected_factor() == ISHIKAWA_OTHER_FACTOR
        has_text = bool(self.custom_factor_edit.text().strip())
        self.add_to_catalog_btn.setEnabled(is_other and has_text)

    def _add_custom_factor_to_catalog(self) -> None:
        custom_factor = self.custom_factor_edit.text().strip()
        if not custom_factor or self._selected_factor() != ISHIKAWA_OTHER_FACTOR:
            return

        category = self._current_category()
        if not ishikawa_factors_service.add_factor(category, custom_factor):
            return

        self.custom_factor_edit.clear()
        self._rebuild_factor_radios(saved_factor=custom_factor)

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
