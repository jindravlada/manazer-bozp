from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
from moduly.pravni_pozadavky.constants import (
    CHANGE_EVALUATE_ACTION_LABEL,
    DEFAULT_EVALUATION_FILTER,
    FILTER_EVALUATION_ALL,
    FILTER_EVALUATION_EVALUATED,
    FILTER_EVALUATION_UNEVALUATED,
)
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.ui.legal_change_detail_dialog import LegalChangeDetailDialog
from moduly.pravni_pozadavky.ui.legal_change_table import LegalChangeTable


class ZmenyLegislativyTab(QWidget):
    """Záložka evidence zjištěných změn legislativy."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.open_btn = QPushButton("Otevřít")
        self.toggle_btn = QPushButton("Deaktivovat")
        self.evaluate_btn = QPushButton(CHANGE_EVALUATE_ACTION_LABEL)
        self.open_btn.setEnabled(False)
        self.toggle_btn.setEnabled(False)
        self.evaluate_btn.setEnabled(False)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.toggle_btn)
        toolbar.addWidget(self.evaluate_btn)
        toolbar.addStretch()

        filters_toolbar = QHBoxLayout()
        self.evaluation_filter = QComboBox()
        self.evaluation_filter.addItem(FILTER_EVALUATION_UNEVALUATED, False)
        self.evaluation_filter.addItem(FILTER_EVALUATION_EVALUATED, True)
        self.evaluation_filter.addItem(FILTER_EVALUATION_ALL, None)
        self.evaluation_filter.setCurrentText(DEFAULT_EVALUATION_FILTER)
        filters_toolbar.addWidget(QLabel("Vyhodnocení:"))
        filters_toolbar.addWidget(self.evaluation_filter)
        filters_toolbar.addStretch()

        self.table = LegalChangeTable()
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat změnu...")

        layout.addLayout(toolbar)
        layout.addLayout(filters_toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.open_btn.clicked.connect(self.open_selected_change)
        self.toggle_btn.clicked.connect(self.toggle_selected_change)
        self.evaluate_btn.clicked.connect(self.mark_selected_evaluated)
        self.evaluation_filter.currentIndexChanged.connect(self.refresh)
        self.table.doubleClicked.connect(self.open_selected_change)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def refresh(self) -> None:
        changes = legal_change_service.list_all(include_inactive=True)
        evaluated_mode = self.evaluation_filter.currentData()
        if evaluated_mode is True:
            changes = [item for item in changes if item.evaluated]
        elif evaluated_mode is False:
            changes = [item for item in changes if not item.evaluated]
        self.table.load_changes(changes)
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.text_filter.update_count()
        self._refresh_action_buttons()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _selected_change(self):
        if self._selected_row_count() != 1:
            return None
        change_id = self.table.selected_change_id()
        if change_id is None:
            return None
        return legal_change_service.get_by_id(change_id)

    def _refresh_action_buttons(self, *_args) -> None:
        change = self._selected_change()
        single = change is not None
        self.open_btn.setEnabled(single)
        self.toggle_btn.setEnabled(single)
        self.evaluate_btn.setEnabled(single and not change.evaluated)
        if change is None:
            self.toggle_btn.setText("Deaktivovat")
        else:
            self.toggle_btn.setText("Obnovit" if not change.active else "Deaktivovat")

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        change = self._selected_change()
        single = change is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        open_action = menu.addAction("Otevřít", self.open_selected_change)
        open_action.setEnabled(single)
        toggle_action = menu.addAction(self.toggle_btn.text(), self.toggle_selected_change)
        toggle_action.setEnabled(single)
        evaluate_action = menu.addAction(
            CHANGE_EVALUATE_ACTION_LABEL,
            self.mark_selected_evaluated,
        )
        evaluate_action.setEnabled(single and change is not None and not change.evaluated)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _update_action_buttons(self) -> None:
        # Kompatibilita se staršími voláními / testy.
        self._refresh_action_buttons()

    def open_selected_change(self) -> None:
        change = self._selected_change()
        if change is None:
            return

        dialog = LegalChangeDetailDialog(self, change=change)
        exec_maximized(dialog)
        self.refresh()

    def toggle_selected_change(self) -> None:
        change = self._selected_change()
        if change is None:
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
            return
        if change.evaluated:
            return

        legal_change_service.mark_evaluated(change.id)
        self.refresh()
