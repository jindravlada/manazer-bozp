"""STATE-SUPERVISION-FINDINGS-CORE-5A1: společný základ zjištění kontroly."""

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

from sqlalchemy.orm import Session

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

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
        CONTROL_RESULT_PARENT_ENTITY_TYPES,
        ENTITY_ACCIDENT,
        ENTITY_AUDITY,
        ENTITY_MU_INVESTIGATION,
        ENTITY_PROVERKY,
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_PORUSENI_PREDPISU,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_ZAVADA,
        FINDING_TYPE_ZJISTENI,
        VALID_ENTITY_TYPES,
        VALID_FINDING_TYPES,
        VALID_LINK_ENTITY_TYPES,
    )
    from core.shared.finding_display import FINDING_TYPE_LABELS
    from core.shared.modely.finding import Finding
    from core.shared.repository.finding_repository import FindingRepository
    from core.shared.sluzby.finding_service import FindingService, finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from core.services.storage_service import storage_service
    from moduly.audity.constants import (
        AUDIT_FINDING_TYPE_LABELS,
        AUDIT_FINDING_TYPE_PKZ,
        KNOWLEDGE_EDITOR_SECTION_EDITABLE_LIST_FIELDS,
    )
    from moduly.statni_dozor.constants import (
        ENTITY_STATE_SUPERVISION as SS_ENTITY_STATE_SUPERVISION,
        STATE_SUPERVISION_FINDING_TYPES,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        is_state_supervision_finding_type,
    )
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
        StateSupervisionFindingService,
        save_state_supervision_findings_batch,
        state_supervision_finding_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _draft(**fields) -> StateSupervisionFindingDraft:
    payload = {
        "finding_type": FINDING_TYPE_ZAVADA,
        "description": "Kontrolní zjištění",
    }
    payload.update(fields)
    return StateSupervisionFindingDraft(**payload)


