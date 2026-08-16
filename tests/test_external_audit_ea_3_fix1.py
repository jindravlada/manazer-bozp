"""EXTERNAL-AUDIT-EA-3-FIX1: Neshody/PKZ pouze v Připomínkách, ne v Nadcházejících."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ea-3-fix1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_EXTERNAL_AUDIT,
        ITEM_TYPE_EXTERNAL_AUDIT_NC,
        ITEM_TYPE_EXTERNAL_AUDIT_PKZ,
        ITEM_TYPE_TASK,
    )
    from core.dashboard.attention_service import (
        get_attention_items,
        get_external_audit_reminder_items,
        get_external_finding_reminder_items,
    )
    from moduly.externi_audity.constants import (
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_STATUS_CANCELLED,
        EXTERNAL_AUDIT_STATUS_CLOSED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    )
    from moduly.externi_audity.sluzby.external_audit_reminder_read_service import (
        external_audit_reminder_read_service,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        external_audit_service,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
        TAB_FINDINGS,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_FINDING_TYPES = frozenset(
    {ITEM_TYPE_EXTERNAL_AUDIT_NC, ITEM_TYPE_EXTERNAL_AUDIT_PKZ}
)


class ExternalAuditEa3Fix1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:6]
        self.wp = settings_service.save_workplace(
            name=f"EA3F1-{suffix}",
            address="Ulice",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def _create_audit(self, **fields):
        payload = {
            "audit_type": EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            "organization_ico": "00000000",
            "organization_name": "Cert Org FIX1",
            "organization_address": "Praha",
        }
        payload.update(fields)
        return external_audit_service.create_audit(**payload)

    def _finding_in_upcoming(self, finding_id: int, as_of: date) -> bool:
        return any(
            item.item_type in _FINDING_TYPES and item.source_id == finding_id
            for item in get_attention_items(today=as_of)
        )

    def _finding_in_reminders(self, finding_id: int, as_of: date) -> bool:
        return any(
            item.source_id == finding_id
            for item in get_external_finding_reminder_items(today=as_of)
        )

    def test_01_findings_never_in_upcoming_with_or_without_task(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 1), workplace_id=self.wp.id
        )
        future_nc = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Budoucí neshoda",
            due_date=date(2026, 9, 20),
        )
        today_nc = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Dnešní neshoda",
            due_date=date(2026, 9, 10),
        )
        future_pkz = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="Budoucí PKZ",
            due_date=date(2026, 9, 25),
        )
        today_pkz = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="Dnešní PKZ",
            due_date=date(2026, 9, 10),
        )
        as_of = date(2026, 9, 10)

        for finding_id in (
            future_nc.id,
            today_nc.id,
            future_pkz.id,
            today_pkz.id,
        ):
            self.assertFalse(self._finding_in_upcoming(int(finding_id), as_of))

        # Bez navázaného úkolu zůstávají mimo Nadcházející
        self.assertEqual(
            external_audit_service.list_finding_task_ids(int(today_nc.id)), []
        )
        self.assertFalse(self._finding_in_upcoming(int(today_nc.id), as_of))

        # Dnešní/prošlé zůstávají v Připomínkách
        self.assertTrue(self._finding_in_reminders(int(today_nc.id), as_of))
        self.assertTrue(self._finding_in_reminders(int(today_pkz.id), as_of))
        self.assertFalse(self._finding_in_reminders(int(future_nc.id), as_of))
        self.assertFalse(self._finding_in_reminders(int(future_pkz.id), as_of))

    def test_02_linked_task_stays_in_upcoming_via_agenda(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 1), workplace_id=self.wp.id
        )
        finding = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Neshoda s úkolem",
            due_date=date(2026, 9, 10),
        )
        task = task_service.create_task(
            title="Neshoda s úkolem",
            due_date=date(2026, 9, 18),
        )
        external_audit_service.link_task(int(finding.id), int(task.id))
        as_of = date(2026, 9, 10)

        self.assertFalse(self._finding_in_upcoming(int(finding.id), as_of))
        self.assertTrue(self._finding_in_reminders(int(finding.id), as_of))
        task_items = [
            item
            for item in get_attention_items(today=as_of)
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        self.assertEqual(len(task_items), 1)
        self.assertEqual(task_items[0].title, "Neshoda s úkolem")
        self.assertEqual(task_items[0].type_label, "Úkol")

    def test_03_resolved_cancelled_closed_rules(self) -> None:
        closed_audit = self._create_audit()
        external_audit_service.add_visit(
            closed_audit.id, visit_date=date(2026, 8, 1), workplace_id=self.wp.id
        )
        open_f = external_audit_service.add_finding(
            closed_audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Otevřená po uzavření",
            due_date=date(2026, 8, 15),
        )
        resolved = external_audit_service.add_finding(
            closed_audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="Vypořádaná",
            due_date=date(2026, 8, 10),
        )
        external_audit_service.resolve_finding(
            int(resolved.id), resolution_text="Hotovo"
        )
        external_audit_service.set_status(
            int(closed_audit.id), EXTERNAL_AUDIT_STATUS_CLOSED
        )

        cancelled = self._create_audit()
        external_audit_service.add_visit(
            cancelled.id, visit_date=date(2026, 8, 1), workplace_id=self.wp.id
        )
        cancelled_f = external_audit_service.add_finding(
            cancelled.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Zrušený",
            due_date=date(2026, 8, 15),
        )
        external_audit_service.set_status(
            int(cancelled.id), EXTERNAL_AUDIT_STATUS_CANCELLED
        )

        as_of = date(2026, 8, 20)
        self.assertTrue(self._finding_in_reminders(int(open_f.id), as_of))
        self.assertFalse(self._finding_in_reminders(int(resolved.id), as_of))
        self.assertFalse(self._finding_in_reminders(int(cancelled_f.id), as_of))
        for fid in (open_f.id, resolved.id, cancelled_f.id):
            self.assertFalse(self._finding_in_upcoming(int(fid), as_of))

    def test_04_audit_days_and_summary_reminder_unchanged(self) -> None:
        audit = self._create_audit(remind_from=date(2026, 9, 1))
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 10), workplace_id=self.wp.id
        )
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 11), workplace_id=self.wp.id
        )
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 11), workplace_id=self.wp.id
        )
        as_of = date(2026, 9, 10)
        days = [
            item.visit_date
            for item in external_audit_reminder_read_service.list_upcoming(as_of=as_of)
            if item.audit.id == audit.id
        ]
        self.assertEqual(days, [date(2026, 9, 10), date(2026, 9, 11)])
        upcoming_audits = [
            item
            for item in get_attention_items(today=as_of)
            if item.item_type == ITEM_TYPE_EXTERNAL_AUDIT and item.source_id == audit.id
        ]
        self.assertEqual(len(upcoming_audits), 2)
        reminders = [
            item
            for item in get_external_audit_reminder_items(today=as_of)
            if item.source_id == audit.id
        ]
        self.assertEqual(len(reminders), 1)

    def test_05_open_finding_from_reminder_focus(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 1), workplace_id=self.wp.id
        )
        finding = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="Focus z Připomínek",
            due_date=date(2026, 9, 5),
        )
        reminder = next(
            item
            for item in get_external_finding_reminder_items(today=date(2026, 9, 10))
            if item.source_id == finding.id
        )
        self.assertEqual(reminder.open_metadata.get("focus_tab"), "findings")
        self.assertEqual(reminder.open_metadata.get("audit_id"), int(audit.id))

        editor = ExternalAuditEditorDialog(
            audit_id=int(audit.id),
            focus_tab="findings",
            focus_finding_id=int(finding.id),
            focus_finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        )
        self.assertEqual(editor.tabs.currentIndex(), TAB_FINDINGS)
        self.assertEqual(
            editor.findings.subtabs.currentWidget(),
            editor.findings.pkz_panel,
        )
        self.assertTrue(editor.findings.pkz_panel.table.selectedIndexes())
        editor.close()

    def test_06_get_attention_does_not_call_finding_reminders_loader(self) -> None:
        """Nadcházející nenačítá findings — jen auditní dny."""
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 10, 1), workplace_id=self.wp.id
        )
        external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Nenačítat",
            due_date=date(2026, 10, 5),
        )
        with patch.object(
            external_audit_reminder_read_service,
            "list_finding_reminders",
            wraps=external_audit_reminder_read_service.list_finding_reminders,
        ) as wrapped_findings:
            with patch.object(
                external_audit_reminder_read_service,
                "list_upcoming",
                wraps=external_audit_reminder_read_service.list_upcoming,
            ) as wrapped_upcoming:
                items = get_attention_items(today=date(2026, 9, 15))
        wrapped_upcoming.assert_called()
        wrapped_findings.assert_not_called()
        self.assertFalse(any(item.item_type in _FINDING_TYPES for item in items))


if __name__ == "__main__":
    unittest.main()
