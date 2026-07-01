from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.proverky.constants import (
    DEFAULT_INSPECTION_SPIS_STATUS,
    DEFAULT_INSPECTION_TYPE,
    INSPECTION_SPIS_STATUSES,
    INSPECTION_TYPES,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.tymy.sluzby.team_service import INSPECTION_TEAM_TYPE_ID, team_service

_INACTIVE_TEAM_COLOR = QColor("#9ca3af")


class BozpInspectionSpisWidget(QWidget):
    """Záložka Spis — identifikace prověrky BOZP."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.number_header = QLabel("Číslo: —")
        self.number_header.setObjectName("SectionTitle")
        layout.addWidget(self.number_header)

        card = QFrame()
        card.setObjectName("ModulePanel")
        columns = QHBoxLayout(card)
        columns.setContentsMargins(12, 12, 12, 12)
        columns.setSpacing(24)

        left_form = QFormLayout()
        right_form = QFormLayout()

        self.number_label = QLabel("—")
        self.number_label.setObjectName("InfoText")

        self.year_combo = QComboBox()
        self._populate_year_combo()

        self.planned_month_combo = QComboBox()
        self._populate_planned_month_combo()

        self.inspection_date_edit = NullableDateEdit()
        self.started_at_edit = NullableDateEdit()
        self.finished_at_edit = NullableDateEdit()

        self.status_combo = QComboBox()
        self.status_combo.addItems(INSPECTION_SPIS_STATUSES)

        self.type_combo = QComboBox()
        self.type_combo.addItems(INSPECTION_TYPES)

        self.workplace_selector = WorkplaceSelector()

        self.team_combo = QComboBox()
        self.team_combo.currentIndexChanged.connect(self._on_team_changed)

        left_form.addRow("Číslo prověrky:", self.number_label)
        left_form.addRow("Rok:", self.year_combo)
        left_form.addRow("Plánovaný měsíc:", self.planned_month_combo)
        left_form.addRow("Datum prověrky:", self.inspection_date_edit)
        left_form.addRow("Zahájení:", self.started_at_edit)
        left_form.addRow("Ukončení:", self.finished_at_edit)
        left_form.addRow("Stav:", self.status_combo)
        left_form.addRow("Typ prověrky:", self.type_combo)

        right_form.addRow("Pracoviště:", self.workplace_selector)
        right_form.addRow("Prověrková komise:", self.team_combo)

        columns.addLayout(left_form, 1)
        columns.addLayout(right_form, 1)
        layout.addWidget(card)

        self.team_members_panel = QFrame()
        self.team_members_panel.setObjectName("ModulePanel")
        members_layout = QVBoxLayout(self.team_members_panel)
        members_layout.setContentsMargins(12, 10, 12, 10)
        members_layout.setSpacing(6)

        members_header = QLabel("Členové komise")
        members_header.setObjectName("SectionTitle")

        self.team_members_table = QTableWidget()
        self.team_members_table.setColumnCount(4)
        self.team_members_table.setHorizontalHeaderLabels(
            ["Osoba", "Role", "Povinný", "Pořadí"]
        )
        self.team_members_table.setSelectionMode(QTableWidget.NoSelection)
        self.team_members_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.team_members_table.setAlternatingRowColors(True)
        self.team_members_table.verticalHeader().setVisible(False)
        self.team_members_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.team_members_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.team_members_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.team_members_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.team_members_placeholder = QLabel("Vyberte prověrkovou komisi pro zobrazení členů.")
        self.team_members_placeholder.setObjectName("MutedText")
        self.team_members_placeholder.setWordWrap(True)

        members_layout.addWidget(members_header)
        members_layout.addWidget(self.team_members_placeholder)
        members_layout.addWidget(self.team_members_table)
        layout.addWidget(self.team_members_panel)

        self.history_panel = QFrame()
        self.history_panel.setObjectName("ModulePanel")
        history_layout = QVBoxLayout(self.history_panel)
        history_layout.setContentsMargins(12, 10, 12, 10)
        history_layout.setSpacing(4)

        history_header = QLabel("Historie pracoviště")
        history_header.setObjectName("SectionTitle")

        self.history_info_label = QLabel()
        self.history_info_label.setObjectName("InfoText")
        self.history_info_label.setWordWrap(True)

        history_layout.addWidget(history_header)
        history_layout.addWidget(self.history_info_label)
        layout.addWidget(self.history_panel)

        layout.addStretch()

        self._set_defaults()

    def _populate_team_combo(self, include_team_id: int | None = None) -> None:
        self.team_combo.blockSignals(True)
        self.team_combo.clear()
        self.team_combo.addItem("—", None)

        teams = team_service.get_teams_for_selection(
            team_type_id=INSPECTION_TEAM_TYPE_ID,
            include_team_id=include_team_id,
        )
        for team in teams:
            label = team.name
            if not team.active:
                label = f"{label} (neaktivní)"
            self.team_combo.addItem(label, team.id)

        self.team_combo.blockSignals(False)

    def _set_team(self, team_id: int | None) -> None:
        self._populate_team_combo(include_team_id=team_id)
        if team_id is None:
            self.team_combo.setCurrentIndex(0)
            self._refresh_team_members(None)
            return

        index = self.team_combo.findData(team_id)
        if index >= 0:
            self.team_combo.setCurrentIndex(index)
        else:
            self.team_combo.setCurrentIndex(0)
        self._refresh_team_members(team_id)

    def _on_team_changed(self) -> None:
        team_id = self.team_combo.currentData()
        self._refresh_team_members(team_id)

    def _refresh_team_members(self, team_id: int | None) -> None:
        if team_id is None:
            self.team_members_placeholder.setVisible(True)
            self.team_members_table.setVisible(False)
            self.team_members_table.setRowCount(0)
            return

        detail = team_service.get_team_detail(team_id)
        if detail is None:
            self.team_members_placeholder.setText("Vybraný tým nebyl nalezen.")
            self.team_members_placeholder.setVisible(True)
            self.team_members_table.setVisible(False)
            self.team_members_table.setRowCount(0)
            return

        self.team_members_placeholder.setVisible(False)
        self.team_members_table.setVisible(True)
        self.team_members_table.setRowCount(len(detail.members))

        for row, member in enumerate(detail.members):
            values = [
                member.person_name,
                member.role_name,
                "Ano" if member.mandatory else "Ne",
                str(member.display_order),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if not detail.team.active:
                    item.setForeground(QBrush(_INACTIVE_TEAM_COLOR))
                self.team_members_table.setItem(row, column, item)

    def _populate_year_combo(self) -> None:
        current_year = date.today().year

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for year in range(current_year - 2, current_year + 4):
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.blockSignals(False)

    def _populate_planned_month_combo(self) -> None:
        self.planned_month_combo.clear()
        self.planned_month_combo.addItem(PLANNED_MONTH_NOT_SET_LABEL, None)
        for month_number, month_name in enumerate(PLANNED_MONTH_NAMES, start=1):
            self.planned_month_combo.addItem(month_name, month_number)
        self.planned_month_combo.setCurrentIndex(0)

    def _set_defaults(self) -> None:
        self.status_combo.setCurrentText(DEFAULT_INSPECTION_SPIS_STATUS)
        self.type_combo.setCurrentText(DEFAULT_INSPECTION_TYPE)
        self._populate_year_combo()
        self.planned_month_combo.setCurrentIndex(0)
        self._populate_team_combo()
        self._refresh_team_members(None)
        self._set_unsaved_history_placeholder()

    def _set_unsaved_history_placeholder(self) -> None:
        self.history_info_label.setText(
            "Prověrka dosud nebyla uložena.\n\n"
            "Po uložení zde budou zobrazeny základní informace o historii pracoviště — "
            "loňské prověrky, opakující se závady a otevřené úkoly."
        )

    def _set_saved_history_placeholder(self) -> None:
        self.history_info_label.setText(
            "Přehled historie pracoviště bude doplněn po napojení na data prověrek."
        )

    def _set_year(self, year: int) -> None:
        index = self.year_combo.findData(year)
        if index >= 0:
            self.year_combo.setCurrentIndex(index)
            return

        self.year_combo.blockSignals(True)
        self.year_combo.insertItem(0, str(year), year)
        self.year_combo.setCurrentIndex(0)
        self.year_combo.blockSignals(False)

    def _set_planned_month(self, planned_month: int | None) -> None:
        if planned_month is None:
            self.planned_month_combo.setCurrentIndex(0)
            return

        index = self.planned_month_combo.findData(planned_month)
        if index >= 0:
            self.planned_month_combo.setCurrentIndex(index)

    def set_number(self, number: str | None) -> None:
        display = (number or "").strip() or "—"
        self.number_label.setText(display)
        self.number_header.setText(f"Číslo: {display}")

    def load_inspection(self, inspection) -> None:
        if inspection is None:
            return

        self.set_number(getattr(inspection, "number", None))

        status = getattr(inspection, "status", None)
        if status:
            index = self.status_combo.findText(status)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)

        inspection_type = getattr(inspection, "inspection_type", None)
        if inspection_type:
            index = self.type_combo.findText(inspection_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

        year = getattr(inspection, "year", None)
        if year:
            self._set_year(year)

        planned_month = getattr(inspection, "planned_month", None)
        self._set_planned_month(planned_month)

        inspection_date = getattr(inspection, "inspection_date", None)
        if inspection_date is not None:
            self.inspection_date_edit.set_date_value(inspection_date)
        else:
            self.inspection_date_edit.clear_date()

        started_at = getattr(inspection, "started_at", None)
        if started_at is not None:
            self.started_at_edit.set_date_value(started_at)

        finished_at = getattr(inspection, "finished_at", None)
        if finished_at is not None:
            self.finished_at_edit.set_date_value(finished_at)

        workplace_id = getattr(inspection, "workplace_id", None)
        workplace_name = getattr(inspection, "workplace_name", None)
        self.workplace_selector.set_workplace(workplace_id, workplace_name or "")

        team_id = getattr(inspection, "team_id", None)
        self._set_team(team_id)

        self._set_saved_history_placeholder()

    def get_data(self) -> dict:
        return {
            "year": self.year_combo.currentData(),
            "planned_month": self.planned_month_combo.currentData(),
            "inspection_date": self.inspection_date_edit.get_date(),
            "started_at": self.started_at_edit.get_date(),
            "finished_at": self.finished_at_edit.get_date(),
            "status": self.status_combo.currentText(),
            "inspection_type": self.type_combo.currentText(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
            "team_id": self.team_combo.currentData(),
        }
