"""Panel řídicího procesu — střední pracovní plocha a pravá metodická podpora."""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
from moduly.audity.constants import (
    GUIDE_LABEL_AREAS,
    GUIDE_LABEL_EXPECTED_OUTPUT,
    GUIDE_LABEL_UCEL,
    GUIDE_LABEL_WHY_IMPORTANT,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget
from moduly.audity.ui.audit_methodology_panel_widget import AuditMethodologyPanelWidget


class AuditProcessOverviewWidget(QWidget):
    """Střední přehled řídicího procesu."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._content_host)
        self._scroll_area = scroll

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_process(self, knowledge: dict | None) -> None:
        self._clear_content()

        if not knowledge:
            self._content_layout.addWidget(self._info_label("Vyberte řídicí proces ve stromu vlevo."))
            self._content_layout.addStretch()
            self.scroll_to_top()
            return

        for label, field in (
            (GUIDE_LABEL_UCEL, "ucel_procesu"),
            (GUIDE_LABEL_WHY_IMPORTANT, "proc_je_dulezity"),
            (GUIDE_LABEL_EXPECTED_OUTPUT, "ocekavany_vystup"),
        ):
            text = audit_knowledge_service.get_text_field(knowledge, field)
            if text:
                self._content_layout.addWidget(self._build_text_block(label, text))

        criteria = audit_knowledge_service.get_active_criteria(knowledge)
        if criteria:
            areas_host = QWidget()
            areas_layout = QVBoxLayout(areas_host)
            areas_layout.setContentsMargins(0, 0, 0, 0)
            areas_layout.setSpacing(6)

            header = QLabel(GUIDE_LABEL_AREAS)
            header.setObjectName("SectionTitle")
            areas_layout.addWidget(header)

            for criterion in criteria:
                name = str(criterion.get("nazev") or "—").strip() or "—"
                row = QLabel(f"• {name}")
                row.setWordWrap(True)
                areas_layout.addWidget(row)

            self._content_layout.addWidget(self._build_panel_block(areas_host))

        self._content_layout.addStretch()
        self.scroll_to_top()

    def scroll_to_top(self) -> None:
        self._scroll_area.verticalScrollBar().setValue(0)

    def _build_text_block(self, label: str, text: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel(label)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(self._info_label(text))
        return container

    def _build_panel_block(self, content: QWidget) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)
        panel_layout.addWidget(content)
        return panel

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label


class AuditProcessKnowledgeWidget(QWidget):
    def __init__(
        self,
        methodology_panel: AuditMethodologyPanelWidget,
        parent=None,
        *,
        verification_filter: str = VERIFICATION_TYPE_DOCUMENTATION,
        extraordinary_only: bool = False,
    ):
        super().__init__(parent)

        self._methodology_panel = methodology_panel
        self._process_knowledge: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.criterion_widget = AuditKnowledgeCriterionWidget(
            methodology_panel=methodology_panel,
            verification_filter=verification_filter,
            extraordinary_only=extraordinary_only,
        )
        layout.addWidget(self.criterion_widget, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def verification_type_changed(self):
        return self.criterion_widget.verification_type_changed

    def set_verification_filter(self, verification_type: str) -> None:
        self.criterion_widget.set_verification_filter(verification_type)

    def show_criterion(
        self,
        criterion: dict | None,
        *,
        process_id: str = "",
        process_label: str = "",
        process_purpose: str = "",
        criterion_label: str = "",
        process_knowledge: dict | None = None,
    ) -> None:
        self._process_knowledge = process_knowledge
        self.criterion_widget.set_process_purpose(process_purpose)
        self._methodology_panel.show_criterion(criterion, process_knowledge)
        self.criterion_widget.set_criterion(
            criterion,
            area_id=process_id,
            area_label=process_label,
            section_label=criterion_label,
        )
        self.criterion_widget.scroll_to_top()

    def clear_criterion(self) -> None:
        self._process_knowledge = None
        self.criterion_widget.set_criterion(None)

    def set_audit_id(self, audit_id: int | None) -> None:
        self.criterion_widget.set_audit_id(audit_id)
        self._methodology_panel.set_audit_id(audit_id)

    def set_deferred_edits(self, deferred_edits) -> None:
        self.criterion_widget.set_deferred_edits(deferred_edits)

    def set_notes_mode(self, notes_mode: str | None) -> None:
        self.criterion_widget.set_notes_mode(notes_mode)

    def capture_section_summary(self) -> None:
        self.criterion_widget.capture_section_summary()

    def reload_section_summary(self) -> None:
        self.criterion_widget.reload_section_summary()

    def set_on_finding_saved(self, callback) -> None:
        self.criterion_widget.set_on_finding_saved(callback)

    def set_on_deferred_dirty(self, callback) -> None:
        self.criterion_widget.set_on_deferred_dirty(callback)

    def refresh_findings_display(self) -> None:
        self.criterion_widget.refresh()
        self._methodology_panel.refresh()
