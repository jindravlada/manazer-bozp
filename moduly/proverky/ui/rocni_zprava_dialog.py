from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from core.widgets.dialog_utils import create_close_box


class RocniZpravaDialog(QDialog):
    """Kostra dialogu roční závěrečné zprávy."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Roční závěrečná zpráva")
        self.resize(720, 480)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Roční závěrečná zpráva pro vedení, odbory a auditory bude doplněna "
            "v další fázi vývoje.\n"
            "Systém zde agreguje výsledky prověrek za kalendářní rok."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()

        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
