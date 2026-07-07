from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.ui.legal_document_dialog import LegalDocumentDialog
from moduly.pravni_pozadavky.ui.legal_document_table import LegalDocumentTable


class PravniPredpisyTab(QWidget):
    """Záložka evidence právních předpisů."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nový")
        self.import_btn = QPushButton("Import JSON")
        self.edit_btn = QPushButton("Upravit")
        self.toggle_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addStretch()

        self.table = LegalDocumentTable()
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat předpis...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_document)
        self.import_btn.clicked.connect(self.import_json_document)
        self.edit_btn.clicked.connect(self.edit_selected_document)
        self.toggle_btn.clicked.connect(self.toggle_selected_document)
        self.table.doubleClicked.connect(self.edit_selected_document)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        documents = legal_document_service.list_all(include_inactive=True)
        self.table.load_documents(documents)
        self.text_filter.update_count()
        self._update_action_buttons()

    def _selected_document(self):
        document_id = self.table.selected_document_id()
        if document_id is None:
            return None
        return legal_document_service.get_by_id(document_id)

    def _update_action_buttons(self) -> None:
        document = self._selected_document()
        if document is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not document.active else "Deaktivovat")

    def new_document(self) -> None:
        dialog = LegalDocumentDialog(self)
        if not exec_maximized(dialog):
            return
        try:
            legal_document_service.create(**dialog.get_data())
        except ValueError as exc:
            QMessageBox.warning(self, "Právní předpisy", str(exc))
            return
        self.refresh()

    def import_json_document(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import právního předpisu z JSON",
            "",
            "JSON soubory (*.json);;Všechny soubory (*)",
        )
        if not file_path:
            return

        try:
            result = legal_document_json_import_service.import_from_file(file_path)
        except ValueError as exc:
            QMessageBox.warning(self, "Import JSON", str(exc))
            return

        document = legal_document_service.get_by_id(result.document_id)
        document_title = document.title if document is not None else f"Předpis #{result.document_id}"
        QMessageBox.information(
            self,
            "Import JSON",
            (
                f"Import dokončen.\n\n"
                f"Předpis: {document_title}\n"
                f"ID předpisu: {result.document_id}\n"
                f"ID verze: {result.version_id}\n"
                f"Počet částí: {result.section_count}"
            ),
        )
        self.refresh()

    def edit_selected_document(self) -> None:
        document = self._selected_document()
        if document is None:
            QMessageBox.information(self, "Právní předpisy", "Vyberte právní předpis.")
            return

        dialog = LegalDocumentDialog(self, document=document)
        if not exec_maximized(dialog):
            return
        try:
            legal_document_service.update(
                document.id,
                active=document.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Právní předpisy", str(exc))
            return
        self.refresh()

    def toggle_selected_document(self) -> None:
        document = self._selected_document()
        if document is None:
            QMessageBox.information(self, "Právní předpisy", "Vyberte právní předpis.")
            return

        if document.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat předpis",
                "Opravdu deaktivovat vybraný právní předpis?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_document_service.deactivate(document.id)
                self.refresh()
            return

        legal_document_service.restore(document.id)
        self.refresh()
