"""Editační formulář oblasti ověření v editoru metodiky auditora."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_LABEL
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.ui.audit_knowledge_control_process_combo import (
    populate_control_process_combo,
    selected_control_process_id,
)

from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_SECTION_LIST_TABS,
    KNOWLEDGE_EDITOR_SECTION_POSTUP_TAB,
    KNOWLEDGE_EDITOR_SECTION_REFERENCE_PHOTO_TAB,
    KNOWLEDGE_EDITOR_SECTION_TABS,
)
from moduly.audity.ui.audity_knowledge_assertions_widget import AudityKnowledgeAssertionsWidget
from moduly.audity.ui.audity_knowledge_described_list_editor_widget import (
    AudityKnowledgeDescribedListEditorWidget,
)
from moduly.audity.ui.audity_knowledge_list_editor_widget import AudityKnowledgeListEditorWidget
from moduly.audity.ui.audity_knowledge_reference_photo_editor_widget import (
    AudityKnowledgeReferencePhotoEditorWidget,
)

SECTION_MULTILINE_VISIBLE_LINES = 3


def text_edit_height_for_visible_lines(edit: QTextEdit, lines: int) -> int:
    """Výška QTextEdit pro daný počet viditelných řádků aktuálního fontu.

    Odvozuje se z ``lineSpacing`` fontu, okrajů dokumentu, rámečku a
    vnitřních okrajů widgetu, aby platila i při jiném DPI a měřítku.
    """
    edit.ensurePolished()
    metrics = edit.fontMetrics()
    contents = edit.contentsMargins()
    viewport = edit.viewportMargins()
    document_margin = int(edit.document().documentMargin())
    return (
        lines * metrics.lineSpacing()
        + (2 * document_margin)
        + (2 * edit.frameWidth())
        + contents.top()
        + contents.bottom()
        + viewport.top()
        + viewport.bottom()
    )


def configure_compact_multiline_edit(
    edit: QTextEdit,
    *,
    lines: int = SECTION_MULTILINE_VISIBLE_LINES,
) -> None:
    """Ponechá víceřádkový editor, ale zafixuje výšku na přibližně ``lines`` řádků."""
    height = text_edit_height_for_visible_lines(edit, lines)
    edit.setFixedHeight(height)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)


class AudityKnowledgeSectionEditorWidget(QWidget):
    """Formulář metadat oblasti ověření a záložky metodických seznamů."""

    content_modified = Signal()
    content_saved = Signal()
    question_kinds_modified = Signal()

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
        self._control_process_combo = QComboBox()
        self._popis_edit = QTextEdit()
        configure_compact_multiline_edit(self._popis_edit)
        self._cil_overeni_edit = QTextEdit()
        configure_compact_multiline_edit(self._cil_overeni_edit)
        self._poradi_spin = QSpinBox()
        self._poradi_spin.setRange(0, 99999)
        self._poradi_spin.setSingleStep(10)
        self._aktivni_check = QCheckBox("Oblast je aktivní")

        form.addRow("Identifikátor:", self._id_label)
        form.addRow("Název:", self._nazev_edit)
        form.addRow(KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_LABEL, self._control_process_combo)
        form.addRow("Popis:", self._popis_edit)
        form.addRow("Cíl ověření:", self._cil_overeni_edit)
        form.addRow("Pořadí:", self._poradi_spin)
        form.addRow("", self._aktivni_check)
        scroll_layout.addLayout(form, stretch=0)

        self._tabs = QTabWidget()
        self._tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._assertions_widget = AudityKnowledgeAssertionsWidget()
        self._list_widgets: dict[str, AudityKnowledgeListEditorWidget] = {}
        self._postup_widget = AudityKnowledgeDescribedListEditorWidget(
            KNOWLEDGE_EDITOR_SECTION_POSTUP_TAB[1]
        )
        self._reference_photo_widget = AudityKnowledgeReferencePhotoEditorWidget()

        list_tab_titles = {title: field_name for title, field_name in KNOWLEDGE_EDITOR_SECTION_LIST_TABS}
        postup_title, postup_field = KNOWLEDGE_EDITOR_SECTION_POSTUP_TAB
        reference_title, reference_field = KNOWLEDGE_EDITOR_SECTION_REFERENCE_PHOTO_TAB

        for index, title in enumerate(KNOWLEDGE_EDITOR_SECTION_TABS):
            if index == 0:
                self._tabs.addTab(self._assertions_widget, title)
                continue

            if title == postup_title:
                self._tabs.addTab(self._postup_widget, title)
                continue

            if title == reference_title:
                self._tabs.addTab(self._reference_photo_widget, title)
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
        self.setMinimumHeight(0)

        for widget in (self._nazev_edit, self._popis_edit, self._cil_overeni_edit):
            widget.textChanged.connect(lambda *_args: self.content_modified.emit())
        self._poradi_spin.valueChanged.connect(lambda *_args: self.content_modified.emit())
        self._aktivni_check.toggled.connect(lambda *_args: self.content_modified.emit())
        self._control_process_combo.currentIndexChanged.connect(
            lambda *_args: self.content_modified.emit(),
        )

        child_widgets = [
            self._assertions_widget,
            self._postup_widget,
            self._reference_photo_widget,
            *self._list_widgets.values(),
        ]
        for child in child_widgets:
            child.content_modified.connect(self.content_modified.emit)
            child.content_saved.connect(self.content_saved.emit)
        self._assertions_widget.question_kinds_modified.connect(
            self.question_kinds_modified.emit
        )

    def has_pending_assertion_kinds(self) -> bool:
        return self._assertions_widget.has_pending_question_kinds()

    def pending_question_kind_overrides(self) -> dict[str, str]:
        return self._assertions_widget.pending_question_kind_overrides()

    def pending_question_kind_changes(self):
        return self._assertions_widget.pending_question_kind_changes()

    def clear_pending_question_kinds_after_persist(self) -> None:
        self._assertions_widget.clear_pending_question_kinds_after_persist()

    def flush_pending_assertion_kinds(self) -> list[str]:
        return self._assertions_widget.flush_pending_question_kinds()

    def discard_pending_assertion_kinds(self) -> None:
        self._assertions_widget.discard_pending_question_kinds()

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
        self._set_metadata_signals_blocked(True)
        try:
            self._process_id = process_id
            self._section_id = section_id

            self._id_label.setText(section_id)
            self._nazev_edit.setText(str(section.get("nazev") or ""))
            populate_control_process_combo(
                self._control_process_combo,
                audit_knowledge_editor_service.normalize_legal_requirement_id(
                    section.get("legal_requirement_id"),
                ),
            )
            self._popis_edit.setPlainText(str(section.get("popis") or ""))
            self._cil_overeni_edit.setPlainText(str(section.get("cil_overeni") or ""))
            self._poradi_spin.setValue(int(section.get("poradi") or 0))
            self._aktivni_check.setChecked(bool(section.get("aktivni", True)))
        finally:
            self._set_metadata_signals_blocked(False)

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
        self._postup_widget.load_section(
            process_id=process_id,
            section_id=section_id,
            section=section,
        )
        self._reference_photo_widget.load_section(
            process_id=process_id,
            section_id=section_id,
            section=section,
        )

    def clear_section(self) -> None:
        self._set_metadata_signals_blocked(True)
        try:
            self._process_id = ""
            self._section_id = ""
            self._id_label.clear()
            self._nazev_edit.clear()
            populate_control_process_combo(self._control_process_combo, None)
            self._popis_edit.clear()
            self._cil_overeni_edit.clear()
            self._poradi_spin.setValue(0)
            self._aktivni_check.setChecked(True)
        finally:
            self._set_metadata_signals_blocked(False)

        self._assertions_widget.clear_section()
        for list_widget in self._list_widgets.values():
            list_widget.clear_section()
        self._postup_widget.clear_section()
        self._reference_photo_widget.clear_section()

    def _set_metadata_signals_blocked(self, blocked: bool) -> None:
        for widget in (self._nazev_edit, self._popis_edit, self._cil_overeni_edit):
            widget.blockSignals(blocked)
        self._poradi_spin.blockSignals(blocked)
        self._aktivni_check.blockSignals(blocked)
        self._control_process_combo.blockSignals(blocked)

    def section_metadata(self) -> dict:
        return {
            "nazev": self._nazev_edit.text().strip(),
            "popis": self._popis_edit.toPlainText().strip(),
            "cil_overeni": self._cil_overeni_edit.toPlainText().strip(),
            "poradi": self._poradi_spin.value(),
            "aktivni": self._aktivni_check.isChecked(),
            "legal_requirement_id": selected_control_process_id(self._control_process_combo),
        }
