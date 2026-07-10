from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from moduly.pravni_pozadavky.constants import (
    DEFAULT_DOCUMENT_ACTIVE_FILTER,
    DEFAULT_INCLUDED_IN_PROCESSES_FILTER,
    FILTER_ACTIVE_ONLY,
    FILTER_ALL_RECORDS,
    FILTER_INCLUDED_IN_PROCESSES_NO,
    FILTER_INCLUDED_IN_PROCESSES_YES,
    FILTER_INACTIVE_ONLY,
)
from moduly.pravni_pozadavky.import_export.legal_document_json_export_service import (
    legal_document_json_export_service,
)
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.import_export.legal_document_txt_import_service import (
    legal_document_txt_import_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.ui.legal_document_dialog import LegalDocumentDialog
from moduly.pravni_pozadavky.ui.legal_document_valid_text_dialog import (
    LegalDocumentValidTextDialog,
)
from moduly.pravni_pozadavky.ui.legal_document_bulk_internet_import_dialog import (
    LegalDocumentBulkInternetImportDialog,
)
from moduly.pravni_pozadavky.ui.legal_document_txt_import_dialog import LegalDocumentTxtImportDialog
from moduly.pravni_pozadavky.ui.legal_document_table import LegalDocumentTable


class PravniPredpisyTab(QWidget):
    """Záložka evidence právních předpisů."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        actions_toolbar = QHBoxLayout()
        actions_toolbar.setSpacing(8)
        filters_toolbar = QHBoxLayout()
        filters_toolbar.setSpacing(8)

        self.new_btn = QPushButton("Nový")
        self.edit_btn = QPushButton("Upravit")
        self.valid_text_btn = QPushButton("Platné znění")
        self.import_bulk_internet_btn = QPushButton("Import z internetu")
        self.import_txt_btn = QPushButton("Import TXT")
        self.import_btn = QPushButton("Import JSON")
        self.export_btn = QPushButton("Export JSON")
        self.toggle_btn = QPushButton("Deaktivovat")

        for button in (
            self.new_btn,
            self.edit_btn,
            self.valid_text_btn,
            self.import_bulk_internet_btn,
            self.import_txt_btn,
            self.import_btn,
            self.export_btn,
            self.toggle_btn,
        ):
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.active_filter = QComboBox()
        self.active_filter.addItems([
            FILTER_ACTIVE_ONLY,
            FILTER_INACTIVE_ONLY,
            FILTER_ALL_RECORDS,
        ])
        self.active_filter.setCurrentText(DEFAULT_DOCUMENT_ACTIVE_FILTER)
        self.included_in_processes_filter = QComboBox()
        self.included_in_processes_filter.addItems([
            FILTER_ALL_RECORDS,
            FILTER_INCLUDED_IN_PROCESSES_YES,
            FILTER_INCLUDED_IN_PROCESSES_NO,
        ])
        self.included_in_processes_filter.setCurrentText(DEFAULT_INCLUDED_IN_PROCESSES_FILTER)

        actions_toolbar.addWidget(self.new_btn)
        actions_toolbar.addWidget(self.edit_btn)
        actions_toolbar.addWidget(self.valid_text_btn)
        actions_toolbar.addWidget(self.import_bulk_internet_btn)
        actions_toolbar.addWidget(self.import_txt_btn)
        actions_toolbar.addWidget(self.import_btn)
        actions_toolbar.addWidget(self.export_btn)
        actions_toolbar.addWidget(self.toggle_btn)
        actions_toolbar.addStretch()

        filters_toolbar.addWidget(QLabel("Záznamy:"))
        filters_toolbar.addWidget(self.active_filter)
        filters_toolbar.addWidget(QLabel("V procesech:"))
        filters_toolbar.addWidget(self.included_in_processes_filter)
        filters_toolbar.addStretch()

        self.table = LegalDocumentTable()
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat předpis...")

        layout.addLayout(actions_toolbar)
        layout.addLayout(filters_toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_document)
        self.import_btn.clicked.connect(self.import_json_document)
        self.import_txt_btn.clicked.connect(self.import_txt_document)
        self.import_bulk_internet_btn.clicked.connect(self.import_bulk_internet_documents)
        self.export_btn.clicked.connect(self.export_json_document)
        self.edit_btn.clicked.connect(self.edit_selected_document)
        self.valid_text_btn.clicked.connect(self.open_valid_text)
        self.toggle_btn.clicked.connect(self.toggle_selected_document)
        self.table.doubleClicked.connect(self.edit_selected_document)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        self.active_filter.currentIndexChanged.connect(self.refresh)
        self.included_in_processes_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self) -> None:
        documents = self._filter_documents(legal_document_service.list_all(include_inactive=True))
        self.table.load_documents(documents)
        self.text_filter.apply_filter()
        self.text_filter.update_count()
        self._update_action_buttons()

    def _filter_documents(self, documents):
        active_mode = self.active_filter.currentText()
        if active_mode == FILTER_ACTIVE_ONLY:
            documents = [document for document in documents if document.active]
        elif active_mode == FILTER_INACTIVE_ONLY:
            documents = [document for document in documents if not document.active]

        included_mode = self.included_in_processes_filter.currentText()
        if included_mode == FILTER_INCLUDED_IN_PROCESSES_YES:
            return [document for document in documents if document.included_in_processes]
        if included_mode == FILTER_INCLUDED_IN_PROCESSES_NO:
            return [document for document in documents if not document.included_in_processes]
        return documents

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

    def import_txt_document(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import právního předpisu z TXT",
            "",
            "Textové soubory (*.txt);;Všechny soubory (*)",
        )
        if not file_path:
            return

        metadata_dialog = LegalDocumentTxtImportDialog(self, file_path=file_path)
        if not exec_maximized(metadata_dialog) or metadata_dialog.import_result is None:
            return

        result = metadata_dialog.import_result
        document = legal_document_service.get_by_id(result.document_id)
        version = legal_document_version_service.get_by_id(result.version_id)
        document_title = document.title if document is not None else f"Předpis #{result.document_id}"
        version_name = version.version_name if version is not None else f"Verze #{result.version_id}"
        QMessageBox.information(
            self,
            "Import TXT",
            (
                f"Import dokončen.\n\n"
                f"Předpis: {document_title}\n"
                f"Verze: {version_name}\n"
                f"Počet částí: {result.section_count}"
            ),
        )
        self.refresh()

    def import_bulk_internet_documents(self) -> None:
        dialog = LegalDocumentBulkInternetImportDialog(self)
        exec_maximized(dialog)
        if dialog.import_summary is not None:
            self.refresh()

    def export_json_document(self) -> None:
        document = self._selected_document()
        if document is None:
            QMessageBox.information(self, "Právní předpisy", "Vyberte právní předpis.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export právního předpisu do JSON",
            f"{document.short_title or document.title}.json",
            "JSON soubory (*.json);;Všechny soubory (*)",
        )
        if not file_path:
            return

        try:
            result = legal_document_json_export_service.export_to_file(document.id, file_path)
        except ValueError as exc:
            QMessageBox.warning(self, "Export JSON", str(exc))
            return

        QMessageBox.information(
            self,
            "Export JSON",
            (
                "Export dokončen.\n\n"
                f"Předpis:\n{result.document_title}\n\n"
                f"Verzí:\n{result.version_name}\n\n"
                f"Částí:\n{result.section_count}"
            ),
        )

    def open_valid_text(self) -> None:
        document = self._selected_document()
        if document is None:
            QMessageBox.information(self, "Právní předpisy", "Vyberte právní předpis.")
            return

        version = legal_document_version_service.get_current_version(document.id)
        if version is None:
            QMessageBox.information(
                self,
                "Právní předpisy",
                "Právní předpis nemá dostupné aktuální znění.",
            )
            return

        dialog = LegalDocumentValidTextDialog(
            self,
            document=document,
            version_id=version.id,
        )
        exec_maximized(dialog)

    def edit_selected_document(self) -> None:
        document = self._selected_document()
        if document is None:
            QMessageBox.information(self, "Právní předpisy", "Vyberte právní předpis.")
            return

        self._open_document_editor(document.id)

    def open_document(self, document_id: int) -> None:
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            QMessageBox.warning(self, "Právní předpisy", "Právní předpis nebyl nalezen.")
            self.refresh()
            return

        self._select_document(document_id)
        self._open_document_editor(document_id)

    def _select_document(self, document_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.text() == str(document_id):
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                break

    def _open_document_editor(self, document_id: int) -> None:
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            QMessageBox.warning(self, "Právní předpisy", "Právní předpis nebyl nalezen.")
            self.refresh()
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
