from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.vysetrovani_mu.constants import (
    DEFAULT_MU_STATUS_FILTER,
    MU_STATUS_BY_FILTER,
    MU_STATUS_DOKONCENO,
    MU_STATUS_FILTER_ODLOZENO,
    MU_STATUS_FILTER_DOKONCENO,
    MU_STATUS_FILTER_PROBIHA,
    MU_STATUS_FILTER_VSE,
    SOURCE_TYPE_ACCIDENT,
    YEAR_FILTER_VSE,
)
from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service
from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog
from moduly.vysetrovani_mu.ui.mu_investigation_table import MuInvestigationTable
from moduly.vysetrovani_mu.ui.mu_sedmero_dialog import MuSedmeroDialog


class VysetrovaniMuPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nové vyšetřování")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Smazat")
        self.sedmero_btn = QPushButton("Sedmero")

        self.status_filter = QComboBox()
        self.status_filter.addItems([
            MU_STATUS_FILTER_PROBIHA,
            MU_STATUS_FILTER_DOKONCENO,
            MU_STATUS_FILTER_ODLOZENO,
            MU_STATUS_FILTER_VSE,
        ])
        self.status_filter.setCurrentText(DEFAULT_MU_STATUS_FILTER)

        self.year_filter = QComboBox()
        self._populate_year_filter()

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.sedmero_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Rok:"))
        toolbar.addWidget(self.year_filter)

        self.table = MuInvestigationTable()
        configure_table_columns(self.table, "mu_investigations")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat vyšetřování...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_investigation)
        self.edit_btn.clicked.connect(self.edit_selected_investigation)
        self.delete_btn.clicked.connect(self.delete_selected_investigation)
        self.sedmero_btn.clicked.connect(self.show_sedmero)
        self.table.doubleClicked.connect(self.edit_selected_investigation)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.year_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def refresh(self):
        investigations = mu_investigation_service.get_all()
        investigations = self._filter_investigations(investigations)
        self.table.load_investigations(investigations)
        configure_table_columns(self.table, "mu_investigations")
        self.text_filter.update_count()

    def _populate_year_filter(self):
        current_year = date.today().year
        years = {current_year}

        for investigation in mu_investigation_service.get_all():
            if investigation.started_at is not None:
                years.add(investigation.started_at.year)

        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        self.year_filter.addItem(str(current_year), current_year)
        for year in sorted(years, reverse=True):
            if year == current_year:
                continue
            self.year_filter.addItem(str(year), year)
        self.year_filter.addItem(YEAR_FILTER_VSE, YEAR_FILTER_VSE)
        self.year_filter.setCurrentIndex(0)
        self.year_filter.blockSignals(False)

    def _filter_investigations(self, investigations):
        mode = self.status_filter.currentText()
        if mode != MU_STATUS_FILTER_VSE:
            status = MU_STATUS_BY_FILTER.get(mode)
            if status is not None:
                investigations = [
                    investigation for investigation in investigations
                    if investigation.status == status
                ]

        year_value = self.year_filter.currentData()
        if year_value != YEAR_FILTER_VSE:
            investigations = [
                investigation for investigation in investigations
                if investigation.started_at is not None and investigation.started_at.year == year_value
            ]

        return investigations

    def _selected_investigation_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None

        return int(item.text())

    def show_sedmero(self):
        MuSedmeroDialog(self).exec()

    def _sync_accident_closed_from_investigation(self, investigation) -> None:
        if (
            investigation is None
            or investigation.source_type != SOURCE_TYPE_ACCIDENT
            or not isinstance(investigation.source_id, int)
            or investigation.source_id <= 0
        ):
            return

        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        should_close = investigation.status == MU_STATUS_DOKONCENO
        accident = accident_service.get_by_id(investigation.source_id)
        if accident is None or getattr(accident, "closed", False) == should_close:
            return

        accident_service.update_accident(investigation.source_id, closed=should_close)

    def new_investigation(self):
        dialog = MuInvestigationDialog(self)
        if exec_maximized(dialog):
            data = dialog.get_data()
            investigation = mu_investigation_service.create_investigation(**data)
            self._sync_accident_closed_from_investigation(investigation)
            self._populate_year_filter()
            self.refresh()

    def edit_selected_investigation(self):
        investigation_id = self._selected_investigation_id()
        if investigation_id is None:
            QMessageBox.information(self, "Vyšetřování MU", "Vyberte vyšetřování.")
            return

        self.open_investigation(investigation_id)

    def open_investigation(self, investigation_id: int):
        investigation = mu_investigation_service.get_by_id(investigation_id)
        if investigation is None:
            QMessageBox.warning(self, "Vyšetřování MU", "Vyšetřování nebylo nalezeno.")
            self.refresh()
            return

        dialog = MuInvestigationDialog(self, investigation=investigation)
        if exec_maximized(dialog):
            data = dialog.get_data()
            updated = mu_investigation_service.update_investigation(investigation_id, **data)
            self._sync_accident_closed_from_investigation(updated)
            if data.get("status") == MU_STATUS_DOKONCENO and self.status_filter.currentText() == MU_STATUS_FILTER_PROBIHA:
                self.status_filter.setCurrentText(MU_STATUS_FILTER_DOKONCENO)
            else:
                self._populate_year_filter()
                self.refresh()

    def open_from_accident(self, accident_id: int) -> None:
        existing = mu_investigation_service.find_by_source(SOURCE_TYPE_ACCIDENT, accident_id)
        if existing is not None:
            self.open_investigation(existing.id)
            return

        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        if accident_service.get_by_id(accident_id) is None:
            QMessageBox.warning(self, "Vyšetřování MU", "Úraz nebyl nalezen.")
            return

        dialog = MuInvestigationDialog(self, accident_id=accident_id)
        if exec_maximized(dialog):
            data = dialog.get_data()
            investigation = mu_investigation_service.create_investigation(**data)
            self._sync_accident_closed_from_investigation(investigation)
            self._populate_year_filter()
            self.refresh()

    def delete_selected_investigation(self):
        investigation_id = self._selected_investigation_id()
        if investigation_id is None:
            QMessageBox.information(self, "Vyšetřování MU", "Vyberte vyšetřování.")
            return

        investigation = mu_investigation_service.get_by_id(investigation_id)
        if investigation is None:
            QMessageBox.warning(self, "Vyšetřování MU", "Vyšetřování nebylo nalezeno.")
            self.refresh()
            return

        answer = QMessageBox.question(
            self,
            "Smazat vyšetřování",
            f"Opravdu smazat vyšetřování {investigation.number or investigation_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            mu_investigation_service.delete_investigation(investigation_id)
            self._populate_year_filter()
            self.refresh()
