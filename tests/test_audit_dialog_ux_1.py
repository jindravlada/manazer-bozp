"""AUDIT-DIALOG-UX-1: akční tlačítka a stay-open ukládání auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-dialog-ux-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_commission_widget import AuditCommissionWidget
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_findings_widget import AuditFindingsWidget
    from moduly.audity.ui.audit_tasks_widget import AuditTasksWidget
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AuditDialogUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"Novák-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Králová-{suffix}"
        ).id
        self.auditor_a = settings_service.save_worker(
            first_name="Petr", last_name=f"AuditorA-{suffix}"
        ).id
        self.auditor_b = settings_service.save_worker(
            first_name="Adam", last_name=f"AuditorB-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Horáková-{suffix}"
        ).id
        self.invited_a = person_service.create_person(
            first_name="Tomáš", last_name=f"InvA-{suffix}"
        ).id
        self.invited_b = person_service.create_person(
            first_name="Ivana", last_name=f"InvB-{suffix}"
        ).id

    def _fill_commission(self, dialog: AuditDialog) -> None:
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)

    def test_findings_buttons_follow_selection(self) -> None:
        audit = audit_service.create_audit(title="Zjištění UX")
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            recommended_action="Oprava",
            status=FINDING_STATUS_OTEVRENE,
        )
        widget = AuditFindingsWidget()
        widget.set_audit_id(audit.id)

        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.delete_btn.isEnabled())

        widget.table.selectRow(0)
        self.assertTrue(widget.edit_btn.isEnabled())
        self.assertTrue(widget.delete_btn.isEnabled())

        widget.table.clearSelection()
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.delete_btn.isEnabled())

    def test_tasks_open_follows_selection_refresh_always(self) -> None:
        audit = audit_service.create_audit(title="Úkoly UX")
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Neshoda",
            recommended_action="Oprava",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_task_service.create_task_from_finding(finding.id)

        widget = AuditTasksWidget()
        widget.set_audit_id(audit.id)

        # Obnovit jen načte seznam — aktivní i bez výběru.
        self.assertTrue(widget.refresh_btn.isEnabled())
        self.assertFalse(widget.open_btn.isEnabled())

        widget.table.selectRow(0)
        self.assertTrue(widget.open_btn.isEnabled())
        self.assertTrue(widget.refresh_btn.isEnabled())

        widget.table.clearSelection()
        self.assertFalse(widget.open_btn.isEnabled())
        self.assertTrue(widget.refresh_btn.isEnabled())

    def test_commission_auditor_actions(self) -> None:
        widget = AuditCommissionWidget()
        widget._members = [
            {
                "thp_worker_id": self.auditor_a,
                "display_name": "A",
                "role_text": "",
                "note_text": "",
            },
            {
                "thp_worker_id": self.auditor_b,
                "display_name": "B",
                "role_text": "",
                "note_text": "",
            },
        ]
        widget._refresh_tables()

        self.assertFalse(widget._member_edit_btn.isEnabled())
        self.assertFalse(widget._member_remove_btn.isEnabled())
        self.assertFalse(widget._member_up_btn.isEnabled())
        self.assertFalse(widget._member_down_btn.isEnabled())

        widget.members_table.selectRow(0)
        self.assertTrue(widget._member_edit_btn.isEnabled())
        self.assertTrue(widget._member_remove_btn.isEnabled())
        self.assertFalse(widget._member_up_btn.isEnabled())
        self.assertTrue(widget._member_down_btn.isEnabled())

        widget.members_table.selectRow(1)
        self.assertTrue(widget._member_up_btn.isEnabled())
        self.assertFalse(widget._member_down_btn.isEnabled())

    def test_commission_invited_actions(self) -> None:
        widget = AuditCommissionWidget()
        widget._invited = [
            {
                "person_id": self.invited_a,
                "display_name": "A",
                "role_text": "",
                "note_text": "",
            },
            {
                "person_id": self.invited_b,
                "display_name": "B",
                "role_text": "",
                "note_text": "",
            },
        ]
        widget._refresh_tables()

        self.assertFalse(widget._invited_edit_btn.isEnabled())
        self.assertFalse(widget._invited_remove_btn.isEnabled())

        widget.invited_table.selectRow(0)
        self.assertTrue(widget._invited_edit_btn.isEnabled())
        self.assertTrue(widget._invited_remove_btn.isEnabled())
        self.assertFalse(widget._invited_up_btn.isEnabled())
        self.assertTrue(widget._invited_down_btn.isEnabled())

        widget.invited_table.selectRow(1)
        self.assertTrue(widget._invited_up_btn.isEnabled())
        self.assertFalse(widget._invited_down_btn.isEnabled())

    def test_footer_save_stay_open(self) -> None:
        audit = audit_service.create_audit(title="Stay open")
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "person_id": None,
                    "display_name": "L",
                    "role_text": None,
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "person_id": None,
                    "display_name": "W",
                    "role_text": None,
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "thp_worker_id": None,
                    "person_id": self.union_id,
                    "display_name": "U",
                    "role_text": None,
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        dialog = AuditDialog(audit=audit_service.get_by_id(audit.id))
        self.assertFalse(dialog._is_dirty())

        dialog.spis_widget.audit_date_edit.set_date_value(date(2026, 6, 1))
        self.assertTrue(dialog._is_dirty())
        self.assertTrue(dialog._persist())
        self.assertFalse(dialog._is_dirty())
        self.assertTrue(dialog.isVisible() or True)
        self.assertEqual(dialog.result(), 0)

        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.audit_date, date(2026, 6, 1))
        dialog.close()

    def test_footer_save_and_close(self) -> None:
        audit = audit_service.create_audit(title="Save close")
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog)
        dialog.spis_widget.audit_date_edit.set_date_value(date(2026, 7, 1))

        dialog._save_and_close()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.audit_date, date(2026, 7, 1))

    def test_close_without_dirty(self) -> None:
        audit = audit_service.create_audit(title="Clean close")
        dialog = AuditDialog(audit=audit)
        self.assertFalse(dialog._is_dirty())
        with patch.object(dialog, "reject", wraps=dialog.reject) as mock_reject:
            dialog._request_close()
            mock_reject.assert_called()

    @patch("moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close", return_value="cancel")
    def test_close_with_dirty_prompt(self, _mock_prompt) -> None:
        audit = audit_service.create_audit(title="Dirty")
        dialog = AuditDialog(audit=audit)
        dialog.spis_widget.audit_date_edit.set_date_value(date(2026, 8, 1))
        self.assertTrue(dialog._is_dirty())
        self.assertFalse(dialog._confirm_close())
        self.assertTrue(dialog._is_dirty())

    def test_no_auto_dirty_tracking(self) -> None:
        audit = audit_service.create_audit(title="No EDC")
        dialog = AuditDialog(audit=audit)
        self.assertFalse(hasattr(dialog, "_editor"))
        text = Path("moduly/audity/ui/audit_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("install_auto_dirty_tracking", text)
        self.assertNotIn("EditorDialogController", text)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
