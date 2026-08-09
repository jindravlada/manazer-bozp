"""Náhled / tisk / PDF chronologického seznamu smluv OZO."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from core.services.storage_service import storage_service
from core.widgets.dialog_utils import configure_resizable_form_dialog
from moduly.smlouvy_ozo.constants import DIALOG_TITLE_CHRONOLOGICAL_LIST
from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
    ozo_contract_list_service,
)


class OzoContractListDialog(QDialog):
    def __init__(self, parent=None, *, year: int, html: str):
        super().__init__(parent)
        self._year = int(year)
        self._html = html
        self.setWindowTitle(f"{DIALOG_TITLE_CHRONOLOGICAL_LIST} – {self._year}")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(
            self, width=780, height=700, min_width=520, min_height=400
        )

        layout = QVBoxLayout(self)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(html)
        layout.addWidget(self.browser, 1)

        footer = QHBoxLayout()
        self.preview_btn = QPushButton("Náhled")
        self.print_btn = QPushButton("Tisk")
        self.pdf_btn = QPushButton("Uložit jako PDF")
        self.close_btn = QPushButton("Zavřít")
        footer.addWidget(self.preview_btn)
        footer.addWidget(self.print_btn)
        footer.addWidget(self.pdf_btn)
        footer.addStretch()
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

        self.preview_btn.clicked.connect(self._show_preview)
        self.print_btn.clicked.connect(self._print)
        self.pdf_btn.clicked.connect(self._save_pdf)
        self.close_btn.clicked.connect(self.reject)

    def _show_preview(self) -> None:
        # Dialog už je náhledem; obnoví HTML.
        self.browser.setHtml(self._html)

    def _print(self) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        document = QTextDocument()
        document.setHtml(self._html)
        document.print_(printer)

    def _save_pdf(self) -> None:
        storage_service.ensure_structure()
        default_name = f"Chronologicky-seznam-smluv-OZO-{self._year}.pdf"
        default_dir = storage_service.export_file("smlouvy_ozo", default_name).parent
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Uložit chronologický seznam jako PDF",
            str(default_dir / default_name),
            "PDF (*.pdf)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() != ".pdf":
            path = path.with_suffix(".pdf")
        try:
            ozo_contract_list_service.write_pdf(self._html, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(
                self,
                self.windowTitle(),
                f"PDF se nepodařilo uložit.\n\n{exc}",
            )
            return
        QMessageBox.information(self, self.windowTitle(), f"PDF uloženo:\n{path}")
