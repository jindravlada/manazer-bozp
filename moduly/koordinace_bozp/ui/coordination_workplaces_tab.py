from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_header_settings import configure_and_persist_table_columns
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import (
    current_table_row,
    refresh_and_restore_selection,
)
from moduly.koordinace_bozp.constants import COORD_HEADER_WORKPLACES, TAB_WORKPLACES
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    CoordinationWorkplaceError,
    coordination_workplace_service,
)
from moduly.koordinace_bozp.ui.coordination_workplace_dialog import (
    CoordinationWorkplaceDialog,
)
from moduly.koordinace_bozp.ui.coordination_workplace_table import (
    CoordinationWorkplaceTable,
)


class CoordinationWorkplacesTab(QWidget):
    """Záložka míst výkonu práce (COORD-006)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id

        layout = QVBoxLayout(self)
        self.unavailable_label = QLabel(
            "Místa výkonu práce lze spravovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        content_layout.addLayout(toolbar)

        self.table = CoordinationWorkplaceTable()
        configure_and_persist_table_columns(self.table, "coordination_workplaces", COORD_HEADER_WORKPLACES)
        content_layout.addWidget(self.table)
        layout.addWidget(self.content)

        self.add_btn.clicked.connect(self.add_workplace)
        self.edit_btn.clicked.connect(self.edit_selected_workplace)
        self.activate_btn.clicked.connect(self.activate_selected_workplace)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_workplace)
        self.table.doubleClicked.connect(self.edit_selected_workplace)
        install_table_row_actions(
            self.table,
            on_edit=self.edit_selected_workplace,
            on_deactivate=self.deactivate_selected_workplace,
            can_edit=lambda: self.edit_btn.isEnabled(),
            can_deactivate=lambda: self.deactivate_btn.isEnabled(),
        )
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh()
        else:
            self.table.setRowCount(0)
            self._update_action_buttons()

    def refresh(
        self,
        *,
        select_id: int | None = None,
        fallback_row: int | None = None,
        preserve_scroll: bool = False,
        ensure_visible: bool = False,
    ) -> None:
        if self.coordination_id is None:
            return
        scroll_value = (
            self.table.verticalScrollBar().value() if preserve_scroll else None
        )
        record_id = (
            select_id
            if select_id is not None
            else self.table.selected_workplace_link_id()
        )
        workplaces = coordination_workplace_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.table.load_workplaces(workplaces)
        configure_and_persist_table_columns(
            self.table, "coordination_workplaces", COORD_HEADER_WORKPLACES
        )
        refresh_and_restore_selection(
            self.table,
            record_id,
            fallback_row=fallback_row,
            scroll=ensure_visible and not preserve_scroll,
            preserve_scroll_value=scroll_value,
            focus=True,
        )
        self._update_action_buttons()

    def add_workplace(self) -> None:
        if self.coordination_id is None:
            return
        dialog = CoordinationWorkplaceDialog(self)
        if not dialog.exec():
            return
        try:
            created = coordination_workplace_service.add(
                self.coordination_id,
                **dialog.get_data(),
            )
        except CoordinationWorkplaceError as error:
            QMessageBox.warning(self, TAB_WORKPLACES, str(error))
            return
        self.refresh(select_id=created.id, ensure_visible=True)

    def edit_selected_workplace(self) -> None:
        item = self._selected_workplace()
        if item is None:
            QMessageBox.information(self, TAB_WORKPLACES, "Vyberte místo.")
            return
        dialog = CoordinationWorkplaceDialog(self, workplace_link=item)
        if not dialog.exec():
            return
        try:
            coordination_workplace_service.update(item.id, **dialog.get_data())
        except CoordinationWorkplaceError as error:
            QMessageBox.warning(self, TAB_WORKPLACES, str(error))
            return
        self.refresh(select_id=item.id, preserve_scroll=True)

    def activate_selected_workplace(self) -> None:
        item = self._selected_workplace()
        if item is None:
            QMessageBox.information(self, TAB_WORKPLACES, "Vyberte místo.")
            return
        if item.active:
            QMessageBox.information(self, TAB_WORKPLACES, "Místo je již aktivní.")
            return
        try:
            coordination_workplace_service.activate(item.id)
        except CoordinationWorkplaceError as error:
            QMessageBox.warning(self, TAB_WORKPLACES, str(error))
            return
        self.refresh(select_id=item.id, ensure_visible=True)

    def deactivate_selected_workplace(self) -> None:
        item = self._selected_workplace()
        if item is None:
            QMessageBox.information(self, TAB_WORKPLACES, "Vyberte místo.")
            return
        if not item.active:
            QMessageBox.information(self, TAB_WORKPLACES, "Místo je již neaktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            "Opravdu deaktivovat vybrané místo výkonu práce?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            row = current_table_row(self.table)
            coordination_workplace_service.deactivate(item.id)
            self.refresh(
                select_id=item.id,
                fallback_row=row,
                ensure_visible=True,
            )

    def _selected_workplace(self):
        workplace_link_id = self.table.selected_workplace_link_id()
        if workplace_link_id is None:
            return None
        return coordination_workplace_service.get_by_id(workplace_link_id)

    def _update_action_buttons(self) -> None:
        item = self._selected_workplace()
        has_selection = item is not None
        self.edit_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not item.active)
        self.deactivate_btn.setEnabled(item.active)
