from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_BUTTON_LABEL,
    METHODOLOGY_PANEL_STRETCH,
    PROCESS_NOT_IMPLEMENTED_TEXT,
    PROCESS_PANEL_LEFT_WIDTH,
    PROCESS_TERM_CRITERION,
    TAB_DOCUMENTACE,
    TAB_TEREN,
    TERRAIN_CHECKLIST_BUTTON_LABEL,
    TERRAIN_CHECKLIST_DIALOG_TITLE,
    TERRAIN_CHECKLIST_REQUIRES_SAVED,
    TERRAIN_CHECKLIST_TOOLTIP,
    WORK_PANEL_STRETCH,
)
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.audit_terrain_checklist_service import (
    audit_terrain_checklist_service,
)
from moduly.audity.ui.audit_knowledge_tree_widget import AuditKnowledgeTreeWidget
from moduly.audity.ui.audit_methodology_panel_widget import AuditMethodologyPanelWidget
from moduly.audity.ui.audit_process_knowledge_widget import (
    AuditProcessKnowledgeWidget,
    AuditProcessOverviewWidget,
)
from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog


class AuditProcessesWidget(QWidget):
    """Záložka Dokumentace / Terén — strom | pracovní plocha | metodická podpora."""

    _PAGE_HINT = 0
    _PAGE_PLACEHOLDER = 1
    _PAGE_OVERVIEW = 2
    _PAGE_KNOWLEDGE = 3

    def __init__(
        self,
        parent=None,
        *,
        verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
    ):
        super().__init__(parent)

        self._verification_type = (
            VERIFICATION_TYPE_TERRAIN
            if verification_type == VERIFICATION_TYPE_TERRAIN
            else VERIFICATION_TYPE_DOCUMENTATION
        )
        self._tab_title = (
            TAB_TEREN if self._verification_type == VERIFICATION_TYPE_TERRAIN else TAB_DOCUMENTACE
        )
        self._audit_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._catalog_error_label = QLabel()
        self._catalog_error_label.setObjectName("WarningText")
        self._catalog_error_label.setWordWrap(True)
        self._catalog_error_label.setVisible(False)
        layout.addWidget(self._catalog_error_label)

        main_splitter = QSplitter()

        self.tree_panel = QWidget()
        tree_layout = QVBoxLayout(self.tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)

        self.knowledge_tree = AuditKnowledgeTreeWidget()
        self.knowledge_tree.criterion_selected.connect(self._on_criterion_selected)
        self.knowledge_tree.process_selected.connect(self._on_process_selected)
        self.knowledge_tree.catalog_error.connect(self._show_catalog_error)
        tree_layout.addWidget(self.knowledge_tree, 1)

        self.tree_panel.setMinimumWidth(PROCESS_PANEL_LEFT_WIDTH)
        self.tree_panel.setMaximumWidth(PROCESS_PANEL_LEFT_WIDTH)

        self.work_methodology_splitter = QSplitter()

        self.center_panel = QFrame()
        self.center_panel.setObjectName("ModulePanel")
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(8)

        self._current_process_id = ""
        self._current_process_purpose = ""
        self._current_process_knowledge: dict | None = None
        self._current_criterion_id = ""
        self._current_criterion_label = ""
        self._planned_process_ids: set[str] | None = None
        self._on_verification_type_changed = None

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self.center_title_label = QLabel()
        self.center_title_label.setObjectName("SectionTitle")
        self.center_title_label.setWordWrap(True)

        self.edit_knowledge_btn = QPushButton(KNOWLEDGE_EDITOR_BUTTON_LABEL)
        self.edit_knowledge_btn.clicked.connect(self._open_knowledge_editor)

        header_row.addWidget(self.center_title_label, 1)
        header_row.addWidget(
            self.edit_knowledge_btn,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
        )

        self.checklist_btn: QPushButton | None = None
        if self._verification_type == VERIFICATION_TYPE_TERRAIN:
            self.checklist_btn = QPushButton(TERRAIN_CHECKLIST_BUTTON_LABEL)
            self.checklist_btn.setToolTip(TERRAIN_CHECKLIST_TOOLTIP)
            self.checklist_btn.setEnabled(False)
            self.checklist_btn.clicked.connect(self._export_terrain_checklist)
            header_row.addWidget(
                self.checklist_btn,
                0,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            )

        self.center_description_label = QLabel()
        self.center_description_label.setObjectName("InfoText")
        self.center_description_label.setWordWrap(True)

        self.content_stack = QStackedWidget()
        self.content_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.content_stack.addWidget(self._build_hint_page())
        self.content_stack.addWidget(self._build_placeholder_page())
        self.overview_widget = AuditProcessOverviewWidget()
        self.content_stack.addWidget(self.overview_widget)

        self.methodology_panel = AuditMethodologyPanelWidget()
        self.knowledge_widget = AuditProcessKnowledgeWidget(
            self.methodology_panel,
            verification_filter=self._verification_type,
        )
        self.knowledge_widget.verification_type_changed.connect(
            self._emit_verification_type_changed
        )
        self.content_stack.addWidget(self.knowledge_widget)

        center_layout.addLayout(header_row)
        center_layout.addWidget(self.center_description_label)
        center_layout.addSpacing(4)
        center_layout.addWidget(self.content_stack, 1)

        self.work_methodology_splitter.addWidget(self.center_panel)
        self.work_methodology_splitter.addWidget(self.methodology_panel)
        self.work_methodology_splitter.setStretchFactor(0, WORK_PANEL_STRETCH)
        self.work_methodology_splitter.setStretchFactor(1, METHODOLOGY_PANEL_STRETCH)
        self.work_methodology_splitter.setSizes([640, 320])

        main_splitter.addWidget(self.tree_panel)
        main_splitter.addWidget(self.work_methodology_splitter)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 960])

        layout.addWidget(main_splitter, 1)

        self.reload_processes()

    def set_on_verification_type_changed(self, callback) -> None:
        self._on_verification_type_changed = callback

    def _emit_verification_type_changed(self) -> None:
        if self._on_verification_type_changed is not None:
            self._on_verification_type_changed()

    def _show_catalog_error(self, message: str) -> None:
        self._catalog_error_label.setText(message)
        self._catalog_error_label.setVisible(True)

    def _clear_catalog_error(self) -> None:
        self._catalog_error_label.clear()
        self._catalog_error_label.setVisible(False)

    def set_audit_id(self, audit_id: int | None) -> None:
        self._audit_id = audit_id
        self.knowledge_widget.set_audit_id(audit_id)
        if self.checklist_btn is not None:
            self.checklist_btn.setEnabled(audit_id is not None)

    def _export_terrain_checklist(self) -> None:
        if self._audit_id is None:
            QMessageBox.information(
                self,
                TERRAIN_CHECKLIST_DIALOG_TITLE,
                TERRAIN_CHECKLIST_REQUIRES_SAVED,
            )
            return
        audit = audit_service.get_by_id(self._audit_id)
        if audit is None:
            QMessageBox.warning(
                self,
                TERRAIN_CHECKLIST_DIALOG_TITLE,
                "Audit nebyl nalezen.",
            )
            return
        try:
            audit_terrain_checklist_service.open_for_audit(
                audit,
                process_ids=self._planned_process_ids,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                TERRAIN_CHECKLIST_DIALOG_TITLE,
                f"Terénní checklist se nepodařilo vygenerovat.\n\n{exc}",
            )

    def set_planned_process_ids(self, process_ids: tuple[str, ...] | list[str]) -> None:
        self._planned_process_ids = set(process_ids) if process_ids else None
        self.reload_processes()
        if self._planned_process_ids:
            first_process_id = next(iter(sorted(self._planned_process_ids)))
            self.knowledge_tree.select_node(first_process_id)

    def set_on_finding_saved(self, callback) -> None:
        self.knowledge_widget.set_on_finding_saved(callback)

    def set_deferred_edits(self, deferred_edits) -> None:
        self.knowledge_widget.set_deferred_edits(deferred_edits)

    def set_on_deferred_dirty(self, callback) -> None:
        self.knowledge_widget.set_on_deferred_dirty(callback)

    def refresh_findings_display(self) -> None:
        self.knowledge_widget.refresh_findings_display()

    def _open_knowledge_editor(self) -> None:
        process_id = self._current_process_id or None
        criterion_id = self._current_criterion_id or None
        exec_maximized(
            AudityKnowledgeEditorDialog(
                self,
                process_id=process_id,
                criterion_id=criterion_id,
            )
        )
        self._refresh_after_knowledge_edit()

    def _refresh_after_knowledge_edit(self) -> None:
        process_id = self._current_process_id
        criterion_id = self._current_criterion_id
        self.knowledge_tree.reload_tree(process_ids=self._planned_process_ids)
        if process_id and criterion_id:
            self.knowledge_tree.select_node(process_id, criterion_id)
        elif process_id:
            self.knowledge_tree.select_node(process_id)
        else:
            self._show_hint()
        self.refresh_findings_display()

    def reload_processes(self) -> None:
        self._clear_catalog_error()
        self.knowledge_tree.reload_tree(process_ids=self._planned_process_ids)
        if self.knowledge_tree.catalog_error_message:
            self._show_catalog_error(self.knowledge_tree.catalog_error_message)
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
        self._current_process_knowledge = None
        self._current_criterion_id = ""
        self._current_criterion_label = ""
        self.center_title_label.setText(self._tab_title)
        self.center_description_label.setText(
            f"Vyberte {PROCESS_TERM_CRITERION.lower()} ve stromu řídicích procesů vlevo."
        )
        self.center_description_label.setVisible(True)
        self.knowledge_widget.clear_criterion()
        self.overview_widget.show_process(None)
        self.methodology_panel.show_hint()
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        self._current_process_id = node.process_id
        self._current_criterion_id = ""
        self._current_criterion_label = ""

        process_def = audit_knowledge_service.get_process_by_id(node.process_id)
        self.center_title_label.setText(node.process_label)

        if process_def and process_def.ucel_procesu:
            self._current_process_purpose = process_def.ucel_procesu
        else:
            self._current_process_purpose = ""

        if process_def and process_def.popis:
            self.center_description_label.setText(process_def.popis)
            self.center_description_label.setVisible(True)
        else:
            self.center_description_label.setText(
                f"Vyberte {PROCESS_TERM_CRITERION.lower()} pod tímto procesem."
            )
            self.center_description_label.setVisible(True)

        self.knowledge_widget.clear_criterion()
        if process_def and process_def.has_knowledge_file:
            knowledge = audit_knowledge_service.load_process_knowledge(process_def)
            self._current_process_knowledge = knowledge
            self.overview_widget.show_process(knowledge)
            self.methodology_panel.show_process(knowledge)
            self.content_stack.setCurrentIndex(self._PAGE_OVERVIEW)
        else:
            self._current_process_knowledge = None
            self.overview_widget.show_process(None)
            self.methodology_panel.show_hint("Pro tento proces zatím není metodická podpora.")
            self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)

        self.overview_widget.scroll_to_top()

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

        if not self._current_process_purpose or self._current_process_knowledge is None:
            process_def = audit_knowledge_service.get_process_by_id(node.process_id)
            if process_def is not None:
                self._current_process_purpose = process_def.ucel_procesu
                if process_def.has_knowledge_file:
                    self._current_process_knowledge = audit_knowledge_service.load_process_knowledge(
                        process_def
                    )

        section_label = str(criterion.get("nazev") or "").strip()
        self.center_title_label.setText(section_label)

        section_popis = str(criterion.get("popis") or "").strip()
        cil_overeni = audit_knowledge_service.get_text_field(criterion, "cil_overeni")
        if cil_overeni:
            self.center_description_label.setText(cil_overeni)
            self.center_description_label.setVisible(True)
        elif section_popis:
            self.center_description_label.setText(section_popis)
            self.center_description_label.setVisible(True)
        else:
            self.center_description_label.setVisible(False)

        self.knowledge_widget.show_criterion(
            criterion,
            process_id=node.process_id,
            process_label=node.process_label,
            process_purpose=self._current_process_purpose,
            criterion_label=section_label,
            process_knowledge=self._current_process_knowledge,
        )
        self.content_stack.setCurrentIndex(self._PAGE_KNOWLEDGE)
