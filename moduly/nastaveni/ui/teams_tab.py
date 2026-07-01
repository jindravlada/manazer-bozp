from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.tymy.repository.team_member_repository import TeamMemberRepository
from moduly.tymy.sluzby.team_service import team_service
from moduly.tymy.ui.team_dialog import TeamDialog
from moduly.tymy.ui.team_member_dialog import TeamMemberDialog

_INACTIVE_COLOR = QColor("#9ca3af")


class TeamsTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._current_team_id: int | None = None

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([420, 680])

        layout.addWidget(splitter)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)

        toolbar = QHBoxLayout()

        self.add_team_button = QPushButton("Přidat tým")
        self.add_team_button.clicked.connect(self.add_team)

        self.edit_team_button = QPushButton("Upravit tým")
        self.edit_team_button.clicked.connect(self.edit_selected_team)

        self.deactivate_team_button = QPushButton("Deaktivovat tým")
        self.deactivate_team_button.clicked.connect(self.deactivate_selected_team)

        toolbar.addWidget(self.add_team_button)
        toolbar.addWidget(self.edit_team_button)
        toolbar.addWidget(self.deactivate_team_button)
        toolbar.addStretch()

        self.team_table = QTableWidget()
        self.team_table.setColumnCount(4)
        self.team_table.setHorizontalHeaderLabels(["ID", "Název", "Typ týmu", "Aktivní"])
        self.team_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.team_table.setSelectionMode(QTableWidget.SingleSelection)
        self.team_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.team_table.doubleClicked.connect(self.edit_selected_team)
        self.team_table.itemSelectionChanged.connect(self._on_team_selection_changed)
        configure_table_columns(self.team_table, "teams")

        self.team_filter = FilterBar(self.team_table)

        panel_layout.addLayout(toolbar)
        panel_layout.addWidget(self.team_filter)
        panel_layout.addWidget(self.team_table)

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)

        self.detail_placeholder = QLabel("Vyberte tým ze seznamu vlevo.")
        self.detail_placeholder.setObjectName("MutedText")
        self.detail_placeholder.setWordWrap(True)

        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.detail_title = QLabel()
        self.detail_title.setObjectName("SectionTitle")

        form = QFormLayout()
        self.detail_name = QLabel()
        self.detail_description = QLabel()
        self.detail_description.setWordWrap(True)
        self.detail_team_type = QLabel()
        self.detail_active = QLabel()
        self.detail_valid_from = QLabel()
        self.detail_valid_to = QLabel()

        form.addRow("Název:", self.detail_name)
        form.addRow("Popis:", self.detail_description)
        form.addRow("Typ týmu:", self.detail_team_type)
        form.addRow("Aktivní:", self.detail_active)
        form.addRow("Platnost od:", self.detail_valid_from)
        form.addRow("Platnost do:", self.detail_valid_to)

        members_label = QLabel("Členové týmu")
        members_label.setObjectName("SectionTitle")

        members_toolbar = QHBoxLayout()
        self.add_member_button = QPushButton("Přidat člena")
        self.edit_member_button = QPushButton("Upravit člena")
        self.remove_member_button = QPushButton("Odebrat člena")
        self.move_member_up_button = QPushButton("Nahoru")
        self.move_member_down_button = QPushButton("Dolů")

        self.add_member_button.clicked.connect(self.add_member)
        self.edit_member_button.clicked.connect(self.edit_member)
        self.remove_member_button.clicked.connect(self.remove_member)
        self.move_member_up_button.clicked.connect(lambda: self.move_member(-1))
        self.move_member_down_button.clicked.connect(lambda: self.move_member(1))

        members_toolbar.addWidget(self.add_member_button)
        members_toolbar.addWidget(self.edit_member_button)
        members_toolbar.addWidget(self.remove_member_button)
        members_toolbar.addWidget(self.move_member_up_button)
        members_toolbar.addWidget(self.move_member_down_button)
        members_toolbar.addStretch()

        self.member_table = QTableWidget()
        self.member_table.setColumnCount(5)
        self.member_table.setHorizontalHeaderLabels(
            ["ID", "Osoba", "Role", "Povinný", "Pořadí"]
        )
        self.member_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.member_table.setSelectionMode(QTableWidget.SingleSelection)
        self.member_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.member_table.doubleClicked.connect(self.edit_member)
        configure_table_columns(self.member_table, "team_members")

        detail_layout.addWidget(self.detail_title)
        detail_layout.addLayout(form)
        detail_layout.addWidget(members_label)
        detail_layout.addLayout(members_toolbar)
        detail_layout.addWidget(self.member_table)

        panel_layout.addWidget(self.detail_placeholder)
        panel_layout.addWidget(self.detail_widget)
        self.detail_widget.hide()

        return panel

    def refresh(self) -> None:
        selected_id = self._selected_team_id()
        teams = team_service.get_all_teams()

        self.team_table.setRowCount(len(teams))
        selected_row = -1

        for row, team in enumerate(teams):
            self.team_table.setItem(row, 0, QTableWidgetItem(str(team.id)))
            self.team_table.setItem(row, 1, QTableWidgetItem(team.name))
            self.team_table.setItem(row, 2, QTableWidgetItem(team.team_type_name))
            active_text = "Ano" if team.active else "Ne"
            self.team_table.setItem(row, 3, QTableWidgetItem(active_text))

            if not team.active:
                for column in range(4):
                    item = self.team_table.item(row, column)
                    if item is not None:
                        item.setForeground(QBrush(_INACTIVE_COLOR))

            if team.id == selected_id:
                selected_row = row

        configure_table_columns(self.team_table, "teams")
        self.team_filter.update_count()

        if selected_row >= 0:
            self.team_table.selectRow(selected_row)
        elif teams:
            self.team_table.selectRow(0)
        else:
            self._current_team_id = None
            self._show_detail(None)

        self._update_team_buttons()

    def _selected_team_id(self) -> int | None:
        selected = self.team_table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.team_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _selected_member_id(self) -> int | None:
        selected = self.member_table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.member_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def _on_team_selection_changed(self) -> None:
        team_id = self._selected_team_id()
        self._current_team_id = team_id
        detail = team_service.get_team_detail(team_id) if team_id is not None else None
        self._show_detail(detail)
        self._update_team_buttons()

    def _show_detail(self, detail) -> None:
        if detail is None:
            self.detail_placeholder.show()
            self.detail_widget.hide()
            return

        team = detail.team
        self.detail_placeholder.hide()
        self.detail_widget.show()

        self.detail_title.setText(team.name)
        self.detail_name.setText(team.name)
        self.detail_description.setText(team.description or "—")
        self.detail_team_type.setText(team.team_type_name or "—")

        if team.active:
            self.detail_active.setText("Ano")
            self.detail_active.setStyleSheet("")
        else:
            self.detail_active.setText("Ne (neaktivní)")
            self.detail_active.setStyleSheet("color: #9ca3af; font-weight: bold;")

        self.detail_valid_from.setText(self._format_date(team.valid_from))
        self.detail_valid_to.setText(self._format_date(team.valid_to) if team.valid_to else "—")

        self.member_table.setRowCount(len(detail.members))
        for row, member in enumerate(detail.members):
            self.member_table.setItem(row, 0, QTableWidgetItem(str(member.id)))
            self.member_table.setItem(row, 1, QTableWidgetItem(member.person_name))
            self.member_table.setItem(row, 2, QTableWidgetItem(member.role_name))
            self.member_table.setItem(
                row, 3, QTableWidgetItem("Ano" if member.mandatory else "Ne")
            )
            self.member_table.setItem(row, 4, QTableWidgetItem(str(member.display_order)))

        configure_table_columns(self.member_table, "team_members")

        members_enabled = team.active
        for button in (
            self.add_member_button,
            self.edit_member_button,
            self.remove_member_button,
            self.move_member_up_button,
            self.move_member_down_button,
        ):
            button.setEnabled(members_enabled)

    @staticmethod
    def _format_date(value: date | None) -> str:
        if value is None:
            return "—"
        return value.strftime("%d.%m.%Y")

    def _update_team_buttons(self) -> None:
        team_id = self._selected_team_id()
        if team_id is None:
            self.deactivate_team_button.setText("Deaktivovat tým")
            self.edit_team_button.setEnabled(False)
            self.deactivate_team_button.setEnabled(False)
            return

        team = team_service.get_team(team_id)
        if team is None:
            self.deactivate_team_button.setText("Deaktivovat tým")
            return

        self.edit_team_button.setEnabled(True)
        self.deactivate_team_button.setEnabled(True)
        if team.active:
            self.deactivate_team_button.setText("Deaktivovat tým")
        else:
            self.deactivate_team_button.setText("Aktivovat tým")

    def add_team(self) -> None:
        dialog = TeamDialog(self)
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["name"]:
            QMessageBox.information(self, "Týmy", "Vyplňte název týmu.")
            return
        if not data["team_type_id"]:
            QMessageBox.information(self, "Týmy", "Vyberte typ týmu.")
            return

        try:
            team = team_service.create_team(**data)
        except ValueError as exc:
            QMessageBox.warning(self, "Týmy", str(exc))
            return

        self.refresh()
        for row in range(self.team_table.rowCount()):
            item = self.team_table.item(row, 0)
            if item and int(item.text()) == team.id:
                self.team_table.selectRow(row)
                break

    def edit_selected_team(self) -> None:
        team_id = self._selected_team_id()
        if team_id is None:
            QMessageBox.information(self, "Týmy", "Vyberte tým.")
            return

        team = team_service.get_team(team_id)
        if team is None:
            QMessageBox.warning(self, "Týmy", "Tým nebyl nalezen.")
            self.refresh()
            return

        dialog = TeamDialog(self, team=team)
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["name"]:
            QMessageBox.information(self, "Týmy", "Vyplňte název týmu.")
            return

        try:
            team_service.update_team(team_id, **data)
        except ValueError as exc:
            QMessageBox.warning(self, "Týmy", str(exc))
            return

        self.refresh()

    def deactivate_selected_team(self) -> None:
        team_id = self._selected_team_id()
        if team_id is None:
            QMessageBox.information(self, "Týmy", "Vyberte tým.")
            return

        team = team_service.get_team(team_id)
        if team is None:
            QMessageBox.warning(self, "Týmy", "Tým nebyl nalezen.")
            self.refresh()
            return

        if team.active:
            text = f"Opravdu deaktivovat tým „{team.name}“?\n\nTým zůstane v databázi kvůli budoucím vazbám."
            title = "Deaktivovat tým"
            new_active = False
        else:
            text = f"Opravdu znovu aktivovat tým „{team.name}“?"
            title = "Aktivovat tým"
            new_active = True

        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        team_service.update_team(team_id, active=new_active)
        self.refresh()

    def add_member(self) -> None:
        if self._current_team_id is None:
            return

        dialog = TeamMemberDialog(self)
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["person_name"] and not data["thp_worker_id"] and not data["person_id"]:
            QMessageBox.information(self, "Týmy", "Vyberte osobu.")
            return

        try:
            team_service.add_member(self._current_team_id, **data)
        except ValueError as exc:
            QMessageBox.warning(self, "Týmy", str(exc))
            return

        self._refresh_detail()

    def edit_member(self) -> None:
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "Týmy", "Vyberte člena týmu.")
            return

        member = TeamMemberRepository().get_by_id(member_id)
        if member is None:
            QMessageBox.warning(self, "Týmy", "Člen týmu nebyl nalezen.")
            self._refresh_detail()
            return

        dialog = TeamMemberDialog(self, member=member)
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["person_name"] and not data["thp_worker_id"] and not data["person_id"]:
            QMessageBox.information(self, "Týmy", "Vyberte osobu.")
            return

        try:
            team_service.update_member(
                member_id,
                role_id=data["role_id"],
                thp_worker_id=data["thp_worker_id"],
                person_id=data["person_id"],
                person_name=data["person_name"],
                mandatory=data["mandatory"],
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Týmy", str(exc))
            return

        self._refresh_detail()

    def remove_member(self) -> None:
        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "Týmy", "Vyberte člena týmu.")
            return

        answer = QMessageBox.question(
            self,
            "Odebrat člena",
            "Opravdu odebrat vybraného člena z týmu?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        team_service.delete_member(member_id)
        self._refresh_detail()

    def move_member(self, direction: int) -> None:
        if self._current_team_id is None:
            return

        member_id = self._selected_member_id()
        if member_id is None:
            QMessageBox.information(self, "Týmy", "Vyberte člena týmu.")
            return

        members = team_service.get_members(self._current_team_id)
        index = next((i for i, item in enumerate(members) if item.id == member_id), None)
        if index is None:
            return

        swap_index = index + direction
        if swap_index < 0 or swap_index >= len(members):
            return

        current = members[index]
        neighbour = members[swap_index]
        current_order = current.display_order
        neighbour_order = neighbour.display_order

        team_service.update_member(current.id, display_order=neighbour_order)
        team_service.update_member(neighbour.id, display_order=current_order)

        self._refresh_detail()
        for row in range(self.member_table.rowCount()):
            item = self.member_table.item(row, 0)
            if item and int(item.text()) == member_id:
                self.member_table.selectRow(row)
                break

    def _refresh_detail(self) -> None:
        if self._current_team_id is None:
            self._show_detail(None)
            return

        detail = team_service.get_team_detail(self._current_team_id)
        self._show_detail(detail)
