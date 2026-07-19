from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns
from moduly.koordinace_bozp.constants import (
    DEFAULT_ACCIDENT_REPORTING,
    DEFAULT_EMERGENCY_REPORTING,
    DEFAULT_EVACUATION_INSTRUCTIONS,
    DEFAULT_FIRE_REPORTING,
    TAB_CONTACTS,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
    CoordinationContactError,
    coordination_contact_service,
)
from moduly.koordinace_bozp.ui.coordination_contact_dialog import (
    CoordinationContactDialog,
)
from moduly.koordinace_bozp.ui.coordination_contact_table import (
    CoordinationContactTable,
)


class CoordinationContactsTab(QWidget):
    """Záložka kontaktů a postupů při mimořádných událostech (COORD-010)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id

        layout = QVBoxLayout(self)
        self.unavailable_label = QLabel(
            "Kontakty a postupy lze spravovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        contacts_group = QGroupBox("Důležité kontakty")
        contacts_layout = QVBoxLayout(contacts_group)
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.up_btn = QPushButton("Nahoru")
        self.down_btn = QPushButton("Dolů")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.up_btn)
        toolbar.addWidget(self.down_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        contacts_layout.addLayout(toolbar)

        self.table = CoordinationContactTable()
        configure_table_columns(self.table, "coordination_contacts")
        contacts_layout.addWidget(self.table)
        content_layout.addWidget(contacts_group, 1)

        procedures_group = QGroupBox("Dohodnuté postupy")
        procedures_form = QFormLayout(procedures_group)
        self.emergency_reporting = QTextEdit()
        self.accident_reporting = QTextEdit()
        self.fire_reporting = QTextEdit()
        self.evacuation_instructions = QTextEdit()
        for widget in (
            self.emergency_reporting,
            self.accident_reporting,
            self.fire_reporting,
            self.evacuation_instructions,
        ):
            widget.setMinimumHeight(70)
        procedures_form.addRow("Hlášení mimořádné události:", self.emergency_reporting)
        procedures_form.addRow("Hlášení pracovního úrazu:", self.accident_reporting)
        procedures_form.addRow("Hlášení požáru:", self.fire_reporting)
        procedures_form.addRow("Evakuace a shromaždiště:", self.evacuation_instructions)
        content_layout.addWidget(procedures_group, 1)

        layout.addWidget(self.content)

        self.add_btn.clicked.connect(self.add_contact)
        self.edit_btn.clicked.connect(self.edit_selected_contact)
        self.up_btn.clicked.connect(self.move_selected_up)
        self.down_btn.clicked.connect(self.move_selected_down)
        self.activate_btn.clicked.connect(self.activate_selected_contact)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_contact)
        self.table.doubleClicked.connect(self.edit_selected_contact)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh()
        else:
            self.table.setRowCount(0)
            self._clear_procedures()
            self._update_action_buttons()

    def refresh(self) -> None:
        if self.coordination_id is None:
            return
        selected_id = self.table.selected_contact_id()
        contacts = coordination_contact_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.table.load_contacts(contacts)
        configure_table_columns(self.table, "coordination_contacts")
        if selected_id is not None:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and int(item.text()) == selected_id:
                    self.table.selectRow(row)
                    break
            else:
                self.table.clear_selection()
        else:
            self.table.clear_selection()
        self._load_procedures()
        self._update_action_buttons()

    def get_procedures_data(self) -> dict:
        return {
            "emergency_reporting": self.emergency_reporting.toPlainText().strip(),
            "accident_reporting": self.accident_reporting.toPlainText().strip(),
            "fire_reporting": self.fire_reporting.toPlainText().strip(),
            "evacuation_instructions": self.evacuation_instructions.toPlainText().strip(),
        }

    def add_contact(self) -> None:
        if self.coordination_id is None:
            return
        dialog = CoordinationContactDialog(
            self,
            coordination_id=self.coordination_id,
        )
        if not dialog.exec():
            return
        try:
            coordination_contact_service.add(
                self.coordination_id,
                **dialog.get_data(),
            )
        except CoordinationContactError as error:
            QMessageBox.warning(self, TAB_CONTACTS, str(error))
            return
        self.refresh()

    def edit_selected_contact(self) -> None:
        if self.coordination_id is None:
            return
        contact = self._selected_contact()
        if contact is None:
            QMessageBox.information(self, TAB_CONTACTS, "Vyberte kontakt.")
            return
        dialog = CoordinationContactDialog(
            self,
            coordination_id=self.coordination_id,
            contact=contact,
        )
        if not dialog.exec():
            return
        try:
            coordination_contact_service.update(contact.id, **dialog.get_data())
        except CoordinationContactError as error:
            QMessageBox.warning(self, TAB_CONTACTS, str(error))
            return
        self.refresh()

    def move_selected_up(self) -> None:
        contact = self._selected_contact()
        if contact is None:
            return
        if coordination_contact_service.move_up(contact.id):
            self.refresh()

    def move_selected_down(self) -> None:
        contact = self._selected_contact()
        if contact is None:
            return
        if coordination_contact_service.move_down(contact.id):
            self.refresh()

    def activate_selected_contact(self) -> None:
        contact = self._selected_contact()
        if contact is None:
            QMessageBox.information(self, TAB_CONTACTS, "Vyberte kontakt.")
            return
        if contact.active:
            QMessageBox.information(self, TAB_CONTACTS, "Kontakt je již aktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat kontakt „{contact.custom_name}“?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            coordination_contact_service.activate(contact.id)
            self.refresh()

    def deactivate_selected_contact(self) -> None:
        contact = self._selected_contact()
        if contact is None:
            QMessageBox.information(self, TAB_CONTACTS, "Vyberte kontakt.")
            return
        if not contact.active:
            QMessageBox.information(self, TAB_CONTACTS, "Kontakt je již neaktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat kontakt „{contact.custom_name}“?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            coordination_contact_service.deactivate(contact.id)
            self.refresh()

    def _load_procedures(self) -> None:
        if self.coordination_id is None:
            self._clear_procedures()
            return
        coordination = bozp_coordination_service.get_by_id(self.coordination_id)
        if coordination is None:
            self._clear_procedures()
            return
        self.emergency_reporting.setPlainText(
            coordination.emergency_reporting or DEFAULT_EMERGENCY_REPORTING
        )
        self.accident_reporting.setPlainText(
            coordination.accident_reporting or DEFAULT_ACCIDENT_REPORTING
        )
        self.fire_reporting.setPlainText(
            coordination.fire_reporting or DEFAULT_FIRE_REPORTING
        )
        self.evacuation_instructions.setPlainText(
            coordination.evacuation_instructions or DEFAULT_EVACUATION_INSTRUCTIONS
        )

    def _clear_procedures(self) -> None:
        self.emergency_reporting.clear()
        self.accident_reporting.clear()
        self.fire_reporting.clear()
        self.evacuation_instructions.clear()

    def _selected_contact(self):
        contact_id = self.table.selected_contact_id()
        if contact_id is None:
            return None
        return coordination_contact_service.get_by_id(contact_id)

    def _update_action_buttons(self) -> None:
        contact = self._selected_contact()
        has_selection = contact is not None
        self.edit_btn.setEnabled(has_selection)
        self.up_btn.setEnabled(has_selection)
        self.down_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not contact.active)
        self.deactivate_btn.setEnabled(contact.active)
