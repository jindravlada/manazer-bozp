from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from moduly.kontroly.sluzby.monthly_control_service import ThpYearRow

CELL_META_ROLE = Qt.ItemDataRole.UserRole


class ControlYearMatrixTable(QTableWidget):
    STATUS_COLORS = {
        "none": QColor("#ffcdd2"),
        "ok": QColor("#ffe0b2"),
        "defect": QColor("#c8e6c9"),
    }
    KL_INACTIVE_COLOR = QColor("#ffcdd2")
    KL_ACTIVE_COLOR = QColor("#c8e6c9")
    KL_NUMBER_COLOR = QColor("#5d4037")
    CURRENT_MONTH_TINT = QColor("#e3f2fd")

    def __init__(self):
        super().__init__()

        self._highlight_month: int | None = None

        self.setColumnCount(14)
        self.setHorizontalHeaderLabels(
            ["THP pracovník", "Typ"] + [str(month) for month in range(1, 13)]
        )

        self._kl_label_font = QFont(self.font())
        self._kl_label_font.setPointSize(max(8, self._kl_label_font.pointSize() - 2))

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(26)
        self.verticalHeader().setMinimumSectionSize(26)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.setAlternatingRowColors(False)
        self.setSelectionMode(QTableWidget.NoSelection)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setShowGrid(True)

    def set_highlight_month(self, month: int | None):
        self._highlight_month = month
        if self.rowCount() > 0:
            self._apply_header_highlights()

    def load_matrix(self, rows: list[ThpYearRow]):
        self.clearSpans()
        if not rows:
            self.setRowCount(0)
            return

        separator_count = max(0, len(rows) - 1)
        self.setRowCount(len(rows) * 2 + separator_count)

        table_row = 0
        for index, row in enumerate(rows):
            status_row = table_row
            kl_row = table_row + 1
            table_row += 2

            name_item = QTableWidgetItem(row.thp_worker_name)
            name_item.setFlags(Qt.ItemIsEnabled)
            self.setItem(status_row, 0, name_item)
            self.setSpan(status_row, 0, 2, 1)

            type_status = QTableWidgetItem("Měsíc")
            type_status.setFlags(Qt.ItemIsEnabled)
            type_kl = QTableWidgetItem("KL")
            type_kl.setFlags(Qt.ItemIsEnabled)
            self.setItem(status_row, 1, type_status)
            self.setItem(kl_row, 1, type_kl)

            for month in range(1, 13):
                column = month + 1
                cell = row.months.get(month, None)
                status = cell.status if cell is not None else "none"

                status_item = QTableWidgetItem("")
                status_item.setFlags(Qt.ItemIsEnabled)
                self._set_status_meta(status_item, row.thp_worker_id, month)
                self.apply_status_cell(status_item, status)
                self.setItem(status_row, column, status_item)

            for kl_index in range(1, 13):
                column = kl_index + 1
                used = row.kl_flags.get(kl_index, False)

                kl_item = QTableWidgetItem(str(kl_index))
                kl_item.setFlags(Qt.ItemIsEnabled)
                kl_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                kl_item.setFont(self._kl_label_font)
                self._set_kl_meta(kl_item, row.thp_worker_id, kl_index)
                self.apply_kl_cell(kl_item, kl_index, used)
                self.setItem(kl_row, column, kl_item)

            if index < len(rows) - 1:
                self._add_thp_separator_row(table_row)
                table_row += 1

        self._apply_header_highlights()

    def cell_meta(self, row: int, column: int) -> dict | None:
        item = self.item(row, column)
        if item is None:
            return None

        meta = item.data(CELL_META_ROLE)
        if not isinstance(meta, dict):
            return None

        return meta

    def apply_status_cell(self, item: QTableWidgetItem, status: str):
        meta = item.data(CELL_META_ROLE)
        if isinstance(meta, dict):
            meta = {**meta, "status": status}
            item.setData(CELL_META_ROLE, meta)
            month = meta.get("month")
        else:
            month = None

        color = self._status_color(status, month)
        item.setBackground(QBrush(color))

    def apply_kl_cell(self, item: QTableWidgetItem, kl_index: int, used: bool):
        item.setText(str(kl_index))
        item.setForeground(QBrush(self.KL_NUMBER_COLOR))
        base = self.KL_ACTIVE_COLOR if used else self.KL_INACTIVE_COLOR
        item.setBackground(QBrush(base))

    def _status_color(self, status: str, month: int | None) -> QColor:
        base = self.STATUS_COLORS.get(status, QColor("#ffffff"))
        if month is not None and month == self._highlight_month:
            return self._blend_colors(base, self.CURRENT_MONTH_TINT, 0.4)
        return base

    def _blend_colors(self, base: QColor, overlay: QColor, factor: float) -> QColor:
        inverse = 1.0 - factor
        return QColor(
            int(base.red() * inverse + overlay.red() * factor),
            int(base.green() * inverse + overlay.green() * factor),
            int(base.blue() * inverse + overlay.blue() * factor),
        )

    def _apply_header_highlights(self):
        highlight_brush = QBrush(self.CURRENT_MONTH_TINT)
        default_brush = QBrush(QColor("#f5f5f5"))

        for month in range(1, 13):
            column = month + 1
            header_item = QTableWidgetItem(str(month))
            if month == self._highlight_month:
                header_item.setBackground(highlight_brush)
                font = header_item.font()
                font.setBold(True)
                header_item.setFont(font)
            else:
                header_item.setBackground(default_brush)
            self.setHorizontalHeaderItem(column, header_item)

        for label, column in (("THP pracovník", 0), ("Typ", 1)):
            header_item = QTableWidgetItem(label)
            header_item.setBackground(default_brush)
            self.setHorizontalHeaderItem(column, header_item)

        for row in range(self.rowCount()):
            for column in range(2, 14):
                cell_item = self.item(row, column)
                if cell_item is None:
                    continue
                cell_meta = cell_item.data(CELL_META_ROLE)
                if not isinstance(cell_meta, dict) or cell_meta.get("part") != "status":
                    continue
                status = cell_meta.get("status", "none")
                self.apply_status_cell(cell_item, status)

    def _set_status_meta(self, item: QTableWidgetItem, thp_worker_id: int, month: int):
        item.setData(
            CELL_META_ROLE,
            {
                "thp_worker_id": thp_worker_id,
                "month": month,
                "part": "status",
            },
        )

    def _set_kl_meta(self, item: QTableWidgetItem, thp_worker_id: int, kl_index: int):
        item.setData(
            CELL_META_ROLE,
            {
                "thp_worker_id": thp_worker_id,
                "kl_index": kl_index,
                "part": "kl",
            },
        )

    def _add_thp_separator_row(self, row: int):
        self.setRowHeight(row, 3)
        separator_color = QBrush(QColor("#9e9e9e"))
        for column in range(self.columnCount()):
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setBackground(separator_color)
            self.setItem(row, column, item)
