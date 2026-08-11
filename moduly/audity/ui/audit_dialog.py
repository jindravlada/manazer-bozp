from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
)

from core.shared.verification_type import (
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
)
from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    EDITOR_SAVE_LABEL,
    configure_editor_close_button,
    configure_editor_save_button,
    confirm_unsaved_editor_close,
)
from moduly.audity.constants import FINDING_SOURCE_LABEL, TAB_LABELS
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_program_service import AuditVisitContext
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.ui.audit_commission_widget import AuditCommissionWidget
from moduly.audity.ui.audit_conclusion_widget import AuditConclusionWidget
from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget
from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget
from moduly.audity.ui.audit_spis_widget import AuditSpisWidget
from moduly.audity.ui.audit_tasks_widget import AuditTasksWidget
from moduly.audity.ui.audit_workplace_history_widget import AuditWorkplaceHistoryWidget

_SAVE_CLOSE_LABEL = "Uložit a zavřít"


class AuditDialog(QDialog):
    """Dialog auditu systému řízení."""

    def __init__(self, parent=None, audit=None, *, visit_context: AuditVisitContext | None = None):
        super().__init__(parent)

        self.audit = audit
        self._baseline: object | None = None
        self._closing = False
        if visit_context is None and audit is not None:
            from moduly.audity.sluzby.audit_program_service import audit_program_service

            visit_context = audit_program_service.resolve_visit_context_for_audit(audit)
        self._visit_context = visit_context

        self.setWindowTitle(FINDING_SOURCE_LABEL)
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.spis_widget = AuditSpisWidget()
        self.commission_widget = AuditCommissionWidget()
        self.processes_widget = AuditProcessesWidget(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        self.terrain_widget = AuditProcessesWidget(
            verification_type=VERIFICATION_TYPE_TERRAIN
        )
        self.history_widget = AuditWorkplaceHistoryWidget()
        self.findings_widget = AuditFindingsWidget()
        self.tasks_widget = AuditTasksWidget()
        self.conclusion_widget = AuditConclusionWidget()
        self.tabs.addTab(self.spis_widget, TAB_LABELS[0])
        self.tabs.addTab(self.commission_widget, TAB_LABELS[1])
        self.tabs.addTab(self.processes_widget, TAB_LABELS[2])
        self.tabs.addTab(self.terrain_widget, TAB_LABELS[3])
        self.tabs.addTab(self.history_widget, TAB_LABELS[4])
        self.tabs.addTab(self.findings_widget, TAB_LABELS[5])
        self.tabs.addTab(self.tasks_widget, TAB_LABELS[6])
        self.tabs.addTab(self.conclusion_widget, TAB_LABELS[7])
        layout.addWidget(self.tabs)

        layout.addLayout(self._build_footer())

        audit_id = audit.id if audit is not None else None
        self.set_audit_id(audit_id)
        if visit_context is not None:
            planned = visit_context.planned_process_ids
            self.processes_widget.set_planned_process_ids(planned)
            self.terrain_widget.set_planned_process_ids(planned)
        self.processes_widget.set_on_finding_saved(self._on_finding_changed)
        self.terrain_widget.set_on_finding_saved(self._on_finding_changed)
        self.processes_widget.set_on_verification_type_changed(
            self._on_verification_type_changed
        )
        self.terrain_widget.set_on_verification_type_changed(
            self._on_verification_type_changed
        )
        self.findings_widget.set_on_task_changed(self._on_related_data_changed)
        self.conclusion_widget.set_complete_handler(self._complete_audit)
        self.spis_widget.load_audit(audit)
        self.history_widget.load_audit(audit)
        self.conclusion_widget.load_audit(audit)
        self.commission_widget.set_audit_context(audit_id)
        self._capture_baseline()

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        footer.addStretch(1)

        self._save_btn = QPushButton()
        configure_editor_save_button(self._save_btn)
        self._save_btn.setText(EDITOR_SAVE_LABEL)

        self._save_close_btn = QPushButton(_SAVE_CLOSE_LABEL)
        configure_editor_save_button(self._save_close_btn)
        self._save_close_btn.setText(_SAVE_CLOSE_LABEL)

        self._close_btn = QPushButton()
        configure_editor_close_button(self._close_btn, is_new=False)
        self._close_btn.setText(EDITOR_CLOSE_LABEL)

        for button in (self._save_btn, self._save_close_btn, self._close_btn):
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._save_btn.clicked.connect(self._save_keep_open)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._close_btn.clicked.connect(self._request_close)

        footer.addWidget(self._save_btn)
        footer.addWidget(self._save_close_btn)
        footer.addWidget(self._close_btn)
        return footer

    def _capture_baseline(self) -> None:
        self._baseline = self.get_data()

    def _is_dirty(self) -> bool:
        return self.get_data() != self._baseline

    def set_audit_id(self, audit_id: int | None) -> None:
        self.processes_widget.set_audit_id(audit_id)
        self.terrain_widget.set_audit_id(audit_id)
        self.findings_widget.set_audit_id(audit_id)
        self.tasks_widget.set_audit_id(audit_id)

    def _on_finding_changed(self) -> None:
        self._on_related_data_changed()
        self.processes_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()

    def _on_verification_type_changed(self) -> None:
        self.processes_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()

    def _on_related_data_changed(self) -> None:
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.conclusion_widget.refresh()

    def _save_keep_open(self) -> None:
        self._persist()

    def _save_and_close(self) -> None:
        if self._persist():
            self._closing = True
            QDialog.accept(self)

    def _persist(self) -> bool:
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Auditní tým", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        payload = self.prepare_save_payload(data)

        if self.audit is None:
            created = audit_service.create_audit(**payload)
            if created is None:
                return False
            self.audit = created
            self.save_commission_members(created.id, data)
            self._reload_after_persist()
        else:
            updated = audit_service.update_audit(self.audit.id, **payload)
            if updated is None:
                return False
            self.save_commission_members(self.audit.id, data)
            self.audit = updated
            self._reload_after_persist()

        self._capture_baseline()
        return True

    def _reload_after_persist(self) -> None:
        assert self.audit is not None
        self.set_audit_id(self.audit.id)
        self.spis_widget.load_audit(self.audit)
        self.history_widget.load_audit(self.audit)
        self.conclusion_widget.load_audit(self.audit)
        self.commission_widget.set_audit_context(self.audit.id)

    def accept(self) -> None:
        """Kompatibilita: validace + uložení (stejná logika jako Uložit a zavřít)."""
        if self._persist():
            self._closing = True
            QDialog.accept(self)

    def _request_close(self) -> None:
        if self._confirm_close():
            self._closing = True
            self.reject()

    def _confirm_close(self) -> bool:
        if self._closing or not self._is_dirty():
            return True
        decision = confirm_unsaved_editor_close(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._persist():
                return False
            self._closing = True
            QDialog.accept(self)
            return False
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_close():
            self._closing = True
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._confirm_close():
            self._closing = True
            QDialog.reject(self)

    def get_data(self) -> dict:
        data = self.spis_widget.get_data()
        data.update(self.conclusion_widget.get_data())
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

    def _complete_audit(self, *, finished_at) -> bool:
        if self.audit is None:
            return False

        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Auditní tým", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        data["finished_at"] = finished_at
        payload = self.prepare_save_payload(data)

        updated = audit_service.update_audit(self.audit.id, **payload)
        if updated is None:
            return False

        audit_commission_service.save_members(
            self.audit.id,
            data.get("commission_members", []),
        )

        self.audit = updated
        self.conclusion_widget.load_audit(self.audit)
        self.history_widget.load_audit(self.audit)
        self.spis_widget.load_audit(self.audit)
        self._capture_baseline()
        return True
