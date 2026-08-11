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

from core.widgets.editor_dialog_controller import (
    EDITOR_CLOSE_LABEL,
    EDITOR_SAVE_LABEL,
    configure_editor_close_button,
    configure_editor_save_button,
    confirm_unsaved_editor_close,
)
from moduly.proverky.constants import (
    TAB_KONTROLOVANE_OBLASTI,
    TAB_TEREN,
    VERIFICATION_TYPE_DOCUMENTATION,
)
from moduly.proverky.sluzby.bozp_inspection_commission_service import (
    bozp_inspection_commission_service,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.inspection_deferred_edits import InspectionDeferredEdits
from moduly.proverky.ui.bozp_inspection_areas_widget import BozpInspectionAreasWidget
from moduly.proverky.ui.bozp_inspection_commission_widget import BozpInspectionCommissionWidget
from moduly.proverky.ui.bozp_inspection_conclusion_widget import BozpInspectionConclusionWidget
from moduly.proverky.ui.bozp_inspection_findings_widget import BozpInspectionFindingsWidget
from moduly.proverky.ui.bozp_inspection_spis_widget import BozpInspectionSpisWidget
from moduly.proverky.ui.bozp_inspection_tasks_widget import BozpInspectionTasksWidget
from moduly.proverky.ui.bozp_inspection_terrain_widget import BozpInspectionTerrainWidget

_SAVE_CLOSE_LABEL = "Uložit a zavřít"


class BozpInspectionDialog(QDialog):
    """Dialog prověrky BOZP — stay-open ukládání + odložené změny (jako AuditDialog)."""

    def __init__(self, parent=None, inspection=None):
        super().__init__(parent)

        self.inspection = inspection
        self._baseline: object | None = None
        self._closing = False
        self._deferred = InspectionDeferredEdits()

        self.setWindowTitle("Prověrka BOZP")
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.spis_widget = BozpInspectionSpisWidget()
        self.commission_widget = BozpInspectionCommissionWidget()
        self.tabs.addTab(self.spis_widget, "Spis")
        self.tabs.addTab(self.commission_widget, "Komise")
        self.areas_widget = BozpInspectionAreasWidget(
            verification_type=VERIFICATION_TYPE_DOCUMENTATION
        )
        self.tabs.addTab(self.areas_widget, TAB_KONTROLOVANE_OBLASTI)
        self.terrain_widget = BozpInspectionTerrainWidget()
        self.tabs.addTab(self.terrain_widget, TAB_TEREN)
        self.findings_widget = BozpInspectionFindingsWidget()
        self.tabs.addTab(self.findings_widget, "Zjištění")
        self.tasks_widget = BozpInspectionTasksWidget()
        self.tabs.addTab(self.tasks_widget, "Úkoly")
        self.conclusion_widget = BozpInspectionConclusionWidget()
        self.tabs.addTab(self.conclusion_widget, "Závěr")
        layout.addWidget(self.tabs)
        layout.addLayout(self._build_footer())

        inspection_id = inspection.id if inspection is not None else None
        self._wire_deferred_edits()
        self.set_inspection_id(inspection_id)
        self.areas_widget.set_on_finding_saved(self._on_finding_changed)
        self.terrain_widget.set_on_finding_saved(self._on_finding_changed)
        self.areas_widget.set_on_verification_type_changed(self._on_verification_type_changed)
        self.terrain_widget.set_on_verification_type_changed(self._on_verification_type_changed)
        self.areas_widget.set_on_knowledge_changed(self._on_knowledge_changed)
        self.terrain_widget.set_on_knowledge_changed(self._on_knowledge_changed)
        self.findings_widget.set_on_task_changed(self._on_related_data_changed)
        self.conclusion_widget.set_complete_handler(self._complete_inspection)
        self.spis_widget.load_inspection(inspection)
        self.conclusion_widget.load_inspection(inspection)
        self.commission_widget.set_inspection_context(inspection_id)
        self._capture_baseline()

    def _wire_deferred_edits(self) -> None:
        self.areas_widget.set_deferred_edits(self._deferred)
        self.terrain_widget.set_deferred_edits(self._deferred)
        self.findings_widget.set_deferred_edits(self._deferred)
        self.tasks_widget.set_deferred_edits(self._deferred)
        self.areas_widget.set_on_deferred_dirty(self._on_deferred_dirty)
        self.terrain_widget.set_on_deferred_dirty(self._on_deferred_dirty)

    def _on_deferred_dirty(self) -> None:
        """Hook pro budoucí indikátor neuložených změn; dirty detekce jde přes _deferred."""
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

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self.areas_widget.set_inspection_id(inspection_id)
        self.terrain_widget.set_inspection_id(inspection_id)
        self.findings_widget.set_inspection_id(inspection_id)
        self.tasks_widget.set_inspection_id(inspection_id)

    def _on_finding_changed(self) -> None:
        self._on_related_data_changed()
        self.areas_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()

    def _on_verification_type_changed(self) -> None:
        self.areas_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()

    def _on_knowledge_changed(self) -> None:
        self.areas_widget.reload_knowledge()
        self.terrain_widget.reload_knowledge()

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
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Komise", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        payload = self._prepare_save_payload(data)

        if self.inspection is None:
            created = bozp_inspection_service.create_inspection(**payload)
            if created is None:
                return False
            self.inspection = created
            self._save_commission_members(created.id, data)
            self._deferred.flush()
            self._reload_after_persist()
        else:
            updated = bozp_inspection_service.update_inspection(self.inspection.id, **payload)
            if updated is None:
                return False
            self._save_commission_members(self.inspection.id, data)
            self._deferred.flush()
            self.inspection = updated
            self._reload_after_persist()

        self._capture_baseline()
        return True

    def _reload_after_persist(self) -> None:
        assert self.inspection is not None
        self.set_inspection_id(self.inspection.id)
        self.spis_widget.load_inspection(self.inspection)
        self.conclusion_widget.load_inspection(self.inspection)
        self.commission_widget.set_inspection_context(self.inspection.id)
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.areas_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()

    def _done_accept(self) -> None:
        self._closing = True
        QDialog.accept(self)

    def _done_reject(self) -> None:
        self._closing = True
        QDialog.reject(self)

    def accept(self) -> None:
        if self._closing:
            QDialog.accept(self)
            return
        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Komise", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return
        self._done_accept()

    def _request_close(self) -> None:
        if self._confirm_close():
            self._done_reject()

    def _confirm_close(self) -> bool:
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
        self._deferred.clear()
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
        data["title"] = ""
        data["commission_members"] = self.commission_widget.get_members_for_save()
        return data

    def _prepare_save_payload(self, data: dict) -> dict:
        payload = {key: value for key, value in data.items() if key != "commission_members"}

        workplace_id = payload.get("workplace_id")
        if workplace_id is None:
            workplace_id = bozp_inspection_service.resolve_workplace_id_by_name(
                payload.get("workplace_name", "")
            )
            payload["workplace_id"] = workplace_id
        payload["workplace_name"] = bozp_inspection_service.resolve_workplace_name(workplace_id)
        payload["title"] = ""
        return payload

    def _save_commission_members(self, inspection_id: int, data: dict) -> None:
        members = data.get("commission_members")
        if members is None:
            return
        bozp_inspection_commission_service.save_members(inspection_id, members)

    def _complete_inspection(self, *, finished_at) -> bool:
        if self.inspection is None:
            return False

        valid, message = self.commission_widget.validate()
        if not valid:
            QMessageBox.warning(self, "Komise", message)
            self.tabs.setCurrentWidget(self.commission_widget)
            return False

        data = self.get_data()
        data["finished_at"] = finished_at
        payload = self._prepare_save_payload(data)

        updated = bozp_inspection_service.update_inspection(self.inspection.id, **payload)
        if updated is None:
            return False

        bozp_inspection_commission_service.save_members(
            self.inspection.id,
            data.get("commission_members", []),
        )
        self._deferred.flush()

        self.inspection = updated
        self.conclusion_widget.load_inspection(self.inspection)
        self.spis_widget.load_inspection(self.inspection)
        self.findings_widget.refresh()
        self.tasks_widget.refresh()
        self.areas_widget.refresh_findings_display()
        self.terrain_widget.refresh_findings_display()
        self._capture_baseline()
        return True
