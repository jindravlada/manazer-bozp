from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.audity.constants import (
    AUDIT_PREPARE_BUTTON,
    AUDIT_PREPARED_ON_LABEL,
    AUDIT_SCOPE_CLEAR,
    AUDIT_SCOPE_GROUP,
    AUDIT_SCOPE_SELECT_ALL,
    AUDIT_SCOPE_SUMMARY,
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
        self.expected_end_date_edit = NullableDateEdit()
        self.started_at_edit.dateChanged.connect(self._update_derived_status)

        terms_group = QGroupBox("Termíny")
        terms_form = QFormLayout(terms_group)
        terms_form.addRow("Plánované datum:", self.audit_date_edit)
        terms_form.addRow("Datum zahájení:", self.started_at_edit)
        terms_form.addRow("Předpokládané datum ukončení:", self.expected_end_date_edit)
        layout.addWidget(terms_group)

        self._scope_checks: list[QCheckBox] = []
        self._scope_editable = False
        self.scope_group = QGroupBox(AUDIT_SCOPE_GROUP)
        self.scope_group.setVisible(False)
        scope_layout = QVBoxLayout(self.scope_group)
        scope_buttons = QHBoxLayout()
        self.scope_select_all_button = QPushButton(AUDIT_SCOPE_SELECT_ALL)
        self.scope_clear_button = QPushButton(AUDIT_SCOPE_CLEAR)
        self.scope_select_all_button.clicked.connect(self.select_all_scope)
        self.scope_clear_button.clicked.connect(self.clear_scope)
        scope_buttons.addWidget(self.scope_select_all_button)
        scope_buttons.addWidget(self.scope_clear_button)
        scope_buttons.addStretch()
        scope_layout.addLayout(scope_buttons)
        self.scope_summary_label = QLabel(AUDIT_SCOPE_SUMMARY.format(selected=0, total=0))
        self.scope_summary_label.setObjectName("InfoText")
        scope_layout.addWidget(self.scope_summary_label)
        self.scope_scroll = QScrollArea()
        self.scope_scroll.setWidgetResizable(True)
        self.scope_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scope_scroll.setMaximumHeight(180)
        self.scope_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self._scope_list = QWidget()
        self._scope_list_layout = QVBoxLayout(self._scope_list)
        self._scope_list_layout.setContentsMargins(0, 0, 0, 0)
        self._scope_list_layout.setSpacing(2)
        self.scope_scroll.setWidget(self._scope_list)
        scope_layout.addWidget(self.scope_scroll)
        layout.addWidget(self.scope_group)

        prepare_row = QHBoxLayout()
        self.prepare_button = QPushButton(AUDIT_PREPARE_BUTTON)
        self.prepare_button.setVisible(False)
        self.prepared_label = QLabel("")
        self.prepared_label.setObjectName("InfoText")
        self.prepared_label.setVisible(False)
        prepare_row.addWidget(self.prepare_button)
        prepare_row.addWidget(self.prepared_label)
        prepare_row.addStretch()
        layout.addLayout(prepare_row)

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
        self.expected_end_date_edit.clear_date()
        self._update_derived_status()
        self.prepare_button.setVisible(False)
        self.prepared_label.setVisible(False)

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

    def apply_visit_context(self, visit_context) -> None:
        """Pracovní předvyplnění z plánované návštěvy. Nic nezapisuje."""
        year = getattr(visit_context, "planned_year", None)
        if year:
            self._set_year(int(year))
        self._set_planned_month(getattr(visit_context, "planned_month", None))
        workplace_id = getattr(visit_context, "workplace_id", None)
        workplace_name = getattr(visit_context, "workplace_name", None) or ""
        self.workplace_selector.set_workplace(workplace_id, workplace_name)
        planned_date = getattr(visit_context, "planned_date", None)
        if planned_date is not None:
            self.audit_date_edit.set_date_value(planned_date)
        else:
            self.audit_date_edit.clear_date()
        self.started_at_edit.clear_date()
        self.expected_end_date_edit.clear_date()
        self._finished_at = None
        self.set_number(None)
        self._update_derived_status()

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

        expected_end_date = getattr(audit, "expected_end_date", None)
        if expected_end_date is not None:
            self.expected_end_date_edit.set_date_value(expected_end_date)
        else:
            self.expected_end_date_edit.clear_date()

        self._finished_at = getattr(audit, "finished_at", None)

        workplace_id = getattr(audit, "workplace_id", None)
        workplace_name = getattr(audit, "workplace_name", None)
        self.workplace_selector.set_workplace(workplace_id, workplace_name or "")

        self._update_derived_status()
        self._refresh_prepare_state(audit)

    def _refresh_prepare_state(self, audit) -> None:
        from moduly.audity.sluzby.audit_v2_create_service import is_planned_unfrozen

        frozen_at = getattr(audit, "questions_frozen_at", None) if audit is not None else None
        unfrozen = audit is not None and getattr(audit, "id", None) and is_planned_unfrozen(audit)
        self.prepare_button.setVisible(bool(unfrozen) and frozen_at is None)
        if frozen_at is not None and not unfrozen:
            self.prepared_label.setText(
                AUDIT_PREPARED_ON_LABEL.format(date=frozen_at.strftime("%d.%m.%Y"))
            )
            self.prepared_label.setVisible(True)
        else:
            self.prepared_label.clear()
            self.prepared_label.setVisible(False)

    def hide_audit_scope(self) -> None:
        self.scope_group.setVisible(False)
        self._scope_editable = False

    def show_editable_scope(
        self,
        processes: list[tuple[str, str]],
        selected_ids: set[str] | None = None,
    ) -> None:
        selected = set(selected_ids or ())
        self._fill_scope(
            processes,
            selected,
            editable=True,
        )

    def show_readonly_scope(self, processes: list[tuple[str, str]]) -> None:
        ids = {process_id for process_id, _name in processes}
        self._fill_scope(processes, ids, editable=False)

    def select_all_scope(self) -> None:
        if not self._scope_editable:
            return
        for checkbox in self._scope_checks:
            checkbox.setChecked(True)
        self._update_scope_summary()

    def clear_scope(self) -> None:
        if not self._scope_editable:
            return
        for checkbox in self._scope_checks:
            checkbox.setChecked(False)
        self._update_scope_summary()

    def selected_scope(self) -> list[dict]:
        chosen: list[dict] = []
        order = 0
        for checkbox in self._scope_checks:
            if not checkbox.isChecked():
                continue
            chosen.append(
                {
                    "process_id": checkbox.property("process_id"),
                    "process_name": checkbox.text(),
                    "display_order": order,
                }
            )
            order += 1
        return chosen

    def _fill_scope(
        self,
        processes: list[tuple[str, str]],
        selected_ids: set[str],
        *,
        editable: bool,
    ) -> None:
        while self._scope_list_layout.count():
            item = self._scope_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._scope_checks = []
        self._scope_editable = editable
        self.scope_select_all_button.setEnabled(editable)
        self.scope_clear_button.setEnabled(editable)
        for process_id, process_name in processes:
            checkbox = QCheckBox(process_name)
            checkbox.setProperty("process_id", process_id)
            checkbox.setEnabled(editable)
            checkbox.blockSignals(True)
            checkbox.setChecked(process_id in selected_ids)
            checkbox.blockSignals(False)
            checkbox.toggled.connect(lambda _checked: self._update_scope_summary())
            self._scope_list_layout.addWidget(checkbox)
            self._scope_checks.append(checkbox)
        self.scope_group.setVisible(True)
        self._update_scope_summary()

    def _update_scope_summary(self) -> None:
        total = len(self._scope_checks)
        selected = sum(1 for checkbox in self._scope_checks if checkbox.isChecked())
        self.scope_summary_label.setText(
            AUDIT_SCOPE_SUMMARY.format(selected=selected, total=total)
        )

    def get_data(self) -> dict:
        return {
            "year": self.year_combo.currentData(),
            "planned_month": self.planned_month_combo.currentData(),
            "audit_date": self.audit_date_edit.get_date(),
            "started_at": self.started_at_edit.get_date(),
            "expected_end_date": self.expected_end_date_edit.get_date(),
            "finished_at": self._finished_at,
            "audit_type": self.type_combo.currentText(),
            "workplace_id": self.workplace_selector.current_workplace_id(),
        }
