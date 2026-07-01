from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from moduly.audity.constants import MODULE_NAME


class AudityPage(QWidget):
    """Dočasná kostra hlavní stránky – plné UI bude doplněno v další fázi."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        label = QLabel(f"{MODULE_NAME} – uživatelské rozhraní bude doplněno v další fázi.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
