from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
from moduly.pravni_pozadavky.ui.legal_check_run_dialog import LegalCheckRunDialog
from moduly.pravni_pozadavky.ui.legal_check_run_table import LegalCheckRunTable


class KontrolyLegislativyTab(QWidget):
    """Záložka evidence kontrolních běhů legislativy."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nová kontrola")
        self.edit_btn = QPushButton("Upravit")
        self.toggle_btn = QPushButton("Deaktivovat")
        self.start_btn = QPushButton("Zahájit")
        self.complete_btn = QPushButton("Dokončit")
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addWidget(self.start_btn)
        toolbar.addWidget(self.complete_btn)
        toolbar.addStretch()

        self.table = LegalCheckRunTable()
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat kontrolu...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_run)
        self.edit_btn.clicked.connect(self.edit_selected_run)
        self.toggle_btn.clicked.connect(self.toggle_selected_run)
        self.start_btn.clicked.connect(self.start_selected_run)
        self.complete_btn.clicked.connect(self.complete_selected_run)
        self.table.doubleClicked.connect(self.edit_selected_run)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        runs = legal_check_run_service.list_all(include_inactive=True)
        self.table.load_runs(runs)
        self.text_filter.update_count()
        self._update_action_buttons()

    def _selected_run(self):
        run_id = self.table.selected_run_id()
        if run_id is None:
            return None
        return legal_check_run_service.get_by_id(run_id)

    def _update_action_buttons(self) -> None:
        run = self._selected_run()
        if run is None:
            self.toggle_btn.setText("Deaktivovat")
            return
        self.toggle_btn.setText("Obnovit" if not run.active else "Deaktivovat")

    def new_run(self) -> None:
        dialog = LegalCheckRunDialog(self)
        if not exec_maximized(dialog):
            return
        try:
            legal_check_run_service.create(**dialog.get_data())
        except ValueError as exc:
            QMessageBox.warning(self, "Kontroly legislativy", str(exc))
            return
        self.refresh()

    def edit_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
            QMessageBox.information(self, "Kontroly legislativy", "Vyberte kontrolu.")
            return

        dialog = LegalCheckRunDialog(self, run=run)
        if not exec_maximized(dialog):
            return
        try:
            legal_check_run_service.update(
                run.id,
                active=run.active,
                **dialog.get_data(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Kontroly legislativy", str(exc))
            return
        self.refresh()

    def toggle_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
            QMessageBox.information(self, "Kontroly legislativy", "Vyberte kontrolu.")
            return

        if run.active:
            answer = QMessageBox.question(
                self,
                "Deaktivovat kontrolu",
                "Opravdu deaktivovat vybranou kontrolu?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_check_run_service.deactivate(run.id)
                self.refresh()
            return

        legal_check_run_service.restore(run.id)
        self.refresh()

    def start_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
            QMessageBox.information(self, "Kontroly legislativy", "Vyberte kontrolu.")
            return
        legal_check_run_service.start_run(run.id)
        self.refresh()

    def complete_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
            QMessageBox.information(self, "Kontroly legislativy", "Vyberte kontrolu.")
            return
        legal_check_run_service.complete_run(run.id)
        self.refresh()
