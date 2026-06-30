from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from moduly.kniha_urazu.sluzby.accident_service import accident_service
from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
from moduly.kniha_urazu.ui.accident_summary_panel import AccidentSummaryPanel
from moduly.kniha_urazu.ui.accident_table import AccidentTable
from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
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
        self.investigation_btn = QPushButton("Šetření úrazu")
        self.mu_investigation_btn = QPushButton("Vyšetřování MU")
        self.vypis_btn = QPushButton("Výpis o pracovním úrazu")
        self.final_report_btn = QPushButton("Závěrečná zpráva")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
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
        self.investigation_btn.clicked.connect(lambda: self.open_investigation())
        self.mu_investigation_btn.clicked.connect(self.open_mu_investigation)
        self.vypis_btn.clicked.connect(self.generate_accident_report)
        self.final_report_btn.clicked.connect(self.generate_final_report)
        self.table.doubleClicked.connect(self.edit_selected_accident)

        self.refresh()

    def refresh(self):
        accidents = accident_service.get_all()
        self.table.load_accidents(accidents)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.table.configure_columns()
        self.summary_panel.update_summary(self.table.compute_summary(accidents))

        self.text_filter.update_count()

    def _selected_accident_id(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 1)
        return int(item.text()) if item else None

    def new_accident(self):
        dialog = AccidentDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["jmeno_prijmeni"] or data["popis_urazoveho_deje"]:
                accident_service.create_accident(**data)
                self.refresh()

    def edit_selected_accident(self):
        accident_id = self._selected_accident_id()
        if accident_id is None:
            QMessageBox.information(self, "Kniha úrazů", "Vyberte úraz.")
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

    def open_accident(self, accident_id: int):
        self._select_accident(accident_id)

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Kniha úrazů", "Úraz nebyl nalezen.")
            self.refresh()
            return

        dialog = AccidentDialog(self, accident=accident)
        if dialog.exec():
            data = dialog.get_data()
            accident_service.update_accident(accident_id, **data)
            self.refresh()

    def generate_accident_report(self):
        accident_id = self._selected_accident_id()
        if accident_id is None:
            QMessageBox.information(self, "Výpis o pracovním úrazu", "Vyberte úraz.")
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Výpis o pracovním úrazu", "Úraz nebyl nalezen.")
            self.refresh()
            return

        try:
            vypis_urazu_service.open_for_accident(accident)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Výpis o pracovním úrazu",
                f"Výpis o pracovním úrazu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def generate_final_report(self):
        accident_id = self._selected_accident_id()
        if accident_id is None:
            QMessageBox.information(self, "Závěrečná zpráva", "Vyberte úraz.")
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

    def open_investigation(self, accident_id: int | None = None):
        # TODO: Cílově bude proces šetření úrazu nahrazen modulem Vyšetřování MU.
        if accident_id is None:
            accident_id = self._selected_accident_id()
        if accident_id is None:
            QMessageBox.information(self, "Šetření úrazu", "Vyberte úraz.")
            return

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            QMessageBox.warning(self, "Šetření úrazu", "Úraz nebyl nalezen.")
            self.refresh()
            return

        dialog = SetreniDialog(self, accident=accident)
        dialog.exec()
        self.refresh()

    def open_mu_investigation(self, accident_id: int | None = None):
        if accident_id is None:
            accident_id = self._selected_accident_id()
        if accident_id is None:
            QMessageBox.information(self, "Vyšetřování MU", "Vyberte úraz.")
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
