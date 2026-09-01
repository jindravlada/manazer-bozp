"""Poddialog jednoho zjištění kontroly — pouze pracovní kopie draftu."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
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

from core.shared.constants import (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    FINDING_TYPE_ZJISTENI,
)
from core.shared.finding_display import FINDING_STATUS_LABELS
from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.statni_dozor.constants import (
    DIALOG_FINDING_EDIT,
    DIALOG_FINDING_NEW,
    FINDING_DESCRIPTION_REQUIRED_MESSAGE,
    LABEL_FINDING_DESCRIPTION,
    LABEL_FINDING_DUE,
    LABEL_FINDING_PERSON,
    LABEL_FINDING_PLACE,
    LABEL_FINDING_RECOMMENDED,
    LABEL_FINDING_RESOLUTION,
    LABEL_FINDING_RESOLVED_AT,
    LABEL_FINDING_STATUS,
    LABEL_FINDING_TYPE,
    STATE_SUPERVISION_FINDING_TYPE_LABELS,
    STATE_SUPERVISION_FINDING_TYPE_ORDER,
)
from moduly.statni_dozor.modely.state_supervision_finding_draft import (
    StateSupervisionFindingDraft,
    new_finding_client_key,
)

_OVERLAY_ALPHA = 110

_STATUS_ORDER = (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
)


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


def _description_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    edit.setMinimumHeight(90)
    edit.setMaximumHeight(140)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return edit


def _note_edit() -> QTextEdit:
    edit = QTextEdit()
    edit.setAcceptRichText(False)
    edit.setTabChangesFocus(True)
    edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
    edit.setMinimumHeight(70)
    edit.setMaximumHeight(110)
    edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return edit


class StateSupervisionFindingDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        draft: StateSupervisionFindingDraft | None = None,
        is_new: bool = False,
    ):
        super().__init__(parent)
        self._original = draft or StateSupervisionFindingDraft(
            finding_type=FINDING_TYPE_ZJISTENI,
            client_key=new_finding_client_key(),
        )
        self._result: StateSupervisionFindingDraft | None = None
        self.setWindowTitle(DIALOG_FINDING_NEW if is_new else DIALOG_FINDING_EDIT)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(
            self, width=640, height=560, min_width=480, min_height=400
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.type_combo = QComboBox()
        for finding_type in STATE_SUPERVISION_FINDING_TYPE_ORDER:
            self.type_combo.addItem(
                STATE_SUPERVISION_FINDING_TYPE_LABELS[finding_type],
                finding_type,
            )

        self.description_edit = _description_edit()
        self.place_edit = QLineEdit()
        self.status_combo = QComboBox()
        for status in _STATUS_ORDER:
            self.status_combo.addItem(FINDING_STATUS_LABELS[status], status)

        self.person_selector = ThpWorkerSelector(include_empty=True)
        self.due_date_edit = NullableDateEdit()
        self.recommended_action_edit = _note_edit()
        self.resolution_note_edit = _note_edit()
        self.resolved_at_edit = NullableDateEdit()

        form.addRow(f"{LABEL_FINDING_TYPE}:", self.type_combo)
        form.addRow(f"{LABEL_FINDING_DESCRIPTION}:", self.description_edit)
        form.addRow(f"{LABEL_FINDING_PLACE}:", self.place_edit)
        form.addRow(f"{LABEL_FINDING_STATUS}:", self.status_combo)
        form.addRow(f"{LABEL_FINDING_PERSON}:", self.person_selector)
        form.addRow(f"{LABEL_FINDING_DUE}:", self.due_date_edit)
        form.addRow(f"{LABEL_FINDING_RECOMMENDED}:", self.recommended_action_edit)
        form.addRow(f"{LABEL_FINDING_RESOLUTION}:", self.resolution_note_edit)
        form.addRow(f"{LABEL_FINDING_RESOLVED_AT}:", self.resolved_at_edit)
        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self, is_new=True)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        configure_form_tab_navigation(self)
        self._apply_draft(self._original)

    @property
    def result_draft(self) -> StateSupervisionFindingDraft | None:
        return self._result

    def _set_combo_data(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _apply_draft(self, draft: StateSupervisionFindingDraft) -> None:
        type_value = draft.finding_type or FINDING_TYPE_ZJISTENI
        if self.type_combo.findData(type_value) < 0:
            type_value = FINDING_TYPE_ZJISTENI
        self._set_combo_data(self.type_combo, type_value)
        self.description_edit.setPlainText(str(draft.description or ""))
        self.place_edit.setText(str(draft.source_area_label or ""))
        status_value = draft.status or FINDING_STATUS_OTEVRENE
        if self.status_combo.findData(status_value) < 0:
            status_value = FINDING_STATUS_OTEVRENE
        self._set_combo_data(self.status_combo, status_value)
        if draft.responsible_person_id:
            self.person_selector.set_person_id(draft.responsible_person_id)
        elif draft.responsible_person_name:
            self.person_selector.setCurrentText(str(draft.responsible_person_name))
        else:
            self.person_selector.set_person_id(None)
        self.due_date_edit.set_date_value(draft.due_date)
        self.recommended_action_edit.setPlainText(str(draft.recommended_action or ""))
        self.resolution_note_edit.setPlainText(str(draft.resolution_note or ""))
        self.resolved_at_edit.set_date_value(draft.resolved_at)

    def get_draft(self) -> StateSupervisionFindingDraft:
        person = self.person_selector.current_person()
        person_id = self.person_selector.current_person_id()
        person_name = (
            person.display_name
            if person is not None
            else self.person_selector.currentText().strip()
        )
        finding_type = self.type_combo.currentData() or FINDING_TYPE_ZJISTENI
        status = self.status_combo.currentData() or FINDING_STATUS_OTEVRENE
        return replace(
            self._original,
            finding_type=str(finding_type),
            description=self.description_edit.toPlainText().strip(),
            source_area_label=self.place_edit.text().strip(),
            status=str(status),
            responsible_person_id=person_id,
            responsible_person_name=str(person_name or ""),
            due_date=self.due_date_edit.get_date(),
            recommended_action=self.recommended_action_edit.toPlainText().strip(),
            resolution_note=self.resolution_note_edit.toPlainText().strip(),
            resolved_at=self.resolved_at_edit.get_date(),
        )

    def _on_save(self) -> None:
        if not self.description_edit.toPlainText().strip():
            QMessageBox.warning(
                self, self.windowTitle(), FINDING_DESCRIPTION_REQUIRED_MESSAGE
            )
            return
        self._result = self.get_draft()
        self.accept()


def exec_finding_dialog(
    parent: QWidget | None,
    *,
    draft: StateSupervisionFindingDraft | None = None,
    is_new: bool = False,
) -> StateSupervisionFindingDraft | None:
    overlay = _ParentDimOverlay(parent) if parent is not None else None
    dialog = StateSupervisionFindingDialog(parent, draft=draft, is_new=is_new)
    try:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result_draft
        return None
    finally:
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
