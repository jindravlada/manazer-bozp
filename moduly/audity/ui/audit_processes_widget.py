from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import (
    PROCESS_NOT_IMPLEMENTED_TEXT,
    PROCESS_PANEL_LEFT_WIDTH,
    PROCESS_TERM_CRITERION,
    TAB_AUDITOVANE_PROCESY,
)
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget
from moduly.audity.ui.audit_process_knowledge_widget import (
    AuditProcessKnowledgeWidget,
    AuditProcessOverviewWidget,
)


class AuditProcessesWidget(QWidget):
    """Záložka Řídicí procesy — vlevo strom, vpravo metodika a pracovní karta."""

    _PAGE_HINT = 0
    _PAGE_PLACEHOLDER = 1
    _PAGE_OVERVIEW = 2
    _PAGE_KNOWLEDGE = 3

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()

        self.tree_panel = QWidget()
        tree_layout = QVBoxLayout(self.tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        self.knowledge_tree = AuditKnowledgeTreeWidget()
        self.knowledge_tree.criterion_selected.connect(self._on_criterion_selected)
        self.knowledge_tree.process_selected.connect(self._on_process_selected)
        tree_layout.addWidget(self.knowledge_tree, 1)

        self.tree_panel.setMinimumWidth(PROCESS_PANEL_LEFT_WIDTH)
        self.tree_panel.setMaximumWidth(PROCESS_PANEL_LEFT_WIDTH)

        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("ModulePanel")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        self._current_process_id = ""
        self._current_process_purpose = ""
        self._current_criterion_id = ""
        self._current_criterion_label = ""

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self.process_title_label = QLabel()
        self.process_title_label.setObjectName("SectionTitle")
        self.process_title_label.setWordWrap(True)
        header_row.addWidget(self.process_title_label, 1)

        self.process_description_label = QLabel()
        self.process_description_label.setObjectName("InfoText")
        self.process_description_label.setWordWrap(True)

        self.content_stack = QStackedWidget()
        self.content_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.content_stack.addWidget(self._build_hint_page())
        self.content_stack.addWidget(self._build_placeholder_page())
        self.overview_widget = AuditProcessOverviewWidget()
        self.content_stack.addWidget(self.overview_widget)
        self.knowledge_widget = AuditProcessKnowledgeWidget()
        self.content_stack.addWidget(self.knowledge_widget)

        detail_layout.addLayout(header_row)
        detail_layout.addWidget(self.process_description_label)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(self.content_stack, 1)

        splitter.addWidget(self.tree_panel)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 720])

        layout.addWidget(splitter, 1)

        self.reload_processes()

    def set_audit_id(self, audit_id: int | None) -> None:
        self.knowledge_widget.set_audit_id(audit_id)

    def set_on_finding_saved(self, callback) -> None:
        self.knowledge_widget.set_on_finding_saved(callback)

    def refresh_findings_display(self) -> None:
        self.knowledge_widget.refresh_findings_display()

    def reload_processes(self) -> None:
        self.knowledge_tree.reload_tree()
        self._show_hint()

    def _build_hint_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(f"Vyberte {PROCESS_TERM_CRITERION.lower()} ve stromu vlevo.")
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(PROCESS_NOT_IMPLEMENTED_TEXT)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _show_hint(self) -> None:
        self._current_process_id = ""
        self._current_process_purpose = ""
        self._current_criterion_id = ""
        self._current_criterion_label = ""
        self.process_title_label.setText(TAB_AUDITOVANE_PROCESY)
        self.process_description_label.setText(
            f"Vyberte {PROCESS_TERM_CRITERION.lower()} ve stromu řídicích procesů vlevo."
        )
        self.process_description_label.setVisible(True)
        self.knowledge_widget.clear_criterion()
        self.overview_widget.show_process(None)
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        self._current_process_id = node.process_id
        self._current_criterion_id = ""
        self._current_criterion_label = ""

        process_def = audit_knowledge_service.get_process_by_id(node.process_id)
        self.process_title_label.setText(node.process_label)

        if process_def and process_def.ucel_procesu:
            self._current_process_purpose = process_def.ucel_procesu
        else:
            self._current_process_purpose = ""

        if process_def and process_def.popis:
            self.process_description_label.setText(process_def.popis)
            self.process_description_label.setVisible(True)
        else:
            self.process_description_label.setText(
                f"Vyberte {PROCESS_TERM_CRITERION.lower()} pod tímto procesem."
            )
            self.process_description_label.setVisible(True)

        self.knowledge_widget.clear_criterion()
        if process_def and process_def.has_knowledge_file:
            knowledge = audit_knowledge_service.load_process_knowledge(process_def)
            self.overview_widget.show_process(knowledge)
            self.content_stack.setCurrentIndex(self._PAGE_OVERVIEW)
        else:
            self.overview_widget.show_process(None)
            self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)

    def _on_criterion_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        criterion = node.section
        if criterion is None:
            self._show_hint()
            return

        self._current_process_id = node.process_id
        self._current_criterion_id = node.node_id
        self._current_criterion_label = str(criterion.get("nazev") or "").strip()

        if not self._current_process_purpose:
            process_def = audit_knowledge_service.get_process_by_id(node.process_id)
            if process_def is not None:
                self._current_process_purpose = process_def.ucel_procesu

        self.process_title_label.setText(node.process_label)
        section_label = str(criterion.get("nazev") or "").strip()
        section_popis = str(criterion.get("popis") or "").strip()
        cil_overeni = audit_knowledge_service.get_text_field(criterion, "cil_overeni")
        if cil_overeni:
            self.process_description_label.setText(cil_overeni)
            self.process_description_label.setVisible(True)
        elif section_popis:
            self.process_description_label.setText(section_popis)
            self.process_description_label.setVisible(True)
        else:
            self.process_description_label.setVisible(False)

        self.knowledge_widget.show_criterion(
            criterion,
            process_id=node.process_id,
            process_label=node.process_label,
            process_purpose=self._current_process_purpose,
            criterion_label=section_label,
        )
        self.content_stack.setCurrentIndex(self._PAGE_KNOWLEDGE)
