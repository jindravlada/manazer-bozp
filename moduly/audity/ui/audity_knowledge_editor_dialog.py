"""Dialog editoru metodiky auditora."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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

from core.widgets.dialog_utils import configure_resizable_form_dialog

from core.export.methodology_questions_pdf import (
    METHODOLOGY_PDF_DIALOG_TITLE,
    METHODOLOGY_PDF_FAILED,
    METHODOLOGY_PDF_SAVED,
    choose_pdf_save_path,
    default_audit_pdf_filename,
    write_methodology_questions_pdf,
)
from core.widgets.knowledge_editor_actions import (
    KNOWLEDGE_EDITOR_EXPORT_PDF_BUTTON,
    clear_save_status,
    confirm_close_with_unsaved_changes,
    create_knowledge_editor_footer,
    show_save_status,
    show_unsaved_status,
)
from moduly.audity.constants import (
    KNOWLEDGE_EDITOR_ADD_PROCESS_BUTTON,
    KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT,
    KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_HINT,
    KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_LABEL,
    KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_NONE,
    KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL,
    KNOWLEDGE_EDITOR_USER_COPY_HINT,
    KNOWLEDGE_EDITOR_WINDOW_TITLE,
    PROCESS_PANEL_LEFT_WIDTH,
    SYSTEM_AUDIT_WORKPLACE_INVALID_COMBO_SUFFIX,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    is_auditable_workplace,
    list_auditable_workplaces,
)
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode, audit_knowledge_service
from moduly.audity.sluzby.audit_methodology_questions_export import (
    build_audit_methodology_questions_document_from_editor,
)
from moduly.audity.sluzby.system_audit_workplace_service import (
    SystemAuditWorkplaceError,
    system_audit_workplace_service,
)
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
from moduly.nastaveni.sluzby.settings_service import settings_service

logger = logging.getLogger(__name__)


class AudityKnowledgeEditorDialog(QDialog):
    """Editor metodiky auditora — editace metadat procesu a oblastí ověření."""

    _PAGE_PROCESS = 0
    _PAGE_SECTION = 1

    def __init__(
        self,
        parent=None,
        *,
        process_id: str | None = None,
        criterion_id: str | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_EDITOR_WINDOW_TITLE)
        configure_resizable_form_dialog(self, width=1180, height=760, min_width=640, min_height=420)

        self._initial_process_id = (process_id or "").strip()
        self._initial_criterion_id = (criterion_id or "").strip()
        self._current_process_id = ""
        self._current_section_id = ""
        self._modified = False
        self._current_dirty = False
        self._system_workplace_dirty = False
        self._saved_system_workplace_id: int | None = None
        self._process_drafts: dict[str, dict] = {}
        self._section_drafts: dict[tuple[str, str], dict] = {}

        audit_knowledge_editor_service.ensure_user_catalogs()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        hint_label = QLabel(KNOWLEDGE_EDITOR_USER_COPY_HINT)
        hint_label.setObjectName("InfoText")
        hint_label.setWordWrap(True)
        root.addWidget(hint_label)

        system_row = QHBoxLayout()
        system_row.setSpacing(8)
        system_label = QLabel(KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_LABEL)
        self._system_workplace_combo = QComboBox()
        self._system_workplace_combo.setMinimumWidth(260)
        self._system_workplace_combo.currentIndexChanged.connect(
            self._on_system_workplace_changed
        )
        self._unclassified_count_label = QLabel(
            KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL.format(count=0)
        )
        self._unclassified_count_label.setObjectName("InfoText")
        system_row.addWidget(system_label)
        system_row.addWidget(self._system_workplace_combo, 1)
        system_row.addWidget(self._unclassified_count_label)
        root.addLayout(system_row)

        system_hint = QLabel(KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_HINT)
        system_hint.setObjectName("InfoText")
        system_hint.setWordWrap(True)
        root.addWidget(system_hint)

        self._catalog_error_label = QLabel()
        self._catalog_error_label.setObjectName("WarningText")
        self._catalog_error_label.setWordWrap(True)
        self._catalog_error_label.setVisible(False)
        root.addWidget(self._catalog_error_label)

        main_splitter = QSplitter()

        self.knowledge_tree = AuditKnowledgeTreeWidget()
        self.knowledge_tree.criterion_selected.connect(self._on_criterion_selected)
        self.knowledge_tree.process_selected.connect(self._on_process_selected)
        self.knowledge_tree.catalog_error.connect(self._show_catalog_error)

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

        self._empty_state_label = QLabel(KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT)
        self._empty_state_label.setObjectName("InfoText")
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._empty_state_label.setAlignment(
            self._empty_state_label.alignment() | Qt.AlignmentFlag.AlignTop
        )

        self.content_stack = QStackedWidget()
        self.content_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.process_editor = AudityKnowledgeProcessEditorWidget()
        self.process_editor.add_section_requested.connect(self._add_section)
        self.process_editor.content_modified.connect(self._mark_modified)
        self.content_stack.addWidget(self.process_editor)
        self.section_editor = AudityKnowledgeSectionEditorWidget()
        self.section_editor.content_modified.connect(self._mark_modified)
        self.section_editor.content_saved.connect(self._on_section_content_saved)
        self.section_editor.question_kinds_modified.connect(
            self._on_assertion_kinds_modified
        )
        self.content_stack.addWidget(self.section_editor)

        center_layout.addWidget(self.center_title_label)
        center_layout.addWidget(self.center_description_label)
        center_layout.addWidget(self._empty_state_label, 1)
        center_layout.addWidget(self.content_stack, 1)

        main_splitter.addWidget(tree_panel)
        main_splitter.addWidget(self.center_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([PROCESS_PANEL_LEFT_WIDTH, 960])
        main_splitter.setMinimumHeight(0)
        main_splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        root.addWidget(main_splitter, 1)

        footer, self._apply_btn, self._save_close_btn, self._close_btn, self._status_label = (
            create_knowledge_editor_footer(
                on_apply=self._apply_changes,
                on_save_close=self._save_and_close,
                on_close=self._request_close,
                apply_enabled=False,
            )
        )
        self._export_pdf_btn = QPushButton(KNOWLEDGE_EDITOR_EXPORT_PDF_BUTTON)
        self._export_pdf_btn.clicked.connect(self._export_questions_pdf)
        footer.insertWidget(0, self._export_pdf_btn)
        footer_host = QWidget()
        footer_host.setLayout(footer)
        footer_host.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        root.addWidget(footer_host, 0)

        self._load_system_workplace_combo()
        self._refresh_unclassified_count()
        self.knowledge_tree.reload_tree(include_inactive=True)
        if self.knowledge_tree.catalog_error_message:
            self._show_catalog_error(self.knowledge_tree.catalog_error_message)
        if self._initial_process_id:
            self._apply_initial_context(
                self._initial_process_id,
                self._initial_criterion_id or None,
            )
        else:
            self._show_hint()

    def _export_questions_pdf(self) -> None:
        try:
            document = build_audit_methodology_questions_document_from_editor(self)
            path = choose_pdf_save_path(
                self,
                default_filename=default_audit_pdf_filename(document.created_on),
            )
            if not path:
                return
            write_methodology_questions_pdf(document, path)
        except Exception:
            logger.exception("Export přehledu auditních otázek do PDF selhal.")
            QMessageBox.warning(
                self,
                METHODOLOGY_PDF_DIALOG_TITLE,
                METHODOLOGY_PDF_FAILED,
            )
            return
        QMessageBox.information(
            self,
            METHODOLOGY_PDF_DIALOG_TITLE,
            METHODOLOGY_PDF_SAVED,
        )

    def _load_system_workplace_combo(self) -> None:
        self._system_workplace_combo.blockSignals(True)
        self._system_workplace_combo.clear()
        self._system_workplace_combo.addItem(KNOWLEDGE_EDITOR_SYSTEM_WORKPLACE_NONE, None)
        for workplace in list_auditable_workplaces():
            self._system_workplace_combo.addItem(workplace.name, workplace.id)
        saved_id = system_audit_workplace_service.get_system_audit_workplace_id()
        self._saved_system_workplace_id = saved_id
        index = self._system_workplace_combo.findData(saved_id)
        if index < 0 and saved_id is not None:
            # Neplatné uložené nastavení: zobrazit, ale nepřepisovat ani nemazat.
            workplace = settings_service.get_workplace_by_id(saved_id)
            label = (
                str(workplace.name).strip()
                if workplace is not None and str(workplace.name or "").strip()
                else f"#{saved_id}"
            )
            if workplace is not None and not is_auditable_workplace(workplace):
                label = f"{label}{SYSTEM_AUDIT_WORKPLACE_INVALID_COMBO_SUFFIX}"
            elif workplace is None:
                label = f"{label}{SYSTEM_AUDIT_WORKPLACE_INVALID_COMBO_SUFFIX}"
            self._system_workplace_combo.addItem(label, saved_id)
            index = self._system_workplace_combo.findData(saved_id)
        if index < 0:
            index = 0
        self._system_workplace_combo.setCurrentIndex(index)
        self._system_workplace_dirty = False
        self._system_workplace_combo.blockSignals(False)

    def _pending_system_workplace_id(self) -> int | None:
        value = self._system_workplace_combo.currentData()
        if value in (None, ""):
            return None
        return int(value)

    def _on_system_workplace_changed(self, _index: int = 0) -> None:
        pending = self._pending_system_workplace_id()
        self._system_workplace_dirty = pending != self._saved_system_workplace_id
        if self._system_workplace_dirty:
            self._mark_modified()
        else:
            self._refresh_dirty_status()

    def _refresh_unclassified_count(self) -> None:
        count = audit_knowledge_service.count_unclassified_active_assertions(
            ensure=False,
            kind_overrides=self.section_editor.pending_question_kind_overrides(),
        )
        self._unclassified_count_label.setText(
            KNOWLEDGE_EDITOR_UNCLASSIFIED_COUNT_LABEL.format(count=count)
        )

    def _on_assertion_kinds_modified(self) -> None:
        # Druh v tabulce jen pracovní kopie — ne stashuj metadata sekce.
        self._refresh_unclassified_count()
        self._refresh_dirty_status()
        if self._has_unsaved_changes():
            show_unsaved_status(self._status_label)

    def _show_catalog_error(self, message: str) -> None:
        self._catalog_error_label.setText(message)
        self._catalog_error_label.setVisible(True)

    def _can_save_current(self) -> bool:
        index = self.content_stack.currentIndex()
        if index == self._PAGE_PROCESS:
            return self.process_editor.has_process()
        if index == self._PAGE_SECTION:
            return self.section_editor.has_section()
        return False

    def _update_action_buttons(self) -> None:
        can_act = self._can_save_current() or self._has_unsaved_changes()
        self._apply_btn.setEnabled(can_act)
        self._save_close_btn.setEnabled(can_act)

    def _mark_modified(self) -> None:
        self._modified = True
        self._current_dirty = True
        show_unsaved_status(self._status_label)
        self._update_action_buttons()

    def _mark_saved(self) -> None:
        self._modified = False
        self._current_dirty = False
        self._system_workplace_dirty = False

    def _has_unsaved_changes(self) -> bool:
        return (
            self._current_dirty
            or self._system_workplace_dirty
            or self.section_editor.has_pending_assertion_kinds()
            or bool(self._process_drafts)
            or bool(self._section_drafts)
        )

    def _refresh_dirty_status(self) -> None:
        if self._has_unsaved_changes():
            self._modified = True
            show_unsaved_status(self._status_label)
        else:
            self._modified = False
            self._current_dirty = False
        self._update_action_buttons()

    def _stash_current_editor(self) -> None:
        if not self._current_dirty:
            return
        index = self.content_stack.currentIndex()
        if index == self._PAGE_PROCESS and self.process_editor.has_process():
            self._process_drafts[self.process_editor.process_id] = (
                self.process_editor.process_metadata()
            )
        elif index == self._PAGE_SECTION and self.section_editor.has_section():
            key = (self.section_editor.process_id, self.section_editor.section_id)
            self._section_drafts[key] = self.section_editor.section_metadata()
        self._current_dirty = False
        self._modified = True

    def _discard_all_drafts(self) -> None:
        self._process_drafts.clear()
        self._section_drafts.clear()
        self.section_editor.discard_pending_assertion_kinds()
        self._load_system_workplace_combo()
        if (
            self.content_stack.isVisible()
            and self.content_stack.currentIndex() == self._PAGE_SECTION
            and self.section_editor.has_section()
        ):
            process_id = self.section_editor.process_id
            section_id = self.section_editor.section_id
            refreshed = audit_knowledge_service.get_criterion(
                process_id,
                section_id,
                ensure=False,
            )
            if refreshed is not None:
                self.section_editor.load_section(
                    process_id=process_id,
                    section_id=section_id,
                    section=refreshed,
                )
        self._mark_saved()
        self._refresh_unclassified_count()
        clear_save_status(self._status_label)
        self._update_action_buttons()

    def _flush_pending_assertion_kinds(self) -> bool:
        if not self.section_editor.has_pending_assertion_kinds():
            return True
        errors = self.section_editor.flush_pending_assertion_kinds()
        if errors:
            self._clear_save_status()
            QMessageBox.warning(self, self.windowTitle(), "\n".join(errors))
            return False
        self._refresh_unclassified_count()
        return True

    def _save_system_workplace_if_needed(self) -> bool:
        if not self._system_workplace_dirty:
            return True
        from moduly.audity.sluzby.audit_method_v2_backup_service import (
            AuditMethodV2BackupError,
        )

        pending = self._pending_system_workplace_id()
        try:
            system_audit_workplace_service.set_system_audit_workplace_id(pending)
        except (SystemAuditWorkplaceError, AuditMethodV2BackupError) as exc:
            self._clear_save_status()
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        self._saved_system_workplace_id = pending
        self._system_workplace_dirty = False
        return True

    def _save_all_pending(self) -> bool:
        self._stash_current_editor()
        if not self._save_system_workplace_if_needed():
            return False
        if not self._flush_pending_assertion_kinds():
            return False
        for process_id, metadata in list(self._process_drafts.items()):
            errors = audit_knowledge_editor_service.save_process_metadata(
                process_id,
                metadata,
            )
            if errors:
                self._clear_save_status()
                QMessageBox.warning(self, self.windowTitle(), "\n".join(errors))
                return False
            self._process_drafts.pop(process_id, None)

        for (process_id, section_id), metadata in list(self._section_drafts.items()):
            errors = audit_knowledge_editor_service.save_section_metadata(
                process_id,
                section_id,
                metadata,
            )
            if errors:
                self._clear_save_status()
                QMessageBox.warning(self, self.windowTitle(), "\n".join(errors))
                return False
            self._section_drafts.pop((process_id, section_id), None)

        # Obnovit aktuálně zobrazenou položku z disku (bez signálů stromu).
        if self.content_stack.isVisible():
            if (
                self.content_stack.currentIndex() == self._PAGE_PROCESS
                and self.process_editor.has_process()
            ):
                process_id = self.process_editor.process_id
                refreshed = audit_knowledge_service.get_process_metadata(
                    process_id,
                    ensure=False,
                )
                if refreshed is not None:
                    self.process_editor.load_process(
                        process_id=process_id,
                        metadata=refreshed,
                    )
            elif (
                self.content_stack.currentIndex() == self._PAGE_SECTION
                and self.section_editor.has_section()
            ):
                process_id = self.section_editor.process_id
                section_id = self.section_editor.section_id
                refreshed = audit_knowledge_service.get_criterion(
                    process_id,
                    section_id,
                    ensure=False,
                )
                if refreshed is not None:
                    self.section_editor.load_section(
                        process_id=process_id,
                        section_id=section_id,
                        section=refreshed,
                    )

        self._refresh_unclassified_count()
        self._mark_saved()
        return True

    def _on_section_content_saved(self) -> None:
        # Seznamy v sekci se ukládají okamžitě; metadata může zůstat dirty.
        self._refresh_unclassified_count()
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            show_save_status(self._status_label)

    def _apply_changes(self) -> None:
        if not self._save_system_workplace_if_needed():
            return
        if not self._flush_pending_assertion_kinds():
            return
        if self._can_save_current():
            if not self._save_current():
                return
        elif self._process_drafts or self._section_drafts:
            if not self._save_all_pending():
                return
        self._current_dirty = False
        self._refresh_unclassified_count()
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            show_save_status(self._status_label)
        else:
            show_unsaved_status(self._status_label)

    def _save_and_close(self) -> None:
        if not self._has_unsaved_changes() and not self._can_save_current():
            self._modified = False
            self.accept()
            return
        if self._save_all_pending():
            self._mark_saved()
            self.accept()

    def _request_close(self) -> None:
        if self._confirm_close():
            super().reject()

    def _confirm_close(self) -> bool:
        if not self._has_unsaved_changes():
            return True

        decision = confirm_close_with_unsaved_changes(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._save_all_pending():
                return False
            self._mark_saved()
        else:
            self._discard_all_drafts()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_close():
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._confirm_close():
            super().reject()

    def _apply_initial_context(
        self,
        process_id: str,
        criterion_id: str | None = None,
    ) -> None:
        if criterion_id:
            if self.knowledge_tree.select_node(process_id, criterion_id):
                return

        if self.knowledge_tree.select_node(process_id):
            return

        self._show_hint()

    def _show_content_page(self, page_index: int) -> None:
        self._empty_state_label.setVisible(False)
        self.content_stack.setVisible(True)
        self.content_stack.setCurrentIndex(page_index)

    def _clear_save_status(self) -> None:
        clear_save_status(self._status_label)

    def _show_hint(self, *, message: str | None = None) -> None:
        self._stash_current_editor()
        self._current_process_id = ""
        self._current_section_id = ""
        self.process_editor.clear_process()
        self.section_editor.clear_section()
        self.center_title_label.setText(self.windowTitle())
        self.center_description_label.clear()
        self.center_description_label.setVisible(False)
        self._empty_state_label.setText(
            message or KNOWLEDGE_EDITOR_SELECT_PROCESS_HINT
        )
        self._empty_state_label.setVisible(True)
        self.content_stack.setVisible(False)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            self._clear_save_status()

    def _on_process_selected(self, node: KnowledgeTreeNode) -> None:
        self._stash_current_editor()
        self._current_process_id = node.process_id
        self._current_section_id = ""
        self.section_editor.clear_section()

        draft = self._process_drafts.pop(node.process_id, None)
        metadata = draft
        if metadata is None:
            metadata = audit_knowledge_service.get_process_metadata(
                node.process_id,
                ensure=False,
            )
        if metadata is None:
            self._update_action_buttons()
            self.process_editor.clear_process()
            self.center_title_label.setText(node.process_label)
            self._show_hint(message="Proces nemá načtený soubor znalostí.")
            return

        self.process_editor.load_process(
            process_id=node.process_id,
            metadata=metadata,
        )
        self._current_dirty = draft is not None
        self.center_title_label.setText(str(metadata.get("nazev") or node.process_label))
        self.center_description_label.setVisible(False)
        self._show_content_page(self._PAGE_PROCESS)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            self._clear_save_status()
        self._update_action_buttons()

    def _on_criterion_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        self._stash_current_editor()
        criterion = node.section
        if criterion is None:
            self._show_hint()
            return

        self._current_process_id = node.process_id
        self._current_section_id = node.node_id
        self.process_editor.clear_process()

        process_def = audit_knowledge_service.get_process_by_id(node.process_id, ensure=False)
        process_label = process_def.nazev if process_def else node.process_label

        fresh_section = audit_knowledge_service.get_criterion(
            node.process_id,
            node.node_id,
            ensure=False,
        )
        if fresh_section is None:
            fresh_section = criterion

        draft_key = (node.process_id, node.node_id)
        draft = self._section_drafts.pop(draft_key, None)
        if draft is not None:
            fresh_section = dict(fresh_section)
            fresh_section.update(draft)

        section_label = str(fresh_section.get("nazev") or "").strip()

        self.section_editor.load_section(
            process_id=node.process_id,
            section_id=node.node_id,
            section=fresh_section,
        )
        self._current_dirty = draft is not None
        self.center_title_label.setText(f"{process_label} → {section_label}")
        self.center_description_label.setVisible(False)
        self._show_content_page(self._PAGE_SECTION)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            self._clear_save_status()
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

        self._process_drafts.pop(process_id, None)
        self._current_dirty = False

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
        self._stash_current_editor()
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
        self._section_drafts.pop((process_id, section_id), None)
        self._current_dirty = False

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
        self._stash_current_editor()
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
