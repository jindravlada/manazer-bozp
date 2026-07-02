"""Panel řídicího procesu — přehled procesu a pracovní karta oblasti ověření."""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from moduly.audity.constants import (
    GUIDE_BLOCK_EVALUATE,
    GUIDE_BLOCK_UNDERSTAND,
    GUIDE_BLOCK_VERIFY,
    GUIDE_LABEL_AREAS,
    GUIDE_LABEL_EXPECTED_OUTPUT,
    GUIDE_LABEL_NORM_REQUIREMENTS,
    GUIDE_LABEL_PROCESS_LINKS,
    GUIDE_LABEL_UCEL,
    GUIDE_LABEL_WHY_IMPORTANT,
    GUIDE_SELECT_AREA_FOR_EVALUATION,
)
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget


class AuditProcessOverviewWidget(QWidget):
    """Přehled řídicího procesu ve třech blocích průvodce auditora."""

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

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def show_process(self, knowledge: dict | None) -> None:
        self._clear_content()

        if not knowledge:
            self._content_layout.addWidget(self._info_label("Vyberte řídicí proces ve stromu vlevo."))
            self._content_layout.addStretch()
            return

        understand = self._build_understand_block(knowledge)
        if understand is not None:
            self._content_layout.addWidget(understand)

        verify = self._build_verify_block(knowledge)
        if verify is not None:
            self._content_layout.addWidget(verify)

        evaluate = self._build_evaluate_block()
        if evaluate is not None:
            self._content_layout.addWidget(evaluate)

        self._content_layout.addStretch()

    def _build_understand_block(self, knowledge: dict) -> QWidget | None:
        parts: list[QWidget] = []

        for label, field in (
            (GUIDE_LABEL_UCEL, "ucel_procesu"),
            (GUIDE_LABEL_WHY_IMPORTANT, "proc_je_dulezity"),
            (GUIDE_LABEL_EXPECTED_OUTPUT, "ocekavany_vystup"),
        ):
            text = audit_knowledge_service.get_text_field(knowledge, field)
            if text:
                parts.append(self._build_text_part(label, text))

        if audit_knowledge_service.has_active_list(knowledge, "vazby_procesy"):
            parts.append(
                self._build_list_part(
                    GUIDE_LABEL_PROCESS_LINKS,
                    audit_knowledge_service.get_active_items(knowledge.get("vazby_procesy")),
                )
            )

        if audit_knowledge_service.has_active_list(knowledge, "pozadavky_norem"):
            parts.append(
                self._build_list_part(
                    GUIDE_LABEL_NORM_REQUIREMENTS,
                    audit_knowledge_service.get_active_items(knowledge.get("pozadavky_norem")),
                )
            )

        if not parts:
            return None
        return self._build_guide_block(GUIDE_BLOCK_UNDERSTAND, parts)

    def _build_verify_block(self, knowledge: dict) -> QWidget | None:
        criteria = audit_knowledge_service.get_active_criteria(knowledge)
        if not criteria:
            return None

        items_host = QWidget()
        items_layout = QVBoxLayout(items_host)
        items_layout.setContentsMargins(0, 0, 0, 0)
        items_layout.setSpacing(6)

        header = QLabel(GUIDE_LABEL_AREAS)
        header.setObjectName("SectionTitle")
        items_layout.addWidget(header)

        for criterion in criteria:
            name = str(criterion.get("nazev") or "—").strip() or "—"
            label = QLabel(f"• {name}")
            label.setWordWrap(True)
            items_layout.addWidget(label)

        return self._build_guide_block(GUIDE_BLOCK_VERIFY, [items_host])

    def _build_evaluate_block(self) -> QWidget:
        return self._build_guide_block(
            GUIDE_BLOCK_EVALUATE,
            [self._info_label(GUIDE_SELECT_AREA_FOR_EVALUATION)],
        )

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_guide_block(self, title: str, parts: list[QWidget]) -> QWidget:
        container = QWidget()
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(8)

        header = QLabel(title)
        header.setObjectName("GuideBlockTitle")
        block_layout.addWidget(header)

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(10)

        for part in parts:
            panel_layout.addWidget(part)

        block_layout.addWidget(panel)
        return container

    def _build_text_part(self, label: str, text: str) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel(label)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(self._info_label(text))
        return container

    def _build_list_part(self, label: str, items: list[dict]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel(label)
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        for item in items:
            name = str(item.get("nazev") or "—").strip() or "—"
            row = QLabel(f"• {name}")
            row.setWordWrap(True)
            layout.addWidget(row)

            popis = str(item.get("popis") or "").strip()
            if popis:
                description = self._info_label(popis)
                description.setContentsMargins(16, 0, 0, 0)
                layout.addWidget(description)

        return container

    @staticmethod
    def _info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label


class AuditProcessKnowledgeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.criterion_widget = AuditKnowledgeCriterionWidget()
        layout.addWidget(self.criterion_widget)

    def show_criterion(
        self,
        criterion: dict | None,
        *,
        process_id: str = "",
        process_label: str = "",
        process_purpose: str = "",
        criterion_label: str = "",
    ) -> None:
        self.criterion_widget.set_process_purpose(process_purpose)
        self.criterion_widget.set_criterion(
            criterion,
            area_id=process_id,
            area_label=process_label,
            section_label=criterion_label,
        )

    def clear_criterion(self) -> None:
        self.criterion_widget.set_criterion(None)

    def set_audit_id(self, audit_id: int | None) -> None:
        self.criterion_widget.set_audit_id(audit_id)

    def set_on_finding_saved(self, callback) -> None:
        self.criterion_widget.set_on_finding_saved(callback)

    def refresh_findings_display(self) -> None:
        self.criterion_widget.refresh()
