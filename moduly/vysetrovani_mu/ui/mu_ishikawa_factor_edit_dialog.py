from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from moduly.vysetrovani_mu.constants import ISHIKAWA_CATEGORIES, ISHIKAWA_OTHER_FACTOR
from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service
from core.widgets.dialog_utils import create_save_cancel_box

_LIST_MIN_HEIGHT = 160
_SECTION_SPACING = 24


class CollapsibleSection(QWidget):
    """Sbalitelná sekce s nadpisem a počtem položek."""

    def __init__(self, title: str, *, expanded: bool = True, parent=None):
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        self._count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._header = QPushButton()
        self._header.setFlat(True)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet(
            "QPushButton { text-align: left; font-weight: bold; padding: 4px 0; }"
        )
        self._header.clicked.connect(self._toggle)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(20, 0, 0, 0)
        self._content_layout.setSpacing(8)

        layout.addWidget(self._header)
        layout.addWidget(self._content)

        self._content.setVisible(expanded)
        self._refresh_header()

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def set_count(self, count: int) -> None:
        self._count = max(0, count)
        self._refresh_header()

    def _refresh_header(self) -> None:
        arrow = "▼" if self._expanded else "▶"
        self._header.setText(f"{arrow} {self._title} ({self._count})")

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._refresh_header()


