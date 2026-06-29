from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class MuInvestigationSourcePanel(QFrame):
    open_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModulePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        header = QLabel("Zdroj šetření")
        header.setObjectName("SectionTitle")

        self.source_type_label = QLabel()
        self.source_type_label.setObjectName("InfoText")

        self.source_record_label = QLabel()
        self.source_record_label.setObjectName("InfoText")
        self.source_record_label.setWordWrap(True)

        self.open_button = QPushButton("Otevřít")

        layout.addWidget(header)
        layout.addWidget(self.source_type_label)
        layout.addWidget(self.source_record_label)
        layout.addSpacing(6)
        layout.addWidget(self.open_button)

        self.open_button.clicked.connect(self.open_requested.emit)
        self.setVisible(False)

    def set_content(
        self,
        source_type_label: str,
        source_record_label: str,
        *,
        can_open: bool,
        open_button_text: str = "Otevřít",
    ) -> None:
        has_binding = bool(source_type_label.strip() and source_record_label.strip())
        self.setVisible(has_binding)
        if not has_binding:
            return

        self.source_type_label.setText(source_type_label)
        self.source_record_label.setText(source_record_label)
        self.open_button.setText(open_button_text)
        self.open_button.setVisible(can_open)
