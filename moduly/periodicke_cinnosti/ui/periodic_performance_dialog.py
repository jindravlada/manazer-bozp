"""Dialog provedení periodické činnosti."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.attachment_widget import AttachmentWidget
from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import configure_resizable_form_dialog, create_save_cancel_box
from core.widgets.editor_dialog_controller import EditorDialogController
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.periodicke_cinnosti.constants import (
    DIALOG_TITLE_PERFORM,
    ENTITY_PERIODIC_OCCURRENCE,
    PERFORMANCE_ATTACHMENTS_HINT,
    PERFORMED_DATE_REQUIRED_MESSAGE,
    PERFORMER_KIND_EXTERNAL,
    PERFORMER_KIND_LABELS,
    PERFORMER_KIND_PERSON,
    PERFORMER_KIND_THP,
    PERFORMER_KINDS,
)
from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
    PeriodicActivityValidationError,
    periodic_activity_service,
)


class PeriodicPerformanceDialog(QDialog):
    def __init__(self, parent=None, *, activity_id: int, activity_title: str = ""):
        super().__init__(parent)
        self.activity_id = int(activity_id)
        self.occurrence = None
        title = DIALOG_TITLE_PERFORM
        if activity_title:
            title = f"{DIALOG_TITLE_PERFORM} – {activity_title}"
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        configure_resizable_form_dialog(self, width=560, height=520, min_width=480, min_height=420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.date_edit = DateEdit()

        self.performer_kind = QComboBox()
        for kind in PERFORMER_KINDS:
            self.performer_kind.addItem(PERFORMER_KIND_LABELS[kind], kind)

        self.thp_selector = ThpWorkerSelector(include_empty=True)
        self.person_selector = PersonSelector(include_empty=True, allow_add_new=True)
        self.external_edit = QLineEdit()
        self.external_edit.setPlaceholderText("Jméno dodavatele / laboratoře")

        self.performer_stack = QStackedWidget()
        self.performer_stack.addWidget(self.thp_selector)
        self.performer_stack.addWidget(self.person_selector)
        self.performer_stack.addWidget(self.external_edit)

        self.result_edit = QTextEdit()
        self.result_edit.setAcceptRichText(False)
        self.result_edit.setMinimumHeight(90)

        form.addRow("Datum provedení:", self.date_edit)
        form.addRow("Kdo provedl:", self.performer_kind)
        form.addRow("", self.performer_stack)
        form.addRow("Výsledek / poznámka:", self.result_edit)
        layout.addLayout(form)

        self.attachments_hint = QLabel(PERFORMANCE_ATTACHMENTS_HINT)
        self.attachments_hint.setObjectName("MutedText")
        self.attachments_hint.setWordWrap(True)
        layout.addWidget(self.attachments_hint)
        self.attachments = AttachmentWidget(ENTITY_PERIODIC_OCCURRENCE, None)
        layout.addWidget(self.attachments, 1)

        buttons = create_save_cancel_box(self, is_new=True)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=True,
            title=self.windowTitle(),
            on_save=self._save,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()
        self._editor.capture_baseline()

        self.performer_kind.currentIndexChanged.connect(self._sync_performer_stack)
        self._sync_performer_stack()

    def _sync_performer_stack(self) -> None:
        kind = self.performer_kind.currentData()
        index = {
            PERFORMER_KIND_THP: 0,
            PERFORMER_KIND_PERSON: 1,
            PERFORMER_KIND_EXTERNAL: 2,
        }.get(kind, 0)
        self.performer_stack.setCurrentIndex(index)

    def _performed_date(self) -> date | None:
        qdate = self.date_edit.date()
        if not qdate.isValid():
            return None
        return date(qdate.year(), qdate.month(), qdate.day())

    def _set_form_enabled(self, enabled: bool) -> None:
        self.date_edit.setEnabled(enabled)
        self.performer_kind.setEnabled(enabled)
        self.performer_stack.setEnabled(enabled)
        self.result_edit.setEnabled(enabled)

    def get_data(self) -> dict:
        kind = self.performer_kind.currentData() or PERFORMER_KIND_THP
        performed_by_id = None
        performed_by_name = ""
        if kind == PERFORMER_KIND_THP:
            worker = self.thp_selector.current_person()
            performed_by_id = self.thp_selector.current_person_id()
            performed_by_name = (
                worker.display_name if worker else self.thp_selector.currentText().strip()
            )
        elif kind == PERFORMER_KIND_PERSON:
            person = self.person_selector.current_person()
            performed_by_id = self.person_selector.current_person_id()
            performed_by_name = (
                person.display_name if person else self.person_selector.display_text()
            )
        else:
            performed_by_name = self.external_edit.text().strip()

        return {
            "performed_at": self._performed_date(),
            "performed_by_kind": kind,
            "performed_by_id": performed_by_id,
            "performed_by_name": performed_by_name,
            "result_note": self.result_edit.toPlainText().strip(),
        }

    def _save(self) -> bool:
        if self.occurrence is not None:
            return True
        if self._performed_date() is None:
            QMessageBox.warning(self, DIALOG_TITLE_PERFORM, PERFORMED_DATE_REQUIRED_MESSAGE)
            return False
        try:
            self.occurrence = periodic_activity_service.record_performance(
                self.activity_id,
                **self.get_data(),
            )
        except PeriodicActivityValidationError as error:
            QMessageBox.warning(self, DIALOG_TITLE_PERFORM, str(error))
            return False
        self.attachments.set_entity(ENTITY_PERIODIC_OCCURRENCE, self.occurrence.id)
        self.attachments_hint.setText("Přílohy k tomuto provedení:")
        self._set_form_enabled(False)
        return True
