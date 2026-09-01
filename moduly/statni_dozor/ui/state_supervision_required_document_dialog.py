"""Poddialog jednoho požadovaného dokladu — pouze pracovní kopie."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
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
from core.widgets.nullable_datetime_edit import NullableDateTimeEdit
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.schuzky.ui.meeting_people_widgets import MeetingPersonTypeahead
from moduly.statni_dozor.constants import (
    DIALOG_DOCUMENT_EDIT,
    DIALOG_DOCUMENT_NEW,
    DOCUMENT_TITLE_REQUIRED_MESSAGE,
    LABEL_DOCUMENT_DUE,
    LABEL_DOCUMENT_NOTE,
    LABEL_DOCUMENT_PREPARED,
    LABEL_DOCUMENT_RESPONSIBLE,
    LABEL_DOCUMENT_SUBMITTED,
    LABEL_DOCUMENT_TITLE,
    RESPONSIBLE_SOURCE_PERSON,
    RESPONSIBLE_SOURCE_THP_WORKER,
)
from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
    StateSupervisionRequiredDocumentDraft,
    new_required_document_client_key,
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


def _normalize_datetime(value):
    if value is None:
        return None
    return value.replace(microsecond=0)


def _note_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    edit.setMinimumHeight(90)
    edit.setMaximumHeight(140)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return edit


def _responsible_exists(source_type: str | None, source_id: int | None) -> bool:
    if not source_type or not source_id:
        return False
    if source_type == RESPONSIBLE_SOURCE_PERSON:
        return person_service.get_by_id(int(source_id)) is not None
    if source_type == RESPONSIBLE_SOURCE_THP_WORKER:
        return settings_service.get_worker_by_id(int(source_id)) is not None
    return False


class StateSupervisionRequiredDocumentDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        draft: StateSupervisionRequiredDocumentDraft | None = None,
        is_new: bool = False,
    ):
        super().__init__(parent)
        self._original = draft or StateSupervisionRequiredDocumentDraft(
            title="",
            client_key=new_required_document_client_key(),
        )
        self._result: StateSupervisionRequiredDocumentDraft | None = None
        self.setWindowTitle(DIALOG_DOCUMENT_NEW if is_new else DIALOG_DOCUMENT_EDIT)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(
            self, width=560, height=480, min_width=420, min_height=360
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit()
        self.person_selector = MeetingPersonTypeahead(include_empty=True)
        self.due_at_edit = NullableDateTimeEdit()
        self.prepared_at_edit = NullableDateTimeEdit()
        self.submitted_at_edit = NullableDateTimeEdit()
        self.note_edit = _note_edit()

        form.addRow(f"{LABEL_DOCUMENT_TITLE}:", self.title_edit)
        form.addRow(f"{LABEL_DOCUMENT_RESPONSIBLE}:", self.person_selector)
        form.addRow(f"{LABEL_DOCUMENT_DUE}:", self.due_at_edit)
        form.addRow(f"{LABEL_DOCUMENT_PREPARED}:", self.prepared_at_edit)
        form.addRow(f"{LABEL_DOCUMENT_SUBMITTED}:", self.submitted_at_edit)
        form.addRow(f"{LABEL_DOCUMENT_NOTE}:", self.note_edit)
        layout.addLayout(form, 1)

        buttons = create_save_cancel_box(self, is_new=True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        configure_form_tab_navigation(self)
        self._apply_draft(self._original)

    @property
    def result_draft(self) -> StateSupervisionRequiredDocumentDraft | None:
        return self._result

    def _apply_draft(self, draft: StateSupervisionRequiredDocumentDraft) -> None:
        self.title_edit.setText(str(draft.title or ""))
        self.note_edit.setPlainText(str(draft.note or ""))
        self.due_at_edit.set_datetime(_normalize_datetime(draft.due_at))
        self.prepared_at_edit.set_datetime(_normalize_datetime(draft.prepared_at))
        self.submitted_at_edit.set_datetime(_normalize_datetime(draft.submitted_at))
        source_type = draft.responsible_source_type
        source_id = draft.responsible_source_id
        if source_type and source_id:
            self.person_selector.set_ref(
                {"source_type": source_type, "source_id": int(source_id)}
            )
            snapshot = str(draft.responsible_name_snapshot or "").strip()
            if snapshot and not _responsible_exists(source_type, int(source_id)):
                index = self.person_selector.currentIndex()
                if index >= 0:
                    self.person_selector.setItemText(index, snapshot)
        else:
            self.person_selector.set_ref(None)

    def get_draft(self) -> StateSupervisionRequiredDocumentDraft:
        original = self._original
        ref = self.person_selector.current_ref()
        if ref is None:
            source_type = None
            source_id = None
            snapshot = None
        else:
            source_type = str(ref["source_type"])
            source_id = int(ref["source_id"])
            same = (
                original.responsible_source_type == source_type
                and original.responsible_source_id == source_id
            )
            if same and original.responsible_name_snapshot:
                snapshot = original.responsible_name_snapshot
            else:
                snapshot = self.person_selector.currentText().strip() or None
        note = self.note_edit.toPlainText().strip() or None
        return replace(
            original,
            title=self.title_edit.text().strip(),
            responsible_source_type=source_type,
            responsible_source_id=source_id,
            responsible_name_snapshot=snapshot,
            due_at=_normalize_datetime(self.due_at_edit.get_datetime()),
            prepared_at=_normalize_datetime(self.prepared_at_edit.get_datetime()),
            submitted_at=_normalize_datetime(self.submitted_at_edit.get_datetime()),
            note=note,
        )

    def _on_save(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, self.windowTitle(), DOCUMENT_TITLE_REQUIRED_MESSAGE)
            return
        self._result = self.get_draft()
        self.accept()


def exec_required_document_dialog(
    parent: QWidget | None,
    *,
    draft: StateSupervisionRequiredDocumentDraft | None = None,
    is_new: bool = False,
) -> StateSupervisionRequiredDocumentDraft | None:
    overlay = _ParentDimOverlay(parent) if parent is not None else None
    dialog = StateSupervisionRequiredDocumentDialog(
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
