from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QToolButton,
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
from core.widgets.editor_dialog_controller import (
    configure_editor_close_button,
    confirm_unsaved_editor_close,
)
from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUS_DRAFT,
    BOZP_COORDINATION_STATUS_READY,
    DEFAULT_BOZP_COORDINATION_STATUS,
    DIALOG_WINDOW_TITLE,
    LABEL_ACTION_NAME,
    LABEL_MEETING_DATE,
    LABEL_MEETING_PLACE,
    READY_EDIT_REVERT_MESSAGE,
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
    BozpCoordinationError,
    bozp_coordination_service,
    default_meeting_place_from_settings,
)
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    LifecycleAction,
    coordination_lifecycle_service,
    is_content_editable,
    is_strict_readonly,
    normalize_coordination_status,
    status_color,
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
from moduly.koordinace_bozp.ui.coordination_lifecycle_ui import (
    run_lifecycle_transition,
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
        self._ready_edit_guard_armed = False
        self._applying_edit_policy = False
        self._dirty = False
        self._closing = False
        self.setWindowTitle(DIALOG_WINDOW_TITLE)
        configure_resizable_form_dialog(self, width=760, height=600, min_width=540, min_height=420)

        layout = QVBoxLayout(self)

        status_bar = QHBoxLayout()
        self.status_caption = QLabel("Stav:")
        self.status_value = QLabel()
        status_font = QFont(self.status_value.font())
        status_font.setBold(True)
        status_font.setPointSize(status_font.pointSize() + 1)
        self.status_value.setFont(status_font)
        self.change_status_btn = QToolButton()
        self.change_status_btn.setText("Změnit stav")
        self.change_status_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.change_status_menu = QMenu(self)
        self.change_status_btn.setMenu(self.change_status_menu)
        status_bar.addWidget(self.status_caption)
        status_bar.addWidget(self.status_value)
        status_bar.addStretch()
        status_bar.addWidget(self.change_status_btn)
        layout.addLayout(status_bar)

        self.tabs = QTabWidget()

        basics_host = QWidget()
        basics_layout = QVBoxLayout(basics_host)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.number_label = QLabel()
        self.meeting_date = DateEdit()
        self.place = QLineEdit()
        self.subject = QLineEdit()
        self.valid_from = DateEdit()
        self.valid_to = DateEdit()
        self.note = QTextEdit()
        self.note.setMinimumHeight(90)

        form.addRow("Číslo koordinace:", self.number_label)
        form.addRow(f"{LABEL_MEETING_DATE}:", self.meeting_date)
        form.addRow(f"{LABEL_MEETING_PLACE}:", self.place)
        form.addRow(f"{LABEL_ACTION_NAME} *:", self.subject)
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

        self.coordinator_tab = CoordinationCoordinatorTab(
            self,
            coordination_id=coordination_id,
        )
        self.coordinator_tab.set_dirty_callback(self.mark_dirty)
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
        self.buttons = create_save_cancel_box(self, is_new=coordination is None)
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.close_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.save_button is not None:
            self.save_button.clicked.connect(self._save)
        self.buttons.rejected.connect(self.reject)
        add_work_dialog_footer(
            layout,
            work_widgets=[self.preview_btn],
            buttons=self.buttons,
        )

        if coordination is None:
            self.number_label.setText(bozp_coordination_service.preview_next_number())
            self.place.setText(default_meeting_place_from_settings())
            self._apply_default_validity_from_meeting()
            self._refresh_status_ui(DEFAULT_BOZP_COORDINATION_STATUS)
            self._set_detail_tabs_enabled(False)
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
            self._refresh_status_ui(coordination.status)
            self._set_detail_tabs_enabled(True)

        self.meeting_date.dateChanged.connect(self._on_meeting_date_changed)
        self.meeting_date.dateChanged.connect(self._on_content_edited)
        self.place.textEdited.connect(self._on_content_edited)
        self.subject.textEdited.connect(self._on_content_edited)
        self.valid_from.dateChanged.connect(self._on_content_edited)
        self.valid_to.dateChanged.connect(self._on_content_edited)
        self.note.textChanged.connect(self._on_content_edited)
        self.place.textEdited.connect(self.mark_dirty)
        self.subject.textEdited.connect(self.mark_dirty)
        self.meeting_date.dateChanged.connect(self.mark_dirty)
        self.valid_from.dateChanged.connect(self.mark_dirty)
        self.valid_to.dateChanged.connect(self.mark_dirty)
        self.note.textChanged.connect(self.mark_dirty)
        # UX-COORD-1: editor se otevírá maximalizovaný.
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)

    def is_dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self, *_args) -> None:
        if self._applying_edit_policy or self._closing:
            return
        self._dirty = True
        self._update_save_enabled()

    def mark_clean(self) -> None:
        self._dirty = False
        self._update_save_enabled()

    def _update_save_enabled(self) -> None:
        if self.save_button is None:
            return
        if self.coordination is None:
            self.save_button.setEnabled(True)
            self.save_button.setVisible(True)
            return
        editable = is_content_editable(self.coordination.status)
        self.save_button.setVisible(editable)
        self.save_button.setEnabled(editable and self.is_dirty())

    def _content_tabs(self):
        return (
            self.employers_tab,
            self.participants_tab,
            self.coordinator_tab,
            self.workplaces_tab,
            self.employer_activities_tab,
            self.measures_tab,
            self.contacts_tab,
            self.risk_submissions_tab,
            self.pbp_attachment_tab,
        )

    def _set_detail_tabs_enabled(self, enabled: bool) -> None:
        """Záložky mimo Základní údaje – až po prvním uložení."""
        for index in range(1, self.tabs.count()):
            self.tabs.setTabEnabled(index, enabled)

    def _bind_coordination_to_tabs(self) -> None:
        coordination_id = self.coordination.id if self.coordination is not None else None
        for tab in self._content_tabs():
            tab.set_coordination_id(coordination_id)

    def _become_existing(self, coordination) -> None:
        """Po prvním uložení nové koordinace – aktivovat editor záložek."""
        self.coordination = coordination
        self._sync_validity_from_meeting = False
        self.number_label.setText(coordination.coordination_number or "")
        self.preview_btn.setEnabled(True)
        self._bind_coordination_to_tabs()
        self._set_detail_tabs_enabled(True)
        configure_editor_close_button(self.close_button, is_new=False)
        self._refresh_status_ui(coordination.status)

    def _save(self) -> bool:
        """Uloží koordinaci (včetně koordinátora) a ponechá editor otevřený."""
        if self.coordination is not None and is_strict_readonly(self.coordination.status):
            return False
        if self._ready_edit_guard_armed and not self.ensure_editable_for_content_change():
            return False
        data = self.get_data()
        try:
            if self.coordination is None:
                created = bozp_coordination_service.create_coordination(**data)
                self._become_existing(created)
            else:
                updated = bozp_coordination_service.update_coordination(
                    self.coordination.id,
                    **data,
                )
                if updated is not None:
                    self.coordination = updated
                    self._refresh_status_ui(updated.status)
        except BozpCoordinationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return False
        if not self.coordinator_tab.persist_coordinator():
            return False
        self.mark_clean()
        return True

    def _refresh_status_ui(self, status: str | None) -> None:
        normalized = normalize_coordination_status(status)
        self.status_value.setText(status_label(normalized))
        self.status_value.setStyleSheet(f"color: {status_color(normalized)};")
        self.change_status_menu.clear()
        self.change_status_btn.setEnabled(self.coordination is not None)
        if self.coordination is not None:
            for action in coordination_lifecycle_service.list_actions(normalized):
                menu_action = self.change_status_menu.addAction(action.label)
                menu_action.triggered.connect(
                    lambda _checked=False, act=action: self._run_lifecycle_action(act)
                )
            self.change_status_btn.setEnabled(
                not self.change_status_menu.isEmpty()
            )
        self._ready_edit_guard_armed = normalized == BOZP_COORDINATION_STATUS_READY
        self._apply_edit_policy(normalized)

    def _apply_edit_policy(self, status: str | None) -> None:
        self._applying_edit_policy = True
        try:
            editable = is_content_editable(status)
            readonly = is_strict_readonly(status)
            self.meeting_date.setEnabled(editable)
            self.place.setReadOnly(not editable)
            self.subject.setReadOnly(not editable)
            self.valid_from.setEnabled(editable)
            self.valid_to.setEnabled(editable)
            self.note.setReadOnly(not editable)

            self._update_save_enabled()

            before_mutate = (
                self.ensure_editable_for_content_change
                if normalize_coordination_status(status) == BOZP_COORDINATION_STATUS_READY
                else None
            )
            for tab in self._content_tabs():
                if hasattr(tab, "set_content_editable"):
                    tab.set_content_editable(
                        editable and not readonly,
                        before_mutate=before_mutate,
                    )
        finally:
            self._applying_edit_policy = False

    def _revert_ready_to_draft(self) -> bool:
        if self.coordination is None:
            return False
        if not self._persist_current_form():
            return False
        try:
            updated = coordination_lifecycle_service.transition(
                self.coordination.id,
                BOZP_COORDINATION_STATUS_DRAFT,
            )
        except Exception as error:  # noqa: BLE001 – UI feedback
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return False
        self.coordination = updated
        self._ready_edit_guard_armed = False
        self._refresh_status_ui(updated.status)
        return True

    def ensure_editable_for_content_change(self) -> bool:
        """Guard pro první obsahovou změnu ve stavu Připraveno k vydání."""
        if not self._ready_edit_guard_armed or self.coordination is None:
            return True
        answer = QMessageBox.question(
            self,
            DIALOG_WINDOW_TITLE,
            READY_EDIT_REVERT_MESSAGE,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False
        return self._revert_ready_to_draft()

    def _on_content_edited(self, *_args) -> None:
        if self._applying_edit_policy or not self._ready_edit_guard_armed:
            return
        if not self.ensure_editable_for_content_change():
            self._reload_basics_from_coordination()

    def _reload_basics_from_coordination(self) -> None:
        coordination = self.coordination
        if coordination is None:
            return
        self._applying_edit_policy = True
        try:
            if coordination.meeting_date:
                self.meeting_date.setDate(_qdate_from_date(coordination.meeting_date))
            self.place.setText(coordination.place or "")
            self.subject.setText(coordination.subject or "")
            if coordination.valid_from:
                self.valid_from.setDate(_qdate_from_date(coordination.valid_from))
            if coordination.valid_to:
                self.valid_to.setDate(_qdate_from_date(coordination.valid_to))
            self.note.setPlainText(coordination.note or "")
        finally:
            self._applying_edit_policy = False

    def _persist_current_form(self) -> bool:
        if self.coordination is None:
            return True
        if is_strict_readonly(self.coordination.status):
            return True
        try:
            updated = bozp_coordination_service.update_coordination(
                self.coordination.id,
                **self.get_data(),
            )
        except BozpCoordinationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return False
        if updated is not None:
            self.coordination = updated
        if not self.coordinator_tab.persist_coordinator():
            return False
        self.mark_clean()
        return True

    def _run_lifecycle_action(self, action: LifecycleAction) -> None:
        if self.coordination is None:
            return
        updated = run_lifecycle_transition(
            self,
            self.coordination.id,
            action,
            before_transition=self._persist_current_form,
        )
        if updated is None:
            return
        self.coordination = updated
        self._refresh_status_ui(updated.status)

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
            self.coordinator_tab.refresh_lookups()
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
        if self.coordination is not None and is_content_editable(self.coordination.status):
            self._persist_current_form()
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
        if (
            self.coordination is not None
            and self.contacts_tab.coordination_id is not None
        ):
            data.update(self.contacts_tab.get_procedures_data())
        if (
            self.coordination is not None
            and self.measures_tab.coordination_id is not None
        ):
            data.update(self.measures_tab.get_agreement_data())
        return data

    def _prompt_unsaved_close(self) -> str:
        return confirm_unsaved_editor_close(self, title=DIALOG_WINDOW_TITLE)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing or not self.is_dirty():
            self._closing = True
            super().closeEvent(event)
            return
        decision = self._prompt_unsaved_close()
        if decision == "cancel":
            event.ignore()
            return
        if decision == "save":
            if not self._save():
                event.ignore()
                return
        self._closing = True
        super().closeEvent(event)

    def reject(self) -> None:
        if self._closing:
            super().reject()
            return
        if self.is_dirty():
            decision = self._prompt_unsaved_close()
            if decision == "cancel":
                return
            if decision == "save":
                if not self._save():
                    return
        self._closing = True
        super().reject()
