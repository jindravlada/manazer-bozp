from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_LEGAL_CHANGE
from core.shared.widgets.entity_links_widget import EntityLinksWidget
from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box, wrap_in_scroll_area
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.pravni_pozadavky.constants import (
    CHANGE_TYPE_LABELS,
    VALID_CHANGE_TYPES,
    legal_document_display_label,
    legal_section_display_label,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.ui.legal_change_impacts_tab import LegalChangeImpactsTab


class LegalChangeDialog(QDialog):
    def __init__(self, parent=None, change=None):
        super().__init__(parent)
        self.change = change

        self.setWindowTitle("Změna legislativy" if change is None else "Upravit změnu")
        configure_resizable_form_dialog(self, width=760, height=680, min_width=560, min_height=480)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._main_tab()), "Změna")
        self.links_widget = EntityLinksWidget(
            ENTITY_LEGAL_CHANGE,
            change.id if change is not None else None,
        )
        if change is None:
            links_tab = QWidget()
            links_layout = QVBoxLayout(links_tab)
            links_layout.addWidget(QLabel("Vazby lze přidat až po uložení změny."))
            self.tabs.addTab(links_tab, "Vazby")
            impacts_tab = LegalChangeImpactsTab()
            self.tabs.addTab(impacts_tab, "Dopady")
        else:
            self.tabs.addTab(self.links_widget, "Vazby")
            self.impacts_tab = LegalChangeImpactsTab(change_id=change.id)
            self.tabs.addTab(self.impacts_tab, "Dopady")
        layout.addWidget(self.tabs, 1)
        layout.addWidget(create_save_cancel_box(self))

        if change is not None:
            self._load_change(change)

    def _main_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.legal_document = QComboBox()
        self.legal_version = QComboBox()
        self.legal_section = QComboBox()
        self.change_type = QComboBox()
        for key in sorted(CHANGE_TYPE_LABELS, key=lambda item: CHANGE_TYPE_LABELS[item]):
            self.change_type.addItem(CHANGE_TYPE_LABELS[key], key)
        self.title = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(90)
        self.published_at = NullableDateEdit()
        self.effective_from = NullableDateEdit()
        self.evaluated = QCheckBox("Vyhodnoceno")
        self.evaluated_by = QLineEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Právní předpis:", self.legal_document)
        form.addRow("Verze předpisu:", self.legal_version)
        form.addRow("Ustanovení:", self.legal_section)
        form.addRow("Typ změny:", self.change_type)
        form.addRow("Název:", self.title)
        form.addRow("Popis:", self.description)
        form.addRow("Datum zveřejnění:", self.published_at)
        form.addRow("Účinnost od:", self.effective_from)
        form.addRow("", self.evaluated)
        form.addRow("Vyhodnotil:", self.evaluated_by)
        form.addRow("Poznámka:", self.note)

        self._populate_documents()
        self._populate_versions()
        self._populate_sections()
        self.legal_document.currentIndexChanged.connect(self._on_document_changed)
        self.legal_version.currentIndexChanged.connect(self._on_version_changed)
        return tab

    def _load_change(self, change) -> None:
        self._populate_documents(selected_id=change.legal_document_id)
        self._populate_versions(
            document_id=change.legal_document_id,
            selected_id=change.legal_document_version_id,
        )
        self._populate_sections(
            document_id=change.legal_document_id,
            version_id=change.legal_document_version_id,
            selected_id=change.legal_section_id,
        )
        self._set_combo_value(self.change_type, change.change_type)
        self.title.setText(change.title)
        self.description.setPlainText(change.description)
        self.published_at.set_date_value(change.published_at)
        self.effective_from.set_date_value(change.effective_from)
        self.evaluated.setChecked(change.evaluated)
        self.evaluated_by.setText(change.evaluated_by)
        self.note.setPlainText(change.note)

    def _populate_documents(self, *, selected_id: int | None = None) -> None:
        self.legal_document.blockSignals(True)
        self.legal_document.clear()
        documents = legal_document_service.list_all(include_inactive=False)
        if selected_id is not None:
            selected = legal_document_service.get_by_id(selected_id)
            if (
                selected is not None
                and not selected.active
                and all(item.id != selected_id for item in documents)
            ):
                documents = [selected, *documents]
        for document in documents:
            label = legal_document_display_label(document) or f"Předpis #{document.id}"
            self.legal_document.addItem(label, document.id)
        if selected_id is not None:
            self._set_combo_value(self.legal_document, selected_id)
        self.legal_document.blockSignals(False)

    def _populate_versions(
        self,
        *,
        document_id: int | None = None,
        selected_id: int | None = None,
    ) -> None:
        if document_id is None:
            document_id = self.legal_document.currentData()
        self.legal_version.blockSignals(True)
        self.legal_version.clear()
        self.legal_version.addItem("— bez vazby —", None)
        if document_id is not None:
            versions = legal_document_version_service.list_by_document(
                document_id,
                include_inactive=False,
            )
            if selected_id is not None:
                selected = legal_document_version_service.get_by_id(selected_id)
                if (
                    selected is not None
                    and not selected.active
                    and all(item.id != selected_id for item in versions)
                ):
                    versions = [selected, *versions]
            for version in versions:
                self.legal_version.addItem(version.version_name, version.id)
        if selected_id is not None:
            self._set_combo_value(self.legal_version, selected_id)
        self.legal_version.blockSignals(False)

    def _populate_sections(
        self,
        *,
        document_id: int | None = None,
        version_id: int | None = None,
        selected_id: int | None = None,
    ) -> None:
        if document_id is None:
            document_id = self.legal_document.currentData()
        if version_id is None:
            version_id = self.legal_version.currentData()
        self.legal_section.clear()
        self.legal_section.addItem("— bez vazby —", None)
        sections = []
        if version_id is not None:
            sections = legal_section_service.list_by_version(version_id, include_inactive=False)
        elif document_id is not None:
            sections = legal_section_service.list_by_document(document_id, include_inactive=False)
        if selected_id is not None:
            selected = legal_section_service.get_by_id(selected_id)
            if (
                selected is not None
                and not selected.active
                and all(item.id != selected_id for item in sections)
            ):
                sections = [selected, *sections]
        for section in sections:
            label = legal_section_display_label(section) or f"Ustanovení #{section.id}"
            self.legal_section.addItem(label, section.id)
        if selected_id is not None:
            self._set_combo_value(self.legal_section, selected_id)

    def _on_document_changed(self) -> None:
        document_id = self.legal_document.currentData()
        self._populate_versions(document_id=document_id)
        self._populate_sections(document_id=document_id)

    def _on_version_changed(self) -> None:
        document_id = self.legal_document.currentData()
        version_id = self.legal_version.currentData()
        self._populate_sections(document_id=document_id, version_id=version_id)

    def _set_combo_value(self, combo: QComboBox, value) -> None:
        if value is None:
            if combo.count() > 0 and combo.itemData(0) is None:
                combo.setCurrentIndex(0)
            return
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def get_data(self) -> dict:
        document_id = self.legal_document.currentData()
        if document_id is None and self.legal_document.count() > 0:
            document_id = self.legal_document.currentData()
        return {
            "legal_document_id": document_id,
            "legal_document_version_id": self.legal_version.currentData(),
            "legal_section_id": self.legal_section.currentData(),
            "change_type": self.change_type.currentData() or "",
            "title": self.title.text().strip(),
            "description": self.description.toPlainText().strip(),
            "published_at": self.published_at.get_date(),
            "effective_from": self.effective_from.get_date(),
            "evaluated": self.evaluated.isChecked(),
            "evaluated_by": self.evaluated_by.text().strip(),
            "note": self.note.toPlainText().strip(),
        }

    def accept(self) -> None:
        data = self.get_data()
        if not data["legal_document_id"]:
            QMessageBox.warning(self, "Změna legislativy", "Vyberte právní předpis.")
            return
        if data["change_type"] not in VALID_CHANGE_TYPES:
            QMessageBox.warning(self, "Změna legislativy", "Vyberte typ změny.")
            return
        if not data["title"]:
            QMessageBox.warning(self, "Změna legislativy", "Název je povinný.")
            return
        super().accept()
