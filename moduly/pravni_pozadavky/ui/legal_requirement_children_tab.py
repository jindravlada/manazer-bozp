from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.ui.legal_requirement_children_table import (
    LegalRequirementChildrenTable,
)


class LegalRequirementChildrenTab(QWidget):
    def __init__(self, requirement_id: int):
        super().__init__()
        self.requirement_id = requirement_id

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový podřízený proces")
        self.open_btn = QPushButton("Otevřít")
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addStretch()

        self.table = LegalRequirementChildrenTable()

        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.create_child_process)
        self.open_btn.clicked.connect(self.open_selected_child)
        self.table.doubleClicked.connect(self.open_selected_child)

        self.refresh()

    def refresh(self) -> None:
        children = legal_requirement_service.list_children(self.requirement_id)
        self.table.load_children(children)

    def create_child_process(self) -> None:
        from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog

        dialog = LegalRequirementDialog(self, parent_requirement_id=self.requirement_id)
        if exec_maximized(dialog):
            try:
                legal_requirement_service.create_requirement(
                    parent_requirement_id=self.requirement_id,
                    **dialog.get_data(),
                )
            except ValueError as exc:
                QMessageBox.warning(self, "Podřízené procesy", str(exc))
                return
        self.refresh()

    def open_selected_child(self) -> None:
        child_id = self.table.selected_requirement_id()
        if child_id is None:
            QMessageBox.information(self, "Podřízené procesy", "Vyberte podřízený proces.")
            return

        self._open_child_editor(child_id)
        self.refresh()

    def _open_child_editor(self, requirement_id: int) -> None:
        from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog

        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            QMessageBox.warning(self, "Podřízené procesy", "Podřízený proces nebyl nalezen.")
            self.refresh()
            return

        dialog = LegalRequirementDialog(self, requirement=requirement)
        if exec_maximized(dialog):
            try:
                legal_requirement_service.update_requirement(requirement_id, **dialog.get_data())
            except ValueError as exc:
                QMessageBox.warning(self, "Podřízené procesy", str(exc))
                return