from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.ui.bozp_inspection_ad_hoc_member_dialog import (
    BozpInspectionAdHocMemberDialog,
)

_AD_HOC_COLOR = QColor("#1d4ed8")


class BozpInspectionCommissionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.inspection_id: int | None = None
        self.current_team_id: int | None = None
        self._members: list[dict] = []

        layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "Vyberte prověrkovou komisi na záložce Spis. "
            "Členové se načtou jako šablona a u této prověrky potvrdíte skutečnou účast."
        )
        self.info_label.setWordWrap(True)

        toolbar = QHBoxLayout()
        self.add_ad_hoc_button = QPushButton("Přidat přizvanou osobu")
        self.remove_ad_hoc_button = QPushButton("Odebrat přizvanou osobu")
        toolbar.addWidget(self.add_ad_hoc_button)
        toolbar.addWidget(self.remove_ad_hoc_button)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Účast", "Osoba", "Role", "Povinný", "Pozn."]
        )
        self.table.setColumnHidden(0, True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)

        layout.addWidget(self.info_label)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)

        self.add_ad_hoc_button.clicked.connect(self.add_ad_hoc_member)
        self.remove_ad_hoc_button.clicked.connect(self.remove_selected_ad_hoc_member)

    def set_inspection_context(
        self,
        inspection_id: int | None,
        team_id: int | None,
    ) -> None:
        self.inspection_id = inspection_id
        self.current_team_id = team_id

        if inspection_id is not None:
            stored = bozp_inspection_commission_service.get_for_inspection(inspection_id)
            self._members = [
                bozp_inspection_commission_service.member_to_dict(member)
                for member in stored
            ]
        else:
            self._members = []

        if not self._members and team_id is not None:
            self.load_from_team(team_id)

        self.refresh()
        self._update_buttons()

    def has_members(self) -> bool:
        return bool(self._members)

    def has_template_members(self) -> bool:
        return any(not member.get("ad_hoc") for member in self._members)

    def load_from_team(self, team_id: int | None, *, keep_ad_hoc: bool = True) -> None:
        self.current_team_id = team_id
        if team_id is None:
            if keep_ad_hoc:
                self._members = [member for member in self._members if member.get("ad_hoc")]
            else:
                self._members = []
            self.refresh()
            self._update_buttons()
            return

        self._members = bozp_inspection_commission_service.merge_team_template(
            self._members,
            team_id,
            keep_ad_hoc=keep_ad_hoc,
        )
        self.refresh()
        self._update_buttons()

    def get_members_for_save(self) -> list[dict]:
        return [dict(member) for member in self._members]

    def refresh(self) -> None:
        self.table.setRowCount(len(self._members))

        for row, member in enumerate(self._members):
            member_id = member.get("id")
            self.table.setItem(row, 0, QTableWidgetItem("" if member_id is None else str(member_id)))

            participated_checkbox = QCheckBox()
            participated_checkbox.setChecked(bool(member.get("participated", True)))
            participated_checkbox.toggled.connect(
                lambda checked, index=row: self._set_participated(index, checked)
            )

            participated_wrapper = QWidget()
            participated_layout = QHBoxLayout(participated_wrapper)
            participated_layout.addWidget(participated_checkbox)
            participated_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            participated_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 1, participated_wrapper)

            person_item = QTableWidgetItem(member.get("person_name") or "—")
            role_item = QTableWidgetItem(member.get("role_name") or "—")
            mandatory_item = QTableWidgetItem("Ano" if member.get("mandatory") else "Ne")
            note_item = QTableWidgetItem("Přizvaná" if member.get("ad_hoc") else "")

            for item in (person_item, role_item, mandatory_item, note_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            if member.get("ad_hoc"):
                for item in (person_item, role_item, mandatory_item, note_item):
                    item.setForeground(QBrush(_AD_HOC_COLOR))

            self.table.setItem(row, 2, person_item)
            self.table.setItem(row, 3, role_item)
            self.table.setItem(row, 4, mandatory_item)
            self.table.setItem(row, 5, note_item)

    def _set_participated(self, row: int, participated: bool) -> None:
        if row < 0 or row >= len(self._members):
            return
        self._members[row]["participated"] = participated

    def _selected_row(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return selected[0].row()

    def add_ad_hoc_member(self) -> None:
        if self.current_team_id is None and not self._members:
            QMessageBox.information(
                self,
                "Komise",
                "Nejdříve vyberte prověrkovou komisi na záložce Spis.",
            )
            return

        dialog = BozpInspectionAdHocMemberDialog(self)
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["person_name"]:
            QMessageBox.information(self, "Komise", "Vyplňte jméno přizvané osoby.")
            return

        next_order = max((int(member.get("display_order") or 0) for member in self._members), default=0) + 10
        self._members.append(
            {
                "id": None,
                "team_member_id": None,
                "thp_worker_id": data.get("thp_worker_id"),
                "person_id": data.get("person_id"),
                "person_name": data["person_name"],
                "role_id": data["role_id"],
                "role_name": data["role_name"],
                "mandatory": False,
                "participated": True,
                "ad_hoc": True,
                "display_order": next_order,
            }
        )
        self.refresh()
        self._update_buttons()

    def remove_selected_ad_hoc_member(self) -> None:
        row = self._selected_row()
        if row is None:
            QMessageBox.information(self, "Komise", "Vyberte přizvanou osobu.")
            return

        member = self._members[row]
        if not member.get("ad_hoc"):
            QMessageBox.information(
                self,
                "Komise",
                "Odebrat lze pouze přizvanou osobu přidanou jen k této prověrce.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Odebrat osobu",
            f"Odebrat přizvanou osobu {member.get('person_name')}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        del self._members[row]
        self.refresh()
        self._update_buttons()

    def _update_buttons(self) -> None:
        enabled = self.current_team_id is not None or bool(self._members)
        self.add_ad_hoc_button.setEnabled(enabled)
        self.remove_ad_hoc_button.setEnabled(enabled)
