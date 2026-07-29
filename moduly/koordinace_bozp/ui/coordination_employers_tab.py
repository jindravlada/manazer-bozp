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
from moduly.koordinace_bozp.constants import COORD_HEADER_EMPLOYERS, TAB_EMPLOYERS
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    CoordinationEmployerError,
    coordination_employer_service,
    employer_abbreviation,
)
from moduly.koordinace_bozp.ui.coordination_employer_dialog import (
    CoordinationEmployerDialog,
)
from moduly.koordinace_bozp.ui.coordination_employer_table import (
    CoordinationEmployerTable,
)
from moduly.koordinace_bozp.ui.coordination_tab_edit_policy import (
    CoordinationTabEditPolicyMixin,
)


class CoordinationEmployersTab(CoordinationTabEditPolicyMixin, QWidget):
    """Záložka zúčastněných zaměstnavatelů (COORD-002)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._content_editable = True
        self._before_mutate = None

        layout = QVBoxLayout(self)

        self.unavailable_label = QLabel(
            "Zúčastněné zaměstnavatele lze spravovat po uložení koordinace."
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

        self.table = CoordinationEmployerTable()
        configure_and_persist_table_columns(self.table, "coordination_employers", COORD_HEADER_EMPLOYERS)
        content_layout.addWidget(self.table)
        layout.addWidget(self.content)

        self.add_btn.clicked.connect(self.add_employer)
        self.edit_btn.clicked.connect(self.edit_selected_employer)
        self.activate_btn.clicked.connect(self.activate_selected_employer)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_employer)
        self.table.doubleClicked.connect(self.edit_selected_employer)
        install_table_row_actions(
            self.table,
            on_edit=self.edit_selected_employer,
            on_deactivate=self.deactivate_selected_employer,
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
            else self.table.selected_employer_id()
        )
        coordination_employer_service.ensure_main_employer(self.coordination_id)
        employers = coordination_employer_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.table.load_employers(employers)
        configure_and_persist_table_columns(
            self.table, "coordination_employers", COORD_HEADER_EMPLOYERS
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

    def add_employer(self) -> None:
        if self.coordination_id is None or not self.allow_mutate():
            return
        dialog = CoordinationEmployerDialog(self)
        if not dialog.exec():
            return
        try:
            created = coordination_employer_service.add_participant(
                self.coordination_id,
                **dialog.get_data(),
            )
        except CoordinationEmployerError as error:
            QMessageBox.warning(self, TAB_EMPLOYERS, str(error))
            return
        self.refresh(select_id=created.id, ensure_visible=True)

    def edit_selected_employer(self) -> None:
        if not self.allow_mutate():
            return
        employer = self._selected_employer()
        if employer is None:
            QMessageBox.information(self, TAB_EMPLOYERS, "Vyberte zaměstnavatele.")
            return
        dialog = CoordinationEmployerDialog(self, employer=employer)
        if not dialog.exec():
            return
        try:
            coordination_employer_service.update_employer(
                employer.id,
                **dialog.get_data(),
            )
        except CoordinationEmployerError as error:
            QMessageBox.warning(self, TAB_EMPLOYERS, str(error))
            return
        self.refresh(select_id=employer.id, preserve_scroll=True)

    def activate_selected_employer(self) -> None:
        if not self.allow_mutate():
            return
        employer = self._selected_employer()
        if employer is None:
            QMessageBox.information(self, TAB_EMPLOYERS, "Vyberte zaměstnavatele.")
            return
        if employer.active:
            QMessageBox.information(self, TAB_EMPLOYERS, "Zaměstnavatel je již aktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat zaměstnavatele "
            f"{employer_abbreviation(employer) or employer.company_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            coordination_employer_service.activate(employer.id)
            self.refresh(select_id=employer.id, ensure_visible=True)

    def deactivate_selected_employer(self) -> None:
        if not self.allow_mutate():
            return
        employer = self._selected_employer()
        if employer is None:
            QMessageBox.information(self, TAB_EMPLOYERS, "Vyberte zaměstnavatele.")
            return
        if employer.is_main:
            QMessageBox.warning(
                self,
                TAB_EMPLOYERS,
                "Hlavního zaměstnavatele nelze deaktivovat ani odstranit.",
            )
            return
        if not employer.active:
            QMessageBox.information(
                self,
                TAB_EMPLOYERS,
                "Zaměstnavatel je již neaktivní.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat zaměstnavatele "
            f"{employer_abbreviation(employer) or employer.company_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            row = current_table_row(self.table)
            coordination_employer_service.deactivate(employer.id)
        except CoordinationEmployerError as error:
            QMessageBox.warning(self, TAB_EMPLOYERS, str(error))
            return
        self.refresh(
            select_id=employer.id,
            fallback_row=row,
            ensure_visible=True,
        )

    def _selected_employer(self):
        employer_id = self.table.selected_employer_id()
        if employer_id is None:
            return None
        return coordination_employer_service.get_by_id(employer_id)

    def _update_action_buttons(self) -> None:
        if not getattr(self, "_content_editable", True):
            self.add_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        employer = self._selected_employer()
        has_selection = employer is not None
        self.add_btn.setEnabled(self.coordination_id is not None)
        self.edit_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not employer.active and not employer.is_main)
        self.deactivate_btn.setEnabled(employer.active and not employer.is_main)
