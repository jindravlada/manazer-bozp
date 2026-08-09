"""Seznam smluv OZO."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
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
    ACTION_ACTIVATE,
    ACTION_DEACTIVATE,
    ACTION_EDIT,
    ACTION_NEW,
    EMPTY_STATE_TEXT,
    ITEM_NOT_FOUND_MESSAGE,
    MODULE_NAME,
    SHOW_INACTIVE_LABEL,
)
from moduly.smlouvy_ozo.sluzby.ozo_contract_service import ozo_contract_service
from moduly.smlouvy_ozo.ui.ozo_contract_dialog import OzoContractDialog
from moduly.smlouvy_ozo.ui.ozo_contract_table import OzoContractTable


class SmlouvyOzoPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dashboard_refresh_callback = None

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton(ACTION_NEW)
        self.edit_btn = QPushButton(ACTION_EDIT)
        self.activate_btn = QPushButton(ACTION_ACTIVATE)
        self.deactivate_btn = QPushButton(ACTION_DEACTIVATE)
        self.edit_btn.setEnabled(False)
        self.activate_btn.setEnabled(False)
        self.deactivate_btn.setEnabled(False)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
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
        self.activate_btn.clicked.connect(self.activate_selected)
        self.deactivate_btn.clicked.connect(self.deactivate_selected)
        self.show_inactive.toggled.connect(self.refresh)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def set_dashboard_refresh_callback(self, callback) -> None:
        self._dashboard_refresh_callback = callback

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def refresh(self) -> None:
        if self.show_inactive.isChecked():
            contracts = ozo_contract_service.get_all()
        else:
            contracts = ozo_contract_service.get_all(active_only=True)
        self.table.load_contracts(contracts)
        configure_table_columns(self.table, "ozo_contracts")
        self.table.clear_selection()
        self.text_filter.update_count()
        self._refresh_action_buttons()

        if contracts:
            self.empty_label.hide()
            self.table.show()
        else:
            self.empty_label.setText(EMPTY_STATE_TEXT)
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
        contract = self._selected_contract()
        single = contract is not None
        self.edit_btn.setEnabled(single)
        self.activate_btn.setEnabled(single and not contract.active)
        self.deactivate_btn.setEnabled(single and contract.active)

    def _show_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()
        contract = self._selected_contract()
        single = contract is not None
        if not single and not index.isValid():
            return
        menu = QMenu(self)
        edit_action = menu.addAction(ACTION_EDIT, self.edit_selected)
        edit_action.setEnabled(self.edit_btn.isEnabled())
        activate_action = menu.addAction(ACTION_ACTIVATE, self.activate_selected)
        activate_action.setEnabled(self.activate_btn.isEnabled())
        deactivate_action = menu.addAction(ACTION_DEACTIVATE, self.deactivate_selected)
        deactivate_action.setEnabled(self.deactivate_btn.isEnabled())
        menu.exec(self.table.viewport().mapToGlobal(position))

    def new_contract(self) -> None:
        dialog = OzoContractDialog(self)
        exec_maximized(dialog)
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
        self.refresh()
        self._notify_dashboard()

    def open_contract(self, contract_id: int) -> None:
        contract = ozo_contract_service.get_by_id(contract_id)
        if contract is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        if not contract.active:
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
        self.refresh()
        self._notify_dashboard()

    def activate_selected(self) -> None:
        if not self.activate_btn.isEnabled():
            return
        contract = self._selected_contract()
        if contract is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        ozo_contract_service.activate(contract.id)
        self.refresh()
        self._notify_dashboard()

    def deactivate_selected(self) -> None:
        if not self.deactivate_btn.isEnabled():
            return
        contract = self._selected_contract()
        if contract is None:
            QMessageBox.warning(self, MODULE_NAME, ITEM_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        ozo_contract_service.deactivate(contract.id)
        self.refresh()
        self._notify_dashboard()

    def _notify_dashboard(self) -> None:
        if callable(self._dashboard_refresh_callback):
            self._dashboard_refresh_callback()
