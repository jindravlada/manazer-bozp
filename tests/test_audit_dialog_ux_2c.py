"""AUDIT-DIALOG-UX-2c: Zavřít/Neukládat nesmí zapsat zjištění, úkoly ani výsledky kontroly."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-dialog-ux-2c-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from core.widgets.control_result_selector import ControlResultSelectorWidget
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


_CONTEXT = ControlPointContext(
    area_id="p1",
    area_label="Proces A",
    section_id="c1",
    section_label="Kritérium A",
    control_point_id="q1",
    control_point_label="Otázka A",
)


def _read_finding_description(finding_id: int) -> str:
    with get_session() as session:
        row = session.get(Finding, finding_id)
        assert row is not None
        value = row.description or ""
        session.expunge(row)
        return value


def _read_control_note(audit_id: int) -> str:
    with get_session() as session:
        rows = (
            session.query(ControlResult)
            .filter_by(
                entity_type=ENTITY_AUDITY,
                entity_id=audit_id,
                source_control_point_id="q1",
            )
            .all()
        )
        assert rows
        value = rows[0].note or ""
        for row in rows:
            session.expunge(row)
        return value


def _read_task_title(task_id: int) -> str:
    with get_session() as session:
        row = session.get(Task, task_id)
        assert row is not None
        value = row.title or ""
        session.expunge(row)
        return value


class AuditDialogUx2cDeferredTextTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id

    def _create_audit(self) -> Audit:
        audit = audit_service.create_audit(
            title="UX-2c",
            audit_date=date(2026, 1, 1),
            silne_stranky="OK",
        )
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        return reloaded

    def _fill_commission(self, dialog: AuditDialog) -> None:
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)

    def _discard_close(self, dialog: AuditDialog) -> None:
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            dialog._request_close()

    def test_finding_description_discard_keeps_original(self) -> None:
        original = "PŮVODNÍ POPIS ZJIŠTĚNÍ"
        audit = self._create_audit()
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description=original,
            status=FINDING_STATUS_OTEVRENE,
        )

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        fake = SimpleNamespace(
            exec=lambda: True,
            get_data=lambda: {
                "finding_type": FINDING_TYPE_ZJISTENI,
                "reference_label": "",
                "description": "ZMĚNĚNÝ POPIS",
                "recommended_action": "",
                "responsible_person_id": None,
                "responsible_person_name": "",
                "due_date": None,
                "status": FINDING_STATUS_OTEVRENE,
                "resolution_note": "",
            },
        )
        with patch("moduly.audity.ui.audit_findings_widget.FindingDialog", return_value=fake):
            dialog.findings_widget.table.selectRow(0)
            dialog.findings_widget.edit_finding()

        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_finding_description(finding.id), original)

        with patch.object(finding_service, "update", wraps=finding_service.update) as spy:
            self._discard_close(dialog)
            spy.assert_not_called()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertEqual(_read_finding_description(finding.id), original)

    def test_finding_description_save_writes(self) -> None:
        audit = self._create_audit()
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="PŘED",
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.stage_finding_update(
            finding.id,
            {
                "finding_type": FINDING_TYPE_ZJISTENI,
                "reference_label": "",
                "description": "PO ULOŽENÍ",
                "recommended_action": "",
                "responsible_person_id": None,
                "responsible_person_name": "",
                "due_date": None,
                "status": FINDING_STATUS_OTEVRENE,
                "resolution_note": "",
            },
        )
        self.assertTrue(dialog._persist())
        self.assertEqual(_read_finding_description(finding.id), "PO ULOŽENÍ")

    def test_control_result_note_discard_keeps_original(self) -> None:
        original = "PŮVODNÍ POZNÁMKA KONTROLY"
        audit = self._create_audit()
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            _CONTEXT,
            result=CONTROL_RESULT_VYHOVUJE,
            note=original,
        )

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        selector = ControlResultSelectorWidget(
            auto_persist=False,
            deferred_edits=dialog._deferred,
        )
        selector.configure(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            context=_CONTEXT,
            must_be_saved_message="x",
        )
        selector._note_edit.setText("ZMĚNĚNÁ POZNÁMKA")
        selector._on_note_text_changed("ZMĚNĚNÁ POZNÁMKA")

        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_control_note(audit.id), original)

        with patch.object(
            control_result_service, "set_result", wraps=control_result_service.set_result
        ) as spy:
            self._discard_close(dialog)
            spy.assert_not_called()

        self.assertEqual(_read_control_note(audit.id), original)

    def test_control_result_note_save_writes(self) -> None:
        audit = self._create_audit()
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            _CONTEXT,
            result=CONTROL_RESULT_VYHOVUJE,
            note="PŘED",
        )
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.set_control_result(
            ENTITY_AUDITY,
            audit.id,
            _CONTEXT,
            result=CONTROL_RESULT_VYHOVUJE,
            note="PO ULOŽENÍ",
            shared_experience=False,
        )
        self.assertTrue(dialog._persist())
        self.assertEqual(_read_control_note(audit.id), "PO ULOŽENÍ")

    def test_task_title_discard_keeps_original(self) -> None:
        original = "PŮVODNÍ NÁZEV ÚKOLU"
        audit = self._create_audit()
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Zjištění pro úkol",
            recommended_action=original,
            status=FINDING_STATUS_OTEVRENE,
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        task_service.update_task(
            task_id=task.id,
            title=original,
            description=task.description or "",
            priority=task.priority or "Normální",
            due_date=task.due_date,
            remind_from=getattr(task, "remind_from", None),
            responsible_person_id=task.responsible_person_id,
            workplace_id=task.workplace_id,
            completed=bool(task.completed),
            completed_date=task.completed_date,
            requires_verification=bool(task.requires_verification),
            check_due_date=task.check_due_date,
            checked_date=task.checked_date,
            checked_by_id=task.checked_by_id,
            canceled=bool(task.canceled),
            note=task.note or "",
        )

        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()

        changed = {
            "title": "ZMĚNĚNÝ NÁZEV ÚKOLU",
            "description": "desc",
            "priority": "Normální",
            "due_date": None,
            "remind_from": None,
            "responsible_person_id": None,
            "workplace_id": None,
            "completed": False,
            "completed_date": None,
            "requires_verification": True,
            "check_due_date": None,
            "checked_date": None,
            "checked_by_id": None,
            "canceled": False,
            "note": "",
        }
        task_view = dialog._deferred.get_task(task.id)
        task_dialog = TaskDialog(
            dialog,
            task=task_view,
            persist_handler=lambda current, data: dialog._deferred.stage_task_update(
                int(current.id), data
            ),
        )
        with patch.object(task_dialog, "get_data", return_value=changed):
            self.assertTrue(task_dialog._persist())

        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_task_title(task.id), original)

        with patch.object(task_service, "update_task", wraps=task_service.update_task) as spy:
            self._discard_close(dialog)
            spy.assert_not_called()

        self.assertEqual(_read_task_title(task.id), original)

    def test_task_title_save_writes(self) -> None:
        audit = self._create_audit()
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Z",
            recommended_action="PŘED",
            status=FINDING_STATUS_OTEVRENE,
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog._capture_baseline()
        dialog._deferred.stage_task_update(
            task.id,
            {
                "title": "PO ULOŽENÍ",
                "description": task.description or "",
                "priority": task.priority or "Normální",
                "due_date": task.due_date,
                "remind_from": getattr(task, "remind_from", None),
                "responsible_person_id": task.responsible_person_id,
                "workplace_id": task.workplace_id,
                "completed": bool(task.completed),
                "completed_date": task.completed_date,
                "requires_verification": bool(task.requires_verification),
                "check_due_date": task.check_due_date,
                "checked_date": task.checked_date,
                "checked_by_id": task.checked_by_id,
                "canceled": bool(task.canceled),
                "note": task.note or "",
            },
        )
        self.assertTrue(dialog._persist())
        self.assertEqual(_read_task_title(task.id), "PO ULOŽENÍ")


if __name__ == "__main__":
    unittest.main()
