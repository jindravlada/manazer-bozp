from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.ui.audit_knowledge_control_process_combo import (
    populate_control_process_combo,
    selected_control_process_id,
)
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_LEGAL_LINK_DIALOG_TITLE,
    HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_REQUIREMENT_REQUIRED,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
    HazardLibraryTemplateLegalLinkError,
    hazard_library_template_legal_link_service,
)


class HazardLibraryTemplateLegalLinkDialog(QDialog):
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
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.requirement_combo = QComboBox()
        self.note = QPlainTextEdit()
        self.note.setMinimumHeight(80)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Právní požadavek *:", self.requirement_combo)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        selected_id = link.legal_requirement_id if link is not None else None
        populate_control_process_combo(self.requirement_combo, selected_id)

        if link is not None:
            self.note.setPlainText(link.note or "")
            self.active_checkbox.setChecked(bool(link.active))

        if read_only:
            self.requirement_combo.setEnabled(False)
            self.note.setReadOnly(True)
            self.active_checkbox.setEnabled(False)
            buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

    def accept(self) -> None:
        if self.read_only:
            super().reject()
            return

        requirement_id = selected_control_process_id(self.requirement_combo)
        if requirement_id is None:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_REQUIREMENT_REQUIRED,
            )
            return

        try:
            if self.link is None:
                hazard_library_template_legal_link_service.create_link(
                    template_id=self.template_id,
                    legal_requirement_id=requirement_id,
                    note=self.note.toPlainText().strip(),
                    active=self.active_checkbox.isChecked(),
                )
            else:
                hazard_library_template_legal_link_service.update_link(
                    self.link.id,
                    template_id=self.template_id,
                    legal_requirement_id=requirement_id,
                    note=self.note.toPlainText().strip(),
                    active=self.active_checkbox.isChecked(),
                )
        except HazardLibraryTemplateLegalLinkError as error:
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return
        super().accept()
