"""AUDIT-INTRO-1: záložka Úvod, changes_since_last, historie provozu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-intro-1-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
session_module.reconfigure_database_engine(force=True)

from core.database.database_initializer import initialize_database  # noqa: E402
from moduly.audity.sluzby.audit_intro_schema_migration import (  # noqa: E402
    apply_audit_intro_schema_ddl,
    needs_audit_intro_schema,
    schema_is_present,
)

initialize_database()
# Testy nevolají plnou prepare_database_for_startup (záloha by zbytečně zdržovala).
apply_audit_intro_schema_ddl(storage_module.storage_service.database_path)

from PySide6.QtWidgets import QApplication  # noqa: E402

from core.shared.constants import (  # noqa: E402
    ENTITY_AUDITY,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_VYPORADANO,
    FINDING_TYPE_NESHODA,
)
from core.shared.sluzby.finding_service import finding_service  # noqa: E402
from moduly.audity.constants import (  # noqa: E402
    AUDIT_INTRO_FIRST_AUDIT_MESSAGE,
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_GENERATION_V2,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    TAB_UVOD,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.sluzby.audit_history_service import audit_history_service  # noqa: E402
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.ui.audit_dialog import AuditDialog  # noqa: E402
from moduly.audity.ui.audit_workplace_history_widget import (  # noqa: E402
    AuditWorkplaceHistoryWidget,
)
from moduly.nastaveni.sluzby.settings_service import settings_service  # noqa: E402
from moduly.ukoly.sluzby.task_service import task_service  # noqa: E402


class AuditIntroSchemaTestCase(unittest.TestCase):
    def test_schema_present_after_startup(self) -> None:
        db = storage_module.storage_service.database_path
        self.assertTrue(schema_is_present(db))
        self.assertFalse(needs_audit_intro_schema(db))


class AuditIntroHistoryTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"Úvod provoz {suffix}",
            active=True,
        )
        self.other = settings_service.save_workplace(
            name=f"Jiný provoz {suffix}",
            active=True,
        )
        self.worker = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Test-{suffix}",
        )

    def test_tab_named_uvod(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        dialog = AuditDialog(audit=audit)
        self.assertEqual(dialog.tabs.tabText(2), TAB_UVOD)
        self.assertEqual(dialog.tabs.tabText(2), "Úvod")
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(4)],
            ["Spis", "Komise", "Úvod", "Dokumentace"],
        )
        self.assertEqual(dialog.tabs.tabText(4), "Terén")
        # Výchozí aktivní záložka zůstává Spis (ne Úvod).
        self.assertEqual(dialog.tabs.currentIndex(), 0)

    def test_first_audit_message_and_no_crash(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        widget = AuditWorkplaceHistoryWidget()
        widget.load_audit(audit)
        widget.ensure_loaded()
        self.assertFalse(widget._first_audit_label.isHidden())
        self.assertIn(AUDIT_INTRO_FIRST_AUDIT_MESSAGE, widget._first_audit_label.text())
        self.assertEqual(widget._audits_table.rowCount(), 0)
        self.assertTrue(widget._changes_edit.isEnabled())
        self.assertTrue(widget._history is not None and widget._history.is_first_audit)

    def test_previous_audits_sorted_exclude_current_and_other_workplace(self) -> None:
        older = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2024,
            planned_month=1,
            audit_date=date(2024, 1, 10),
            started_at=date(2024, 1, 10),
            finished_at=date(2024, 1, 10),
        )
        newer = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            planned_month=6,
            audit_date=date(2025, 6, 15),
            started_at=date(2025, 6, 15),
            finished_at=date(2025, 6, 15),
        )
        audit_service.create_audit(
            workplace_id=self.other.id,
            workplace_name=self.other.name,
            year=2025,
            planned_month=7,
            audit_date=date(2025, 7, 1),
            started_at=date(2025, 7, 1),
            finished_at=date(2025, 7, 1),
        )
        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
            started_at=date(2026, 4, 1),
        )
        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )
        ids = [item.audit_id for item in history.previous_audits]
        self.assertEqual(ids, [newer.id, older.id])
        self.assertNotIn(current.id, ids)

    def test_findings_and_tasks_all_statuses_exclude_current(self) -> None:
        previous = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            planned_month=3,
            audit_date=date(2025, 3, 1),
            started_at=date(2025, 3, 1),
            finished_at=date(2025, 3, 1),
        )
        open_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        closed_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Vypořádané zjištění",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2025, 4, 1),
        )
        active_task = task_service.create_task(
            title="Aktivní úkol",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 5, 1),
        )
        done_task = task_service.create_task(
            title="Hotový úkol",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 5, 2),
            completed=True,
            completed_date=date(2025, 5, 3),
        )
        canceled_task = task_service.create_task(
            title="Zrušený úkol",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 5, 4),
        )
        task_service.cancel_task(canceled_task.id)
        finding_service.update(open_finding.id, task_id=active_task.id)
        finding_service.update(closed_finding.id, task_id=done_task.id)
        # Zrušený úkol navážeme druhým otevřeným zjištěním? Stačí task_id na closed + manuální
        # třetí finding pro zrušený.
        cancel_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění se zrušeným úkolem",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.update(cancel_finding.id, task_id=canceled_task.id)

        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
            started_at=date(2026, 4, 1),
        )
        current_finding = finding_service.create(
            ENTITY_AUDITY,
            current.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění aktuálního auditu",
            status=FINDING_STATUS_OTEVRENE,
        )
        current_task = task_service.create_task(
            title="Úkol aktuálního auditu",
            responsible_person_id=self.worker.id,
            due_date=date(2026, 6, 1),
        )
        finding_service.update(current_finding.id, task_id=current_task.id)

        history = audit_history_service.get_workplace_history(
            self.workplace.id,
            exclude_audit_id=current.id,
        )
        titles = {item.title for item in history.findings}
        self.assertIn("Otevřené zjištění", titles)
        self.assertIn("Vypořádané zjištění", titles)
        self.assertNotIn("Zjištění aktuálního auditu", titles)

        task_titles = {item.title for item in history.tasks}
        self.assertTrue(any("Aktivní úkol" in title for title in task_titles))
        self.assertTrue(any("Hotový úkol" in title for title in task_titles))
        self.assertTrue(any("Zrušený úkol" in title for title in task_titles))
        self.assertFalse(any("Úkol aktuálního auditu" in title for title in task_titles))

    def test_changes_since_last_save_keep_open_and_discard(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        dialog = AuditDialog(audit=audit)
        dialog.history_widget._changes_edit.setPlainText("Nová linka")
        self.assertTrue(dialog._is_dirty())
        with (
            patch.object(dialog.commission_widget, "validate", return_value=(True, "")),
            patch.object(dialog, "save_commission_members"),
        ):
            self.assertTrue(dialog._persist())
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.changes_since_last, "Nová linka")

        dialog.history_widget._changes_edit.setPlainText("Dočasná změna")
        self.assertTrue(dialog._is_dirty())
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._confirm_close())
        self.assertEqual(dialog.history_widget._changes_edit.toPlainText(), "Nová linka")
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.changes_since_last, "Nová linka")

    def test_save_and_close_persists(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        dialog = AuditDialog(audit=audit)
        dialog.history_widget._changes_edit.setPlainText("Zavřít text")
        with (
            patch.object(dialog.commission_widget, "validate", return_value=(True, "")),
            patch.object(dialog, "save_commission_members"),
            patch.object(dialog, "_done_accept") as accept_mock,
        ):
            dialog._save_and_close()
            accept_mock.assert_called_once()
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.changes_since_last, "Zavřít text")

    def test_opening_uvod_does_not_write(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        before = audit_service.get_by_id(audit.id)
        assert before is not None
        before_updated = before.updated_at
        dialog = AuditDialog(audit=audit)
        dialog.tabs.setCurrentWidget(dialog.history_widget)
        after = audit_service.get_by_id(audit.id)
        assert after is not None
        self.assertEqual(after.updated_at, before_updated)
        self.assertIsNone(after.changes_since_last)

    def test_lazy_load_skips_history_until_tab(self) -> None:
        previous = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            planned_month=1,
            audit_date=date(2025, 1, 1),
            started_at=date(2025, 1, 1),
            finished_at=date(2025, 1, 1),
        )
        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
            started_at=date(2026, 4, 1),
        )
        with patch.object(
            audit_history_service,
            "get_workplace_history",
            wraps=audit_history_service.get_workplace_history,
        ) as mocked:
            dialog = AuditDialog(audit=current)
            self.assertEqual(mocked.call_count, 0)
            dialog.tabs.setCurrentWidget(dialog.history_widget)
            self.assertGreaterEqual(mocked.call_count, 1)
            self.assertEqual(dialog.history_widget._audits_table.rowCount(), 1)
            self.assertEqual(
                int(dialog.history_widget._audits_table.item(0, 0).text()),
                previous.id,
            )

    def test_refresh_does_not_reload_methodology(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        dialog = AuditDialog(audit=audit)
        dialog.tabs.setCurrentWidget(dialog.history_widget)
        with patch.object(dialog, "set_audit_id") as set_id:
            dialog.history_widget.refresh()
            set_id.assert_not_called()

    def test_no_ensure_catalogs_or_knowledge_tree_on_intro(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
        )
        with (
            patch(
                "moduly.audity.sluzby.audit_knowledge_service.AuditKnowledgeService.ensure_catalogs"
            ) as ensure,
            patch(
                "moduly.audity.sluzby.audit_knowledge_service.AuditKnowledgeService.get_knowledge_tree"
            ) as tree,
        ):
            history = audit_history_service.get_workplace_history(
                self.workplace.id,
                exclude_audit_id=audit.id,
            )
            self.assertTrue(history.is_first_audit)
            ensure.assert_not_called()
            tree.assert_not_called()

    def test_legacy_and_v2_snapshots_untouched(self) -> None:
        from core.database.session import get_session
        from sqlalchemy import select

        from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot

        legacy = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            planned_month=1,
        )
        v2 = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=2,
        )
        with get_session() as session:
            for audit, generation in (
                (legacy, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1),
                (v2, AUDIT_METHODOLOGY_GENERATION_V2),
            ):
                row = session.get(Audit, audit.id)
                assert row is not None
                row.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                row.methodology_generation = generation
                session.add(
                    AuditQuestionSnapshot(
                        audit_id=audit.id,
                        process_id="p",
                        process_name="P",
                        section_id="s",
                        section_name="S",
                        assertion_id=f"q-{audit.id}",
                        assertion_text="Snapshot text",
                        verification_type="dokumentace",
                        severity="stredni",
                        question_kind="legacy"
                        if generation == AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
                        else "operation",
                        display_order=1,
                        is_in_scope=True,
                    )
                )
            session.commit()

        audit_service.update_audit(legacy.id, changes_since_last="poznámka")
        with get_session() as session:
            snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id.in_([legacy.id, v2.id])
                    )
                )
            )
        self.assertEqual(len(snaps), 2)
        self.assertTrue(all(s.assertion_text == "Snapshot text" for s in snaps))


class AuditIntroOpenDetailTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"Detail provoz {suffix}",
            active=True,
        )
        self.worker = settings_service.save_worker(
            first_name="Jan",
            last_name=f"Detail-{suffix}",
        )

    def test_open_audit_finding_task_paths(self) -> None:
        previous = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            planned_month=2,
            audit_date=date(2025, 2, 2),
            started_at=date(2025, 2, 2),
            finished_at=date(2025, 2, 2),
        )
        finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Detail zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        task = task_service.create_task(
            title="Detail úkol",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 3, 1),
        )
        finding_service.update(finding.id, task_id=task.id)
        current = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            planned_month=4,
            started_at=date(2026, 4, 1),
        )
        widget = AuditWorkplaceHistoryWidget()
        widget.load_audit(current)
        widget.ensure_loaded()

        opened: list[str] = []

        def fake_exec_maximized(dialog):
            opened.append("audit")
            return 0

        with patch(
            "moduly.audity.ui.audit_workplace_history_widget.exec_maximized",
            side_effect=fake_exec_maximized,
        ):
            widget._audits_table.selectRow(0)
            widget._open_selected_audit()
        self.assertIn("audit", opened)

        with patch(
            "moduly.audity.ui.audit_workplace_history_widget.FindingDialog"
        ) as finding_dialog_cls:
            finding_dialog_cls.return_value.exec.return_value = False
            widget._findings_table.selectRow(0)
            widget._open_selected_finding()
            finding_dialog_cls.assert_called_once()

        with patch(
            "moduly.audity.ui.audit_workplace_history_widget.TaskDialog"
        ) as task_dialog_cls:
            task_dialog_cls.return_value.exec.return_value = 0
            widget._tasks_table.selectRow(0)
            widget._open_selected_task()
            task_dialog_cls.assert_called_once()


if __name__ == "__main__":
    unittest.main()
