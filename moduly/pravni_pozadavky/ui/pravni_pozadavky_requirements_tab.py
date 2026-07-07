from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    DEFAULT_ACTIVE_FILTER,
    FILTER_ACTIVE_ONLY,
    FILTER_ALL_RECORDS,
    FILTER_ARCHIVED_ONLY,
    FILTER_AREA_VSE,
    FILTER_PERSON_VSE,
    FILTER_STATUS_VSE,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.sluzby.legal_requirement_task_service import (
    legal_requirement_task_service,
)
from moduly.pravni_pozadavky.ui.legal_requirement_check_dialog import LegalRequirementCheckDialog
from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog
from moduly.pravni_pozadavky.ui.legal_requirement_table import LegalRequirementTable


class PravniPozadavkyRequirementsTab(QWidget):
    """Záložka evidence právních požadavků."""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.new_btn = QPushButton("Nový požadavek")
        self.edit_btn = QPushButton("Upravit")
        self.archive_btn = QPushButton("Archivovat")
        self.verify_btn = QPushButton("Ověřit plnění")
        self.task_btn = QPushButton("Vytvořit úkol")

        self.area_filter = QComboBox()
        self.status_filter = QComboBox()
        self.person_filter = QComboBox()
        self.active_filter = QComboBox()
        self.active_filter.addItems([
            FILTER_ACTIVE_ONLY,
            FILTER_ARCHIVED_ONLY,
            FILTER_ALL_RECORDS,
        ])
        self.active_filter.setCurrentText(DEFAULT_ACTIVE_FILTER)

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.archive_btn)
        toolbar.addWidget(self.verify_btn)
        toolbar.addWidget(self.task_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Oblast:"))
        toolbar.addWidget(self.area_filter)
        toolbar.addWidget(QLabel("Stav:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(QLabel("Osoba:"))
        toolbar.addWidget(self.person_filter)
        toolbar.addWidget(QLabel("Záznamy:"))
        toolbar.addWidget(self.active_filter)

        self.table = LegalRequirementTable()
        configure_table_columns(self.table, "legal_requirements")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat požadavek...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_requirement)
        self.edit_btn.clicked.connect(self.edit_selected_requirement)
        self.archive_btn.clicked.connect(self.archive_selected_requirement)
        self.verify_btn.clicked.connect(self.verify_selected_requirement)
        self.task_btn.clicked.connect(self.create_task_for_selected)
        self.table.doubleClicked.connect(self.edit_selected_requirement)
        self.area_filter.currentIndexChanged.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.person_filter.currentIndexChanged.connect(self.refresh)
        self.active_filter.currentIndexChanged.connect(self.refresh)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clear_selection()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def refresh(self) -> None:
        self._populate_filter_options()
        requirements = self._filter_requirements(legal_requirement_service.get_all())
        self.table.load_requirements(requirements)
        configure_table_columns(self.table, "legal_requirements")
        self.table.clear_selection()
        self.text_filter.update_count()

    def show_created_requirement(self, requirement_id: int | None = None) -> None:
        self.area_filter.setCurrentIndex(0)
        self.status_filter.setCurrentIndex(0)
        self.person_filter.setCurrentIndex(0)
        self.active_filter.setCurrentText(DEFAULT_ACTIVE_FILTER)
        self.text_filter.clear()
        self.refresh()
        if requirement_id is not None:
            self._select_requirement(requirement_id)

    def _select_requirement(self, requirement_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.text() == str(requirement_id):
                self.table.selectRow(row)
                self.table.scrollToItem(item)
                break

    def _populate_filter_options(self) -> None:
        requirements = legal_requirement_service.get_all()
        areas = sorted({item.area.strip() for item in requirements if item.area.strip()})
        persons = sorted(
            {item.responsible_person_name.strip() for item in requirements if item.responsible_person_name.strip()}
        )

        self._repopulate_combo(self.area_filter, FILTER_AREA_VSE, areas)
        self._repopulate_combo(
            self.status_filter,
            FILTER_STATUS_VSE,
            [COMPLIANCE_STATUS_LABELS[key] for key in sorted(COMPLIANCE_STATUS_LABELS)],
        )
        self._repopulate_combo(self.person_filter, FILTER_PERSON_VSE, persons)

    def _repopulate_combo(self, combo: QComboBox, all_label: str, values: list[str]) -> None:
        current = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(all_label)
        combo.addItems(values)
        index = combo.findText(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _filter_requirements(self, requirements):
        active_mode = self.active_filter.currentText()
        if active_mode == FILTER_ACTIVE_ONLY:
            requirements = [item for item in requirements if item.active]
        elif active_mode == FILTER_ARCHIVED_ONLY:
            requirements = [item for item in requirements if not item.active]

        area = self.area_filter.currentText()
        if area != FILTER_AREA_VSE:
            requirements = [item for item in requirements if item.area == area]

        status_label = self.status_filter.currentText()
        if status_label != FILTER_STATUS_VSE:
            status_keys = [
                key for key, label in COMPLIANCE_STATUS_LABELS.items() if label == status_label
            ]
            if status_keys:
                requirements = [item for item in requirements if item.compliance_status == status_keys[0]]

        person = self.person_filter.currentText()
        if person != FILTER_PERSON_VSE:
            requirements = [item for item in requirements if item.responsible_person_name == person]

        return requirements

    def _selected_requirement_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def new_requirement(self) -> None:
        dialog = LegalRequirementDialog(self)
        if exec_maximized(dialog):
            requirement = legal_requirement_service.create_requirement(**dialog.get_data())
            self.show_created_requirement(requirement.id)

    def edit_selected_requirement(self) -> None:
        requirement_id = self._selected_requirement_id()
        if requirement_id is None:
            QMessageBox.information(self, "Právní požadavky", "Vyberte požadavek.")
            return
        self.open_requirement(requirement_id)

    def open_requirement(self, requirement_id: int) -> None:
        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            QMessageBox.warning(self, "Právní požadavky", "Požadavek nebyl nalezen.")
            self.refresh()
            return

        dialog = LegalRequirementDialog(self, requirement=requirement)
        if exec_maximized(dialog):
            legal_requirement_service.update_requirement(requirement_id, **dialog.get_data())
            self.refresh()

    def archive_selected_requirement(self) -> None:
        requirement_id = self._selected_requirement_id()
        if requirement_id is None:
            QMessageBox.information(self, "Právní požadavky", "Vyberte požadavek.")
            return

        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            QMessageBox.warning(self, "Právní požadavky", "Požadavek nebyl nalezen.")
            self.refresh()
            return

        if not requirement.active:
            answer = QMessageBox.question(
                self,
                "Obnovit požadavek",
                "Požadavek je archivní. Chcete ho obnovit do aktivních?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer == QMessageBox.Yes:
                legal_requirement_service.restore_requirement(requirement_id)
                self.refresh()
            return

        answer = QMessageBox.question(
            self,
            "Archivovat požadavek",
            "Opravdu archivovat vybraný požadavek?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            legal_requirement_service.archive_requirement(requirement_id)
            self.refresh()

    def verify_selected_requirement(self) -> None:
        requirement_id = self._selected_requirement_id()
        if requirement_id is None:
            QMessageBox.information(self, "Právní požadavky", "Vyberte požadavek.")
            return

        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            QMessageBox.warning(self, "Právní požadavky", "Požadavek nebyl nalezen.")
            self.refresh()
            return

        dialog = LegalRequirementCheckDialog(self, requirement=requirement)
        if exec_maximized(dialog):
            if dialog.created_task is not None:
                QMessageBox.information(
                    self,
                    "Úkol založen",
                    f"Byl založen úkol #{dialog.created_task.id}.",
                )
            self.refresh()

    def create_task_for_selected(self) -> None:
        requirement_id = self._selected_requirement_id()
        if requirement_id is None:
            QMessageBox.information(self, "Právní požadavky", "Vyberte požadavek.")
            return

        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            QMessageBox.warning(self, "Právní požadavky", "Požadavek nebyl nalezen.")
            self.refresh()
            return

        if not legal_requirement_task_service.can_create_task(requirement):
            QMessageBox.information(
                self,
                "Právní požadavky",
                "Úkol lze založit pouze u nesplněného nebo částečně splněného požadavku.",
            )
            return

        existing = legal_requirement_task_service.find_open_task(requirement_id)
        if existing is not None:
            QMessageBox.information(
                self,
                "Právní požadavky",
                f"Požadavek už má otevřený úkol #{existing.id}.",
            )
            return

        task = legal_requirement_task_service.create_task_from_requirement(requirement_id)
        QMessageBox.information(self, "Úkol založen", f"Byl založen úkol #{task.id}.")
        self.refresh()
