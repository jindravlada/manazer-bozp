"""STATE-SUPERVISION-ATTACHMENTS-BUNDLE-4A2: přílohy v atomickém uložení spisu."""

from __future__ import annotations

import importlib
import inspect
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.orm import Session

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

    from core.models.attachment_staging import AttachmentStagingState
    from core.services.attachment_service import attachment_service
    from core.services.storage_service import storage_service
    from moduly.statni_dozor.constants import (
        ENTITY_STATE_SUPERVISION,
        PARTICIPANT_ROLE_INSPECTOR,
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


class StateSupervisionAttachmentsBundle4a2TestCase(unittest.TestCase):
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
        self.sources = Path(tempfile.mkdtemp(prefix="ss-attach-src-"))
        attachments_dir = storage_service.attachments_dir
        if attachments_dir.exists():
            shutil.rmtree(attachments_dir)
        attachments_dir.mkdir(parents=True, exist_ok=True)
        session = session_module.get_session()
        try:
            from sqlalchemy import delete

            from core.models.attachment import Attachment

            session.execute(delete(Attachment))
            session.commit()
        finally:
            session.close()

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

    def test_old_call_without_attachments_keeps_three_tuple(self) -> None:
        before = _count("attachments")
        with patch.object(
            attachment_module.AttachmentService, "prepare_attachment_staging"
        ) as prepare:
            result = state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Bez příloh {self.marker}"},
            )
        prepare.assert_not_called()
        self.assertEqual(len(result), 3)
        record, docs, items = result
        self.assertEqual(docs, [])
        self.assertEqual(items, [])
        self.assertEqual(_count("attachments"), before)
        target = storage_service.attachments_dir / ENTITY_STATE_SUPERVISION / str(
            record.id
        )
        self.assertFalse(target.exists())

    def test_wrapper_does_not_change_attachments(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Wrapper {self.marker}"
        )
        created = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("původní.txt"))
        )
        path = attachment_service.resolve_path(created)
        result = state_supervision_service.save_supervision_with_documents(
            supervision_id=record.id,
            fields={"authority_name": f"Wrapper {self.marker}"},
            documents=self._docs("Z wrapperu"),
        )
        self.assertEqual(len(result), 2)
        rows = attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, record.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].id, created.id)
        self.assertTrue(path.is_file())
        self.assertEqual(
            [row.title for row in state_supervision_required_document_service.list_documents(record.id)],
            ["Z wrapperu"],
        )

    def test_keep_existing_does_not_call_staging_api(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Keep {self.marker}"
        )
        with (
            patch.object(
                attachment_module.AttachmentService, "prepare_attachment_staging"
            ) as prepare,
            patch.object(
                attachment_module.AttachmentService, "finalize_attachment_changes"
            ) as finalize,
            patch.object(
                attachment_module.AttachmentService, "rollback_attachment_changes"
            ) as rollback,
        ):
            state_supervision_service.save_supervision_bundle(
                supervision_id=record.id,
                fields={"authority_name": f"Keep {self.marker}"},
                attachments=KEEP_EXISTING,
            )
        prepare.assert_not_called()
        finalize.assert_not_called()
        rollback.assert_not_called()
        self.assertFalse(
            (
                storage_service.attachments_dir
                / ENTITY_STATE_SUPERVISION
                / str(record.id)
            ).exists()
        )

    def test_none_attachments_is_rejected(self) -> None:
        with self.assertRaisesRegex(StateSupervisionError, "None"):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"None {self.marker}"},
                attachments=None,
            )

    def test_new_parent_gets_id_before_prepare(self) -> None:
        source = self._source("protokol.pdf", "pdf")
        staging = self._staging(source)
        seen: dict[str, int] = {}
        real_prepare = attachment_module.AttachmentService.prepare_attachment_staging

        def spy(service, entity_type, entity_id, staging_state, session):
            seen["entity_id"] = int(entity_id)
            seen["entity_type"] = str(entity_type)
            return real_prepare(
                service, entity_type, entity_id, staging_state, session
            )

        commits: list[str] = []
        original_commit = Session.commit

        def spy_commit(self, *args, **kwargs):
            commits.append("commit")
            return original_commit(self, *args, **kwargs)

        with (
            patch.object(
                attachment_module.AttachmentService,
                "prepare_attachment_staging",
                spy,
            ),
            patch.object(Session, "commit", spy_commit),
        ):
            result = state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Nový {self.marker}"},
                attachments=staging,
            )
        self.assertEqual(len(result), 3)
        record = result[0]
        self.assertGreater(seen["entity_id"], 0)
        self.assertEqual(seen["entity_id"], record.id)
        self.assertEqual(seen["entity_type"], ENTITY_STATE_SUPERVISION)
        self.assertEqual(len(commits), 1)
        rows = attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, record.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].entity_type, ENTITY_STATE_SUPERVISION)
        self.assertEqual(rows[0].entity_id, record.id)
        stored = attachment_service.resolve_path(rows[0])
        self.assertEqual(
            stored.parent,
            storage_service.attachments_dir
            / ENTITY_STATE_SUPERVISION
            / str(record.id),
        )
        self.assertEqual(stored.read_text(encoding="utf-8"), "pdf")
        self.assertEqual(staging.pending_add_paths, [str(source)])

    def test_existing_parent_add_one_and_many_and_remove(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Existující {self.marker}"
        )
        first = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("stará.txt", "old"))
        )
        old_path = attachment_service.resolve_path(first)

        added = state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            attachments=self._staging(self._source("nová.txt", "new")),
        )
        self.assertEqual(len(added), 3)
        names = {
            row.filename
            for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, record.id
            )
        }
        self.assertEqual(names, {"stará.txt", "nová.txt"})

        many = self._staging(
            self._source("a.txt", "A"),
            self._source("b.txt", "B"),
        )
        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            attachments=many,
        )
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, record.id)),
            4,
        )

        remove = AttachmentStagingState()
        remove.mark_for_removal(first.id)
        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            attachments=remove,
        )
        ids = {
            row.id
            for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, record.id
            )
        }
        self.assertNotIn(first.id, ids)
        self.assertFalse(old_path.exists())
        self.assertEqual(remove.pending_remove_ids, [first.id])

    def test_add_and_remove_together_empty_staging_keeps_unmarked(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Mix {self.marker}"
        )
        keep = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("zůstane.txt"))
        )
        drop = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("odebrat.txt"))
        )
        drop_path = attachment_service.resolve_path(drop)
        staging = self._staging(self._source("přidat.txt"))
        staging.mark_for_removal(drop.id)
        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            attachments=staging,
        )
        rows = attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, record.id)
        ids = {row.id for row in rows}
        names = {row.filename for row in rows}
        self.assertIn(keep.id, ids)
        self.assertNotIn(drop.id, ids)
        self.assertIn("přidat.txt", names)
        self.assertFalse(drop_path.exists())

        empty = AttachmentStagingState()
        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            attachments=empty,
        )
        self.assertEqual(
            {
                row.id
                for row in attachment_service.get_for_entity(
                    ENTITY_STATE_SUPERVISION, record.id
                )
            },
            ids,
        )

    def test_domain_errors_do_not_copy_attachments(self) -> None:
        source = self._source("nepoužít.txt")
        before_s = _count("state_supervisions")
        cases = [
            dict(
                documents=[StateSupervisionRequiredDocumentDraft(title="  ")],
                timeline_items=self._timeline(),
                participants=self._participants(),
            ),
            dict(
                documents=self._docs(),
                timeline_items=[StateSupervisionTimelineItemDraft(title="  ")],
                participants=self._participants(),
            ),
            dict(
                documents=self._docs(),
                timeline_items=self._timeline(),
                participants=[
                    StateSupervisionParticipantDraft(
                        role=PARTICIPANT_ROLE_INSPECTOR,
                        name_snapshot="  ",
                    )
                ],
            ),
        ]
        for kwargs in cases:
            staging = self._staging(source)
            with patch(
                "core.services.attachment_service.shutil.copy2"
            ) as copy2:
                with self.assertRaises(StateSupervisionError):
                    state_supervision_service.save_supervision_bundle(
                        supervision_id=None,
                        fields={"authority_name": f"Chyba {self.marker}"},
                        attachments=staging,
                        **kwargs,
                    )
            copy2.assert_not_called()
            self.assertEqual(staging.pending_add_paths, [str(source)])
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("attachments"), 0)

    def test_prepare_and_second_file_and_commit_failures_roll_back(self) -> None:
        before_s = _count("state_supervisions")
        missing = self.sources / "chybí.txt"
        staging = AttachmentStagingState()
        staging.add_pending_path(missing)
        with self.assertRaisesRegex(Exception, "neexistuje"):
            state_supervision_service.save_supervision_bundle(
                supervision_id=None,
                fields={"authority_name": f"Prepare {self.marker}"},
                documents=self._docs(),
                timeline_items=self._timeline(),
                participants=self._participants(),
                attachments=staging,
            )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(_count("attachments"), 0)
        self.assertEqual(staging.pending_add_paths, [str(missing)])

        first = self._source("první.txt")
        second = self._source("druhý.txt")
        batch = self._staging(first, second)
        real_copy = shutil.copy2
        calls = {"n": 0}

        def flaky(src, dst, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] >= 2:
                raise OSError("disk full")
            return real_copy(src, dst, *args, **kwargs)

        with patch("core.services.attachment_service.shutil.copy2", flaky):
            with self.assertRaisesRegex(OSError, "disk full"):
                state_supervision_service.save_supervision_bundle(
                    supervision_id=None,
                    fields={"authority_name": f"Druhá {self.marker}"},
                    attachments=batch,
                )
        self.assertEqual(_count("state_supervisions"), before_s)
        self.assertEqual(list(storage_service.attachments_dir.rglob("*.txt")), [])
        self.assertEqual(batch.pending_add_paths, [str(first), str(second)])

        existing = state_supervision_service.create_supervision(
            authority_name=f"Původní {self.marker}"
        )
        created = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION,
            existing.id,
            str(self._source("ponechat.txt", "keep")),
        )
        path = attachment_service.resolve_path(created)
        remove = AttachmentStagingState()
        remove.mark_for_removal(created.id)
        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            with self.assertRaisesRegex(RuntimeError, "commit fail"):
                state_supervision_service.save_supervision_bundle(
                    supervision_id=existing.id,
                    fields={"authority_name": f"Změna {self.marker}"},
                    documents=self._docs("Nemá zůstat"),
                    timeline_items=self._timeline("Nemá zůstat"),
                    participants=self._participants("Nemá zůstat"),
                    attachments=remove,
                )
        reloaded = state_supervision_service.get_supervision(existing.id)
        self.assertEqual(reloaded.authority_name, f"Původní {self.marker}")
        self.assertEqual(
            state_supervision_required_document_service.list_documents(existing.id),
            [],
        )
        self.assertEqual(
            state_supervision_timeline_item_service.list_timeline_items(existing.id),
            [],
        )
        self.assertEqual(
            state_supervision_participant_service.list_participants(existing.id),
            [],
        )
        self.assertTrue(path.is_file())
        self.assertEqual(
            [row.id for row in attachment_service.get_for_entity(
                ENTITY_STATE_SUPERVISION, existing.id
            )],
            [created.id],
        )

        with patch.object(Session, "commit", side_effect=RuntimeError("commit fail")):
            with self.assertRaisesRegex(RuntimeError, "commit fail"):
                state_supervision_service.save_supervision_bundle(
                    supervision_id=None,
                    fields={"authority_name": f"Commit {self.marker}"},
                    attachments=self._staging(self._source("po-commitu.txt")),
                )
        self.assertEqual(_count("state_supervisions"), before_s + 1)
        self.assertEqual(list(storage_service.attachments_dir.rglob("po-commitu.txt")), [])

    def test_attachment_error_rolls_back_parent_and_collections(self) -> None:
        existing = state_supervision_service.create_supervision(
            authority_name=f"Hlavní {self.marker}"
        )
        staging = AttachmentStagingState()
        staging.add_pending_path(self.sources / "není.pdf")
        with self.assertRaisesRegex(Exception, "neexistuje"):
            state_supervision_service.save_supervision_bundle(
                supervision_id=existing.id,
                fields={"authority_name": f"Změněno {self.marker}"},
                documents=self._docs("Nový doklad"),
                timeline_items=self._timeline("Nový úkon"),
                participants=self._participants("Nový účastník"),
                attachments=staging,
            )
        loaded = state_supervision_service.get_supervision(existing.id)
        self.assertEqual(loaded.authority_name, f"Hlavní {self.marker}")
        self.assertEqual(
            state_supervision_required_document_service.list_documents(existing.id),
            [],
        )
        self.assertEqual(
            state_supervision_timeline_item_service.list_timeline_items(existing.id),
            [],
        )
        self.assertEqual(
            state_supervision_participant_service.list_participants(existing.id),
            [],
        )
        self.assertEqual(staging.pending_add_paths, [str(self.sources / "není.pdf")])

    def test_finalize_removes_file_and_warning_keeps_success(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Finalize {self.marker}"
        )
        created = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("starý.txt"))
        )
        path = attachment_service.resolve_path(created)
        staging = AttachmentStagingState()
        staging.mark_for_removal(created.id)
        staging.add_pending_path(self._source("nový.txt", "keep-me"))
        result = state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            attachments=staging,
        )
        self.assertEqual(len(result), 3)
        self.assertFalse(path.exists())
        rows = attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, record.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].filename, "nový.txt")
        self.assertTrue(attachment_service.resolve_path(rows[0]).is_file())

        leftover = attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("varovani.txt"))
        )
        leftover_path = attachment_service.resolve_path(leftover)
        warn_staging = AttachmentStagingState()
        warn_staging.mark_for_removal(leftover.id)
        with patch.object(Path, "unlink", side_effect=OSError("denied")):
            with self.assertLogs(
                "moduly.statni_dozor.sluzby.state_supervision_service",
                level="WARNING",
            ) as logs:
                warned = state_supervision_service.save_supervision_bundle(
                    supervision_id=record.id,
                    fields={"authority_name": record.authority_name},
                    attachments=warn_staging,
                )
        self.assertEqual(len(warned), 3)
        self.assertIsNone(
            next(
                (
                    row
                    for row in attachment_service.get_for_entity(
                        ENTITY_STATE_SUPERVISION, record.id
                    )
                    if row.id == leftover.id
                ),
                None,
            )
        )
        self.assertTrue(leftover_path.is_file())
        self.assertTrue(any(str(record.id) in message for message in logs.output))
        self.assertTrue(any("denied" in message for message in logs.output))

    def test_repeated_staging_is_not_deduplicated(self) -> None:
        source = self._source("opakovat.txt", "once")
        staging = self._staging(source)
        first = state_supervision_service.save_supervision_bundle(
            supervision_id=None,
            fields={"authority_name": f"Opak {self.marker}"},
            attachments=staging,
        )[0]
        self.assertEqual(staging.pending_add_paths, [str(source)])
        second = state_supervision_service.save_supervision_bundle(
            supervision_id=first.id,
            fields={"authority_name": first.authority_name},
            attachments=staging,
        )
        self.assertEqual(len(second), 3)
        rows = attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, first.id)
        self.assertEqual(len(rows), 2)
        names = {row.filename for row in rows}
        self.assertEqual(names, {"opakovat.txt", "opakovat_2.txt"})

    def test_documents_timeline_participants_keep_empty_list_semantics(self) -> None:
        record = state_supervision_service.create_supervision(
            authority_name=f"Kolekce {self.marker}"
        )
        state_supervision_required_document_service.create_document(
            record.id, title="Doklad"
        )
        state_supervision_timeline_item_service.create_timeline_item(
            record.id, title="Úkon"
        )
        state_supervision_participant_service.create_participant(
            record.id,
            role=PARTICIPANT_ROLE_INSPECTOR,
            name_snapshot="Účastník",
        )
        attachment_service.add_file(
            ENTITY_STATE_SUPERVISION, record.id, str(self._source("kolekce.txt"))
        )
        state_supervision_service.save_supervision_bundle(
            supervision_id=record.id,
            fields={"authority_name": record.authority_name},
            documents=[],
            timeline_items=[],
            participants=[],
        )
        self.assertEqual(
            state_supervision_required_document_service.list_documents(record.id),
            [],
        )
        self.assertEqual(
            state_supervision_timeline_item_service.list_timeline_items(record.id),
            [],
        )
        self.assertEqual(
            state_supervision_participant_service.list_participants(record.id),
            [],
        )
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_STATE_SUPERVISION, record.id)),
            1,
        )

    def test_bundle_contract_and_editor_still_four_tabs(self) -> None:
        source = inspect.getsource(StateSupervisionService.save_supervision_bundle)
        self.assertEqual(source.count("sess.commit()"), 1)
        self.assertNotIn("session.commit()", source)
        self.assertIn("prepare_attachment_staging", source)
        self.assertIn("finalize_attachment_changes", source)
        self.assertIn("rollback_attachment_changes", source)
        self.assertNotIn("staging.clear()", source)
        wrapper = inspect.getsource(
            StateSupervisionService.save_supervision_with_documents
        )
        self.assertIn("attachments=KEEP_EXISTING", wrapper)

        from moduly.statni_dozor.ui.state_supervision_editor_dialog import (
            StateSupervisionEditorDialog,
        )

        editor = inspect.getsource(StateSupervisionEditorDialog)
        self.assertEqual(editor.count("self.tabs.addTab("), 4)
        self.assertIn("TAB_ANNOUNCEMENT", editor)
        self.assertIn("TAB_SUBJECT_PREPARATION", editor)
        self.assertIn("TAB_COURSE", editor)
        self.assertIn("TAB_CONCLUSION", editor)
        self.assertNotIn("prepare_attachment_staging", editor)
        self.assertNotIn("pending_add_paths", editor)
        init = inspect.getsource(StateSupervisionEditorDialog.__init__)
        self.assertNotIn("save_supervision_bundle", init)


if __name__ == "__main__":
    unittest.main()
