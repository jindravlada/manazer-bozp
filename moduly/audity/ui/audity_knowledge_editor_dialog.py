"""Dialog editoru metodiky auditora."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_close_button, configure_save_cancel_buttons
from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT,
    KNOWLEDGE_EDITOR_USER_COPY_HINT,
    KNOWLEDGE_EDITOR_WINDOW_TITLE,
    PROCESS_PANEL_LEFT_WIDTH,
    PROCESS_TERM_CRITERION,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget
from moduly.audity.ui.audity_knowledge_section_editor_widget import (
    AudityKnowledgeSectionEditorWidget,
)
from moduly.audity.ui.audit_process_knowledge_widget import AuditProcessOverviewWidget


class AudityKnowledgeEditorDialog(QDialog):
    """Editor metodiky auditora — editace metadat oblasti ověření."""

    _PAGE_HINT = 0
    _PAGE_PROCESS = 1
    _PAGE_SECTION = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_EDITOR_WINDOW_TITLE)

        self._current_process_id = ""
        self._current_section_id = ""

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
        self.section_editor = AudityKnowledgeSectionEditorWidget()
        self.content_stack.addWidget(self.section_editor)

        center_layout.addWidget(self.center_title_label)
        center_layout.addWidget(self.center_description_label)
        center_layout.addWidget(self.content_stack, 1)

        main_splitter.addWidget(tree_panel)
        main_splitter.addWidget(self.center_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 960])

        root.addWidget(main_splitter, 1)

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close
        )
        configure_save_cancel_buttons(self._button_box)
        configure_close_button(self._button_box)
        self._save_btn = self._button_box.button(QDialogButtonBox.StandardButton.Save)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._save_current_section)
        self._button_box.rejected.connect(self.reject)
        root.addWidget(self._button_box)

        self.knowledge_tree.reload_tree(include_inactive=True)
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

    def _show_hint(self) -> None:
        self._current_process_id = ""
        self._current_section_id = ""
        self._save_btn.setEnabled(False)
        self.section_editor.clear_section()
        self.center_title_label.setText(self.windowTitle())
        self.center_description_label.setText(
            f"Vyberte {PROCESS_TERM_CRITERION.lower()} ve stromu řídicích procesů vlevo."
        )
        self.center_description_label.setVisible(True)
        self.overview_widget.show_process(None)
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        self._current_process_id = node.process_id
        self._current_section_id = ""
        self._save_btn.setEnabled(False)
        self.section_editor.clear_section()

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

    def _on_criterion_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        criterion = node.section
        if criterion is None:
            self._show_hint()
            return

        self._current_process_id = node.process_id
        self._current_section_id = node.node_id

        section_label = str(criterion.get("nazev") or "").strip()
        process_def = audit_knowledge_service.get_process_by_id(node.process_id)
        process_label = process_def.nazev if process_def else node.process_label

        self.center_title_label.setText(f"{process_label} → {section_label}")
        self.center_description_label.setVisible(False)

        fresh_section = audit_knowledge_service.get_criterion(node.process_id, node.node_id)
        if fresh_section is None:
            fresh_section = criterion

        self.section_editor.load_section(
            process_id=node.process_id,
            section_id=node.node_id,
            section=fresh_section,
        )
        self._save_btn.setEnabled(True)
        self.content_stack.setCurrentIndex(self._PAGE_SECTION)

    def _save_current_section(self) -> list[str]:
        if not self.section_editor.has_section():
            return []

        process_id = self.section_editor.process_id
        section_id = self.section_editor.section_id
        errors = audit_knowledge_editor_service.save_section_metadata(
            process_id,
            section_id,
            self.section_editor.section_metadata(),
        )
        if errors:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "\n".join(errors),
            )
            return errors

        self.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        if not self.knowledge_tree.select_node(process_id, section_id):
            self._show_hint()
            return []

        refreshed = audit_knowledge_service.get_criterion(
            process_id,
            section_id,
            ensure=False,
        )
        if refreshed is None:
            self._show_hint()
            return []

        self.section_editor.load_section(
            process_id=process_id,
            section_id=section_id,
            section=refreshed,
        )
        process_def = audit_knowledge_service.get_process_by_id(process_id, ensure=False)
        process_label = process_def.nazev if process_def else process_id
        self.center_title_label.setText(
            f"{process_label} → {str(refreshed.get('nazev') or section_id).strip()}"
        )
        return []
