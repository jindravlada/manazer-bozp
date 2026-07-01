from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
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

from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.widgets.person_selector import PersonSelector
from moduly.proverky.constants import (
    COMMISSION_DUPLICATE_PERSON_MESSAGE,
    COMMISSION_MISSING_LEADER_MESSAGE,
    COMMISSION_MISSING_UNION_MESSAGE,
    COMMISSION_MISSING_WORKPLACE_MESSAGE,
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
)
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.ui.bozp_inspection_commission_entry_dialog import (
    BozpInspectionCommissionEntryDialog,
)


class BozpInspectionCommissionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.inspection_id: int | None = None
        self._members: list[dict] = []
        self._invited: list[dict] = []

        layout = QVBoxLayout(self)

        fixed_box = QGroupBox("Základní složení komise")
        fixed_form = QFormLayout(fixed_box)

        self.leader_selector = ThpWorkerSelector(include_empty=True)
        self.workplace_selector = ThpWorkerSelector(include_empty=True)
        self.union_selector = PersonSelector(include_empty=True, allow_add_new=True)

        fixed_form.addRow("Vedoucí komise:", self.leader_selector)
        fixed_form.addRow("Zástupce pracoviště:", self.workplace_selector)
        fixed_form.addRow("Zástupce odborové organizace:", self.union_selector)
        layout.addWidget(fixed_box)

        self.members_box = QGroupBox("Členové komise")
        members_layout = QVBoxLayout(self.members_box)
        members_layout.addWidget(self._build_list_toolbar("member"))
        self.members_table = self._create_list_table()
        members_layout.addWidget(self.members_table)
        layout.addWidget(self.members_box)

        self.invited_box = QGroupBox("Přizvané osoby")
        invited_layout = QVBoxLayout(self.invited_box)
        invited_layout.addWidget(self._build_list_toolbar("invited"))
        self.invited_table = self._create_list_table()
        invited_layout.addWidget(self.invited_table)
        layout.addWidget(self.invited_box)

        info = QLabel(
            "Vedoucí komise, zástupce pracoviště a zástupce odborové organizace jsou povinní. "
            "Členové komise a přizvané osoby jsou volitelní."
        )
        info.setWordWrap(True)
        info.setObjectName("MutedText")
        layout.addWidget(info)

    def _create_list_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["ID", "Jméno", "Role", "Poznámka", "Pořadí"])
        table.setColumnHidden(0, True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        return table

    def _build_list_toolbar(self, list_type: str) -> QWidget:
        toolbar = QWidget()
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(0, 0, 0, 0)

        if list_type == "member":
            add_btn = QPushButton("Přidat člena")
            edit_btn = QPushButton("Upravit")
            remove_btn = QPushButton("Odebrat")
            up_btn = QPushButton("Nahoru")
            down_btn = QPushButton("Dolů")
            add_btn.clicked.connect(self.add_member)
            edit_btn.clicked.connect(self.edit_member)
            remove_btn.clicked.connect(self.remove_member)
            up_btn.clicked.connect(lambda: self.move_item("member", -1))
            down_btn.clicked.connect(lambda: self.move_item("member", 1))
        else:
            add_btn = QPushButton("Přizvat osobu")
            edit_btn = QPushButton("Upravit")
            remove_btn = QPushButton("Odebrat")
            up_btn = QPushButton("Nahoru")
            down_btn = QPushButton("Dolů")
            add_btn.clicked.connect(self.add_invited)
            edit_btn.clicked.connect(self.edit_invited)
            remove_btn.clicked.connect(self.remove_invited)
            up_btn.clicked.connect(lambda: self.move_item("invited", -1))
            down_btn.clicked.connect(lambda: self.move_item("invited", 1))

        for button in (add_btn, edit_btn, remove_btn, up_btn, down_btn):
            row.addWidget(button)
        row.addStretch()
        return toolbar

    def set_inspection_context(self, inspection_id: int | None) -> None:
        self.inspection_id = inspection_id
        self._members = []
        self._invited = []
        self.leader_selector.setCurrentIndex(0)
        self.workplace_selector.setCurrentIndex(0)
        self.union_selector.setCurrentIndex(0)

        if inspection_id is not None:
            records = bozp_inspection_commission_service.get_for_inspection(inspection_id)
            for record in records:
                data = bozp_inspection_commission_service.member_to_dict(record)
                if data["record_type"] == COMMISSION_RECORD_LEADER:
                    if data.get("thp_worker_id") is not None:
                        self.leader_selector.set_person_id(data["thp_worker_id"])
                elif data["record_type"] == COMMISSION_RECORD_WORKPLACE:
                    if data.get("thp_worker_id") is not None:
                        self.workplace_selector.set_person_id(data["thp_worker_id"])
                elif data["record_type"] == COMMISSION_RECORD_UNION:
                    if data.get("person_id") is not None:
                        self.union_selector.set_person_id(data["person_id"])
                elif data["record_type"] == COMMISSION_RECORD_MEMBER:
                    self._members.append(data)
                elif data["record_type"] == COMMISSION_RECORD_INVITED:
                    self._invited.append(data)

        self._refresh_tables()

    def validate(self) -> tuple[bool, str]:
        leader_id = self.leader_selector.current_person_id()
        leader_name = self._leader_display_name()
        if leader_id is None or not leader_name:
            return False, COMMISSION_MISSING_LEADER_MESSAGE

        workplace_id = self.workplace_selector.current_person_id()
        workplace_name = self._workplace_display_name()
        if workplace_id is None or not workplace_name:
            return False, COMMISSION_MISSING_WORKPLACE_MESSAGE

        union_id = self.union_selector.current_person_id()
        union_name = self._union_display_name()
        if union_id is None or not union_name:
            return False, COMMISSION_MISSING_UNION_MESSAGE

        try:
            bozp_inspection_commission_service.validate_members(self.get_members_for_save())
        except ValueError as exc:
            return False, str(exc)

        return True, ""

    def get_members_for_save(self) -> list[dict]:
        members: list[dict] = []

        leader = self.leader_selector.current_person()
        leader_id = self.leader_selector.current_person_id()
        leader_name = leader.display_name if leader else self.leader_selector.currentText().strip()
        if leader_id is not None and leader_name:
            members.append(
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader_id,
                    "person_id": None,
                    "display_name": leader_name,
                    "role_text": None,
                    "display_order": 10,
                    "active": True,
                }
            )

        workplace = self.workplace_selector.current_person()
        workplace_id = self.workplace_selector.current_person_id()
        workplace_name = (
            workplace.display_name if workplace else self.workplace_selector.currentText().strip()
        )
        if workplace_id is not None and workplace_name:
            members.append(
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": workplace_id,
                    "person_id": None,
                    "display_name": workplace_name,
                    "role_text": None,
                    "display_order": 15,
                    "active": True,
                }
            )

        union_person = self.union_selector.current_person()
        union_id = self.union_selector.current_person_id()
        union_name = union_person.display_name if union_person else self.union_selector.display_text()
        if union_id is not None and union_name:
            members.append(
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "thp_worker_id": None,
                    "person_id": union_id,
                    "display_name": union_name,
                    "role_text": None,
                    "display_order": 20,
                    "active": True,
                }
            )

        for index, member in enumerate(self._members, start=1):
            members.append(
                {
                    "record_type": COMMISSION_RECORD_MEMBER,
                    "thp_worker_id": member.get("thp_worker_id"),
                    "person_id": None,
                    "display_name": member.get("display_name", ""),
                    "role_text": member.get("role_text"),
                    "note_text": member.get("note_text"),
                    "display_order": index * 10,
                    "active": True,
                }
            )

        for index, member in enumerate(self._invited, start=1):
            members.append(
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "thp_worker_id": None,
                    "person_id": member.get("person_id"),
                    "display_name": member.get("display_name", ""),
                    "role_text": member.get("role_text"),
                    "note_text": member.get("note_text"),
                    "display_order": index * 10,
                    "active": True,
                }
            )

        return members

    def _leader_display_name(self) -> str:
        leader = self.leader_selector.current_person()
        if leader is not None:
            return leader.display_name
        return self.leader_selector.currentText().strip()

    def _workplace_display_name(self) -> str:
        worker = self.workplace_selector.current_person()
        if worker is not None:
            return worker.display_name
        return self.workplace_selector.currentText().strip()

    def _union_display_name(self) -> str:
        person = self.union_selector.current_person()
        if person is not None:
            return person.display_name
        return self.union_selector.display_text()

    def _refresh_tables(self) -> None:
        self._fill_table(self.members_table, self._members)
        self._fill_table(self.invited_table, self._invited)

    @staticmethod
    def _fill_table(table: QTableWidget, items: list[dict]) -> None:
        table.setRowCount(len(items))
        for row, item in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(str(row)))
            table.setItem(row, 1, QTableWidgetItem(item.get("display_name") or "—"))
            table.setItem(row, 2, QTableWidgetItem(item.get("role_text") or ""))
            table.setItem(row, 3, QTableWidgetItem(item.get("note_text") or ""))
            table.setItem(row, 4, QTableWidgetItem(str((row + 1) * 10)))

    def _selected_row(self, table: QTableWidget) -> int | None:
        selected = table.selectionModel().selectedRows()
        if not selected:
            return None
        return selected[0].row()

    def _thp_worker_already_in_commission(
        self,
        thp_worker_id: int,
        *,
        exclude_member_row: int | None = None,
    ) -> bool:
        leader_id = self.leader_selector.current_person_id()
        if leader_id == thp_worker_id:
            return True

        workplace_id = self.workplace_selector.current_person_id()
        if workplace_id == thp_worker_id:
            return True

        for index, member in enumerate(self._members):
            if exclude_member_row is not None and index == exclude_member_row:
                continue
            if member.get("thp_worker_id") == thp_worker_id:
                return True

        return False

    def _person_already_in_commission(
        self,
        person_id: int,
        *,
        exclude_invited_row: int | None = None,
    ) -> bool:
        union_id = self.union_selector.current_person_id()
        if union_id == person_id:
            return True

        for index, invited in enumerate(self._invited):
            if exclude_invited_row is not None and index == exclude_invited_row:
                continue
            if invited.get("person_id") == person_id:
                return True

        return False

    def _show_duplicate_person_message(self) -> None:
        QMessageBox.information(self, "Komise", COMMISSION_DUPLICATE_PERSON_MESSAGE)

    def add_member(self) -> None:
        dialog = BozpInspectionCommissionEntryDialog(self, entry_type="member")
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["thp_worker_id"] or not data["display_name"]:
            QMessageBox.information(self, "Komise", "Vyberte THP pracovníka.")
            return
        if self._thp_worker_already_in_commission(data["thp_worker_id"]):
            self._show_duplicate_person_message()
            return
        self._members.append(data)
        self._refresh_tables()

    def edit_member(self) -> None:
        row = self._selected_row(self.members_table)
        if row is None:
            QMessageBox.information(self, "Komise", "Vyberte člena komise.")
            return
        dialog = BozpInspectionCommissionEntryDialog(
            self,
            entry_type="member",
            entry=self._members[row],
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["thp_worker_id"] or not data["display_name"]:
            QMessageBox.information(self, "Komise", "Vyberte THP pracovníka.")
            return
        if self._thp_worker_already_in_commission(
            data["thp_worker_id"],
            exclude_member_row=row,
        ):
            self._show_duplicate_person_message()
            return
        self._members[row] = data
        self._refresh_tables()
        self.members_table.selectRow(row)

    def remove_member(self) -> None:
        row = self._selected_row(self.members_table)
        if row is None:
            QMessageBox.information(self, "Komise", "Vyberte člena komise.")
            return
        del self._members[row]
        self._refresh_tables()

    def add_invited(self) -> None:
        dialog = BozpInspectionCommissionEntryDialog(self, entry_type="invited")
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["person_id"] or not data["display_name"]:
            QMessageBox.information(self, "Komise", "Vyberte osobu ze seznamu.")
            return
        if self._person_already_in_commission(data["person_id"]):
            self._show_duplicate_person_message()
            return
        self._invited.append(data)
        self._refresh_tables()

    def edit_invited(self) -> None:
        row = self._selected_row(self.invited_table)
        if row is None:
            QMessageBox.information(self, "Komise", "Vyberte přizvanou osobu.")
            return
        dialog = BozpInspectionCommissionEntryDialog(
            self,
            entry_type="invited",
            entry=self._invited[row],
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["person_id"] or not data["display_name"]:
            QMessageBox.information(self, "Komise", "Vyberte osobu ze seznamu.")
            return
        if self._person_already_in_commission(data["person_id"], exclude_invited_row=row):
            self._show_duplicate_person_message()
            return
        self._invited[row] = data
        self._refresh_tables()
        self.invited_table.selectRow(row)

    def remove_invited(self) -> None:
        row = self._selected_row(self.invited_table)
        if row is None:
            QMessageBox.information(self, "Komise", "Vyberte přizvanou osobu.")
            return
        del self._invited[row]
        self._refresh_tables()

    def move_item(self, list_type: str, direction: int) -> None:
        items = self._members if list_type == "member" else self._invited
        table = self.members_table if list_type == "member" else self.invited_table

        row = self._selected_row(table)
        if row is None:
            QMessageBox.information(self, "Komise", "Vyberte položku v seznamu.")
            return

        new_row = row + direction
        if new_row < 0 or new_row >= len(items):
            return

        items[row], items[new_row] = items[new_row], items[row]
        self._refresh_tables()
        table.selectRow(new_row)
