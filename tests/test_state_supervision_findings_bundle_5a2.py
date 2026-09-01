"""STATE-SUPERVISION-FINDINGS-BUNDLE-5A2: zjištění v atomickém uložení spisu."""

from __future__ import annotations

import importlib
import inspect
import os
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from datetime import datetime
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

    import core.services.attachment_service as attachment_module

    importlib.reload(attachment_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.models.attachment_staging import AttachmentStagingState
    from core.services.attachment_service import attachment_service
    from core.services.storage_service import storage_service
    from core.shared.constants import (
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.repository.finding_repository import FindingRepository
    from core.shared.sluzby.finding_service import FindingService
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.statni_dozor.constants import (
        PARTICIPANT_ROLE_INSPECTOR,
        STATUS_CANCELLED,
        STATUS_CLOSED,
    )
    from moduly.statni_dozor.modely.state_supervision import StateSupervision
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_participant_draft import (
        StateSupervisionParticipantDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
        StateSupervisionRequiredDocumentDraft,
    )
    from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
        StateSupervisionTimelineItemDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
        StateSupervisionFindingService,
        state_supervision_finding_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_participant_service import (
        state_supervision_participant_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
        state_supervision_required_document_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        KEEP_EXISTING,
        StateSupervisionError,
        StateSupervisionService,
        state_supervision_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
        state_supervision_timeline_item_service,
    )


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _write(path: Path, text: str = "obsah") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _draft(**fields) -> StateSupervisionFindingDraft:
    payload = {
        "finding_type": FINDING_TYPE_ZAVADA,
        "description": "Kontrolní zjištění",
    }
    payload.update(fields)
    return StateSupervisionFindingDraft(**payload)


class StateSupervisionFindingsBundle5a2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
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
        self.sources = Path(tempfile.mkdtemp(prefix="ss-find-src-"))
        attachments_dir = storage_service.attachments_dir
        if attachments_dir.exists():
            shutil.rmtree(attachments_dir)
        attachments_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.sources, ignore_errors=True)

    def _source(self, name: str, text: str = "obsah") -> Path:
        return _write(self.sources / name, text)

    def _staging(self, *paths: Path) -> AttachmentStagingState:
        staging = AttachmentStagingState()
        for path in paths:
            staging.add_pending_path(path)
        return staging

    def _docs(self, title: str = "Doklad"):
        return [StateSupervisionRequiredDocumentDraft(title=title)]

    def _timeline(self, title: str = "Úkon"):
        return [StateSupervisionTimelineItemDraft(title=title)]

    def _participants(self, name: str = "Inspektor"):
        return [
            StateSupervisionParticipantDraft(
                role=PARTICIPANT_ROLE_INSPECTOR,
                name_snapshot=name,
            )
        ]

    def _list(self, supervision_id: int):
        return state_supervision_finding_service.list_findings(supervision_id)

    def test_01_old_call_keep_existing_wrapper_and_none(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Původní {self.marker}"
        )
        existing = state_supervision_finding_service.save_state_supervision_findings_batch(
            record.id,
            [_draft(description="Historie", display_order=20)],
            replace_orders=False,
        )[0]
        before = _count("findings")
        with patch.object(
            StateSupervisionFindingService,
            "save_state_supervision_findings_batch",
        ) as batch:
            result = state_supervision_service.save_supervision_bundle(
                supervision_id=record.id,
                fields={"authority_name": f"Bez findings {self.marker}"},
            )
            batch.assert_not_called()
        self.assertEqual(len(result), 3)
        self.assertEqual(result[1], [])
        self.assertEqual(result[2], [])
        listed = self._list(record.id)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, existing.id)
        self.assertEqual(listed[0].description, "Historie")
        self.assertEqual(listed[0].display_order, 20)
        self.assertEqual(_count("findings"), before)

        with patch.object(
            StateSupervisionFindingService,
            "save_state_supervision_findings_batch",
        ) as batch:
            result = state_supervision_service.save_supervision_bundle(
                supervision_id=record.id,
                fields={"authority_name": f"Keep {self.marker}"},
                findings=KEEP_EXISTING,
            )
            batch.assert_not_called()
        self.assertEqual(len(result), 3)

        wrapped = state_supervision_service.save_supervision_with_documents(
            supervision_id=record.id,
            fields={"authority_name": f"Wrapper {self.marker}"},
            documents=self._docs("Z wrapperu"),
        )
        self.assertEqual(len(wrapped), 2)
        listed = self._list(record.id)
        self.assertEqual(listed[0].id, existing.id)
        self.assertEqual(listed[0].description, "Historie")
        wrapper = inspect.getsource(
            StateSupervisionService.save_supervision_with_documents
        )
        self.assertIn("findings=KEEP_EXISTING", wrapper)

        with self.assertRaisesRegex(StateSupervisionError, "None"):
            state_supervision_service.save_supervision_bundle(
                supervision_id=record.id,
                fields={"authority_name": f"None {self.marker}"},
                findings=None,
            )
        self.assertEqual(self._list(record.id)[0].description, "Historie")

    def test_02_new_parent_findings_id_before_flush_one_commit(self) -> None:
        drafts = [
            _draft(description="První", display_order=5),
            _draft(description="Druhé", display_order=1),
        ]
        keys = [draft.client_key for draft in drafts]
        seen: dict[str, object] = {}
        real = StateSupervisionFindingService.save_state_supervision_findings_batch

        def spy(service, supervision_id, batch_drafts, *, session=None, replace_orders=True):
            seen["supervision_id"] = int(supervision_id)
            seen["parent"] = session.get(StateSupervision, int(supervision_id))
            seen["replace_orders"] = replace_orders
            return real(
                service,
                supervision_id,
                batch_drafts,
                session=session,
                replace_orders=replace_orders,
            )

        commits: list[str] = []
        original = Session.commit

        def spy_commit(self, *args, **kwargs):
            commits.append("commit")
            return original(self, *args, **kwargs)

        with (
            patch.object(
                StateSupervisionFindingService,
                "save_state_supervision_findings_batch",
                spy,
            ),
            patch.object(Session, "commit", spy_commit),
        ):
            result = state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Nová {self.marker}"},
                findings=drafts,
            )
        self.assertEqual(len(result), 3)
        record = result[0]
        self.assertGreater(int(seen["supervision_id"]), 0)
        self.assertEqual(seen["supervision_id"], record.id)
        self.assertIsNotNone(seen["parent"])
        self.assertTrue(seen["replace_orders"])
        self.assertEqual(len(commits), 1)
        listed = self._list(record.id)
        self.assertEqual([row.description for row in listed], ["Druhé", "První"])
        self.assertEqual([row.display_order for row in listed], [0, 10])
        self.assertEqual(listed[0].entity_type, ENTITY_STATE_SUPERVISION)
        self.assertEqual(listed[0].entity_id, record.id)
        self.assertEqual(listed[1].entity_id, record.id)
        self.assertIsNone(drafts[0].id)
        self.assertIsNone(drafts[1].id)
        self.assertEqual([draft.client_key for draft in drafts], keys)
        self.assertEqual(drafts[0].description, "První")

    def test_03_existing_create_update_mix_status_task_omit_empty(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Existující {self.marker}"
        )
        created = state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            findings=[_draft(description="Původní", task_id=4242)],
        )
        self.assertEqual(len(created), 3)
        original = self._list(record.id)[0]
        self.assertEqual(original.task_id, 4242)
        before_tasks = _count("tasks")

        mixed = [
            _draft(
                id=original.id,
                description="Upravené",
                status=FINDING_STATUS_V_PROCESU,
                task_id=4242,
                display_order=0,
            ),
            _draft(
                description="Nové",
                finding_type=FINDING_TYPE_NEDOSTATEK,
                display_order=8,
            ),
        ]
        with patch.object(finding_task_service, "create_task_from_finding") as create_task:
            state_supervision_service.save_supervision_bundle(
                supervision_id=record.id,
                fields={"authority_name": record.authority_name},
                findings=mixed,
            )
            create_task.assert_not_called()
        self.assertEqual(_count("tasks"), before_tasks)
        listed = self._list(record.id)
        self.assertEqual(len(listed), 2)
        self.assertEqual(listed[0].id, original.id)
        self.assertEqual(listed[0].description, "Upravené")
        self.assertEqual(listed[0].status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(listed[0].task_id, 4242)
        self.assertEqual(listed[1].description, "Nové")
        self.assertEqual(listed[0].display_order, 0)
        self.assertEqual(listed[1].display_order, 10)

        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            findings=[
                _draft(
                    id=original.id,
                    description="Vypořádané",
                    status=FINDING_STATUS_VYPORADANO,
                    task_id=4242,
                )
            ],
        )
        listed = self._list(record.id)
        self.assertEqual(len(listed), 2)
        self.assertEqual(listed[0].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(listed[0].task_id, 4242)
        self.assertEqual(listed[1].description, "Nové")

        with (
            patch.object(
                StateSupervisionFindingService,
                "save_state_supervision_findings_batch",
            ) as batch,
            patch.object(FindingRepository, "delete") as repo_delete,
            patch.object(FindingService, "delete") as service_delete,
        ):
            state_supervision_service.save_supervision_bundle(
                supervision_id=record.id,
                fields={"authority_name": record.authority_name},
                findings=[],
            )
            batch.assert_not_called()
            repo_delete.assert_not_called()
            service_delete.assert_not_called()
        listed = self._list(record.id)
        self.assertEqual(len(listed), 2)
        self.assertEqual(listed[0].display_order, 0)
        self.assertEqual(listed[1].display_order, 10)
        self.assertEqual(listed[1].description, "Nové")

    def test_04_closed_and_cancelled_keep_findings(self) -> None:
        closed = state_supervision_service.create_supervision(
            authority_name=f"Uzavřená {self.marker}"
        )
        state_supervision_service.save_supervision_bundle(
            supervision_id=closed.id,
            fields={"authority_name": closed.authority_name},
            findings=[_draft(description="Před uzavřením")],
        )
        started = datetime(2026, 3, 1, 8, 0, 0)
        ended = datetime(2026, 3, 1, 16, 0, 0)
        closed_at = datetime(2026, 3, 2, 9, 0, 0)
        state_supervision_service.update_supervision(
            closed.id,
            started_at=started,
            ended_at=ended,
            closed_at=closed_at,
            status=STATUS_CLOSED,
        )
        state_supervision_service.save_supervision_bundle(
            supervision_id=closed.id,
            fields={
                "authority_name": closed.authority_name,
                "started_at": started,
                "ended_at": ended,
                "closed_at": closed_at,
                "status": STATUS_CLOSED,
            },
            findings=[_draft(description="Po uzavření")],
        )
        listed = self._list(closed.id)
        self.assertEqual(
            {row.description for row in listed},
            {"Před uzavřením", "Po uzavření"},
        )

        cancelled = state_supervision_service.create_supervision(
            authority_name=f"Zrušená {self.marker}"
        )
        state_supervision_service.save_supervision_bundle(
            supervision_id=cancelled.id,
            fields={"authority_name": cancelled.authority_name},
            findings=[_draft(description="Před zrušením")],
        )
        state_supervision_service.update_supervision(
            cancelled.id,
            status=STATUS_CANCELLED,
        )
        state_supervision_service.save_supervision_bundle(
            supervision_id=cancelled.id,
            fields={
                "authority_name": cancelled.authority_name,
                "status": STATUS_CANCELLED,
            },
            findings=[],
        )
        self.assertEqual(
            [row.description for row in self._list(cancelled.id)],
            ["Před zrušením"],
        )

    def test_05_finding_error_rolls_back_parent_collections_before_prepare(self) -> None:
        before_s = _count("state_supervisions")
        before_f = _count("findings")
        before_d = _count("state_supervision_required_documents")
        before_t = _count("state_supervision_timeline_items")
        before_p = _count("state_supervision_participants")
        staging = self._staging(self._source("nemá-kopírovat.txt"))
        with patch(
            "core.services.attachment_service.shutil.copy2"
        ) as copy2:
            with self.assertRaises(StateSupervisionError):
                state_supervision_service.save_supervision_bundle(
                    supervision_id=None,
                    fields={"authority_name": f"Chyba {self.marker}"},
                    documents=self._docs(),
                    timeline_items=self._timeline(),
                    participants=self._participants(),
                    findings=[
                        _draft(description="Platné"),
                        _draft(
                            finding_type=FINDING_TYPE_NESHODA,
                            description="Neplatné",
                        ),
                    ],
                    attachments=staging,
                )
            copy2.assert_not_called()
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("findings"), before_f)
        self.assertEqual(_count("state_supervision_required_documents"), before_d)
        self.assertEqual(_count("state_supervision_timeline_items"), before_t)
        self.assertEqual(_count("state_supervision_participants"), before_p)

        existing = state_supervision_service.create_supervision(
            authority_name=f"Hlavní {self.marker}"
        )
        original_name = existing.authority_name
        with self.assertRaises(StateSupervisionError):
            state_supervision_service.save_supervision_bundle(
                supervision_id=existing.id,
                fields={"authority_name": f"Změna {self.marker}"},
                findings=[_draft(description="   ")],
            )
        reloaded = state_supervision_service.get_supervision(existing.id)
        self.assertEqual(reloaded.authority_name, original_name)
        self.assertEqual(self._list(existing.id), [])

    def test_06_attachment_and_commit_errors_roll_back_findings(self) -> None:
        before_s = _count("state_supervisions")
        before_f = _count("findings")
        draft = _draft(description="Má zmizet")
        missing = self.sources / "není.pdf"
        staging = AttachmentStagingState()
        staging.add_pending_path(missing)
        with self.assertRaisesRegex(Exception, "neexistuje"):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Prepare {self.marker}"},
                findings=[draft],
                attachments=staging,
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("findings"), before_f)
        self.assertIsNone(draft.id)
        self.assertEqual(draft.description, "Má zmizet")

        draft2 = _draft(description="Po commitu")
        staging2 = self._staging(self._source("po-commitu.txt"))
        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            with self.assertRaisesRegex(RuntimeError, "commit fail"):
                state_supervision_service.save_supervision_bundle(
                    supervision_id=None,
                    fields={"authority_name": f"Commit {self.marker}"},
                    findings=[draft2],
                    attachments=staging2,
                )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("findings"), before_f)
        self.assertEqual(list(storage_service.attachments_dir.rglob("po-commitu.txt")), [])
        self.assertIsNone(draft2.id)

    def test_07_runtime_order_docs_timeline_participants_findings_prepare(self) -> None:
        order: list[str] = []
        real_docs = (
            state_supervision_required_document_service.save_document_batch
        )
        real_tl = state_supervision_timeline_item_service.save_timeline_batch
        real_part = state_supervision_participant_service.save_participant_batch
        real_find = (
            state_supervision_finding_service.save_state_supervision_findings_batch
        )
        real_prepare = attachment_module.AttachmentService.prepare_attachment_staging

        def wrap_docs(*args, **kwargs):
            order.append("docs")
            return real_docs(*args, **kwargs)

        def wrap_tl(*args, **kwargs):
            order.append("timeline")
            return real_tl(*args, **kwargs)

        def wrap_part(*args, **kwargs):
            order.append("participants")
            return real_part(*args, **kwargs)

        def wrap_find(*args, **kwargs):
            order.append("findings")
            return real_find(*args, **kwargs)

        def wrap_prepare(service, *args, **kwargs):
            order.append("prepare")
            return real_prepare(service, *args, **kwargs)

        with (
            patch.object(
                state_supervision_required_document_service,
                "save_document_batch",
                wrap_docs,
            ),
            patch.object(
                state_supervision_timeline_item_service,
                "save_timeline_batch",
                wrap_tl,
            ),
            patch.object(
                state_supervision_participant_service,
                "save_participant_batch",
                wrap_part,
            ),
            patch.object(
                state_supervision_finding_service,
                "save_state_supervision_findings_batch",
                wrap_find,
            ),
            patch.object(
                attachment_module.AttachmentService,
                "prepare_attachment_staging",
                wrap_prepare,
            ),
        ):
            result = state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Pořadí {self.marker}"},
                documents=self._docs(),
                timeline_items=self._timeline(),
                participants=self._participants(),
                findings=[_draft(description="Zjištění")],
                attachments=self._staging(self._source("příloha.txt")),
            )
        self.assertEqual(
            order,
            ["docs", "timeline", "participants", "findings", "prepare"],
        )
        self.assertEqual(len(result), 3)
        listed = self._list(result[0].id)
        self.assertEqual([row.description for row in listed], ["Zjištění"])

    def test_08_no_side_effects_editor_agenda_and_contract(self) -> None:
        source = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)
        self.assertIn("save_state_supervision_findings_batch", source)
        self.assertIn("prepare_attachment_staging", source)
        self.assertNotIn("finding_service.delete", source)
        self.assertNotIn("self.repository.delete", source)
        self.assertNotIn("finding_task_service", source)
        batch = inspect.getsource(StateSupervisionFindingService)
        self.assertNotIn("finding_task_service", batch)

        from moduly.agenda.ui.agenda_page import AgendaPage
        from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
            StateSupervisionEditorDialog,
        )

        editor = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor.count("self.tabs.addTab("), 5)
        self.assertIn("StateSupervisionFindingDraft", editor)
        self.assertNotIn("save_state_supervision_findings_batch", editor)
        persist = inspect.getsource(StateSupervisionEditorDialog._persist)
        self.assertIn("findings=", persist)
        self.assertIn("ACTION_CREATE_TASK", editor)
        agenda = inspect.getsource(AgendaPage)
        self.assertEqual(agenda.count("self.tabs.addTab("), 4)

        record = state_supervision_service.create_supervision(
            authority_name=f"Open {self.marker}"
        )
        state_supervision_finding_service.save_state_supervision_findings_batch(
            record.id,
            [_draft(description="Načíst")],
        )
        before = _count("findings")
        with patch.object(Session, "commit") as commit:
            listed = self._list(record.id)
            commit.assert_not_called()
        self.assertEqual([row.description for row in listed], ["Načíst"])
        self.assertEqual(_count("findings"), before)
        self.assertEqual(listed[0].status, FINDING_STATUS_OTEVRENE)
        self.assertEqual(listed[0].finding_type, FINDING_TYPE_ZAVADA)


if __name__ == "__main__":
    unittest.main()
