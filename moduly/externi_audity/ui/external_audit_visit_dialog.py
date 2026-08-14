"""Dialog návštěvy programu externího auditu."""

from __future__ import annotations

from datetime import date, time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.nullable_time_edit import NullableTimeEdit, parse_czech_time
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    list_auditable_workplaces,
)
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
    EXTERNAL_AUDIT_PARTICIPANT_ROLE_LABELS,
)
from moduly.externi_audity.sluzby.external_audit_draft import (
    ParticipantDraft,
    VisitDraft,
    new_client_key,
)
from moduly.externi_audity.sluzby.external_audit_service import (
    ExternalAuditError,
    _validate_time_range,
)


def _time_to_stored(value: time | None) -> str | None:
    if value is None:
        return None
    return f"{value.hour:02d}:{value.minute:02d}"


def _apply_stored_time(widget: NullableTimeEdit, stored: str | None) -> None:
    if not stored:
        widget.clear_time()
        return
    parsed = parse_czech_time(stored)
    widget.set_time_value(parsed)


class ExternalAuditVisitDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        visit: VisitDraft | None = None,
        participants: list[ParticipantDraft] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Návštěva programu" if visit else "Nová návštěva")
        configure_resizable_form_dialog(
            self, width=560, height=560, min_width=480, min_height=420
        )
        self._visit = visit
        self._participants = list(participants or [])
        self.result_visit: VisitDraft | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.visit_date = NullableDateEdit()
        if visit is not None:
            self.visit_date.set_date_value(visit.visit_date)
        else:
            self.visit_date.set_date_value(date.today())
        form.addRow("Datum *:", self.visit_date)

        time_row = QHBoxLayout()
        self.time_from = NullableTimeEdit()
        self.time_to = NullableTimeEdit()
        _apply_stored_time(self.time_from, visit.time_from if visit else None)
        _apply_stored_time(self.time_to, visit.time_to if visit else None)
        time_row.addWidget(self.time_from)
        time_row.addWidget(QLabel("–"))
        time_row.addWidget(self.time_to)
        form.addRow("Čas od / do:", time_row)

        self.workplace = QComboBox()
        self.workplace.addItem("— vyberte provoz —", None)
        selected_wp = visit.workplace_id if visit else None
        for workplace in list_auditable_workplaces():
            label = str(workplace.name or "").strip() or f"#{workplace.id}"
            self.workplace.addItem(label, int(workplace.id))
        if selected_wp is not None:
            index = self.workplace.findData(int(selected_wp))
            if index < 0 and visit is not None:
                self.workplace.addItem(
                    visit.workplace_name_snapshot or f"#{selected_wp}",
                    int(selected_wp),
                )
                index = self.workplace.findData(int(selected_wp))
            self.workplace.setCurrentIndex(max(index, 0))
        form.addRow("Provoz *:", self.workplace)

        layout.addLayout(form)

        self.auditor_list = self._role_list(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            visit,
        )
        self.rep_list = self._role_list(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
            visit,
        )
        self.invited_list = self._role_list(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
            visit,
        )
        layout.addWidget(
            QLabel(
                EXTERNAL_AUDIT_PARTICIPANT_ROLE_LABELS[
                    EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
                ]
                + ":"
            )
        )
        layout.addWidget(self.auditor_list)
        layout.addWidget(
            QLabel(
                EXTERNAL_AUDIT_PARTICIPANT_ROLE_LABELS[
                    EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE
                ]
                + ":"
            )
        )
        layout.addWidget(self.rep_list)
        layout.addWidget(
            QLabel(
                EXTERNAL_AUDIT_PARTICIPANT_ROLE_LABELS[
                    EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON
                ]
                + ":"
            )
        )
        layout.addWidget(self.invited_list)

        self.note = QTextEdit()
        self.note.setAcceptRichText(False)
        self.note.setMaximumHeight(80)
        if visit and visit.note:
            self.note.setPlainText(visit.note)
        layout.addWidget(QLabel("Poznámka:"))
        layout.addWidget(self.note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        for button in buttons.buttons():
            button.setAutoDefault(False)
            button.setDefault(False)
        layout.addWidget(buttons)

    def _role_list(
        self, role: str, visit: VisitDraft | None
    ) -> QListWidget:
        widget = QListWidget()
        widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        selected = set(visit.participant_keys if visit else [])
        for participant in self._participants:
            if participant.role != role:
                continue
            item = QListWidgetItem(participant.display_name_snapshot)
            item.setData(Qt.ItemDataRole.UserRole, participant.client_key)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(
                Qt.CheckState.Checked
                if participant.client_key in selected
                else Qt.CheckState.Unchecked
            )
            widget.addItem(item)
        return widget

    def _checked_keys(self, widget: QListWidget) -> list[str]:
        keys: list[str] = []
        for row in range(widget.count()):
            item = widget.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                keys.append(str(item.data(Qt.ItemDataRole.UserRole)))
        return keys

    def _finish_pending_edits(self) -> None:
        """Dokončí rozpracovanou editaci data/času před sběrem hodnot."""
        self.visit_date._normalize_input()
        self.time_from._normalize_input()
        self.time_to._normalize_input()

    def _read_optional_time(self, widget: NullableTimeEdit, label: str) -> str | None:
        text = widget.line_edit.text().strip()
        if not text:
            return None
        parsed = widget.get_time()
        if parsed is None:
            raise ExternalAuditError(
                f"Neplatný {label} „{text}“. Použijte např. 800 nebo 8:00."
            )
        return _time_to_stored(parsed)

    def _accept(self) -> None:
        self._finish_pending_edits()
        visit_date = self.visit_date.get_date()
        if visit_date is None:
            QMessageBox.warning(self, "Návštěva", "Datum je povinné.")
            return
        workplace_id = self.workplace.currentData()
        if workplace_id is None:
            QMessageBox.warning(self, "Návštěva", "Vyberte auditovatelný provoz.")
            return
        try:
            time_from = self._read_optional_time(self.time_from, "čas od")
            time_to = self._read_optional_time(self.time_to, "čas do")
            time_from, time_to = _validate_time_range(time_from, time_to)
        except ExternalAuditError as exc:
            QMessageBox.warning(self, "Návštěva", str(exc))
            return

        from moduly.audity.sluzby.audit_auditable_workplace_service import (
            require_auditable_workplace_id,
        )

        try:
            workplace = require_auditable_workplace_id(int(workplace_id))
        except ValueError as exc:
            QMessageBox.warning(self, "Návštěva", str(exc))
            return

        keys = (
            self._checked_keys(self.auditor_list)
            + self._checked_keys(self.rep_list)
            + self._checked_keys(self.invited_list)
        )
        base = self._visit
        self.result_visit = VisitDraft(
            client_key=base.client_key if base else new_client_key(),
            visit_date=visit_date,
            workplace_id=int(workplace.id),
            workplace_name_snapshot=str(workplace.name or "").strip(),
            workplace_address_snapshot=str(workplace.address or "").strip(),
            time_from=time_from,
            time_to=time_to,
            note=self.note.toPlainText().strip() or None,
            display_order=base.display_order if base else 0,
            participant_keys=keys,
            db_id=base.db_id if base else None,
        )
        self.accept()
