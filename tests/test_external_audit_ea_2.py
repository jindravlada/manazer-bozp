"""EXTERNAL-AUDIT-EA-2: zjištění, vypořádání, úkoly, přehledové agregace."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ea-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.externi_audity.constants import (
        EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
        EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
        EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
        EXTERNAL_AUDIT_STATUS_CLOSED,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
        format_display_date,
    )
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        FindingDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        ExternalAuditError,
        external_audit_service,
        normalize_finding_draft_fields,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
        TAB_ATTACHMENTS,
        TAB_FINDINGS,
        TAB_PARTICIPANTS,
        TAB_PROGRAM,
        TAB_SPIS,
    )
    from moduly.externi_audity.ui.external_audit_findings_widget import FILTER_ALL
    from moduly.externi_audity.ui.external_audits_overview_dialog import (
        COL_NC,
        COL_PKZ,
        COL_STRENGTH,
        COL_TASKS,
        ExternalAuditsOverviewDialog,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ExternalAuditEa2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def _base_draft(self, **kwargs) -> ExternalAuditDraft:
        data = {
            "audit_id": None,
            "audit_type": EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            "status": EXTERNAL_AUDIT_STATUS_PLANNED,
            "organization_ico": "12345678",
            "organization_name": "Test Org EA2",
            "organization_address": "Ulice 1",
        }
        data.update(kwargs)
        return ExternalAuditDraft(**data)

    def test_01_editor_findings_tab_order_and_subtabs(self) -> None:
        editor = ExternalAuditEditorDialog()
        self.assertEqual(editor.tabs.tabText(TAB_SPIS), "Spis")
        self.assertEqual(editor.tabs.tabText(TAB_PROGRAM), "Program")
        self.assertEqual(editor.tabs.tabText(TAB_PARTICIPANTS), "Účastníci")
        self.assertEqual(editor.tabs.tabText(TAB_FINDINGS), "Zjištění")
        self.assertEqual(editor.tabs.tabText(TAB_ATTACHMENTS), "Přílohy")
        self.assertEqual(
            [editor.findings.subtabs.tabText(i) for i in range(3)],
            ["Neshody", "PKZ", "Silné stránky"],
        )
        self.assertEqual(
            editor.findings.nc_panel.status_filter.currentData(), FILTER_ALL
        )
        self.assertEqual(
            editor.findings.pkz_panel.status_filter.currentData(), FILTER_ALL
        )
        self.assertIsNone(editor.findings.strength_panel.status_filter)

    def test_02_draft_findings_discard_on_close_without_save(self) -> None:
        editor = ExternalAuditEditorDialog()
        editor.ico.setText("87654321")
        editor.organization_name.setText("Draft Org")
        editor._draft.findings.append(
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Dočasná neshoda",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        )
        self.assertTrue(editor._is_dirty())
        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            editor._request_close()
        # Po discard se dialog zavře bez zápisu — DB bez auditu s tímto IČ
        rows = [
            row
            for row in external_audit_service.list_overview_rows()
            if row.organization_ico == "87654321"
        ]
        self.assertEqual(rows, [])

    def test_03_atomic_save_bundle_findings_and_ids(self) -> None:
        draft = self._base_draft()
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="NC 1",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                due_date=date(2026, 9, 1),
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
                description="PKZ 1",
                status=EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
                description="Síla 1",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
            ),
        ]
        saved = external_audit_service.save_bundle(draft)
        self.assertIsNotNone(saved.id)
        self.assertTrue(all(item.db_id for item in draft.findings))
        loaded = external_audit_service.load_draft(int(saved.id))
        self.assertEqual(len(loaded.findings), 3)
        by_type = {item.finding_type: item for item in loaded.findings}
        self.assertEqual(
            by_type[EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY].description, "NC 1"
        )
        self.assertEqual(
            by_type[EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH].status,
            EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
        )

    def test_04_normalize_validation_rules(self) -> None:
        with self.assertRaises(ExternalAuditError):
            normalize_finding_draft_fields(
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="  ",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                due_date=None,
                resolution_text=None,
            )
        with self.assertRaises(ExternalAuditError):
            normalize_finding_draft_fields(
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Text",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
                due_date=None,
                resolution_text="",
            )
        with self.assertRaises(ExternalAuditError):
            normalize_finding_draft_fields(
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
                description="Síla",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
                due_date=date(2026, 1, 1),
                resolution_text=None,
            )
        with self.assertRaises(ExternalAuditError):
            normalize_finding_draft_fields(
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
                description="Síla",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                due_date=None,
                resolution_text="x",
            )
        strength = normalize_finding_draft_fields(
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
            description="Síla OK",
            status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            due_date=None,
            resolution_text=None,
        )
        self.assertEqual(strength["status"], EXTERNAL_AUDIT_FINDING_STATUS_RECORDED)
        self.assertIsNone(strength["due_date"])
        self.assertIsNone(strength["resolution_text"])

        resolved = normalize_finding_draft_fields(
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="NC",
            status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            due_date=None,
            resolution_text="Hotovo",
            previous_status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        )
        self.assertEqual(resolved["status"], EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED)
        self.assertIsNotNone(resolved["resolved_at"])
        stamp = resolved["resolved_at"]

        same = normalize_finding_draft_fields(
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="NC",
            status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            due_date=None,
            resolution_text="Hotovo",
            previous_status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            previous_resolved_at=stamp,
        )
        self.assertEqual(same["resolved_at"], stamp)

        reopened = normalize_finding_draft_fields(
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="NC",
            status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            due_date=None,
            resolution_text="Hotovo",
            previous_status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            previous_resolved_at=stamp,
        )
        self.assertIsNone(reopened["resolved_at"])
        self.assertEqual(reopened["resolution_text"], "Hotovo")

    def test_05_resolved_visible_default_filter_all(self) -> None:
        draft = self._base_draft(
            organization_ico=f"11{uuid.uuid4().hex[:6]}",
            organization_name="Filter Org",
        )
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Otevřená",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Vypořádaná",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
                resolution_text="OK",
                resolved_at=datetime.now(),
            ),
        ]
        saved = external_audit_service.save_bundle(draft)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        panel = editor.findings.nc_panel
        self.assertEqual(panel.status_filter.currentData(), FILTER_ALL)
        panel.refresh()
        self.assertEqual(panel.table.rowCount(), 2)
        self.assertIn("Zobrazeno: 2 / 2", panel.count_label.text())
        panel.status_filter.setCurrentIndex(
            panel.status_filter.findData(EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED)
        )
        self.assertEqual(panel.table.rowCount(), 1)

    def test_06_task_link_multi_and_duplicate_and_statuses(self) -> None:
        draft = self._base_draft(
            organization_ico=f"22{uuid.uuid4().hex[:6]}",
            organization_name="Task Org",
        )
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="NC s úkoly",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
                description="Bez úkolu",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
            ),
        ]
        saved = external_audit_service.save_bundle(draft)
        finding_id = draft.findings[0].db_id
        strength_id = draft.findings[1].db_id
        assert finding_id and strength_id

        t1 = task_service.create_task(title=f"EA2-A-{uuid.uuid4().hex[:4]}")
        t2 = task_service.create_task(title=f"EA2-B-{uuid.uuid4().hex[:4]}")
        external_audit_service.link_task(finding_id, t1.id)
        external_audit_service.link_task(finding_id, t2.id)
        with self.assertRaises(ExternalAuditError):
            external_audit_service.link_task(finding_id, t1.id)
        with self.assertRaises(ExternalAuditError):
            external_audit_service.link_task(strength_id, t1.id)

        task_service.update_task(t1.id, title=t1.title, completed=True)
        task_service.update_task(t2.id, title=t2.title, canceled=True)

        by_finding = external_audit_service.list_tasks_for_findings([finding_id])
        tasks = by_finding[finding_id]
        self.assertEqual({int(task.id) for task in tasks}, {t1.id, t2.id})
        statuses = {int(task.id): task.computed_status for task in tasks}
        self.assertEqual(statuses[t1.id], "Ukončeno")
        self.assertEqual(statuses[t2.id], "Zrušeno")

        loaded = external_audit_service.get_detail(int(saved.id))
        nc = next(
            item
            for item in loaded.findings
            if item.finding_type == EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY
        )
        self.assertEqual(nc.status, EXTERNAL_AUDIT_FINDING_STATUS_OPEN)

        external_audit_service.set_status(int(saved.id), EXTERNAL_AUDIT_STATUS_CLOSED)
        after_close = external_audit_service.get_detail(int(saved.id))
        nc2 = next(
            item
            for item in after_close.findings
            if item.finding_type == EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY
        )
        self.assertEqual(nc2.status, EXTERNAL_AUDIT_FINDING_STATUS_OPEN)

    def test_07_task_dialog_cancel_creates_no_link(self) -> None:
        draft = self._base_draft(
            organization_ico=f"33{uuid.uuid4().hex[:6]}",
            organization_name="Dialog Org",
        )
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
                description="PKZ dialog",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        ]
        saved = external_audit_service.save_bundle(draft)
        finding_id = int(draft.findings[0].db_id)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        panel = editor.findings.pkz_panel
        panel.refresh()
        panel.table.selectRow(0)

        class _FakeTaskDialog:
            def __init__(self, *args, **kwargs):
                self.task = None
                self.title_edit = type("T", (), {"setPlainText": lambda *a, **k: None})()
                self.workplace_selector = type(
                    "W", (), {"set_workplace_id": lambda *a, **k: None}
                )()

            def _capture_baseline(self):
                return None

            def exec(self):
                return QDialog.DialogCode.Rejected

        with patch(
            "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
            _FakeTaskDialog,
        ):
            panel.create_task()
        self.assertEqual(
            external_audit_service.list_finding_task_ids(finding_id), []
        )

    def test_08_task_dialog_save_creates_link(self) -> None:
        draft = self._base_draft(
            organization_ico=f"44{uuid.uuid4().hex[:6]}",
            organization_name="Dialog Save Org",
        )
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="NC dialog save",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        ]
        saved = external_audit_service.save_bundle(draft)
        finding_id = int(draft.findings[0].db_id)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        panel = editor.findings.nc_panel
        panel.refresh()
        panel.table.selectRow(0)

        created = task_service.create_task(title="precreated-link-target")

        class _FakeTaskDialog:
            def __init__(self, *args, **kwargs):
                self.task = created
                self.title_edit = type("T", (), {"setPlainText": lambda *a, **k: None})()
                self.workplace_selector = type(
                    "W", (), {"set_workplace_id": lambda *a, **k: None}
                )()

            def _capture_baseline(self):
                return None

            def exec(self):
                return QDialog.DialogCode.Accepted

        with patch(
            "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
            _FakeTaskDialog,
        ):
            panel.create_task()
        self.assertEqual(
            external_audit_service.list_finding_task_ids(finding_id), [created.id]
        )

    def test_09_overview_aggregates_batch(self) -> None:
        draft = self._base_draft(
            organization_ico=f"55{uuid.uuid4().hex[:6]}",
            organization_name="Agg Org",
        )
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="O",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="V",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
                resolution_text="ok",
                resolved_at=datetime.now(),
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
                description="P",
                status=EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
            ),
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
                description="S",
                status=EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
            ),
        ]
        saved = external_audit_service.save_bundle(draft)
        nc_id = draft.findings[0].db_id
        assert nc_id
        active = task_service.create_task(title=f"EA2-act-{uuid.uuid4().hex[:4]}")
        done = task_service.create_task(title=f"EA2-done-{uuid.uuid4().hex[:4]}")
        canceled = task_service.create_task(title=f"EA2-can-{uuid.uuid4().hex[:4]}")
        external_audit_service.link_task(nc_id, active.id)
        external_audit_service.link_task(nc_id, done.id)
        external_audit_service.link_task(nc_id, canceled.id)
        task_service.update_task(done.id, title=done.title, completed=True)
        task_service.update_task(canceled.id, title=canceled.title, canceled=True)

        row = next(
            item
            for item in external_audit_service.list_overview_rows()
            if item.audit_id == int(saved.id)
        )
        self.assertEqual(row.nonconformity_open, 1)
        self.assertEqual(row.nonconformity_resolved, 1)
        self.assertEqual(row.improvement_open, 1)
        self.assertEqual(row.improvement_resolved, 0)
        self.assertEqual(row.strength_count, 1)
        self.assertEqual(row.tasks_active, 1)
        self.assertEqual(row.tasks_done, 1)
        self.assertEqual(row.tasks_canceled, 1)

        dialog = ExternalAuditsOverviewDialog()
        dialog.year_filter.setValue(dialog.year_filter.minimum())
        dialog.refresh()
        found = False
        for r in range(dialog.table.rowCount()):
            org = dialog.table.item(r, 3)
            if org and org.data(Qt.ItemDataRole.UserRole) == int(saved.id):
                self.assertEqual(dialog.table.item(r, COL_NC).text(), "1/1")
                self.assertEqual(dialog.table.item(r, COL_PKZ).text(), "1/0")
                self.assertEqual(dialog.table.item(r, COL_STRENGTH).text(), "1")
                self.assertEqual(dialog.table.item(r, COL_TASKS).text(), "1/1/1")
                found = True
                break
        self.assertTrue(found)

    def test_10_czech_date_format(self) -> None:
        self.assertEqual(format_display_date(date(2026, 8, 15)), "15.08.2026")
        self.assertEqual(format_display_date(None), "—")
        self.assertEqual(
            format_display_date(datetime(2026, 1, 2, 10, 0, 0)), "02.01.2026"
        )

    def test_11_remove_only_unsaved_draft_finding(self) -> None:
        draft = self._base_draft(
            organization_ico=f"66{uuid.uuid4().hex[:6]}",
            organization_name="Remove Org",
        )
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Uložená",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        ]
        saved = external_audit_service.save_bundle(draft)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        panel = editor.findings.nc_panel
        panel.refresh()
        panel.table.selectRow(0)
        with patch(
            "moduly.externi_audity.ui.external_audit_findings_widget.QMessageBox.information"
        ) as info:
            panel.remove_selected()
            info.assert_called_once()
        self.assertEqual(len(editor._draft.findings_for_type(
            EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY
        )), 1)

        editor._draft.findings.append(
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Jen draft",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        )
        panel.refresh()
        # Vybrat draft řádek (druhý)
        for row in range(panel.table.rowCount()):
            item = panel.table.item(row, 0)
            key = item.data(Qt.ItemDataRole.UserRole)
            finding = editor._draft.finding_by_key(str(key))
            if finding and finding.db_id is None:
                panel.table.selectRow(row)
                break
        panel.remove_selected()
        texts = [
            item.description
            for item in editor._draft.findings_for_type(
                EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY
            )
        ]
        self.assertEqual(texts, ["Uložená"])

    def test_12_task_dialog_is_agenda_dialog(self) -> None:
        self.assertTrue(issubclass(TaskDialog, QDialog))
        self.assertEqual(
            TaskDialog.__module__, "moduly.ukoly.ui.task_dialog"
        )


if __name__ == "__main__":
    unittest.main()
