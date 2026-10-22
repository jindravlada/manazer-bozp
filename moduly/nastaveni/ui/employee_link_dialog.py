"""Ruční propojení centrálního zaměstnance se zaměstnancem z Testů."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    wrap_in_scroll_area,
)
from core.widgets.filter_bar import FilterBar
from moduly.nastaveni.sluzby.employee_central_link_service import (
    TAKEOVER_FIELDS,
    EmployeeLinkError,
    EmployeeTakeoverProposal,
    employee_central_link_service,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.testy.sluzby.test_employee_service import test_employee_service

_TITLE = "Zaměstnanci"
_FIELD_ROLE = Qt.ItemDataRole.UserRole


class EmployeeLinkDialog(QDialog):
    """Výběr protějšku z Testů a potvrzení převzetí chybějících údajů.

    Návrh se jen zobrazuje. Zápis proběhne až po tlačítku Potvrdit propojení
    a následném shrnutí. Shoda osobního čísla je nápověda, ne výběr.
    """

    def __init__(self, parent=None, *, worker_id: int):
        super().__init__(parent)
        self.worker_id = int(worker_id)
        self._employee_id: int | None = None
        self._proposal: EmployeeTakeoverProposal | None = None
        self._blocked = False

        self.setWindowTitle("Propojit s Testy")
        configure_resizable_form_dialog(
            self,
            width=860,
            height=720,
            min_width=720,
            min_height=520,
        )

        layout = QVBoxLayout(self)
        host = QWidget()
        form = QVBoxLayout(host)

        self.central_label = QLabel("")
        self.central_label.setWordWrap(True)
        form.addWidget(self.central_label)

        self.locked_box = QGroupBox("Propojený zaměstnanec z Testů")
        locked_layout = QVBoxLayout(self.locked_box)
        self.locked_label = QLabel("")
        self.locked_label.setWordWrap(True)
        locked_layout.addWidget(self.locked_label)

        self.picker_box = QGroupBox("Zaměstnanec z Testů")
        picker_layout = QVBoxLayout(self.picker_box)
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.employee_table = QTableWidget()
        headers = [
            "ID",
            "Osobní číslo",
            "Příjmení",
            "Jméno",
            "Titul před",
            "Titul za",
            "Provoz",
            "Aktivní",
        ]
        self.employee_table.setColumnCount(len(headers))
        self.employee_table.setHorizontalHeaderLabels(headers)
        self.employee_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.employee_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.employee_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.employee_table.setColumnHidden(0, True)
        self.employee_filter = FilterBar(
            self.employee_table,
            placeholder="Hledat osobní číslo, jméno nebo příjmení...",
        )
        picker_layout.addWidget(self.hint_label)
        picker_layout.addWidget(self.employee_filter)
        picker_layout.addWidget(self.employee_table)

        proposal_box = QGroupBox("Převzetí údajů")
        proposal_layout = QVBoxLayout(proposal_box)
        self.proposal_table = QTableWidget()
        self.proposal_table.setColumnCount(4)
        self.proposal_table.setHorizontalHeaderLabels(
            ["Údaj", "Testy", "Nastavení", "Převzít"]
        )
        self.proposal_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.proposal_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proposal_table.verticalHeader().setVisible(False)
        self.proposal_table.setWordWrap(True)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        proposal_layout.addWidget(self.proposal_table)
        proposal_layout.addWidget(self.status_label)

        form.addWidget(self.locked_box)
        form.addWidget(self.picker_box)
        form.addWidget(proposal_box)
        layout.addWidget(wrap_in_scroll_area(host), 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.confirm_button = QPushButton("Potvrdit propojení")
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self._confirm)
        self.cancel_button = QPushButton("Zrušit")
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.confirm_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.employee_table.itemSelectionChanged.connect(self._on_employee_selected)
        self._load()

    def _load(self) -> None:
        worker = settings_service.get_worker_by_id(self.worker_id)
        if worker is None:
            QMessageBox.warning(self, _TITLE, "Zaměstnanec nebyl nalezen.")
            self._blocked = True
            self.confirm_button.setEnabled(False)
            return
        workplace = settings_service.get_workplace_by_id(worker.workplace_id)
        workplace_name = workplace.name if workplace is not None else ""
        self.central_label.setText(
            "Zaměstnanec v Nastavení: " + self._person_line(worker, workplace_name)
        )
        link = employee_central_link_service.get_by_worker(self.worker_id)
        if link is None:
            self.locked_box.hide()
            self.picker_box.show()
            self._fill_employees(worker.personal_number or "")
            self._clear_proposal("Vyberte zaměstnance z Testů.")
            return
        employee = test_employee_service.get_employee(link.test_employee_id)
        self.picker_box.hide()
        self.locked_box.show()
        if employee is None:
            self.locked_label.setText("Propojený zaměstnanec z Testů nebyl nalezen.")
            self._block("Propojený zaměstnanec z Testů nebyl nalezen.")
            return
        place = settings_service.get_workplace_by_id(employee.workplace_id)
        self.locked_label.setText(self._person_line(employee, place.name if place else ""))
        self._employee_id = int(employee.id)
        self._load_proposal(int(employee.id))

    def _fill_employees(self, personal_number: str) -> None:
        employees = test_employee_service.list_employees(include_inactive=True)
        workplaces = {
            workplace.id: workplace.name
            for workplace in settings_service.get_workplaces(include_inactive=True)
        }
        self.employee_table.blockSignals(True)
        self.employee_table.setRowCount(len(employees))
        hints = []
        wanted = personal_number.strip()
        for row, employee in enumerate(employees):
            workplace_name = workplaces.get(employee.workplace_id, "")
            values = [
                str(employee.id),
                employee.personal_number,
                employee.last_name,
                employee.first_name,
                employee.title_before or "",
                employee.title_after or "",
                workplace_name,
                "Ano" if employee.active else "Ne",
            ]
            for column, value in enumerate(values):
                self.employee_table.setItem(row, column, QTableWidgetItem(value))
            if wanted and employee.personal_number == wanted:
                hints.append(f"{employee.personal_number} – {employee.display_name}")
        self.employee_table.clearSelection()
        self.employee_table.setCurrentCell(-1, -1)
        self.employee_table.blockSignals(False)
        self.employee_filter.update_count()
        if hints:
            self.hint_label.setText(
                "Stejné osobní číslo v Testech: "
                + "; ".join(hints)
                + ". Jde jen o nápovědu, propojení se samo neprovede."
            )
            self.hint_label.show()
        else:
            self.hint_label.clear()
            self.hint_label.hide()

    def _on_employee_selected(self) -> None:
        employee_id = self._selected_employee_id()
        if employee_id is None:
            self._employee_id = None
            self._clear_proposal("Vyberte zaměstnance z Testů.")
            return
        self._employee_id = employee_id
        self._load_proposal(employee_id)

    def _selected_employee_id(self) -> int | None:
        selected = self.employee_table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.employee_table.item(selected[0].row(), 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def _load_proposal(self, employee_id: int) -> None:
        worker_link = employee_central_link_service.get_by_worker(self.worker_id)
        if worker_link is not None and int(worker_link.test_employee_id) != int(employee_id):
            self._block(
                "Centrální zaměstnanec je již propojen s jiným zaměstnancem z Testů."
            )
            return
        employee_link = employee_central_link_service.get_by_test_employee(employee_id)
        if employee_link is not None and int(employee_link.thp_worker_id) != self.worker_id:
            self._block(
                "Tento zaměstnanec z Testů je již propojen s jiným zaměstnancem."
            )
            return
        try:
            proposal = employee_central_link_service.propose_takeover(
                test_employee_id=employee_id,
                thp_worker_id=self.worker_id,
            )
        except EmployeeLinkError as error:
            self._block(str(error))
            return
        self._proposal = proposal
        self._blocked = False
        self._show_proposal(proposal)
        self.confirm_button.setEnabled(True)

    def _show_proposal(self, proposal: EmployeeTakeoverProposal) -> None:
        by_field = {item.field: item for item in proposal.fields}
        self.proposal_table.setRowCount(len(TAKEOVER_FIELDS))
        for row, field in enumerate(TAKEOVER_FIELDS):
            item = by_field[field]
            self.proposal_table.setItem(row, 0, self._text_item(item.label))
            self.proposal_table.setItem(row, 1, self._text_item(item.test_value))
            self.proposal_table.setItem(row, 2, self._text_item(item.central_value))
            choice = QTableWidgetItem(item.proposed_change)
            if item.will_change:
                choice.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                )
                choice.setCheckState(Qt.CheckState.Unchecked)
                choice.setData(_FIELD_ROLE, field)
            else:
                choice.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.proposal_table.setItem(row, 3, choice)
        self.proposal_table.resizeRowsToContents()
        if proposal.already_linked:
            self.status_label.setText(
                "Propojení už existuje. Zaškrtnuté položky se doplní, "
                "další vazba se nezaloží."
            )
        else:
            self.status_label.setText(
                "Zaškrtněte údaje k převzetí. Bez zaškrtnutí se uloží jen propojení."
            )

    def _clear_proposal(self, status: str) -> None:
        self._proposal = None
        self._blocked = False
        self.proposal_table.setRowCount(0)
        self.status_label.setText(status)
        self.confirm_button.setEnabled(False)

    def _block(self, message: str) -> None:
        self._proposal = None
        self._blocked = True
        self.proposal_table.setRowCount(0)
        self.status_label.setText(message)
        self.confirm_button.setEnabled(False)

    def _checked_fields(self) -> list[tuple[str, str]]:
        selected = []
        for row in range(self.proposal_table.rowCount()):
            item = self.proposal_table.item(row, 3)
            if item is None:
                continue
            field = item.data(_FIELD_ROLE)
            if not field or item.checkState() != Qt.CheckState.Checked:
                continue
            selected.append((str(field), item.text()))
        return selected

    def _confirm(self) -> None:
        if self._blocked or self._proposal is None or self._employee_id is None:
            return
        worker = settings_service.get_worker_by_id(self.worker_id)
        employee = test_employee_service.get_employee(self._employee_id)
        if worker is None or employee is None:
            QMessageBox.warning(self, _TITLE, "Zaměstnanec nebyl nalezen.")
            return
        checked = self._checked_fields()
        lines = [
            f"Nastavení: {worker.display_name}",
            f"Testy: {employee.display_name}, osobní číslo {employee.personal_number}",
        ]
        if self._proposal.already_linked:
            lines.append("Propojení už existuje a znovu se nezaloží.")
        else:
            lines.append("Vznikne propojení těchto dvou osob.")
        if checked:
            lines.append("Převezme se:")
            lines.extend(f"- {text}" for _field, text in checked)
        else:
            lines.append("Žádné údaje se nepřevezmou.")
        answer = QMessageBox.question(
            self,
            _TITLE,
            "\n".join(lines),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = employee_central_link_service.apply_confirmed_takeover(
                test_employee_id=self._employee_id,
                thp_worker_id=self.worker_id,
                revision=self._proposal.revision,
                confirm_fields=[field for field, _text in checked],
            )
        except EmployeeLinkError as error:
            QMessageBox.warning(self, _TITLE, str(error))
            reload_answer = QMessageBox.question(
                self,
                _TITLE,
                "Načíst nový návrh?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reload_answer == QMessageBox.StandardButton.Yes:
                self._load_proposal(self._employee_id)
            return
        if result.linked_now and result.applied_fields:
            done = "Propojení bylo uloženo a vybrané údaje byly převzaty."
        elif result.linked_now:
            done = "Propojení bylo uloženo. Údaje se nepřevzaly."
        elif result.applied_fields:
            done = "Vybrané údaje byly doplněny."
        else:
            done = "Propojení zůstává beze změny."
        QMessageBox.information(self, _TITLE, done)
        self.accept()

    def _text_item(self, value: str) -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        return item

    def _person_line(self, person, workplace_name: str) -> str:
        number = str(person.personal_number or "").strip() or "—"
        place = workplace_name or "bez provozu"
        state = "aktivní" if person.active else "neaktivní"
        return f"{person.display_name}, osobní číslo {number}, {place}, {state}"
