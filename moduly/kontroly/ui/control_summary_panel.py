from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from moduly.kontroly.sluzby.monthly_control_service import (
    YearMatrixKlSummary,
    YearMatrixMonthSummary,
    YearMatrixSummary,
)
from moduly.kontroly.ui.control_summary_card import ControlDoneSummaryCard, ControlSummaryCard

CURRENT_MONTH_BG = "#e3f2fd"
CURRENT_MONTH_BORDER = "#90caf9"

ROW_LABEL_STYLES = {
    "Provedeno": ("#e8f5e9", "#c8e6c9"),
    "Se závadou": ("#fff3e0", "#ffe0b2"),
    "Neprovedeno": ("#ffebee", "#ffcdd2"),
    "Omluveno": ("#e3f2fd", "#bbdefb"),
}

KL_COMPLETE_BG = "#c8e6c9"
KL_COMPLETE_BORDER = "#81c784"
KL_MISSING_BG = "#ffcdd2"
KL_MISSING_BORDER = "#e57373"


class ControlSummaryPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._highlight_month: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 4)
        root.setSpacing(10)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        self.thp_card = ControlSummaryCard(
            "",
            "#f5f5f5",
            "#e0e0e0",
            "Počet pracovníků THP zařazených do systému kontrol.",
        )
        self.done_card = ControlDoneSummaryCard()
        self.defect_card = ControlSummaryCard(
            "Se závadou",
            "#fff3e0",
            "#ffe0b2",
            "Počet kontrol, při kterých byla zjištěna alespoň jedna závada.",
        )
        self.none_card = ControlSummaryCard(
            "Neprovedeno",
            "#ffebee",
            "#ffcdd2",
            "Počet měsíců, ve kterých zatím nebyla provedena kontrola.",
        )
        self.excused_card = ControlSummaryCard(
            "Omluveno",
            "#e3f2fd",
            "#bbdefb",
            "Počet kontrol označených jako omluvené (dovolená, nemoc, nerelevantní list).",
        )

        for card in (self.thp_card, self.done_card, self.defect_card, self.none_card, self.excused_card):
            cards_row.addWidget(card, 1)

        root.addLayout(cards_row)

        monthly_title = QLabel("Měsíční přehled")
        monthly_title.setStyleSheet("font-weight: bold;")
        root.addWidget(monthly_title)

        monthly_grid = QGridLayout()
        monthly_grid.setHorizontalSpacing(6)
        monthly_grid.setVerticalSpacing(2)
        monthly_grid.setContentsMargins(0, 0, 0, 0)

        monthly_grid.addWidget(QLabel(""), 0, 0)
        self._month_headers: list[QLabel] = []
        for month in range(1, 13):
            header = QLabel(str(month))
            header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header.setMinimumWidth(28)
            monthly_grid.addWidget(header, 0, month)
            self._month_headers.append(header)

        self._month_done_labels = self._add_monthly_row(monthly_grid, 1, "Provedeno")
        self._month_defect_labels = self._add_monthly_row(monthly_grid, 2, "Se závadou")
        self._month_none_labels = self._add_monthly_row(monthly_grid, 3, "Neprovedeno")
        self._month_excused_labels = self._add_monthly_row(monthly_grid, 4, "Omluveno")

        root.addLayout(monthly_grid)

        kl_title = QLabel("KL")
        kl_title.setStyleSheet("font-weight: bold;")
        root.addWidget(kl_title)

        kl_grid = QGridLayout()
        kl_grid.setHorizontalSpacing(6)
        kl_grid.setVerticalSpacing(4)
        kl_grid.setContentsMargins(0, 0, 0, 0)

        self._kl_number_labels: list[QLabel] = []
        self._kl_status_labels: list[QLabel] = []
        for index, kl_number in enumerate(range(1, 13)):
            number_label = QLabel(str(kl_number))
            number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number_label.setMinimumWidth(28)
            kl_grid.addWidget(number_label, 0, index)
            self._kl_number_labels.append(number_label)

            status_label = QLabel(str(kl_number))
            status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            status_label.setMinimumSize(28, 24)
            kl_grid.addWidget(status_label, 1, index)
            self._kl_status_labels.append(status_label)

        root.addLayout(kl_grid)

        self._month_value_labels = (
            self._month_done_labels,
            self._month_defect_labels,
            self._month_none_labels,
            self._month_excused_labels,
        )

    def set_highlight_month(self, month: int | None):
        self._highlight_month = month

    def _add_monthly_row(self, grid: QGridLayout, row: int, label_text: str) -> list[QLabel]:
        background, border = ROW_LABEL_STYLES[label_text]
        row_label = QLabel(label_text)
        row_label.setStyleSheet(
            f"""
            background-color: {background};
            border: 1px solid {border};
            border-radius: 4px;
            padding: 4px 8px;
            """
        )
        grid.addWidget(row_label, row, 0)

        value_labels: list[QLabel] = []
        for month in range(1, 13):
            value = QLabel("0")
            value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            value.setMinimumWidth(28)
            grid.addWidget(value, row, month)
            value_labels.append(value)

        return value_labels

    def _apply_month_highlight(self):
        for index, header in enumerate(self._month_headers, start=1):
            is_current = index == self._highlight_month
            if is_current:
                style = (
                    f"background-color: {CURRENT_MONTH_BG};"
                    f"border: 1px solid {CURRENT_MONTH_BORDER};"
                    "border-radius: 4px;"
                    "font-weight: bold;"
                )
            else:
                style = ""
            header.setStyleSheet(style)

            for row_labels in self._month_value_labels:
                label = row_labels[index - 1]
                if is_current:
                    label.setStyleSheet(
                        f"background-color: {CURRENT_MONTH_BG};"
                        f"border: 1px solid {CURRENT_MONTH_BORDER};"
                        "border-radius: 4px;"
                    )
                else:
                    label.setStyleSheet("")

    def _apply_kl_cell(self, label: QLabel, kl_number: int, complete: bool):
        if complete:
            background = KL_COMPLETE_BG
            border = KL_COMPLETE_BORDER
        else:
            background = KL_MISSING_BG
            border = KL_MISSING_BORDER

        label.setText(str(kl_number))
        label.setStyleSheet(
            f"""
            background-color: {background};
            border: 1px solid {border};
            border-radius: 4px;
            color: #5d4037;
            font-size: 11px;
            """
        )

    def update_summary(
        self,
        summary: YearMatrixSummary,
        monthly: YearMatrixMonthSummary,
        kl: YearMatrixKlSummary,
    ):
        total_slots = summary.thp_count * 12

        self.thp_card.set_value(str(summary.thp_count), "THP")
        self.done_card.set_values(summary.done_count, total_slots)
        self.defect_card.set_value(str(summary.defect_count))
        self.none_card.set_value(str(summary.none_count))
        self.excused_card.set_value(str(summary.excused_count))

        for index, value in enumerate(monthly.done_by_month):
            self._month_done_labels[index].setText(str(value))
        for index, value in enumerate(monthly.defect_by_month):
            self._month_defect_labels[index].setText(str(value))
        for index, value in enumerate(monthly.none_by_month):
            self._month_none_labels[index].setText(str(value))
        for index, value in enumerate(monthly.excused_by_month):
            self._month_excused_labels[index].setText(str(value))

        missing_kl = set(kl.missing_kl_numbers)
        for index, kl_number in enumerate(range(1, 13)):
            complete = kl_number not in missing_kl
            self._apply_kl_cell(self._kl_status_labels[index], kl_number, complete)

        self._apply_month_highlight()
