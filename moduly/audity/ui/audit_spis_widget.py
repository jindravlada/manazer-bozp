from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.audity.constants import (
    AUDIT_STATUS_PLANOVANO,
    AUDIT_TYPES,
    DEFAULT_AUDIT_TYPE,
    PLANNED_MONTH_NAMES,
    PLANNED_MONTH_NOT_SET_LABEL,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    list_auditable_workplaces,
)
from moduly.audity.sluzby.audit_service import audit_service


class AuditSpisWidget(QWidget):
    """Záložka Spis — identifikace auditu systému řízení."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._finished_at: date | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.number_label = QLabel("—")
        self.number_label.setObjectName("InfoText")

        self.status_label = QLabel(AUDIT_STATUS_PLANOVANO)
        self.status_label.setObjectName("InfoText")

        self.year_combo = QComboBox()
        self._populate_year_combo()

        self.planned_month_combo = QComboBox()
        self._populate_planned_month_combo()

        self.workplace_selector = WorkplaceSelector(
            workplaces_loader=list_auditable_workplaces,
        )

        basic_group = QGroupBox("Základní údaje")
        basic_form = QFormLayout(basic_group)
        basic_form.addRow("Číslo auditu:", self.number_label)
        basic_form.addRow("Stav:", self.status_label)
        basic_form.addRow("Rok:", self.year_combo)
        basic_form.addRow("Plánovaný měsíc:", self.planned_month_combo)
        basic_form.addRow("Auditovaný provoz:", self.workplace_selector)
        layout.addWidget(basic_group)

        self.audit_date_edit = NullableDateEdit()
        self.started_at_edit = NullableDateEdit()
        self.started_at_edit.dateChanged.connect(self._update_derived_status)

        terms_group = QGroupBox("Termíny")
        terms_form = QFormLayout(terms_group)
        terms_form.addRow("Datum auditu:", self.audit_date_edit)
        terms_form.addRow("Datum zahájení:", self.started_at_edit)
        layout.addWidget(terms_group)

        self.type_combo = QComboBox()
        self.type_combo.addItems(AUDIT_TYPES)

        type_group = QGroupBox("Typ auditu")
        type_form = QFormLayout(type_group)
        type_form.addRow("Typ:", self.type_combo)
        layout.addWidget(type_group)

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
        self.type_combo.setCurrentText(DEFAULT_AUDIT_TYPE)
        self._populate_year_combo()
        self.planned_month_combo.setCurrentIndex(0)
        self._finished_at = None
        self._update_derived_status()

    def _update_derived_status(self) -> None:
        started_at = self.started_at_edit.get_date()
        status = audit_service.derive_status(started_at, self._finished_at)
        self.status_label.setText(status)

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

    def load_audit(self, audit) -> None:
        if audit is None:
            self._set_defaults()
            self.set_number(None)
            return

        self.set_number(getattr(audit, "number", None))

        audit_type = getattr(audit, "audit_type", None)
        if audit_type:
            index = self.type_combo.findText(audit_type)
            if index >= 0:
                self.type_combo.setCurrentIndex(index)

        year = getattr(audit, "year", None)
        if year:
            self._set_year(year)

        planned_month = getattr(audit, "planned_month", None)
        self._set_planned_month(planned_month)

        audit_date = getattr(audit, "audit_date", None)
        if audit_date is not None:
            self.audit_date_edit.set_date_value(audit_date)
        else:
            self.audit_date_edit.clear_date()

        started_at = getattr(audit, "started_at", None)
        if started_at is not None:
            self.started_at_edit.set_date_value(started_at)
        else:
            self.started_at_edit.clear_date()

        self._finished_at = getattr(audit, "finished_at", None)

        workplace_id = getattr(audit, "workplace_id", None)
        workplace_name = getattr(audit, "workplace_name", None)
        self.workplace_selector.set_workplace(workplace_id, workplace_name or "")

        self._update_derived_status()

    def get_data(self) -> dict:
        return {
            "year": self.year_combo.currentData(),
            "planned_month": self.planned_month_combo.currentData(),
            "audit_date": self.audit_date_edit.get_date(),
            "started_at": self.started_at_edit.get_date(),
            "finished_at": self._finished_at,
            "audit_type": self.type_combo.currentText(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
        }
