from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.ui.legal_change_dialog import LegalChangeDialog
from moduly.pravni_pozadavky.ui.legal_change_table import LegalChangeTable


class ZmenyLegislativyTab(QWidget):
    """Záložka evidence změn legislativy."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nová změna")
        self.edit_btn = QPushButton("Upravit")
        self.toggle_btn = QPushButton("Deaktivovat")
        self.evaluate_btn = QPushButton("Označit jako vyhodnocené")
        self.unevaluate_btn = QPushButton("Označit jako nevyhodnocené")
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addWidget(self.evaluate_btn)
        toolbar.addWidget(self.unevaluate_btn)
        toolbar.addStretch()

        self.table = LegalChangeTable()
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat změnu...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_change)
        self.edit_btn.clicked.connect(self.edit_selected_change)
        self.toggle_btn.clicked.connect(self.toggle_selected_change)
        self.evaluate_btn.clicked.connect(self.mark_selected_evaluated)
        self.unevaluate_btn.clicked.connect(self.mark_selected_unevaluated)
        self.table.doubleClicked.connect(self.edit_selected_change)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        changes = legal_change_service.list_all(include_inactive=True)
        self.table.load_changes(changes)
        self.text_filter.update_count()
        self._update_action_buttons()

    def _selected_change(self):
        change_id = self.table.selected_change_id()
        if change_id is None:
            return None
        return legal_change_service.get_by_id(change_id)

    def _update_action_buttons(self) -> None:
        change = self._selected_change()
        if change is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not change.active else "Deaktivovat")

    def new_change(self) -> None:
        dialog = LegalChangeDialog(self)
        if not exec_maximized(dialog):
            return
        try:
            legal_change_service.create(**dialog.get_data())
        except ValueError as exc:
            QMessageBox.warning(self, "Změny legislativy", str(exc))
            return
        self.refresh()

    def edit_selected_change(self) -> None:
        change = self._selected_change()
        if change is None:
            QMessageBox.information(self, "Změny legislativy", "Vyberte změnu.")
            return

        dialog = LegalChangeDialog(self, change=change)
        if not exec_maximized(dialog):
            return
        try:
            legal_change_service.update(
                change.id,
                active=change.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Změny legislativy", str(exc))
            return
        self.refresh()

    def toggle_selected_change(self) -> None:
        change = self._selected_change()
        if change is None:
            QMessageBox.information(self, "Změny legislativy", "Vyberte změnu.")
            return

        if change.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat změnu",
                "Opravdu deaktivovat vybranou změnu?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_change_service.deactivate(change.id)
                self.refresh()
            return

        legal_change_service.restore(change.id)
        self.refresh()

    def mark_selected_evaluated(self) -> None:
        change = self._selected_change()
        if change is None:
            QMessageBox.information(self, "Změny legislativy", "Vyberte změnu.")
            return
        legal_change_service.mark_evaluated(change.id)
        self.refresh()

    def mark_selected_unevaluated(self) -> None:
        change = self._selected_change()
        if change is None:
            QMessageBox.information(self, "Změny legislativy", "Vyberte změnu.")
            return
        legal_change_service.mark_unevaluated(change.id)
        self.refresh()
