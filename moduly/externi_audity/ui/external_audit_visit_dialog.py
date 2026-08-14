"""Dialog návštěvy programu externího auditu."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.dialog_utils import configure_resizable_form_dialog
from core.widgets.nullable_date_edit import NullableDateEdit
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
        self.time_from = QLineEdit(visit.time_from if visit and visit.time_from else "")
        self.time_from.setPlaceholderText("HH:MM")
        self.time_to = QLineEdit(visit.time_to if visit and visit.time_to else "")
        self.time_to.setPlaceholderText("HH:MM")
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

    def _accept(self) -> None:
        visit_date = self.visit_date.get_date()
        if visit_date is None:
            QMessageBox.warning(self, "Návštěva", "Datum je povinné.")
            return
        workplace_id = self.workplace.currentData()
        if workplace_id is None:
            QMessageBox.warning(self, "Návštěva", "Vyberte auditovatelný provoz.")
            return
        try:
            time_from, time_to = _validate_time_range(
                self.time_from.text(), self.time_to.text()
            )
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
