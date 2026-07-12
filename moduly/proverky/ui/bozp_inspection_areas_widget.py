from PySide6.QtCore import Qt
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

from core.widgets.dialog_utils import exec_maximized
from moduly.proverky.constants import (
    AREA_NOT_IMPLEMENTED_TEXT,
    KNOWLEDGE_CONTROL_PROCEDURE_BUTTON_LABEL,
    KNOWLEDGE_EDIT_FROM_CARD_LABEL,
)
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KnowledgeTreeNode,
    proverky_knowledge_service,
)
from moduly.proverky.ui.bozp_area_knowledge_widget import BozpAreaKnowledgeWidget
from moduly.proverky.ui.bozp_knowledge_tree_widget import BozpKnowledgeTreeWidget
from moduly.proverky.ui.proverky_control_procedure_dialog import ProverkyControlProcedureDialog
from moduly.proverky.ui.proverky_knowledge_editor_dialog import ProverkyKnowledgeEditorDialog


class BozpInspectionAreasWidget(QWidget):
    """Záložka Kontrolované oblasti — znalostní strom a pracovní karta."""

    _PAGE_HINT = 0
    _PAGE_PLACEHOLDER = 1
    _PAGE_KNOWLEDGE = 2

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()

        self.knowledge_tree = BozpKnowledgeTreeWidget()
        self.knowledge_tree.section_selected.connect(self._on_section_selected)
        self.knowledge_tree.area_selected.connect(self._on_area_selected)

        self.detail_panel = QFrame()
        self.detail_panel.setObjectName("ModulePanel")
        detail_layout = QVBoxLayout(self.detail_panel)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        self._current_area_id = ""
        self._current_section_id = ""
        self._current_section_label = ""
        self._procedure_dialog: ProverkyControlProcedureDialog | None = None

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)

        self.area_title_label = QLabel()
        self.area_title_label.setObjectName("SectionTitle")
        self.area_title_label.setWordWrap(True)

        self.edit_knowledge_btn = QPushButton(KNOWLEDGE_EDIT_FROM_CARD_LABEL)
        self.edit_knowledge_btn.clicked.connect(self._open_knowledge_editor_from_card)

        self.control_procedure_btn = QPushButton(KNOWLEDGE_CONTROL_PROCEDURE_BUTTON_LABEL)
        self.control_procedure_btn.clicked.connect(self._open_control_procedure_dialog)
        self.control_procedure_btn.setEnabled(False)

        header_row.addWidget(self.area_title_label, 1)
        header_row.addWidget(self.control_procedure_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        header_row.addWidget(self.edit_knowledge_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        self.area_description_label = QLabel()
        self.area_description_label.setObjectName("InfoText")
        self.area_description_label.setWordWrap(True)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self._build_hint_page())
        self.content_stack.addWidget(self._build_placeholder_page())
        self.knowledge_widget = BozpAreaKnowledgeWidget()
        self.content_stack.addWidget(self.knowledge_widget)

        detail_layout.addLayout(header_row)
        detail_layout.addWidget(self.area_description_label)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(self.content_stack, 1)

        splitter.addWidget(self.knowledge_tree)
        splitter.addWidget(self.detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        self.reload_areas()

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.knowledge_widget.set_inspection_id(inspection_id)

    def set_on_finding_saved(self, callback) -> None:
        self.knowledge_widget.set_on_finding_saved(callback)

    def refresh_findings_display(self) -> None:
        self.knowledge_widget.refresh_findings_display()

    def reload_areas(self) -> None:
        self.knowledge_tree.reload_tree()
        self._show_hint()

    def _build_hint_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Vyberte sekci ve stromu znalostí vlevo.")
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(AREA_NOT_IMPLEMENTED_TEXT)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return page

    def _open_knowledge_editor_from_card(self) -> None:
        if self._current_area_id and self._current_section_id:
            dialog = ProverkyKnowledgeEditorDialog(
                self,
                area_id=self._current_area_id,
                section_id=self._current_section_id,
            )
            if exec_maximized(dialog) == QDialog.DialogCode.Accepted:
                self._refresh_after_knowledge_edit()
            return

        exec_maximized(ProverkyKnowledgeEditorDialog(self))

    def _open_control_procedure_dialog(self) -> None:
        if not self._current_area_id or not self._current_section_id:
            QMessageBox.information(
                self,
                KNOWLEDGE_CONTROL_PROCEDURE_BUTTON_LABEL,
                "Vyberte sekci ve stromu znalostí vlevo.",
            )
            return

        section = proverky_knowledge_service.get_section(
            self._current_area_id,
            self._current_section_id,
        )
        if section is None:
            QMessageBox.warning(
                self,
                KNOWLEDGE_CONTROL_PROCEDURE_BUTTON_LABEL,
                "Postup kontroly se nepodařilo načíst.",
            )
            return

        if self._procedure_dialog is not None and self._procedure_dialog.isVisible():
            self._procedure_dialog.set_section(
                section,
                section_label=self._current_section_label,
            )
            self._procedure_dialog.raise_()
            self._procedure_dialog.activateWindow()
            return

        dialog = ProverkyControlProcedureDialog(
            section,
            section_label=self._current_section_label,
            parent=self,
        )
        dialog.destroyed.connect(lambda: setattr(self, "_procedure_dialog", None))
        self._procedure_dialog = dialog
        dialog.show()

    def _refresh_after_knowledge_edit(self) -> None:
        area_id = self._current_area_id
        section_id = self._current_section_id
        self.knowledge_tree.reload_tree()
        if area_id and section_id:
            self.knowledge_tree.select_node(area_id, section_id)

        if (
            self._procedure_dialog is not None
            and self._procedure_dialog.isVisible()
            and area_id
            and section_id
        ):
            section = proverky_knowledge_service.get_section(area_id, section_id)
            if section is not None:
                self._procedure_dialog.set_section(
                    section,
                    section_label=self._current_section_label,
                )

    def _show_hint(self) -> None:
        self._current_area_id = ""
        self._current_section_id = ""
        self._current_section_label = ""
        self.control_procedure_btn.setEnabled(False)
        self.area_title_label.setText("Kontrolované oblasti")
        self.area_description_label.setText("Vyberte sekci ve stromu znalostí vlevo.")
        self.area_description_label.setVisible(True)
        self.knowledge_widget.clear_section()
        self.content_stack.setCurrentIndex(self._PAGE_HINT)

    def _on_area_selected(self, node: KnowledgeTreeNode) -> None:
        self._current_area_id = node.area_id
        self._current_section_id = ""
        self._current_section_label = ""
        self.control_procedure_btn.setEnabled(False)

        area_def = proverky_knowledge_service.get_area_by_id(node.area_id)

        self.area_title_label.setText(node.area_label)
        if area_def and area_def.popis:
            self.area_description_label.setText(area_def.popis)
            self.area_description_label.setVisible(True)
        else:
            self.area_description_label.setText("Vyberte sekci pod touto oblastí.")
            self.area_description_label.setVisible(True)

        self.knowledge_widget.clear_section()
        if area_def and area_def.has_knowledge_file and node.children:
            self.content_stack.setCurrentIndex(self._PAGE_HINT)
        else:
            self.content_stack.setCurrentIndex(self._PAGE_PLACEHOLDER)

    def _on_section_selected(self, node: KnowledgeTreeNode | None) -> None:
        if node is None:
            return

        section = node.section
        if section is None:
            self._show_hint()
            return

        self._current_area_id = node.area_id
        self._current_section_id = node.node_id
        self._current_section_label = str(section.get("nazev") or "").strip()
        self.control_procedure_btn.setEnabled(True)

        self.area_title_label.setText(node.area_label)
        section_label = str(section.get("nazev") or "").strip()
        section_popis = str(section.get("popis") or "").strip()
        if section_popis:
            self.area_description_label.setText(section_popis)
            self.area_description_label.setVisible(True)
        else:
            self.area_description_label.setVisible(False)

        self.knowledge_widget.show_section(
            section,
            area_id=node.area_id,
            area_label=node.area_label,
            section_label=section_label,
        )
        self.content_stack.setCurrentIndex(self._PAGE_KNOWLEDGE)