class StateSupervisionFindingsCore5a1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.marker = uuid.uuid4().hex[:8]
        self.service = state_supervision_finding_service

    def _supervision(self, **fields):
        payload = {"authority_name": f"OIP {self.marker}"}
        payload.update(fields)
        return state_supervision_service.create_supervision(**payload)

    def test_01_entity_type_and_finding_subset(self) -> None:
        self.assertEqual(ENTITY_STATE_SUPERVISION, "state_supervision")
        self.assertIs(ENTITY_STATE_SUPERVISION, SS_ENTITY_STATE_SUPERVISION)
        self.assertIn(ENTITY_STATE_SUPERVISION, VALID_ENTITY_TYPES)
        self.assertNotIn(ENTITY_STATE_SUPERVISION, VALID_LINK_ENTITY_TYPES)
        self.assertNotIn(ENTITY_STATE_SUPERVISION, CONTROL_RESULT_PARENT_ENTITY_TYPES)

        expected = {
            FINDING_TYPE_PRILEZITOST,
            FINDING_TYPE_NEDOSTATEK,
            FINDING_TYPE_ZAVADA,
            FINDING_TYPE_PORUSENI_PREDPISU,
            FINDING_TYPE_ZJISTENI,
        }
        self.assertEqual(STATE_SUPERVISION_FINDING_TYPES, expected)
        for code in expected:
            self.assertIn(code, VALID_FINDING_TYPES)
            self.assertTrue(is_state_supervision_finding_type(code))
        self.assertFalse(is_state_supervision_finding_type(FINDING_TYPE_NESHODA))
        self.assertNotIn("pkz", VALID_FINDING_TYPES)
        self.assertNotIn("PKZ", VALID_FINDING_TYPES)
        self.assertIn("pkz", KNOWLEDGE_EDITOR_SECTION_EDITABLE_LIST_FIELDS)

        self.assertEqual(
            FINDING_TYPE_LABELS[FINDING_TYPE_PRILEZITOST],
            "Příležitost ke zlepšování",
        )
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_NEDOSTATEK], "Nedostatek")
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_ZAVADA], "Závada")
        self.assertEqual(
            FINDING_TYPE_LABELS[FINDING_TYPE_PORUSENI_PREDPISU],
            "Porušení předpisu",
        )
        self.assertEqual(FINDING_TYPE_LABELS[FINDING_TYPE_ZJISTENI], "Zjištění")
        self.assertEqual(
            AUDIT_FINDING_TYPE_LABELS[AUDIT_FINDING_TYPE_PKZ],
            "Příležitost ke zlepšování",
        )

    def test_02_draft_client_key_and_fields(self) -> None:
        draft = StateSupervisionFindingDraft(
            finding_type=FINDING_TYPE_NEDOSTATEK,
            description="První řádek\nDruhý řádek — stroj v hale.",
            source_area_label="Sklad chemikálií",
        )
        self.assertIsNone(draft.id)
        self.assertTrue(draft.client_key)
        key = draft.client_key
        draft.description = "Upravený popis"
        draft.display_order = 40
        self.assertEqual(draft.client_key, key)
        other = _draft(description="Jiné")
        self.assertNotEqual(draft.client_key, other.client_key)
        self.assertEqual(draft.source_area_label, "Sklad chemikálií")
        self.assertIsNone(draft.task_id)

        parent = self._supervision()
        saved = self.service.save_state_supervision_findings_batch(
            parent.id,
            [draft],
        )
        self.assertEqual(saved[0].description, "Upravený popis")
        self.assertEqual(saved[0].source_area_label, "Sklad chemikálií")
        self.assertIsNone(draft.id)
        self.assertEqual(draft.client_key, key)

        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(description="   \n  ")],
            )

    def test_03_all_five_types_and_reject_others(self) -> None:
        parent = self._supervision()
        drafts = [
            _draft(finding_type=code, description=f"Text {code}", display_order=index)
            for index, code in enumerate(sorted(STATE_SUPERVISION_FINDING_TYPES))
        ]
        saved = self.service.save_state_supervision_findings_batch(parent.id, drafts)
        self.assertEqual(len(saved), 5)
        self.assertEqual(
            {row.finding_type for row in saved},
            STATE_SUPERVISION_FINDING_TYPES,
        )
        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(finding_type=FINDING_TYPE_NESHODA, description="Neshoda")],
            )
        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(finding_type=FINDING_TYPE_POZOROVANI, description="Pozorování")],
            )
        self.assertEqual(len(self.service.list_findings(parent.id)), 5)

    def test_04_task_id_preserved_without_creating_task(self) -> None:
        parent = self._supervision()
        before_tasks = _count("tasks")
        with patch.object(finding_task_service, "create_task_from_finding") as create_task:
            saved = self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(description="S úkolem", task_id=4242)],
            )
            create_task.assert_not_called()
        self.assertEqual(saved[0].task_id, 4242)
        self.assertEqual(_count("tasks"), before_tasks)

        updated = self.service.save_state_supervision_findings_batch(
            parent.id,
            [
                _draft(
                    id=saved[0].id,
                    description="Po úpravě",
                    task_id=None,
                )
            ],
        )
        self.assertEqual(updated[0].task_id, 4242)
        self.assertEqual(_count("tasks"), before_tasks)

    def test_05_own_session_batch_create_update_and_order(self) -> None:
        parent = self._supervision()
        drafts = [
            _draft(description="C", display_order=50),
            _draft(description="A", display_order=1),
            _draft(description="B", display_order=1),
        ]
        commits: list[str] = []
        original = Session.commit

        def spy_commit(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with patch.object(Session, "commit", spy_commit):
            saved = save_state_supervision_findings_batch(parent.id, drafts)
        self.assertEqual(len(commits), 1)
        self.assertEqual([row.description for row in saved], ["A", "B", "C"])
        self.assertEqual([row.display_order for row in saved], [0, 10, 20])

        first_id = saved[0].id
        mixed = [
            _draft(id=first_id, description="A upraveno", display_order=0),
            _draft(description="D nové", display_order=5),
        ]
        mixed_saved = self.service.save_state_supervision_findings_batch(
            parent.id,
            mixed,
        )
        self.assertEqual(mixed_saved[0].id, first_id)
        self.assertEqual(mixed_saved[0].description, "A upraveno")
        listed = self.service.list_findings(parent.id)
        self.assertEqual(len(listed), 4)
        self.assertEqual(listed[0].description, "A upraveno")
        self.assertEqual(listed[0].display_order, 0)
        self.assertEqual(listed[1].id, saved[1].id)
        self.assertEqual(listed[1].display_order, 10)
        self.assertEqual(listed[2].description, "D nové")
        self.assertEqual(listed[2].display_order, 10)
        self.assertEqual(listed[3].id, saved[2].id)
        self.assertEqual(listed[3].display_order, 20)

    def test_06_empty_batch_and_omitted_are_not_deleted(self) -> None:
        parent = self._supervision()
        saved = self.service.save_state_supervision_findings_batch(
            parent.id,
            [_draft(description="Historie 1"), _draft(description="Historie 2")],
        )
        before = _count("findings")
        with (
            patch.object(FindingRepository, "delete") as repo_delete,
            patch.object(FindingService, "delete") as service_delete,
        ):
            empty = self.service.save_state_supervision_findings_batch(parent.id, [])
            self.assertEqual(empty, [])
            listed = self.service.list_findings(parent.id)
            self.assertEqual(len(listed), 2)
            only_first = self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(id=saved[0].id, description="Historie 1b")],
            )
            self.assertEqual(len(only_first), 1)
            remaining = self.service.list_findings(parent.id)
            self.assertEqual(len(remaining), 2)
            self.assertEqual(
                {row.description for row in remaining},
                {"Historie 1b", "Historie 2"},
            )
            repo_delete.assert_not_called()
            service_delete.assert_not_called()
        self.assertEqual(_count("findings"), before)
        source = inspect.getsource(StateSupervisionFindingService)
        self.assertNotIn("self.repository.delete", source)
        self.assertNotIn("finding_service.delete", source)
        self.assertNotIn("delete_for_entity", source)
        self.assertNotIn("finding_task_service", source)

    def test_07_foreign_and_other_entity_rejected(self) -> None:
        parent = self._supervision()
        other = self._supervision(authority_name=f"KHS {self.marker}")
        foreign = self.service.save_state_supervision_findings_batch(
            other.id,
            [_draft(description="Cizí kontrola")],
        )[0]
        audit_finding = finding_service.create(
            ENTITY_AUDITY,
            9001,
            finding_type=FINDING_TYPE_NESHODA,
            description="Auditní neshoda",
        )
        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(id=foreign.id, description="Únos")],
            )
        reloaded = finding_service.get_by_id(foreign.id)
        assert reloaded is not None
        self.assertEqual(reloaded.entity_id, other.id)
        self.assertEqual(reloaded.description, "Cizí kontrola")

        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [_draft(id=audit_finding.id, description="Cizí typ")],
            )
        audit_reloaded = finding_service.get_by_id(audit_finding.id)
        assert audit_reloaded is not None
        self.assertEqual(audit_reloaded.entity_type, ENTITY_AUDITY)
        self.assertEqual(audit_reloaded.description, "Auditní neshoda")
        self.assertEqual(self.service.list_findings(parent.id), [])
        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                9_999_999,
                [_draft(description="Bez rodiče")],
            )

    def test_08_caller_owned_session_and_rollback(self) -> None:
        sess = get_session()
        draft = _draft(description="Jen flush")
        try:
            record = state_supervision_service.create_supervision(
                authority_name=f"Flush {self.marker}",
                session=sess,
            )
            sess.flush()
            parent_id = int(record.id)
            self.assertGreater(parent_id, 0)
            with patch.object(Session, "commit") as commit:
                saved = self.service.save_state_supervision_findings_batch(
                    parent_id,
                    [draft],
                    session=sess,
                )
                commit.assert_not_called()
            self.assertIsNone(draft.id)
            self.assertIsNotNone(saved[0].id)
            self.assertEqual(len(self.service.list_findings(parent_id, session=sess)), 1)
            sess.rollback()
        finally:
            sess.close()
        self.assertIsNone(draft.id)
        self.assertIsNone(state_supervision_service.get_supervision(parent_id))

        parent = self._supervision()
        original = self.service.save_state_supervision_findings_batch(
            parent.id,
            [_draft(description="Původní text")],
        )[0]
        update_draft = _draft(id=original.id, description="Nový text")
        new_draft = _draft(description="Nemá zůstat")
        sess = get_session()
        try:
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [update_draft, new_draft],
                session=sess,
            )
            self.assertEqual(update_draft.id, original.id)
            self.assertIsNone(new_draft.id)
            sess.rollback()
        finally:
            sess.close()
        listed = self.service.list_findings(parent.id)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].description, "Původní text")
        self.assertIsNone(new_draft.id)

    def test_09_second_draft_error_rolls_back_first(self) -> None:
        parent = self._supervision()
        before = _count("findings")
        with self.assertRaises(StateSupervisionError):
            self.service.save_state_supervision_findings_batch(
                parent.id,
                [
                    _draft(description="Platné"),
                    _draft(finding_type=FINDING_TYPE_NESHODA, description="Neplatné"),
                ],
            )
        self.assertEqual(_count("findings"), before)
        self.assertEqual(self.service.list_findings(parent.id), [])

    def test_10_list_all_statuses_sort_and_no_write(self) -> None:
        parent = self._supervision()
        self.assertEqual(self.service.list_findings(parent.id), [])
        self.service.save_state_supervision_findings_batch(
            parent.id,
            [
                _draft(
                    description="Otevřené",
                    status=FINDING_STATUS_OTEVRENE,
                    display_order=20,
                ),
                _draft(
                    description="Vypořádané",
                    status=FINDING_STATUS_VYPORADANO,
                    display_order=0,
                    resolution_note="Hotovo",
                ),
                _draft(
                    description="V procesu",
                    status=FINDING_STATUS_V_PROCESU,
                    display_order=10,
                ),
            ],
        )
        with patch.object(Session, "commit") as commit:
            listed = self.service.list_findings(parent.id)
            commit.assert_not_called()
        self.assertEqual(
            [row.description for row in listed],
            ["Vypořádané", "V procesu", "Otevřené"],
        )
        self.assertEqual(listed[0].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(listed[0].resolved_at, date.today())
        self.assertEqual(
            [row.display_order for row in listed],
            [0, 10, 20],
        )

        started = datetime(2026, 3, 1, 8, 0, 0)
        ended = datetime(2026, 3, 1, 16, 0, 0)
        closed = datetime(2026, 3, 2, 9, 0, 0)
        state_supervision_service.update_supervision(
            parent.id,
            started_at=started,
            ended_at=ended,
            closed_at=closed,
            status=STATUS_CLOSED,
        )
        self.assertEqual(len(self.service.list_findings(parent.id)), 3)
        self.service.save_state_supervision_findings_batch(parent.id, [])
        self.assertEqual(len(self.service.list_findings(parent.id)), 3)

        cancelled = self._supervision(authority_name=f"Zrušená {self.marker}")
        self.service.save_state_supervision_findings_batch(
            cancelled.id,
            [_draft(description="Před zrušením")],
        )
        state_supervision_service.update_supervision(
            cancelled.id,
            status=STATUS_CANCELLED,
        )
        rows = self.service.list_findings(cancelled.id)
        self.assertEqual([row.description for row in rows], ["Před zrušením"])

    def test_11_finding_service_and_other_modules_still_work(self) -> None:
        base = uuid.uuid4().int % 10**8 + 1
        audit = finding_service.create(
            ENTITY_AUDITY,
            base,
            finding_type=FINDING_TYPE_NESHODA,
            description="Audit",
        )
        inspection = finding_service.create(
            ENTITY_PROVERKY,
            base + 1,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Prověrka",
        )
        accident = finding_service.create(
            ENTITY_ACCIDENT,
            base + 2,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Úraz",
        )
        mu = finding_service.create(
            ENTITY_MU_INVESTIGATION,
            base + 3,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="MU",
        )
        self.assertEqual(finding_service.get_by_id(audit.id).description, "Audit")
        self.assertEqual(
            [row.description for row in finding_service.get_for_entity(ENTITY_PROVERKY, base + 1)],
            ["Prověrka"],
        )
        self.assertEqual(inspection.entity_type, ENTITY_PROVERKY)
        updated = finding_service.update(accident.id, description="Úraz upraven")
        assert updated is not None
        self.assertEqual(updated.description, "Úraz upraven")
        self.assertTrue(finding_service.delete(mu.id))
        self.assertIsNone(finding_service.get_by_id(mu.id))
        summary = finding_service.summarize(ENTITY_AUDITY, base)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary[FINDING_TYPE_NESHODA], 1)

        sig = inspect.signature(FindingService.delete)
        self.assertNotIn("session", sig.parameters)
        ss = self._supervision()
        ss_finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            ss.id,
            finding_type=FINDING_TYPE_ZAVADA,
            description="Přes FindingService",
        )
        self.assertEqual(ss_finding.entity_type, ENTITY_STATE_SUPERVISION)
        self.assertEqual(len(self.service.list_findings(ss.id)), 1)

    def test_12_bundle_ui_tasks_and_navigation_unchanged(self) -> None:
        bundle = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertIn("(kontrola, doklady, průběh)", bundle)
        self.assertEqual(bundle.count("sess.commit()"), 1)

        task_source = inspect.getsource(finding_task_service.__class__)
        self.assertNotIn("state_supervision", task_source)
        self.assertNotIn("ENTITY_STATE_SUPERVISION", task_source)

        from moduly.agenda.ui.agenda_page import AgendaPage
        from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
            StateSupervisionEditorDialog,
        )

        editor_source = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor_source.count("self.tabs.addTab("), 5)
        self.assertNotIn("StateSupervisionFindingDraft", editor_source)
        self.assertNotIn("save_state_supervision_findings_batch", editor_source)
        self.assertNotIn("Vytvořit úkol", editor_source)

        agenda_source = inspect.getsource(AgendaPage)
        self.assertEqual(agenda_source.count("self.tabs.addTab("), 4)

        from moduly.externi_audity.modely import ExternalAuditFinding

        self.assertNotEqual(ExternalAuditFinding.__tablename__, Finding.__tablename__)
        self.assertEqual(Finding.__tablename__, "findings")