class MuIshikawaFactorEditDialog(QDialog):
    def __init__(self, parent=None, *, category: str, factor: dict):
        super().__init__(parent)

        self._category = category
        self._original_name = (factor.get("name") or "").strip()
        self._sections_by_list: dict[QListWidget, CollapsibleSection] = {}

        self.setWindowTitle(f"Správa faktoru – {category}")
        self.resize(620, 680)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(4, 4, 4, 4)
        scroll_layout.setSpacing(_SECTION_SPACING)
        scroll.setWidget(scroll_content)

        header_form = QFormLayout()
        header_form.setSpacing(12)

        self.name_edit = QLineEdit()
        self.name_edit.setText(self._original_name)
        if self._original_name == ISHIKAWA_OTHER_FACTOR:
            self.name_edit.setReadOnly(True)

        self.parent_combo = QComboBox()
        self.parent_combo.addItem("— hlavní faktor —", "")
        for parent_name in ishikawa_factors_service.get_main_factors(
            self._category,
            exclude=self._original_name,
        ):
            self.parent_combo.addItem(parent_name, parent_name)
        current_parent = str(factor.get("parent") or "").strip()
        parent_index = self.parent_combo.findData(current_parent)
        if parent_index >= 0:
            self.parent_combo.setCurrentIndex(parent_index)
        if self._original_name == ISHIKAWA_OTHER_FACTOR:
            self.parent_combo.setEnabled(False)

        header_form.addRow("Název faktoru:", self.name_edit)
        header_form.addRow("Nadřazený faktor:", self.parent_combo)
        scroll_layout.addLayout(header_form)

        self.questions_list = self._create_list_section(
            scroll_layout,
            "Metodické otázky",
        )
        self.evidence_list = self._create_list_section(
            scroll_layout,
            "Typické důkazy",
        )
        self.related_list = self._create_related_section(scroll_layout)
        self.supports_list = self._create_list_section(
            scroll_layout,
            "Co tuto hypotézu podporuje",
        )
        self.contradicts_list = self._create_list_section(
            scroll_layout,
            "Co tuto hypotézu oslabuje",
        )
        self.actions_list = self._create_list_section(
            scroll_layout,
            "Doporučené vyšetřovací kroky",
        )
        self.suggest_list = self._create_suggest_section(scroll_layout)

        for question in factor.get("questions") or []:
            value = str(question).strip()
            if value:
                self.questions_list.addItem(value)

        for item in factor.get("evidence") or []:
            value = str(item).strip()
            if value:
                self.evidence_list.addItem(value)

        for item in factor.get("related") or []:
            value = str(item).strip()
            if value:
                self.related_list.addItem(value)

        for item in factor.get("supports") or []:
            value = str(item).strip()
            if value:
                self.supports_list.addItem(value)

        for item in factor.get("contradicts") or []:
            value = str(item).strip()
            if value:
                self.contradicts_list.addItem(value)

        for item in factor.get("actions") or []:
            value = str(item).strip()
            if value:
                self.actions_list.addItem(value)

        for entry in factor.get("suggest") or []:
            if not isinstance(entry, dict):
                continue
            suggest_category = str(entry.get("category") or "").strip()
            suggest_factor = str(entry.get("factor") or "").strip()
            if suggest_category and suggest_factor:
                self._add_suggest_list_item(suggest_category, suggest_factor)

        for list_widget in self._sections_by_list:
            self._refresh_section_count(list_widget)

        scroll_layout.addStretch()
        root_layout.addWidget(scroll, stretch=1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        root_layout.addLayout(button_row)

    def exec(self) -> int:
        self.showMaximized()
        return super().exec()

    def _create_list_widget(self) -> QListWidget:
        list_widget = QListWidget()
        list_widget.setMinimumHeight(_LIST_MIN_HEIGHT)
        return list_widget

    def _register_list_section(self, list_widget: QListWidget, section: CollapsibleSection) -> None:
        self._sections_by_list[list_widget] = section

    def _refresh_section_count(self, list_widget: QListWidget) -> None:
        section = self._sections_by_list.get(list_widget)
        if section is not None:
            section.set_count(list_widget.count())

    def _create_list_section(self, parent_layout: QVBoxLayout, title: str) -> QListWidget:
        section = CollapsibleSection(title, expanded=True)
        list_widget = self._create_list_widget()
        section.content_layout().addWidget(list_widget)
        section.content_layout().addLayout(self._list_toolbar(list_widget))
        self._register_list_section(list_widget, section)
        parent_layout.addWidget(section)
        return list_widget

    def _create_related_section(self, parent_layout: QVBoxLayout) -> QListWidget:
        section = CollapsibleSection("Související faktory", expanded=True)
        list_widget = self._create_list_widget()
        section.content_layout().addWidget(list_widget)
        section.content_layout().addLayout(self._related_toolbar())
        self._register_list_section(list_widget, section)
        parent_layout.addWidget(section)
        return list_widget

    def _create_suggest_section(self, parent_layout: QVBoxLayout) -> QListWidget:
        section = CollapsibleSection("Doporučené další směry šetření", expanded=True)
        list_widget = self._create_list_widget()
        section.content_layout().addWidget(list_widget)
        section.content_layout().addLayout(self._suggest_toolbar())
        self._register_list_section(list_widget, section)
        parent_layout.addWidget(section)
        return list_widget

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "parent": str(self.parent_combo.currentData() or "").strip(),
            "questions": self._list_values(self.questions_list),
            "evidence": self._list_values(self.evidence_list),
            "related": self._list_values(self.related_list),
            "supports": self._list_values(self.supports_list),
            "contradicts": self._list_values(self.contradicts_list),
            "actions": self._list_values(self.actions_list),
            "suggest": self._suggest_values(),
        }

    def _list_toolbar(self, list_widget: QListWidget) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Přidat")
        edit_btn = QPushButton("Upravit")
        remove_btn = QPushButton("Odebrat")
        add_btn.clicked.connect(lambda: self._add_item(list_widget))
        edit_btn.clicked.connect(lambda: self._edit_item(list_widget))
        remove_btn.clicked.connect(lambda: self._remove_item(list_widget))
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addStretch()
        return toolbar

    def _related_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Přidat")
        remove_btn = QPushButton("Odebrat")
        add_btn.clicked.connect(self._add_related_factor)
        remove_btn.clicked.connect(lambda: self._remove_item(self.related_list))
        toolbar.addWidget(add_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addStretch()
        return toolbar

    def _suggest_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        add_btn = QPushButton("Přidat doporučení")
        edit_btn = QPushButton("Upravit")
        remove_btn = QPushButton("Odebrat")
        add_btn.clicked.connect(self._add_suggest_item)
        edit_btn.clicked.connect(self._edit_suggest_item)
        remove_btn.clicked.connect(lambda: self._remove_item(self.suggest_list))
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(remove_btn)
        toolbar.addStretch()
        return toolbar

    def _current_factor_name(self) -> str:
        return self.name_edit.text().strip() or self._original_name

    def _list_values(self, list_widget: QListWidget) -> list[str]:
        values: list[str] = []
        for row in range(list_widget.count()):
            value = list_widget.item(row).text().strip()
            if value and value not in values:
                values.append(value)
        return values

    def _suggest_values(self) -> list[dict]:
        values: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for row in range(self.suggest_list.count()):
            entry = self.suggest_list.item(row).data(Qt.ItemDataRole.UserRole)
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category") or "").strip()
            factor = str(entry.get("factor") or "").strip()
            if not category or not factor:
                continue
            key = (category, factor)
            if key in seen:
                continue
            seen.add(key)
            values.append({"category": category, "factor": factor})
        return values

    def _add_suggest_list_item(self, category: str, factor: str) -> None:
        item = QListWidgetItem(ishikawa_factors_service.format_suggest_line(category, factor))
        item.setData(Qt.ItemDataRole.UserRole, {"category": category, "factor": factor})
        self.suggest_list.addItem(item)
        self.suggest_list.setCurrentRow(self.suggest_list.count() - 1)
        self._refresh_section_count(self.suggest_list)

    def _pick_suggest_entry(
        self,
        *,
        initial_category: str = "",
        initial_factor: str = "",
        exclude: set[tuple[str, str]] | None = None,
    ) -> dict | None:
        excluded = exclude or set()
        categories = list(ISHIKAWA_CATEGORIES)
        if not categories:
            return None

        category_index = 0
        if initial_category and initial_category in categories:
            category_index = categories.index(initial_category)

        category, accepted = QInputDialog.getItem(
            self,
            "Doporučený směr šetření",
            "Kategorie:",
            categories,
            category_index,
            editable=False,
        )
        if not accepted or not category:
            return None

        category_name = str(category).strip()
        factor_options = [
            name
            for name in ishikawa_factors_service.get_factors(category_name)
            if name != ISHIKAWA_OTHER_FACTOR
        ]
        if not factor_options:
            QMessageBox.information(
                self,
                "Správa faktoru",
                f"Kategorie „{category_name}“ nemá k dispozici žádný faktor.",
            )
            return None

        factor_index = 0
        if initial_factor and initial_factor in factor_options:
            factor_index = factor_options.index(initial_factor)

        factor_name, accepted = QInputDialog.getItem(
            self,
            "Doporučený směr šetření",
            "Faktor:",
            factor_options,
            factor_index,
            editable=False,
        )
        if not accepted or not factor_name:
            return None

        value = str(factor_name).strip()
        if not value or (category_name, value) in excluded:
            return None

        return {"category": category_name, "factor": value}

    def _add_suggest_item(self) -> None:
        excluded = {
            (entry["category"], entry["factor"])
            for entry in self._suggest_values()
        }
        entry = self._pick_suggest_entry(exclude=excluded)
        if entry is None:
            return
        self._add_suggest_list_item(entry["category"], entry["factor"])

    def _edit_suggest_item(self) -> None:
        item = self.suggest_list.currentItem()
        if item is None:
            QMessageBox.information(self, "Správa faktoru", "Vyberte doporučení.")
            return

        current = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(current, dict):
            return

        current_category = str(current.get("category") or "").strip()
        current_factor = str(current.get("factor") or "").strip()
        excluded = {
            (entry["category"], entry["factor"])
            for entry in self._suggest_values()
            if (entry["category"], entry["factor"]) != (current_category, current_factor)
        }
        entry = self._pick_suggest_entry(
            initial_category=current_category,
            initial_factor=current_factor,
            exclude=excluded,
        )
        if entry is None:
            return

        item.setText(
            ishikawa_factors_service.format_suggest_line(entry["category"], entry["factor"])
        )
        item.setData(Qt.ItemDataRole.UserRole, entry)

    def _add_item(self, list_widget: QListWidget) -> None:
        text, accepted = QInputDialog.getText(self, "Přidat položku", "Text:")
        if not accepted:
            return
        value = text.strip()
        if not value:
            return
        list_widget.addItem(value)
        list_widget.setCurrentRow(list_widget.count() - 1)
        self._refresh_section_count(list_widget)

    def _add_related_factor(self) -> None:
        current_name = self._current_factor_name()
        selected_related = set(self._list_values(self.related_list))
        options = [
            name
            for name in ishikawa_factors_service.get_factors(self._category)
            if name != current_name
            and name != ISHIKAWA_OTHER_FACTOR
            and name not in selected_related
        ]
        if not options:
            QMessageBox.information(
                self,
                "Správa faktoru",
                "Nejsou k dispozici další faktory této kategorie.",
            )
            return

        choice, accepted = QInputDialog.getItem(
            self,
            "Přidat související faktor",
            "Faktor:",
            options,
            editable=False,
        )
        if not accepted or not choice:
            return

        value = str(choice).strip()
        if not value or value in selected_related or value == current_name:
            return

        self.related_list.addItem(value)
        self.related_list.setCurrentRow(self.related_list.count() - 1)
        self._refresh_section_count(self.related_list)

    def _edit_item(self, list_widget: QListWidget) -> None:
        item = list_widget.currentItem()
        if item is None:
            QMessageBox.information(self, "Správa faktoru", "Vyberte položku.")
            return

        text, accepted = QInputDialog.getText(
            self,
            "Upravit položku",
            "Text:",
            text=item.text(),
        )
        if not accepted:
            return
        value = text.strip()
        if not value:
            return
        item.setText(value)

    def _remove_item(self, list_widget: QListWidget) -> None:
        row = list_widget.currentRow()
        if row < 0:
            QMessageBox.information(self, "Správa faktoru", "Vyberte položku.")
            return
        list_widget.takeItem(row)
        self._refresh_section_count(list_widget)

    def _accept(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.information(self, "Správa faktoru", "Vyplňte název faktoru.")
            return
        if self._original_name == ISHIKAWA_OTHER_FACTOR and name != ISHIKAWA_OTHER_FACTOR:
            QMessageBox.information(self, "Správa faktoru", 'Název "Jiné" nelze změnit.')
            return
        if name == ISHIKAWA_OTHER_FACTOR and self._original_name != ISHIKAWA_OTHER_FACTOR:
            QMessageBox.information(self, "Správa faktoru", 'Název "Jiné" je vyhrazený.')
            return
        self.accept()
