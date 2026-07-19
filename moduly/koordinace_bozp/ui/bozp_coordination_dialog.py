from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import (
    add_work_dialog_footer,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from moduly.koordinace_bozp.constants import (
    DEFAULT_BOZP_COORDINATION_STATUS,
    DIALOG_WINDOW_TITLE,
    LABEL_ACTION_NAME,
    LABEL_MEETING_DATE,
    LABEL_MEETING_PLACE,
    TAB_BASICS,
    TAB_CONTACTS,
    TAB_COORDINATOR,
    TAB_EMPLOYER_ACTIVITIES,
    TAB_EMPLOYERS,
    TAB_MEASURES,
    TAB_PARTICIPANTS,
    TAB_PBP_ATTACHMENT,
    TAB_RISK_SUBMISSIONS,
    TAB_WORKPLACES,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    CoordinationLifecycleBlocked,
    CoordinationLifecycleError,
    CoordinationLifecycleNeedsConfirmation,
    LifecycleAction,
    coordination_lifecycle_service,
    status_label,
)
from moduly.koordinace_bozp.sluzby.coordination_validity import add_one_year
from moduly.koordinace_bozp.ui.coordination_contacts_tab import (
    CoordinationContactsTab,
)
from moduly.koordinace_bozp.ui.coordination_coordinator_tab import (
    CoordinationCoordinatorTab,
)
from moduly.koordinace_bozp.ui.coordination_employer_activities_tab import (
    CoordinationEmployerActivitiesTab,
)
from moduly.koordinace_bozp.ui.coordination_employers_tab import (
    CoordinationEmployersTab,
)
from moduly.koordinace_bozp.ui.coordination_measures_tab import (
    CoordinationMeasuresTab,
)
from moduly.koordinace_bozp.ui.coordination_participants_tab import (
    CoordinationParticipantsTab,
)
from moduly.koordinace_bozp.ui.coordination_pbp_attachment_tab import (
    CoordinationPbpAttachmentTab,
)
from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
    CoordinationProtocolPreviewDialog,
)
from moduly.koordinace_bozp.ui.coordination_risk_submissions_tab import (
    CoordinationRiskSubmissionsTab,
)
from moduly.koordinace_bozp.ui.coordination_workplaces_tab import (
    CoordinationWorkplacesTab,
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

        basics_host = QWidget()
        basics_layout = QVBoxLayout(basics_host)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.number_label = QLabel()
        self.meeting_date = DateEdit()
        self.place = QLineEdit()
        self.subject = QLineEdit()
        self.status_label = QLabel()
        self.lifecycle_row = QHBoxLayout()
        self._lifecycle_buttons: list[QPushButton] = []
        self.valid_from = DateEdit()
        self.valid_to = DateEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(90)
        self.insert_default_measures = QCheckBox(
            "Vložit výchozí sadu organizačních opatření"
        )
        self.insert_default_measures.setChecked(True)

        form.addRow("Číslo koordinace:", self.number_label)
        form.addRow(f"{LABEL_MEETING_DATE}:", self.meeting_date)
        form.addRow(f"{LABEL_MEETING_PLACE}:", self.place)
        form.addRow(f"{LABEL_ACTION_NAME} *:", self.subject)
        form.addRow("Stav:", self.status_label)
        form.addRow("", self._wrap_lifecycle_row())
        form.addRow("Platnost od:", self.valid_from)
        form.addRow("Platnost do:", self.valid_to)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.insert_default_measures)

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

        self.coordinator_tab = CoordinationCoordinatorTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.coordinator_tab, TAB_COORDINATOR)

        self.workplaces_tab = CoordinationWorkplacesTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.workplaces_tab, TAB_WORKPLACES)

        self.employer_activities_tab = CoordinationEmployerActivitiesTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.employer_activities_tab, TAB_EMPLOYER_ACTIVITIES)

        self.measures_tab = CoordinationMeasuresTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.measures_tab, TAB_MEASURES)

        self.contacts_tab = CoordinationContactsTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.contacts_tab, TAB_CONTACTS)

        self.risk_submissions_tab = CoordinationRiskSubmissionsTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.risk_submissions_tab, TAB_RISK_SUBMISSIONS)

        self.pbp_attachment_tab = CoordinationPbpAttachmentTab(
            self,
            coordination_id=coordination_id,
        )
        self.tabs.addTab(self.pbp_attachment_tab, TAB_PBP_ATTACHMENT)
        layout.addWidget(self.tabs, 1)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.preview_btn = QPushButton("Náhled protokolu")
        self.preview_btn.setEnabled(coordination_id is not None)
        self.preview_btn.clicked.connect(self.open_protocol_preview)
        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        add_work_dialog_footer(
            layout,
            work_widgets=[self.preview_btn],
            buttons=buttons,
        )

        if coordination is None:
            self.number_label.setText(bozp_coordination_service.preview_next_number())
            self._refresh_status_ui(DEFAULT_BOZP_COORDINATION_STATUS)
            self._apply_default_validity_from_meeting()
            self.insert_default_measures.setVisible(True)
        else:
            self.number_label.setText(coordination.coordination_number or "")
            if coordination.meeting_date:
                self.meeting_date.setDate(_qdate_from_date(coordination.meeting_date))
            self.place.setText(coordination.place or "")
            self.subject.setText(coordination.subject or "")
            if coordination.valid_from:
                self.valid_from.setDate(_qdate_from_date(coordination.valid_from))
            if coordination.valid_to:
                self.valid_to.setDate(_qdate_from_date(coordination.valid_to))
            self.note.setPlainText(coordination.note or "")
            self.insert_default_measures.setVisible(False)
            self.insert_default_measures.setChecked(False)
            self._refresh_status_ui(coordination.status)

        self.meeting_date.dateChanged.connect(self._on_meeting_date_changed)
        # UX-COORD-1: editor se otevírá maximalizovaný.
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def _wrap_lifecycle_row(self) -> QWidget:
        host = QWidget()
        host.setLayout(self.lifecycle_row)
        self.lifecycle_row.setContentsMargins(0, 0, 0, 0)
        self.lifecycle_row.addStretch()
        return host

    def _refresh_status_ui(self, status: str | None) -> None:
        self.status_label.setText(status_label(status))
        for button in self._lifecycle_buttons:
            self.lifecycle_row.removeWidget(button)
            button.deleteLater()
        self._lifecycle_buttons.clear()

        if self.coordination is None:
            return

        for action in coordination_lifecycle_service.list_actions(status):
            button = QPushButton(action.label)
            button.clicked.connect(
                lambda _checked=False, act=action: self._run_lifecycle_action(act)
            )
            self.lifecycle_row.insertWidget(self.lifecycle_row.count() - 1, button)
            self._lifecycle_buttons.append(button)

    def _run_lifecycle_action(self, action: LifecycleAction) -> None:
        if self.coordination is None:
            return
        try:
            updated = self._transition_with_confirmations(action)
        except CoordinationLifecycleBlocked as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return
        except CoordinationLifecycleError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return
        self.coordination = updated
        self._refresh_status_ui(updated.status)

    def _transition_with_confirmations(self, action: LifecycleAction):
        assert self.coordination is not None
        confirm_warnings = False
        confirm_sensitive = False
        while True:
            try:
                return coordination_lifecycle_service.transition(
                    self.coordination.id,
                    action.target_status,
                    confirm_warnings=confirm_warnings,
                    confirm_sensitive=confirm_sensitive,
                )
            except CoordinationLifecycleNeedsConfirmation as error:
                answer = QMessageBox.question(
                    self,
                    DIALOG_WINDOW_TITLE,
                    str(error),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    raise CoordinationLifecycleError("Přechod byl zrušen.") from error
                if error.sensitive:
                    confirm_sensitive = True
                else:
                    confirm_warnings = True

    def _on_meeting_date_changed(self, *_args) -> None:
        if self._sync_validity_from_meeting:
            self._apply_default_validity_from_meeting()

    def _apply_default_validity_from_meeting(self) -> None:
        meeting = _date_from_qdate(self.meeting_date.date())
        self.valid_from.setDate(_qdate_from_date(meeting))
        self.valid_to.setDate(_qdate_from_date(add_one_year(meeting)))

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.participants_tab:
            self.participants_tab.refresh_employers()
        elif widget is self.coordinator_tab:
            self.coordinator_tab.refresh()
        elif widget is self.workplaces_tab:
            self.workplaces_tab.refresh()
        elif widget is self.employer_activities_tab:
            self.employer_activities_tab.refresh_employers()
        elif widget is self.measures_tab:
            self.measures_tab.refresh()
        elif widget is self.contacts_tab:
            self.contacts_tab.refresh()
        elif widget is self.risk_submissions_tab:
            self.risk_submissions_tab.refresh_employers()
        elif widget is self.pbp_attachment_tab:
            self.pbp_attachment_tab.refresh_status()
        elif widget is self.employers_tab:
            self.employers_tab.refresh()

    def open_protocol_preview(self) -> None:
        coordination_id = self.coordination.id if self.coordination is not None else None
        if coordination_id is None:
            QMessageBox.information(
                self,
                DIALOG_WINDOW_TITLE,
                "Náhled protokolu je dostupný po uložení koordinace.",
            )
            return
        dialog = CoordinationProtocolPreviewDialog(
            self,
            coordination_id=coordination_id,
        )
        dialog.exec()

    def get_data(self) -> dict:
        data = {
            "meeting_date": _date_from_qdate(self.meeting_date.date()),
            "place": self.place.text().strip(),
            "subject": self.subject.text().strip(),
            "note": self.note.toPlainText().strip(),
            "valid_from": _date_from_qdate(self.valid_from.date()),
            "valid_to": _date_from_qdate(self.valid_to.date()),
        }
        if self.coordination is None:
            data["insert_default_measures"] = self.insert_default_measures.isChecked()
        elif self.contacts_tab.coordination_id is not None:
            data.update(self.contacts_tab.get_procedures_data())
        return data
