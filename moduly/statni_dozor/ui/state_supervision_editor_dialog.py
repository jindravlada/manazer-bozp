"""Editor kontroly státního dozoru — pět záložek včetně průběhu a zjištění."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.models.attachment_staging import (
    AttachmentStagingError,
    AttachmentStagingState,
)
from core.services.attachment_service import attachment_service
from core.widgets.dialog_utils import (
    configure_create_linked_action_button,
    configure_edit_action_button,
    configure_form_tab_navigation,
    configure_new_action_button,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import (
    EditorDialogController,
    configure_editor_save_button,
)
from core.widgets.info_tooltip import set_widget_tooltip
from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
from core.widgets.search_combo_box import SearchComboBox
from core.shared.finding_display import FINDING_STATUS_LABELS
from core.widgets.table_utils import apply_cell_tooltip, configure_table_columns
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    ACTION_ADD,
    ACTION_CREATE_TASK,
    ACTION_EDIT,
    ACTION_MOVE_DOWN,
    ACTION_MOVE_UP,
    ACTION_OPEN_TASK,
    ACTION_REMOVE,
    ACTION_SAVE_AND_CLOSE,
    AUTHORITY_REQUIRED_MESSAGE,
    AUTHORITY_SUGGESTIONS,
    CLOSED_AT_REQUIRED_MESSAGE,
    CLOSED_BEFORE_ENDED_MESSAGE,
    DEFAULT_STATUS,
    DIALOG_TITLE_EDIT,
    DIALOG_TITLE_NEW,
    ATTENDANCE_UNEVALUATED_LABEL,
    COL_DOCUMENT_TITLE,
    COL_FINDING_TASK,
    COL_FINDING_TYPE,
    COL_PARTICIPANT_ROLE,
    COL_TIMELINE_TITLE,
    DOCUMENT_COLUMN_HEADERS,
    EMPTY_DOCUMENTS,
    EMPTY_FINDINGS,
    EMPTY_PARTICIPANTS,
    EMPTY_TIMELINE,
    EMPTY_VALUE,
    FINDING_COLUMN_HEADERS,
    FINDING_STORED_REMOVE_HINT,
    FINDING_TASK_DIRTY_TOOLTIP,
    FINDING_TASK_HINT_DIRTY,
    FINDING_TASK_HINT_LINKED,
    FINDING_TASK_HINT_UNSAVED,
    FINDING_TASK_LINKED,
    FINDING_TASK_MISSING_LABEL,
    FINDING_TASK_MISSING_OPEN_MESSAGE,
    FINDING_TASK_NOT_FOUND_MESSAGE,
    FINDING_TASK_RELOAD_FAILED_MESSAGE,
    FINDING_TASK_SAVE_FIRST_TOOLTIP,
    ENDED_BEFORE_STARTED_MESSAGE,
    ENTITY_STATE_SUPERVISION,
    GROUP_ACTUAL_COURSE,
    GROUP_COMPLETION_CLOSE,
    GROUP_COURSE_TIMELINE,
    GROUP_FINDINGS,
    GROUP_INFORMING,
    GROUP_INITIAL_INFORMATION,
    GROUP_NOTIFICATION,
    GROUP_OBJECTIONS,
    GROUP_PARTICIPANTS,
    GROUP_PLANNED_START,
    GROUP_PREPARATION,
    GROUP_PROTOCOL,
    GROUP_REPRESENTATION,
    GROUP_REQUIRED_DOCUMENTS,
    GROUP_RESULT,
    GROUP_SUBJECT,
    LABEL_ANNOUNCED_AT,
    LABEL_AUTHORITY,
    LABEL_AUTHORITY_ADDRESS,
    LABEL_AUTHORITY_CONFIRMATION_AT,
    LABEL_AUTHORITY_ICO,
    LABEL_CLOSED_AT,
    LABEL_COMPLETION_EVIDENCE_SENT_AT,
    LABEL_ENDED_AT,
    LABEL_FILE_NUMBER,
    LABEL_FINAL_SUMMARY,
    LABEL_INITIAL_INFORMATION,
    LABEL_MANAGEMENT_NOTIFIED_AT,
    LABEL_NOTIFICATION_METHOD,
    LABEL_NOTIFICATION_NOTE,
    LABEL_OBJECTIONS_DUE_AT,
    LABEL_OBJECTIONS_NOTE,
    LABEL_OBJECTIONS_SUBMITTED_AT,
    LABEL_PLANNED_CONTROL_PLACE,
    LABEL_PLANNED_START_AT,
    LABEL_PLANNED_START_PLACE,
    LABEL_POWER_OF_ATTORNEY,
    LABEL_POWER_OF_ATTORNEY_NOTE,
    LABEL_PREPARATION_NOTE,
    LABEL_PROTOCOL_NUMBER,
    LABEL_PROTOCOL_RECEIVED_AT,
    LABEL_RESULT,
    LABEL_STARTED_AT,
    LABEL_STATUS,
    LABEL_SUBJECT,
    LABEL_TRADE_UNION_NOTIFIED_AT,
    LABEL_WORKPLACE,
    NOTIFICATION_METHOD_EMPTY_LABEL,
    OBJECTIONS_BEFORE_PROTOCOL_MESSAGE,
    PARTICIPANT_ATTENDANCE_LABELS,
    PARTICIPANT_COLUMN_HEADERS,
    PARTICIPANT_ROLE_INSPECTOR,
    PARTICIPANT_ROLE_LABELS,
    PLANNED_NO_LABEL,
    PLANNED_YES_LABEL,
    RESULT_SUGGESTIONS,
    SAVE_ERROR_MESSAGE,
    STATE_SUPERVISION_FINDING_TYPE_LABELS,
    STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS,
    STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER,
    STATE_SUPERVISION_STATUS_LABELS,
    STATE_SUPERVISION_STATUS_ORDER,
    STATUS_CLOSED,
    TAB_ANNOUNCEMENT,
    TAB_ATTACHMENTS,
    TAB_CONCLUSION,
    TAB_COURSE,
    TAB_SUBJECT_PREPARATION,
    TIMELINE_COLUMN_HEADERS,
    TIMELINE_HINT,
    TOOLTIP_INITIAL_INFORMATION,
    TOOLTIP_PREPARATION_NOTE,
    TOOLTIP_SUBJECT,
)
from moduly.statni_dozor.modely.state_supervision import StateSupervision
from moduly.statni_dozor.modely.state_supervision_finding_draft import (
    StateSupervisionFindingDraft,
    new_finding_client_key,
)
from moduly.statni_dozor.modely.state_supervision_participant_draft import (
    StateSupervisionParticipantDraft,
    new_participant_client_key,
)
from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
    StateSupervisionRequiredDocumentDraft,
    new_required_document_client_key,
)
from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
    StateSupervisionTimelineItemDraft,
    new_timeline_item_client_key,
)
from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
    state_supervision_finding_service,
)
from moduly.statni_dozor.sluzby.state_supervision_finding_task_service import (
    state_supervision_finding_task_service,
)
from moduly.statni_dozor.sluzby.state_supervision_closure_readiness import (
    state_supervision_closure_readiness,
)
from moduly.statni_dozor.sluzby.state_supervision_participant_service import (
    state_supervision_participant_service,
)
from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
    state_supervision_required_document_service,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    StateSupervisionError,
    state_supervision_service,
)
from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
    state_supervision_timeline_item_service,
)
from moduly.statni_dozor.ui.state_supervision_attachment_staging_widget import (
    StateSupervisionAttachmentStagingWidget,
)
from moduly.statni_dozor.ui.state_supervision_closure_confirm import (
    confirm_supervision_closure,
)
from moduly.statni_dozor.ui.state_supervision_table import (
    display_or_dash,
    format_supervision_date,
    format_supervision_datetime,
)

_ROLE_DOCUMENT_KEY = Qt.ItemDataRole.UserRole
_ROLE_TIMELINE_KEY = Qt.ItemDataRole.UserRole
_ROLE_FINDING_KEY = Qt.ItemDataRole.UserRole
_ROLE_PARTICIPANT_KEY = Qt.ItemDataRole.UserRole

logger = logging.getLogger(__name__)

_EDITOR_FIELDS = (
    "status",
    "authority_ico",
    "authority_name",
    "authority_address",
    "workplace_id",
    "workplace_name_snapshot",
    "workplace_address_snapshot",
    "notification_method",
    "announced_at",
    "notification_note",
    "trade_union_notified_at",
    "management_notified_at",
    "planned_start_at",
    "planned_start_place",
    "planned_control_place",
    "started_at",
    "ended_at",
    "file_number",
    "subject",
    "initial_information",
    "preparation_note",
    "power_of_attorney_required",
    "power_of_attorney_note",
    "result",
    "final_summary",
    "protocol_number",
    "protocol_received_at",
    "objections_due_at",
    "objections_submitted_at",
    "objections_note",
    "completion_evidence_sent_at",
    "authority_confirmation_at",
    "closed_at",
)


class _SupervisionEditorController(EditorDialogController):
    """Stejná aktivace Uložit i pro tlačítko Uložit a zavřít."""

    def __init__(self, *args, extra_save_buttons=(), **kwargs):
        self._extra_save_buttons = list(extra_save_buttons)
        super().__init__(*args, **kwargs)

    def _refresh_save_enabled(self) -> None:
        super()._refresh_save_enabled()
        enabled = bool(self.save_button is not None and self.save_button.isEnabled())
        for button in self._extra_save_buttons:
            button.setEnabled(enabled)
        refresh_findings = getattr(self._dialog, "_refresh_finding_actions", None)
        if callable(refresh_findings):
            refresh_findings()


def _medium_note_edit(*, stretch: bool = False) -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    edit.setMinimumHeight(110)
    if stretch:
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    else:
        edit.setMaximumHeight(160)
        edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return edit


def _short_note_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setMinimumHeight(52)
    edit.setMaximumHeight(78)
    return edit


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(microsecond=0)


def _participant_role_label(role: str | None) -> str:
    if not role:
        return EMPTY_VALUE
    return PARTICIPANT_ROLE_LABELS.get(role, role)


def _participant_planned_label(planned: bool) -> str:
    return PLANNED_YES_LABEL if planned else PLANNED_NO_LABEL


def _participant_attendance_label(status: str | None) -> str:
    if not status:
        return ATTENDANCE_UNEVALUATED_LABEL
    return PARTICIPANT_ATTENDANCE_LABELS.get(status, status)


def _finding_type_label(finding_type: str | None) -> str:
    if not finding_type:
        return EMPTY_VALUE
    return STATE_SUPERVISION_FINDING_TYPE_LABELS.get(finding_type, finding_type)


def _finding_status_label(status: str | None) -> str:
    if not status:
        return EMPTY_VALUE
    return FINDING_STATUS_LABELS.get(status, status)


def _finding_task_texts(task) -> tuple[str, str]:
    if task is None:
        return FINDING_TASK_MISSING_LABEL, FINDING_TASK_MISSING_LABEL
    title = str(task.title or "").strip() or FINDING_TASK_LINKED
    status = str(getattr(task, "computed_status", None) or task.status or "").strip()
    due = format_supervision_date(task.due_date) if task.due_date else ""
    tooltip_lines = [title]
    if status:
        tooltip_lines.append(status)
    if due:
        tooltip_lines.append(due)
    return title, "\n".join(tooltip_lines)


def _is_finding_error(message: str) -> bool:
    text = str(message or "").casefold()
    if "kontrola státního dozoru" in text and "neexistuje" in text:
        return False
    return "zjištění" in text


class StateSupervisionEditorDialog(QDialog):
    def __init__(self, parent=None, *, supervision_id: int | None = None):
        super().__init__(parent)
        self._record: StateSupervision | None = None
        self._supervision_id = supervision_id
        self._persisted = False
        self._loaded_workplace_id: int | None = None
        self._loaded_name_snapshot = ""
        self._loaded_address_snapshot = ""
        self._document_drafts: list[StateSupervisionRequiredDocumentDraft] = []
        self._timeline_drafts: list[StateSupervisionTimelineItemDraft] = []
        self._findings_drafts: list[StateSupervisionFindingDraft] = []
        self._participant_drafts: list[StateSupervisionParticipantDraft] = []
        self._attachment_staging = AttachmentStagingState()
        self._finding_task_busy = False

        if supervision_id is not None:
            self._record = state_supervision_service.get_supervision(supervision_id)
            if self._record is not None:
                self._supervision_id = int(self._record.id)

        is_existing = self._record is not None
        self.setWindowTitle(DIALOG_TITLE_EDIT if is_existing else DIALOG_TITLE_NEW)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=980, height=720, min_width=640, min_height=480)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_header())
        self.tabs = QTabWidget()
        self.tabs.addTab(wrap_in_scroll_area(self._build_announcement_tab()), TAB_ANNOUNCEMENT)
        self.tabs.addTab(self._build_subject_tab(), TAB_SUBJECT_PREPARATION)
        self._course_tab_index = self.tabs.addTab(self._build_course_tab(), TAB_COURSE)
        self._conclusion_tab_index = self.tabs.addTab(
            wrap_in_scroll_area(self._build_conclusion_tab()), TAB_CONCLUSION
        )
        self._attachments_tab_index = self.tabs.addTab(
            self._build_attachments_tab(), TAB_ATTACHMENTS
        )
        layout.addWidget(self.tabs, 1)
        layout.addLayout(self._build_footer())

        configure_form_tab_navigation(self)

        # is_new=False: Uložit řídí snapshot != baseline i u nové kontroly.
        self._editor = _SupervisionEditorController(
            self,
            self._buttons,
            is_new=False,
            title=self.windowTitle(),
            on_save=self._persist,
            extra_save_buttons=(self._save_close_btn,),
        )
        self._editor.set_snapshot_provider(self.get_snapshot)
        self._editor.install_auto_dirty_tracking()
        for widget in self._datetime_widgets():
            widget.dateTimeChanged.connect(self._editor.refresh_dirty)

        if self._record is not None:
            self._apply_record(self._record)
            self._load_documents(int(self._record.id))
            self._load_timeline(int(self._record.id))
            self._load_findings(int(self._record.id))
            self._load_participants(int(self._record.id))
            self._load_attachments(int(self._record.id))
        else:
            self._set_combo_data(self.status_combo, DEFAULT_STATUS)
            self._refresh_documents_table()
            self._refresh_timeline_table()
            self._refresh_findings_table()
            self._refresh_participants_table()
            self._load_attachments(None)

        self._editor.capture_baseline()

    @property
    def saved(self) -> bool:
        return self._persisted

    @property
    def supervision_id(self) -> int | None:
        if self._supervision_id is not None:
            return int(self._supervision_id)
        if self._record is not None:
            return int(self._record.id)
        return None

    def _build_header(self) -> QWidget:
        host = QWidget()
        form = QFormLayout(host)
        form.setContentsMargins(0, 0, 0, 0)

        self.authority_combo = SearchComboBox(values=list(AUTHORITY_SUGGESTIONS))
        self.authority_combo.setCurrentText("")
        self.ico_edit = QLineEdit()
        self.address_edit = QLineEdit()
        self.workplace_selector = WorkplaceSelector(include_empty=True)
        self.status_combo = QComboBox()
        for status in STATE_SUPERVISION_STATUS_ORDER:
            self.status_combo.addItem(STATE_SUPERVISION_STATUS_LABELS[status], status)
        self._set_combo_data(self.status_combo, DEFAULT_STATUS)

        form.addRow(f"{LABEL_AUTHORITY}:", self.authority_combo)
        form.addRow(f"{LABEL_AUTHORITY_ICO}:", self.ico_edit)
        form.addRow(f"{LABEL_AUTHORITY_ADDRESS}:", self.address_edit)
        form.addRow(f"{LABEL_WORKPLACE}:", self.workplace_selector)
        form.addRow(f"{LABEL_STATUS}:", self.status_combo)
        return host

    def _build_announcement_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        notification = QGroupBox(GROUP_NOTIFICATION)
        notification_form = QFormLayout(notification)
        self.notification_method_combo = QComboBox()
        self.notification_method_combo.addItem(NOTIFICATION_METHOD_EMPTY_LABEL, None)
        for method in STATE_SUPERVISION_NOTIFICATION_METHOD_ORDER:
            self.notification_method_combo.addItem(
                STATE_SUPERVISION_NOTIFICATION_METHOD_EDITOR_LABELS[method],
                method,
            )
        self.announced_at_edit = NullableDateTimeEdit()
        self.file_number_edit = QLineEdit()
        self.notification_note_edit = _short_note_edit()
        notification_form.addRow(f"{LABEL_NOTIFICATION_METHOD}:", self.notification_method_combo)
        notification_form.addRow(f"{LABEL_ANNOUNCED_AT}:", self.announced_at_edit)
        notification_form.addRow(f"{LABEL_FILE_NUMBER}:", self.file_number_edit)
        notification_form.addRow(f"{LABEL_NOTIFICATION_NOTE}:", self.notification_note_edit)

        planned = QGroupBox(GROUP_PLANNED_START)
        planned_form = QFormLayout(planned)
        self.planned_start_at_edit = NullableDateTimeEdit()
        self.planned_start_place_edit = QLineEdit()
        self.planned_control_place_edit = QLineEdit()
        planned_form.addRow(f"{LABEL_PLANNED_START_AT}:", self.planned_start_at_edit)
        planned_form.addRow(f"{LABEL_PLANNED_START_PLACE}:", self.planned_start_place_edit)
        planned_form.addRow(f"{LABEL_PLANNED_CONTROL_PLACE}:", self.planned_control_place_edit)

        actual = QGroupBox(GROUP_ACTUAL_COURSE)
        actual_form = QFormLayout(actual)
        self.started_at_edit = NullableDateTimeEdit()
        self.ended_at_edit = NullableDateTimeEdit()
        actual_form.addRow(f"{LABEL_STARTED_AT}:", self.started_at_edit)
        actual_form.addRow(f"{LABEL_ENDED_AT}:", self.ended_at_edit)

        informing = QGroupBox(GROUP_INFORMING)
        informing_form = QFormLayout(informing)
        self.trade_union_notified_at_edit = NullableDateTimeEdit()
        self.management_notified_at_edit = NullableDateTimeEdit()
        informing_form.addRow(
            f"{LABEL_TRADE_UNION_NOTIFIED_AT}:",
            self.trade_union_notified_at_edit,
        )
        informing_form.addRow(
            f"{LABEL_MANAGEMENT_NOTIFIED_AT}:",
            self.management_notified_at_edit,
        )

        representation = QGroupBox(GROUP_REPRESENTATION)
        representation_form = QFormLayout(representation)
        self.power_of_attorney_checkbox = QCheckBox(LABEL_POWER_OF_ATTORNEY)
        self.power_of_attorney_note_edit = _short_note_edit()
        representation_form.addRow("", self.power_of_attorney_checkbox)
        representation_form.addRow(
            f"{LABEL_POWER_OF_ATTORNEY_NOTE}:",
            self.power_of_attorney_note_edit,
        )

        layout.addWidget(notification)
        layout.addWidget(planned)
        layout.addWidget(actual)
        layout.addWidget(informing)
        layout.addWidget(representation)
        layout.addWidget(self._build_participants_section())
        layout.addStretch(1)
        return page

    def _build_participants_section(self) -> QWidget:
        box = QGroupBox(GROUP_PARTICIPANTS)
        layout = QVBoxLayout(box)

        toolbar = QHBoxLayout()
        self.add_participant_btn = QPushButton(ACTION_ADD)
        self.edit_participant_btn = QPushButton(ACTION_EDIT)
        self.remove_participant_btn = QPushButton(ACTION_REMOVE)
        self.move_participant_up_btn = QPushButton(ACTION_MOVE_UP)
        self.move_participant_down_btn = QPushButton(ACTION_MOVE_DOWN)
        configure_new_action_button(self.add_participant_btn)
        configure_edit_action_button(self.edit_participant_btn)
        for button in (
            self.add_participant_btn,
            self.edit_participant_btn,
            self.remove_participant_btn,
            self.move_participant_up_btn,
            self.move_participant_down_btn,
        ):
            button.setAutoDefault(False)
            button.setDefault(False)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.participants_empty_label = QLabel(EMPTY_PARTICIPANTS)
        self.participants_empty_label.setWordWrap(True)
        self.participants_empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.participants_empty_label)

        self.participants_table = QTableWidget(0, len(PARTICIPANT_COLUMN_HEADERS))
        self.participants_table.setHorizontalHeaderLabels(PARTICIPANT_COLUMN_HEADERS)
        self.participants_table.verticalHeader().setVisible(False)
        self.participants_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.participants_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.participants_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.participants_table.setSortingEnabled(False)
        self.participants_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.participants_table.setMinimumHeight(140)
        self.participants_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        configure_table_columns(self.participants_table, "state_supervision_participants")
        layout.addWidget(self.participants_table, 1)

        self.add_participant_btn.clicked.connect(self._add_participant)
        self.edit_participant_btn.clicked.connect(self._edit_selected_participant)
        self.remove_participant_btn.clicked.connect(self._remove_selected_participant)
        self.move_participant_up_btn.clicked.connect(
            lambda: self._move_selected_participant(-1)
        )
        self.move_participant_down_btn.clicked.connect(
            lambda: self._move_selected_participant(1)
        )
        self.participants_table.doubleClicked.connect(self._edit_selected_participant)
        self.participants_table.itemSelectionChanged.connect(
            self._refresh_participant_actions
        )
        self._refresh_participant_actions()
        return box

    def _build_subject_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        subject_box = QGroupBox(GROUP_SUBJECT)
        subject_layout = QVBoxLayout(subject_box)
        self.subject_edit = _medium_note_edit()
        self.subject_edit.setMaximumHeight(130)
        set_widget_tooltip(self.subject_edit, TOOLTIP_SUBJECT)
        subject_layout.addWidget(QLabel(f"{LABEL_SUBJECT}:"))
        subject_layout.addWidget(self.subject_edit, 1)

        initial_box = QGroupBox(GROUP_INITIAL_INFORMATION)
        initial_layout = QVBoxLayout(initial_box)
        self.initial_information_edit = _medium_note_edit()
        self.initial_information_edit.setMaximumHeight(130)
        set_widget_tooltip(self.initial_information_edit, TOOLTIP_INITIAL_INFORMATION)
        initial_layout.addWidget(QLabel(f"{LABEL_INITIAL_INFORMATION}:"))
        initial_layout.addWidget(self.initial_information_edit, 1)

        preparation_box = QGroupBox(GROUP_PREPARATION)
        preparation_layout = QVBoxLayout(preparation_box)
        self.preparation_note_edit = _medium_note_edit(stretch=True)
        self.preparation_note_edit.setMaximumHeight(140)
        set_widget_tooltip(self.preparation_note_edit, TOOLTIP_PREPARATION_NOTE)
        preparation_layout.addWidget(QLabel(f"{LABEL_PREPARATION_NOTE}:"))
        preparation_layout.addWidget(self.preparation_note_edit, 1)

        layout.addWidget(subject_box, 1)
        layout.addWidget(initial_box, 1)
        layout.addWidget(preparation_box, 1)
        layout.addWidget(self._build_documents_section(), 3)
        return page

    def _build_documents_section(self) -> QWidget:
        box = QGroupBox(GROUP_REQUIRED_DOCUMENTS)
        layout = QVBoxLayout(box)

        toolbar = QHBoxLayout()
        self.add_document_btn = QPushButton(ACTION_ADD)
        self.edit_document_btn = QPushButton(ACTION_EDIT)
        self.remove_document_btn = QPushButton(ACTION_REMOVE)
        self.move_document_up_btn = QPushButton(ACTION_MOVE_UP)
        self.move_document_down_btn = QPushButton(ACTION_MOVE_DOWN)
        configure_new_action_button(self.add_document_btn)
        configure_edit_action_button(self.edit_document_btn)
        for button in (
            self.add_document_btn,
            self.edit_document_btn,
            self.remove_document_btn,
            self.move_document_up_btn,
            self.move_document_down_btn,
        ):
            button.setAutoDefault(False)
            button.setDefault(False)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.documents_empty_label = QLabel(EMPTY_DOCUMENTS)
        self.documents_empty_label.setWordWrap(True)
        self.documents_empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.documents_empty_label)

        self.documents_table = QTableWidget(0, len(DOCUMENT_COLUMN_HEADERS))
        self.documents_table.setHorizontalHeaderLabels(DOCUMENT_COLUMN_HEADERS)
        self.documents_table.verticalHeader().setVisible(False)
        self.documents_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.documents_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.documents_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.documents_table.setSortingEnabled(False)
        self.documents_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.documents_table.setMinimumHeight(140)
        self.documents_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        configure_table_columns(self.documents_table, "state_supervision_required_documents")
        layout.addWidget(self.documents_table, 1)

        self.add_document_btn.clicked.connect(self._add_document)
        self.edit_document_btn.clicked.connect(self._edit_selected_document)
        self.remove_document_btn.clicked.connect(self._remove_selected_document)
        self.move_document_up_btn.clicked.connect(lambda: self._move_selected_document(-1))
        self.move_document_down_btn.clicked.connect(lambda: self._move_selected_document(1))
        self.documents_table.doubleClicked.connect(self._edit_selected_document)
        self.documents_table.itemSelectionChanged.connect(self._refresh_document_actions)
        self._refresh_document_actions()
        return box

    def _build_course_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(self._build_timeline_section(), 1)
        layout.addWidget(self._build_findings_section(), 1)
        return page

    def _build_timeline_section(self) -> QWidget:
        box = QGroupBox(GROUP_COURSE_TIMELINE)
        layout = QVBoxLayout(box)

        self.timeline_hint_label = QLabel(TIMELINE_HINT)
        self.timeline_hint_label.setWordWrap(True)
        self.timeline_hint_label.setStyleSheet("color: #666;")
        layout.addWidget(self.timeline_hint_label)

        toolbar = QHBoxLayout()
        self.add_timeline_btn = QPushButton(ACTION_ADD)
        self.edit_timeline_btn = QPushButton(ACTION_EDIT)
        self.remove_timeline_btn = QPushButton(ACTION_REMOVE)
        self.move_timeline_up_btn = QPushButton(ACTION_MOVE_UP)
        self.move_timeline_down_btn = QPushButton(ACTION_MOVE_DOWN)
        configure_new_action_button(self.add_timeline_btn)
        configure_edit_action_button(self.edit_timeline_btn)
        for button in (
            self.add_timeline_btn,
            self.edit_timeline_btn,
            self.remove_timeline_btn,
            self.move_timeline_up_btn,
            self.move_timeline_down_btn,
        ):
            button.setAutoDefault(False)
            button.setDefault(False)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.timeline_empty_label = QLabel(EMPTY_TIMELINE)
        self.timeline_empty_label.setWordWrap(True)
        self.timeline_empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.timeline_empty_label)

        self.timeline_table = QTableWidget(0, len(TIMELINE_COLUMN_HEADERS))
        self.timeline_table.setHorizontalHeaderLabels(TIMELINE_COLUMN_HEADERS)
        self.timeline_table.verticalHeader().setVisible(False)
        self.timeline_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.timeline_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.timeline_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.timeline_table.setSortingEnabled(False)
        self.timeline_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.timeline_table.setMinimumHeight(120)
        self.timeline_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        configure_table_columns(self.timeline_table, "state_supervision_timeline_items")
        layout.addWidget(self.timeline_table, 1)

        self.add_timeline_btn.clicked.connect(self._add_timeline_item)
        self.edit_timeline_btn.clicked.connect(self._edit_selected_timeline_item)
        self.remove_timeline_btn.clicked.connect(self._remove_selected_timeline_item)
        self.move_timeline_up_btn.clicked.connect(
            lambda: self._move_selected_timeline_item(-1)
        )
        self.move_timeline_down_btn.clicked.connect(
            lambda: self._move_selected_timeline_item(1)
        )
        self.timeline_table.doubleClicked.connect(self._edit_selected_timeline_item)
        self.timeline_table.itemSelectionChanged.connect(self._refresh_timeline_actions)
        self._refresh_timeline_actions()
        return box

    def _build_findings_section(self) -> QWidget:
        box = QGroupBox(GROUP_FINDINGS)
        layout = QVBoxLayout(box)

        toolbar = QHBoxLayout()
        self.add_finding_btn = QPushButton(ACTION_ADD)
        self.edit_finding_btn = QPushButton(ACTION_EDIT)
        self.remove_finding_btn = QPushButton(ACTION_REMOVE)
        self.move_finding_up_btn = QPushButton(ACTION_MOVE_UP)
        self.move_finding_down_btn = QPushButton(ACTION_MOVE_DOWN)
        self.create_finding_task_btn = QPushButton(ACTION_CREATE_TASK)
        self.open_finding_task_btn = QPushButton(ACTION_OPEN_TASK)
        configure_new_action_button(self.add_finding_btn)
        configure_edit_action_button(self.edit_finding_btn)
        configure_create_linked_action_button(self.create_finding_task_btn)
        configure_edit_action_button(self.open_finding_task_btn)
        for button in (
            self.add_finding_btn,
            self.edit_finding_btn,
            self.remove_finding_btn,
            self.move_finding_up_btn,
            self.move_finding_down_btn,
            self.create_finding_task_btn,
            self.open_finding_task_btn,
        ):
            button.setAutoDefault(False)
            button.setDefault(False)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.finding_task_hint_label = QLabel()
        self.finding_task_hint_label.setWordWrap(True)
        self.finding_task_hint_label.setStyleSheet("color: #666;")
        self.finding_task_hint_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.finding_task_hint_label.setVisible(False)
        layout.addWidget(self.finding_task_hint_label)

        self.findings_empty_label = QLabel(EMPTY_FINDINGS)
        self.findings_empty_label.setWordWrap(True)
        self.findings_empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.findings_empty_label)

        self.findings_table = QTableWidget(0, len(FINDING_COLUMN_HEADERS))
        self.findings_table.setHorizontalHeaderLabels(FINDING_COLUMN_HEADERS)
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.findings_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.findings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.findings_table.setSortingEnabled(False)
        self.findings_table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.findings_table.setMinimumHeight(120)
        self.findings_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        configure_table_columns(self.findings_table, "state_supervision_findings")
        layout.addWidget(self.findings_table, 1)

        self.add_finding_btn.clicked.connect(self._add_finding)
        self.edit_finding_btn.clicked.connect(self._edit_selected_finding)
        self.remove_finding_btn.clicked.connect(self._remove_selected_finding)
        self.move_finding_up_btn.clicked.connect(lambda: self._move_selected_finding(-1))
        self.move_finding_down_btn.clicked.connect(lambda: self._move_selected_finding(1))
        self.create_finding_task_btn.clicked.connect(self._create_finding_task)
        self.open_finding_task_btn.clicked.connect(self._open_finding_task)
        self.findings_table.doubleClicked.connect(self._edit_selected_finding)
        self.findings_table.itemSelectionChanged.connect(self._refresh_finding_actions)
        self._refresh_finding_actions()
        return box

    def _build_conclusion_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        result_box = QGroupBox(GROUP_RESULT)
        result_form = QFormLayout(result_box)
        self.result_combo = SearchComboBox()
        self.result_combo.set_items(list(RESULT_SUGGESTIONS), include_empty=True)
        self.final_summary_edit = _medium_note_edit()
        result_form.addRow(f"{LABEL_RESULT}:", self.result_combo)
        result_form.addRow(f"{LABEL_FINAL_SUMMARY}:", self.final_summary_edit)

        protocol_box = QGroupBox(GROUP_PROTOCOL)
        protocol_form = QFormLayout(protocol_box)
        self.protocol_number_edit = QLineEdit()
        self.protocol_received_at_edit = NullableDateTimeEdit()
        protocol_form.addRow(f"{LABEL_PROTOCOL_NUMBER}:", self.protocol_number_edit)
        protocol_form.addRow(
            f"{LABEL_PROTOCOL_RECEIVED_AT}:",
            self.protocol_received_at_edit,
        )

        objections_box = QGroupBox(GROUP_OBJECTIONS)
        objections_form = QFormLayout(objections_box)
        self.objections_due_at_edit = NullableDateTimeEdit()
        self.objections_submitted_at_edit = NullableDateTimeEdit()
        self.objections_note_edit = _medium_note_edit()
        objections_form.addRow(f"{LABEL_OBJECTIONS_DUE_AT}:", self.objections_due_at_edit)
        objections_form.addRow(
            f"{LABEL_OBJECTIONS_SUBMITTED_AT}:",
            self.objections_submitted_at_edit,
        )
        objections_form.addRow(f"{LABEL_OBJECTIONS_NOTE}:", self.objections_note_edit)

        close_box = QGroupBox(GROUP_COMPLETION_CLOSE)
        close_form = QFormLayout(close_box)
        self.completion_evidence_sent_at_edit = NullableDateTimeEdit()
        self.authority_confirmation_at_edit = NullableDateTimeEdit()
        self.closed_at_edit = NullableDateTimeEdit()
        close_form.addRow(
            f"{LABEL_COMPLETION_EVIDENCE_SENT_AT}:",
            self.completion_evidence_sent_at_edit,
        )
        close_form.addRow(
            f"{LABEL_AUTHORITY_CONFIRMATION_AT}:",
            self.authority_confirmation_at_edit,
        )
        close_form.addRow(f"{LABEL_CLOSED_AT}:", self.closed_at_edit)

        layout.addWidget(result_box)
        layout.addWidget(protocol_box)
        layout.addWidget(objections_box)
        layout.addWidget(close_box)
        layout.addStretch(1)
        return page

    def _build_attachments_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.attachments_widget = StateSupervisionAttachmentStagingWidget(
            page,
            staging=self._attachment_staging,
            on_changed=self._on_attachments_changed,
        )
        layout.addWidget(self.attachments_widget, 1)
        return page

    def _on_attachments_changed(self) -> None:
        editor = getattr(self, "_editor", None)
        if editor is not None:
            editor.refresh_dirty()

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addStretch(1)

        self._buttons = create_save_cancel_box(self, is_new=False)
        self._save_close_btn = QPushButton()
        configure_editor_save_button(self._save_close_btn)
        self._save_close_btn.setText(ACTION_SAVE_AND_CLOSE)
        self._save_close_btn.setAutoDefault(False)
        self._save_close_btn.setDefault(False)
        self._save_close_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._buttons.addButton(self._save_close_btn, QDialogButtonBox.ButtonRole.ApplyRole)
        self._save_close_btn.clicked.connect(self._save_and_close)
        footer.addWidget(self._buttons)
        return footer

    def _datetime_widgets(self) -> tuple[NullableDateTimeEdit, ...]:
        return (
            self.announced_at_edit,
            self.planned_start_at_edit,
            self.started_at_edit,
            self.ended_at_edit,
            self.trade_union_notified_at_edit,
            self.management_notified_at_edit,
            self.protocol_received_at_edit,
            self.objections_due_at_edit,
            self.objections_submitted_at_edit,
            self.completion_evidence_sent_at_edit,
            self.authority_confirmation_at_edit,
            self.closed_at_edit,
        )

    def _set_combo_data(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _apply_record(self, record: StateSupervision) -> None:
        self._record = record
        self._supervision_id = int(record.id)
        self._loaded_workplace_id = (
            int(record.workplace_id) if record.workplace_id else None
        )
        self._loaded_name_snapshot = str(record.workplace_name_snapshot or "")
        self._loaded_address_snapshot = str(record.workplace_address_snapshot or "")

        blockers = [
            self.authority_combo,
            self.ico_edit,
            self.address_edit,
            self.workplace_selector,
            self.status_combo,
            self.notification_method_combo,
            self.file_number_edit,
            self.notification_note_edit,
            self.planned_start_place_edit,
            self.planned_control_place_edit,
            self.power_of_attorney_checkbox,
            self.power_of_attorney_note_edit,
            self.subject_edit,
            self.initial_information_edit,
            self.preparation_note_edit,
            self.result_combo,
            self.final_summary_edit,
            self.protocol_number_edit,
            self.objections_note_edit,
            *self._datetime_widgets(),
        ]
        for widget in blockers:
            widget.blockSignals(True)
        try:
            self.authority_combo.setCurrentText(str(record.authority_name or ""))
            self.ico_edit.setText(str(record.authority_ico or ""))
            self.address_edit.setText(str(record.authority_address or ""))
            self.workplace_selector.set_workplace_id(
                record.workplace_id,
                workplace_name=str(record.workplace_name_snapshot or ""),
            )
            self._set_combo_data(self.status_combo, record.status or DEFAULT_STATUS)
            self._set_combo_data(self.notification_method_combo, record.notification_method)
            self.announced_at_edit.set_datetime(_normalize_datetime(record.announced_at))
            self.file_number_edit.setText(str(record.file_number or ""))
            self.notification_note_edit.setPlainText(str(record.notification_note or ""))
            self.planned_start_at_edit.set_datetime(
                _normalize_datetime(record.planned_start_at)
            )
            self.planned_start_place_edit.setText(str(record.planned_start_place or ""))
            self.planned_control_place_edit.setText(str(record.planned_control_place or ""))
            self.started_at_edit.set_datetime(_normalize_datetime(record.started_at))
            self.ended_at_edit.set_datetime(_normalize_datetime(record.ended_at))
            self.trade_union_notified_at_edit.set_datetime(
                _normalize_datetime(record.trade_union_notified_at)
            )
            self.management_notified_at_edit.set_datetime(
                _normalize_datetime(record.management_notified_at)
            )
            self.power_of_attorney_checkbox.setChecked(bool(record.power_of_attorney_required))
            self.power_of_attorney_note_edit.setPlainText(
                str(record.power_of_attorney_note or "")
            )
            self.subject_edit.setPlainText(str(record.subject or ""))
            self.initial_information_edit.setPlainText(
                str(record.initial_information or "")
            )
            self.preparation_note_edit.setPlainText(str(record.preparation_note or ""))
            self.result_combo.setCurrentText(str(record.result or ""))
            self.final_summary_edit.setPlainText(str(record.final_summary or ""))
            self.protocol_number_edit.setText(str(record.protocol_number or ""))
            self.protocol_received_at_edit.set_datetime(
                _normalize_datetime(record.protocol_received_at)
            )
            self.objections_due_at_edit.set_datetime(
                _normalize_datetime(record.objections_due_at)
            )
            self.objections_submitted_at_edit.set_datetime(
                _normalize_datetime(record.objections_submitted_at)
            )
            self.objections_note_edit.setPlainText(str(record.objections_note or ""))
            self.completion_evidence_sent_at_edit.set_datetime(
                _normalize_datetime(record.completion_evidence_sent_at)
            )
            self.authority_confirmation_at_edit.set_datetime(
                _normalize_datetime(record.authority_confirmation_at)
            )
            self.closed_at_edit.set_datetime(_normalize_datetime(record.closed_at))
        finally:
            for widget in blockers:
                widget.blockSignals(False)

    def _workplace_payload(self) -> tuple[int | None, str, str]:
        workplace_id = self.workplace_selector.current_workplace_id()
        if workplace_id is not None:
            workplace_id = int(workplace_id)
            if workplace_id == self._loaded_workplace_id:
                return (
                    workplace_id,
                    self._loaded_name_snapshot,
                    self._loaded_address_snapshot,
                )
            workplace = settings_service.get_workplace_by_id(workplace_id)
            if workplace is None:
                return workplace_id, self.workplace_selector.display_text(), ""
            return (
                workplace_id,
                str(workplace.name or "").strip(),
                str(workplace.address or "").strip(),
            )
        text = self.workplace_selector.display_text()
        if not text:
            return None, "", ""
        return None, text, ""

    def get_data(self) -> dict:
        workplace_id, name_snapshot, address_snapshot = self._workplace_payload()
        status = self.status_combo.currentData() or DEFAULT_STATUS
        method = self.notification_method_combo.currentData()
        return {
            "authority_name": self.authority_combo.currentText().strip(),
            "authority_ico": self.ico_edit.text().strip(),
            "authority_address": self.address_edit.text().strip(),
            "workplace_id": workplace_id,
            "workplace_name_snapshot": name_snapshot,
            "workplace_address_snapshot": address_snapshot,
            "status": str(status),
            "notification_method": str(method) if method else None,
            "announced_at": _normalize_datetime(self.announced_at_edit.get_datetime()),
            "file_number": self.file_number_edit.text().strip(),
            "notification_note": self.notification_note_edit.toPlainText().strip(),
            "planned_start_at": _normalize_datetime(
                self.planned_start_at_edit.get_datetime()
            ),
            "planned_start_place": self.planned_start_place_edit.text().strip(),
            "planned_control_place": self.planned_control_place_edit.text().strip(),
            "started_at": _normalize_datetime(self.started_at_edit.get_datetime()),
            "ended_at": _normalize_datetime(self.ended_at_edit.get_datetime()),
            "trade_union_notified_at": _normalize_datetime(
                self.trade_union_notified_at_edit.get_datetime()
            ),
            "management_notified_at": _normalize_datetime(
                self.management_notified_at_edit.get_datetime()
            ),
            "power_of_attorney_required": self.power_of_attorney_checkbox.isChecked(),
            "power_of_attorney_note": self.power_of_attorney_note_edit.toPlainText().strip(),
            "subject": self.subject_edit.toPlainText().strip(),
            "initial_information": self.initial_information_edit.toPlainText().strip(),
            "preparation_note": self.preparation_note_edit.toPlainText().strip(),
            "result": self.result_combo.currentText().strip(),
            "final_summary": self.final_summary_edit.toPlainText().strip(),
            "protocol_number": self.protocol_number_edit.text().strip(),
            "protocol_received_at": _normalize_datetime(
                self.protocol_received_at_edit.get_datetime()
            ),
            "objections_due_at": _normalize_datetime(
                self.objections_due_at_edit.get_datetime()
            ),
            "objections_submitted_at": _normalize_datetime(
                self.objections_submitted_at_edit.get_datetime()
            ),
            "objections_note": self.objections_note_edit.toPlainText().strip(),
            "completion_evidence_sent_at": _normalize_datetime(
                self.completion_evidence_sent_at_edit.get_datetime()
            ),
            "authority_confirmation_at": _normalize_datetime(
                self.authority_confirmation_at_edit.get_datetime()
            ),
            "closed_at": _normalize_datetime(self.closed_at_edit.get_datetime()),
        }

    def get_snapshot(self) -> tuple:
        data = self.get_data()
        return tuple(data[key] for key in _EDITOR_FIELDS) + (
            self._documents_snapshot(),
            self._timeline_snapshot(),
            self._findings_snapshot(),
            self._participants_snapshot(),
            self._attachment_staging.snapshot(),
        )

    def _focus_conclusion_datetime(self, widget: NullableDateTimeEdit) -> None:
        self.tabs.setCurrentIndex(self._conclusion_tab_index)
        widget.setFocus(Qt.FocusReason.OtherFocusReason)
        if widget.has_value():
            widget.edit.setFocus(Qt.FocusReason.OtherFocusReason)
        else:
            widget.set_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _focus_attachments_tab(self) -> None:
        self.tabs.setCurrentIndex(self._attachments_tab_index)

    def _focus_course_tab(self) -> None:
        self.tabs.setCurrentIndex(self._course_tab_index)

    def _validation_message(self, data: dict) -> str | None:
        if not data["authority_name"]:
            return AUTHORITY_REQUIRED_MESSAGE
        started = data["started_at"]
        ended = data["ended_at"]
        if started is not None and ended is not None and ended < started:
            return ENDED_BEFORE_STARTED_MESSAGE
        protocol_received = data["protocol_received_at"]
        objections_submitted = data["objections_submitted_at"]
        if (
            protocol_received is not None
            and objections_submitted is not None
            and objections_submitted < protocol_received
        ):
            self._focus_conclusion_datetime(self.objections_submitted_at_edit)
            return OBJECTIONS_BEFORE_PROTOCOL_MESSAGE
        closed_at = data["closed_at"]
        if data["status"] == STATUS_CLOSED and closed_at is None:
            self._focus_conclusion_datetime(self.closed_at_edit)
            return CLOSED_AT_REQUIRED_MESSAGE
        if ended is not None and closed_at is not None and closed_at < ended:
            self._focus_conclusion_datetime(self.closed_at_edit)
            return CLOSED_BEFORE_ENDED_MESSAGE
        return None

    def _baseline_status(self) -> str:
        baseline = getattr(self._editor, "_baseline", None)
        index = _EDITOR_FIELDS.index("status")
        if isinstance(baseline, tuple) and len(baseline) > index:
            return str(baseline[index] or DEFAULT_STATUS)
        if self._record is not None:
            return str(self._record.status or DEFAULT_STATUS)
        return DEFAULT_STATUS

    def _is_transition_to_closed(self, working_status: str) -> bool:
        return working_status == STATUS_CLOSED and self._baseline_status() != STATUS_CLOSED

    def _confirm_closure_if_needed(self, working_status: str) -> bool:
        if not self._is_transition_to_closed(working_status):
            return True
        readiness = state_supervision_closure_readiness(self._findings_drafts)
        if not readiness.needs_confirmation:
            return True
        if confirm_supervision_closure(self, readiness):
            return True
        self._focus_course_tab()
        return False

    def _persist(self) -> bool:
        data = self.get_data()
        message = self._validation_message(data)
        if message:
            QMessageBox.warning(self, self.windowTitle(), message)
            return False
        if not self._confirm_closure_if_needed(str(data["status"])):
            return False
        payload = {key: data[key] for key in _EDITOR_FIELDS}
        previous_id = self._supervision_id
        try:
            record, _docs, _items = state_supervision_service.save_supervision_bundle(
                supervision_id=self._supervision_id,
                fields=payload,
                documents=self._drafts_for_save(),
                timeline_items=self._timeline_drafts_for_save(),
                participants=self._participant_drafts_for_save(),
                attachments=self._attachment_staging,
                findings=self._findings_drafts_for_save(),
            )
            loaded = state_supervision_service.get_supervision(int(record.id))
            if loaded is None:
                raise StateSupervisionError(SAVE_ERROR_MESSAGE)
            self._apply_record(loaded)
            self._load_documents(int(loaded.id))
            self._load_timeline(int(loaded.id))
            self._load_findings(int(loaded.id))
            self._load_participants(int(loaded.id))
            self._attachment_staging = AttachmentStagingState()
            self.attachments_widget.bind_staging(self._attachment_staging)
            self._load_attachments(int(loaded.id))
            self._persisted = True
            self.setWindowTitle(DIALOG_TITLE_EDIT)
            return True
        except StateSupervisionError as error:
            self._supervision_id = previous_id
            if _is_finding_error(str(error)):
                self._focus_course_tab()
            logger.exception("Uložení kontroly státního dozoru selhalo.")
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        except AttachmentStagingError as error:
            self._supervision_id = previous_id
            self._focus_attachments_tab()
            logger.exception("Uložení příloh spisu státního dozoru selhalo.")
            QMessageBox.warning(self, self.windowTitle(), str(error))
            return False
        except OSError:
            self._supervision_id = previous_id
            if self._attachment_staging.has_changes():
                self._focus_attachments_tab()
            logger.exception("Uložení kontroly státního dozoru selhalo.")
            QMessageBox.warning(self, self.windowTitle(), SAVE_ERROR_MESSAGE)
            return False
        except Exception:
            self._supervision_id = previous_id
            logger.exception("Uložení kontroly státního dozoru selhalo.")
            QMessageBox.warning(self, self.windowTitle(), SAVE_ERROR_MESSAGE)
            return False

    def _active_documents(self) -> list[StateSupervisionRequiredDocumentDraft]:
        return [item for item in self._document_drafts if item.active]

    def _documents_snapshot(self) -> tuple:
        rows = []
        for item in self._document_drafts:
            rows.append(
                (
                    item.client_key,
                    item.id,
                    str(item.title or ""),
                    item.responsible_source_type,
                    item.responsible_source_id,
                    item.responsible_name_snapshot,
                    _normalize_datetime(item.due_at),
                    _normalize_datetime(item.prepared_at),
                    _normalize_datetime(item.submitted_at),
                    item.note,
                    int(item.display_order or 0),
                    bool(item.active),
                )
            )
        return tuple(rows)

    def _drafts_for_save(self) -> list[StateSupervisionRequiredDocumentDraft]:
        active = [
            replace(item, display_order=index * 10)
            for index, item in enumerate(self._active_documents())
        ]
        inactive = [item for item in self._document_drafts if not item.active]
        return active + inactive

    def _load_documents(self, supervision_id: int) -> None:
        records = state_supervision_required_document_service.list_documents(
            int(supervision_id),
            include_inactive=False,
        )
        loaded: list[StateSupervisionRequiredDocumentDraft] = []
        for record in records:
            loaded.append(
                StateSupervisionRequiredDocumentDraft(
                    title=str(record.title or ""),
                    id=int(record.id),
                    responsible_source_type=record.responsible_source_type,
                    responsible_source_id=record.responsible_source_id,
                    responsible_name_snapshot=record.responsible_name_snapshot,
                    due_at=_normalize_datetime(record.due_at),
                    prepared_at=_normalize_datetime(record.prepared_at),
                    submitted_at=_normalize_datetime(record.submitted_at),
                    note=record.note,
                    display_order=int(record.display_order or 0),
                    active=bool(record.active),
                    client_key=f"db-{record.id}",
                )
            )
        self._document_drafts = loaded
        self._refresh_documents_table()

    def _refresh_documents_table(self, *, select_key: str | None = None) -> None:
        active = self._active_documents()
        self.documents_empty_label.setVisible(not active)
        self.documents_table.setVisible(True)
        self.documents_table.setRowCount(len(active))
        for row, item in enumerate(active):
            values = [
                display_or_dash(item.title),
                display_or_dash(item.responsible_name_snapshot),
                format_supervision_datetime(_normalize_datetime(item.due_at)),
                format_supervision_datetime(_normalize_datetime(item.prepared_at)),
                format_supervision_datetime(_normalize_datetime(item.submitted_at)),
                display_or_dash(item.note),
            ]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == COL_DOCUMENT_TITLE:
                    cell.setData(_ROLE_DOCUMENT_KEY, item.client_key)
                apply_cell_tooltip(cell, text if text != EMPTY_VALUE else "")
                self.documents_table.setItem(row, column, cell)
        configure_table_columns(
            self.documents_table, "state_supervision_required_documents"
        )
        if select_key:
            self._select_document_key(select_key)
        self._refresh_document_actions()

    def _selected_document_key(self) -> str | None:
        rows = self.documents_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.documents_table.item(rows[0].row(), COL_DOCUMENT_TITLE)
        if item is None:
            return None
        key = item.data(_ROLE_DOCUMENT_KEY)
        return str(key) if key else None

    def _select_document_key(self, client_key: str) -> None:
        for row in range(self.documents_table.rowCount()):
            item = self.documents_table.item(row, COL_DOCUMENT_TITLE)
            if item is not None and item.data(_ROLE_DOCUMENT_KEY) == client_key:
                self.documents_table.selectRow(row)
                return
        self.documents_table.clearSelection()

    def _draft_by_key(self, client_key: str | None) -> StateSupervisionRequiredDocumentDraft | None:
        if not client_key:
            return None
        for item in self._document_drafts:
            if item.client_key == client_key:
                return item
        return None

    def _refresh_document_actions(self, *_args) -> None:
        active = self._active_documents()
        key = self._selected_document_key()
        has_one = key is not None
        self.edit_document_btn.setEnabled(has_one)
        self.remove_document_btn.setEnabled(has_one)
        index = next((i for i, item in enumerate(active) if item.client_key == key), -1)
        self.move_document_up_btn.setEnabled(has_one and index > 0)
        self.move_document_down_btn.setEnabled(has_one and 0 <= index < len(active) - 1)

    def _add_document(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_required_document_dialog import (
            exec_required_document_dialog,
        )

        active = self._active_documents()
        next_order = (max((item.display_order for item in active), default=-10) + 10)
        draft = StateSupervisionRequiredDocumentDraft(
            title="",
            display_order=next_order,
            client_key=new_required_document_client_key(),
        )
        saved = exec_required_document_dialog(self, draft=draft, is_new=True)
        if saved is None:
            return
        self._document_drafts.append(saved)
        self._refresh_documents_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _edit_selected_document(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_required_document_dialog import (
            exec_required_document_dialog,
        )

        current = self._draft_by_key(self._selected_document_key())
        if current is None:
            return
        saved = exec_required_document_dialog(self, draft=replace(current), is_new=False)
        if saved is None:
            return
        for index, item in enumerate(self._document_drafts):
            if item.client_key == current.client_key:
                self._document_drafts[index] = saved
                break
        self._refresh_documents_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _remove_selected_document(self) -> None:
        current = self._draft_by_key(self._selected_document_key())
        if current is None:
            return
        if current.id is None:
            self._document_drafts = [
                item for item in self._document_drafts if item.client_key != current.client_key
            ]
        else:
            current.active = False
        self._refresh_documents_table()
        self._editor.refresh_dirty()

    def _move_selected_document(self, delta: int) -> None:
        key = self._selected_document_key()
        active = self._active_documents()
        index = next((i for i, item in enumerate(active) if item.client_key == key), -1)
        target = index + delta
        if index < 0 or target < 0 or target >= len(active):
            return
        active[index], active[target] = active[target], active[index]
        for order, item in enumerate(active):
            item.display_order = order * 10
        inactive = [item for item in self._document_drafts if not item.active]
        self._document_drafts = active + inactive
        self._refresh_documents_table(select_key=key)
        self._editor.refresh_dirty()

    def _active_timeline_items(self) -> list[StateSupervisionTimelineItemDraft]:
        return [item for item in self._timeline_drafts if item.active]

    def _timeline_snapshot(self) -> tuple:
        rows = []
        for item in self._timeline_drafts:
            rows.append(
                (
                    item.client_key,
                    item.id,
                    _normalize_datetime(item.occurred_at),
                    str(item.title or ""),
                    item.place,
                    item.notes,
                    int(item.display_order or 0),
                    bool(item.active),
                )
            )
        return tuple(rows)

    def _timeline_drafts_for_save(self) -> list[StateSupervisionTimelineItemDraft]:
        active = [
            replace(item, display_order=index * 10)
            for index, item in enumerate(self._active_timeline_items())
        ]
        inactive = [item for item in self._timeline_drafts if not item.active]
        return active + inactive

    def _load_timeline(self, supervision_id: int) -> None:
        records = state_supervision_timeline_item_service.list_timeline_items(
            int(supervision_id),
            include_inactive=False,
        )
        loaded: list[StateSupervisionTimelineItemDraft] = []
        for record in records:
            loaded.append(
                StateSupervisionTimelineItemDraft(
                    title=str(record.title or ""),
                    id=int(record.id),
                    occurred_at=_normalize_datetime(record.occurred_at),
                    place=record.place,
                    notes=record.notes,
                    display_order=int(record.display_order or 0),
                    active=bool(record.active),
                    client_key=f"db-{record.id}",
                )
            )
        self._timeline_drafts = loaded
        self._refresh_timeline_table()

    def _refresh_timeline_table(self, *, select_key: str | None = None) -> None:
        active = self._active_timeline_items()
        self.timeline_empty_label.setVisible(not active)
        self.timeline_table.setVisible(True)
        self.timeline_table.setRowCount(len(active))
        for row, item in enumerate(active):
            values = [
                format_supervision_datetime(_normalize_datetime(item.occurred_at)),
                display_or_dash(item.title),
                display_or_dash(item.place),
                display_or_dash(item.notes),
            ]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == COL_TIMELINE_TITLE:
                    cell.setData(_ROLE_TIMELINE_KEY, item.client_key)
                apply_cell_tooltip(cell, text if text != EMPTY_VALUE else "")
                self.timeline_table.setItem(row, column, cell)
        configure_table_columns(
            self.timeline_table, "state_supervision_timeline_items"
        )
        if select_key:
            self._select_timeline_key(select_key)
        self._refresh_timeline_actions()

    def _selected_timeline_key(self) -> str | None:
        rows = self.timeline_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.timeline_table.item(rows[0].row(), COL_TIMELINE_TITLE)
        if item is None:
            return None
        key = item.data(_ROLE_TIMELINE_KEY)
        return str(key) if key else None

    def _select_timeline_key(self, client_key: str) -> None:
        for row in range(self.timeline_table.rowCount()):
            item = self.timeline_table.item(row, COL_TIMELINE_TITLE)
            if item is not None and item.data(_ROLE_TIMELINE_KEY) == client_key:
                self.timeline_table.selectRow(row)
                return
        self.timeline_table.clearSelection()

    def _timeline_draft_by_key(
        self, client_key: str | None
    ) -> StateSupervisionTimelineItemDraft | None:
        if not client_key:
            return None
        for item in self._timeline_drafts:
            if item.client_key == client_key:
                return item
        return None

    def _refresh_timeline_actions(self, *_args) -> None:
        active = self._active_timeline_items()
        key = self._selected_timeline_key()
        has_one = key is not None
        self.edit_timeline_btn.setEnabled(has_one)
        self.remove_timeline_btn.setEnabled(has_one)
        index = next((i for i, item in enumerate(active) if item.client_key == key), -1)
        self.move_timeline_up_btn.setEnabled(has_one and index > 0)
        self.move_timeline_down_btn.setEnabled(has_one and 0 <= index < len(active) - 1)

    def _add_timeline_item(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_timeline_item_dialog import (
            exec_timeline_item_dialog,
        )

        active = self._active_timeline_items()
        next_order = max((item.display_order for item in active), default=-10) + 10
        draft = StateSupervisionTimelineItemDraft(
            title="",
            display_order=next_order,
            client_key=new_timeline_item_client_key(),
        )
        saved = exec_timeline_item_dialog(self, draft=draft, is_new=True)
        if saved is None:
            return
        self._timeline_drafts.append(saved)
        self._refresh_timeline_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _edit_selected_timeline_item(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_timeline_item_dialog import (
            exec_timeline_item_dialog,
        )

        current = self._timeline_draft_by_key(self._selected_timeline_key())
        if current is None:
            return
        saved = exec_timeline_item_dialog(self, draft=replace(current), is_new=False)
        if saved is None:
            return
        for index, item in enumerate(self._timeline_drafts):
            if item.client_key == current.client_key:
                self._timeline_drafts[index] = saved
                break
        self._refresh_timeline_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _remove_selected_timeline_item(self) -> None:
        current = self._timeline_draft_by_key(self._selected_timeline_key())
        if current is None:
            return
        if current.id is None:
            self._timeline_drafts = [
                item
                for item in self._timeline_drafts
                if item.client_key != current.client_key
            ]
        else:
            current.active = False
        self._refresh_timeline_table()
        self._editor.refresh_dirty()

    def _move_selected_timeline_item(self, delta: int) -> None:
        key = self._selected_timeline_key()
        active = self._active_timeline_items()
        index = next((i for i, item in enumerate(active) if item.client_key == key), -1)
        target = index + delta
        if index < 0 or target < 0 or target >= len(active):
            return
        active[index], active[target] = active[target], active[index]
        for order, item in enumerate(active):
            item.display_order = order * 10
        inactive = [item for item in self._timeline_drafts if not item.active]
        self._timeline_drafts = active + inactive
        self._refresh_timeline_table(select_key=key)
        self._editor.refresh_dirty()

    def _findings_snapshot(self) -> tuple:
        rows = []
        for item in self._findings_drafts:
            rows.append(
                (
                    item.id,
                    item.client_key,
                    str(item.finding_type or ""),
                    str(item.description or ""),
                    str(item.source_area_label or ""),
                    str(item.status or ""),
                    item.responsible_person_id,
                    str(item.responsible_person_name or ""),
                    item.due_date,
                    str(item.recommended_action or ""),
                    str(item.resolution_note or ""),
                    item.resolved_at,
                    item.task_id,
                    int(item.display_order or 0),
                )
            )
        return tuple(rows)

    def _findings_drafts_for_save(self) -> list[StateSupervisionFindingDraft]:
        return [
            replace(item, display_order=index * 10)
            for index, item in enumerate(self._findings_drafts)
        ]

    def _load_findings(self, supervision_id: int, *, select_key: str | None = None) -> None:
        records = state_supervision_finding_service.list_findings(int(supervision_id))
        loaded: list[StateSupervisionFindingDraft] = []
        for record in records:
            loaded.append(
                StateSupervisionFindingDraft(
                    finding_type=str(record.finding_type or ""),
                    description=str(record.description or ""),
                    id=int(record.id),
                    source_area_label=str(record.source_area_label or ""),
                    status=str(record.status or ""),
                    responsible_person_id=record.responsible_person_id,
                    responsible_person_name=str(record.responsible_person_name or ""),
                    due_date=record.due_date,
                    recommended_action=str(record.recommended_action or ""),
                    resolution_note=str(record.resolution_note or ""),
                    resolved_at=record.resolved_at,
                    task_id=record.task_id,
                    display_order=int(record.display_order or 0),
                    client_key=f"db-{record.id}",
                )
            )
        self._findings_drafts = loaded
        self._refresh_findings_table(select_key=select_key)

    def _finding_tasks_by_id(self) -> dict[int, object]:
        ids = sorted(
            {
                int(item.task_id)
                for item in self._findings_drafts
                if item.task_id is not None
            }
        )
        if not ids:
            return {}
        from moduly.ukoly.sluzby.task_service import task_service

        return {
            int(task.id): task
            for task in task_service.get_tasks_by_ids(ids)
            if getattr(task, "id", None) is not None
        }

    def _refresh_findings_table(self, *, select_key: str | None = None) -> None:
        rows = self._findings_drafts
        tasks_by_id = self._finding_tasks_by_id()
        self.findings_empty_label.setVisible(not rows)
        self.findings_table.setVisible(True)
        self.findings_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            if item.task_id is None:
                task_text = EMPTY_VALUE
                task_tooltip = ""
            else:
                task_text, task_tooltip = _finding_task_texts(
                    tasks_by_id.get(int(item.task_id))
                )
            values = [
                _finding_type_label(item.finding_type),
                display_or_dash(item.description),
                display_or_dash(item.source_area_label),
                _finding_status_label(item.status),
                display_or_dash(item.responsible_person_name),
                format_supervision_date(item.due_date),
                task_text,
            ]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == COL_FINDING_TYPE:
                    cell.setData(_ROLE_FINDING_KEY, item.client_key)
                if column == COL_FINDING_TASK:
                    apply_cell_tooltip(cell, task_tooltip)
                else:
                    apply_cell_tooltip(cell, text if text != EMPTY_VALUE else "")
                self.findings_table.setItem(row, column, cell)
        configure_table_columns(self.findings_table, "state_supervision_findings")
        if select_key:
            self._select_finding_key(select_key)
        self._refresh_finding_actions()

    def _selected_finding_key(self) -> str | None:
        rows = self.findings_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.findings_table.item(rows[0].row(), COL_FINDING_TYPE)
        if item is None:
            return None
        key = item.data(_ROLE_FINDING_KEY)
        return str(key) if key else None

    def _select_finding_key(self, client_key: str) -> None:
        for row in range(self.findings_table.rowCount()):
            item = self.findings_table.item(row, COL_FINDING_TYPE)
            if item is not None and item.data(_ROLE_FINDING_KEY) == client_key:
                self.findings_table.selectRow(row)
                return
        self.findings_table.clearSelection()

    def _finding_draft_by_key(
        self, client_key: str | None
    ) -> StateSupervisionFindingDraft | None:
        if not client_key:
            return None
        for item in self._findings_drafts:
            if item.client_key == client_key:
                return item
        return None

    def _refresh_finding_actions(self, *_args) -> None:
        if not hasattr(self, "create_finding_task_btn"):
            return
        key = self._selected_finding_key()
        current = self._finding_draft_by_key(key)
        has_one = current is not None
        stored = has_one and current.id is not None
        dirty = self._editor_is_dirty()
        self.edit_finding_btn.setEnabled(has_one)
        self.remove_finding_btn.setEnabled(has_one and not stored)
        if stored:
            set_widget_tooltip(self.remove_finding_btn, FINDING_STORED_REMOVE_HINT)
        else:
            set_widget_tooltip(self.remove_finding_btn, "")
        index = next(
            (i for i, item in enumerate(self._findings_drafts) if item.client_key == key),
            -1,
        )
        self.move_finding_up_btn.setEnabled(has_one and index > 0)
        self.move_finding_down_btn.setEnabled(
            has_one and 0 <= index < len(self._findings_drafts) - 1
        )

        create_enabled = False
        open_enabled = False
        create_tooltip = ""
        hint = ""
        if current is None:
            pass
        elif current.id is None:
            create_tooltip = FINDING_TASK_SAVE_FIRST_TOOLTIP
            hint = FINDING_TASK_HINT_UNSAVED
        elif current.task_id is not None:
            open_enabled = True
            hint = FINDING_TASK_HINT_LINKED
            if dirty:
                create_tooltip = FINDING_TASK_DIRTY_TOOLTIP
        elif dirty:
            create_tooltip = FINDING_TASK_DIRTY_TOOLTIP
            hint = FINDING_TASK_HINT_DIRTY
        elif not self._finding_task_busy:
            create_enabled = True

        self.create_finding_task_btn.setEnabled(create_enabled)
        self.open_finding_task_btn.setEnabled(open_enabled)
        set_widget_tooltip(self.create_finding_task_btn, create_tooltip)
        self.finding_task_hint_label.setText(hint)
        self.finding_task_hint_label.setVisible(bool(hint))

    def _editor_is_dirty(self) -> bool:
        editor = getattr(self, "_editor", None)
        if editor is None:
            return False
        return bool(editor.is_dirty())

    def _add_finding(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_finding_dialog import (
            exec_finding_dialog,
        )

        next_order = (
            max((item.display_order for item in self._findings_drafts), default=-10) + 10
        )
        draft = StateSupervisionFindingDraft(
            display_order=next_order,
            client_key=new_finding_client_key(),
        )
        saved = exec_finding_dialog(self, draft=draft, is_new=True)
        if saved is None:
            return
        self._findings_drafts.append(saved)
        self._refresh_findings_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _edit_selected_finding(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_finding_dialog import (
            exec_finding_dialog,
        )

        current = self._finding_draft_by_key(self._selected_finding_key())
        if current is None:
            return
        saved = exec_finding_dialog(self, draft=replace(current), is_new=False)
        if saved is None:
            return
        for index, item in enumerate(self._findings_drafts):
            if item.client_key == current.client_key:
                self._findings_drafts[index] = saved
                break
        self._refresh_findings_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _remove_selected_finding(self) -> None:
        current = self._finding_draft_by_key(self._selected_finding_key())
        if current is None or current.id is not None:
            return
        self._findings_drafts = [
            item
            for item in self._findings_drafts
            if item.client_key != current.client_key
        ]
        self._refresh_findings_table()
        self._editor.refresh_dirty()

    def _move_selected_finding(self, delta: int) -> None:
        key = self._selected_finding_key()
        index = next(
            (i for i, item in enumerate(self._findings_drafts) if item.client_key == key),
            -1,
        )
        target = index + delta
        if index < 0 or target < 0 or target >= len(self._findings_drafts):
            return
        self._findings_drafts[index], self._findings_drafts[target] = (
            self._findings_drafts[target],
            self._findings_drafts[index],
        )
        for order, item in enumerate(self._findings_drafts):
            item.display_order = order * 10
        self._refresh_findings_table(select_key=key)
        self._editor.refresh_dirty()

    def _create_finding_task(self) -> None:
        if self._finding_task_busy:
            return
        current = self._finding_draft_by_key(self._selected_finding_key())
        if current is None or current.id is None:
            return
        if current.task_id is not None:
            return
        if self._editor_is_dirty():
            return

        from core.shared.sluzby.finding_service import finding_service
        from moduly.agenda.constants import PRIORITY_CRITICAL
        from moduly.ukoly.ui.task_dialog import TaskDialog

        finding = finding_service.get_by_id(int(current.id))
        if finding is None:
            QMessageBox.warning(self, GROUP_FINDINGS, FINDING_TASK_NOT_FOUND_MESSAGE)
            return

        finding_id = int(finding.id)
        defaults = state_supervision_finding_task_service.task_defaults_for_finding(
            finding
        )
        select_key = current.client_key

        def _create(data: dict):
            try:
                return state_supervision_finding_task_service.create_task_for_finding(
                    finding_id,
                    data,
                )
            except StateSupervisionError as exc:
                logger.warning(
                    "Vytvoření úkolu ze zjištění %s selhalo: %s",
                    finding_id,
                    exc,
                )
                QMessageBox.warning(self, GROUP_FINDINGS, str(exc))
                return None
            except Exception:
                logger.exception(
                    "Vytvoření úkolu ze zjištění %s selhalo.",
                    finding_id,
                )
                QMessageBox.warning(
                    self,
                    GROUP_FINDINGS,
                    "Úkol se nepodařilo vytvořit.",
                )
                return None

        dialog = None
        self._finding_task_busy = True
        self.create_finding_task_btn.setEnabled(False)
        try:
            dialog = TaskDialog(
                self,
                create_factory=_create,
                fixed_priority=PRIORITY_CRITICAL,
                source_finding=finding,
            )
            self._apply_finding_task_defaults(dialog, defaults)
            dialog.exec()
        finally:
            self._finding_task_busy = False

        task = getattr(dialog, "task", None) if dialog is not None else None
        task_id = getattr(task, "id", None)
        if task is None or task_id is None:
            self._refresh_finding_actions()
            return

        try:
            supervision_id = self.supervision_id
            if supervision_id is None:
                raise RuntimeError("missing supervision id")
            self._load_findings(int(supervision_id), select_key=select_key)
        except Exception:
            logger.exception("Obnovení zjištění po vytvoření úkolu selhalo.")
            self._apply_created_task_id(select_key, int(task_id))
            self._refresh_findings_table(select_key=select_key)
            QMessageBox.warning(
                self,
                GROUP_FINDINGS,
                FINDING_TASK_RELOAD_FAILED_MESSAGE,
            )
        self._editor.capture_baseline()
        self._notify_agenda_task_created()
        self._refresh_finding_actions()

    def _apply_finding_task_defaults(self, dialog, defaults: dict) -> None:
        dialog.title_edit.setPlainText(str(defaults.get("title") or ""))
        person_id = defaults.get("responsible_person_id")
        dialog.person_selector.set_person_id(person_id)
        due_date = defaults.get("due_date")
        if due_date is not None:
            dialog.due_date_edit.set_date_iso(due_date.isoformat())
        dialog.requires_verification_checkbox.setChecked(
            bool(defaults.get("requires_verification", True))
        )
        dialog._verification_changed()
        dialog._apply_fixed_priority()
        dialog._capture_baseline()

    def _apply_created_task_id(self, client_key: str, task_id: int) -> None:
        for index, item in enumerate(self._findings_drafts):
            if item.client_key == client_key:
                self._findings_drafts[index] = replace(item, task_id=int(task_id))
                return

    def _open_finding_task(self) -> None:
        current = self._finding_draft_by_key(self._selected_finding_key())
        if current is None or current.task_id is None:
            return
        from moduly.ukoly.sluzby.task_service import task_service
        from moduly.ukoly.ui.task_dialog import TaskDialog

        select_key = current.client_key
        task = task_service.get_task_by_id(int(current.task_id))
        if task is None:
            QMessageBox.warning(
                self,
                GROUP_FINDINGS,
                FINDING_TASK_MISSING_OPEN_MESSAGE,
            )
            self._refresh_findings_table(select_key=select_key)
            return
        dialog = TaskDialog(self, task=task)
        dialog.exec()
        self._refresh_findings_table(select_key=select_key)

    def _notify_agenda_task_created(self) -> None:
        from moduly.agenda.ui.agenda_page import AgendaPage

        widget = self.parentWidget()
        while widget is not None:
            if isinstance(widget, AgendaPage):
                current_index = widget.tabs.currentIndex()
                widget.refresh()
                widget._refresh_dashboard()
                widget.tabs.setCurrentIndex(current_index)
                return
            widget = widget.parentWidget()

    def _active_participants(self) -> list[StateSupervisionParticipantDraft]:
        return [item for item in self._participant_drafts if item.active]

    def _participants_snapshot(self) -> tuple:
        rows = []
        for item in self._participant_drafts:
            rows.append(
                (
                    item.id,
                    item.client_key,
                    str(item.role or ""),
                    item.source_type,
                    item.source_id,
                    str(item.name_snapshot or ""),
                    item.organization_snapshot,
                    item.contact_note,
                    bool(item.planned),
                    item.attendance_status,
                    item.note,
                    int(item.display_order or 0),
                    bool(item.active),
                )
            )
        return tuple(rows)

    def _participant_drafts_for_save(self) -> list[StateSupervisionParticipantDraft]:
        active = [
            replace(item, display_order=index * 10)
            for index, item in enumerate(self._active_participants())
        ]
        inactive = [item for item in self._participant_drafts if not item.active]
        return active + inactive

    def _load_participants(self, supervision_id: int) -> None:
        records = state_supervision_participant_service.list_participants(
            int(supervision_id),
            include_inactive=False,
        )
        loaded: list[StateSupervisionParticipantDraft] = []
        for record in records:
            loaded.append(
                StateSupervisionParticipantDraft(
                    role=str(record.role or ""),
                    name_snapshot=str(record.name_snapshot or ""),
                    id=int(record.id),
                    source_type=record.source_type,
                    source_id=record.source_id,
                    organization_snapshot=record.organization_snapshot,
                    contact_note=record.contact_note,
                    planned=bool(record.planned),
                    attendance_status=record.attendance_status,
                    note=record.note,
                    display_order=int(record.display_order or 0),
                    active=bool(record.active),
                    client_key=f"db-{record.id}",
                )
            )
        self._participant_drafts = loaded
        self._refresh_participants_table()

    def _load_attachments(self, supervision_id: int | None) -> None:
        if not supervision_id:
            self.attachments_widget.set_existing([])
            return
        rows = attachment_service.get_for_entity(
            ENTITY_STATE_SUPERVISION, int(supervision_id)
        )
        self.attachments_widget.set_existing(rows)

    def _refresh_participants_table(self, *, select_key: str | None = None) -> None:
        active = self._active_participants()
        self.participants_empty_label.setVisible(not active)
        self.participants_table.setVisible(True)
        self.participants_table.setRowCount(len(active))
        for row, item in enumerate(active):
            values = [
                _participant_role_label(item.role),
                display_or_dash(item.name_snapshot),
                display_or_dash(item.organization_snapshot),
                _participant_planned_label(bool(item.planned)),
                _participant_attendance_label(item.attendance_status),
                display_or_dash(item.contact_note),
                display_or_dash(item.note),
            ]
            for column, text in enumerate(values):
                cell = QTableWidgetItem(text)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if column == COL_PARTICIPANT_ROLE:
                    cell.setData(_ROLE_PARTICIPANT_KEY, item.client_key)
                apply_cell_tooltip(cell, text if text != EMPTY_VALUE else "")
                self.participants_table.setItem(row, column, cell)
        configure_table_columns(
            self.participants_table, "state_supervision_participants"
        )
        if select_key:
            self._select_participant_key(select_key)
        self._refresh_participant_actions()

    def _selected_participant_key(self) -> str | None:
        rows = self.participants_table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.participants_table.item(rows[0].row(), COL_PARTICIPANT_ROLE)
        if item is None:
            return None
        key = item.data(_ROLE_PARTICIPANT_KEY)
        return str(key) if key else None

    def _select_participant_key(self, client_key: str) -> None:
        for row in range(self.participants_table.rowCount()):
            item = self.participants_table.item(row, COL_PARTICIPANT_ROLE)
            if item is not None and item.data(_ROLE_PARTICIPANT_KEY) == client_key:
                self.participants_table.selectRow(row)
                return
        self.participants_table.clearSelection()

    def _participant_draft_by_key(
        self, client_key: str | None
    ) -> StateSupervisionParticipantDraft | None:
        if not client_key:
            return None
        for item in self._participant_drafts:
            if item.client_key == client_key:
                return item
        return None

    def _refresh_participant_actions(self, *_args) -> None:
        active = self._active_participants()
        key = self._selected_participant_key()
        has_one = key is not None
        self.edit_participant_btn.setEnabled(has_one)
        self.remove_participant_btn.setEnabled(has_one)
        index = next((i for i, item in enumerate(active) if item.client_key == key), -1)
        self.move_participant_up_btn.setEnabled(has_one and index > 0)
        self.move_participant_down_btn.setEnabled(
            has_one and 0 <= index < len(active) - 1
        )

    def _add_participant(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_participant_dialog import (
            exec_participant_dialog,
        )

        active = self._active_participants()
        next_order = max((item.display_order for item in active), default=-10) + 10
        draft = StateSupervisionParticipantDraft(
            role=PARTICIPANT_ROLE_INSPECTOR,
            display_order=next_order,
            client_key=new_participant_client_key(),
        )
        saved = exec_participant_dialog(self, draft=draft, is_new=True)
        if saved is None:
            return
        self._participant_drafts.append(saved)
        self._refresh_participants_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _edit_selected_participant(self) -> None:
        from moduly.statni_dozor.ui.state_supervision_participant_dialog import (
            exec_participant_dialog,
        )

        current = self._participant_draft_by_key(self._selected_participant_key())
        if current is None:
            return
        saved = exec_participant_dialog(self, draft=replace(current), is_new=False)
        if saved is None:
            return
        for index, item in enumerate(self._participant_drafts):
            if item.client_key == current.client_key:
                self._participant_drafts[index] = saved
                break
        self._refresh_participants_table(select_key=saved.client_key)
        self._editor.refresh_dirty()

    def _remove_selected_participant(self) -> None:
        current = self._participant_draft_by_key(self._selected_participant_key())
        if current is None:
            return
        if current.id is None:
            self._participant_drafts = [
                item
                for item in self._participant_drafts
                if item.client_key != current.client_key
            ]
        else:
            current.active = False
        self._refresh_participants_table()
        self._editor.refresh_dirty()

    def _move_selected_participant(self, delta: int) -> None:
        key = self._selected_participant_key()
        active = self._active_participants()
        index = next((i for i, item in enumerate(active) if item.client_key == key), -1)
        target = index + delta
        if index < 0 or target < 0 or target >= len(active):
            return
        active[index], active[target] = active[target], active[index]
        for order, item in enumerate(active):
            item.display_order = order * 10
        inactive = [item for item in self._participant_drafts if not item.active]
        self._participant_drafts = active + inactive
        self._refresh_participants_table(select_key=key)
        self._editor.refresh_dirty()

    def _save_and_close(self) -> None:
        if not self._editor._run_save():
            return
        self.accept()
