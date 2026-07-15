from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.pravni_pozadavky.constants import legal_document_catalog_link_label
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_DOCUMENT_REQUIRED,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
    HazardLibraryTemplateLegalLinkError,
    hazard_library_template_legal_link_service,
)


class HazardLibraryTemplateLegalLinkDialog(QDialog):
    """Kompaktní dialog vazby zdroje na právní předpis (R20e.1)."""

    def __init__(
        self,
        parent=None,
        *,
        template_id: int,
        link=None,
        read_only: bool = False,
    ):
        super().__init__(parent)
        self.template_id = template_id
        self.link = link
        self.read_only = read_only

        self.setWindowTitle(HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE)
        self.setMinimumSize(560, 280)
        self.resize(700, 350)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.document_combo = QComboBox()
        self.document_combo.setEditable(True)
        self.document_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.document_combo.setMinimumWidth(360)

        self.note = QPlainTextEdit()
        self.note.setFixedHeight(90)
        self.note.setPlaceholderText("Volitelná poznámka k vazbě")

        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Právní předpis *:", self.document_combo)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        selected_id = link.legal_document_id if link is not None else None
        self._populate_documents(selected_id)

        if link is not None:
            self.note.setPlainText(link.note or "")
            self.active_checkbox.setChecked(bool(link.active))

        if read_only:
            self.document_combo.setEnabled(False)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def _populate_documents(self, selected_id: int | None) -> None:
        self.document_combo.clear()
        self.document_combo.addItem("— vyberte právní předpis —", None)
        documents = legal_document_service.list_all(include_inactive=False)
        if selected_id is not None:
            selected = legal_document_service.get_by_id(selected_id)
            if (
                selected is not None
                and not selected.active
                and all(item.id != selected_id for item in documents)
            ):
                documents = [selected, *documents]
        selected_index = 0
        for document in documents:
            label = legal_document_catalog_link_label(document)
            self.document_combo.addItem(label, document.id)
            if selected_id is not None and document.id == selected_id:
                selected_index = self.document_combo.count() - 1
        self.document_combo.setCurrentIndex(selected_index)

    def _selected_document_id(self) -> int | None:
        data = self.document_combo.currentData()
        return int(data) if data is not None else None

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        document_id = self._selected_document_id()
        if document_id is None:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_DOCUMENT_REQUIRED,
            )
            return

        try:
            # R20e.1: pouze předpis; proces se dopočítá přes požadavky předpisu.
            if self.link is None:
                hazard_library_template_legal_link_service.create_link(
                    template_id=self.template_id,
                    legal_document_id=document_id,
                    note=self.note.toPlainText().strip(),
                    active=self.active_checkbox.isChecked(),
                )
            else:
                hazard_library_template_legal_link_service.update_link(
                    self.link.id,
                    template_id=self.template_id,
                    legal_document_id=document_id,
                    note=self.note.toPlainText().strip(),
                    active=self.active_checkbox.isChecked(),
                )
        except HazardLibraryTemplateLegalLinkError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()
