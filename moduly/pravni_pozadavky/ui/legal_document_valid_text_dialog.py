from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog, create_close_box
from moduly.pravni_pozadavky.constants import legal_document_regulation_number
from moduly.pravni_pozadavky.sluzby.legal_document_valid_text_service import ValidTextDocument
from moduly.pravni_pozadavky.ui.legal_document_valid_text_tab import LegalDocumentValidTextTab
from moduly.pravni_pozadavky.ui.legal_document_valid_text_worker import (
    LegalDocumentValidTextThreadRunner,
)


class LegalDocumentValidTextDialog(QDialog):
    """Samostatná read-only čtečka platného znění vybrané verze předpisu."""

    def __init__(
        self,
        parent=None,
        *,
        document,
        version_id: int,
    ) -> None:
        super().__init__(parent)
        self._version_id = version_id
        self._content_loaded = False
        self._runner = LegalDocumentValidTextThreadRunner(version_id=version_id)

        regulation_number = legal_document_regulation_number(document)
        self.setWindowTitle(f"Platné znění – {regulation_number}")
        configure_resizable_form_dialog(self, width=920, height=720, min_width=640, min_height=480)
        self.setModal(True)

        layout = QVBoxLayout(self)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        loading_root = QWidget()
        loading_layout = QVBoxLayout(loading_root)
        self.status_label = QLabel("Načítám platné znění…")
        self.status_label.setWordWrap(True)
        loading_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        loading_layout.addWidget(self.progress_bar)
        loading_layout.addStretch()
        self.stack.addWidget(loading_root)

        self.valid_text_tab = LegalDocumentValidTextTab(
            document_id=document.id,
            version_id=version_id,
        )
        self.valid_text_tab.set_search_enabled(False)
        self.stack.addWidget(self.valid_text_tab)

        close_box = create_close_box(self)
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        worker = self._runner.worker
        worker.finished.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        self._runner.start()

    def _on_loaded(self, document: ValidTextDocument) -> None:
        if self._content_loaded:
            return
        self.valid_text_tab.apply_document(document)
        self.valid_text_tab.set_search_enabled(True)
        self._content_loaded = True
        self.stack.setCurrentWidget(self.valid_text_tab)

    def _on_failed(self, message: str) -> None:
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.status_label.setText("Platné znění se nepodařilo načíst.")
        QMessageBox.warning(
            self,
            "Platné znění",
            message or "Platné znění se nepodařilo načíst.",
        )
