"""Editor znalostí prověrek BOZP — strom vlevo, editace vpravo (jako editor auditora)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.knowledge_editor_actions import (
    clear_save_status,
    confirm_close_with_unsaved_changes,
    create_knowledge_editor_footer,
    show_save_status,
    show_unsaved_status,
)
from moduly.proverky.constants import (
    AREA_PANEL_LEFT_WIDTH,
    KNOWLEDGE_EDITOR_SELECT_SECTION_HINT,
    KNOWLEDGE_EDITOR_USER_COPY_HINT,
    KNOWLEDGE_EDITOR_WINDOW_TITLE,
)
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KnowledgeTreeNode,
    proverky_knowledge_service,
)
from moduly.proverky.ui.bozp_knowledge_tree_widget import BozpKnowledgeTreeWidget
from moduly.proverky.ui.proverky_knowledge_section_edit_dialog import (
    ProverkyKnowledgeSectionEditDialog,
)


class ProverkyKnowledgeEditorDialog(QDialog):
    """Editor metodiky prověrek — QSplitter: strom oblastí/sekcí + editační panel."""

    def __init__(
        self,
        parent=None,
        *,
        area_id: str | None = None,
        section_id: str | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_EDITOR_WINDOW_TITLE)
        configure_resizable_form_dialog(self, width=1180, height=760, min_width=640, min_height=420)

        self._initial_area_id = (area_id or "").strip()
        self._initial_section_id = (section_id or "").strip()
        self._current_area_id = ""
        self._current_section_id = ""
        self._modified = False
        self._section_editor: ProverkyKnowledgeSectionEditDialog | None = None
        self._drafts: dict[tuple[str, str], dict] = {}
        self._pending_control_point_id: str | None = None

        proverky_knowledge_service.ensure_catalogs()

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        hint_label = QLabel(KNOWLEDGE_EDITOR_USER_COPY_HINT)
        hint_label.setObjectName("InfoText")
        hint_label.setWordWrap(True)
        root.addWidget(hint_label)

        main_splitter = QSplitter()

        self.knowledge_tree = BozpKnowledgeTreeWidget()
        self.knowledge_tree.section_selected.connect(self._on_section_selected)
        self.knowledge_tree.area_selected.connect(self._on_area_selected)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.addWidget(self.knowledge_tree, 1)
        tree_panel.setMinimumWidth(AREA_PANEL_LEFT_WIDTH)
        tree_panel.setMaximumWidth(AREA_PANEL_LEFT_WIDTH)

        self.center_panel = QFrame()
        self.center_panel.setObjectName("ModulePanel")
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(12, 12, 12, 12)
        center_layout.setSpacing(8)

        self.center_title_label = QLabel()
        self.center_title_label.setObjectName("SectionTitle")
        self.center_title_label.setWordWrap(True)

        self._empty_state_label = QLabel(KNOWLEDGE_EDITOR_SELECT_SECTION_HINT)
        self._empty_state_label.setObjectName("InfoText")
        self._empty_state_label.setWordWrap(True)
        self._empty_state_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._empty_state_label.setAlignment(
            self._empty_state_label.alignment() | Qt.AlignmentFlag.AlignTop
        )

        self._editor_host = QWidget()
        self._editor_host_layout = QVBoxLayout(self._editor_host)
        self._editor_host_layout.setContentsMargins(0, 0, 0, 0)
        self._editor_host_layout.setSpacing(0)
        self._editor_host.setVisible(False)

        center_layout.addWidget(self.center_title_label)
        center_layout.addWidget(self._empty_state_label, 1)
        center_layout.addWidget(self._editor_host, 1)

        main_splitter.addWidget(tree_panel)
        main_splitter.addWidget(self.center_panel)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([AREA_PANEL_LEFT_WIDTH, 960])
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
        footer_host = QWidget()
        footer_host.setLayout(footer)
        footer_host.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        root.addWidget(footer_host, 0)

        self.knowledge_tree.reload_tree(include_inactive=True)
        if self._initial_area_id:
            self._apply_initial_context(
                self._initial_area_id,
                self._initial_section_id or None,
            )
        else:
            self._show_hint()

    def navigate_to_control_point(
        self,
        area_id: str,
        section_id: str,
        control_point_id: str,
    ) -> bool:
        """Přepne editor na sekci a otevře zvolený kontrolní bod."""
        area_id = str(area_id or "").strip()
        section_id = str(section_id or "").strip()
        control_point_id = str(control_point_id or "").strip()
        if not area_id or not section_id or not control_point_id:
            return False

        if (
            self._current_area_id == area_id
            and self._current_section_id == section_id
            and self._section_editor is not None
        ):
            return self._section_editor.select_control_point(control_point_id)

        self._pending_control_point_id = control_point_id
        if not self.knowledge_tree.select_node(area_id, section_id):
            self._pending_control_point_id = None
            QMessageBox.information(
                self,
                self.windowTitle(),
                (
                    "Sekci s podobnou kontrolní otázkou se nepodařilo otevřít.\n\n"
                    f"Oblast: {area_id}\nSekce: {section_id}\n"
                    f"Kontrolní bod: {control_point_id}"
                ),
            )
            return False
        return True

    def _apply_pending_control_point(self) -> None:
        pending = self._pending_control_point_id
        self._pending_control_point_id = None
        if not pending or self._section_editor is None:
            return
        self._section_editor.select_control_point(pending)

    def _apply_initial_context(self, area_id: str, section_id: str | None) -> None:
        if section_id and self.knowledge_tree.select_node(area_id, section_id):
            return
        if self.knowledge_tree.select_node(area_id):
            return
        self._show_hint()

    def _can_save_current(self) -> bool:
        return self._section_editor is not None

    def _update_action_buttons(self) -> None:
        enabled = self._can_save_current()
        self._apply_btn.setEnabled(enabled)
        self._save_close_btn.setEnabled(enabled or self._has_unsaved_changes())

    def _mark_modified(self) -> None:
        self._modified = True
        show_unsaved_status(self._status_label)
        self._update_action_buttons()

    def _mark_saved(self) -> None:
        self._modified = False
        if self._section_editor is not None:
            self._section_editor._mark_saved()

    def _has_unsaved_changes(self) -> bool:
        if self._drafts:
            return True
        if self._section_editor is not None and self._section_editor.is_modified:
            return True
        return False

    def _refresh_dirty_status(self) -> None:
        if self._has_unsaved_changes():
            self._modified = True
            show_unsaved_status(self._status_label)
        else:
            self._modified = False
        self._update_action_buttons()

    def _stash_current_section_draft(self) -> None:
        if self._section_editor is None or not self._section_editor.is_modified:
            return
        key = (self._section_editor.area_id, self._section_editor.section_id)
        self._drafts[key] = self._section_editor.capture_draft()
        self._modified = True

    def _discard_all_drafts(self) -> None:
        self._drafts.clear()
        self._mark_saved()
        clear_save_status(self._status_label)
        self._update_action_buttons()

    def _persist_draft(self, area_id: str, section_id: str, payload: dict) -> bool:
        if not str(payload.get("nazev") or "").strip():
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"Sekce „{section_id}“: název sekce je povinný.",
            )
            return False
        saved, errors = proverky_knowledge_service.save_section(
            area_id,
            section_id,
            payload,
        )
        if errors:
            QMessageBox.warning(self, self.windowTitle(), "\n".join(errors))
            return False
        return bool(saved)

    def _save_all_pending(self) -> bool:
        self._stash_current_section_draft()
        pending = list(self._drafts.items())
        if not pending and self._section_editor is not None:
            if not self._section_editor.persist_changes():
                return False
            self._mark_saved()
            return True

        for (area_id, section_id), payload in pending:
            if not self._persist_draft(area_id, section_id, payload):
                return False

        self._drafts.clear()
        if self._section_editor is not None:
            area_id = self._section_editor.area_id
            section_id = self._section_editor.section_id
            self._reload_section_editor(area_id, section_id, mark_clean=True)
        else:
            self._mark_saved()
        return True

    def _apply_changes(self) -> None:
        if self._save_current():
            if self._has_unsaved_changes():
                show_unsaved_status(self._status_label)
            else:
                show_save_status(self._status_label)

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

    def _show_hint(self, *, message: str | None = None) -> None:
        self._stash_current_section_draft()
        self._current_area_id = ""
        self._current_section_id = ""
        self._clear_section_editor()
        self.center_title_label.setText(self.windowTitle())
        self._empty_state_label.setText(message or KNOWLEDGE_EDITOR_SELECT_SECTION_HINT)
        self._empty_state_label.setVisible(True)
        self._editor_host.setVisible(False)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            clear_save_status(self._status_label)

    def _clear_section_editor(self) -> None:
        if self._section_editor is None:
            return
        self._editor_host_layout.removeWidget(self._section_editor)
        self._section_editor.deleteLater()
        self._section_editor = None

    def _on_area_selected(self, node: KnowledgeTreeNode) -> None:
        self._stash_current_section_draft()
        self._clear_section_editor()
        self._current_area_id = node.area_id
        self._current_section_id = ""
        self.center_title_label.setText(node.label)
        self._empty_state_label.setText(
            f"Oblast „{node.label}“ — vyberte sekci ve stromu pro editaci metodiky."
        )
        self._empty_state_label.setVisible(True)
        self._editor_host.setVisible(False)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            clear_save_status(self._status_label)
        self._update_action_buttons()

    def _on_section_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        self._stash_current_section_draft()

        section = node.section
        if section is None:
            self._show_hint()
            return

        draft_key = (node.area_id, node.node_id)
        draft = self._drafts.pop(draft_key, None)
        try:
            editor = ProverkyKnowledgeSectionEditDialog(
                self,
                area_id=node.area_id,
                section_id=node.node_id,
                embedded=True,
                section_data=draft,
                initially_modified=draft is not None,
            )
        except ValueError as exc:
            if draft is not None:
                self._drafts[draft_key] = draft
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            self._show_hint()
            return

        self._clear_section_editor()
        self._section_editor = editor
        editor.content_modified.connect(self._mark_modified)
        editor.content_saved.connect(self._on_section_content_saved)
        self._editor_host_layout.addWidget(editor, 1)

        self._current_area_id = node.area_id
        self._current_section_id = node.node_id
        self.center_title_label.setText(f"{node.area_label} → {node.label}")
        self._empty_state_label.setVisible(False)
        self._editor_host.setVisible(True)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            clear_save_status(self._status_label)
        self._update_action_buttons()
        self._apply_pending_control_point()

    def _on_section_content_saved(self) -> None:
        key = None
        if self._section_editor is not None:
            key = (self._section_editor.area_id, self._section_editor.section_id)
        if key is not None:
            self._drafts.pop(key, None)
        self._refresh_dirty_status()
        if not self._has_unsaved_changes():
            show_save_status(self._status_label)

    def _reload_section_editor(
        self,
        area_id: str,
        section_id: str,
        *,
        mark_clean: bool,
    ) -> bool:
        try:
            editor = ProverkyKnowledgeSectionEditDialog(
                self,
                area_id=area_id,
                section_id=section_id,
                embedded=True,
            )
        except ValueError:
            return False

        self._clear_section_editor()
        self._section_editor = editor
        editor.content_modified.connect(self._mark_modified)
        editor.content_saved.connect(self._on_section_content_saved)
        self._editor_host_layout.addWidget(editor, 1)
        self._current_area_id = area_id
        self._current_section_id = section_id
        area = proverky_knowledge_service.get_area_by_id(area_id)
        section = proverky_knowledge_service.get_section(area_id, section_id) or {}
        area_label = area.nazev if area else area_id
        section_label = str(section.get("nazev") or section_id)
        self.center_title_label.setText(f"{area_label} → {section_label}")
        self._empty_state_label.setVisible(False)
        self._editor_host.setVisible(True)
        if mark_clean:
            self._mark_saved()
        self._refresh_dirty_status()
        self._update_action_buttons()
        return True

    def _save_current(self) -> bool:
        if self._section_editor is None:
            return False
        area_id = self._section_editor.area_id
        section_id = self._section_editor.section_id
        if not self._section_editor.persist_changes():
            return False

        self._drafts.pop((area_id, section_id), None)

        self.knowledge_tree.reload_tree(include_inactive=True)
        self.knowledge_tree.blockSignals(True)
        try:
            if not self.knowledge_tree.select_node(area_id, section_id):
                self._show_hint()
                return False
        finally:
            self.knowledge_tree.blockSignals(False)

        if not self._reload_section_editor(area_id, section_id, mark_clean=True):
            return True
        return True
