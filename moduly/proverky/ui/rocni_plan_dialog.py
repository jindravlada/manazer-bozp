from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

from core.widgets.dialog_utils import create_close_box


class RocniPlanDialog(QDialog):
    """Kostra dialogu ročního plánu prověrek."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Roční plán prověrek BOZP")
        self.resize(720, 480)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Roční plán pokrytí pracovišť bude doplněn v další fázi vývoje.\n"
            "Zde vznikne přehled plánovaných a provedených prověrek za rok."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()

        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
