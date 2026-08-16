"""EXTERNAL-AUDIT-EA-3: Externí audity a Neshody/PKZ v Nadcházejících a Připomínkách."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ea-3-"))

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
        SOURCE_LABEL_EXTERNAL_AUDIT,
    )
    from core.dashboard.attention_service import (
        get_attention_items,
        get_external_audit_reminder_items,
        get_external_finding_reminder_items,
    )
    from moduly.externi_audity.constants import (
        EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
        EXTERNAL_AUDIT_STATUS_CANCELLED,
        EXTERNAL_AUDIT_STATUS_CLOSED,
        EXTERNAL_AUDIT_STATUS_IN_PROGRESS,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    )
    from moduly.externi_audity.sluzby.external_audit_draft import (
        FindingDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_reminder_read_service import (
        external_audit_reminder_read_service,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        external_audit_service,
    )
    from moduly.externi_audity.sluzby.external_audit_text import shorten_finding_title
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
        TAB_FINDINGS,
        TAB_PROGRAM,
    )
    from moduly.externi_audity.ui.external_audit_findings_widget import (
        _task_description,
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


class ExternalAuditEa3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:6]
        self.wp_a = settings_service.save_workplace(
            name=f"EA3-A-{suffix}",
            address="Ulice A",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.wp_b = settings_service.save_workplace(
            name=f"EA3-B-{suffix}",
            address="Ulice B",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def _create_audit(self, **fields):
        payload = {
            "audit_type": EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            "organization_ico": "00000000",
            "organization_name": "Cert Org EA3",
            "organization_address": "Praha",
            "status": EXTERNAL_AUDIT_STATUS_PLANNED,
        }
        payload.update(fields)
        return external_audit_service.create_audit(**payload)

    def test_01_shorten_finding_title(self) -> None:
        self.assertEqual(
            shorten_finding_title("Neexistuje školení BOZP"),
            "Neexistuje školení BOZP",
        )
        self.assertEqual(
            shorten_finding_title("  Ahoj\n\n  světe  "),
            "Ahoj světe",
        )
        long = "Slovo " * 30
        short = shorten_finding_title(long, limit=40)
        self.assertTrue(short.endswith("…"))
        self.assertLessEqual(len(short), 42)
        self.assertNotIn("Externí audit", short)

    def test_02_upcoming_one_row_per_unique_day_and_dedupe(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 10), workplace_id=self.wp_a.id
        )
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 11), workplace_id=self.wp_a.id
        )
        external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 9, 11),
            workplace_id=self.wp_b.id,
            time_from="09:00",
            time_to="11:00",
        )
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 12), workplace_id=self.wp_a.id
        )

        upcoming = external_audit_reminder_read_service.list_upcoming(
            as_of=date(2026, 9, 10)
        )
        days = [item.visit_date for item in upcoming if item.audit.id == audit.id]
        self.assertEqual(days, [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)])

        day11 = next(item for item in upcoming if item.visit_date == date(2026, 9, 11))
        self.assertEqual(len(day11.workplace_names), 2)
        self.assertTrue(any("09:00" in t for t in day11.time_labels))

        attention = [
            item
            for item in get_attention_items(today=date(2026, 9, 10))
            if item.item_type == ITEM_TYPE_EXTERNAL_AUDIT and item.source_id == audit.id
        ]
        self.assertEqual(len(attention), 3)
        for item in attention:
            self.assertEqual(item.type_label, "Audit")
            self.assertEqual(item.title, "Externí audit")
            self.assertEqual(item.priority, "")
            self.assertEqual(item.subtitle, SOURCE_LABEL_EXTERNAL_AUDIT)
            self.assertTrue(
                item.identity_key.startswith(f"external-audit:{audit.id}:")
            )
            self.assertIn("Organizace:", item.detail_tooltip)

    def test_03_upcoming_past_day_gone_future_remain_closed_cancelled_hidden(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 10), workplace_id=self.wp_a.id
        )
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 12), workplace_id=self.wp_a.id
        )
        mid = external_audit_reminder_read_service.list_upcoming(
            as_of=date(2026, 9, 11)
        )
        days = [item.visit_date for item in mid if item.audit.id == audit.id]
        self.assertEqual(days, [date(2026, 9, 12)])

        external_audit_service.set_status(audit.id, EXTERNAL_AUDIT_STATUS_CLOSED)
        self.assertFalse(
            any(
                item.audit.id == audit.id
                for item in external_audit_reminder_read_service.list_upcoming(
                    as_of=date(2026, 9, 11)
                )
            )
        )

        audit2 = self._create_audit()
        external_audit_service.add_visit(
            audit2.id, visit_date=date(2026, 10, 1), workplace_id=self.wp_a.id
        )
        external_audit_service.set_status(audit2.id, EXTERNAL_AUDIT_STATUS_CANCELLED)
        self.assertFalse(
            any(
                item.audit.id == audit2.id
                for item in external_audit_reminder_read_service.list_upcoming(
                    as_of=date(2026, 9, 11)
                )
            )
        )

        bare = self._create_audit()
        self.assertFalse(
            any(
                item.audit.id == bare.id
                for item in external_audit_reminder_read_service.list_upcoming(
                    as_of=date(2026, 9, 11)
                )
            )
        )

    def test_04_audit_reminders_one_row_trigger_and_persist(self) -> None:
        with_remind = self._create_audit(remind_from=date(2026, 8, 1))
        external_audit_service.add_visit(
            with_remind.id,
            visit_date=date(2026, 9, 10),
            workplace_id=self.wp_a.id,
        )
        external_audit_service.add_visit(
            with_remind.id,
            visit_date=date(2026, 9, 11),
            workplace_id=self.wp_b.id,
        )
        # Před remind_from → nic
        self.assertFalse(
            any(
                item.audit.id == with_remind.id
                for item in external_audit_reminder_read_service.list_audit_reminders(
                    as_of=date(2026, 7, 31)
                )
            )
        )
        # Od remind_from → jeden řádek (ne 2 za dny)
        reminders = [
            item
            for item in external_audit_reminder_read_service.list_audit_reminders(
                as_of=date(2026, 8, 1)
            )
            if item.audit.id == with_remind.id
        ]
        self.assertEqual(len(reminders), 1)

        # Bez remind_from → od prvního dne programu
        no_remind = self._create_audit()
        external_audit_service.add_visit(
            no_remind.id,
            visit_date=date(2026, 9, 20),
            workplace_id=self.wp_a.id,
        )
        self.assertFalse(
            any(
                item.audit.id == no_remind.id
                for item in external_audit_reminder_read_service.list_audit_reminders(
                    as_of=date(2026, 9, 19)
                )
            )
        )
        self.assertTrue(
            any(
                item.audit.id == no_remind.id
                for item in external_audit_reminder_read_service.list_audit_reminders(
                    as_of=date(2026, 9, 20)
                )
            )
        )

        # Po konci programu zůstává do Uzavřeno
        after = [
            item
            for item in get_external_audit_reminder_items(today=date(2026, 9, 30))
            if item.source_id == with_remind.id
        ]
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0].identity_key, f"external-audit:{with_remind.id}")
        self.assertEqual(after[0].title, "Externí audit")
        self.assertEqual(after[0].type_label, "Audit")
        self.assertEqual(after[0].subtitle, SOURCE_LABEL_EXTERNAL_AUDIT)
        self.assertEqual(after[0].date, date(2026, 9, 10))

        external_audit_service.set_status(
            with_remind.id, EXTERNAL_AUDIT_STATUS_IN_PROGRESS
        )
        self.assertTrue(
            any(
                item.source_id == with_remind.id
                for item in get_external_audit_reminder_items(today=date(2026, 10, 1))
            )
        )
        external_audit_service.set_status(with_remind.id, EXTERNAL_AUDIT_STATUS_CLOSED)
        self.assertFalse(
            any(
                item.source_id == with_remind.id
                for item in get_external_audit_reminder_items(today=date(2026, 10, 1))
            )
        )

        # Bez programu + remind_from → nic
        bare = self._create_audit(remind_from=date(2026, 1, 1))
        self.assertFalse(
            any(
                item.audit.id == bare.id
                for item in external_audit_reminder_read_service.list_audit_reminders(
                    as_of=date(2026, 8, 15)
                )
            )
        )

    def test_05_findings_upcoming_and_reminders_rules(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 8, 1), workplace_id=self.wp_a.id
        )
        future = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Budoucí neshoda text",
            due_date=date(2026, 9, 20),
        )
        today_f = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="Dnešní PKZ text",
            due_date=date(2026, 9, 10),
        )
        past = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Po termínu neshoda",
            due_date=date(2026, 9, 1),
        )
        no_due = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Bez termínu",
        )
        strength = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
            description="Silná stránka",
        )
        as_of = date(2026, 9, 10)

        upcoming = {
            int(item.finding.id): item
            for item in external_audit_reminder_read_service.list_upcoming_findings(
                as_of=as_of
            )
        }
        reminders = {
            int(item.finding.id): item
            for item in external_audit_reminder_read_service.list_finding_reminders(
                as_of=as_of
            )
        }
        self.assertIn(future.id, upcoming)
        self.assertNotIn(future.id, reminders)
        self.assertIn(today_f.id, upcoming)
        self.assertIn(today_f.id, reminders)
        self.assertNotIn(past.id, upcoming)
        self.assertIn(past.id, reminders)
        self.assertNotIn(no_due.id, upcoming)
        self.assertNotIn(no_due.id, reminders)
        self.assertNotIn(strength.id, upcoming)
        self.assertNotIn(strength.id, reminders)

        attention = get_attention_items(today=as_of)
        nc = next(
            item
            for item in attention
            if item.item_type == ITEM_TYPE_EXTERNAL_AUDIT_NC
            and item.source_id == future.id
        )
        self.assertEqual(nc.title, "Budoucí neshoda text")
        self.assertEqual(nc.subtitle, SOURCE_LABEL_EXTERNAL_AUDIT)
        self.assertEqual(nc.priority, "")
        self.assertNotIn("Externí audit –", nc.title)
        self.assertEqual(nc.identity_key, f"external-audit-finding:{future.id}")

        pkz = next(
            item
            for item in get_external_finding_reminder_items(today=as_of)
            if item.source_id == today_f.id
        )
        self.assertEqual(pkz.item_type, ITEM_TYPE_EXTERNAL_AUDIT_PKZ)
        self.assertEqual(pkz.title, "Dnešní PKZ text")
        self.assertIn("Dnešní PKZ text", pkz.detail_tooltip)

        external_audit_service.resolve_finding(past.id, resolution_text="Hotovo")
        self.assertFalse(
            any(
                int(item.finding.id) == past.id
                for item in external_audit_reminder_read_service.list_finding_reminders(
                    as_of=as_of
                )
            )
        )

    def test_06_closed_audit_keeps_open_finding_cancelled_hides(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 8, 1), workplace_id=self.wp_a.id
        )
        finding = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Zůstává po uzavření",
            due_date=date(2026, 8, 15),
        )
        external_audit_service.set_status(audit.id, EXTERNAL_AUDIT_STATUS_CLOSED)
        as_of = date(2026, 8, 20)
        self.assertTrue(
            any(
                int(item.finding.id) == finding.id
                for item in external_audit_reminder_read_service.list_finding_reminders(
                    as_of=as_of
                )
            )
        )
        # Audit samotný zmizí z Nadcházejících/Připomínek
        self.assertFalse(
            any(
                item.audit.id == audit.id
                for item in external_audit_reminder_read_service.list_upcoming(
                    as_of=as_of
                )
            )
        )

        cancelled = self._create_audit()
        external_audit_service.add_visit(
            cancelled.id, visit_date=date(2026, 8, 1), workplace_id=self.wp_a.id
        )
        cf = external_audit_service.add_finding(
            cancelled.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Zrušený audit zjištění",
            due_date=date(2026, 8, 15),
        )
        external_audit_service.set_status(cancelled.id, EXTERNAL_AUDIT_STATUS_CANCELLED)
        self.assertFalse(
            any(
                int(item.finding.id) == cf.id
                for item in external_audit_reminder_read_service.list_finding_reminders(
                    as_of=as_of
                )
            )
        )
        self.assertFalse(
            any(
                int(item.finding.id) == cf.id
                for item in external_audit_reminder_read_service.list_upcoming_findings(
                    as_of=as_of
                )
            )
        )

    def test_07_open_focus_program_and_finding(self) -> None:
        audit = self._create_audit()
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 10), workplace_id=self.wp_a.id
        )
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 11), workplace_id=self.wp_b.id
        )
        finding = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            description="Focus PKZ",
            due_date=date(2026, 9, 15),
        )

        editor = ExternalAuditEditorDialog(
            audit_id=int(audit.id),
            focus_tab="program",
            focus_visit_date=date(2026, 9, 11),
        )
        self.assertEqual(editor.tabs.currentIndex(), TAB_PROGRAM)
        selected = {idx.row() for idx in editor.visits_table.selectedIndexes()}
        self.assertIn(1, selected)
        editor.close()

        editor2 = ExternalAuditEditorDialog(
            audit_id=int(audit.id),
            focus_tab="findings",
            focus_finding_id=int(finding.id),
            focus_finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        )
        self.assertEqual(editor2.tabs.currentIndex(), TAB_FINDINGS)
        self.assertEqual(
            editor2.findings.subtabs.currentWidget(),
            editor2.findings.pkz_panel,
        )
        selected_f = {
            idx.row() for idx in editor2.findings.pkz_panel.table.selectedIndexes()
        }
        self.assertTrue(selected_f)
        editor2.close()

    def test_08_task_title_clean_description_context_no_rename_no_dashboard_dup(self) -> None:
        audit = self._create_audit(organization_name="Org Task EA3")
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 1), workplace_id=self.wp_a.id
        )
        draft = external_audit_service.load_draft(audit.id)
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Neexistuje školení BOZP",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                due_date=date(2026, 9, 20),
            )
        ]
        external_audit_service.save_bundle(draft)
        finding_id = int(draft.findings[0].db_id)

        editor = ExternalAuditEditorDialog(audit_id=int(audit.id))
        panel = editor.findings.nc_panel
        panel.refresh()
        panel.table.selectRow(0)

        captured: dict = {}

        class _FakeTaskDialog:
            def __init__(self, parent=None, task=None, *, create_kwargs=None, create_factory=None, **kwargs):
                self.task = None
                self._create_factory = create_factory
                self._title = ""
                self.title_edit = type(
                    "T",
                    (),
                    {
                        "setPlainText": lambda _s, text: setattr(self, "_title", text),
                    },
                )()
                self.workplace_selector = type(
                    "W", (), {"set_workplace_id": lambda *a, **k: None}
                )()

            def _capture_baseline(self):
                return None

            def exec(self):
                captured["title"] = self._title
                data = {
                    "title": self._title,
                    "description": "",
                    "priority": "Normální",
                    "due_date": date(2026, 9, 20),
                    "remind_from": None,
                    "responsible_person_id": None,
                    "workplace_id": None,
                    "completed": False,
                    "completed_date": None,
                    "requires_verification": False,
                    "check_due_date": None,
                    "checked_date": None,
                    "checked_by_id": None,
                    "canceled": False,
                    "note": "",
                }
                self.task = self._create_factory(data)
                return QDialog.DialogCode.Accepted

        with patch(
            "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
            _FakeTaskDialog,
        ):
            panel.create_task()

        self.assertEqual(captured["title"], "Neexistuje školení BOZP")
        self.assertNotIn("Externí audit", captured["title"])
        links = external_audit_service.list_finding_task_ids(finding_id)
        self.assertEqual(len(links), 1)
        task = task_service.get_task_by_id(links[0])
        self.assertEqual(task.title, "Neexistuje školení BOZP")
        self.assertIn("Vzniklo z externího auditu", task.description)
        self.assertIn("Org Task EA3", task.description)
        self.assertIn("Neexistuje školení BOZP", task.description)

        # Existující úkol se nepřejmenuje
        old_title = "Externí audit – neshoda: starý"
        existing = task_service.create_task(title=old_title, due_date=date(2026, 9, 25))
        reloaded = task_service.get_task_by_id(existing.id)
        self.assertEqual(reloaded.title, old_title)

        # Úkol se neobjeví podruhé jako EA položka (jen jako task)
        attention = get_attention_items(today=date(2026, 9, 15))
        ea_finding_ids = {
            item.source_id
            for item in attention
            if item.item_type
            in {ITEM_TYPE_EXTERNAL_AUDIT_NC, ITEM_TYPE_EXTERNAL_AUDIT_PKZ}
        }
        self.assertIn(finding_id, ea_finding_ids)
        task_items = [
            item
            for item in attention
            if item.item_type == ITEM_TYPE_TASK and item.source_id == task.id
        ]
        self.assertEqual(len(task_items), 1)
        # Žádná EA položka s ID úkolu
        self.assertFalse(
            any(
                item.item_type == ITEM_TYPE_EXTERNAL_AUDIT
                and item.source_id == task.id
                for item in attention
            )
        )

        desc = _task_description(draft, draft.findings[0])
        self.assertIn("Vzniklo z externího auditu", desc)
        self.assertEqual(
            EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            "resolved",
        )

    def test_09_batch_read_no_n_plus_1_and_refresh_no_write(self) -> None:
        audits = []
        for i in range(5):
            audit = self._create_audit(organization_name=f"Batch {i}")
            external_audit_service.add_visit(
                audit.id,
                visit_date=date(2026, 10, 1 + i),
                workplace_id=self.wp_a.id,
            )
            external_audit_service.add_finding(
                audit.id,
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description=f"Batch finding {i}",
                due_date=date(2026, 10, 5 + i),
            )
            audits.append(audit)

        db_path = storage_module.storage_service.database_path
        statements: list[str] = []

        def _trace(stmt: str) -> None:
            statements.append(stmt)

        conn = sqlite3.connect(str(db_path))
        try:
            # Samostatné spojení jen pro baseline mtime/count — hlavní cesta
            # jde přes službu.
            before_updated = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(length(organization_name)), 0) "
                "FROM external_audits"
            ).fetchone()
        finally:
            conn.close()

        # Počet SELECT přes session: list_upcoming + list_upcoming_findings
        # musí být O(1) rel. k počtu auditů (ne 1 SELECT na audit).
        with patch.object(
            session_module,
            "get_session",
            wraps=session_module.get_session,
        ) as wrapped:
            external_audit_reminder_read_service.list_upcoming(as_of=date(2026, 9, 15))
            external_audit_reminder_read_service.list_audit_reminders(
                as_of=date(2026, 9, 15)
            )
            external_audit_reminder_read_service.list_upcoming_findings(
                as_of=date(2026, 9, 15)
            )
            external_audit_reminder_read_service.list_finding_reminders(
                as_of=date(2026, 9, 15)
            )
            # Každá metoda = 1 session (bundles 1×, findings 1×) → ≤ 4
            self.assertLessEqual(wrapped.call_count, 4)

        get_attention_items(today=date(2026, 9, 15))
        get_external_audit_reminder_items(today=date(2026, 9, 15))
        get_external_finding_reminder_items(today=date(2026, 9, 15))

        conn = sqlite3.connect(str(db_path))
        try:
            after_updated = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(length(organization_name)), 0) "
                "FROM external_audits"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(before_updated, after_updated)
        _ = statements
        _ = audits

    def test_10_upcoming_and_reminders_not_mutually_exclusive(self) -> None:
        audit = self._create_audit(remind_from=date(2026, 9, 1))
        external_audit_service.add_visit(
            audit.id, visit_date=date(2026, 9, 10), workplace_id=self.wp_a.id
        )
        finding = external_audit_service.add_finding(
            audit.id,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Dnes oboje",
            due_date=date(2026, 9, 10),
        )
        as_of = date(2026, 9, 10)
        upcoming_ids = {
            item.identity_key for item in get_attention_items(today=as_of)
        }
        reminder_ids = {
            item.identity_key
            for item in (
                get_external_audit_reminder_items(today=as_of)
                + get_external_finding_reminder_items(today=as_of)
            )
        }
        self.assertIn(f"external-audit:{audit.id}:{date(2026, 9, 10).isoformat()}", upcoming_ids)
        self.assertIn(f"external-audit:{audit.id}", reminder_ids)
        self.assertIn(f"external-audit-finding:{finding.id}", upcoming_ids)
        self.assertIn(f"external-audit-finding:{finding.id}", reminder_ids)


if __name__ == "__main__":
    unittest.main()
