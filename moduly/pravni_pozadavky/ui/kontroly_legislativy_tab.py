from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from moduly.pravni_pozadavky.constants import CHECK_RUN_COMPLETED
from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
from moduly.pravni_pozadavky.ui.legal_check_first_run_dialog import LegalCheckFirstRunDialog
from moduly.pravni_pozadavky.ui.legal_check_progress_dialog import LegalCheckProgressDialog
from moduly.pravni_pozadavky.ui.legal_check_run_dialog import LegalCheckRunDialog
from moduly.pravni_pozadavky.ui.legal_check_run_table import LegalCheckRunTable


def _find_pravni_pozadavky_page(widget):
    from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage

    current = widget
    while current is not None:
        if isinstance(current, PravniPozadavkyPage):
            return current
        current = current.parentWidget()
    return None


class KontrolyLegislativyTab(QWidget):
    """Záložka evidence kontrolních běhů změn legislativy."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.perform_check_btn = QPushButton("Provést kontrolu")
        self.open_btn = QPushButton("Otevřít")
        self.toggle_btn = QPushButton("Deaktivovat")
        self.open_btn.setEnabled(False)
        self.toggle_btn.setEnabled(False)
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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self._recover_stale_runs()
        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        self._recover_stale_runs()
        self.refresh()
        super().showEvent(event)

    def _recover_stale_runs(self) -> None:
        legal_check_run_service.recover_stale_in_progress_runs()

    def refresh(self) -> None:
        runs = legal_check_run_service.list_all(include_inactive=True)
        self.table.load_runs(runs)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.text_filter.update_count()
        self._refresh_action_buttons()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _selected_run(self):
        if self._selected_row_count() != 1:
            return None
        run_id = self.table.selected_run_id()
        if run_id is None:
            return None
        return legal_check_run_service.get_by_id(run_id)

    def _refresh_action_buttons(self, *_args) -> None:
        run = self._selected_run()
        single = run is not None
        self.open_btn.setEnabled(single)
        self.toggle_btn.setEnabled(single)
        if run is None:
            self.toggle_btn.setText("Deaktivovat")
        else:
            self.toggle_btn.setText("Obnovit" if not run.active else "Deaktivovat")

    def _update_action_buttons(self) -> None:
        # Kompatibilita se staršími voláními / testy.
        self._refresh_action_buttons()

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        run = self._selected_run()
        single = run is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        open_action = menu.addAction("Otevřít", self.open_selected_run)
        open_action.setEnabled(single)
        toggle_action = menu.addAction(self.toggle_btn.text(), self.toggle_selected_run)
        toggle_action.setEnabled(single)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def perform_check(self) -> None:
        period_to = date.today()
        last_completed = legal_check_run_service.get_last_completed_run()
        if last_completed is not None:
            period_from = legal_check_run_service.get_run_completion_date(last_completed)
        else:
            dialog = LegalCheckFirstRunDialog(self)
            if not exec_maximized(dialog):
                return
            period_from = dialog.get_period_from()

        progress_dialog = LegalCheckProgressDialog(
            self,
            period_from=period_from,
            period_to=period_to,
        )
        progress_dialog.exec()
        result = progress_dialog.result_data()
        self.refresh()
        if result is None or result.run.status != CHECK_RUN_COMPLETED:
            return

        if result.changes_count > 0:
            page = _find_pravni_pozadavky_page(self)
            if page is not None:
                page.changes_tab.refresh()
                page.tabs.setCurrentWidget(page.changes_tab)

        if result.is_first_check:
            QMessageBox.information(
                self,
                "Kontroly změn",
                (
                    "První kontrola legislativy byla dokončena.\n\n"
                    f"Kontrolováno předpisů: {result.documents_checked_count}\n\n"
                    "Byl vytvořen výchozí referenční stav pro sledování budoucích změn.\n\n"
                    "Budoucí kontroly již budou vyhledávat pouze skutečné změny legislativy."
                ),
            )
            return

        QMessageBox.information(
            self,
            "Kontroly změn",
            (
                "Kontrola změn dokončena.\n"
                f"Kontrolováno předpisů: {result.documents_checked_count}\n"
                f"Nalezené změny: {result.changes_count}"
                + (
                    "\n\nPřejděte na záložku Zjištěné změny."
                    if result.changes_count > 0
                    else ""
                )
            ),
        )

    def open_selected_run(self) -> None:
        run = self._selected_run()
        if run is None:
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
