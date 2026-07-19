from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_utils import configure_table_columns
from moduly.koordinace_bozp.constants import TAB_EMPLOYER_ACTIVITIES
from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
    CoordinationEmployerActivityError,
    coordination_employer_activity_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.koordinace_bozp.ui.coordination_employer_activity_dialog import (
    CoordinationEmployerActivityDialog,
)
from moduly.koordinace_bozp.ui.coordination_employer_activity_table import (
    CoordinationEmployerActivityTable,
)


class CoordinationEmployerActivitiesTab(QWidget):
    """Záložka činností zúčastněných zaměstnavatelů (COORD-008)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id

        layout = QVBoxLayout(self)

        self.unavailable_label = QLabel(
            "Činnosti zaměstnavatelů lze spravovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        employer_row = QHBoxLayout()
        employer_row.addWidget(QLabel("Zaměstnavatel:"))
        self.employer_combo = QComboBox()
        self.employer_combo.currentIndexChanged.connect(self._on_employer_changed)
        employer_row.addWidget(self.employer_combo, 1)
        content_layout.addLayout(employer_row)

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

        self.table = CoordinationEmployerActivityTable()
        configure_table_columns(self.table, "coordination_employer_activities")
        content_layout.addWidget(self.table)
        layout.addWidget(self.content)

        self.add_btn.clicked.connect(self.add_activity)
        self.edit_btn.clicked.connect(self.edit_selected_activity)
        self.activate_btn.clicked.connect(self.activate_selected_activity)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_activity)
        self.table.doubleClicked.connect(self.edit_selected_activity)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh_employers()
        else:
            self.employer_combo.clear()
            self.table.setRowCount(0)
            self._update_action_buttons()

    def refresh_employers(self) -> None:
        if self.coordination_id is None:
            return
        coordination_employer_service.ensure_main_employer(self.coordination_id)
        previous_id = self.current_employer_id()
        employers = coordination_employer_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.employer_combo.blockSignals(True)
        self.employer_combo.clear()
        for employer in employers:
            label = f"{employer.abbreviation} – {employer.company_name}".strip(" –")
            if not employer.active:
                label = f"{label} (neaktivní)"
            self.employer_combo.addItem(label, employer.id)
        self.employer_combo.blockSignals(False)

        if previous_id is not None:
            index = self.employer_combo.findData(previous_id)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self.refresh_activities()

    def refresh_activities(self) -> None:
        employer_id = self.current_employer_id()
        if employer_id is None:
            self.table.setRowCount(0)
            self._update_action_buttons()
            return
        activities = coordination_employer_activity_service.list_for_employer(
            employer_id,
            include_inactive=True,
        )
        self.table.load_activities(activities)
        configure_table_columns(self.table, "coordination_employer_activities")
        self.table.clear_selection()
        self._update_action_buttons()

    def current_employer_id(self) -> int | None:
        data = self.employer_combo.currentData()
        return int(data) if isinstance(data, int) else None

    def current_employer(self):
        employer_id = self.current_employer_id()
        if employer_id is None:
            return None
        return coordination_employer_service.get_by_id(employer_id)

    def add_activity(self) -> None:
        if self.coordination_id is None:
            return
        employer = self.current_employer()
        if employer is None:
            QMessageBox.information(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "Vyberte zaměstnavatele.",
            )
            return
        if not employer.active:
            QMessageBox.warning(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "K deaktivovanému zaměstnavateli nelze přidat činnost.",
            )
            return
        dialog = CoordinationEmployerActivityDialog(
            self,
            coordination_id=self.coordination_id,
            default_employer_id=employer.id,
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            coordination_employer_activity_service.add(**data)
        except CoordinationEmployerActivityError as error:
            QMessageBox.warning(self, TAB_EMPLOYER_ACTIVITIES, str(error))
            return
        self.refresh_employers()
        created_employer_id = data.get("coordination_employer_id")
        if isinstance(created_employer_id, int):
            index = self.employer_combo.findData(created_employer_id)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self.refresh_activities()

    def edit_selected_activity(self) -> None:
        if self.coordination_id is None:
            return
        activity = self._selected_activity()
        if activity is None:
            QMessageBox.information(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "Vyberte činnost.",
            )
            return
        dialog = CoordinationEmployerActivityDialog(
            self,
            coordination_id=self.coordination_id,
            activity=activity,
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        try:
            coordination_employer_activity_service.update(
                activity.id,
                **data,
            )
        except CoordinationEmployerActivityError as error:
            QMessageBox.warning(self, TAB_EMPLOYER_ACTIVITIES, str(error))
            return
        self.refresh_employers()
        employer_id = data.get("coordination_employer_id")
        if isinstance(employer_id, int):
            index = self.employer_combo.findData(employer_id)
            if index >= 0:
                self.employer_combo.setCurrentIndex(index)
        self.refresh_activities()

    def activate_selected_activity(self) -> None:
        activity = self._selected_activity()
        if activity is None:
            QMessageBox.information(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "Vyberte činnost.",
            )
            return
        if activity.active:
            QMessageBox.information(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "Činnost je již aktivní.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat činnost „{activity.activity_name}“?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        try:
            coordination_employer_activity_service.activate(activity.id)
        except CoordinationEmployerActivityError as error:
            QMessageBox.warning(self, TAB_EMPLOYER_ACTIVITIES, str(error))
            return
        self.refresh_activities()

    def deactivate_selected_activity(self) -> None:
        activity = self._selected_activity()
        if activity is None:
            QMessageBox.information(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "Vyberte činnost.",
            )
            return
        if not activity.active:
            QMessageBox.information(
                self,
                TAB_EMPLOYER_ACTIVITIES,
                "Činnost je již neaktivní.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat činnost „{activity.activity_name}“?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        coordination_employer_activity_service.deactivate(activity.id)
        self.refresh_activities()

    def _on_employer_changed(self) -> None:
        self.refresh_activities()

    def _selected_activity(self):
        activity_id = self.table.selected_activity_id()
        if activity_id is None:
            return None
        return coordination_employer_activity_service.get_by_id(activity_id)

    def _update_action_buttons(self) -> None:
        employer = self.current_employer()
        can_add = employer is not None and bool(employer.active)
        self.add_btn.setEnabled(can_add)

        activity = self._selected_activity()
        has_selection = activity is not None
        self.edit_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not activity.active)
        self.deactivate_btn.setEnabled(activity.active)
