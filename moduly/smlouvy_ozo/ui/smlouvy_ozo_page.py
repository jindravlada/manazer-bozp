"""Seznam smluv OZO."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.smlouvy_ozo.constants import (
    ACTION_CHRONOLOGICAL_LIST,
    ACTION_EDIT,
    ACTION_NEW,
    ACTION_OTHER_CERTIFICATES,
    ACTION_OZO_PERSON,
    DIALOG_TITLE_CHRONOLOGICAL_LIST,
    EMPTY_STATE_TEXT,
    EMPTY_STATE_YEAR_TEXT,
    ITEM_NOT_FOUND_MESSAGE,
    MODULE_NAME,
    OZO_PERSON_MISSING_MESSAGE,
    SHOW_INACTIVE_LABEL,
    YEAR_FILTER_ALL,
    YEAR_REQUIRED_FOR_LIST_MESSAGE,
)
from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
    ozo_contract_list_service,
)
from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
from moduly.smlouvy_ozo.ui.ozo_contract_dialog import OzoContractDialog
from moduly.smlouvy_ozo.ui.ozo_contract_list_dialog import OzoContractListDialog
from moduly.smlouvy_ozo.ui.ozo_contract_table import OzoContractTable
from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog
from moduly.smlouvy_ozo.ui.qualification_certificates_dialog import (
    QualificationCertificatesDialog,
)

class SmlouvyOzoPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dashboard_refresh_callback = None

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(ACTION_NEW)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.ozo_person_btn = QPushButton(ACTION_OZO_PERSON)
        self.other_certificates_btn = QPushButton(ACTION_OTHER_CERTIFICATES)
        self.list_btn = QPushButton(ACTION_CHRONOLOGICAL_LIST)
        self.edit_btn.setEnabled(False)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.ozo_person_btn)
        toolbar.addWidget(self.other_certificates_btn)
        toolbar.addWidget(self.list_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Rok:"))
        self.year_filter = QComboBox()
        toolbar.addWidget(self.year_filter)
        # Výjimečně archivované (active=False) záznamy – ne běžné ukončení smlouvy.
        self.show_inactive = QCheckBox(SHOW_INACTIVE_LABEL)
        toolbar.addWidget(self.show_inactive)

        self.table = OzoContractTable()
        configure_table_columns(self.table, "ozo_contracts")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat ve Smlouvách OZO...")
        self.empty_label = QLabel(EMPTY_STATE_TEXT)
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_contract)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.ozo_person_btn.clicked.connect(self.edit_ozo_person)
        self.other_certificates_btn.clicked.connect(self.open_other_certificates)
        self.list_btn.clicked.connect(self.open_chronological_list)
        self.year_filter.currentIndexChanged.connect(self.refresh)
        self.show_inactive.toggled.connect(self.refresh)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self._populate_year_filter(select_year=date.today().year)
        self.refresh()

    def set_dashboard_refresh_callback(self, callback) -> None:
        self._dashboard_refresh_callback = callback

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._populate_year_filter(select_year=self.selected_year())
        self.refresh()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def selected_year(self) -> int | None:
        data = self.year_filter.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            return None

    def _populate_year_filter(self, *, select_year: int | None = None) -> None:
        previous = select_year if select_year is not None else self.selected_year()
        years = set(ozo_contract_service.available_years())
        years.add(date.today().year)
        ordered = sorted(years, reverse=True)

        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        for year in ordered:
            self.year_filter.addItem(str(year), year)
        self.year_filter.addItem(YEAR_FILTER_ALL, None)

        if previous is not None:
            index = self.year_filter.findData(previous)
            if index >= 0:
                self.year_filter.setCurrentIndex(index)
            else:
                # konkrétní rok – výchozí aktuální
                current_index = self.year_filter.findData(date.today().year)
                self.year_filter.setCurrentIndex(max(0, current_index))
        else:
            # Vše
            all_index = self.year_filter.findData(None)
            if all_index >= 0:
                self.year_filter.setCurrentIndex(all_index)
        self.year_filter.blockSignals(False)
        # Při výběru roku je historie včetně archivovaných – checkbox se nepoužívá.
        year_mode = self.selected_year() is not None
        self.show_inactive.setEnabled(not year_mode)

    def refresh(self) -> None:
        year = self.selected_year()
        if year is not None:
            contracts = ozo_contract_service.list_for_calendar_year(year)
            empty_text = EMPTY_STATE_YEAR_TEXT
        elif self.show_inactive.isChecked():
            contracts = ozo_contract_service.get_all()
            empty_text = EMPTY_STATE_TEXT
        else:
            contracts = ozo_contract_service.get_all(active_only=True)
            empty_text = EMPTY_STATE_TEXT

        self.table.load_contracts(contracts)
        configure_table_columns(self.table, "ozo_contracts")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._refresh_action_buttons()

        if contracts:
            self.empty_label.hide()
            self.table.show()
        else:
            self.empty_label.setText(empty_text)
            self.empty_label.show()
            self.table.hide()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _selected_contract(self):
        contract_id = self.table.selected_contract_id()
        if contract_id is None:
            return None
        return ozo_contract_service.get_by_id(contract_id)

    def _refresh_action_buttons(self, *_args) -> None:
        self.edit_btn.setEnabled(self._selected_contract() is not None)

    def _show_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()
        if self._selected_contract() is None and not index.isValid():
            return
        menu = QMenu(self)
        edit_action = menu.addAction(ACTION_EDIT, self.edit_selected)
        edit_action.setEnabled(self.edit_btn.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(position))

    def edit_ozo_person(self) -> None:
        dialog = OzoPersonDialog(self)
        dialog.exec()
        self._notify_dashboard()

    def open_other_certificates(self) -> None:
        dialog = QualificationCertificatesDialog(self)
        dialog.exec()
        self._notify_dashboard()

    def open_qualification_certificate(self, certificate_id: int) -> None:
        from moduly.smlouvy_ozo.constants import (
            CERTIFICATE_NOT_FOUND_MESSAGE,
            DIALOG_TITLE_OTHER_CERTIFICATES,
        )
        from moduly.smlouvy_ozo.sluzby.qualification_certificate_service import (
            qualification_certificate_service,
        )
        from moduly.smlouvy_ozo.ui.qualification_certificate_dialog import (
            QualificationCertificateDialog,
        )

        certificate = qualification_certificate_service.get_by_id(certificate_id)
        if certificate is None:
            QMessageBox.warning(
                self, DIALOG_TITLE_OTHER_CERTIFICATES, CERTIFICATE_NOT_FOUND_MESSAGE
            )
            return
        dialog = QualificationCertificateDialog(self, certificate=certificate)
        exec_maximized(dialog)
        self._notify_dashboard()

    def open_chronological_list(self) -> None:
        year = self.selected_year()
        if year is None:
            QMessageBox.warning(
                self,
                DIALOG_TITLE_CHRONOLOGICAL_LIST,
                YEAR_REQUIRED_FOR_LIST_MESSAGE,
            )
            return
        missing = ozo_contract_list_service.missing_ozo_fields(year)
        if missing:
            QMessageBox.warning(
                self,
                DIALOG_TITLE_CHRONOLOGICAL_LIST,
                OZO_PERSON_MISSING_MESSAGE.format(
                    items="\n".join(f"• {item}" for item in missing)
                ),
            )
            return
        html = ozo_contract_list_service.build_html(year)
        dialog = OzoContractListDialog(self, year=year, html=html)
        dialog.exec()

    def new_contract(self) -> None:
        dialog = OzoContractDialog(self)
        exec_maximized(dialog)
        self._populate_year_filter(select_year=self.selected_year())
        self.refresh()
        if dialog.contract is not None:
            self._notify_dashboard()

    def edit_selected(self) -> None:
        if self._selected_row_count() != 1:
            return
        contract = self._selected_contract()
        if contract is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = OzoContractDialog(self, contract=contract)
        exec_maximized(dialog)
        self._populate_year_filter(select_year=self.selected_year())
        self.refresh()
        self._notify_dashboard()

    def open_contract(self, contract_id: int) -> None:
        from moduly.smlouvy_ozo.sluzby.ozo_contract_service import relation_date

        contract = ozo_contract_service.get_by_id(contract_id)
        if contract is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        rel = relation_date(contract)
        if rel is not None:
            self._populate_year_filter(select_year=rel.year)
        elif not contract.active:
            index = self.year_filter.findData(None)
            if index >= 0:
                self.year_filter.setCurrentIndex(index)
            self.show_inactive.setChecked(True)
        self.refresh()
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == contract_id:
                self.table.selectRow(row)
                break
        self._refresh_action_buttons()
        dialog = OzoContractDialog(self, contract=contract)
        exec_maximized(dialog)
        self._populate_year_filter(select_year=self.selected_year())
        self.refresh()
        self._notify_dashboard()

    def _notify_dashboard(self) -> None:
        if callable(self._dashboard_refresh_callback):
            self._dashboard_refresh_callback()
