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
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_service import (
    BulkInternetImportSummary,
)
from moduly.pravni_pozadavky.ui.legal_predpis_import_progress_dialog import (
    LegalPredpisImportProgressDialog,
)

_COL_REGULATION = 0
_COL_STATUS = 1
_COL_TITLE = 2
_COL_SECTION_COUNT = 3
_COL_ERROR = 4


def format_predpis_import_summary(summary: BulkInternetImportSummary) -> str:
    return (
        "Import dokončen.\n\n"
        f"Importováno předpisů: {summary.ok_count}\n"
        f"Přeskočeno: {summary.skipped_count}\n"
        f"Chyby: {summary.error_count}"
    )


class LegalDocumentBulkInternetImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.import_summary: BulkInternetImportSummary | None = None

        self.setWindowTitle("Import právních předpisů")
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
            QMessageBox.warning(self, "Import právních předpisů", "Zadejte alespoň jeden předpis.")
            return

        self._set_import_in_progress(True)
        self.results_table.setRowCount(0)
        self.summary_label.hide()
        self.summary_label.clear()

        progress_dialog = LegalPredpisImportProgressDialog(self, import_text=text)
        progress_dialog.exec()

        self._set_import_in_progress(False)

        if progress_dialog.was_cancelled():
            partial_summary = progress_dialog.summary()
            if partial_summary is not None and partial_summary.rows:
                self.import_summary = partial_summary
                self._load_results(partial_summary)
            return

        summary = progress_dialog.summary()
        if summary is None:
            return

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
        message = format_predpis_import_summary(summary)
        self.summary_label.setText(message)
        self.summary_label.show()
        QMessageBox.information(self, "Import právních předpisů", message)

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text or "")
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.results_table.setItem(row, column, item)

    def _set_import_in_progress(self, active: bool) -> None:
        self.input_text.setEnabled(not active)
        self.import_btn.setEnabled(not active)
