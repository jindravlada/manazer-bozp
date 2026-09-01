"""STATE-SUPERVISION-FINDING-TASK-CORE-5A4: kritický úkol ze zjištění."""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import sqlite3
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.navigation.source_navigator import source_navigator
    from core.shared.constants import (
        ENTITY_ACCIDENT,
        ENTITY_AUDITY,
        ENTITY_FINDING,
        ENTITY_MU_INVESTIGATION,
        ENTITY_PROVERKY,
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.repository.finding_repository import FindingRepository
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from core.shared.task_source_display import (
        task_source_label,
        task_source_short_label,
        task_source_short_labels,
    )
    from moduly.agenda.constants import PRIORITY_CRITICAL, PRIORITY_LOW
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.statni_dozor.constants import (
        FILTER_MODE_ACTIVE,
        FINDING_PARENT_MISSING_MESSAGE,
        FINDING_TASK_ALREADY_LINKED_MESSAGE,
        FINDING_TASK_MISSING_TASK_MESSAGE,
        FINDING_TASK_NOT_FOUND_MESSAGE,
        FINDING_TASK_WRONG_ENTITY_MESSAGE,
        ITEM_NOT_FOUND_MESSAGE,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_IN_PROGRESS,
        TAB_STATE_SUPERVISION,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_task_service import (
        state_supervision_finding_task_service as ss_finding_task_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _delete_supervision(supervision_id: int) -> None:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        conn.execute(
            "DELETE FROM state_supervisions WHERE id = ?",
            (int(supervision_id),),
        )
        conn.commit()
    finally:
        conn.close()


class StateSupervisionFindingTaskCore5a4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        cls._app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        source_navigator.configure(None)

    def tearDown(self) -> None:
        source_navigator.configure(None)

    def _supervision(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}", "subject": "BOZP na pracovišti"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _ss_finding(self, parent_id: int, **fields):
        payload = {
            "finding_type": FINDING_TYPE_ZAVADA,
            "description": f"Zjištění {self.marker}",
            "status": FINDING_STATUS_OTEVRENE,
        }
        payload.update(fields)
        return finding_service.create(ENTITY_STATE_SUPERVISION, parent_id, **payload)

    def _foreign_finding(self, entity_type: str, entity_id: int, **fields):
        payload = {
            "finding_type": FINDING_TYPE_NESHODA if entity_type == ENTITY_AUDITY else FINDING_TYPE_ZJISTENI,
            "description": f"Cizí {self.marker}",
            "status": FINDING_STATUS_OTEVRENE,
        }
        payload.update(fields)
        return finding_service.create(entity_type, entity_id, **payload)

    def test_01_validation_allows_ss_rejects_foreign_missing_and_linked(self) -> None:
        parent = self._supervision()
        allowed = self._ss_finding(parent.id, description="Povolené SS")
        task = ss_finding_task_service.create_task_for_finding(allowed.id)
        self.assertEqual(task.source_module, ENTITY_FINDING)
        self.assertEqual(task.source_record_id, allowed.id)

        audit_finding = self._foreign_finding(ENTITY_AUDITY, 91001)
        inspection_finding = self._foreign_finding(ENTITY_PROVERKY, 91002)
        with self.assertRaises(StateSupervisionError) as audit_err:
            ss_finding_task_service.create_task_for_finding(audit_finding.id)
        self.assertEqual(str(audit_err.exception), FINDING_TASK_WRONG_ENTITY_MESSAGE)
        with self.assertRaises(StateSupervisionError) as inspection_err:
            ss_finding_task_service.create_task_for_finding(inspection_finding.id)
        self.assertEqual(str(inspection_err.exception), FINDING_TASK_WRONG_ENTITY_MESSAGE)
        self.assertIsNone(finding_service.get_by_id(audit_finding.id).task_id)
        self.assertIsNone(finding_service.get_by_id(inspection_finding.id).task_id)

        with self.assertRaises(StateSupervisionError) as missing_err:
            ss_finding_task_service.create_task_for_finding(9_999_999)
        self.assertEqual(str(missing_err.exception), FINDING_TASK_NOT_FOUND_MESSAGE)

        orphan_parent = self._supervision(authority_name=f"Mazaná {self.marker}")
        orphan_finding = self._ss_finding(orphan_parent.id, description="Bez rodiče")
        _delete_supervision(orphan_parent.id)
        self.assertIsNone(state_supervision_service.get_supervision(orphan_parent.id))
        with self.assertRaises(StateSupervisionError) as parent_err:
            ss_finding_task_service.create_task_for_finding(orphan_finding.id)
        self.assertIn(str(orphan_parent.id), str(parent_err.exception))
        self.assertIsNone(finding_service.get_by_id(orphan_finding.id).task_id)

        linked = finding_service.get_by_id(allowed.id)
        assert linked is not None
        original_task_id = linked.task_id
        original_title = task.title
        with self.assertRaises(StateSupervisionError) as linked_err:
            ss_finding_task_service.create_task_for_finding(
                allowed.id,
                {"title": "Neměnit existující"},
            )
        self.assertEqual(str(linked_err.exception), FINDING_TASK_ALREADY_LINKED_MESSAGE)
        reloaded = finding_service.get_by_id(allowed.id)
        assert reloaded is not None
        self.assertEqual(reloaded.task_id, original_task_id)
        self.assertEqual(task_service.get_task_by_id(original_task_id).title, original_title)

        dangling = self._ss_finding(parent.id, description="Visící task_id")
        finding_service.update(dangling.id, task_id=8_888_777)
        with self.assertLogs(
            "moduly.statni_dozor.sluzby.state_supervision_finding_task_service",
            level=logging.ERROR,
        ) as logs:
            with self.assertRaises(StateSupervisionError) as dangling_err:
                ss_finding_task_service.create_task_for_finding(dangling.id)
        self.assertEqual(str(dangling_err.exception), FINDING_TASK_MISSING_TASK_MESSAGE)
        joined = "\n".join(logs.output)
        self.assertIn(str(dangling.id), joined)
        self.assertIn("8888777", joined)
        after = finding_service.get_by_id(dangling.id)
        assert after is not None
        self.assertEqual(after.task_id, 8_888_777)
        self.assertIsNone(task_service.get_task_by_id(8_888_777))

    def test_02_create_forces_identity_priority_and_defaults(self) -> None:
        parent = self._supervision()
        due = date(2026, 4, 15)
        finding = self._ss_finding(
            parent.id,
            description="Popis zjištění\ndruhý řádek česky",
            recommended_action="Doplnit dokumentaci OOPP",
            due_date=due,
            responsible_person_id=42,
            responsible_person_name="Jan Novák",
        )
        defaults = ss_finding_task_service.task_defaults_for_finding(finding)
        self.assertEqual(defaults["title"], "Doplnit dokumentaci OOPP")
        self.assertIn("Popis zjištění", defaults["description"])
        self.assertIn("druhý řádek česky", defaults["description"])
        self.assertIn("Doporučené opatření", defaults["description"])
        self.assertEqual(defaults["priority"], PRIORITY_CRITICAL)
        self.assertEqual(PRIORITY_CRITICAL, "Kritická")
        self.assertEqual(defaults["due_date"], due)
        self.assertEqual(defaults["responsible_person_id"], 42)
        self.assertTrue(defaults["requires_verification"])
        self.assertEqual(defaults["source_module"], ENTITY_FINDING)
        self.assertEqual(defaults["source_record_id"], finding.id)

        fallback = self._ss_finding(
            parent.id,
            description="Krátký název z popisu\nDalší řádek",
            recommended_action="",
        )
        fallback_defaults = ss_finding_task_service.task_defaults_for_finding(fallback)
        self.assertEqual(fallback_defaults["title"], "Krátký název z popisu")

        before_tasks = _count("tasks")
        commits: list[str] = []
        original_commit = Session.commit

        def spy_commit(self, *args, **kwargs):
            commits.append("commit")
            return original_commit(self, *args, **kwargs)

        with patch.object(Session, "commit", spy_commit):
            task = ss_finding_task_service.create_task_for_finding(
                finding.id,
                {
                    "title": "",
                    "description": "",
                    "priority": PRIORITY_LOW,
                    "source_module": "manual",
                    "source_record_id": 999,
                    "due_date": due,
                    "responsible_person_id": 42,
                },
            )
        self.assertEqual(len(commits), 1)
        self.assertEqual(_count("tasks"), before_tasks + 1)
        self.assertEqual(task.source_module, ENTITY_FINDING)
        self.assertEqual(task.source_record_id, finding.id)
        self.assertEqual(task.priority, PRIORITY_CRITICAL)
        self.assertNotEqual(task.priority, PRIORITY_LOW)
        self.assertEqual(task.title, "Doplnit dokumentaci OOPP")
        self.assertIn("druhý řádek česky", task.description)
        self.assertEqual(task.due_date, due)
        self.assertEqual(task.responsible_person_id, 42)
        self.assertEqual(task.responsible_person, "Jan Novák")
        self.assertTrue(task.requires_verification)
        stored = finding_service.get_by_id(finding.id)
        assert stored is not None
        self.assertEqual(stored.task_id, task.id)
        self.assertEqual(stored.status, FINDING_STATUS_V_PROCESU)

        sig = inspect.signature(ss_finding_task_service.create_task_for_finding)
        self.assertIn("finding_id", sig.parameters)
        self.assertIn("task_fields", sig.parameters)
        factory = ss_finding_task_service.create_task_for_finding
        self.assertTrue(callable(factory))

    def test_03_atomicity_no_orphan_and_retry_creates_one(self) -> None:
        parent = self._supervision()
        finding = self._ss_finding(parent.id, description="Atomické")
        before_tasks = _count("tasks")

        with self.assertRaises(ValueError):
            ss_finding_task_service.create_task_for_finding(
                finding.id,
                {
                    "title": "Nevalidní",
                    "due_date": date(2026, 1, 1),
                    "remind_from": date(2026, 1, 2),
                },
            )
        self.assertEqual(_count("tasks"), before_tasks)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)

        with patch.object(Session, "flush", side_effect=RuntimeError("flush Task")):
            with self.assertRaises(RuntimeError):
                ss_finding_task_service.create_task_for_finding(
                    finding.id,
                    {"title": "Po flush chybě"},
                )
        self.assertEqual(_count("tasks"), before_tasks)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)

        with patch.object(FindingRepository, "save", side_effect=RuntimeError("finding write")):
            with self.assertRaises(RuntimeError):
                ss_finding_task_service.create_task_for_finding(
                    finding.id,
                    {"title": "Po chybě Finding"},
                )
        self.assertEqual(_count("tasks"), before_tasks)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)

        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            with self.assertRaises(RuntimeError):
                ss_finding_task_service.create_task_for_finding(
                    finding.id,
                    {"title": "Po chybě commit"},
                )
        self.assertEqual(_count("tasks"), before_tasks)
        self.assertIsNone(finding_service.get_by_id(finding.id).task_id)

        task = ss_finding_task_service.create_task_for_finding(
            finding.id,
            {"title": "Druhý pokus"},
        )
        self.assertEqual(_count("tasks"), before_tasks + 1)
        stored = finding_service.get_by_id(finding.id)
        assert stored is not None
        self.assertEqual(stored.task_id, task.id)
        self.assertEqual(task.title, "Druhý pokus")
        self.assertEqual(task.priority, PRIORITY_CRITICAL)

    def test_04_source_display_ss_and_existing_modules(self) -> None:
        parent = self._supervision(
            authority_name="KHS Praha",
            subject="Hygiena provozu",
        )
        ss_finding = self._ss_finding(parent.id, description="Zdroj SS")
        ss_task = ss_finding_task_service.create_task_for_finding(ss_finding.id)
        self.assertEqual(task_source_short_label(ss_task), "Státní dozor")
        long_label = task_source_label(ss_task)
        self.assertTrue(long_label.startswith("Státní dozor"))
        self.assertIn("KHS Praha", long_label)
        self.assertIn("Hygiena provozu", long_label)
        self.assertNotIn("finding", long_label)
        self.assertNotIn("state_supervision", long_label)
        self.assertNotIn(f"Finding #{ss_finding.id}", long_label)

        audit_finding = self._foreign_finding(ENTITY_AUDITY, 1, description="Auditní")
        inspection_finding = self._foreign_finding(ENTITY_PROVERKY, 1, description="Prověrkové")
        accident_finding = self._foreign_finding(ENTITY_ACCIDENT, 1, description="Úrazové")
        mu_finding = self._foreign_finding(ENTITY_MU_INVESTIGATION, 1, description="MU")
        audit_task = task_service.create_task(
            title="Audit úkol",
            source_module=ENTITY_FINDING,
            source_record_id=audit_finding.id,
        )
        inspection_task = task_service.create_task(
            title="Prověrka úkol",
            source_module=ENTITY_FINDING,
            source_record_id=inspection_finding.id,
        )
        accident_task = task_service.create_task(
            title="Úraz úkol",
            source_module=ENTITY_FINDING,
            source_record_id=accident_finding.id,
        )
        mu_task = task_service.create_task(
            title="MU úkol",
            source_module=ENTITY_FINDING,
            source_record_id=mu_finding.id,
        )
        self.assertEqual(task_source_short_label(audit_task), "Audit")
        self.assertEqual(task_source_short_label(inspection_task), "Prověrka")
        self.assertEqual(task_source_short_label(accident_task), "Úraz")
        self.assertEqual(task_source_short_label(mu_task), "MU")
        self.assertTrue(task_source_label(audit_task).startswith("Audit systému řízení"))
        self.assertEqual(task_source_label(inspection_task), "Prověrka BOZP")
        self.assertTrue(task_source_label(accident_task).startswith("Úraz"))
        self.assertTrue(task_source_label(mu_task).startswith("Vyšetřování MU"))

        second = self._ss_finding(parent.id, description="Druhé SS")
        second_task = ss_finding_task_service.create_task_for_finding(second.id)
        batch_tasks = [ss_task, second_task, audit_task]
        with (
            patch.object(finding_service, "get_by_id") as get_one,
            patch.object(finding_service, "get_by_ids", wraps=finding_service.get_by_ids) as get_many,
            patch.object(
                state_supervision_service,
                "get_supervision",
            ) as get_one_ss,
        ):
            labels = task_source_short_labels(batch_tasks)
            get_one.assert_not_called()
            get_one_ss.assert_not_called()
            get_many.assert_called()
        self.assertEqual(labels[ss_task.id], "Státní dozor")
        self.assertEqual(labels[second_task.id], "Státní dozor")
        self.assertEqual(labels[audit_task.id], "Audit")

    def test_05_navigation_opens_supervision_without_write(self) -> None:
        closed_at = datetime(2026, 3, 2, 9, 0, 0)
        active = self._supervision(status=STATUS_IN_PROGRESS, authority_name=f"Aktivní {self.marker}")
        closed = self._supervision(
            status=STATUS_CLOSED,
            authority_name=f"Uzavřená {self.marker}",
            closed_at=closed_at,
        )
        cancelled = self._supervision(
            status=STATUS_CANCELLED,
            authority_name=f"Zrušená {self.marker}",
        )
        finding = self._ss_finding(active.id, description="Navigace")
        closed_finding = self._ss_finding(closed.id, description="Navigace uzavřená")
        cancelled_finding = self._ss_finding(cancelled.id, description="Navigace zrušená")

        page = AgendaPage()
        host = MagicMock()
        host._page_widgets = {"agenda": page}
        host._show = MagicMock()
        source_navigator.configure(host)

        opened: list[int | None] = []

        class FakeDialog:
            def __init__(self, parent=None, *, supervision_id=None):
                opened.append(supervision_id)
                self.saved = False
                self.supervision_id = supervision_id

        with (
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.StateSupervisionEditorDialog",
                FakeDialog,
            ),
            patch(
                "moduly.statni_dozor.ui.state_supervision_tab.exec_maximized",
                lambda dialog: None,
            ),
            patch.object(Session, "commit") as commit,
        ):
            ss_index = page.tabs.indexOf(page.state_supervision_tab)
            self.assertGreaterEqual(ss_index, 0)
            self.assertEqual(page.tabs.tabText(ss_index), TAB_STATE_SUPERVISION)
            open_src = inspect.getsource(AgendaPage.open_supervision)
            self.assertIn("indexOf(self.state_supervision_tab)", open_src)
            self.assertNotIn("setCurrentIndex(1)", open_src)

            self.assertTrue(source_navigator.open_finding(finding.id))
            self.assertEqual(page.tabs.currentIndex(), ss_index)
            self.assertEqual(opened[-1], active.id)
            host._show.assert_called_with("agenda")
            commit.assert_not_called()

            opened.clear()
            self.assertTrue(source_navigator.open_finding(closed_finding.id))
            self.assertEqual(opened[-1], closed.id)
            self.assertTrue(source_navigator.open_finding(cancelled_finding.id))
            self.assertEqual(opened[-1], cancelled.id)

            page.state_supervision_tab.mode_filter.setCurrentText(FILTER_MODE_ACTIVE)
            page.state_supervision_tab.refresh()
            from moduly.statni_dozor.constants import COL_STATUS

            present_ids: list[int] = []
            table = page.state_supervision_tab.table
            for row in range(table.rowCount()):
                cell = table.item(row, COL_STATUS)
                if cell is None:
                    continue
                present_ids.append(int(cell.data(Qt.ItemDataRole.UserRole)))
            self.assertNotIn(closed.id, present_ids)
            self.assertNotIn(cancelled.id, present_ids)
            opened.clear()
            page.open_supervision(closed.id)
            self.assertEqual(opened[-1], closed.id)
            self.assertEqual(
                page.state_supervision_tab.mode_filter.currentText(),
                FILTER_MODE_ACTIVE,
            )

        orphan_parent = self._supervision(authority_name=f"Bez rodiče {self.marker}")
        orphan_finding = self._ss_finding(orphan_parent.id, description="Navigace bez rodiče")
        _delete_supervision(orphan_parent.id)
        with patch.object(QMessageBox, "warning", return_value=None) as warn:
            self.assertFalse(source_navigator.open_finding(orphan_finding.id))
            warn.assert_called()
            self.assertEqual(warn.call_args.args[2], FINDING_PARENT_MISSING_MESSAGE)

        with patch.object(QMessageBox, "warning", return_value=None) as warn:
            self.assertFalse(source_navigator.open_finding(9_999_111))
            warn.assert_called()

        with patch.object(QMessageBox, "warning", return_value=None) as warn:
            page.open_supervision(9_999_222)
            warn.assert_called()
            self.assertEqual(warn.call_args.args[2], ITEM_NOT_FOUND_MESSAGE)

    def test_06_no_automatic_task_from_save_load_or_editor(self) -> None:
        from moduly.statni_dozor.modely.state_supervision_finding_draft import (
            StateSupervisionFindingDraft,
        )
        from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
            StateSupervisionEditorDialog,
        )

        parent = self._supervision()
        before = _count("tasks")
        state_supervision_service.save_supervision_bundle(
            supervision_id=parent.id,
            fields={"authority_name": parent.authority_name},
            findings=[
                StateSupervisionFindingDraft(
                    finding_type=FINDING_TYPE_NEDOSTATEK,
                    description=f"Uložit bez úkolu {self.marker}",
                )
            ],
        )
        self.assertEqual(_count("tasks"), before)
        listed = finding_service.get_for_entity(ENTITY_STATE_SUPERVISION, parent.id)
        self.assertTrue(listed)
        self.assertTrue(all(row.task_id is None for row in listed))

        dialog = StateSupervisionEditorDialog(supervision_id=parent.id)
        self.assertEqual(_count("tasks"), before)
        self.assertTrue(dialog._editor._run_save())
        self.assertEqual(_count("tasks"), before)
        texts = [
            dialog.add_finding_btn.text(),
            dialog.edit_finding_btn.text(),
            dialog.remove_finding_btn.text(),
        ]
        self.assertNotIn("Vytvořit úkol", texts)
        self.assertEqual(dialog.create_finding_task_btn.text(), "Vytvořit úkol")
        editor_src = inspect.getsource(StateSupervisionEditorDialog)
        persist_src = inspect.getsource(StateSupervisionEditorDialog._persist)
        bundle_src = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertIn("ACTION_CREATE_TASK", editor_src)
        self.assertIn("create_task_for_finding", editor_src)
        self.assertNotIn("create_task_for_finding", persist_src)
        self.assertNotIn("create_task_for_finding", bundle_src)
        self.assertNotIn("state_supervision_finding_task_service", persist_src)
        self.assertNotIn("state_supervision_finding_task_service", bundle_src)
        self.assertEqual(editor_src.count("self.tabs.addTab("), 5)
        dialog.close()

        agenda = inspect.getsource(AgendaPage)
        self.assertEqual(agenda.count("self.tabs.addTab("), 4)
        self.assertIn("open_supervision", agenda)
        task_src = inspect.getsource(finding_task_service.__class__)
        self.assertNotIn("state_supervision", task_src)
        self.assertNotIn("ENTITY_STATE_SUPERVISION", task_src)
        create_src = inspect.getsource(task_service.create_task)
        self.assertIn("session", create_src)

    def test_07_task_dialog_create_factory_contract_and_audit_priority_untouched(self) -> None:
        factory_src = inspect.getsource(TaskDialog)
        self.assertIn("create_factory", factory_src)
        self.assertIn("self._create_factory(data)", factory_src)
        audit_finding = self._foreign_finding(
            ENTITY_AUDITY,
            77001,
            description="Auditní zjištění",
            recommended_action="Opravit dokumentaci",
        )
        audit_task = finding_task_service.create_task_from_finding(audit_finding.id)
        self.assertEqual(audit_task.priority, "Normální")
        self.assertNotEqual(audit_task.priority, PRIORITY_CRITICAL)
        self.assertEqual(audit_task.source_module, ENTITY_FINDING)


if __name__ == "__main__":
    unittest.main()
