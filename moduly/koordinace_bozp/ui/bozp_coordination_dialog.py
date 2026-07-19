from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUS_LABELS,
    BOZP_COORDINATION_STATUSES,
    DEFAULT_BOZP_COORDINATION_STATUS,
    DIALOG_WINDOW_TITLE,
    TAB_BASICS,
    TAB_EMPLOYERS,
    TAB_PARTICIPANTS,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_validity import add_one_year
from moduly.koordinace_bozp.ui.coordination_employers_tab import (
    CoordinationEmployersTab,
)
from moduly.koordinace_bozp.ui.coordination_participants_tab import (
    CoordinationParticipantsTab,
)


def _qdate_from_date(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)


def _date_from_qdate(value: QDate) -> date:
    return date(value.year(), value.month(), value.day())


class BozpCoordinationDialog(QDialog):
    """Dialog koordinace BOZP – údaje, zaměstnavatelé a účastníci."""

    def __init__(self, parent=None, coordination=None):
        super().__init__(parent)
        self.coordination = coordination
        self._sync_validity_from_meeting = coordination is None
        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        configure_resizable_form_dialog(self, width=760, height=600, min_width=540, min_height=420)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        basics_host = QWidget()
        basics_layout = QVBoxLayout(basics_host)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.number_label = QLabel()
        self.meeting_date = DateEdit()
        self.place = QLineEdit()
        self.subject = QLineEdit()
        self.status = QComboBox()
        for status_id in BOZP_COORDINATION_STATUSES:
            self.status.addItem(BOZP_COORDINATION_STATUS_LABELS[status_id], status_id)
        self.valid_from = DateEdit()
        self.valid_to = DateEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(90)

        form.addRow("Číslo koordinace:", self.number_label)
        form.addRow("Datum koordinační schůzky:", self.meeting_date)
        form.addRow("Místo:", self.place)
        form.addRow("Předmět koordinace *:", self.subject)
        form.addRow("Stav:", self.status)
        form.addRow("Platnost od:", self.valid_from)
        form.addRow("Platnost do:", self.valid_to)
        form.addRow("Poznámka:", self.note)

        basics_layout.addWidget(wrap_in_scroll_area(form_host), 1)
        self.tabs.addTab(basics_host, TAB_BASICS)

        coordination_id = coordination.id if coordination is not None else None
        self.employers_tab = CoordinationEmployersTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.employers_tab, TAB_EMPLOYERS)

        self.participants_tab = CoordinationParticipantsTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.participants_tab, TAB_PARTICIPANTS)
        layout.addWidget(self.tabs, 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if coordination is None:
            self.number_label.setText(bozp_coordination_service.preview_next_number())
            self.status.setCurrentIndex(
                self.status.findData(DEFAULT_BOZP_COORDINATION_STATUS)
            )
            self._apply_default_validity_from_meeting()
        else:
            self.number_label.setText(coordination.coordination_number or "")
            if coordination.meeting_date:
                self.meeting_date.setDate(_qdate_from_date(coordination.meeting_date))
            self.place.setText(coordination.place or "")
            self.subject.setText(coordination.subject or "")
            index = self.status.findData(coordination.status)
            self.status.setCurrentIndex(index if index >= 0 else 0)
            if coordination.valid_from:
                self.valid_from.setDate(_qdate_from_date(coordination.valid_from))
            if coordination.valid_to:
                self.valid_to.setDate(_qdate_from_date(coordination.valid_to))
            self.note.setPlainText(coordination.note or "")

        self.meeting_date.dateChanged.connect(self._on_meeting_date_changed)

    def _on_meeting_date_changed(self, *_args) -> None:
        if self._sync_validity_from_meeting:
            self._apply_default_validity_from_meeting()

    def _apply_default_validity_from_meeting(self) -> None:
        meeting = _date_from_qdate(self.meeting_date.date())
        self.valid_from.setDate(_qdate_from_date(meeting))
        self.valid_to.setDate(_qdate_from_date(add_one_year(meeting)))

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.participants_tab:
            self.participants_tab.refresh_employers()

    def get_data(self) -> dict:
        return {
            "meeting_date": _date_from_qdate(self.meeting_date.date()),
            "place": self.place.text().strip(),
            "subject": self.subject.text().strip(),
            "status": self.status.currentData() or DEFAULT_BOZP_COORDINATION_STATUS,
            "note": self.note.toPlainText().strip(),
            "valid_from": _date_from_qdate(self.valid_from.date()),
            "valid_to": _date_from_qdate(self.valid_to.date()),
        }
