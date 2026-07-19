from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_bool,
    typed_text,
)
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.sluzby.profession_service import (
    ProfessionError,
    profession_service,
)
from moduly.rizeni_rizik.ui.profession_dialog import ProfessionDialog


class ProfessionsManagementDialog(QDialog):
    """Správa číselníku profesí a jejich ohrožených skupin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Profese")
        self.resize(820, 540)

        layout = QVBoxLayout(self)
        info = QLabel(
            "Číselník profesí / pracovních zařazení pro generování "
            "Pravidel bezpečné práce. Jedna profese může zahrnovat více "
            "ohrožených skupin."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        toolbar = QHBoxLayout()
        add_button = QPushButton("Přidat")
        add_button.clicked.connect(self.add_profession)
        edit_button = QPushButton("Upravit")
        edit_button.clicked.connect(self.edit_selected_profession)
        self.activate_button = QPushButton("Aktivovat")
        self.activate_button.clicked.connect(self.activate_selected_profession)
        self.deactivate_button = QPushButton("Deaktivovat")
        self.deactivate_button.clicked.connect(self.deactivate_selected_profession)
        self.filter = QComboBox()
        self.filter.addItems(["Aktivní", "Všechny"])
        self.filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(add_button)
        toolbar.addWidget(edit_button)
        toolbar.addWidget(self.activate_button)
        toolbar.addWidget(self.deactivate_button)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Zobrazit:"))
        toolbar.addWidget(self.filter)
        layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Název", "Ohrožené skupiny", "Poznámka", "Aktivní"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_selected_profession)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)
        configure_table_columns(self.table, "professions")
        enable_typed_sorting(self.table)
        self.text_filter = FilterBar(self.table)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        close_button = QPushButton("Zavřít")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.refresh()

    def refresh(self) -> None:
        include_inactive = self.filter.currentIndex() == 1
        professions = profession_service.get_all(include_inactive=include_inactive)
        with sorting_paused(self.table):
            self.table.setRowCount(len(professions))
            for row_index, profession in enumerate(professions):
                group_names = self._group_names(profession.id)
                name_item = create_typed_item(
                    profession.name,
                    typed_text(profession.name),
                    stable_id=profession.id,
                )
                name_item.setData(Qt.ItemDataRole.UserRole, profession.id)
                self.table.setItem(row_index, 0, name_item)
                self.table.setItem(
                    row_index,
                    1,
                    create_typed_item(
                        group_names,
                        typed_text(group_names),
                        stable_id=profession.id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    2,
                    create_typed_item(
                        profession.note or "",
                        typed_text(profession.note),
                        stable_id=profession.id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    3,
                    create_typed_item(
                        "Ano" if profession.active else "Ne",
                        typed_bool(profession.active),
                        stable_id=profession.id,
                    ),
                )
        configure_table_columns(self.table, "professions")
        self._update_action_buttons()

    def _group_names(self, profession_id: int) -> str:
        names: list[str] = []
        for group_id in profession_service.get_group_ids(profession_id):
            group = exposed_group_service.get_by_id(group_id)
            if group is not None:
                names.append(group.name)
        return ", ".join(names)

    def _update_action_buttons(self) -> None:
        profession_id = self._selected_profession_id()
        if profession_id is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        profession = profession_service.get_by_id(profession_id)
        if profession is None:
            self.activate_button.setEnabled(False)
            self.deactivate_button.setEnabled(False)
            return
        self.activate_button.setEnabled(not profession.active)
        self.deactivate_button.setEnabled(profession.active)

    def _selected_profession_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def add_profession(self) -> None:
        dialog = ProfessionDialog(self)
        if not dialog.exec():
            return
        try:
            data = dialog.get_data()
            profession_service.create_profession(**data)
        except ProfessionError as error:
            QMessageBox.warning(self, "Profese", str(error))
            return
        self.refresh()

    def edit_selected_profession(self) -> None:
        profession_id = self._selected_profession_id()
        if profession_id is None:
            QMessageBox.information(self, "Profese", "Vyberte profesi.")
            return
        profession = profession_service.get_by_id(profession_id)
        if profession is None:
            return
        dialog = ProfessionDialog(
            self,
            profession=profession,
            group_ids=profession_service.get_group_ids(profession_id),
        )
        if not dialog.exec():
            return
        try:
            data = dialog.get_data()
            profession_service.update_profession(profession_id, **data)
        except ProfessionError as error:
            QMessageBox.warning(self, "Profese", str(error))
            return
        self.refresh()

    def activate_selected_profession(self) -> None:
        profession_id = self._selected_profession_id()
        if profession_id is None:
            QMessageBox.information(self, "Profese", "Vyberte profesi.")
            return
        try:
            profession_service.activate(profession_id)
        except ProfessionError as error:
            QMessageBox.warning(self, "Profese", str(error))
            return
        self.refresh()

    def deactivate_selected_profession(self) -> None:
        profession_id = self._selected_profession_id()
        if profession_id is None:
            QMessageBox.information(self, "Profese", "Vyberte profesi.")
            return
        try:
            profession_service.deactivate(profession_id)
        except ProfessionError as error:
            QMessageBox.warning(self, "Profese", str(error))
            return
        self.refresh()
