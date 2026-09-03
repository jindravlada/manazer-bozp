"""STATE-SUPERVISION-FINDING-AGREED-ACTION-1: Dohodnutý další postup."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
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

    import core.services.attachment_service as attachment_module

    importlib.reload(attachment_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_OPATRENI,
        FINDING_TYPE_PORUSENI_PREDPISU,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.finding_display import FINDING_TYPE_LABELS
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.finding_service import finding_service
    from core.widgets.finding_dialog import FindingDialog
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.audity.constants import AUDIT_FINDING_TYPE_LABELS, AUDIT_FINDING_TYPES
    from moduly.statni_dozor.constants import (
        ATTENTION_REASON_OVERDUE_FINDINGS,
        COL_FINDING_TYPE,
        STATE_SUPERVISION_FINDING_TYPE_LABELS,
        STATE_SUPERVISION_FINDING_TYPE_ORDER,
        STATE_SUPERVISION_FINDING_TYPES,
        is_state_supervision_finding_type,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_attention import (
        attention_for_supervision,
    )
    from moduly.statni_dozor.sluzby.state_supervision_closure_readiness import (
        state_supervision_closure_readiness,
    )
    from moduly.statni_dozor.sluzby.state_supervision_deadline_projection import (
        KIND_FINDING,
        list_state_supervision_deadline_items,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
        state_supervision_finding_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_task_service import (
        state_supervision_finding_task_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        state_supervision_service,
    )
    from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
        StateSupervisionEditorDialog,
    )
    from moduly.statni_dozor.ui.state_supervision_finding_dialog import (
        StateSupervisionFindingDialog,
    )


_EXPECTED_ORDER = (
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_OPATRENI,
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_PORUSENI_PREDPISU,
    FINDING_TYPE_ZJISTENI,
)

_EXPECTED_LABELS = (
    "Příležitost ke zlepšení (PKZ)",
    "Dohodnutý další postup",
    "Nedostatek",
    "Závada",
    "Porušení požadavku",
    "Jiné zjištění",
)


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _draft(**fields) -> StateSupervisionFindingDraft:
    payload = {
        "finding_type": FINDING_TYPE_OPATRENI,
        "description": "Kontrolní zjištění",
    }
    payload.update(fields)
    return StateSupervisionFindingDraft(**payload)


class StateSupervisionFindingAgreedAction1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        importlib.reload(attachment_module)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]

    def _supervision(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def _save(self, dialog: StateSupervisionEditorDialog) -> bool:
        return bool(dialog._editor._run_save())

    def _add_working(self, dialog: StateSupervisionEditorDialog, **fields):
        payload = {"description": f"Zjištění {self.marker}"}
        payload.update(fields)
        payload.setdefault("display_order", len(dialog._findings_drafts) * 10)
        draft = _draft(**payload)
        dialog._findings_drafts.append(draft)
        dialog._refresh_findings_table(select_key=draft.client_key)
        dialog._editor.refresh_dirty()
        return draft

    def test_01_opatreni_is_allowed_with_local_label_and_order(self) -> None:
        self.assertEqual(FINDING_TYPE_OPATRENI, "opatreni")
        self.assertTrue(is_state_supervision_finding_type(FINDING_TYPE_OPATRENI))
        self.assertIn(FINDING_TYPE_OPATRENI, STATE_SUPERVISION_FINDING_TYPES)
        self.assertNotIn(FINDING_TYPE_POZOROVANI, STATE_SUPERVISION_FINDING_TYPES)
        self.assertFalse(is_state_supervision_finding_type(FINDING_TYPE_POZOROVANI))
        self.assertEqual(STATE_SUPERVISION_FINDING_TYPE_ORDER, _EXPECTED_ORDER)
        self.assertEqual(
            STATE_SUPERVISION_FINDING_TYPE_LABELS[FINDING_TYPE_OPATRENI],
            "Dohodnutý další postup",
        )
        self.assertEqual(
            [STATE_SUPERVISION_FINDING_TYPE_LABELS[code] for code in STATE_SUPERVISION_FINDING_TYPE_ORDER],
            list(_EXPECTED_LABELS),
        )

        sub = StateSupervisionFindingDialog(is_new=True)
        labels = [sub.type_combo.itemText(i) for i in range(sub.type_combo.count())]
        codes = [sub.type_combo.itemData(i) for i in range(sub.type_combo.count())]
        self.assertEqual(labels, list(_EXPECTED_LABELS))
        self.assertEqual(tuple(codes), _EXPECTED_ORDER)
        self.assertNotIn("opatreni", labels)
        self.assertNotIn("Opatření", labels)
        self.assertNotIn("Pozorování", labels)
        sub.close()

    def test_02_draft_save_reload_edit_and_resolve(self) -> None:
        dialog = StateSupervisionEditorDialog()
        self.assertIsNone(dialog.supervision_id)
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        draft = self._add_working(
            dialog,
            finding_type=FINDING_TYPE_OPATRENI,
            description="Předložené měření již nebylo považováno za dostatečně aktuální.",
            recommended_action="Provést nové měření a výsledek doložit kontrolnímu orgánu.",
            due_date=date(2026, 10, 15),
        )
        self.assertIsNone(draft.id)
        self.assertTrue(draft.client_key)
        self.assertEqual(_count("findings"), 0)
        before_tasks = _count("tasks")
        self.assertTrue(self._save(dialog))
        self.assertIsNotNone(dialog.supervision_id)
        self.assertEqual(dialog._findings_drafts[0].finding_type, FINDING_TYPE_OPATRENI)
        self.assertIsNotNone(dialog._findings_drafts[0].id)
        self.assertEqual(_count("tasks"), before_tasks)
        stored = state_supervision_finding_service.list_findings(dialog.supervision_id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].finding_type, FINDING_TYPE_OPATRENI)
        self.assertEqual(
            stored[0].recommended_action,
            "Provést nové měření a výsledek doložit kontrolnímu orgánu.",
        )
        supervision_id = dialog.supervision_id
        dialog.close()

        reopened = StateSupervisionEditorDialog(supervision_id=supervision_id)
        self.assertEqual(reopened.findings_table.rowCount(), 1)
        self.assertEqual(
            reopened.findings_table.item(0, COL_FINDING_TYPE).text(),
            "Dohodnutý další postup",
        )
        self.assertNotEqual(
            reopened.findings_table.item(0, COL_FINDING_TYPE).text(),
            "opatreni",
        )
        self.assertEqual(reopened._findings_drafts[0].finding_type, FINDING_TYPE_OPATRENI)
        self.assertEqual(
            reopened._findings_drafts[0].recommended_action,
            "Provést nové měření a výsledek doložit kontrolnímu orgánu.",
        )
        reopened._findings_drafts[0] = _draft(
            id=reopened._findings_drafts[0].id,
            client_key=reopened._findings_drafts[0].client_key,
            finding_type=FINDING_TYPE_OPATRENI,
            description="Upravený popis dohodnutého postupu.",
            recommended_action=reopened._findings_drafts[0].recommended_action,
            due_date=date(2026, 10, 15),
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 9, 1),
        )
        reopened._refresh_findings_table()
        reopened._editor.refresh_dirty()
        self.assertTrue(reopened._editor.is_dirty())
        self.assertTrue(self._save(reopened))
        reopened.close()

        listed = state_supervision_finding_service.list_findings(supervision_id)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].finding_type, FINDING_TYPE_OPATRENI)
        self.assertEqual(listed[0].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(listed[0].description, "Upravený popis dohodnutého postupu.")
        self.assertEqual(listed[0].resolved_at, date(2026, 9, 1))
        self.assertIsNone(listed[0].task_id)

    def test_03_dirty_snapshot_no_auto_task_and_manual_task(self) -> None:
        dialog = StateSupervisionEditorDialog()
        dialog.authority_combo.setCurrentText(f"OIP {self.marker}")
        dialog._editor.capture_baseline()
        self.assertFalse(dialog._editor.is_dirty())
        baseline = dialog.get_snapshot()
        self._add_working(
            dialog,
            finding_type=FINDING_TYPE_OPATRENI,
            description="Dohodnutý postup ke snapshotu",
        )
        self.assertTrue(dialog._editor.is_dirty())
        self.assertNotEqual(dialog.get_snapshot(), baseline)

        other = StateSupervisionEditorDialog()
        other.authority_combo.setCurrentText(f"KHS {self.marker}")
        other._editor.capture_baseline()
        self.assertFalse(other._editor.is_dirty())
        other_baseline = other.get_snapshot()
        self._add_working(
            other,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Závada ke snapshotu",
        )
        self.assertTrue(other._editor.is_dirty())
        self.assertNotEqual(other.get_snapshot(), other_baseline)
        other.close()

        before_tasks = _count("tasks")
        self.assertTrue(self._save(dialog))
        self.assertFalse(dialog._editor.is_dirty())
        self.assertEqual(_count("tasks"), before_tasks)
        finding_id = int(dialog._findings_drafts[0].id)
        dialog.close()

        task = state_supervision_finding_task_service.create_task_for_finding(
            finding_id,
            {"title": f"Navazující úkol {self.marker}"},
        )
        self.assertEqual(task.priority, PRIORITY_CRITICAL)
        reloaded = finding_service.get_by_id(finding_id)
        assert reloaded is not None
        self.assertEqual(reloaded.task_id, task.id)
        self.assertEqual(_count("tasks"), before_tasks + 1)

    def test_04_deadline_projection_closure_and_attention(self) -> None:
        parent = self._supervision()
        due = date(2026, 8, 1)
        now = datetime(2026, 9, 3, 12, 0, 0)
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_OPATRENI,
            description=f"Dohodnutý postup {self.marker}",
            due_date=due,
            status=FINDING_STATUS_OTEVRENE,
        )

        items = list_state_supervision_deadline_items(
            today=now.date(),
            load_supervisions=lambda: [parent],
            load_findings=lambda ids: finding_service.get_for_entities(
                ENTITY_STATE_SUPERVISION, list(ids)
            ),
        )
        finding_items = [item for item in items if item.kind == KIND_FINDING]
        self.assertEqual({item.child_id for item in finding_items}, {finding.id})

        open_draft = _draft(
            finding_type=FINDING_TYPE_OPATRENI,
            status=FINDING_STATUS_OTEVRENE,
            client_key="open-opatreni",
            due_date=due,
        )
        open_ready = state_supervision_closure_readiness(
            [open_draft],
            load_tasks=lambda ids: [],
        )
        self.assertEqual(open_ready.open_findings_count, 1)
        self.assertTrue(open_ready.needs_confirmation)

        resolved_ready = state_supervision_closure_readiness(
            [
                _draft(
                    finding_type=FINDING_TYPE_OPATRENI,
                    status=FINDING_STATUS_VYPORADANO,
                    client_key="done-opatreni",
                )
            ],
            load_tasks=lambda ids: [],
        )
        self.assertEqual(resolved_ready.open_findings_count, 0)
        self.assertFalse(resolved_ready.needs_confirmation)

        overdue = attention_for_supervision(parent, findings=[finding], now=now)
        self.assertEqual(overdue.overdue_findings_count, 1)
        self.assertIn(
            ATTENTION_REASON_OVERDUE_FINDINGS,
            {reason.code for reason in overdue.reasons},
        )

        finding_service.update(
            finding.id,
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 9, 1),
        )
        resolved = finding_service.get_by_id(finding.id)
        quiet = attention_for_supervision(parent, findings=[resolved], now=now)
        self.assertEqual(quiet.overdue_findings_count, 0)
        resolved_items = list_state_supervision_deadline_items(
            today=now.date(),
            load_supervisions=lambda: [parent],
            load_findings=lambda ids: finding_service.get_for_entities(
                ENTITY_STATE_SUPERVISION, list(ids)
            ),
        )
        self.assertEqual(
            [item.child_id for item in resolved_items if item.kind == KIND_FINDING],
            [],
        )

        with self.assertRaises(StateSupervisionError):
            state_supervision_finding_service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(finding_type=FINDING_TYPE_POZOROVANI, description="Pozorování")],
            )

    def test_05_proverky_and_audits_keep_shared_opatreni_label(self) -> None:
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_OPATRENI], "Opatření")
        self.assertNotEqual(
            FINDING_TYPE_LABELS[FINDING_TYPE_OPATRENI],
            STATE_SUPERVISION_FINDING_TYPE_LABELS[FINDING_TYPE_OPATRENI],
        )
        self.assertNotIn("Dohodnutý další postup", FINDING_TYPE_LABELS.values())
        self.assertNotIn(FINDING_TYPE_OPATRENI, AUDIT_FINDING_TYPES)
        self.assertNotIn("Dohodnutý další postup", AUDIT_FINDING_TYPE_LABELS.values())

        shared = FindingDialog()
        texts = [shared.type_combo.itemText(i) for i in range(shared.type_combo.count())]
        opatreni_index = shared.type_combo.findData(FINDING_TYPE_OPATRENI)
        self.assertGreaterEqual(opatreni_index, 0)
        self.assertEqual(shared.type_combo.itemText(opatreni_index), "Opatření")
        self.assertNotIn("Dohodnutý další postup", texts)
        shared.close()

    def test_06_open_does_not_write_and_no_migration(self) -> None:
        parent = self._supervision()
        finding_service.create(
            ENTITY_STATE_SUPERVISION,
            parent.id,
            finding_type=FINDING_TYPE_OPATRENI,
            description=f"Existující {self.marker}",
            status=FINDING_STATUS_OTEVRENE,
        )
        before_findings = _count("findings")
        before_ss = _count("state_supervisions")
        commits: list[str] = []
        original = Session.commit

        def spy_commit(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with patch.object(Session, "commit", spy_commit):
            dialog = StateSupervisionEditorDialog(supervision_id=parent.id)
            self.assertEqual(dialog.findings_table.rowCount(), 1)
            self.assertEqual(
                dialog.findings_table.item(0, COL_FINDING_TYPE).text(),
                "Dohodnutý další postup",
            )
            dialog.close()
        self.assertEqual(commits, [])
        self.assertEqual(_count("findings"), before_findings)
        self.assertEqual(_count("state_supervisions"), before_ss)

        self.assertEqual(FINDING_TYPE_OPATRENI, "opatreni")
        columns = {column.name for column in Finding.__table__.columns}
        self.assertIn("finding_type", columns)
        self.assertNotIn("agreed_action", columns)
        source = inspect.getsource(Finding)
        self.assertNotIn("dohodnuty", source.casefold())
        migrations = list(
            Path("moduly/statni_dozor/sluzby").glob("*schema_migration*.py")
        )
        self.assertFalse(
            any("agreed" in path.name or "opatreni" in path.name for path in migrations)
        )


if __name__ == "__main__":
    unittest.main()
