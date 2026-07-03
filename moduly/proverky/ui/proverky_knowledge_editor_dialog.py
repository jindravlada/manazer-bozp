from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.proverky.constants import (
    KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
    KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.ui.proverky_knowledge_section_edit_dialog import (
    ProverkyKnowledgeSectionEditDialog,
)


class ProverkyKnowledgeEditorDialog(QDialog):
    """Výběr oblasti a sekce pro editaci znalostní karty."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Editor znalostí prověrek")
        self.resize(520, 180)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._area_combo = QComboBox()
        self._section_combo = QComboBox()
        form.addRow("Oblast:", self._area_combo)
        form.addRow("Sekce:", self._section_combo)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        open_btn = QPushButton("Upravit")
        close_btn = QPushButton("Zavřít")
        buttons.addWidget(open_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._area_combo.currentIndexChanged.connect(self._reload_sections)
        open_btn.clicked.connect(self._open_editor)
        close_btn.clicked.connect(self.reject)

        self._load_areas()
        self._select_defaults()

    def _load_areas(self) -> None:
        self._area_combo.blockSignals(True)
        self._area_combo.clear()

        for area in proverky_knowledge_service.get_areas(include_inactive=True):
            if not area.has_knowledge_file:
                continue
            self._area_combo.addItem(area.nazev, area.id)

        self._area_combo.blockSignals(False)
        self._reload_sections()

    def _select_defaults(self) -> None:
        area_index = self._area_combo.findData(KNOWLEDGE_EDITOR_DEFAULT_AREA_ID)
        if area_index >= 0:
            self._area_combo.setCurrentIndex(area_index)

        section_index = self._section_combo.findData(KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID)
        if section_index >= 0:
            self._section_combo.setCurrentIndex(section_index)

    def _reload_sections(self) -> None:
        self._section_combo.clear()
        area_id = str(self._area_combo.currentData() or "").strip()
        if not area_id:
            return

        for section in proverky_knowledge_service.list_sections(area_id, include_inactive=True):
            section_id = str(section.get("id") or "").strip()
            nazev = str(section.get("nazev") or section_id)
            if section_id:
                self._section_combo.addItem(nazev, section_id)

    def _open_editor(self) -> None:
        area_id = str(self._area_combo.currentData() or "").strip()
        section_id = str(self._section_combo.currentData() or "").strip()
        if not area_id or not section_id:
            QMessageBox.information(self, self.windowTitle(), "Vyberte oblast a sekci.")
            return

        try:
            dialog = ProverkyKnowledgeSectionEditDialog(
                self,
                area_id=area_id,
                section_id=section_id,
            )
        except ValueError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return

        if exec_maximized(dialog) == QDialog.DialogCode.Accepted:
            self.accept()
