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
    AUDIT_COMPLETION_REQUIRES_PREPARATION_MESSAGE,
    AUDIT_COMPLETION_REQUIRES_START_DATE_MESSAGE,
    AUDIT_EXECUTION_REQUIRES_PREPARATION_MESSAGE,
    AUDIT_EXECUTION_REQUIRES_SAVE_THEN_PREPARE_MESSAGE,
    AUDIT_LEAD_RECOMMENDATION_EMPTY_REVIEW_MESSAGE,
    AUDIT_LEAD_RECOMMENDATION_STALE_REVIEW_MESSAGE,
    AUDIT_PREPARE_BUTTON,
    AUDIT_PREPARE_CONFIRM_MESSAGE,
    AUDIT_SCOPE_REQUIRED_MESSAGE,
    AUDIT_START_DATE_REQUIRED_MESSAGE,
    FINDING_SOURCE_LABEL,
    TAB_LABELS,
    TAB_MIMORADNE,
)
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    AUDITABLE_WORKPLACE_REQUIRED_MESSAGE,
)
from moduly.audity.sluzby.audit_commission_service import audit_commission_service
from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits
from moduly.audity.sluzby.audit_program_service import (
    AuditVisitContext,
    audit_program_service,
)
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
        if audit is None and visit_context is not None:
            self.spis_widget.apply_visit_context(visit_context)
        # Úvod: jen kontext + text changes_since_last; historie lazy při otevření záložky.
        self.history_widget.load_audit(audit)
        self.history_widget.content_modified.connect(self._on_deferred_dirty)
        self.conclusion_widget.load_audit(audit)
        self.commission_widget.set_audit_context(audit_id)
        self._apply_scope_mode()
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

        self.spis_widget.prepare_button.clicked.connect(self._prepare_audit)
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
        from moduly.audity.sluzby.audit_v2_create_service import is_planned_unfrozen

        if self.audit is not None and is_planned_unfrozen(self.audit):
            self.processes_widget.show_unprepared_state()
            self.terrain_widget.show_unprepared_state()
            self.extraordinary_widget.show_unprepared_state()
            return
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

    def _is_visit_draft(self) -> bool:
        return self.audit is None and self._visit_context is not None

    def _validate_visit_draft(self, data: dict) -> str | None:
        workplace_id = data.get("workplace_id")
        if workplace_id is None:
            workplace_id = audit_service.resolve_workplace_id_by_name(
                data.get("workplace_name", "")
            )
        if workplace_id is None or int(workplace_id) <= 0:
            return AUDITABLE_WORKPLACE_REQUIRED_MESSAGE
        return None

    def _audit_is_prepared(self) -> bool:
        from moduly.audity.sluzby.audit_v2_create_service import is_planned_unfrozen

        audit = self.audit
        if audit is None or is_planned_unfrozen(audit):
            return False
        return getattr(audit, "questions_frozen_at", None) is not None

    def _form_has_execution(self, data: dict) -> bool:
        if not audit_service.is_conclusion_blank(data.get("conclusion_text")):
            return True
        if not is_recommendation_blank(data.get("lead_auditor_recommendation")):
            return True
        if str(data.get("silne_stranky") or "").strip():
            return True
        return False

    def _execution_block_message(self, data: dict) -> str | None:
        if not self._deferred.has_execution_changes() and not self._form_has_execution(data):
            return None
        if self.audit is None:
            return AUDIT_EXECUTION_REQUIRES_SAVE_THEN_PREPARE_MESSAGE
        if not self._audit_is_prepared():
            return AUDIT_EXECUTION_REQUIRES_PREPARATION_MESSAGE
        if data.get("started_at") is None:
            return AUDIT_START_DATE_REQUIRED_MESSAGE
        return None

    def _apply_scope_mode(self) -> None:
        audit = self.audit
        if self._visit_context is not None or (
            audit is not None and getattr(audit, "program_visit_id", None)
        ):
            self.spis_widget.hide_audit_scope()
            return

        from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
        from moduly.audity.sluzby.audit_scope_service import (
            list_audit_scope_processes,
            snapshot_scope_labels,
        )
        from moduly.audity.sluzby.audit_v2_create_service import is_planned_unfrozen

        editable = audit is None or (
            getattr(audit, "id", None)
            and is_planned_unfrozen(audit)
            and getattr(audit, "questions_frozen_at", None) is None
        )
        if editable:
            catalog = [
                (process.id, process.nazev)
                for process in audit_knowledge_service.get_processes(ensure=True)
            ]
            known = {process_id for process_id, _name in catalog}
            selected: set[str] = set()
            if audit is not None and getattr(audit, "id", None):
                for row in list_audit_scope_processes(int(audit.id)):
                    selected.add(row.process_id)
                    if row.process_id not in known:
                        catalog.append(
                            (row.process_id, row.process_name or row.process_id)
                        )
                        known.add(row.process_id)
            self.spis_widget.show_editable_scope(catalog, selected)
            return
        if audit is not None and getattr(audit, "id", None):
            self.spis_widget.show_readonly_scope(snapshot_scope_labels(int(audit.id)))
            return
        self.spis_widget.hide_audit_scope()

    def _manual_scope_is_editable(self) -> bool:
        audit = self.audit
        if self._visit_context is not None:
            return False
        if audit is not None and getattr(audit, "program_visit_id", None):
            return False
        return self.spis_widget.scope_group.isVisible() and self.spis_widget._scope_editable

    def _prepare_audit(self) -> None:
        if self.audit is None or not getattr(self.audit, "id", None):
            return
        if self._manual_scope_is_editable():
            chosen = self.spis_widget.selected_scope()
            if not chosen:
                QMessageBox.warning(
                    self,
                    AUDIT_PREPARE_BUTTON,
                    AUDIT_SCOPE_REQUIRED_MESSAGE,
                )
                return
            from moduly.audity.sluzby.audit_scope_service import (
                replace_audit_scope_processes,
            )

            try:
                replace_audit_scope_processes(int(self.audit.id), chosen)
            except Exception as exc:
                QMessageBox.warning(self, AUDIT_PREPARE_BUTTON, str(exc))
                return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(AUDIT_PREPARE_BUTTON)
        box.setText(AUDIT_PREPARE_CONFIRM_MESSAGE)
        yes_btn = box.addButton("Ano", QMessageBox.ButtonRole.YesRole)
        box.addButton("Ne", QMessageBox.ButtonRole.NoRole)
        box.exec()
        if box.clickedButton() is not yes_btn:
            return
        try:
            prepared = audit_program_service.prepare_audit_from_visit(int(self.audit.id))
        except (
            AuditV2CreateError,
            SystemAuditWorkplaceError,
            AuditExtraordinaryError,
            ValueError,
        ) as exc:
            QMessageBox.warning(self, AUDIT_PREPARE_BUTTON, str(exc))
            return
        self.audit = prepared
        self.spis_widget.load_audit(prepared)
        self.conclusion_widget.load_audit(prepared)
        self.set_audit_id(prepared.id)
        self._capture_baseline()

    def _persist(self) -> bool:
        """Zápis Spis/Závěr/komise + odložených zjištění/úkolů/výsledků kontroly."""
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Auditní tým", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        if self._is_visit_draft():
            visit_error = self._validate_visit_draft(data)
            if visit_error is not None:
                QMessageBox.warning(self, "Nový audit", visit_error)
                self.tabs.setCurrentWidget(self.spis_widget)
                return False

        self.processes_widget.capture_section_summary()
        self.terrain_widget.capture_section_summary()

        execution_error = self._execution_block_message(data)
        if execution_error is not None:
            QMessageBox.warning(self, FINDING_SOURCE_LABEL, execution_error)
            return False

        if self.audit is None:
            payload = self.prepare_save_payload(data)
            try:
                if self._visit_context is not None:
                    created = audit_program_service.create_audit_from_visit(
                        self._visit_context.visit_id,
                        started_at=data["started_at"],
                        fields=payload,
                        commission_members=data.get("commission_members"),
                    )
                else:
                    created = create_manual_audit_with_v2_snapshot(
                        fields=payload,
                        commission_members=data.get("commission_members"),
                        scope_processes=self.spis_widget.selected_scope(),
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
            except ValueError as exc:
                QMessageBox.warning(self, "Audit", str(exc))
                self.tabs.setCurrentWidget(self.spis_widget)
                return False
            if updated is None:
                return False
            self.save_commission_members(self.audit.id, data)
            if (
                not getattr(updated, "program_visit_id", None)
                and self.spis_widget._scope_editable
            ):
                from moduly.audity.sluzby.audit_scope_service import (
                    replace_audit_scope_processes,
                )

                try:
                    replace_audit_scope_processes(
                        int(updated.id),
                        self.spis_widget.selected_scope(),
                    )
                except Exception as exc:
                    QMessageBox.warning(self, "Nový audit", str(exc))
                    return False
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
        self._apply_scope_mode()

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
        data["scope_processes"] = self.spis_widget.selected_scope()
        return data

    def prepare_save_payload(self, data: dict) -> dict:
        payload = {
            key: value
            for key, value in data.items()
            if key not in {"commission_members", "scope_processes"}
        }

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

        data_for_gate = self.get_data()
        if not self._audit_is_prepared():
            QMessageBox.warning(self, "Závěr", AUDIT_COMPLETION_REQUIRES_PREPARATION_MESSAGE)
            self.tabs.setCurrentWidget(self.spis_widget)
            return False
        if data_for_gate.get("started_at") is None:
            QMessageBox.warning(self, "Závěr", AUDIT_COMPLETION_REQUIRES_START_DATE_MESSAGE)
            self.tabs.setCurrentWidget(self.spis_widget)
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
