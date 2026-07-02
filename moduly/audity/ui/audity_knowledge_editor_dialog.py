"""Dialog editoru metodiky auditora — zatím pouze navigace ve stromu procesů."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_close_button
from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER,
    KNOWLEDGE_EDITOR_EDIT_PLACEHOLDER,
    KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT,
    KNOWLEDGE_EDITOR_USER_COPY_HINT,
    KNOWLEDGE_EDITOR_WINDOW_TITLE,
    METHODOLOGY_PANEL_MIN_WIDTH,
    METHODOLOGY_PANEL_STRETCH,
    PROCESS_PANEL_LEFT_WIDTH,
    PROCESS_TERM_CRITERION,
    WORK_PANEL_STRETCH,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget
from moduly.audity.ui.audit_process_knowledge_widget import AuditProcessOverviewWidget


class AudityKnowledgeEditorDialog(QDialog):
    """Editor metodiky auditora — v1.2 zatím bez editace, pouze navigace."""

    _PAGE_HINT = 0
    _PAGE_PROCESS = 1
    _PAGE_SECTION = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_EDITOR_WINDOW_TITLE)

        audit_knowledge_editor_service.ensure_user_catalogs()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        hint_label = QLabel(KNOWLEDGE_EDITOR_USER_COPY_HINT)
        hint_label.setObjectName("InfoText")
        hint_label.setWordWrap(True)
        root.addWidget(hint_label)

        main_splitter = QSplitter()

        self.knowledge_tree = AuditKnowledgeTreeWidget()
        self.knowledge_tree.criterion_selected.connect(self._on_criterion_selected)
        self.knowledge_tree.process_selected.connect(self._on_process_selected)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.addWidget(self.knowledge_tree, 1)
        tree_panel.setMinimumWidth(PROCESS_PANEL_LEFT_WIDTH)
        tree_panel.setMaximumWidth(PROCESS_PANEL_LEFT_WIDTH)

        work_splitter = QSplitter()

        self.center_panel = QFrame()
        self.center_panel.setObjectName("ModulePanel")
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(8)

        self.center_title_label = QLabel()
        self.center_title_label.setObjectName("SectionTitle")
        self.center_title_label.setWordWrap(True)

        self.center_description_label = QLabel()
        self.center_description_label.setObjectName("InfoText")
        self.center_description_label.setWordWrap(True)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_hint_page())
        self.overview_widget = AuditProcessOverviewWidget()
        self.content_stack.addWidget(self.overview_widget)
        self.content_stack.addWidget(self._build_section_page())

        center_layout.addWidget(self.center_title_label)
        center_layout.addWidget(self.center_description_label)
        center_layout.addWidget(self.content_stack, 1)

        self.right_panel = QFrame()
        self.right_panel.setObjectName("ModulePanel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)

        right_title = QLabel("Auditní tvrzení")
        right_title.setObjectName("SectionTitle")
        self.right_placeholder_label = QLabel(KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER)
        self.right_placeholder_label.setObjectName("InfoText")
        self.right_placeholder_label.setWordWrap(True)
        right_layout.addWidget(right_title)
        right_layout.addWidget(self.right_placeholder_label)
        right_layout.addStretch()

        self.right_panel.setMinimumWidth(METHODOLOGY_PANEL_MIN_WIDTH)

        work_splitter.addWidget(self.center_panel)
        work_splitter.addWidget(self.right_panel)
        work_splitter.setStretchFactor(0, WORK_PANEL_STRETCH)
        work_splitter.setStretchFactor(1, METHODOLOGY_PANEL_STRETCH)
        work_splitter.setSizes([640, 320])

        main_splitter.addWidget(tree_panel)
        main_splitter.addWidget(work_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 960])

        root.addWidget(main_splitter, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        configure_close_button(buttons)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.knowledge_tree.reload_tree()
        self._show_hint()

    def _build_hint_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _build_section_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(KNOWLEDGE_EDITOR_EDIT_PLACEHOLDER)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _show_hint(self) -> None:
        self.center_title_label.setText(self.windowTitle())
        self.center_description_label.setText(
            f"Vyberte {PROCESS_TERM_CRITERION.lower()} ve stromu řídicích procesů vlevo."
        )
        self.center_description_label.setVisible(True)
        self.overview_widget.show_process(None)
        self.right_placeholder_label.setText(KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER)
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        process_def = audit_knowledge_service.get_process_by_id(node.process_id)
        self.center_title_label.setText(node.process_label)

        if process_def and process_def.popis:
            self.center_description_label.setText(process_def.popis)
            self.center_description_label.setVisible(True)
        else:
            self.center_description_label.setText(
                f"Vyberte {PROCESS_TERM_CRITERION.lower()} pod tímto procesem."
            )
            self.center_description_label.setVisible(True)

        if process_def and process_def.has_knowledge_file:
            knowledge = audit_knowledge_service.load_process_knowledge(process_def)
            self.overview_widget.show_process(knowledge)
            self.content_stack.setCurrentIndex(self._PAGE_PROCESS)
        else:
            self.overview_widget.show_process(None)
            self.content_stack.setCurrentIndex(self._PAGE_HINT)

        self.right_placeholder_label.setText(KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER)

    def _on_criterion_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        criterion = node.section
        if criterion is None:
            self._show_hint()
            return

        section_label = str(criterion.get("nazev") or "").strip()
        self.center_title_label.setText(section_label)

        cil_overeni = audit_knowledge_service.get_text_field(criterion, "cil_overeni")
        section_popis = str(criterion.get("popis") or "").strip()
        if cil_overeni:
            self.center_description_label.setText(cil_overeni)
            self.center_description_label.setVisible(True)
        elif section_popis:
            self.center_description_label.setText(section_popis)
            self.center_description_label.setVisible(True)
        else:
            self.center_description_label.setVisible(False)

        assertions = audit_knowledge_service.get_audit_questions(criterion)
        if assertions:
            lines = [
                f"• {str(item.get('text') or item.get('nazev') or '—').strip()}"
                for item in assertions
            ]
            preview = "\n".join(lines[:5])
            if len(assertions) > 5:
                preview += f"\n… (+{len(assertions) - 5} dalších)"
            self.right_placeholder_label.setText(
                f"{KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER}\n\nNáhled ({len(assertions)}):\n{preview}"
            )
        else:
            self.right_placeholder_label.setText(KNOWLEDGE_EDITOR_ASSERTIONS_PLACEHOLDER)

        self.content_stack.setCurrentIndex(self._PAGE_SECTION)
