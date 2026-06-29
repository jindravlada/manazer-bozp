from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout


class ControlSummaryCard(QFrame):
    def __init__(
        self,
        title: str,
        background: str,
        border: str,
        tooltip: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setToolTip(tooltip)

        self.setStyleSheet(
            f"""
            ControlSummaryCard {{
                background-color: {background};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #424242; font-size: 12px;")
        self.title_label.setToolTip(tooltip)
        if not title:
            self.title_label.hide()

        self.value_label = QLabel("0")
        self.value_label.setStyleSheet("color: #212121; font-size: 28px; font-weight: bold;")
        self.value_label.setToolTip(tooltip)

        self.detail_label = QLabel("")
        self.detail_label.setStyleSheet("color: #616161; font-size: 11px;")
        self.detail_label.setToolTip(tooltip)
        self.detail_label.setVisible(False)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.detail_label)

    def set_value(self, value: str, detail: str = ""):
        self.value_label.setText(value)
        self.detail_label.setText(detail)
        self.detail_label.setVisible(bool(detail))


class ControlDoneSummaryCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        tooltip = "Počet provedených kontrol bez ohledu na zjištěnou závadu."
        self.setToolTip(tooltip)

        self.setStyleSheet(
            """
            ControlDoneSummaryCard {
                background-color: #e8f5e9;
                border: 1px solid #c8e6c9;
                border-radius: 8px;
            }
            QProgressBar {
                border: none;
                border-radius: 4px;
                background-color: #c8e6c9;
                min-height: 8px;
                max-height: 8px;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #66bb6a;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        self.title_label = QLabel("Provedeno")
        self.title_label.setStyleSheet("color: #424242; font-size: 12px;")
        self.title_label.setToolTip(tooltip)

        self.ratio_label = QLabel("0 / 0")
        self.ratio_label.setStyleSheet("color: #212121; font-size: 20px; font-weight: bold;")
        self.ratio_label.setToolTip(tooltip)

        self.percent_label = QLabel("0 %")
        self.percent_label.setStyleSheet("color: #616161; font-size: 11px;")
        self.percent_label.setToolTip(tooltip)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setToolTip(tooltip)

        layout.addWidget(self.title_label)
        layout.addWidget(self.ratio_label)
        layout.addWidget(self.percent_label)
        layout.addWidget(self.progress_bar)

    def set_values(self, done_count: int, total_count: int):
        percent = 0 if total_count == 0 else round(done_count * 100 / total_count)
        self.ratio_label.setText(f"{done_count} / {total_count}")
        self.percent_label.setText(f"{percent} %")
        self.progress_bar.setValue(percent)
