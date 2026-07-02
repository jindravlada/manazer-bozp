"""Dialog editoru metodiky auditora."""

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.knowledge_editor_actions import (
    clear_save_status,
    confirm_close_with_unsaved_changes,
    create_knowledge_editor_footer,
    show_save_status,
)
from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_ADD_PROCESS_BUTTON,
    KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT,
    KNOWLEDGE_EDITOR_USER_COPY_HINT,
    KNOWLEDGE_EDITOR_WINDOW_TITLE,
    PROCESS_PANEL_LEFT_WIDTH,
    PROCESS_TERM_CRITERION,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget
from moduly.audity.ui.audity_knowledge_process_create_dialog import (
    AudityKnowledgeProcessCreateDialog,
)
from moduly.audity.ui.audity_knowledge_process_editor_widget import (
    AudityKnowledgeProcessEditorWidget,
)
from moduly.audity.ui.audity_knowledge_section_dialog import AudityKnowledgeSectionDialog
from moduly.audity.ui.audity_knowledge_section_editor_widget import (
    AudityKnowledgeSectionEditorWidget,
)


class AudityKnowledgeEditorDialog(QDialog):
    """Editor metodiky auditora — editace metadat procesu a oblastí ověření."""

    _PAGE_HINT = 0
    _PAGE_PROCESS = 1
    _PAGE_SECTION = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_EDITOR_WINDOW_TITLE)

        self._current_process_id = ""
        self._current_section_id = ""
        self._modified = False

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

        tree_toolbar = QHBoxLayout()
        self._add_process_btn = QPushButton(KNOWLEDGE_EDITOR_ADD_PROCESS_BUTTON)
        self._add_process_btn.clicked.connect(self._add_process)
        tree_toolbar.addWidget(self._add_process_btn)
        tree_toolbar.addStretch()
        tree_layout.addLayout(tree_toolbar)

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
        self.process_editor = AudityKnowledgeProcessEditorWidget()
        self.process_editor.add_section_requested.connect(self._add_section)
        self.process_editor.content_modified.connect(self._mark_modified)
        self.content_stack.addWidget(self.process_editor)
        self.section_editor = AudityKnowledgeSectionEditorWidget()
        self.section_editor.content_modified.connect(self._mark_modified)
        self.section_editor.content_saved.connect(self._mark_saved)
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

        footer, self._apply_btn, self._save_close_btn, self._close_btn, self._status_label = (
            create_knowledge_editor_footer(
                on_apply=self._apply_changes,
                on_save_close=self._save_and_close,
                on_close=self._request_close,
                apply_enabled=False,
            )
        )
        root.addLayout(footer)

        self.knowledge_tree.reload_tree(include_inactive=True)
        self._show_hint()

    def _can_save_current(self) -> bool:
        index = self.content_stack.currentIndex()
        if index == self._PAGE_PROCESS:
            return self.process_editor.has_process()
        if index == self._PAGE_SECTION:
            return self.section_editor.has_section()
        return False

    def _update_action_buttons(self) -> None:
        enabled = self._can_save_current()
        self._apply_btn.setEnabled(enabled)
        self._save_close_btn.setEnabled(enabled)

    def _mark_modified(self) -> None:
        self._modified = True

    def _mark_saved(self) -> None:
        self._modified = False

    def _apply_changes(self) -> None:
        if self._save_current():
            self._mark_saved()
            show_save_status(self._status_label)

    def _save_and_close(self) -> None:
        if not self._can_save_current():
            self._modified = False
            self.accept()
            return
        if self._save_current():
            self._mark_saved()
            self.accept()

    def _request_close(self) -> None:
        if self._confirm_close():
            super().reject()

    def _confirm_close(self) -> bool:
        if not self._modified:
            return True

        decision = confirm_close_with_unsaved_changes(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._can_save_current():
                return False
            if not self._save_current():
                return False
            self._mark_saved()
        else:
            self._mark_saved()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_close():
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._confirm_close():
            super().reject()

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

    def _clear_save_status(self) -> None:
        clear_save_status(self._status_label)

    def _show_hint(self) -> None:
        self._clear_save_status()
        self._mark_saved()
        self._current_process_id = ""
        self._current_section_id = ""
        self._update_action_buttons()
        self.process_editor.clear_process()
        self.section_editor.clear_section()
        self.center_title_label.setText(self.windowTitle())
        self.center_description_label.setText(
            f"Vyberte řídicí proces nebo {PROCESS_TERM_CRITERION.lower()} ve stromu vlevo."
        )
        self.center_description_label.setVisible(True)
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        self._clear_save_status()
        self._current_process_id = node.process_id
        self._current_section_id = ""
        self.section_editor.clear_section()

        metadata = audit_knowledge_service.get_process_metadata(
            node.process_id,
            ensure=False,
        )
        if metadata is None:
            self._update_action_buttons()
            self.process_editor.clear_process()
            self.center_title_label.setText(node.process_label)
            self.center_description_label.setText(
                "Proces nemá načtený soubor znalostí."
            )
            self.center_description_label.setVisible(True)
            self.content_stack.setCurrentIndex(self._PAGE_HINT)
            return

        self.process_editor.load_process(
            process_id=node.process_id,
            metadata=metadata,
        )
        self._mark_saved()
        self.center_title_label.setText(str(metadata.get("nazev") or node.process_label))
        self.center_description_label.setVisible(False)
        self.content_stack.setCurrentIndex(self._PAGE_PROCESS)
        self._update_action_buttons()

    def _on_criterion_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        self._clear_save_status()
        criterion = node.section
        if criterion is None:
            self._show_hint()
            return

        self._current_process_id = node.process_id
        self._current_section_id = node.node_id
        self.process_editor.clear_process()

        section_label = str(criterion.get("nazev") or "").strip()
        process_def = audit_knowledge_service.get_process_by_id(node.process_id, ensure=False)
        process_label = process_def.nazev if process_def else node.process_label

        fresh_section = audit_knowledge_service.get_criterion(
            node.process_id,
            node.node_id,
            ensure=False,
        )
        if fresh_section is None:
            fresh_section = criterion

        self.section_editor.load_section(
            process_id=node.process_id,
            section_id=node.node_id,
            section=fresh_section,
        )
        self._mark_saved()
        self.center_title_label.setText(f"{process_label} → {section_label}")
        self.center_description_label.setVisible(False)
        self.content_stack.setCurrentIndex(self._PAGE_SECTION)
        self._update_action_buttons()

    def _save_current(self) -> bool:
        if self.content_stack.currentIndex() == self._PAGE_PROCESS:
            return self._save_current_process()
        if self.content_stack.currentIndex() == self._PAGE_SECTION:
            return self._save_current_section()
        return False

    def _save_current_process(self) -> bool:
        if not self.process_editor.has_process():
            return False

        process_id = self.process_editor.process_id
        errors = audit_knowledge_editor_service.save_process_metadata(
            process_id,
            self.process_editor.process_metadata(),
        )
        if errors:
            self._clear_save_status()
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "\n".join(errors),
            )
            return False

        self.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        self.knowledge_tree.blockSignals(True)
        try:
            if not self.knowledge_tree.select_node(process_id):
                self._show_hint()
                return False

            refreshed = audit_knowledge_service.get_process_metadata(process_id, ensure=False)
            if refreshed is None:
                self._show_hint()
                return False

            self.process_editor.load_process(process_id=process_id, metadata=refreshed)
            self.center_title_label.setText(str(refreshed.get("nazev") or process_id))
        finally:
            self.knowledge_tree.blockSignals(False)

        return True

    def _add_section(self) -> None:
        if not self.process_editor.has_process():
            return

        process_id = self.process_editor.process_id
        process = audit_knowledge_service.get_process_by_id(process_id, ensure=False)
        if process is None or not process.soubor_znalosti:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Proces '{process_id}' nemá soubor znalostí.",
            )
            return

        knowledge = audit_knowledge_service.load_process_knowledge(process, ensure=False)
        if knowledge is None:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Soubor znalostí procesu '{process_id}' nelze načíst.",
            )
            return

        existing_ids = audit_knowledge_service.collect_section_ids(
            knowledge.get("sekce") or []
        )
        default_poradi = audit_knowledge_editor_service.suggest_next_section_poradi(
            process_id
        )

        dialog = AudityKnowledgeSectionDialog(
            existing_ids=existing_ids,
            default_poradi=default_poradi,
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeSectionDialog.DialogCode.Accepted:
            return

        section_id, errors = audit_knowledge_editor_service.create_section(
            process_id,
            dialog.section_payload(),
        )
        if errors:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "\n".join(errors),
            )
            return
        if not section_id:
            return

        self.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        if not self.knowledge_tree.select_node(process_id, section_id):
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Oblast '{section_id}' byla vytvořena, ale ve stromu se nepodařilo obnovit výběr.",
            )
            return

    def _save_current_section(self) -> bool:
        if not self.section_editor.has_section():
            return False

        process_id = self.section_editor.process_id
        section_id = self.section_editor.section_id
        errors = audit_knowledge_editor_service.save_section_metadata(
            process_id,
            section_id,
            self.section_editor.section_metadata(),
        )
        if errors:
            self._clear_save_status()
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "\n".join(errors),
            )
            return False

        self.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        self.knowledge_tree.blockSignals(True)
        try:
            if not self.knowledge_tree.select_node(process_id, section_id):
                self._show_hint()
                return False

            refreshed = audit_knowledge_service.get_criterion(
                process_id,
                section_id,
                ensure=False,
            )
            if refreshed is None:
                self._show_hint()
                return False

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
        finally:
            self.knowledge_tree.blockSignals(False)

        return True

    def _add_process(self) -> None:
        existing_ids = audit_knowledge_editor_service.collect_process_ids()
        default_poradi = audit_knowledge_editor_service.suggest_next_process_poradi()

        dialog = AudityKnowledgeProcessCreateDialog(
            existing_ids=existing_ids,
            default_poradi=default_poradi,
            parent=self,
        )
        if dialog.exec() != AudityKnowledgeProcessCreateDialog.DialogCode.Accepted:
            return

        process_id, errors = audit_knowledge_editor_service.create_process(
            dialog.process_payload(),
        )
        if errors:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "\n".join(errors),
            )
            return
        if not process_id:
            return

        self.knowledge_tree.reload_tree(include_inactive=True, ensure=False)
        if not self.knowledge_tree.select_node(process_id):
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Proces '{process_id}' byl vytvořen, ale ve stromu se nepodařilo obnovit výběr.",
            )
            return
