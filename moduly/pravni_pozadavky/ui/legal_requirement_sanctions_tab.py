from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.sluzby.legal_requirement_sanction_service import (
    legal_requirement_sanction_service,
)
from moduly.pravni_pozadavky.ui.legal_requirement_sanction_dialog import (
    LegalRequirementSanctionDialog,
)
from moduly.pravni_pozadavky.ui.legal_requirement_sanction_table import (
    LegalRequirementSanctionTable,
)


class LegalRequirementSanctionsTab(QWidget):
    def __init__(self, requirement_id: int | None = None):
        super().__init__()
        self.requirement_id = requirement_id

        layout = QVBoxLayout(self)

        if requirement_id is None:
            layout.addWidget(
                QLabel("Sankce lze přidat až po uložení požadavku."),
            )
            self.table = None
            self.add_btn = None
            self.edit_btn = None
            self.deactivate_btn = None
            return

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()

        self.table = LegalRequirementSanctionTable()

        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_sanction)
        self.edit_btn.clicked.connect(self.edit_selected_sanction)
        self.deactivate_btn.clicked.connect(self.toggle_selected_sanction)
        self.table.doubleClicked.connect(self.edit_selected_sanction)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        if self.table is None or self.requirement_id is None:
            return
        sanctions = legal_requirement_sanction_service.list_by_requirement(
            self.requirement_id,
            include_inactive=True,
        )
        self.table.load_sanctions(sanctions)
        self._update_action_buttons()

    def _selected_sanction(self):
        if self.table is None:
            return None
        sanction_id = self.table.selected_sanction_id()
        if sanction_id is None:
            return None
        return legal_requirement_sanction_service.get_by_id(sanction_id)

    def _update_action_buttons(self) -> None:
        if self.deactivate_btn is None:
            return
        sanction = self._selected_sanction()
        if sanction is None:
            self.deactivate_btn.setText("Deaktivovat")
            return
        self.deactivate_btn.setText("Obnovit" if not sanction.active else "Deaktivovat")

    def add_sanction(self) -> None:
        if self.requirement_id is None:
            return

        dialog = LegalRequirementSanctionDialog(self)
        if not exec_maximized(dialog):
            return

        try:
            legal_requirement_sanction_service.create(
                requirement_id=self.requirement_id,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Sankce", str(exc))
            return

        self.refresh()

    def edit_selected_sanction(self) -> None:
        sanction = self._selected_sanction()
        if sanction is None:
            QMessageBox.information(self, "Sankce", "Vyberte sankci.")
            return

        dialog = LegalRequirementSanctionDialog(self, sanction=sanction)
        if not exec_maximized(dialog):
            return

        try:
            legal_requirement_sanction_service.update(
                sanction.id,
                active=sanction.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Sankce", str(exc))
            return

        self.refresh()

    def toggle_selected_sanction(self) -> None:
        sanction = self._selected_sanction()
        if sanction is None:
            QMessageBox.information(self, "Sankce", "Vyberte sankci.")
            return

        if sanction.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat sankci",
                "Opravdu deaktivovat vybranou sankci?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_requirement_sanction_service.deactivate(sanction.id)
                self.refresh()
            return

        legal_requirement_sanction_service.restore(sanction.id)
        self.refresh()
