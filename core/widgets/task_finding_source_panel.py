from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout


class TaskFindingSourcePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModulePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        source_header = QLabel("Zdroj:")
        source_header.setObjectName("SectionTitle")

        self.source_label = QLabel()
        self.source_label.setObjectName("InfoText")
        self.source_label.setWordWrap(True)

        description_header = QLabel("Popis zjištění")
        description_header.setObjectName("SectionTitle")

        self.description_label = QLabel()
        self.description_label.setObjectName("InfoText")
        self.description_label.setWordWrap(True)

        self.open_button = QPushButton("Otevřít zdrojový záznam")

        layout.addWidget(source_header)
        layout.addWidget(self.source_label)
        layout.addSpacing(6)
        layout.addWidget(description_header)
        layout.addWidget(self.description_label)
        layout.addSpacing(8)
        layout.addWidget(self.open_button)

    def set_content(self, source_label: str, description: str) -> None:
        self.source_label.setText(source_label)
        self.description_label.setText(description.strip() or "—")
