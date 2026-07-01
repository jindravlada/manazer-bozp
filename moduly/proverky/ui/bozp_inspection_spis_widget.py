from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.proverky.constants import (
    DEFAULT_INSPECTION_TYPE,
    INSPECTION_TYPES,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)


class BozpInspectionSpisWidget(QWidget):
    """Záložka Spis — identifikace prověrky BOZP."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.number_label = QLabel("—")
        self.number_label.setObjectName("InfoText")

        self.year_combo = QComboBox()
        self._populate_year_combo()

        self.planned_month_combo = QComboBox()
        self._populate_planned_month_combo()

        self.workplace_selector = WorkplaceSelector()

        basic_group = QGroupBox("Základní údaje")
        basic_form = QFormLayout(basic_group)
        basic_form.addRow("Číslo prověrky:", self.number_label)
        basic_form.addRow("Rok:", self.year_combo)
        basic_form.addRow("Plánovaný měsíc:", self.planned_month_combo)
        basic_form.addRow("Pracoviště:", self.workplace_selector)
        layout.addWidget(basic_group)

        self.inspection_date_edit = NullableDateEdit()
        self.started_at_edit = NullableDateEdit()

        terms_group = QGroupBox("Termíny")
        terms_form = QFormLayout(terms_group)
        terms_form.addRow("Datum prověrky:", self.inspection_date_edit)
        terms_form.addRow("Zahájení:", self.started_at_edit)
        layout.addWidget(terms_group)

        self.type_combo = QComboBox()
        self.type_combo.addItems(INSPECTION_TYPES)

        type_group = QGroupBox("Typ prověrky")
        type_form = QFormLayout(type_group)
        type_form.addRow("Typ:", self.type_combo)
        layout.addWidget(type_group)

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

        self._set_defaults()

    def _populate_year_combo(self) -> None:
        current_year = date.today().year

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for year in range(current_year - 2, current_year + 4):
            self.year_combo.addItem(str(year), year)
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.blockSignals(False)

    def _populate_planned_month_combo(self) -> None:
        self.planned_month_combo.clear()
        self.planned_month_combo.addItem(PLANNED_MONTH_NOT_SET_LABEL, None)
        for month_number, month_name in enumerate(PLANNED_MONTH_NAMES, start=1):
            self.planned_month_combo.addItem(month_name, month_number)
        self.planned_month_combo.setCurrentIndex(0)

    def _set_defaults(self) -> None:
        self.type_combo.setCurrentText(DEFAULT_INSPECTION_TYPE)
        self._populate_year_combo()
        self.planned_month_combo.setCurrentIndex(0)
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

    def _set_year(self, year: int) -> None:
        index = self.year_combo.findData(year)
        if index >= 0:
            self.year_combo.setCurrentIndex(index)
            return

        self.year_combo.blockSignals(True)
        self.year_combo.insertItem(0, str(year), year)
        self.year_combo.setCurrentIndex(0)
        self.year_combo.blockSignals(False)

    def _set_planned_month(self, planned_month: int | None) -> None:
        if planned_month is None:
            self.planned_month_combo.setCurrentIndex(0)
            return

        index = self.planned_month_combo.findData(planned_month)
        if index >= 0:
            self.planned_month_combo.setCurrentIndex(index)

    def set_number(self, number: str | None) -> None:
        display = (number or "").strip() or "—"
        self.number_label.setText(display)

    def load_inspection(self, inspection) -> None:
        if inspection is None:
            return

        self.set_number(getattr(inspection, "number", None))

        inspection_type = getattr(inspection, "inspection_type", None)
        if inspection_type:
            index = self.type_combo.findText(inspection_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

        year = getattr(inspection, "year", None)
        if year:
            self._set_year(year)

        planned_month = getattr(inspection, "planned_month", None)
        self._set_planned_month(planned_month)

        inspection_date = getattr(inspection, "inspection_date", None)
        if inspection_date is not None:
            self.inspection_date_edit.set_date_value(inspection_date)
        else:
            self.inspection_date_edit.clear_date()

        started_at = getattr(inspection, "started_at", None)
        if started_at is not None:
            self.started_at_edit.set_date_value(started_at)

        workplace_id = getattr(inspection, "workplace_id", None)
        workplace_name = getattr(inspection, "workplace_name", None)
        self.workplace_selector.set_workplace(workplace_id, workplace_name or "")

        self._set_saved_history_placeholder()

    def get_data(self) -> dict:
        return {
            "year": self.year_combo.currentData(),
            "planned_month": self.planned_month_combo.currentData(),
            "inspection_date": self.inspection_date_edit.get_date(),
            "started_at": self.started_at_edit.get_date(),
            "inspection_type": self.type_combo.currentText(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
        }
