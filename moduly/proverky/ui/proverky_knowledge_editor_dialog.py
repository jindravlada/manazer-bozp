"""Editor znalostí prověrek BOZP — strom vlevo, editace vpravo (jako editor auditora)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
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
        self._save_close_btn.setEnabled(enabled)

    def _mark_modified(self) -> None:
        self._modified = True
        show_unsaved_status(self._status_label)

    def _mark_saved(self) -> None:
        self._modified = False
        if self._section_editor is not None:
            self._section_editor._mark_saved()

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
        if not self._modified and (
            self._section_editor is None or not self._section_editor.is_modified
        ):
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

    def _show_hint(self, *, message: str | None = None) -> None:
        clear_save_status(self._status_label)
        self._mark_saved()
        self._current_area_id = ""
        self._current_section_id = ""
        self._clear_section_editor()
        self.center_title_label.setText(self.windowTitle())
        self._empty_state_label.setText(message or KNOWLEDGE_EDITOR_SELECT_SECTION_HINT)
        self._empty_state_label.setVisible(True)
        self._editor_host.setVisible(False)
        self._update_action_buttons()

    def _clear_section_editor(self) -> None:
        if self._section_editor is None:
            return
        self._editor_host_layout.removeWidget(self._section_editor)
        self._section_editor.deleteLater()
        self._section_editor = None

    def _on_area_selected(self, node: KnowledgeTreeNode) -> None:
        if not self._prepare_selection_change():
            self._restore_tree_selection()
            return
        self._show_hint(
            message=(
                f"Oblast „{node.label}“ — vyberte sekci ve stromu pro editaci metodiky."
            )
        )
        self._current_area_id = node.area_id
        self.center_title_label.setText(node.label)

    def _on_section_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return
        if not self._prepare_selection_change():
            self._restore_tree_selection()
            return

        clear_save_status(self._status_label)
        section = node.section
        if section is None:
            self._show_hint()
            return

        try:
            editor = ProverkyKnowledgeSectionEditDialog(
                self,
                area_id=node.area_id,
                section_id=node.node_id,
                embedded=True,
            )
        except ValueError as exc:
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
        self._mark_saved()
        self.center_title_label.setText(f"{node.area_label} → {node.label}")
        self._empty_state_label.setVisible(False)
        self._editor_host.setVisible(True)
        self._update_action_buttons()

    def _on_section_content_saved(self) -> None:
        self._mark_saved()
        show_save_status(self._status_label)

    def _prepare_selection_change(self) -> bool:
        if self._section_editor is None:
            return True
        if not self._section_editor.is_modified and not self._modified:
            return True
        decision = confirm_close_with_unsaved_changes(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._save_current():
                return False
            self._mark_saved()
            return True
        self._mark_saved()
        return True

    def _restore_tree_selection(self) -> None:
        if self._current_area_id and self._current_section_id:
            self.knowledge_tree.blockSignals(True)
            try:
                self.knowledge_tree.select_node(
                    self._current_area_id,
                    self._current_section_id,
                )
            finally:
                self.knowledge_tree.blockSignals(False)

    def _save_current(self) -> bool:
        if self._section_editor is None:
            return False
        area_id = self._section_editor.area_id
        section_id = self._section_editor.section_id
        if not self._section_editor.persist_changes():
            return False

        self.knowledge_tree.reload_tree(include_inactive=True)
        self.knowledge_tree.blockSignals(True)
        try:
            if not self.knowledge_tree.select_node(area_id, section_id):
                self._show_hint()
                return False
        finally:
            self.knowledge_tree.blockSignals(False)

        # Znovu načíst editor se uloženými daty (včetně řídicího procesu).
        try:
            editor = ProverkyKnowledgeSectionEditDialog(
                self,
                area_id=area_id,
                section_id=section_id,
                embedded=True,
            )
        except ValueError:
            return True

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
        self._update_action_buttons()
        return True
