from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.import_export.legal_requirement_json_import_service import (
    LegalRequirementJsonImportSummary,
    legal_requirement_json_import_service,
)

_COL_ITEM = 0
_COL_STATUS = 1
_COL_TITLE = 2
_COL_ERROR = 3


class LegalRequirementJsonImportDialog(QDialog):
    def __init__(self, parent=None, *, file_path: str):
        super().__init__(parent)
        self.import_summary: LegalRequirementJsonImportSummary | None = None

        self.setWindowTitle("Import požadavků z JSON")
        configure_resizable_form_dialog(self, width=900, height=640, min_width=720, min_height=480)

        layout = QVBoxLayout(self)

        self.file_label = QLabel(file_path)
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Ustanovení",
            "Stav",
            "Název",
            "Chyba",
        ])
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(_COL_ITEM, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_TITLE, QHeaderView.Stretch)
        header.setSectionResizeMode(_COL_ERROR, QHeaderView.Stretch)
        layout.addWidget(self.results_table, 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Zavřít")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        try:
            self.import_summary = legal_requirement_json_import_service.import_from_file(
                file_path,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Import požadavků JSON", str(exc))
            return

        self._load_results(self.import_summary)
        self._show_summary(self.import_summary)

    def _load_results(self, summary: LegalRequirementJsonImportSummary) -> None:
        self.results_table.setRowCount(len(summary.rows))
        for row_index, row in enumerate(summary.rows):
            self._set_item(row_index, _COL_ITEM, row.item_label)
            self._set_item(row_index, _COL_STATUS, row.status)
            self._set_item(row_index, _COL_TITLE, row.title)
            self._set_item(row_index, _COL_ERROR, row.error)

    def _show_summary(self, summary: LegalRequirementJsonImportSummary) -> None:
        message = (
            f"Celkem: {summary.total}\n"
            f"Vytvořeno: {summary.created_count}\n"
            f"Rozšířeno: {summary.extended_count}\n"
            f"Přeskočeno: {summary.skipped_count}\n"
            f"Chyby: {summary.error_count}"
        )
        self.summary_label.setText(message)
        QMessageBox.information(self, "Import požadavků JSON", f"Import dokončen.\n\n{message}")

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.results_table.setItem(row, column, item)
