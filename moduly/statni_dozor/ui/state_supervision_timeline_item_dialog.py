"""Poddialog jednoho záznamu průběhu kontroly — pouze pracovní kopie."""

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
from moduly.statni_dozor.constants import (
    DIALOG_TIMELINE_EDIT,
    DIALOG_TIMELINE_NEW,
    LABEL_TIMELINE_NOTES,
    LABEL_TIMELINE_OCCURRED_AT,
    LABEL_TIMELINE_PLACE,
    LABEL_TIMELINE_TITLE,
    TIMELINE_TITLE_REQUIRED_MESSAGE,
)
from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
    StateSupervisionTimelineItemDraft,
    new_timeline_item_client_key,
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


def _notes_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    edit.setMinimumHeight(90)
    edit.setMaximumHeight(140)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return edit


class StateSupervisionTimelineItemDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        draft: StateSupervisionTimelineItemDraft | None = None,
        is_new: bool = False,
    ):
        super().__init__(parent)
        self._original = draft or StateSupervisionTimelineItemDraft(
            title="",
            client_key=new_timeline_item_client_key(),
        )
        self._result: StateSupervisionTimelineItemDraft | None = None
        self.setWindowTitle(DIALOG_TIMELINE_NEW if is_new else DIALOG_TIMELINE_EDIT)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(
            self, width=560, height=420, min_width=420, min_height=320
        )

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.occurred_at_edit = NullableDateTimeEdit()
        self.title_edit = QLineEdit()
        self.place_edit = QLineEdit()
        self.notes_edit = _notes_edit()

        form.addRow(f"{LABEL_TIMELINE_OCCURRED_AT}:", self.occurred_at_edit)
        form.addRow(f"{LABEL_TIMELINE_TITLE}:", self.title_edit)
        form.addRow(f"{LABEL_TIMELINE_PLACE}:", self.place_edit)
        form.addRow(f"{LABEL_TIMELINE_NOTES}:", self.notes_edit)
        layout.addLayout(form, 1)

        buttons = create_save_cancel_box(self, is_new=True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        configure_form_tab_navigation(self)
        self._apply_draft(self._original)

    @property
    def result_draft(self) -> StateSupervisionTimelineItemDraft | None:
        return self._result

    def _apply_draft(self, draft: StateSupervisionTimelineItemDraft) -> None:
        self.occurred_at_edit.set_datetime(_normalize_datetime(draft.occurred_at))
        self.title_edit.setText(str(draft.title or ""))
        self.place_edit.setText(str(draft.place or ""))
        self.notes_edit.setPlainText(str(draft.notes or ""))

    def get_draft(self) -> StateSupervisionTimelineItemDraft:
        place = self.place_edit.text().strip() or None
        notes = self.notes_edit.toPlainText().strip() or None
        return replace(
            self._original,
            title=self.title_edit.text().strip(),
            occurred_at=_normalize_datetime(self.occurred_at_edit.get_datetime()),
            place=place,
            notes=notes,
        )

    def _on_save(self) -> None:
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, self.windowTitle(), TIMELINE_TITLE_REQUIRED_MESSAGE)
            return
        self._result = self.get_draft()
        self.accept()


def exec_timeline_item_dialog(
    parent: QWidget | None,
    *,
    draft: StateSupervisionTimelineItemDraft | None = None,
    is_new: bool = False,
) -> StateSupervisionTimelineItemDraft | None:
    overlay = _ParentDimOverlay(parent) if parent is not None else None
    dialog = StateSupervisionTimelineItemDialog(
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
