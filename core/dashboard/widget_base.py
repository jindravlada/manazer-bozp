from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class DashboardCard(QFrame):
    def __init__(self, title: str, value: str = "—", subtitle: str = ""):
        super().__init__()
        self.setObjectName("DashboardCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DashboardCardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("DashboardCardValue")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("DashboardCardSubtitle")
        self.subtitle_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.subtitle_label)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(value)
        self.subtitle_label.setText(subtitle)


class DashboardPanel(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("DashboardPanel")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 14, 18, 14)
        self.layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DashboardPanelTitle")
        self.layout.addWidget(self.title_label)
