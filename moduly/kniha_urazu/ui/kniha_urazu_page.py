from PySide6.QtCore import Qt
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
from moduly.kniha_urazu.sluzby.accident_service import accident_service
from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
from moduly.kniha_urazu.ui.accident_summary_panel import AccidentSummaryPanel
from moduly.kniha_urazu.ui.accident_table import AccidentTable
from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
from moduly.kniha_urazu.ui.union_notice_dialog import UnionNoticeDialog
from moduly.kniha_urazu.sluzby.zaverecna_zprava_service import zaverecna_zprava_service
from moduly.kniha_urazu.sluzby.vypis_urazu_service import vypis_urazu_service


class KnihaUrazuPage(QWidget):
    def __init__(self, open_mu_investigation_callback=None):
        super().__init__()

        self.open_mu_investigation_callback = open_mu_investigation_callback

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nový úraz")
        self.edit_btn = QPushButton("Upravit")
        self.notice_btn = QPushButton("Ohláška OO")
        self.investigation_btn = QPushButton("Ohlašovací povinnosti")
        self.mu_investigation_btn = QPushButton("Vyšetřování MU")
        self.vypis_btn = QPushButton("Výpis o pracovním úrazu")
        self.final_report_btn = QPushButton("Závěrečná zpráva")

        self._selection_action_buttons = (
            self.edit_btn,
            self.notice_btn,
            self.investigation_btn,
            self.mu_investigation_btn,
            self.vypis_btn,
            self.final_report_btn,
        )
        for button in self._selection_action_buttons:
            button.setEnabled(False)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.notice_btn)
        toolbar.addWidget(self.investigation_btn)
        toolbar.addWidget(self.mu_investigation_btn)
        toolbar.addWidget(self.vypis_btn)
        toolbar.addWidget(self.final_report_btn)
        toolbar.addStretch()

        self.table = AccidentTable()
        self.text_filter = FilterBar(self.table)
        self.summary_panel = AccidentSummaryPanel()

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.addWidget(self.text_filter, 1)
        filter_row.addWidget(self.summary_panel)

        layout.addLayout(toolbar)
        layout.addLayout(filter_row)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_accident)
        self.edit_btn.clicked.connect(self.edit_selected_accident)
        self.notice_btn.clicked.connect(self.open_union_notice)
        self.investigation_btn.clicked.connect(lambda: self.open_investigation())
        self.mu_investigation_btn.clicked.connect(lambda: self.open_mu_investigation())
        self.vypis_btn.clicked.connect(self.generate_accident_report)
        self.final_report_btn.clicked.connect(self.generate_final_report)
        self.table.doubleClicked.connect(self.edit_selected_accident)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def refresh(self):
        accidents = accident_service.get_all()
        self.table.load_accidents(accidents)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.configure_columns()
        self.summary_panel.update_summary(self.table.compute_summary(accidents))

        self.text_filter.update_count()
        self._refresh_action_buttons()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        # Akce nad jedním záznamem; vícenásobný výběr žádná nepodporuje.
        enabled = self._selected_row_count() == 1
        for button in self._selection_action_buttons:
            button.setEnabled(enabled)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        enabled = self._selected_row_count() == 1
        if not enabled and not index.isValid():
            return

        menu = QMenu(self)
        actions = (
            (self.edit_btn.text(), self.edit_selected_accident),
            (self.notice_btn.text(), self.open_union_notice),
            (self.investigation_btn.text(), lambda: self.open_investigation()),
            (self.mu_investigation_btn.text(), lambda: self.open_mu_investigation()),
            (self.vypis_btn.text(), self.generate_accident_report),
            (self.final_report_btn.text(), self.generate_final_report),
        )
        for label, slot in actions:
            action = menu.addAction(label, slot)
            action.setEnabled(enabled)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _selected_accident_id(self):
        if self._selected_row_count() != 1:
            return None

        selected = self.table.selectionModel().selectedRows()
        item = self.table.item(selected[0].row(), 1)
        return int(item.text()) if item else None

    def open_union_notice(self) -> None:
        accident_id = self._selected_accident_id()
        if accident_id is None:
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Ohláška OO", "Úraz nebyl nalezen.")
            self.refresh()
            return

        dialog = UnionNoticeDialog(self, accident=accident)
        dialog.exec()

    def new_accident(self):
        dialog = AccidentDialog(self)
        if exec_maximized(dialog):
            data = dialog.get_data()
            if data["jmeno_prijmeni"] or data["popis_urazoveho_deje"]:
                accident_service.create_accident(**data)
                self.refresh()

    def edit_selected_accident(self):
        accident_id = self._selected_accident_id()
        if accident_id is None:
            return

        self.open_accident(accident_id)

    def _select_accident(self, accident_id: int) -> bool:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item is None:
                continue
            try:
                if int(item.text()) == accident_id:
                    self.table.selectRow(row)
                    self.table.setCurrentCell(row, 0)
                    return True
            except ValueError:
                continue
        return False

    def open_accident(self, accident_id: int, focus_tab: str | None = None):
        self._select_accident(accident_id)

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Kniha úrazů", "Úraz nebyl nalezen.")
            self.refresh()
            return

        dialog = AccidentDialog(self, accident=accident, focus_tab=focus_tab)
        if exec_maximized(dialog):
            data = dialog.get_data()
            accident_service.update_accident(accident_id, **data)
            self.refresh()

    def generate_accident_report(self):
        accident_id = self._selected_accident_id()
        if accident_id is None:
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Výpis o pracovním úrazu", "Úraz nebyl nalezen.")
            self.refresh()
            return

        try:
            vypis_urazu_service.open_for_accident(
                accident,
                confirm_replace_custom=self._confirm_replace_vypis_template,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Výpis o pracovním úrazu",
                f"Výpis o pracovním úrazu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _confirm_replace_vypis_template(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Výpis o pracovním úrazu")
        box.setText(
            "Používá se uživatelsky upravená nebo starší šablona Výpisu "
            "o pracovním úrazu. Novou výchozí šablonu nelze použít automaticky."
        )
        box.setInformativeText(
            "Chcete nyní použít novou výchozí šablonu?\n"
            "Původní soubor se před nahrazením zálohuje."
        )
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_button = box.button(QMessageBox.StandardButton.Yes)
        no_button = box.button(QMessageBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText("Ano")
        if no_button is not None:
            no_button.setText("Ne")
        return box.exec() == QMessageBox.StandardButton.Yes

    def generate_final_report(self):
        accident_id = self._selected_accident_id()
        if accident_id is None:
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Závěrečná zpráva", "Úraz nebyl nalezen.")
            self.refresh()
            return

        try:
            zaverecna_zprava_service.open_for_accident(accident)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Závěrečná zpráva",
                f"Závěrečnou zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def open_investigation(
        self,
        accident_id: int | None = None,
        focus_obligation_key: str | None = None,
    ):
        if accident_id is None:
            accident_id = self._selected_accident_id()
        if accident_id is None:
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Ohlašovací povinnosti", "Úraz nebyl nalezen.")
            self.refresh()
            return

        accident_id = accident.id
        dialog = SetreniDialog(
            self,
            accident=accident,
            focus_obligation_key=focus_obligation_key,
        )
        exec_maximized(dialog)
        self.refresh()
        if dialog.open_mu_after_close:
            self.open_mu_investigation(accident_id)

    def open_mu_investigation(self, accident_id: int | None = None):
        if type(accident_id) is not int:
            accident_id = self._selected_accident_id()
        if accident_id is None:
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Vyšetřování MU", "Úraz nebyl nalezen.")
            self.refresh()
            return

        if self.open_mu_investigation_callback is None:
            QMessageBox.warning(
                self,
                "Vyšetřování MU",
                "Modul Vyšetřování MU není dostupný.",
            )
            return

        self.open_mu_investigation_callback(accident_id)
