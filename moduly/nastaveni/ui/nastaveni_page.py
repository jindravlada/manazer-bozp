from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
    QTableWidget, QLabel, QMessageBox, QComboBox, QCompleter,
    QFormLayout, QLineEdit, QMenu, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
)
from PySide6.QtCore import Qt

from core.services.ares_service import ares_service
from core.services.cz_nace_service import cz_nace_service
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_int,
    typed_text,
)
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.exposed_group_service import (
    ExposedGroupError,
    exposed_group_service,
)
from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPE_WORKPLACE,
    WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
)
from moduly.nastaveni.sluzby.settings_service import (
    SettingsEmployerError,
    settings_service,
)
from moduly.nastaveni.sluzby.workplace_hierarchy_service import WorkplaceHierarchyError
from moduly.nastaveni.ui.person_dialog import PersonDialog
from moduly.nastaveni.ui.exposed_group_dialog import ExposedGroupDialog
from moduly.nastaveni.ui.responsibility_role_dialog import ResponsibilityRoleDialog
from moduly.nastaveni.ui.thp_worker_dialog import ThpWorkerDialog
from moduly.nastaveni.ui.workplace_dialog import WorkplaceDialog
from moduly.statni_dozor.constants import TAB_STATE_SUPERVISION
from moduly.statni_dozor.ui.control_authority_catalog_tab import ControlAuthorityCatalogTab


