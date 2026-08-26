from __future__ import annotations

import copy

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

from core.shared.section_summary import NOTES_MODE_SECTION_SUMMARY_V1
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
from moduly.audity.constants import (
    AUDIT_LEAD_RECOMMENDATION_EMPTY_REVIEW_MESSAGE,
    AUDIT_LEAD_RECOMMENDATION_STALE_REVIEW_MESSAGE,
    FINDING_SOURCE_LABEL,
    TAB_LABELS,
    TAB_MIMORADNE,
)
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits
from moduly.audity.sluzby.audit_program_service import AuditVisitContext
from moduly.audity.sluzby.audit_question_source_service import (
    AuditQuestionSourceError,
    audit_question_source_service,
)
from moduly.audity.sluzby.audit_service import AuditCompletionError, audit_service
from moduly.audity.sluzby.audit_lead_recommendation_service import (
    compute_results_signature,
    generate_lead_auditor_recommendation,
    is_recommendation_blank,
)
from moduly.audity.sluzby.audit_v2_create_service import (
    AuditV2CreateError,
    create_manual_audit_with_v2_snapshot,
)
from moduly.audity.sluzby.system_audit_workplace_service import (
    SystemAuditWorkplaceError,
)
from moduly.audity.ui.audit_commission_widget import AuditCommissionWidget
from moduly.audity.ui.audit_conclusion_widget import AuditConclusionWidget
from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget
from moduly.audity.ui.audit_processes_widget import AuditProcessesWidget
from moduly.audity.ui.audit_spis_widget import AuditSpisWidget
from moduly.audity.ui.audit_tasks_widget import AuditTasksWidget
from moduly.audity.ui.audit_workplace_history_widget import AuditWorkplaceHistoryWidget
from moduly.audity.sluzby.audit_extraordinary_question_service import (
    AuditExtraordinaryError,
)
_SAVE_CLOSE_LABEL = "Uložit a zavřít"


