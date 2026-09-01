"""Poddialog jednoho účastníka kontroly — pouze pracovní kopie."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    configure_resizable_form_dialog,
    create_save_cancel_box,
)
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.schuzky.ui.meeting_people_widgets import MeetingPersonTypeahead
from moduly.statni_dozor.constants import (
    ATTENDANCE_ABSENT,
    ATTENDANCE_ATTENDED,
    ATTENDANCE_UNEVALUATED_LABEL,
    DIALOG_PARTICIPANT_EDIT,
    DIALOG_PARTICIPANT_NEW,
    LABEL_PARTICIPANT_ATTENDANCE,
    LABEL_PARTICIPANT_CATALOG,
    LABEL_PARTICIPANT_CONTACT,
    LABEL_PARTICIPANT_EXTERNAL_NAME,
    LABEL_PARTICIPANT_NOTE,
    LABEL_PARTICIPANT_ORGANIZATION,
    LABEL_PARTICIPANT_PLANNED,
    LABEL_PARTICIPANT_ROLE,
    PARTICIPANT_ATTENDANCE_LABELS,
    PARTICIPANT_IDENTITY_CONFLICT_MESSAGE,
    PARTICIPANT_NAME_REQUIRED_MESSAGE,
    PARTICIPANT_ROLE_INSPECTOR,
    PARTICIPANT_ROLE_LABELS,
    PARTICIPANT_ROLE_ORDER,
    PARTICIPANT_SOURCE_PERSON,
    PARTICIPANT_SOURCE_THP_WORKER,
)
from moduly.statni_dozor.modely.state_supervision_participant_draft import (
    StateSupervisionParticipantDraft,
    new_participant_client_key,
)

_OVERLAY_ALPHA = 110


class _ParentDimOverlay(QWidget):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._sync_geometry()
        host.installEventFilter(self)
        self.raise_()
        self.show()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        ):
            self._sync_geometry()
        return False

    def _sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, _OVERLAY_ALPHA))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        event.accept()

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.accept()


def _note_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    edit.setMinimumHeight(52)
    edit.setMaximumHeight(78)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return edit


def _catalog_person_exists(source_type: str | None, source_id: int | None) -> bool:
    if not source_type or not source_id:
        return False
    if source_type == PARTICIPANT_SOURCE_PERSON:
        return person_service.get_by_id(int(source_id)) is not None
    if source_type == PARTICIPANT_SOURCE_THP_WORKER:
        return settings_service.get_worker_by_id(int(source_id)) is not None
    return False


class StateSupervisionParticipantDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        draft: StateSupervisionParticipantDraft | None = None,
        is_new: bool = False,
    ):
        super().__init__(parent)
        self._original = draft or StateSupervisionParticipantDraft(
            role=PARTICIPANT_ROLE_INSPECTOR,
            client_key=new_participant_client_key(),
        )
        self._result: StateSupervisionParticipantDraft | None = None
        self.setWindowTitle(DIALOG_PARTICIPANT_NEW if is_new else DIALOG_PARTICIPANT_EDIT)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(
            self, width=560, height=520, min_width=420, min_height=380
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.role_combo = QComboBox()
        for role in PARTICIPANT_ROLE_ORDER:
            self.role_combo.addItem(PARTICIPANT_ROLE_LABELS[role], role)

        self.person_selector = MeetingPersonTypeahead(include_empty=True)
        self.external_name_edit = QLineEdit()
        self.organization_edit = QLineEdit()
        self.contact_edit = QLineEdit()
        self.planned_checkbox = QCheckBox(LABEL_PARTICIPANT_PLANNED)
        self.attendance_combo = QComboBox()
        self.attendance_combo.addItem(ATTENDANCE_UNEVALUATED_LABEL, None)
        for status in (ATTENDANCE_ATTENDED, ATTENDANCE_ABSENT):
            self.attendance_combo.addItem(PARTICIPANT_ATTENDANCE_LABELS[status], status)
        self.note_edit = _note_edit()

        form.addRow(f"{LABEL_PARTICIPANT_ROLE}:", self.role_combo)
        form.addRow(f"{LABEL_PARTICIPANT_CATALOG}:", self.person_selector)
        form.addRow(f"{LABEL_PARTICIPANT_EXTERNAL_NAME}:", self.external_name_edit)
        form.addRow(f"{LABEL_PARTICIPANT_ORGANIZATION}:", self.organization_edit)
        form.addRow(f"{LABEL_PARTICIPANT_CONTACT}:", self.contact_edit)
        form.addRow("", self.planned_checkbox)
        form.addRow(f"{LABEL_PARTICIPANT_ATTENDANCE}:", self.attendance_combo)
        form.addRow(f"{LABEL_PARTICIPANT_NOTE}:", self.note_edit)
        layout.addLayout(form, 1)

        buttons = create_save_cancel_box(self, is_new=True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        configure_form_tab_navigation(self)
        self.person_selector.currentIndexChanged.connect(self._on_catalog_changed)
        self._apply_draft(self._original)

    @property
    def result_draft(self) -> StateSupervisionParticipantDraft | None:
        return self._result

    def _apply_draft(self, draft: StateSupervisionParticipantDraft) -> None:
        role_index = self.role_combo.findData(draft.role or PARTICIPANT_ROLE_INSPECTOR)
        self.role_combo.setCurrentIndex(role_index if role_index >= 0 else 0)
        self.organization_edit.setText(str(draft.organization_snapshot or ""))
        self.contact_edit.setText(str(draft.contact_note or ""))
        self.planned_checkbox.setChecked(bool(draft.planned))
        attendance_index = self.attendance_combo.findData(draft.attendance_status)
        self.attendance_combo.setCurrentIndex(
            attendance_index if attendance_index >= 0 else 0
        )
        self.note_edit.setPlainText(str(draft.note or ""))

        self.person_selector.blockSignals(True)
        self.external_name_edit.blockSignals(True)
        source_type = draft.source_type
        source_id = draft.source_id
        if source_type and source_id:
            self.person_selector.set_ref(
                {"source_type": source_type, "source_id": int(source_id)}
            )
            snapshot = str(draft.name_snapshot or "").strip()
            if snapshot and not _catalog_person_exists(source_type, int(source_id)):
                index = self.person_selector.currentIndex()
                if index >= 0:
                    self.person_selector.setItemText(index, snapshot)
            self.external_name_edit.clear()
            self.external_name_edit.setEnabled(False)
        else:
            self.person_selector.set_ref(None)
            self.external_name_edit.setText(str(draft.name_snapshot or ""))
            self.external_name_edit.setEnabled(True)
        self.person_selector.blockSignals(False)
        self.external_name_edit.blockSignals(False)

    def _on_catalog_changed(self, *_args) -> None:
        if self.person_selector.current_ref() is not None:
            self.external_name_edit.blockSignals(True)
            self.external_name_edit.clear()
            self.external_name_edit.blockSignals(False)
            self.external_name_edit.setEnabled(False)
        else:
            self.external_name_edit.setEnabled(True)

    def get_draft(self) -> StateSupervisionParticipantDraft:
        original = self._original
        ref = self.person_selector.current_ref()
        external = self.external_name_edit.text().strip()
        if ref is None:
            source_type = None
            source_id = None
            snapshot = external
        else:
            source_type = str(ref["source_type"])
            source_id = int(ref["source_id"])
            same = (
                original.source_type == source_type
                and original.source_id == source_id
            )
            if same and original.name_snapshot:
                snapshot = original.name_snapshot
            else:
                snapshot = self.person_selector.currentText().strip()
        organization = self.organization_edit.text().strip() or None
        contact = self.contact_edit.text().strip() or None
        note = self.note_edit.toPlainText().strip() or None
        role = self.role_combo.currentData() or PARTICIPANT_ROLE_INSPECTOR
        return replace(
            original,
            role=str(role),
            source_type=source_type,
            source_id=source_id,
            name_snapshot=snapshot,
            organization_snapshot=organization,
            contact_note=contact,
            planned=self.planned_checkbox.isChecked(),
            attendance_status=self.attendance_combo.currentData(),
            note=note,
        )

    def _on_save(self) -> None:
        ref = self.person_selector.current_ref()
        external = self.external_name_edit.text().strip()
        catalog_name = self.person_selector.currentText().strip()
        if ref is not None and external and external != catalog_name:
            QMessageBox.warning(
                self, self.windowTitle(), PARTICIPANT_IDENTITY_CONFLICT_MESSAGE
            )
            return
        if ref is None and not external:
            QMessageBox.warning(
                self, self.windowTitle(), PARTICIPANT_NAME_REQUIRED_MESSAGE
            )
            return
        self._result = self.get_draft()
        self.accept()


def exec_participant_dialog(
    parent: QWidget | None,
    *,
    draft: StateSupervisionParticipantDraft | None = None,
    is_new: bool = False,
) -> StateSupervisionParticipantDraft | None:
    overlay = _ParentDimOverlay(parent) if parent is not None else None
    dialog = StateSupervisionParticipantDialog(
        parent, draft=draft, is_new=is_new
    )
    try:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result_draft
        return None
    finally:
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
