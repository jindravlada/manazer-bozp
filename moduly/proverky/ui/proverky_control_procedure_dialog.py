from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_close_button, create_close_box
from moduly.proverky.constants import (
    KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT,
    KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service


class ProverkyControlProcedureDialog(QDialog):
    """Nemodální okno s doporučeným postupem kontroly."""

    def __init__(self, section: dict, *, section_label: str = "", parent=None):
        super().__init__(parent)

        self.setWindowTitle(KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        if section_label:
            self.setWindowTitle(f"{KNOWLEDGE_CONTROL_PROCEDURE_DIALOG_TITLE} – {section_label}")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(12)
        scroll.setWidget(self._content_host)

        root_layout.addWidget(scroll, 1)

        buttons = create_close_box(self)
        configure_close_button(buttons)
        buttons.rejected.connect(self.close)
        root_layout.addWidget(buttons)

        self.set_section(section)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.showMaximized()

    def set_section(self, section: dict) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        intro = str(section.get("postup_kontroly_uvod") or "").strip()
        if intro:
            intro_label = QLabel(intro)
            intro_label.setWordWrap(True)
            self._content_layout.addWidget(intro_label)

        items = proverky_knowledge_service.get_active_items(section.get("postup_kontroly"))
        if not items:
            empty = QLabel(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT)
            empty.setObjectName("InfoText")
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
        else:
            for index, item in enumerate(items, start=1):
                text = str(item.get("text") or "—").strip() or "—"
                step_label = QLabel(f"{index}. {text}")
                step_label.setWordWrap(True)
                self._content_layout.addWidget(step_label)

        self._content_layout.addStretch()
