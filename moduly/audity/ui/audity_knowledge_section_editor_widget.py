"""Editační formulář oblasti ověření v editoru metodiky auditora."""

from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_SECTION_LIST_TABS,
    KNOWLEDGE_EDITOR_SECTION_TABS,
)
from moduly.audity.ui.audity_knowledge_assertions_widget import AudityKnowledgeAssertionsWidget
from moduly.audity.ui.audity_knowledge_list_editor_widget import AudityKnowledgeListEditorWidget


class AudityKnowledgeSectionEditorWidget(QWidget):
    """Formulář metadat oblasti ověření a záložky metodických seznamů."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._process_id = ""
        self._section_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self._id_label = QLabel()
        self._nazev_edit = QLineEdit()
        self._popis_edit = QTextEdit()
        self._popis_edit.setMinimumHeight(90)
        self._cil_overeni_edit = QTextEdit()
        self._cil_overeni_edit.setMinimumHeight(90)
        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)
        self._aktivni_check = QCheckBox("Oblast je aktivní")

        form.addRow("Identifikátor:", self._id_label)
        form.addRow("Název:", self._nazev_edit)
        form.addRow("Popis:", self._popis_edit)
        form.addRow("Cíl ověření:", self._cil_overeni_edit)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        scroll_layout.addLayout(form)

        self._tabs = QTabWidget()
        self._assertions_widget = AudityKnowledgeAssertionsWidget()
        self._list_widgets: dict[str, AudityKnowledgeListEditorWidget] = {}

        list_tab_titles = {title: field_name for title, field_name in KNOWLEDGE_EDITOR_SECTION_LIST_TABS}
        for index, title in enumerate(KNOWLEDGE_EDITOR_SECTION_TABS):
            if index == 0:
                self._tabs.addTab(self._assertions_widget, title)
                continue

            field_name = list_tab_titles.get(title)
            if field_name is None:
                continue
            list_widget = AudityKnowledgeListEditorWidget(field_name)
            self._list_widgets[field_name] = list_widget
            self._tabs.addTab(list_widget, title)

        scroll_layout.addWidget(self._tabs, stretch=1)
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, stretch=1)

    @property
    def process_id(self) -> str:
        return self._process_id

    @property
    def section_id(self) -> str:
        return self._section_id

    def has_section(self) -> bool:
        return bool(self._process_id and self._section_id)

    def load_section(
        self,
        *,
        process_id: str,
        section_id: str,
        section: dict,
    ) -> None:
        self._process_id = process_id
        self._section_id = section_id

        self._id_label.setText(section_id)
        self._nazev_edit.setText(str(section.get("nazev") or ""))
        self._popis_edit.setPlainText(str(section.get("popis") or ""))
        self._cil_overeni_edit.setPlainText(str(section.get("cil_overeni") or ""))
        self._poradi_spin.setValue(int(section.get("poradi") or 0))
        self._aktivni_check.setChecked(bool(section.get("aktivni", True)))
        self._assertions_widget.load_section(
            process_id=process_id,
            section_id=section_id,
            section=section,
        )
        for list_widget in self._list_widgets.values():
            list_widget.load_section(
                process_id=process_id,
                section_id=section_id,
                section=section,
            )

    def clear_section(self) -> None:
        self._process_id = ""
        self._section_id = ""
        self._id_label.clear()
        self._nazev_edit.clear()
        self._popis_edit.clear()
        self._cil_overeni_edit.clear()
        self._poradi_spin.setValue(0)
        self._aktivni_check.setChecked(True)
        self._assertions_widget.clear_section()
        for list_widget in self._list_widgets.values():
            list_widget.clear_section()

    def section_metadata(self) -> dict:
        return {
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "cil_overeni": self._cil_overeni_edit.toPlainText().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
        }
