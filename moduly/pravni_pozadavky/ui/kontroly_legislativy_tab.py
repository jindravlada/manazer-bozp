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
    """Záložka evidence kontrolních běhů změn legislativy."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.perform_check_btn = QPushButton("Provést kontrolu")
        self.open_btn = QPushButton("Otevřít")
        self.toggle_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.perform_check_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addStretch()

        self.table = LegalCheckRunTable()
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat kontrolu...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.perform_check_btn.clicked.connect(self.perform_check)
        self.open_btn.clicked.connect(self.open_selected_run)
        self.toggle_btn.clicked.connect(self.toggle_selected_run)
        self.table.doubleClicked.connect(self.open_selected_run)
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

    def perform_check(self) -> None:
        QMessageBox.information(
            self,
            "Kontroly změn",
            "Provést kontrolu bude dostupné ve fázi 58.",
        )

    def open_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
            QMessageBox.information(self, "Kontroly změn", "Vyberte kontrolu.")
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
            QMessageBox.warning(self, "Kontroly změn", str(exc))
            return
        self.refresh()

    def toggle_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
            QMessageBox.information(self, "Kontroly změn", "Vyberte kontrolu.")
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
