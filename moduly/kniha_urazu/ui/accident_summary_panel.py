from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

_ZOU_TOOLTIP = (
    "Záznam o úrazu:\n"
    "🟥 po termínu\n"
    "🟧 čeká na odeslání / zpracování\n"
    "🟩 hotovo"
)
_OP_TOOLTIP = (
    "Opatření:\n"
    "🟥 počet úrazů, u kterých existuje alespoň jedno neukončené opatření"
)
_SETRENI_TOOLTIP = (
    "Šetření:\n"
    "🟦 počet nedokončených šetření\n"
    "(logika bude doplněna později)"
)


class AccidentSummaryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        grid = QGridLayout(self)
        grid.setContentsMargins(12, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(0)

        title = QLabel("Souhrn")
        title.setStyleSheet("font-weight: bold;")
        grid.addWidget(title, 0, 0, 1, 4)

        zou_label = QLabel("ZoÚ")
        zou_label.setToolTip(_ZOU_TOOLTIP)
        grid.addWidget(zou_label, 1, 0)
        self.zou_overdue_label = QLabel("🟥 0")
        self.zou_waiting_label = QLabel("🟧 0")
        self.zou_done_label = QLabel("🟩 0")
        for label in (self.zou_overdue_label, self.zou_waiting_label, self.zou_done_label):
            label.setToolTip(_ZOU_TOOLTIP)
        grid.addWidget(self.zou_overdue_label, 1, 1)
        grid.addWidget(self.zou_waiting_label, 1, 2)
        grid.addWidget(self.zou_done_label, 1, 3)

        op_label = QLabel("Opatření")
        op_label.setToolTip(_OP_TOOLTIP)
        grid.addWidget(op_label, 2, 0)
        self.op_incomplete_label = QLabel("🟥 0")
        self.op_incomplete_label.setToolTip(_OP_TOOLTIP)
        grid.addWidget(self.op_incomplete_label, 2, 1, 1, 3)

        setreni_label = QLabel("Šetření")
        setreni_label.setToolTip(_SETRENI_TOOLTIP)
        grid.addWidget(setreni_label, 3, 0)
        self.setreni_incomplete_label = QLabel("🟦 0")
        self.setreni_incomplete_label.setToolTip(_SETRENI_TOOLTIP)
        grid.addWidget(self.setreni_incomplete_label, 3, 1, 1, 3)

    def update_summary(self, summary):
        self.zou_overdue_label.setText(f"🟥 {summary.get('zou_overdue', 0)}")
        self.zou_waiting_label.setText(f"🟧 {summary.get('zou_waiting', 0)}")
        self.zou_done_label.setText(f"🟩 {summary.get('zou_done', 0)}")
        self.op_incomplete_label.setText(f"🟥 {summary.get('op_incomplete', 0)}")
        self.setreni_incomplete_label.setText(f"🟦 {summary.get('setreni_incomplete', 0)}")