class AuditDialog(QDialog):
    """Dialog auditu systému řízení."""

    def __init__(self, parent=None, audit=None, *, visit_context: AuditVisitContext | None = None):
        super().__init__(parent)

        self.audit = audit
        self._baseline: object | None = None
        self._closing = False
        self._deferred = AuditDeferredEdits()
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
        self.extraordinary_widget = AuditProcessesWidget(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            extraordinary_only=True,
        )
        self.history_widget = AuditWorkplaceHistoryWidget()
        self.findings_widget = AuditFindingsWidget()
        self.tasks_widget = AuditTasksWidget()
        self.conclusion_widget = AuditConclusionWidget()
        self.tabs.addTab(self.spis_widget, TAB_LABELS[0])
        self.tabs.addTab(self.commission_widget, TAB_LABELS[1])
        self.tabs.addTab(self.history_widget, TAB_LABELS[2])
        self.tabs.addTab(self.processes_widget, TAB_LABELS[3])
        self.tabs.addTab(self.terrain_widget, TAB_LABELS[4])
        self.tabs.addTab(self.extraordinary_widget, TAB_MIMORADNE)
        self.tabs.addTab(self.findings_widget, TAB_LABELS[6])
        self.tabs.addTab(self.tasks_widget, TAB_LABELS[7])
        self.tabs.addTab(self.conclusion_widget, TAB_LABELS[8])
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        layout.addLayout(self._build_footer())

        audit_id = audit.id if audit is not None else None
        self._wire_deferred_edits()
        self.set_audit_id(audit_id)
        if visit_context is not None:
            planned = visit_context.planned_process_ids
            self.processes_widget.set_planned_process_ids(planned)
            self.terrain_widget.set_planned_process_ids(planned)
        self.processes_widget.set_on_finding_saved(self._on_finding_changed)
        self.terrain_widget.set_on_finding_saved(self._on_finding_changed)
        self.extraordinary_widget.set_on_finding_saved(self._on_finding_changed)
        self.processes_widget.set_on_verification_type_changed(
            self._on_verification_type_changed
        )
        self.terrain_widget.set_on_verification_type_changed(
            self._on_verification_type_changed
        )
        self.findings_widget.set_on_task_changed(self._on_related_data_changed)
        self.conclusion_widget.set_complete_handler(self._complete_audit)
        self.conclusion_widget.set_review_needed_handler(
            lambda: self.tabs.setCurrentWidget(self.conclusion_widget)
        )
        self.spis_widget.load_audit(audit)
        # Úvod: jen kontext + text changes_since_last; historie lazy při otevření záložky.
        self.history_widget.load_audit(audit)
        self.history_widget.content_modified.connect(self._on_deferred_dirty)
        self.conclusion_widget.load_audit(audit)
        self.commission_widget.set_audit_context(audit_id)
        self._capture_baseline()

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.history_widget:
            self.history_widget.ensure_loaded()
        current = self.tabs.widget(index)
        if current is self.processes_widget or current is self.terrain_widget:
            current.reload_section_summary()

    def _wire_deferred_edits(self) -> None:
        self.processes_widget.set_deferred_edits(self._deferred)
        self.terrain_widget.set_deferred_edits(self._deferred)
        self.extraordinary_widget.set_deferred_edits(self._deferred)
        self.findings_widget.set_deferred_edits(self._deferred)
        self.tasks_widget.set_deferred_edits(self._deferred)
        self.history_widget.set_deferred_edits(self._deferred)
        self.processes_widget.set_on_deferred_dirty(self._on_deferred_dirty)
        self.terrain_widget.set_on_deferred_dirty(self._on_deferred_dirty)
        self.extraordinary_widget.set_on_deferred_dirty(self._on_deferred_dirty)

    def _on_deferred_dirty(self) -> None:
        # Dirty se počítá z bufferu; callback drží konzistenci s budoucími signaly.
        return

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
            # Enter v poli formuláře nesmí samo spustit Uložit.
            button.setAutoDefault(False)
            button.setDefault(False)

        self._save_btn.clicked.connect(self._save_keep_open)
        self._save_close_btn.clicked.connect(self._save_and_close)
        self._close_btn.clicked.connect(self._request_close)

        footer.addWidget(self._save_btn)
        footer.addWidget(self._save_close_btn)
        footer.addWidget(self._close_btn)
        return footer

    def _capture_baseline(self) -> None:
        self._baseline = copy.deepcopy(self.get_data())

    def _is_dirty(self) -> bool:
        return self.get_data() != self._baseline or self._deferred.has_changes()

    def set_audit_id(self, audit_id: int | None) -> None:
        self.processes_widget.set_audit_id(audit_id)
        self.terrain_widget.set_audit_id(audit_id)
        self.extraordinary_widget.set_audit_id(audit_id)
        self.findings_widget.set_audit_id(audit_id)
        self.tasks_widget.set_audit_id(audit_id)
        notes_mode = (
            getattr(self.audit, "notes_mode", None)
            if self.audit is not None
            else NOTES_MODE_SECTION_SUMMARY_V1
        )
        self.processes_widget.set_notes_mode(notes_mode)
        self.terrain_widget.set_notes_mode(notes_mode)
        self.extraordinary_widget.set_notes_mode(None)
        # Jeden resolve pro všechny záložky — snapshot bez ensure_catalogs / get_knowledge_tree.
        try:
            source = audit_question_source_service.resolve_for_audit(audit_id)
        except AuditQuestionSourceError as exc:
            QMessageBox.warning(self, FINDING_SOURCE_LABEL, str(exc))
            source = None
        self.processes_widget.set_question_source(source)
        self.terrain_widget.set_question_source(source)
        self.extraordinary_widget.set_question_source(source)

    def _on_finding_changed(self) -> None:
        self._on_related_data_changed()
        self.processes_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()
        self.extraordinary_widget.refresh_findings_display()
        self.extraordinary_widget.refresh_findings_display()

    def _on_verification_type_changed(self) -> None:
        self.processes_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()
        self.extraordinary_widget.refresh_findings_display()
        self.extraordinary_widget.refresh_findings_display()

    def _on_related_data_changed(self) -> None:
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.conclusion_widget.refresh()

    def _save_keep_open(self) -> None:
        self._persist()

    def _save_and_close(self) -> None:
        if self._persist():
            self._done_accept()

    def _persist(self) -> bool:
        """Zápis Spis/Závěr/komise + odložených zjištění/úkolů/výsledků kontroly."""
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Auditní tým", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        self.processes_widget.capture_section_summary()
        self.terrain_widget.capture_section_summary()

        if self.audit is None:
            payload = self.prepare_save_payload(data)
            try:
                created = create_manual_audit_with_v2_snapshot(
                    fields=payload,
                    commission_members=data.get("commission_members"),
                )
            except (
                AuditV2CreateError,
                SystemAuditWorkplaceError,
                AuditExtraordinaryError,
                ValueError,
            ) as exc:
                QMessageBox.warning(self, "Nový audit", str(exc))
                return False
            if created is None:
                return False
            self.audit = created
            self._deferred.flush(entity_id=created.id)
            self._reload_after_persist()
        else:
            self._deferred.flush(entity_id=self.audit.id)
            payload = self.prepare_save_payload(data)
            try:
                updated = audit_service.update_audit(self.audit.id, **payload)
            except AuditCompletionError as exc:
                QMessageBox.warning(self, "Závěr", str(exc))
                self.tabs.setCurrentWidget(self.conclusion_widget)
                return False
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
        if self.history_widget._loaded:
            self.history_widget.refresh()
        self.conclusion_widget.load_audit(self.audit)
        self.commission_widget.set_audit_context(self.audit.id)
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.processes_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()
        self.extraordinary_widget.refresh_findings_display()

    def _done_accept(self) -> None:
        self._closing = True
        QDialog.accept(self)

    def _done_reject(self) -> None:
        self._closing = True
        QDialog.reject(self)

    def accept(self) -> None:
        """Validace komise a zavření Accepted — bez zápisu do DB.

        Ukládání jen přes Uložit / Uložit a zavřít / Uložit v dirty promptu.
        """
        if self._closing:
            QDialog.accept(self)
            return
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Auditní tým", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return
        self._done_accept()

    def _request_close(self) -> None:
        if self._confirm_close():
            self._done_reject()

    def _confirm_close(self) -> bool:
        """True = lze zavřít (čisté / Neukládat). False = zůstat otevřený."""
        if self._closing or not self._is_dirty():
            return True
        decision = confirm_unsaved_editor_close(self, title=self.windowTitle())
        if decision == "cancel":
            return False
        if decision == "save":
            if not self._persist():
                return False
            self._done_accept()
            return False
        # Neukládat — zahodit UI i odložené změny; DB netknutá.
        self._deferred.clear()
        self.history_widget.discard_changes()
        if self.audit is not None:
            self.spis_widget.load_audit(self.audit)
            self.conclusion_widget.load_audit(self.audit)
            self.commission_widget.set_audit_context(self.audit.id)
        return True

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing:
            event.accept()
            return
        if self._confirm_close():
            self._closing = True
            event.accept()
        else:
            event.ignore()

    def reject(self) -> None:
        if self._closing:
            QDialog.reject(self)
            return
        if self._confirm_close():
            self._done_reject()

    def get_data(self) -> dict:
        data = self.spis_widget.get_data()
        data.update(self.conclusion_widget.get_data())
        data.update(self.history_widget.get_data())
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
        rec = payload.get("lead_auditor_recommendation")
        if is_recommendation_blank(rec):
            payload["lead_auditor_recommendation"] = None
            payload["lead_auditor_recommendation_results_signature"] = None
        elif self.audit is not None and getattr(self.audit, "id", None):
            payload["lead_auditor_recommendation_results_signature"] = (
                compute_results_signature(int(self.audit.id))
            )
        else:
            payload["lead_auditor_recommendation_results_signature"] = None
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

        self.processes_widget.capture_section_summary()
        self.terrain_widget.capture_section_summary()
        self._deferred.flush(entity_id=self.audit.id)

        rec = self.conclusion_widget.recommendation_edit.toPlainText()
        current_sig = compute_results_signature(int(self.audit.id))
        saved_sig = str(
            getattr(self.audit, "lead_auditor_recommendation_results_signature", None)
            or ""
        ).strip()

        if is_recommendation_blank(rec):
            draft = generate_lead_auditor_recommendation(int(self.audit.id))
            self.conclusion_widget.apply_generated_recommendation(draft)
            self.tabs.setCurrentWidget(self.conclusion_widget)
            QMessageBox.information(
                self,
                "Závěr",
                AUDIT_LEAD_RECOMMENDATION_EMPTY_REVIEW_MESSAGE,
            )
            return False

        if (
            saved_sig != current_sig
            and not self.conclusion_widget.recommendation_review_pending()
        ):
            self.conclusion_widget.mark_recommendation_review_pending()
            self.tabs.setCurrentWidget(self.conclusion_widget)
            QMessageBox.warning(
                self,
                "Závěr",
                AUDIT_LEAD_RECOMMENDATION_STALE_REVIEW_MESSAGE,
            )
            return False

        data = self.get_data()
        data["finished_at"] = finished_at
        payload = self.prepare_save_payload(data)

        try:
            updated = audit_service.update_audit(self.audit.id, **payload)
        except AuditCompletionError as exc:
            QMessageBox.warning(self, "Závěr", str(exc))
            self.tabs.setCurrentWidget(self.conclusion_widget)
            return False
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
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.processes_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()
        self.extraordinary_widget.refresh_findings_display()
        self._capture_baseline()
        return True
