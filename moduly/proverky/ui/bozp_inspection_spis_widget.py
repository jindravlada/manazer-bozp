from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.proverky.constants import (
    DEFAULT_INSPECTION_SPIS_STATUS,
    DEFAULT_INSPECTION_TYPE,
    INSPECTION_SPIS_STATUSES,
    INSPECTION_TYPES,
)


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

        self.inspection_date_edit = NullableDateEdit()
        self.started_at_edit = NullableDateEdit()
        self.finished_at_edit = NullableDateEdit()

        self.status_combo = QComboBox()
        self.status_combo.addItems(INSPECTION_SPIS_STATUSES)

        self.type_combo = QComboBox()
        self.type_combo.addItems(INSPECTION_TYPES)

        self.workplace_selector = WorkplaceSelector()
        self.workplace_manager_selector = ThpWorkerSelector()
        self.bozp_specialist_selector = ThpWorkerSelector()
        self.commission_chair_selector = ThpWorkerSelector()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Např. Veřejná prověrka BOZP/PO")

        left_form.addRow("Číslo prověrky:", self.number_label)
        left_form.addRow("Rok:", self.year_combo)
        left_form.addRow("Datum prověrky:", self.inspection_date_edit)
        left_form.addRow("Zahájení:", self.started_at_edit)
        left_form.addRow("Ukončení:", self.finished_at_edit)
        left_form.addRow("Stav:", self.status_combo)
        left_form.addRow("Typ prověrky:", self.type_combo)

        right_form.addRow("Pracoviště:", self.workplace_selector)
        right_form.addRow("Vedoucí pracoviště:", self.workplace_manager_selector)
        right_form.addRow("Specialista BOZP:", self.bozp_specialist_selector)
        right_form.addRow("Předseda komise:", self.commission_chair_selector)
        right_form.addRow("Stručný název prověrky:", self.title_edit)

        columns.addLayout(left_form, 1)
        columns.addLayout(right_form, 1)
        layout.addWidget(card)

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

        self.inspection_date_edit.dateChanged.connect(self._sync_year_from_inspection_date)
        self._set_defaults()

    def _populate_year_combo(self) -> None:
        current_year = date.today().year
        years = range(current_year + 1, current_year - 6, -1)

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for year in years:
            self.year_combo.addItem(str(year), year)
        self.year_combo.blockSignals(False)

    def _set_defaults(self) -> None:
        today = date.today()
        self.status_combo.setCurrentText(DEFAULT_INSPECTION_SPIS_STATUS)
        self.type_combo.setCurrentText(DEFAULT_INSPECTION_TYPE)
        self.inspection_date_edit.set_date_value(today)
        self._set_year(today.year)
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

    def _sync_year_from_inspection_date(self) -> None:
        inspection_date = self.inspection_date_edit.get_date()
        if inspection_date is not None:
            self._set_year(inspection_date.year)

    def _set_year(self, year: int) -> None:
        index = self.year_combo.findData(year)
        if index >= 0:
            self.year_combo.setCurrentIndex(index)
            return

        self.year_combo.blockSignals(True)
        self.year_combo.insertItem(0, str(year), year)
        self.year_combo.setCurrentIndex(0)
        self.year_combo.blockSignals(False)

    def set_number(self, number: str | None) -> None:
        display = (number or "").strip() or "—"
        self.number_label.setText(display)
        self.number_header.setText(f"Číslo: {display}")

    def load_inspection(self, inspection) -> None:
        if inspection is None:
            return

        self.set_number(getattr(inspection, "number", None))
        title = getattr(inspection, "title", None)
        if title:
            self.title_edit.setText(title)

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

        inspection_date = getattr(inspection, "inspection_date", None)
        if inspection_date is not None:
            self.inspection_date_edit.set_date_value(inspection_date)

        started_at = getattr(inspection, "started_at", None)
        if started_at is not None:
            self.started_at_edit.set_date_value(started_at)

        finished_at = getattr(inspection, "finished_at", None)
        if finished_at is not None:
            self.finished_at_edit.set_date_value(finished_at)

        workplace_id = getattr(inspection, "workplace_id", None)
        if workplace_id:
            self.workplace_selector.set_workplace_id(workplace_id)

        workplace_manager_id = getattr(inspection, "workplace_manager_id", None)
        if workplace_manager_id:
            self.workplace_manager_selector.set_person_id(workplace_manager_id)

        bozp_specialist_id = getattr(inspection, "bozp_specialist_id", None)
        if bozp_specialist_id:
            self.bozp_specialist_selector.set_person_id(bozp_specialist_id)

        commission_chair_id = getattr(inspection, "commission_chair_id", None)
        if commission_chair_id:
            self.commission_chair_selector.set_person_id(commission_chair_id)

        self._set_saved_history_placeholder()
