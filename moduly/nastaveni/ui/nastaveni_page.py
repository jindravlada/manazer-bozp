from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QLabel, QMessageBox, QComboBox, QCompleter,
    QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt

from core.services.ares_service import ares_service
from core.services.cz_nace_service import cz_nace_service
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.nastaveni.ui.person_dialog import PersonDialog
from moduly.nastaveni.ui.responsibility_role_dialog import ResponsibilityRoleDialog
from moduly.nastaveni.ui.thp_worker_dialog import ThpWorkerDialog
from moduly.nastaveni.ui.workplace_dialog import WorkplaceDialog


class NastaveniPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tabs.addTab(self._workers_tab(), "THP pracovníci")
        self.tabs.addTab(self._persons_tab(), "Osoby")
        self.tabs.addTab(self._workplaces_tab(), "Pracoviště")
        self.tabs.addTab(self._responsibility_roles_tab(), "Funkce / role")
        self.tabs.addTab(self._employer_tab(), "Zaměstnavatel")

        layout.addWidget(self.tabs)
        self.refresh()

    def _employer_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()

        self.employer_ico = QLineEdit()
        self.employer_name = QLineEdit()
        self.employer_address = QLineEdit()
        self.employer_nace = QComboBox()
        self.employer_nace.setEditable(True)

        self._setup_cz_nace_completer()

        form.addRow("IČO:", self.employer_ico)
        form.addRow("Název:", self.employer_name)
        form.addRow("Adresa:", self.employer_address)
        form.addRow("Hlavní CZ-NACE:", self.employer_nace)

        buttons = QHBoxLayout()
        self.load_ares_button = QPushButton("Načíst z ARES")
        self.load_ares_button.clicked.connect(self.load_from_ares)

        self.save_employer_button = QPushButton("Uložit zaměstnavatele")
        self.save_employer_button.clicked.connect(self.save_employer)

        buttons.addWidget(self.load_ares_button)
        buttons.addWidget(self.save_employer_button)
        buttons.addStretch()

        note = QLabel("CZ-NACE lze vybrat z ARES nebo ručně psát s našeptávačem.")

        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(note)
        layout.addStretch()

        return tab

    def _setup_cz_nace_completer(self):
        displays = cz_nace_service.get_all_displays()

        self.employer_nace.clear()
        self.employer_nace.addItems(displays)

        completer = QCompleter(displays, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)

        self.employer_nace.setCompleter(completer)

    def _workers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()

        add_button = QPushButton("Přidat THP pracovníka")
        add_button.clicked.connect(self.add_worker)

        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_worker)

        self.active_toggle_button = QPushButton("Deaktivovat / Aktivovat")
        self.active_toggle_button.clicked.connect(self.toggle_selected_worker_active)

        self.worker_filter = QComboBox()
        self.worker_filter.addItems(["Aktivní", "Všichni"])
        self.worker_filter.currentIndexChanged.connect(self.refresh_workers)

        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.active_toggle_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.worker_filter)

        self.worker_table = QTableWidget()
        self.worker_table.setColumnCount(10)
        self.worker_table.setHorizontalHeaderLabels(
            ["ID", "Titul před", "Příjmení", "Jméno", "Titul za", "Funkce", "Telefon", "E-mail", "Kont.", "Aktivní"]
        )
        self.worker_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.worker_table.setSelectionMode(QTableWidget.SingleSelection)
        self.worker_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.worker_table.doubleClicked.connect(self.edit_selected_worker)
        self.worker_table.itemSelectionChanged.connect(self.update_worker_buttons)
        configure_table_columns(self.worker_table, "thp_workers")

        self.worker_text_filter = FilterBar(self.worker_table)

        layout.addLayout(toolbar)
        layout.addWidget(self.worker_text_filter)
        layout.addWidget(self.worker_table)

        return tab

    def _persons_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Společný seznam osob pro audity, prověrky, úkoly a další moduly. "
            "Není to evidence zaměstnanců ani THP pracovníků."
        )
        info.setWordWrap(True)

        toolbar = QHBoxLayout()

        self.person_add_button = QPushButton("Nová osoba")
        self.person_add_button.clicked.connect(self.add_person)

        self.person_edit_button = QPushButton("Upravit")
        self.person_edit_button.clicked.connect(self.edit_selected_person)

        self.person_active_toggle_button = QPushButton("Deaktivovat / Aktivovat")
        self.person_active_toggle_button.clicked.connect(self.toggle_selected_person_active)

        self.person_filter = QComboBox()
        self.person_filter.addItems([
            "Aktivní",
            "Zaměstnanci",
            "Ostatní osoby",
            "Neaktivní",
            "Vše",
        ])
        self.person_filter.currentIndexChanged.connect(self.refresh_persons)

        toolbar.addWidget(self.person_add_button)
        toolbar.addWidget(self.person_edit_button)
        toolbar.addWidget(self.person_active_toggle_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.person_filter)

        self.person_table = QTableWidget()
        self.person_table.setColumnCount(8)
        self.person_table.setHorizontalHeaderLabels(
            ["ID", "Jméno", "Organizace", "Pracovní zařazení", "E-mail", "Telefon", "Zam.", "Stav"]
        )
        self.person_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.person_table.setSelectionMode(QTableWidget.SingleSelection)
        self.person_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.person_table.doubleClicked.connect(self.edit_selected_person)
        self.person_table.itemSelectionChanged.connect(self.update_person_buttons)
        configure_table_columns(self.person_table, "persons")

        self.person_text_filter = FilterBar(self.person_table)

        layout.addWidget(info)
        layout.addLayout(toolbar)
        layout.addWidget(self.person_text_filter)
        layout.addWidget(self.person_table)

        return tab

    def _workplaces_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()

        add_button = QPushButton("Přidat pracoviště")
        add_button.clicked.connect(self.add_workplace)

        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_workplace)

        self.workplace_active_toggle_button = QPushButton("Deaktivovat / Aktivovat")
        self.workplace_active_toggle_button.clicked.connect(self.toggle_selected_workplace_active)

        self.workplace_filter = QComboBox()
        self.workplace_filter.addItems(["Aktivní", "Všechna"])
        self.workplace_filter.currentIndexChanged.connect(self.refresh_workplaces)

        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.workplace_active_toggle_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.workplace_filter)

        self.workplace_table = QTableWidget()
        self.workplace_table.setColumnCount(5)
        self.workplace_table.setHorizontalHeaderLabels(
            ["ID", "Název", "Adresa", "Poznámka", "Aktivní"]
        )
        self.workplace_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.workplace_table.setSelectionMode(QTableWidget.SingleSelection)
        self.workplace_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.workplace_table.doubleClicked.connect(self.edit_selected_workplace)
        self.workplace_table.itemSelectionChanged.connect(self.update_workplace_buttons)
        configure_table_columns(self.workplace_table, "workplaces")

        self.workplace_text_filter = FilterBar(self.workplace_table)

        layout.addLayout(toolbar)
        layout.addWidget(self.workplace_text_filter)
        layout.addWidget(self.workplace_table)

        return tab

    def _responsibility_roles_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Číselník odpovědných funkcí a rolí pro procesní požadavky BOZP.",
        )
        info.setWordWrap(True)

        toolbar = QHBoxLayout()

        add_button = QPushButton("Přidat roli")
        add_button.clicked.connect(self.add_responsibility_role)

        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_responsibility_role)

        self.responsibility_role_active_toggle_button = QPushButton("Deaktivovat / Aktivovat")
        self.responsibility_role_active_toggle_button.clicked.connect(
            self.toggle_selected_responsibility_role_active,
        )

        self.responsibility_role_filter = QComboBox()
        self.responsibility_role_filter.addItems(["Aktivní", "Všechny"])
        self.responsibility_role_filter.currentIndexChanged.connect(self.refresh_responsibility_roles)

        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.responsibility_role_active_toggle_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.responsibility_role_filter)

        self.responsibility_role_table = QTableWidget()
        self.responsibility_role_table.setColumnCount(4)
        self.responsibility_role_table.setHorizontalHeaderLabels(
            ["ID", "Název", "Popis", "Aktivní"],
        )
        self.responsibility_role_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.responsibility_role_table.setSelectionMode(QTableWidget.SingleSelection)
        self.responsibility_role_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.responsibility_role_table.doubleClicked.connect(self.edit_selected_responsibility_role)
        self.responsibility_role_table.itemSelectionChanged.connect(
            self.update_responsibility_role_buttons,
        )
        configure_table_columns(self.responsibility_role_table, "responsibility_roles")

        self.responsibility_role_text_filter = FilterBar(self.responsibility_role_table)

        layout.addWidget(info)
        layout.addLayout(toolbar)
        layout.addWidget(self.responsibility_role_text_filter)
        layout.addWidget(self.responsibility_role_table)

        return tab

    def load_from_ares(self):
        ico = self.employer_ico.text().strip()

        if not ico:
            QMessageBox.warning(self, "ARES", "Zadejte IČO.")
            return

        try:
            data = ares_service.find_by_ico(ico)
        except Exception as exc:
            QMessageBox.critical(self, "ARES", f"Nepodařilo se načíst data z ARES.\n\n{exc}")
            return

        if not data:
            QMessageBox.warning(self, "ARES", "Záznam nebyl nalezen.")
            return

        self.employer_ico.setText(data.get("ico", ""))
        self.employer_name.setText(data.get("name", ""))
        self.employer_address.setText(data.get("address", ""))

        self.employer_nace.clear()
        self.employer_nace.addItems(data.get("nace_list", []))
        self.employer_nace.setEditText(data.get("nace", ""))

    def save_employer(self):
        settings_service.save_employer(
            ico=self.employer_ico.text().strip(),
            name=self.employer_name.text().strip(),
            address=self.employer_address.text().strip(),
            nace=self.employer_nace.currentText().strip(),
        )
        self.refresh()

    def add_worker(self):
        dialog = ThpWorkerDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["first_name"] and data["last_name"]:
                settings_service.save_worker(**data)
                self.refresh_workers()

    def add_person(self):
        dialog = PersonDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["first_name"] and data["last_name"]:
                person_service.create_person(**data)
                self.refresh_persons()

    def _selected_person_id(self) -> int | None:
        selected = self.person_table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.person_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_person(self):
        person_id = self._selected_person_id()
        if person_id is None:
            QMessageBox.information(self, "Osoby", "Vyberte osobu.")
            return

        person = person_service.get_by_id(person_id)
        if person is None:
            QMessageBox.warning(self, "Osoby", "Osoba nebyla nalezena.")
            self.refresh_persons()
            return

        dialog = PersonDialog(self, person=person)
        if dialog.exec():
            data = dialog.get_data()
            if data["first_name"] and data["last_name"]:
                person_service.update_person(person_id, **data)
                self.refresh_persons()

    def toggle_selected_person_active(self):
        person_id = self._selected_person_id()
        if person_id is None:
            QMessageBox.information(self, "Osoby", "Vyberte osobu.")
            return

        person = person_service.get_by_id(person_id)
        if person is None:
            QMessageBox.warning(self, "Osoby", "Osoba nebyla nalezena.")
            self.refresh_persons()
            return

        if person.active:
            text = f"Opravdu deaktivovat osobu {person.display_name}?"
            title = "Deaktivovat osobu"
            activate = False
        else:
            text = f"Opravdu znovu aktivovat osobu {person.display_name}?"
            title = "Aktivovat osobu"
            activate = True

        answer = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            if activate:
                person_service.activate(person_id)
            else:
                person_service.deactivate(person_id)
            self.refresh_persons()

    def update_person_buttons(self):
        person_id = self._selected_person_id()
        if person_id is None:
            self.person_active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        person = person_service.get_by_id(person_id)
        if person is None:
            self.person_active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        self.person_active_toggle_button.setText("Deaktivovat" if person.active else "Aktivovat")

    def _selected_worker_id(self) -> int | None:
        selected = self.worker_table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.worker_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_worker(self):
        worker_id = self._selected_worker_id()
        if worker_id is None:
            QMessageBox.information(self, "THP pracovníci", "Vyberte pracovníka.")
            return

        self.open_worker(worker_id)

    def open_worker(self, worker_id: int):
        self.tabs.setCurrentIndex(0)

        worker = settings_service.get_worker_by_id(worker_id)
        if worker is None:
            QMessageBox.warning(self, "THP pracovníci", "Pracovník nebyl nalezen.")
            self.refresh_workers()
            return

        dialog = ThpWorkerDialog(self, worker=worker)
        if dialog.exec():
            data = dialog.get_data()
            if data["first_name"] and data["last_name"]:
                settings_service.save_worker(id=worker_id, **data)
                self.refresh_workers()

    def toggle_selected_worker_active(self):
        worker_id = self._selected_worker_id()
        if worker_id is None:
            QMessageBox.information(self, "THP pracovníci", "Vyberte pracovníka.")
            return

        worker = settings_service.get_worker_by_id(worker_id)
        if worker is None:
            QMessageBox.warning(self, "THP pracovníci", "Pracovník nebyl nalezen.")
            self.refresh_workers()
            return

        if worker.active:
            text = f"Opravdu deaktivovat pracovníka {worker.full_name}?"
            title = "Deaktivovat pracovníka"
            new_state = False
        else:
            text = f"Opravdu znovu aktivovat pracovníka {worker.full_name}?"
            title = "Aktivovat pracovníka"
            new_state = True

        answer = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if answer == QMessageBox.Yes:
            if new_state:
                settings_service.activate_worker(worker_id)
            else:
                settings_service.deactivate_worker(worker_id)
            self.refresh_workers()

    def update_worker_buttons(self):
        worker_id = self._selected_worker_id()
        if worker_id is None:
            self.active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        worker = settings_service.get_worker_by_id(worker_id)
        if worker is None:
            self.active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        self.active_toggle_button.setText("Deaktivovat" if worker.active else "Aktivovat")

    def add_workplace(self):
        dialog = WorkplaceDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                settings_service.save_workplace(**data)
                self.refresh_workplaces()

    def _selected_workplace_id(self) -> int | None:
        selected = self.workplace_table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.workplace_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_workplace(self):
        workplace_id = self._selected_workplace_id()
        if workplace_id is None:
            QMessageBox.information(self, "Pracoviště", "Vyberte pracoviště.")
            return

        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            QMessageBox.warning(self, "Pracoviště", "Pracoviště nebylo nalezeno.")
            self.refresh_workplaces()
            return

        dialog = WorkplaceDialog(self, workplace=workplace)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                settings_service.save_workplace(id=workplace_id, **data)
                self.refresh_workplaces()

    def toggle_selected_workplace_active(self):
        workplace_id = self._selected_workplace_id()
        if workplace_id is None:
            QMessageBox.information(self, "Pracoviště", "Vyberte pracoviště.")
            return

        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            QMessageBox.warning(self, "Pracoviště", "Pracoviště nebylo nalezeno.")
            self.refresh_workplaces()
            return

        if workplace.active:
            text = f"Opravdu deaktivovat pracoviště {workplace.name}?"
            title = "Deaktivovat pracoviště"
            new_state = False
        else:
            text = f"Opravdu znovu aktivovat pracoviště {workplace.name}?"
            title = "Aktivovat pracoviště"
            new_state = True

        answer = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if answer == QMessageBox.Yes:
            if new_state:
                settings_service.activate_workplace(workplace_id)
            else:
                settings_service.deactivate_workplace(workplace_id)
            self.refresh_workplaces()

    def update_workplace_buttons(self):
        workplace_id = self._selected_workplace_id()
        if workplace_id is None:
            self.workplace_active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            self.workplace_active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        self.workplace_active_toggle_button.setText("Deaktivovat" if workplace.active else "Aktivovat")

    def add_responsibility_role(self):
        dialog = ResponsibilityRoleDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                try:
                    responsibility_role_service.create_role(**data)
                except ValueError as exc:
                    QMessageBox.warning(self, "Funkce / role", str(exc))
                    return
                self.refresh_responsibility_roles()

    def _selected_responsibility_role_id(self) -> int | None:
        selected = self.responsibility_role_table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.responsibility_role_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_responsibility_role(self):
        role_id = self._selected_responsibility_role_id()
        if role_id is None:
            QMessageBox.information(self, "Funkce / role", "Vyberte roli.")
            return

        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            QMessageBox.warning(self, "Funkce / role", "Role nebyla nalezena.")
            self.refresh_responsibility_roles()
            return

        dialog = ResponsibilityRoleDialog(self, role=role)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                try:
                    responsibility_role_service.update_role(role_id, **data)
                except ValueError as exc:
                    QMessageBox.warning(self, "Funkce / role", str(exc))
                    return
                self.refresh_responsibility_roles()

    def toggle_selected_responsibility_role_active(self):
        role_id = self._selected_responsibility_role_id()
        if role_id is None:
            QMessageBox.information(self, "Funkce / role", "Vyberte roli.")
            return

        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            QMessageBox.warning(self, "Funkce / role", "Role nebyla nalezena.")
            self.refresh_responsibility_roles()
            return

        if role.active:
            text = f"Opravdu deaktivovat roli {role.name}?"
            title = "Deaktivovat roli"
            new_state = False
        else:
            text = f"Opravdu znovu aktivovat roli {role.name}?"
            title = "Aktivovat roli"
            new_state = True

        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.Yes:
            if new_state:
                responsibility_role_service.activate(role_id)
            else:
                responsibility_role_service.deactivate(role_id)
            self.refresh_responsibility_roles()

    def update_responsibility_role_buttons(self):
        role_id = self._selected_responsibility_role_id()
        if role_id is None:
            self.responsibility_role_active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            self.responsibility_role_active_toggle_button.setText("Deaktivovat / Aktivovat")
            return

        self.responsibility_role_active_toggle_button.setText(
            "Deaktivovat" if role.active else "Aktivovat",
        )

    def refresh(self):
        employer = settings_service.get_employer()
        if employer:
            self.employer_ico.setText(employer.ico)
            self.employer_name.setText(employer.name)
            self.employer_address.setText(employer.address)
            self.employer_nace.setEditText(employer.nace)

        self.refresh_workers()
        self.refresh_persons()
        self.refresh_workplaces()
        self.refresh_responsibility_roles()

    def refresh_workers(self):
        include_inactive = self.worker_filter.currentText() == "Všichni"
        workers = settings_service.get_workers(include_inactive=include_inactive)

        self.worker_table.setRowCount(len(workers))
        for row, worker in enumerate(workers):
            self.worker_table.setItem(row, 0, QTableWidgetItem(str(worker.id)))
            self.worker_table.setItem(row, 1, QTableWidgetItem(worker.title_before))
            self.worker_table.setItem(row, 2, QTableWidgetItem(worker.last_name))
            self.worker_table.setItem(row, 3, QTableWidgetItem(worker.first_name))
            self.worker_table.setItem(row, 4, QTableWidgetItem(worker.title_after))
            self.worker_table.setItem(row, 5, QTableWidgetItem(worker.position))
            self.worker_table.setItem(row, 6, QTableWidgetItem(worker.phone))
            self.worker_table.setItem(row, 7, QTableWidgetItem(worker.email))
            self.worker_table.setItem(row, 8, QTableWidgetItem("Ano" if worker.performs_controls else "Ne"))
            self.worker_table.setItem(row, 9, QTableWidgetItem("Ano" if worker.active else "Ne"))

        configure_table_columns(self.worker_table, "thp_workers")
        self.worker_text_filter.update_count()
        self.update_worker_buttons()

    def refresh_persons(self):
        mode = self.person_filter.currentText()
        if mode == "Vše":
            persons = person_service.get_all(include_inactive=True)
        elif mode == "Neaktivní":
            persons = [
                person for person in person_service.get_all(include_inactive=True)
                if not person.active
            ]
        elif mode == "Zaměstnanci":
            persons = [
                person for person in person_service.get_all(include_inactive=False)
                if person.is_employee
            ]
        elif mode == "Ostatní osoby":
            persons = [
                person for person in person_service.get_all(include_inactive=False)
                if not person.is_employee
            ]
        else:
            persons = person_service.get_all(include_inactive=False)

        self.person_table.setRowCount(len(persons))
        for row, person in enumerate(persons):
            self.person_table.setItem(row, 0, QTableWidgetItem(str(person.id)))
            self.person_table.setItem(row, 1, QTableWidgetItem(person.display_name))
            self.person_table.setItem(row, 2, QTableWidgetItem(person.organization or ""))
            self.person_table.setItem(row, 3, QTableWidgetItem(person.job_title or ""))
            self.person_table.setItem(row, 4, QTableWidgetItem(person.email or ""))
            self.person_table.setItem(row, 5, QTableWidgetItem(person.phone or ""))
            self.person_table.setItem(row, 6, QTableWidgetItem("Ano" if person.is_employee else "Ne"))
            self.person_table.setItem(row, 7, QTableWidgetItem("Aktivní" if person.active else "Neaktivní"))

        configure_table_columns(self.person_table, "persons")
        self.person_text_filter.update_count()
        self.update_person_buttons()

    def refresh_workplaces(self):
        include_inactive = self.workplace_filter.currentText() == "Všechna"
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)

        self.workplace_table.setRowCount(len(workplaces))
        for row, workplace in enumerate(workplaces):
            self.workplace_table.setItem(row, 0, QTableWidgetItem(str(workplace.id)))
            self.workplace_table.setItem(row, 1, QTableWidgetItem(workplace.name))
            self.workplace_table.setItem(row, 2, QTableWidgetItem(workplace.address))
            self.workplace_table.setItem(row, 3, QTableWidgetItem(workplace.note))
            self.workplace_table.setItem(row, 4, QTableWidgetItem("Ano" if workplace.active else "Ne"))

        configure_table_columns(self.workplace_table, "workplaces")
        self.workplace_text_filter.update_count()
        self.update_workplace_buttons()

    def refresh_responsibility_roles(self):
        include_inactive = self.responsibility_role_filter.currentText() == "Všechny"
        roles = responsibility_role_service.get_all(include_inactive=include_inactive)

        self.responsibility_role_table.setRowCount(len(roles))
        for row, role in enumerate(roles):
            self.responsibility_role_table.setItem(row, 0, QTableWidgetItem(str(role.id)))
            self.responsibility_role_table.setItem(row, 1, QTableWidgetItem(role.name))
            self.responsibility_role_table.setItem(row, 2, QTableWidgetItem(role.description))
            self.responsibility_role_table.setItem(
                row,
                3,
                QTableWidgetItem("Ano" if role.active else "Ne"),
            )

        configure_table_columns(self.responsibility_role_table, "responsibility_roles")
        self.responsibility_role_text_filter.update_count()
        self.update_responsibility_role_buttons()
