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

from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.audity.constants import (
    COMMISSION_DUPLICATE_PERSON_MESSAGE,
    COMMISSION_LABEL_INVITED,
    COMMISSION_LABEL_LEADER,
    COMMISSION_LABEL_MEMBER,
    COMMISSION_LABEL_UNION,
    COMMISSION_LABEL_WORKPLACE,
    COMMISSION_MISSING_LEADER_MESSAGE,
    COMMISSION_MISSING_UNION_MESSAGE,
    COMMISSION_MISSING_WORKPLACE_MESSAGE,
    COMMISSION_RECORD_INVITED,
    COMMISSION_RECORD_LEADER,
    COMMISSION_RECORD_MEMBER,
    COMMISSION_RECORD_UNION,
    COMMISSION_RECORD_WORKPLACE,
)
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.ui.audit_commission_entry_dialog import AuditCommissionEntryDialog


class AuditCommissionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.audit_id: int | None = None
        self._members: list[dict] = []
        self._invited: list[dict] = []

        layout = QVBoxLayout(self)

        fixed_box = QGroupBox("Základní složení auditního týmu")
        fixed_form = QFormLayout(fixed_box)

        self.leader_selector = ThpWorkerSelector(include_empty=True)
        self.workplace_selector = ThpWorkerSelector(include_empty=True)
        self.union_selector = PersonSelector(
            include_empty=True,
            allow_add_new=True,
            exclude_thp_linked=True,
        )

        fixed_form.addRow(f"{COMMISSION_LABEL_LEADER}:", self.leader_selector)
        fixed_form.addRow(f"{COMMISSION_LABEL_WORKPLACE}:", self.workplace_selector)
        fixed_form.addRow(f"{COMMISSION_LABEL_UNION}:", self.union_selector)
        layout.addWidget(fixed_box)

        self.members_box = QGroupBox("Auditoři")
        members_layout = QVBoxLayout(self.members_box)
        members_layout.addWidget(self._build_list_toolbar("member"))
        self.members_table = self._create_list_table()
        members_layout.addWidget(self.members_table)
        layout.addWidget(self.members_box)

        self.invited_box = QGroupBox(COMMISSION_LABEL_INVITED)
        invited_layout = QVBoxLayout(self.invited_box)
        invited_layout.addWidget(self._build_list_toolbar("invited"))
        self.invited_table = self._create_list_table()
        invited_layout.addWidget(self.invited_table)
        layout.addWidget(self.invited_box)

        info = QLabel(
            f"{COMMISSION_LABEL_LEADER}, {COMMISSION_LABEL_WORKPLACE.lower()} "
            f"a {COMMISSION_LABEL_UNION.lower()} jsou povinní. "
            f"{COMMISSION_LABEL_MEMBER}i a {COMMISSION_LABEL_INVITED.lower()} jsou volitelní."
        )
        info.setWordWrap(True)
        info.setObjectName("MutedText")
        layout.addWidget(info)

        self._committed_leader_id: int | None = None
        self._committed_workplace_id: int | None = None
        self._committed_union_id: int | None = None

        self.leader_selector.currentIndexChanged.connect(self._on_leader_selector_changed)
        self.workplace_selector.currentIndexChanged.connect(self._on_workplace_selector_changed)
        self.union_selector.currentIndexChanged.connect(self._on_union_selector_changed)

    @staticmethod
    def _selected_thp_id(selector: ThpWorkerSelector) -> int | None:
        data = selector.currentData()
        return data if isinstance(data, int) else None

    @staticmethod
    def _selected_person_id(selector: PersonSelector) -> int | None:
        data = selector.currentData()
        return data if isinstance(data, int) else None

    def _sync_committed_selector_state(self) -> None:
        self._committed_leader_id = self._selected_thp_id(self.leader_selector)
        self._committed_workplace_id = self._selected_thp_id(self.workplace_selector)
        self._committed_union_id = self._selected_person_id(self.union_selector)

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
            add_btn = QPushButton("Přidat auditora")
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

    def set_audit_context(self, audit_id: int | None) -> None:
        self.audit_id = audit_id
        self._members = []
        self._invited = []
        self.leader_selector.setCurrentIndex(0)
        self.workplace_selector.setCurrentIndex(0)
        self.union_selector.setCurrentIndex(0)

        for selector in (self.leader_selector, self.workplace_selector, self.union_selector):
            selector.blockSignals(True)

        if audit_id is not None:
            records = audit_commission_service.get_for_audit(audit_id)
            for record in records:
                data = audit_commission_service.member_to_dict(record)
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

        for selector in (self.leader_selector, self.workplace_selector, self.union_selector):
            selector.blockSignals(False)

        self._sync_committed_selector_state()
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
            audit_commission_service.validate_members(self.get_members_for_save())
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

    def _thp_used_in_commission(
        self,
        thp_worker_id: int,
        *,
        ignore_leader: bool = False,
        ignore_workplace: bool = False,
        exclude_member_row: int | None = None,
    ) -> bool:
        if not ignore_leader and self._selected_thp_id(self.leader_selector) == thp_worker_id:
            return True
        if not ignore_workplace and self._selected_thp_id(self.workplace_selector) == thp_worker_id:
            return True

        for index, member in enumerate(self._members):
            if exclude_member_row is not None and index == exclude_member_row:
                continue
            if member.get("thp_worker_id") == thp_worker_id:
                return True

        return False

    def _person_used_in_commission(
        self,
        person_id: int,
        *,
        ignore_union: bool = False,
        exclude_invited_row: int | None = None,
    ) -> bool:
        if not ignore_union and self._selected_person_id(self.union_selector) == person_id:
            return True

        for index, invited in enumerate(self._invited):
            if exclude_invited_row is not None and index == exclude_invited_row:
                continue
            if invited.get("person_id") == person_id:
                return True

        return False

    def _restore_thp_selector(self, selector: ThpWorkerSelector, person_id: int | None) -> None:
        selector.blockSignals(True)
        try:
            if person_id is None:
                if selector.include_empty:
                    selector.setCurrentIndex(0)
                else:
                    selector.setCurrentText("")
            else:
                selector.set_person_id(person_id)
        finally:
            selector.blockSignals(False)

    def _restore_person_selector(self, selector: PersonSelector, person_id: int | None) -> None:
        selector.blockSignals(True)
        try:
            selector.set_person_id(person_id)
        finally:
            selector.blockSignals(False)

    def _on_leader_selector_changed(self, _index: int = -1) -> None:
        new_id = self._selected_thp_id(self.leader_selector)
        if new_id is None:
            self._committed_leader_id = None
            return
        if new_id == self._committed_leader_id:
            return
        if self._thp_used_in_commission(new_id, ignore_leader=True):
            self._show_duplicate_person_message()
            self._restore_thp_selector(self.leader_selector, self._committed_leader_id)
            return
        self._committed_leader_id = new_id

    def _on_workplace_selector_changed(self, _index: int = -1) -> None:
        new_id = self._selected_thp_id(self.workplace_selector)
        if new_id is None:
            self._committed_workplace_id = None
            return
        if new_id == self._committed_workplace_id:
            return
        if self._thp_used_in_commission(new_id, ignore_workplace=True):
            self._show_duplicate_person_message()
            self._restore_thp_selector(self.workplace_selector, self._committed_workplace_id)
            return
        self._committed_workplace_id = new_id

    def _on_union_selector_changed(self, _index: int = -1) -> None:
        new_id = self._selected_person_id(self.union_selector)
        if new_id is None:
            self._committed_union_id = None
            return
        if new_id == self._committed_union_id:
            return
        if self._person_used_in_commission(new_id, ignore_union=True):
            self._show_duplicate_person_message()
            self._restore_person_selector(self.union_selector, self._committed_union_id)
            return
        self._committed_union_id = new_id

    def _thp_worker_already_in_commission(
        self,
        thp_worker_id: int,
        *,
        exclude_member_row: int | None = None,
    ) -> bool:
        return self._thp_used_in_commission(
            thp_worker_id,
            exclude_member_row=exclude_member_row,
        )

    def _person_already_in_commission(
        self,
        person_id: int,
        *,
        exclude_invited_row: int | None = None,
    ) -> bool:
        return self._person_used_in_commission(
            person_id,
            exclude_invited_row=exclude_invited_row,
        )

    def _show_duplicate_person_message(self) -> None:
        QMessageBox.information(self, "Auditní tým", COMMISSION_DUPLICATE_PERSON_MESSAGE)

    def add_member(self) -> None:
        dialog = AuditCommissionEntryDialog(self, entry_type="member")
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["thp_worker_id"] or not data["display_name"]:
            QMessageBox.information(self, "Auditní tým", "Vyberte THP pracovníka.")
            return
        if self._thp_worker_already_in_commission(data["thp_worker_id"]):
            self._show_duplicate_person_message()
            return
        self._members.append(data)
        self._refresh_tables()

    def edit_member(self) -> None:
        row = self._selected_row(self.members_table)
        if row is None:
            QMessageBox.information(self, "Auditní tým", "Vyberte auditora.")
            return
        dialog = AuditCommissionEntryDialog(
            self,
            entry_type="member",
            entry=self._members[row],
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["thp_worker_id"] or not data["display_name"]:
            QMessageBox.information(self, "Auditní tým", "Vyberte THP pracovníka.")
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
            QMessageBox.information(self, "Auditní tým", "Vyberte auditora.")
            return
        del self._members[row]
        self._refresh_tables()

    def add_invited(self) -> None:
        dialog = AuditCommissionEntryDialog(self, entry_type="invited")
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["person_id"] or not data["display_name"]:
            QMessageBox.information(self, "Auditní tým", "Vyberte osobu ze seznamu.")
            return
        if self._person_already_in_commission(data["person_id"]):
            self._show_duplicate_person_message()
            return
        self._invited.append(data)
        self._refresh_tables()

    def edit_invited(self) -> None:
        row = self._selected_row(self.invited_table)
        if row is None:
            QMessageBox.information(self, "Auditní tým", "Vyberte přizvanou osobu.")
            return
        dialog = AuditCommissionEntryDialog(
            self,
            entry_type="invited",
            entry=self._invited[row],
        )
        if not dialog.exec():
            return
        data = dialog.get_data()
        if not data["person_id"] or not data["display_name"]:
            QMessageBox.information(self, "Auditní tým", "Vyberte osobu ze seznamu.")
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
            QMessageBox.information(self, "Auditní tým", "Vyberte přizvanou osobu.")
            return
        del self._invited[row]
        self._refresh_tables()

    def move_item(self, list_type: str, direction: int) -> None:
        items = self._members if list_type == "member" else self._invited
        table = self.members_table if list_type == "member" else self.invited_table

        row = self._selected_row(table)
        if row is None:
            QMessageBox.information(self, "Auditní tým", "Vyberte položku v seznamu.")
            return

        new_row = row + direction
        if new_row < 0 or new_row >= len(items):
            return

        items[row], items[new_row] = items[new_row], items[row]
        self._refresh_tables()
        table.selectRow(new_row)
