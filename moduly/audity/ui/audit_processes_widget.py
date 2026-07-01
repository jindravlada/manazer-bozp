from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from moduly.audity.constants import (
    PROCESS_NOT_IMPLEMENTED_TEXT,
    PROCESS_TERM_CRITERION,
    PROCESS_TERM_PROCESS,
    TAB_AUDITOVANE_PROCESY,
)
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget
from moduly.audity.ui.audit_process_knowledge_widget import AuditProcessKnowledgeWidget


class AuditProcessesWidget(QWidget):
    """Záložka Auditované procesy — strom procesů a pracovní karta."""

    _PAGE_HINT = 0
    _PAGE_PLACEHOLDER = 1
    _PAGE_KNOWLEDGE = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()

        self.knowledge_tree = AuditKnowledgeTreeWidget()
        self.knowledge_tree.criterion_selected.connect(self._on_criterion_selected)
        self.knowledge_tree.process_selected.connect(self._on_process_selected)

        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("ModulePanel")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        self._current_process_id = ""
        self._current_process_purpose = ""
        self._current_criterion_id = ""
        self._current_criterion_label = ""

        self.process_title_label = QLabel()
        self.process_title_label.setObjectName("SectionTitle")
        self.process_title_label.setWordWrap(True)

        self.process_description_label = QLabel()
        self.process_description_label.setObjectName("InfoText")
        self.process_description_label.setWordWrap(True)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_hint_page())
        self.content_stack.addWidget(self._build_placeholder_page())
        self.knowledge_widget = AuditProcessKnowledgeWidget()
        self.content_stack.addWidget(self.knowledge_widget)

        detail_layout.addWidget(self.process_title_label)
        detail_layout.addWidget(self.process_description_label)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(self.content_stack, 1)

        splitter.addWidget(self.knowledge_tree)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

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
            f"Vyberte {PROCESS_TERM_CRITERION.lower()} ve stromu auditovaných procesů vlevo."
        )
        self.process_description_label.setVisible(True)
        self.knowledge_widget.clear_criterion()
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        self._current_process_id = node.process_id
        self._current_criterion_id = ""
        self._current_criterion_label = ""

        process_def = audit_knowledge_service.get_process_by_id(node.process_id)
        self.process_title_label.setText(node.process_label)

        description_parts: list[str] = []
        if process_def and process_def.popis:
            description_parts.append(process_def.popis)
        if process_def and process_def.ucel_procesu:
            self._current_process_purpose = process_def.ucel_procesu
            description_parts.append(f"Účel procesu: {process_def.ucel_procesu}")
        else:
            self._current_process_purpose = ""

        if description_parts:
            self.process_description_label.setText("\n\n".join(description_parts))
            self.process_description_label.setVisible(True)
        else:
            self.process_description_label.setText(
                f"Vyberte {PROCESS_TERM_CRITERION.lower()} pod tímto procesem."
            )
            self.process_description_label.setVisible(True)

        self.knowledge_widget.clear_criterion()
        if process_def and process_def.has_knowledge_file and node.children:
            self.content_stack.setCurrentIndex(self._PAGE_HINT)
        else:
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
        criterion_popis = str(criterion.get("popis") or "").strip()
        header_parts = []
        if self._current_process_purpose:
            header_parts.append(f"Účel procesu: {self._current_process_purpose}")
        if criterion_popis:
            header_parts.append(f"{PROCESS_TERM_CRITERION}: {criterion_popis}")
        if header_parts:
            self.process_description_label.setText("\n\n".join(header_parts))
            self.process_description_label.setVisible(True)
        else:
            self.process_description_label.setVisible(False)

        self.knowledge_widget.show_criterion(
            criterion,
            process_id=node.process_id,
            process_label=node.process_label,
            process_purpose=self._current_process_purpose,
            criterion_label=self._current_criterion_label,
        )
        self.content_stack.setCurrentIndex(self._PAGE_KNOWLEDGE)