class NastaveniPage(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.workers_tab = self._workers_tab()
        self.persons_tab = self._persons_tab()
        self.workplaces_tab = self._workplaces_tab()
        self.state_supervision_catalog_tab = ControlAuthorityCatalogTab()
        self.responsibility_roles_tab = self._responsibility_roles_tab()
        self.exposed_groups_tab = self._exposed_groups_tab()
        self.employer_tab = self._employer_tab()

        self.tabs.addTab(self.workers_tab, "THP pracovníci")
        self.tabs.addTab(self.persons_tab, "Osoby")
        self.tabs.addTab(self.workplaces_tab, "Provozy a pracoviště")
        self.tabs.addTab(self.state_supervision_catalog_tab, TAB_STATE_SUPERVISION)
        self.tabs.addTab(self.responsibility_roles_tab, "Funkce / role")
        self.tabs.addTab(self.exposed_groups_tab, "Ohrožené skupiny")
        self.tabs.addTab(self.employer_tab, "Zaměstnavatel")

        layout.addWidget(self.tabs)
        self.refresh()

    def _employer_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        form = QFormLayout()

        self.employer_ico = QLineEdit()
        self.employer_name = QLineEdit()
        self.employer_address = QLineEdit()
        self.employer_abbreviation = QLineEdit()
        self.employer_abbreviation.setMaxLength(32)
        self.employer_nace = QComboBox()
        self.employer_nace.setEditable(True)
        self.employer_nace.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # Dlouhé položky CZ-NACE nesmí určovat minimální šířku celé stránky / okna.
        self.employer_nace.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.employer_nace.setMinimumContentsLength(28)

        self._setup_cz_nace_completer()

        form.addRow("IČO:", self.employer_ico)
        form.addRow("Název:", self.employer_name)
        form.addRow("Zkratka:", self.employer_abbreviation)
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

        note = QLabel(
            "Zkratka je nepovinná. Pokud není vyplněná, použije se automatická "
            "zkratka z názvu. CZ-NACE lze vybrat z ARES nebo ručně psát s našeptávačem."
        )
        note.setWordWrap(True)

        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(note)
        layout.addStretch()

        self.employer_name.textChanged.connect(self._update_employer_abbreviation_placeholder)
        self._update_employer_abbreviation_placeholder()

        return tab

    def _update_employer_abbreviation_placeholder(self) -> None:
        from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
            default_abbreviation,
        )

        suggested = default_abbreviation(self.employer_name.text())
        self.employer_abbreviation.setPlaceholderText(
            f"automaticky: {suggested}" if suggested else ""
        )
    def _setup_cz_nace_completer(self):
        displays: list[str] = []
        self.employer_nace.clear()
        for code, display in cz_nace_service.entries():
            self.employer_nace.addItem(display, code)
            displays.append(display)

        completer = QCompleter(displays, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)

        self.employer_nace.setCompleter(completer)

    def _show_employer_nace(self, raw: str) -> None:
        """Do pole vloží položku číselníku, nebo ponechá neznámou hodnotu."""
        found = cz_nace_service.lookup(raw)
        if found is not None:
            code, _display = found
            index = self.employer_nace.findData(code)
            if index >= 0:
                self.employer_nace.setCurrentIndex(index)
                return

        self.employer_nace.setCurrentIndex(-1)
        self.employer_nace.setEditText(str(raw or "").strip())

    def _stored_employer_nace(self) -> str:
        """Kód vybrané položky. Neznámý text se ukládá beze změny."""
        text = self.employer_nace.currentText().strip()
        if not text:
            return ""

        index = self.employer_nace.currentIndex()
        if index >= 0 and self.employer_nace.itemText(index).strip() == text:
            data = self.employer_nace.itemData(index)
            if data:
                return str(data).strip()

        for row in range(self.employer_nace.count()):
            if self.employer_nace.itemText(row).strip() == text:
                data = self.employer_nace.itemData(row)
                if data:
                    return str(data).strip()
        return text

    def _workers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        toolbar = QHBoxLayout()

        add_button = QPushButton("Přidat THP pracovníka")
        add_button.clicked.connect(self.add_worker)

        self.worker_edit_button = QPushButton("Upravit")
        self.worker_edit_button.clicked.connect(self.edit_selected_worker)
        self.worker_edit_button.setEnabled(False)

        self.worker_activate_button = QPushButton("Aktivovat")
        self.worker_activate_button.clicked.connect(self.activate_selected_worker)
        self.worker_activate_button.setEnabled(False)

        self.worker_deactivate_button = QPushButton("Deaktivovat")
        self.worker_deactivate_button.clicked.connect(self.deactivate_selected_worker)
        self.worker_deactivate_button.setEnabled(False)

        self.worker_filter = QComboBox()
        self.worker_filter.addItems(["Aktivní", "Všichni"])
        self.worker_filter.currentIndexChanged.connect(self.refresh_workers)

        toolbar.addWidget(add_button)
        toolbar.addWidget(self.worker_edit_button)
        toolbar.addWidget(self.worker_activate_button)
        toolbar.addWidget(self.worker_deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.worker_filter)

        self.worker_table = QTableWidget()
        self.worker_table.setColumnCount(10)
        self.worker_table.setHorizontalHeaderLabels(
            ["ID", "Titul před", "Příjmení", "Jméno", "Titul za", "Funkce", "Telefon", "E-mail", "Kont.", "Aktivní"]
        )
        self.worker_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.worker_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.worker_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.worker_table.doubleClicked.connect(self.edit_selected_worker)
        self.worker_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.worker_table.customContextMenuRequested.connect(self._show_worker_context_menu)
        self.worker_table.itemSelectionChanged.connect(self.update_worker_buttons)
        configure_table_columns(self.worker_table, "thp_workers")
        enable_typed_sorting(self.worker_table)

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
        self.person_edit_button.setEnabled(False)

        self.person_activate_button = QPushButton("Aktivovat")
        self.person_activate_button.clicked.connect(self.activate_selected_person)
        self.person_activate_button.setEnabled(False)

        self.person_deactivate_button = QPushButton("Deaktivovat")
        self.person_deactivate_button.clicked.connect(self.deactivate_selected_person)
        self.person_deactivate_button.setEnabled(False)

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
        toolbar.addWidget(self.person_activate_button)
        toolbar.addWidget(self.person_deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.person_filter)

        self.person_table = QTableWidget()
        self.person_table.setColumnCount(8)
        self.person_table.setHorizontalHeaderLabels(
            ["ID", "Jméno", "Organizace", "Pracovní zařazení", "E-mail", "Telefon", "Zam.", "Stav"]
        )
        self.person_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.person_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.person_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.person_table.doubleClicked.connect(self.edit_selected_person)
        self.person_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.person_table.customContextMenuRequested.connect(self._show_person_context_menu)
        self.person_table.itemSelectionChanged.connect(self.update_person_buttons)
        configure_table_columns(self.person_table, "persons")
        enable_typed_sorting(self.person_table)

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

        self.workplace_add_operation_button = QPushButton("Nový provoz")
        self.workplace_add_operation_button.clicked.connect(self.add_workplace_operation)

        self.workplace_add_workplace_button = QPushButton("Nové pracoviště")
        self.workplace_add_workplace_button.clicked.connect(self.add_workplace_item)

        self.workplace_add_part_button = QPushButton("Nová část pracoviště")
        self.workplace_add_part_button.clicked.connect(self.add_workplace_part)

        self.workplace_edit_button = QPushButton("Upravit")
        self.workplace_edit_button.clicked.connect(self.edit_selected_workplace)
        self.workplace_edit_button.setEnabled(False)

        self.workplace_activate_button = QPushButton("Aktivovat")
        self.workplace_activate_button.clicked.connect(self.activate_selected_workplace)
        self.workplace_activate_button.setEnabled(False)

        self.workplace_deactivate_button = QPushButton("Deaktivovat")
        self.workplace_deactivate_button.clicked.connect(self.deactivate_selected_workplace)
        self.workplace_deactivate_button.setEnabled(False)

        self.workplace_filter = QComboBox()
        self.workplace_filter.addItems(["Aktivní", "Všechna"])
        self.workplace_filter.currentIndexChanged.connect(self.refresh_workplaces)

        toolbar.addWidget(self.workplace_add_operation_button)
        toolbar.addWidget(self.workplace_add_workplace_button)
        toolbar.addWidget(self.workplace_add_part_button)
        toolbar.addWidget(self.workplace_edit_button)
        toolbar.addWidget(self.workplace_activate_button)
        toolbar.addWidget(self.workplace_deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.workplace_filter)

        self.workplace_tree = QTreeWidget()
        self.workplace_tree.setColumnCount(3)
        self.workplace_tree.setHeaderLabels(["Název", "Typ", "Aktivní"])
        self.workplace_tree.setSelectionBehavior(QTreeWidget.SelectRows)
        self.workplace_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.workplace_tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        self.workplace_tree.setRootIsDecorated(True)
        self.workplace_tree.setUniformRowHeights(True)
        self.workplace_tree.itemDoubleClicked.connect(self._on_workplace_item_double_clicked)
        self.workplace_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.workplace_tree.customContextMenuRequested.connect(self._show_workplace_context_menu)
        self.workplace_tree.itemSelectionChanged.connect(self.update_workplace_buttons)

        filter_row = QHBoxLayout()
        self.workplace_search_edit = QLineEdit()
        self.workplace_search_edit.setPlaceholderText("🔍 Hledat...")
        self.workplace_count_label = QLabel("Zobrazeno: 0 / 0")
        self.workplace_search_edit.textChanged.connect(self._apply_workplace_tree_filter)
        filter_row.addWidget(self.workplace_search_edit, 1)
        filter_row.addWidget(self.workplace_count_label)

        layout.addLayout(toolbar)
        layout.addLayout(filter_row)
        layout.addWidget(self.workplace_tree)

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

        self.responsibility_role_edit_button = QPushButton("Upravit")
        self.responsibility_role_edit_button.clicked.connect(self.edit_selected_responsibility_role)
        self.responsibility_role_edit_button.setEnabled(False)

        self.responsibility_role_activate_button = QPushButton("Aktivovat")
        self.responsibility_role_activate_button.clicked.connect(
            self.activate_selected_responsibility_role,
        )
        self.responsibility_role_activate_button.setEnabled(False)

        self.responsibility_role_deactivate_button = QPushButton("Deaktivovat")
        self.responsibility_role_deactivate_button.clicked.connect(
            self.deactivate_selected_responsibility_role,
        )
        self.responsibility_role_deactivate_button.setEnabled(False)

        self.responsibility_role_filter = QComboBox()
        self.responsibility_role_filter.addItems(["Aktivní", "Všechny"])
        self.responsibility_role_filter.currentIndexChanged.connect(self.refresh_responsibility_roles)

        toolbar.addWidget(add_button)
        toolbar.addWidget(self.responsibility_role_edit_button)
        toolbar.addWidget(self.responsibility_role_activate_button)
        toolbar.addWidget(self.responsibility_role_deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.responsibility_role_filter)

        self.responsibility_role_table = QTableWidget()
        self.responsibility_role_table.setColumnCount(4)
        self.responsibility_role_table.setHorizontalHeaderLabels(
            ["ID", "Název", "Popis", "Aktivní"],
        )
        self.responsibility_role_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.responsibility_role_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.responsibility_role_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.responsibility_role_table.doubleClicked.connect(self.edit_selected_responsibility_role)
        self.responsibility_role_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.responsibility_role_table.customContextMenuRequested.connect(
            self._show_responsibility_role_context_menu,
        )
        self.responsibility_role_table.itemSelectionChanged.connect(
            self.update_responsibility_role_buttons,
        )
        configure_table_columns(self.responsibility_role_table, "responsibility_roles")
        enable_typed_sorting(self.responsibility_role_table)

        self.responsibility_role_text_filter = FilterBar(self.responsibility_role_table)

        layout.addWidget(info)
        layout.addLayout(toolbar)
        layout.addWidget(self.responsibility_role_text_filter)
        layout.addWidget(self.responsibility_role_table)

        return tab

    def _exposed_groups_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            "Společný číselník ohrožených skupin osob pro posouzení rizik a další moduly.",
        )
        info.setWordWrap(True)

        toolbar = QHBoxLayout()
        add_button = QPushButton("Přidat")
        add_button.clicked.connect(self.add_exposed_group)
        self.exposed_group_edit_button = QPushButton("Upravit")
        self.exposed_group_edit_button.clicked.connect(self.edit_selected_exposed_group)
        self.exposed_group_edit_button.setEnabled(False)
        self.exposed_group_activate_button = QPushButton("Aktivovat")
        self.exposed_group_activate_button.clicked.connect(
            self.activate_selected_exposed_group,
        )
        self.exposed_group_activate_button.setEnabled(False)
        self.exposed_group_deactivate_button = QPushButton("Deaktivovat")
        self.exposed_group_deactivate_button.clicked.connect(
            self.deactivate_selected_exposed_group,
        )
        self.exposed_group_deactivate_button.setEnabled(False)
        self.exposed_group_filter = QComboBox()
        self.exposed_group_filter.addItems(["Aktivní", "Všechny"])
        self.exposed_group_filter.currentIndexChanged.connect(self.refresh_exposed_groups)
        toolbar.addWidget(add_button)
        toolbar.addWidget(self.exposed_group_edit_button)
        toolbar.addWidget(self.exposed_group_activate_button)
        toolbar.addWidget(self.exposed_group_deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.exposed_group_filter)

        self.exposed_group_table = QTableWidget()
        self.exposed_group_table.setColumnCount(3)
        self.exposed_group_table.setHorizontalHeaderLabels(["Název", "Poznámka", "Aktivní"])
        self.exposed_group_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.exposed_group_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.exposed_group_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.exposed_group_table.doubleClicked.connect(self.edit_selected_exposed_group)
        self.exposed_group_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.exposed_group_table.customContextMenuRequested.connect(
            self._show_exposed_group_context_menu,
        )
        self.exposed_group_table.itemSelectionChanged.connect(
            self.update_exposed_group_buttons,
        )
        configure_table_columns(self.exposed_group_table, "exposed_groups")
        enable_typed_sorting(self.exposed_group_table)
        self.exposed_group_text_filter = FilterBar(self.exposed_group_table)

        layout.addWidget(info)
        layout.addLayout(toolbar)
        layout.addWidget(self.exposed_group_text_filter)
        layout.addWidget(self.exposed_group_table)
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
        self._show_employer_nace(data.get("nace_code") or data.get("nace") or "")

    def save_employer(self):
        try:
            settings_service.save_employer(
                ico=self.employer_ico.text().strip(),
                name=self.employer_name.text().strip(),
                address=self.employer_address.text().strip(),
                nace=self._stored_employer_nace(),
                abbreviation=self.employer_abbreviation.text().strip(),
            )
        except SettingsEmployerError as exc:
            QMessageBox.warning(self, "Zaměstnavatel", str(exc))
            return
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
        if len(selected) != 1:
            return None

        item = self.person_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_person(self):
        person_id = self._selected_person_id()
        if person_id is None:
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

    def activate_selected_person(self):
        person_id = self._selected_person_id()
        if person_id is None:
            return

        person = person_service.get_by_id(person_id)
        if person is None:
            QMessageBox.warning(self, "Osoby", "Osoba nebyla nalezena.")
            self.refresh_persons()
            return
        if person.active:
            return

        answer = QMessageBox.question(
            self,
            "Aktivovat osobu",
            f"Opravdu znovu aktivovat osobu {person.display_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            person_service.activate(person_id)
            self.refresh_persons()

    def deactivate_selected_person(self):
        person_id = self._selected_person_id()
        if person_id is None:
            return

        person = person_service.get_by_id(person_id)
        if person is None:
            QMessageBox.warning(self, "Osoby", "Osoba nebyla nalezena.")
            self.refresh_persons()
            return
        if not person.active:
            return

        answer = QMessageBox.question(
            self,
            "Deaktivovat osobu",
            f"Opravdu deaktivovat osobu {person.display_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            person_service.deactivate(person_id)
            self.refresh_persons()

    def update_person_buttons(self):
        person_id = self._selected_person_id()
        person = person_service.get_by_id(person_id) if person_id is not None else None
        single = person is not None
        self.person_edit_button.setEnabled(single)
        self.person_activate_button.setEnabled(single and not person.active)
        self.person_deactivate_button.setEnabled(single and person.active)

    def _show_person_context_menu(self, position) -> None:
        index = self.person_table.indexAt(position)
        if index.isValid():
            self.person_table.selectRow(index.row())
            self.update_person_buttons()

        person_id = self._selected_person_id()
        single = person_id is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_person)
        edit_action.setEnabled(self.person_edit_button.isEnabled())
        activate_action = menu.addAction("Aktivovat", self.activate_selected_person)
        activate_action.setEnabled(self.person_activate_button.isEnabled())
        deactivate_action = menu.addAction("Deaktivovat", self.deactivate_selected_person)
        deactivate_action.setEnabled(self.person_deactivate_button.isEnabled())
        menu.exec(self.person_table.viewport().mapToGlobal(position))

    def _selected_worker_id(self) -> int | None:
        selected = self.worker_table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None

        item = self.worker_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_worker(self):
        worker_id = self._selected_worker_id()
        if worker_id is None:
            return

        self.open_worker(worker_id)

    def open_worker(self, worker_id: int):
        index = self.tabs.indexOf(self.workers_tab)
        if index >= 0:
            self.tabs.setCurrentIndex(index)

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

    def activate_selected_worker(self):
        worker_id = self._selected_worker_id()
        if worker_id is None:
            return

        worker = settings_service.get_worker_by_id(worker_id)
        if worker is None:
            QMessageBox.warning(self, "THP pracovníci", "Pracovník nebyl nalezen.")
            self.refresh_workers()
            return
        if worker.active:
            return

        answer = QMessageBox.question(
            self,
            "Aktivovat pracovníka",
            f"Opravdu znovu aktivovat pracovníka {worker.full_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            settings_service.activate_worker(worker_id)
            self.refresh_workers()

    def deactivate_selected_worker(self):
        worker_id = self._selected_worker_id()
        if worker_id is None:
            return

        worker = settings_service.get_worker_by_id(worker_id)
        if worker is None:
            QMessageBox.warning(self, "THP pracovníci", "Pracovník nebyl nalezen.")
            self.refresh_workers()
            return
        if not worker.active:
            return

        answer = QMessageBox.question(
            self,
            "Deaktivovat pracovníka",
            f"Opravdu deaktivovat pracovníka {worker.full_name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            settings_service.deactivate_worker(worker_id)
            self.refresh_workers()

    def update_worker_buttons(self):
        worker_id = self._selected_worker_id()
        worker = settings_service.get_worker_by_id(worker_id) if worker_id is not None else None
        single = worker is not None
        self.worker_edit_button.setEnabled(single)
        self.worker_activate_button.setEnabled(single and not worker.active)
        self.worker_deactivate_button.setEnabled(single and worker.active)

    def _show_worker_context_menu(self, position) -> None:
        index = self.worker_table.indexAt(position)
        if index.isValid():
            self.worker_table.selectRow(index.row())
            self.update_worker_buttons()

        worker_id = self._selected_worker_id()
        single = worker_id is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_worker)
        edit_action.setEnabled(self.worker_edit_button.isEnabled())
        activate_action = menu.addAction("Aktivovat", self.activate_selected_worker)
        activate_action.setEnabled(self.worker_activate_button.isEnabled())
        deactivate_action = menu.addAction("Deaktivovat", self.deactivate_selected_worker)
        deactivate_action.setEnabled(self.worker_deactivate_button.isEnabled())
        menu.exec(self.worker_table.viewport().mapToGlobal(position))

    def add_workplace_operation(self):
        self._open_workplace_dialog(
            default_item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def add_workplace_item(self):
        selected = self._selected_workplace()
        default_parent_id = None
        if selected is not None and selected.item_type == WORKPLACE_ITEM_TYPE_OPERATION:
            default_parent_id = selected.id
        self._open_workplace_dialog(
            default_item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            default_parent_id=default_parent_id,
        )

    def add_workplace_part(self):
        selected = self._selected_workplace()
        default_parent_id = None
        if selected is not None:
            if selected.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE:
                default_parent_id = selected.id
            elif selected.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE_PART and selected.parent_id:
                default_parent_id = selected.parent_id
        self._open_workplace_dialog(
            default_item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            default_parent_id=default_parent_id,
        )

    def _open_workplace_dialog(
        self,
        *,
        workplace=None,
        default_item_type: str | None = None,
        default_parent_id: int | None = None,
    ) -> None:
        dialog = WorkplaceDialog(
            self,
            workplace=workplace,
            default_item_type=default_item_type,
            default_parent_id=default_parent_id,
        )
        if dialog.exec():
            data = dialog.get_data()
            if not data["name"]:
                return
            try:
                if workplace is not None:
                    settings_service.save_workplace(id=workplace.id, **data)
                else:
                    settings_service.save_workplace(**data)
            except WorkplaceHierarchyError as error:
                QMessageBox.warning(self, "Provozy a pracoviště", str(error))
                return
            self.refresh_workplaces()

    def _selected_workplace_id(self) -> int | None:
        item = self.workplace_tree.currentItem()
        if item is None:
            return None
        workplace_id = item.data(0, Qt.ItemDataRole.UserRole)
        return int(workplace_id) if workplace_id else None

    def _selected_workplace(self):
        workplace_id = self._selected_workplace_id()
        if workplace_id is None:
            return None
        return settings_service.get_workplace_by_id(workplace_id)

    def _on_workplace_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        workplace_id = item.data(0, Qt.ItemDataRole.UserRole)
        if workplace_id:
            self.edit_selected_workplace()

    def edit_selected_workplace(self):
        workplace = self._selected_workplace()
        if workplace is None:
            return

        self._open_workplace_dialog(workplace=workplace)

    def activate_selected_workplace(self):
        workplace = self._selected_workplace()
        if workplace is None or workplace.active:
            return

        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu znovu aktivovat položku {workplace.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            settings_service.activate_workplace(workplace.id)
            self.refresh_workplaces()

    def deactivate_selected_workplace(self):
        workplace = self._selected_workplace()
        if workplace is None or not workplace.active:
            return

        active_children = settings_service.get_active_workplace_children(workplace.id)
        if active_children:
            QMessageBox.warning(
                self,
                "Provozy a pracoviště",
                (
                    f"Položka {workplace.name} má {len(active_children)} aktivních "
                    "podřízených položek. Deaktivace nadřazené položky je "
                    "automaticky neovlivní."
                ),
            )
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat položku {workplace.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            settings_service.deactivate_workplace(workplace.id)
            self.refresh_workplaces()

    def update_workplace_buttons(self):
        workplace = self._selected_workplace()
        single = workplace is not None
        self.workplace_edit_button.setEnabled(single)
        self.workplace_activate_button.setEnabled(single and not workplace.active)
        self.workplace_deactivate_button.setEnabled(single and workplace.active)

    def _show_workplace_context_menu(self, position) -> None:
        item = self.workplace_tree.itemAt(position)
        if item is not None:
            self.workplace_tree.setCurrentItem(item)
            self.update_workplace_buttons()

        workplace = self._selected_workplace()
        single = workplace is not None
        if not single and item is None:
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_workplace)
        edit_action.setEnabled(self.workplace_edit_button.isEnabled())
        activate_action = menu.addAction("Aktivovat", self.activate_selected_workplace)
        activate_action.setEnabled(self.workplace_activate_button.isEnabled())
        deactivate_action = menu.addAction("Deaktivovat", self.deactivate_selected_workplace)
        deactivate_action.setEnabled(self.workplace_deactivate_button.isEnabled())
        menu.exec(self.workplace_tree.viewport().mapToGlobal(position))

    def _apply_workplace_tree_filter(self) -> None:
        text = self.workplace_search_edit.text().strip().lower()
        total = 0
        visible = 0

        def walk(item: QTreeWidgetItem) -> bool:
            nonlocal total, visible
            total += 1
            row_text = " ".join(item.text(column) for column in range(item.columnCount())).lower()
            child_match = False
            for index in range(item.childCount()):
                if walk(item.child(index)):
                    child_match = True
            match = (text in row_text if text else True) or child_match
            item.setHidden(not match)
            if match:
                visible += 1
            return match

        for index in range(self.workplace_tree.topLevelItemCount()):
            walk(self.workplace_tree.topLevelItem(index))

        self.workplace_count_label.setText(f"Zobrazeno: {visible} / {total}")

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
        if len(selected) != 1:
            return None

        item = self.responsibility_role_table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def edit_selected_responsibility_role(self):
        role_id = self._selected_responsibility_role_id()
        if role_id is None:
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

    def activate_selected_responsibility_role(self):
        role_id = self._selected_responsibility_role_id()
        if role_id is None:
            return

        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            QMessageBox.warning(self, "Funkce / role", "Role nebyla nalezena.")
            self.refresh_responsibility_roles()
            return
        if role.active:
            return

        answer = QMessageBox.question(
            self,
            "Aktivovat roli",
            f"Opravdu znovu aktivovat roli {role.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            responsibility_role_service.activate(role_id)
            self.refresh_responsibility_roles()

    def deactivate_selected_responsibility_role(self):
        role_id = self._selected_responsibility_role_id()
        if role_id is None:
            return

        role = responsibility_role_service.get_by_id(role_id)
        if role is None:
            QMessageBox.warning(self, "Funkce / role", "Role nebyla nalezena.")
            self.refresh_responsibility_roles()
            return
        if not role.active:
            return

        answer = QMessageBox.question(
            self,
            "Deaktivovat roli",
            f"Opravdu deaktivovat roli {role.name}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            responsibility_role_service.deactivate(role_id)
            self.refresh_responsibility_roles()

    def update_responsibility_role_buttons(self):
        role_id = self._selected_responsibility_role_id()
        role = responsibility_role_service.get_by_id(role_id) if role_id is not None else None
        single = role is not None
        self.responsibility_role_edit_button.setEnabled(single)
        self.responsibility_role_activate_button.setEnabled(single and not role.active)
        self.responsibility_role_deactivate_button.setEnabled(single and role.active)

    def _show_responsibility_role_context_menu(self, position) -> None:
        index = self.responsibility_role_table.indexAt(position)
        if index.isValid():
            self.responsibility_role_table.selectRow(index.row())
            self.update_responsibility_role_buttons()

        role_id = self._selected_responsibility_role_id()
        single = role_id is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_responsibility_role)
        edit_action.setEnabled(self.responsibility_role_edit_button.isEnabled())
        activate_action = menu.addAction("Aktivovat", self.activate_selected_responsibility_role)
        activate_action.setEnabled(self.responsibility_role_activate_button.isEnabled())
        deactivate_action = menu.addAction(
            "Deaktivovat",
            self.deactivate_selected_responsibility_role,
        )
        deactivate_action.setEnabled(self.responsibility_role_deactivate_button.isEnabled())
        menu.exec(self.responsibility_role_table.viewport().mapToGlobal(position))

    def refresh(self):
        employer = settings_service.get_employer()
        if employer:
            self.employer_ico.setText(employer.ico)
            self.employer_name.setText(employer.name)
            self.employer_address.setText(employer.address)
            self.employer_abbreviation.setText(getattr(employer, "abbreviation", "") or "")
            self._show_employer_nace(employer.nace)
        self._update_employer_abbreviation_placeholder()

        self.refresh_workers()
        self.refresh_persons()
        self.refresh_workplaces()
        self.refresh_responsibility_roles()
        self.refresh_exposed_groups()
        self.state_supervision_catalog_tab.refresh()

    def refresh_workers(self):
        include_inactive = self.worker_filter.currentText() == "Všichni"
        workers = settings_service.get_workers(include_inactive=include_inactive)

        with sorting_paused(self.worker_table):
            self.worker_table.setRowCount(len(workers))
            for row, worker in enumerate(workers):
                self.worker_table.setItem(
                    row, 0, create_typed_item(str(worker.id), typed_int(worker.id), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 1, create_typed_item(worker.title_before, typed_text(worker.title_before), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 2, create_typed_item(worker.last_name, typed_text(worker.last_name), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 3, create_typed_item(worker.first_name, typed_text(worker.first_name), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 4, create_typed_item(worker.title_after, typed_text(worker.title_after), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 5, create_typed_item(worker.position, typed_text(worker.position), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 6, create_typed_item(worker.phone, typed_text(worker.phone), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row, 7, create_typed_item(worker.email, typed_text(worker.email), stable_id=worker.id)
                )
                self.worker_table.setItem(
                    row,
                    8,
                    create_typed_item(
                        "Ano" if worker.performs_controls else "Ne",
                        typed_bool(worker.performs_controls),
                        stable_id=worker.id,
                    ),
                )
                self.worker_table.setItem(
                    row,
                    9,
                    create_typed_item(
                        "Ano" if worker.active else "Ne", typed_bool(worker.active), stable_id=worker.id
                    ),
                )

        configure_table_columns(self.worker_table, "thp_workers")
        self.worker_table.clearSelection()
        self.worker_table.setCurrentCell(-1, -1)
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

        with sorting_paused(self.person_table):
            self.person_table.setRowCount(len(persons))
            for row, person in enumerate(persons):
                self.person_table.setItem(
                    row, 0, create_typed_item(str(person.id), typed_int(person.id), stable_id=person.id)
                )
                self.person_table.setItem(
                    row,
                    1,
                    create_typed_item(person.display_name, typed_text(person.display_name), stable_id=person.id),
                )
                self.person_table.setItem(
                    row,
                    2,
                    create_typed_item(person.organization or "", typed_text(person.organization), stable_id=person.id),
                )
                self.person_table.setItem(
                    row,
                    3,
                    create_typed_item(person.job_title or "", typed_text(person.job_title), stable_id=person.id),
                )
                self.person_table.setItem(
                    row,
                    4,
                    create_typed_item(person.email or "", typed_text(person.email), stable_id=person.id),
                )
                self.person_table.setItem(
                    row,
                    5,
                    create_typed_item(person.phone or "", typed_text(person.phone), stable_id=person.id),
                )
                self.person_table.setItem(
                    row,
                    6,
                    create_typed_item(
                        "Ano" if person.is_employee else "Ne",
                        typed_bool(person.is_employee),
                        stable_id=person.id,
                    ),
                )
                self.person_table.setItem(
                    row,
                    7,
                    create_typed_item(
                        "Aktivní" if person.active else "Neaktivní",
                        typed_bool(person.active),
                        stable_id=person.id,
                    ),
                )

        configure_table_columns(self.person_table, "persons")
        self.person_table.clearSelection()
        self.person_table.setCurrentCell(-1, -1)
        self.person_text_filter.update_count()
        self.update_person_buttons()

    def refresh_workplaces(self):
        include_inactive = self.workplace_filter.currentText() == "Všechna"
        workplaces = settings_service.get_workplaces(include_inactive=include_inactive)

        expanded_ids = set()
        iterator = QTreeWidgetItemIterator(self.workplace_tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded():
                workplace_id = item.data(0, Qt.ItemDataRole.UserRole)
                if workplace_id:
                    expanded_ids.add(int(workplace_id))
            iterator += 1

        selected_id = self._selected_workplace_id()
        self.workplace_tree.clear()

        by_id: dict[int, QTreeWidgetItem] = {}
        for workplace in workplaces:
            item = QTreeWidgetItem(
                [
                    workplace.name,
                    settings_service.workplace_item_type_label(workplace.item_type),
                    "Ano" if workplace.active else "Ne",
                ]
            )
            item.setData(0, Qt.ItemDataRole.UserRole, workplace.id)
            by_id[workplace.id] = item

        roots: list[QTreeWidgetItem] = []
        for workplace in workplaces:
            item = by_id[workplace.id]
            if workplace.parent_id and workplace.parent_id in by_id:
                by_id[workplace.parent_id].addChild(item)
            else:
                roots.append(item)

        for root in roots:
            self.workplace_tree.addTopLevelItem(root)

        for workplace_id, item in by_id.items():
            if workplace_id in expanded_ids:
                item.setExpanded(True)

        if selected_id is not None and selected_id in by_id:
            self.workplace_tree.setCurrentItem(by_id[selected_id])

        for column in range(self.workplace_tree.columnCount()):
            self.workplace_tree.resizeColumnToContents(column)

        self._apply_workplace_tree_filter()
        self.update_workplace_buttons()

    def refresh_responsibility_roles(self):
        include_inactive = self.responsibility_role_filter.currentText() == "Všechny"
        roles = responsibility_role_service.get_all(include_inactive=include_inactive)

        with sorting_paused(self.responsibility_role_table):
            self.responsibility_role_table.setRowCount(len(roles))
            for row, role in enumerate(roles):
                self.responsibility_role_table.setItem(
                    row, 0, create_typed_item(str(role.id), typed_int(role.id), stable_id=role.id)
                )
                self.responsibility_role_table.setItem(
                    row, 1, create_typed_item(role.name, typed_text(role.name), stable_id=role.id)
                )
                self.responsibility_role_table.setItem(
                    row, 2, create_typed_item(role.description, typed_text(role.description), stable_id=role.id)
                )
                self.responsibility_role_table.setItem(
                    row,
                    3,
                    create_typed_item(
                        "Ano" if role.active else "Ne", typed_bool(role.active), stable_id=role.id
                    ),
                )

        configure_table_columns(self.responsibility_role_table, "responsibility_roles")
        self.responsibility_role_table.clearSelection()
        self.responsibility_role_table.setCurrentCell(-1, -1)
        self.responsibility_role_text_filter.update_count()
        self.update_responsibility_role_buttons()

    def add_exposed_group(self):
        dialog = ExposedGroupDialog(self)
        if dialog.exec():
            try:
                data = dialog.get_data()
                exposed_group_service.create_group(**data)
            except ExposedGroupError as error:
                QMessageBox.warning(self, "Ohrožené skupiny", str(error))
                return
            self.refresh_exposed_groups()

    def _selected_exposed_group_id(self) -> int | None:
        selected = self.exposed_group_table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.exposed_group_table.item(selected[0].row(), 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def edit_selected_exposed_group(self):
        group_id = self._selected_exposed_group_id()
        if group_id is None:
            return
        group = exposed_group_service.get_by_id(group_id)
        if group is None:
            self.refresh_exposed_groups()
            return
        dialog = ExposedGroupDialog(self, group=group)
        if dialog.exec():
            try:
                data = dialog.get_data()
                exposed_group_service.update_group(group_id, **data)
            except ExposedGroupError as error:
                QMessageBox.warning(self, "Ohrožené skupiny", str(error))
                return
            self.refresh_exposed_groups()

    def activate_selected_exposed_group(self):
        group_id = self._selected_exposed_group_id()
        if group_id is None:
            return
        try:
            exposed_group_service.activate(group_id)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny", str(error))
            return
        self.refresh_exposed_groups()

    def deactivate_selected_exposed_group(self):
        group_id = self._selected_exposed_group_id()
        if group_id is None:
            return
        try:
            exposed_group_service.deactivate(group_id)
        except ExposedGroupError as error:
            QMessageBox.warning(self, "Ohrožené skupiny", str(error))
            return
        self.refresh_exposed_groups()

    def update_exposed_group_buttons(self):
        group_id = self._selected_exposed_group_id()
        group = exposed_group_service.get_by_id(group_id) if group_id is not None else None
        single = group is not None
        self.exposed_group_edit_button.setEnabled(single)
        self.exposed_group_activate_button.setEnabled(single and not group.active)
        self.exposed_group_deactivate_button.setEnabled(single and group.active)

    def _show_exposed_group_context_menu(self, position) -> None:
        index = self.exposed_group_table.indexAt(position)
        if index.isValid():
            self.exposed_group_table.selectRow(index.row())
            self.update_exposed_group_buttons()

        group_id = self._selected_exposed_group_id()
        single = group_id is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_exposed_group)
        edit_action.setEnabled(self.exposed_group_edit_button.isEnabled())
        activate_action = menu.addAction("Aktivovat", self.activate_selected_exposed_group)
        activate_action.setEnabled(self.exposed_group_activate_button.isEnabled())
        deactivate_action = menu.addAction("Deaktivovat", self.deactivate_selected_exposed_group)
        deactivate_action.setEnabled(self.exposed_group_deactivate_button.isEnabled())
        menu.exec(self.exposed_group_table.viewport().mapToGlobal(position))

    def refresh_exposed_groups(self):
        include_inactive = self.exposed_group_filter.currentText() == "Všechny"
        groups = exposed_group_service.get_all(include_inactive=include_inactive)
        with sorting_paused(self.exposed_group_table):
            self.exposed_group_table.setRowCount(len(groups))
            for row, group in enumerate(groups):
                name_item = create_typed_item(group.name, typed_text(group.name), stable_id=group.id)
                name_item.setData(Qt.ItemDataRole.UserRole, group.id)
                self.exposed_group_table.setItem(row, 0, name_item)
                self.exposed_group_table.setItem(
                    row, 1, create_typed_item(group.note or "", typed_text(group.note), stable_id=group.id)
                )
                self.exposed_group_table.setItem(
                    row,
                    2,
                    create_typed_item(
                        "Ano" if group.active else "Ne", typed_bool(group.active), stable_id=group.id
                    ),
                )
        configure_table_columns(self.exposed_group_table, "exposed_groups")
        self.exposed_group_table.clearSelection()
        self.exposed_group_table.setCurrentCell(-1, -1)
        self.exposed_group_text_filter.update_count()
        self.update_exposed_group_buttons()
