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
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.ui.coordination_employers_tab import (
    CoordinationEmployersTab,
)


class BozpCoordinationDialog(QDialog):
    """Dialog koordinace BOZP – základní údaje a zaměstnavatelé."""

    def __init__(self, parent=None, coordination=None):
        super().__init__(parent)
        self.coordination = coordination
        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        configure_resizable_form_dialog(self, width=720, height=560, min_width=520, min_height=400)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

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
        self.note = QTextEdit()
        self.note.setMinimumHeight(90)

        form.addRow("Číslo koordinace:", self.number_label)
        form.addRow("Datum koordinační schůzky:", self.meeting_date)
        form.addRow("Místo:", self.place)
        form.addRow("Předmět koordinace *:", self.subject)
        form.addRow("Stav:", self.status)
        form.addRow("Poznámka:", self.note)

        basics_layout.addWidget(wrap_in_scroll_area(form_host), 1)
        self.tabs.addTab(basics_host, TAB_BASICS)

        coordination_id = coordination.id if coordination is not None else None
        self.employers_tab = CoordinationEmployersTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.employers_tab, TAB_EMPLOYERS)
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
        else:
            self.number_label.setText(coordination.coordination_number or "")
            if coordination.meeting_date:
                self.meeting_date.setDate(
                    QDate(
                        coordination.meeting_date.year,
                        coordination.meeting_date.month,
                        coordination.meeting_date.day,
                    )
                )
            self.place.setText(coordination.place or "")
            self.subject.setText(coordination.subject or "")
            index = self.status.findData(coordination.status)
            self.status.setCurrentIndex(index if index >= 0 else 0)
            self.note.setPlainText(coordination.note or "")

    def get_data(self) -> dict:
        qdate = self.meeting_date.date()
        return {
            "meeting_date": date(qdate.year(), qdate.month(), qdate.day()),
            "place": self.place.text().strip(),
            "subject": self.subject.text().strip(),
            "status": self.status.currentData() or DEFAULT_BOZP_COORDINATION_STATUS,
            "note": self.note.toPlainText().strip(),
        }
