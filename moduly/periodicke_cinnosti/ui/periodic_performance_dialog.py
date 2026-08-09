"""Dialog provedení periodické činnosti."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.person_selector import PersonSelector
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.periodicke_cinnosti.constants import (
    DIALOG_TITLE_PERFORM,
    PERFORMED_DATE_REQUIRED_MESSAGE,
    PERFORMER_KIND_EXTERNAL,
    PERFORMER_KIND_LABELS,
    PERFORMER_KIND_PERSON,
    PERFORMER_KIND_THP,
    PERFORMER_KINDS,
)


class PeriodicPerformanceDialog(QDialog):
    def __init__(self, parent=None, *, activity_title: str = ""):
        super().__init__(parent)
        title = DIALOG_TITLE_PERFORM
        if activity_title:
            title = f"{DIALOG_TITLE_PERFORM} – {activity_title}"
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.resize(520, 320)

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

        buttons = create_save_cancel_box(self, is_new=True)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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

    def _on_accept(self) -> None:
        if self._performed_date() is None:
            QMessageBox.warning(self, DIALOG_TITLE_PERFORM, PERFORMED_DATE_REQUIRED_MESSAGE)
            return
        self.accept()

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
