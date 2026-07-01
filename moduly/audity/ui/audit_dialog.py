from PySide6.QtWidgets import (
    QDialog,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from moduly.audity.constants import FINDING_SOURCE_LABEL, TAB_AUDITOVANE_PROCESY
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.ui.audit_commission_widget import AuditCommissionWidget
from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget
from moduly.audity.ui.audit_spis_widget import AuditSpisWidget


class AuditDialog(QDialog):
    """Dialog auditu systému řízení."""

    def __init__(self, parent=None, audit=None):
        super().__init__(parent)

        self.audit = audit

        self.setWindowTitle(FINDING_SOURCE_LABEL)
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.spis_widget = AuditSpisWidget()
        self.commission_widget = AuditCommissionWidget()
        self.processes_widget = AuditProcessesWidget()
        self.tabs.addTab(self.spis_widget, "Spis")
        self.tabs.addTab(self.commission_widget, "Komise")
        self.tabs.addTab(self.processes_widget, TAB_AUDITOVANE_PROCESY)
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        audit_id = audit.id if audit is not None else None
        self.processes_widget.set_audit_id(audit_id)
        self.commission_widget.set_audit_context(audit_id)
        self.spis_widget.load_audit(audit)

    def exec(self):
        self.showMaximized()
        return super().exec()

    def accept(self) -> None:
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Auditní tým", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return
        super().accept()

    def get_data(self) -> dict:
        data = self.spis_widget.get_data()
        data["commission_members"] = self.commission_widget.get_members_for_save()
        return data

    def prepare_save_payload(self, data: dict) -> dict:
        payload = {key: value for key, value in data.items() if key != "commission_members"}

        workplace_id = payload.get("workplace_id")
        if workplace_id is None:
            workplace_id = audit_service.resolve_workplace_id_by_name(
                payload.get("workplace_name", "")
            )
            payload["workplace_id"] = workplace_id
        payload["workplace_name"] = audit_service.resolve_workplace_name(workplace_id)
        payload["title"] = payload.get("title") or ""
        return payload

    def save_commission_members(self, audit_id: int, data: dict) -> None:
        members = data.get("commission_members")
        if members is None:
            return
        audit_commission_service.save_members(audit_id, members)
