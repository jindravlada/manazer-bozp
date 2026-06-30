from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_LEVEL_LABELS,
    ISHIKAWA_LEVELS,
    ISHIKAWA_OTHER_FACTOR,
    ISHIKAWA_TRIGGER_NONE_LABEL,
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_LABELS,
    ISHIKAWA_STATUSES,
    ishikawa_question_for_category,
)
from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service
from moduly.vysetrovani_mu.ui.mu_ishikawa_factor_edit_dialog import MuIshikawaFactorEditDialog


class MuIshikawaCauseDialog(QDialog):
    def __init__(
        self,
        parent=None,
        cause: dict | None = None,
        *,
        title: str = "Příčina",
        other_causes: list[dict] | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self._other_causes = list(other_causes or [])

        self._factor_radios: list[QRadioButton] = []
        self._factor_button_group = QButtonGroup(self)
        self._factor_button_group.setExclusive(True)
        self._pending_custom_factor = ""

        root_layout = QVBoxLayout(self)
        columns_layout = QHBoxLayout()

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        left_panel = QWidget()
        left_form = QFormLayout(left_panel)
        left_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.category_combo = QComboBox()
        for category in ISHIKAWA_CATEGORIES:
            self.category_combo.addItem(category, category)

        self.question_label = QLabel("—")
        self.question_label.setWordWrap(True)
        self.question_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        factors_group = QGroupBox("Typický faktor")
        factors_group_layout = QVBoxLayout(factors_group)
        self.factors_container = QWidget()
        self.factors_layout = QVBoxLayout(self.factors_container)
        self.factors_layout.setContentsMargins(0, 0, 0, 0)
        factors_group_layout.addWidget(self.factors_container)

        self._custom_factor_label = QLabel("Vlastní faktor:")
        factors_group_layout.addWidget(self._custom_factor_label)

        self.custom_factor_edit = QLineEdit()
        self.custom_factor_edit.setPlaceholderText("Doplňte faktor mimo číselník")

        self.add_to_catalog_btn = QPushButton("Přidat do číselníku")
        self.add_to_catalog_btn.clicked.connect(self._add_custom_factor_to_catalog)

        custom_factor_row = QHBoxLayout()
        custom_factor_row.addWidget(self.custom_factor_edit, stretch=1)
        custom_factor_row.addWidget(self.add_to_catalog_btn)
        self._custom_factor_row_widget = QWidget()
        self._custom_factor_row_widget.setLayout(custom_factor_row)
        factors_group_layout.addWidget(self._custom_factor_row_widget)

        manage_row = QHBoxLayout()
        manage_row.addStretch()
        self.manage_factor_btn = QPushButton("Správa faktoru")
        self.manage_factor_btn.clicked.connect(self._open_factor_management)
        manage_row.addWidget(self.manage_factor_btn)
        factors_group_layout.addLayout(manage_row)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Popis možné příčiny")
        self.description_edit.setMinimumHeight(120)

        self.evidence_edit = QTextEdit()
        self.evidence_edit.setPlaceholderText("Důkazy / opora ve zjištěních")
        self.evidence_edit.setMinimumHeight(100)

        self.status_combo = QComboBox()
        for status in ISHIKAWA_STATUSES:
            self.status_combo.addItem(ISHIKAWA_STATUS_LABELS[status], status)

        self.level_combo = QComboBox()
        for level in ISHIKAWA_LEVELS:
            self.level_combo.addItem(ISHIKAWA_LEVEL_LABELS[level], level)

        self.triggered_by_combo = QComboBox()
        self._populate_triggered_by_combo()

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Poznámka")
        self.note_edit.setMinimumHeight(80)

        left_form.addRow("Kategorie:", self.category_combo)
        left_form.addRow("Otázka při šetření:", self.question_label)
        left_form.addRow("", factors_group)
        left_form.addRow("Popis možné příčiny:", self.description_edit)
        left_form.addRow("Důkazy / opora:", self.evidence_edit)
        left_form.addRow("Stav:", self.status_combo)
        left_form.addRow("Úroveň:", self.level_combo)
        left_form.addRow("Vyvoláno příčinou:", self.triggered_by_combo)
        left_form.addRow("Poznámka:", self.note_edit)

        left_scroll.setWidget(left_panel)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        methodology_title = QLabel("Metodická podpora")
        methodology_title.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(methodology_title)

        self.factor_questions_group = self._create_readonly_group(
            "Otázky k vybranému faktoru",
            right_layout,
        )
        self.factor_questions_label = self.factor_questions_group.findChild(QLabel)

        self.factor_evidence_group = self._create_readonly_group(
            "Typické důkazy",
            right_layout,
        )
        self.factor_evidence_label = self.factor_evidence_group.findChild(QLabel)

        self.factor_related_group = self._create_readonly_group(
            "Možné navazující faktory",
            right_layout,
            monospace=True,
        )
        self.factor_related_label = self.factor_related_group.findChild(QLabel)

        self.factor_supports_group = self._create_readonly_group(
            "Co tuto hypotézu podporuje",
            right_layout,
        )
        self.factor_supports_label = self.factor_supports_group.findChild(QLabel)

        self.factor_contradicts_group = self._create_readonly_group(
            "Co tuto hypotézu oslabuje",
            right_layout,
        )
        self.factor_contradicts_label = self.factor_contradicts_group.findChild(QLabel)

        self.factor_actions_group = self._create_readonly_group(
            "Doporučené vyšetřovací kroky",
            right_layout,
        )
        self.factor_actions_label = self.factor_actions_group.findChild(QLabel)

        self.factor_suggest_group = self._create_readonly_group(
            "Doporučené další směry šetření",
            right_layout,
        )
        self.factor_suggest_label = self.factor_suggest_group.findChild(QLabel)

        self._methodology_hint = QLabel("Vyberte typický faktor pro zobrazení metodické podpory.")
        self._methodology_empty_hint = QLabel("Pro tento faktor zatím není metodická karta.")
        self._methodology_empty_hint.setWordWrap(True)
        self._methodology_empty_hint.setStyleSheet("color: palette(mid);")
        self._methodology_empty_hint.setVisible(False)
        self._methodology_hint.setWordWrap(True)
        self._methodology_hint.setStyleSheet("color: palette(mid);")
        right_layout.addWidget(self._methodology_hint)
        right_layout.addWidget(self._methodology_empty_hint)
        right_layout.addStretch()

        right_scroll.setWidget(right_panel)

        columns_layout.addWidget(left_scroll, stretch=1)
        columns_layout.addWidget(right_scroll, stretch=1)
        root_layout.addLayout(columns_layout, stretch=1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root_layout.addWidget(buttons)

        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        self._factor_button_group.buttonClicked.connect(self._on_factor_selected)
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
            self._set_combo_data(
                self.triggered_by_combo,
                str(cause.get("triggered_by_cause_id") or "").strip(),
            )
            self.note_edit.setPlainText(cause.get("note") or "")

        self._update_question_label()
        self._rebuild_factor_radios(saved_factor)
        self.category_combo.blockSignals(False)
        self._update_custom_factor_visibility()
        self._update_factor_details()

        self.showMaximized()

    @staticmethod
    def _create_readonly_group(title: str, parent_layout: QVBoxLayout, *, monospace: bool = False) -> QGroupBox:
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        label = QLabel("")
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        if monospace:
            font = label.font()
            font.setFamily("Monospace")
            font.setStyleHint(font.StyleHint.Monospace)
            label.setFont(font)
        group_layout.addWidget(label)
        group.setVisible(False)
        parent_layout.addWidget(group)
        return group

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
            "triggered_by_cause_id": str(self.triggered_by_combo.currentData() or "").strip(),
            "note": self.note_edit.toPlainText().strip(),
        }

    def _populate_triggered_by_combo(self) -> None:
        self.triggered_by_combo.clear()
        self.triggered_by_combo.addItem(ISHIKAWA_TRIGGER_NONE_LABEL, "")
        for other_cause in self._other_causes:
            cause_id = str(other_cause.get("id") or "").strip()
            if not cause_id:
                continue
            self.triggered_by_combo.addItem(
                self._trigger_cause_label(other_cause),
                cause_id,
            )

    @staticmethod
    def _trigger_cause_label(cause: dict, description_max_len: int = 50) -> str:
        category = str(cause.get("category") or "").strip() or "—"
        factor = str(cause.get("factor") or "").strip()
        custom_factor = str(cause.get("custom_factor") or "").strip()
        if factor == ISHIKAWA_OTHER_FACTOR and custom_factor:
            factor_label = custom_factor
        elif factor:
            factor_label = factor
        else:
            factor_label = ""

        description = str(cause.get("description") or "").strip()
        if len(description) > description_max_len:
            description = description[: description_max_len - 1].rstrip() + "…"

        parts = [category]
        if factor_label:
            parts.append(factor_label)
        if description:
            parts.append(description)
        return " – ".join(parts)

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
        factor_name = button.property("factor_name")
        if factor_name:
            return str(factor_name)
        return button.text()

    def _current_category(self) -> str:
        return self.category_combo.currentData() or ISHIKAWA_CATEGORIES[0]

    def _on_category_changed(self) -> None:
        self._update_question_label()
        self._rebuild_factor_radios()

    def _on_factor_selected(self, button) -> None:
        factor_name = button.property("factor_name") or button.text()
        self._rebuild_factor_radios(saved_factor=str(factor_name))

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
        available_factors = set(ishikawa_factors_service.get_factors(category))
        expanded_parents = (
            ishikawa_factors_service.get_expanded_parents(category, selected)
            if selected
            else frozenset()
        )
        display_factors = ishikawa_factors_service.get_factors_display(
            category,
            expanded_parents=expanded_parents,
        )

        if selected and selected not in available_factors and selected != ISHIKAWA_OTHER_FACTOR:
            if not self.custom_factor_edit.text().strip():
                self.custom_factor_edit.setText(selected)
            selected = ISHIKAWA_OTHER_FACTOR

        for factor_name, level in display_factors:
            radio = QRadioButton(factor_name)
            if level:
                radio.setStyleSheet(f"margin-left: {24 * level}px;")
            radio.setProperty("factor_name", factor_name)
            self._factor_button_group.addButton(radio)
            self.factors_layout.addWidget(radio)
            self._factor_radios.append(radio)

        if selected:
            for radio in self._factor_radios:
                if radio.property("factor_name") == selected:
                    radio.setChecked(True)
                    break

        if selected == ISHIKAWA_OTHER_FACTOR and self._pending_custom_factor:
            self.custom_factor_edit.setText(self._pending_custom_factor)
            self._pending_custom_factor = ""

        self._update_custom_factor_visibility()
        self._update_factor_details()

    def _update_manage_factor_state(self) -> None:
        factor = self._selected_factor()
        self.manage_factor_btn.setEnabled(bool(factor) and factor != ISHIKAWA_OTHER_FACTOR)

    def _open_factor_management(self) -> None:
        factor_name = self._selected_factor()
        if not factor_name or factor_name == ISHIKAWA_OTHER_FACTOR:
            return

        category = self._current_category()
        factor = ishikawa_factors_service.get_factor(category, factor_name)
        if factor is None:
            QMessageBox.information(self, "Ishikawa+", "Vybraný faktor nebyl nalezen v číselníku.")
            return

        dialog = MuIshikawaFactorEditDialog(self, category=category, factor=factor)
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not ishikawa_factors_service.update_factor(
            category,
            factor_name,
            data["name"],
            data["questions"],
            data["evidence"],
            data["related"],
            data["parent"],
            data["supports"],
            data["contradicts"],
            data["actions"],
            data["suggest"],
        ):
            QMessageBox.warning(
                self,
                "Ishikawa+",
                "Faktor se nepodařilo uložit. Zkontrolujte název a duplicity.",
            )
            return

        ishikawa_factors_service.reload()
        self._rebuild_factor_radios(saved_factor=data["name"])

    def _update_methodology_hint_visibility(self) -> None:
        groups = (
            self.factor_questions_group,
            self.factor_evidence_group,
            self.factor_related_group,
            self.factor_supports_group,
            self.factor_contradicts_group,
            self.factor_actions_group,
            self.factor_suggest_group,
        )
        has_content = any(group.isVisible() for group in groups)
        factor = self._selected_factor()
        self._methodology_hint.setVisible(not factor or factor == ISHIKAWA_OTHER_FACTOR)
        self._methodology_empty_hint.setVisible(
            bool(factor) and factor != ISHIKAWA_OTHER_FACTOR and not has_content
        )

    def _update_factor_details(self) -> None:
        factor = self._selected_factor()
        if not factor or factor == ISHIKAWA_OTHER_FACTOR:
            self.factor_questions_group.setVisible(False)
            self.factor_evidence_group.setVisible(False)
            self.factor_related_group.setVisible(False)
            self.factor_supports_group.setVisible(False)
            self.factor_contradicts_group.setVisible(False)
            self.factor_actions_group.setVisible(False)
            self.factor_suggest_group.setVisible(False)
            self._update_methodology_hint_visibility()
            self._update_manage_factor_state()
            return

        category = self._current_category()
        questions = ishikawa_factors_service.get_factor_questions(category, factor)
        if questions:
            self.factor_questions_label.setText("\n".join(f"• {question}" for question in questions))
            self.factor_questions_group.setVisible(True)
        else:
            self.factor_questions_group.setVisible(False)

        evidence = ishikawa_factors_service.get_factor_evidence(category, factor)
        if evidence:
            self.factor_evidence_label.setText("\n".join(f"• {item}" for item in evidence))
            self.factor_evidence_group.setVisible(True)
        else:
            self.factor_evidence_group.setVisible(False)

        related = ishikawa_factors_service.get_factor_related(category, factor)
        if related:
            self.factor_related_label.setText(self._format_related_tree(factor, related))
            self.factor_related_group.setVisible(True)
        else:
            self.factor_related_group.setVisible(False)

        supports = ishikawa_factors_service.get_factor_supports(category, factor)
        if supports:
            self.factor_supports_label.setText("\n".join(f"• {item}" for item in supports))
            self.factor_supports_group.setVisible(True)
        else:
            self.factor_supports_group.setVisible(False)

        contradicts = ishikawa_factors_service.get_factor_contradicts(category, factor)
        if contradicts:
            self.factor_contradicts_label.setText("\n".join(f"• {item}" for item in contradicts))
            self.factor_contradicts_group.setVisible(True)
        else:
            self.factor_contradicts_group.setVisible(False)

        actions = ishikawa_factors_service.get_factor_actions(category, factor)
        if actions:
            self.factor_actions_label.setText("\n".join(f"• {item}" for item in actions))
            self.factor_actions_group.setVisible(True)
        else:
            self.factor_actions_group.setVisible(False)

        suggest = ishikawa_factors_service.get_factor_suggest(category, factor)
        if suggest:
            self.factor_suggest_label.setText(
                "\n".join(
                    ishikawa_factors_service.format_suggest_line(
                        entry["category"],
                        entry["factor"],
                    )
                    for entry in suggest
                )
            )
            self.factor_suggest_group.setVisible(True)
        else:
            self.factor_suggest_group.setVisible(False)

        self._update_methodology_hint_visibility()
        self._update_manage_factor_state()

    @staticmethod
    def _format_related_tree(factor: str, related: tuple[str, ...]) -> str:
        lines = [factor]
        last_index = len(related) - 1
        for index, name in enumerate(related):
            branch = "└─" if index == last_index else "├─"
            lines.append(f"  {branch} {name}")
        return "\n".join(lines)

    def _update_custom_factor_visibility(self) -> None:
        is_other = self._selected_factor() == ISHIKAWA_OTHER_FACTOR
        self._custom_factor_row_widget.setVisible(is_other)
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
