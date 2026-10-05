from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.testy.constants import MODULE_NAME, PAGE_SUBTITLE


class TestyPage(QWidget):
    """Úvodní stránka modulu Testy."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel(MODULE_NAME)
        title.setObjectName("PageTitle")

        subtitle = QLabel(PAGE_SUBTITLE)
        subtitle.setObjectName("InfoText")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
