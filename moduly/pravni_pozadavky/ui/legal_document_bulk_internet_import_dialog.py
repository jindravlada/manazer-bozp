from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_service import (
    BulkInternetImportSummary,
    legal_document_bulk_internet_import_service,
)

_COL_REGULATION = 0
_COL_STATUS = 1
_COL_TITLE = 2
_COL_SECTION_COUNT = 3
_COL_ERROR = 4


class LegalDocumentBulkInternetImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.import_summary: BulkInternetImportSummary | None = None

        self.setWindowTitle("Hromadný import právních předpisů z internetu")
        configure_resizable_form_dialog(self, width=900, height=640, min_width=720, min_height=480)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Zadejte jeden předpis na řádek. Podporované formáty:\n"
            "262/2006, 262/2006 Sb., Zákon 262/2006 Sb., NV 390/2021 Sb., "
            "Nařízení vlády 390/2021 Sb."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "262/2006\n"
            "Zákon 262/2006 Sb.\n"
            "NV 390/2021 Sb."
        )
        self.input_text.setMinimumHeight(140)
        layout.addWidget(self.input_text)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "Předpis",
            "Stav",
            "Název",
            "Počet částí",
            "Chyba",
        ])
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SingleSelection)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(_COL_REGULATION, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_STATUS, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_TITLE, QHeaderView.Stretch)
        header.setSectionResizeMode(_COL_SECTION_COUNT, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_ERROR, QHeaderView.Stretch)
        layout.addWidget(self.results_table, 1)

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.hide()
        layout.addWidget(self.summary_label)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.import_btn = QPushButton("Importovat")
        self.close_btn = QPushButton("Zavřít")
        buttons.addWidget(self.import_btn)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.import_btn.clicked.connect(self._run_import)
        self.close_btn.clicked.connect(self.reject)

    def _run_import(self) -> None:
        text = self.input_text.toPlainText()
        if not any(line.strip() for line in text.splitlines()):
            QMessageBox.warning(self, "Hromadný import", "Zadejte alespoň jeden předpis.")
            return

        self._set_import_in_progress(True)
        self.results_table.setRowCount(0)
        self.summary_label.hide()
        self.summary_label.clear()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            summary = legal_document_bulk_internet_import_service.import_lines(
                text,
                on_progress=self._update_progress,
            )
        finally:
            self._set_import_in_progress(False)
            QApplication.restoreOverrideCursor()

        self.import_summary = summary
        self._load_results(summary)
        self._show_summary(summary)

    def _load_results(self, summary: BulkInternetImportSummary) -> None:
        self.results_table.setRowCount(len(summary.rows))
        for row_index, row in enumerate(summary.rows):
            section_count = "" if row.section_count is None else str(row.section_count)
            self._set_item(row_index, _COL_REGULATION, row.regulation_label)
            self._set_item(row_index, _COL_STATUS, row.status)
            self._set_item(row_index, _COL_TITLE, row.title)
            self._set_item(row_index, _COL_SECTION_COUNT, section_count)
            self._set_item(row_index, _COL_ERROR, row.error)

    def _show_summary(self, summary: BulkInternetImportSummary) -> None:
        message = (
            f"Celkem: {summary.total}\n"
            f"OK: {summary.ok_count}\n"
            f"Chyby: {summary.error_count}\n"
            f"Přeskočeno: {summary.skipped_count}"
        )
        self.summary_label.setText(message)
        self.summary_label.show()
        QMessageBox.information(self, "Hromadný import", f"Import dokončen.\n\n{message}")

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.results_table.setItem(row, column, item)

    def _set_import_in_progress(self, active: bool) -> None:
        self.input_text.setEnabled(not active)
        self.import_btn.setEnabled(not active)
        if not active:
            self.status_label.hide()
            self.status_label.clear()

    def _update_progress(self, current: int, total: int, label: str) -> None:
        self.status_label.setText(f"Zpracovávám {current}/{total}: {label}")
        self.status_label.show()
        QApplication.processEvents()
