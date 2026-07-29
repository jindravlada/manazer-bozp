from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
    coordination_employer_activity_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
    employer_abbreviation,
)
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    coordination_workplace_service,
)


class CoordinationEmployerActivityDialog(QDialog):
    """Přidání / úprava činnosti zaměstnavatele (COORD-008)."""

    def __init__(
        self,
        parent=None,
        *,
        coordination_id: int,
        activity=None,
        default_employer_id: int | None = None,
    ):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self.activity = activity
        self.setWindowTitle(
            "Upravit činnost" if activity is not None else "Přidat činnost"
        )
        configure_resizable_form_dialog(
            self,
            width=560,
            height=460,
            min_width=440,
            min_height=360,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.employer = QComboBox()
        self.workplace = QComboBox()
        self.activity_name = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(70)
        self.planned_from = NullableDateEdit()
        self.planned_to = NullableDateEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)

        form.addRow("Zaměstnavatel *:", self.employer)
        form.addRow("Místo výkonu práce:", self.workplace)
        form.addRow("Název činnosti *:", self.activity_name)
        form.addRow("Popis:", self.description)
        form.addRow("Plánováno od:", self.planned_from)
        form.addRow("Plánováno do:", self.planned_to)
        form.addRow("Poznámka:", self.note)
        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        preserve_employer = (
            activity.coordination_employer_id
            if activity is not None
            else default_employer_id
        )
        preserve_workplace = (
            activity.coordination_workplace_id if activity is not None else None
        )
        self._reload_employers(preserve_id=preserve_employer)
        self._reload_workplaces(preserve_id=preserve_workplace)

        if activity is not None:
            self.activity_name.setText(activity.activity_name or "")
            self.description.setPlainText(activity.description or "")
            if activity.planned_from:
                self.planned_from.set_date_value(activity.planned_from)
            if activity.planned_to:
                self.planned_to.set_date_value(activity.planned_to)
            self.note.setPlainText(activity.note or "")

    def _reload_employers(self, *, preserve_id: int | None = None) -> None:
        self.employer.clear()
        employers = coordination_employer_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        for item in employers:
            if not item.active and item.id != preserve_id:
                continue
            label = f"{employer_abbreviation(item)} – {item.company_name}".strip(" –")
            if not item.active:
                label = f"{label} (neaktivní)"
            self.employer.addItem(label, item.id)
        if preserve_id is not None:
            index = self.employer.findData(preserve_id)
            if index >= 0:
                self.employer.setCurrentIndex(index)

    def _reload_workplaces(self, *, preserve_id: int | None = None) -> None:
        self.workplace.clear()
        self.workplace.addItem("— bez místa —", None)
        places = coordination_workplace_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        for place in places:
            if not place.active and place.id != preserve_id:
                continue
            label = coordination_employer_activity_service.workplace_label(place.id)
            self.workplace.addItem(label or f"Místo #{place.id}", place.id)
        if preserve_id is not None:
            index = self.workplace.findData(preserve_id)
            if index >= 0:
                self.workplace.setCurrentIndex(index)

    def get_data(self) -> dict:
        workplace_id = self.workplace.currentData()
        return {
            "coordination_employer_id": self.employer.currentData(),
            "coordination_workplace_id": (
                int(workplace_id) if isinstance(workplace_id, int) else None
            ),
            "activity_name": self.activity_name.text(),
            "description": self.description.toPlainText(),
            "planned_from": self.planned_from.get_date(),
            "planned_to": self.planned_to.get_date(),
            "note": self.note.toPlainText(),
        }
