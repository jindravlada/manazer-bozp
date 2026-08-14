"""AUDIT-METHOD-SUPPORT-SNAPSHOT-1-PERF: rychlý startup guard."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-method-support-perf-"))
_WS = _TMP / ".local" / "share" / "manazer-bozp"
_DB = _WS / "databaze" / "manager_bozp.db"


def _active_paths() -> tuple[Path, Path]:
    """Aktuální workspace/DB po případném reloadu storage jinými testy."""
    from core.services.storage_service import storage_service

    storage_service.ensure_structure()
    return Path(storage_service.base), Path(storage_service.database_path)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
        apply_method_support_snapshot_1_schema_ddl,
    )

    apply_method_support_snapshot_1_schema_ddl(_DB)

    from core.database.session import get_session
    from core.database.upgrade_guard import (
        mark_migration_complete,
        prepare_database_for_startup,
    )
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_QUESTION_KIND_SYSTEM,
        METHOD_SUPPORT_STATUS_AVAILABLE,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.modely.audit_question_support_snapshot import (
        AuditQuestionSupportSnapshot,
    )
    from moduly.audity.sluzby.audit_knowledge_service import (
        KnowledgeTreeNode,
        audit_knowledge_service,
    )
    from moduly.audity.sluzby.audit_method_support_backfill_service import (
        BACKFILL_TRANSITION_ID,
    )
    from moduly.audity.sluzby.audit_method_support_integrity_guard import (
        MethodSupportIntegrityError,
        prepare_method_support_integrity_guard,
        run_method_support_fast_integrity_check,
        run_method_support_full_integrity_check,
    )
    from moduly.audity.sluzby.audit_method_support_payload_service import (
        payload_integrity_hash,
    )
    from moduly.audity.sluzby.audit_method_support_photo_service import (
        _sha256_file,
    )
    from moduly.audity.sluzby.audit_method_support_snapshot_1_schema_migration import (
        TRANSITION_ID as SCHEMA_TRANSITION_ID,
    )
    from moduly.audity.sluzby.audit_method_support_snapshot_service import (
        audit_method_support_snapshot_service,
    )
    from moduly.audity.sluzby.audit_v2_create_service import create_audit_with_v2_snapshot
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.audity.sluzby.system_audit_workplace_service import (
        system_audit_workplace_service,
    )


def _fake_tree() -> list[KnowledgeTreeNode]:
    section = {
        "id": "sec_perf",
        "nazev": "Sekce PERF",
        "aktivni": True,
        "cil_overeni": "Ověřit",
        "objektivni_dukazy": [
            {"id": "d1", "nazev": "Důkaz", "poradi": 10, "aktivni": True}
        ],
        "doporucene_rozhovory": [],
        "pozorovani_v_provozu": [],
        "typicke_neshody": [],
        "pkz": [],
        "pozorovani": [],
        "vazby_procesy": [],
        "pozadavky_normy": [],
        "postup_kontroly": [],
        "referencni_fotografie": [],
        "auditni_tvrzeni": [
            {
                "id": "sys_perf",
                "text": "Systémová PERF",
                "poradi": 10,
                "aktivni": True,
                "zavaznost": "stredni",
                "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
                "question_kind": AUDIT_QUESTION_KIND_SYSTEM,
            },
            {
                "id": "ops_perf",
                "text": "Provozní PERF",
                "poradi": 20,
                "aktivni": True,
                "zavaznost": "stredni",
                "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
                "question_kind": "operation",
            },
        ],
        "sekce": [],
    }
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id="proc_perf",
        process_label="Proces PERF",
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id="proc_perf",
            label="Proces PERF",
            process_id="proc_perf",
            process_label="Proces PERF",
            section=None,
            children=(section_node,),
        )
    ]


class MethodSupportPerfTestCase(unittest.TestCase):
    def setUp(self) -> None:
        # Obnov home + storage na tento test temp (ochrana před cizími test moduly).
        self._home_patch = patch.object(Path, "home", return_value=_TMP)
        self._home_patch.start()
        import core.services.storage_service as storage_module
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        import core.database.session as session_module
        importlib.reload(session_module)
        global get_session
        get_session = session_module.get_session
        session_module.reconfigure_database_engine(force=True)
        apply_method_support_snapshot_1_schema_ddl(_DB)

        with get_session() as session:
            session.execute(text("DELETE FROM audit_question_support_snapshots"))
            session.execute(text("DELETE FROM audit_question_snapshots"))
            session.execute(text("DELETE FROM audits"))
            session.commit()
        self.ws, self.db = _active_paths()
        self.system = settings_service.save_workplace(
            name=f"PERF Sys-{uuid.uuid4().hex[:4]}",
            active=True,
            audit_enabled=True,
        )
        self.wp = settings_service.save_workplace(
            name=f"PERF WP-{uuid.uuid4().hex[:4]}",
            active=True,
            audit_enabled=True,
        )
        system_audit_workplace_service.set_system_audit_workplace_id(self.system.id)
        self.tree = _fake_tree()
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=SCHEMA_TRANSITION_ID
        )
        mark_migration_complete(
            self.ws, backup_path=None, transition_id=BACKFILL_TRANSITION_ID
        )
        mark_migration_complete(
            self.ws, backup_path=None, transition_id="audit-snapshot-1a"
        )
        mark_migration_complete(
            self.ws, backup_path=None, transition_id="audit-snapshot-0"
        )
        mark_migration_complete(
            self.ws, backup_path=None, transition_id="audit-snapshot-integrity-seal"
        )

    def tearDown(self) -> None:
        self._home_patch.stop()

    def _create_audit(self):
        audit = create_audit_with_v2_snapshot(
            fields={
                "workplace_id": self.wp.id,
                "workplace_name": self.wp.name,
                "year": 2026,
                "started_at": date(2026, 8, 1),
                "title": "PERF",
            },
            workplace_id=self.wp.id,
            knowledge_tree=self.tree,
            ensure_knowledge=False,
        )
        with get_session() as session:
            from sqlalchemy import select

            supports = list(
                session.scalars(
                    select(AuditQuestionSupportSnapshot).where(
                        AuditQuestionSupportSnapshot.audit_id == int(audit.id)
                    )
                )
            )
            self.assertGreaterEqual(
                len(supports), 1, "očekáván alespoň jeden support snapshot"
            )
        return audit

    def test_01_fast_ok_no_live_tree_no_json_no_photo_hash(self) -> None:
        self._create_audit()
        with (
            patch.object(
                audit_knowledge_service,
                "get_knowledge_tree",
                wraps=audit_knowledge_service.get_knowledge_tree,
            ) as tree,
            patch(
                "moduly.audity.sluzby.audit_method_support_integrity_guard."
                "run_method_support_full_integrity_check",
                wraps=run_method_support_full_integrity_check,
            ) as full,
            patch(
                "moduly.audity.sluzby.audit_method_support_snapshot_service.json.loads",
                wraps=json.loads,
            ) as loads,
            patch(
                "moduly.audity.sluzby.audit_method_support_photo_service._sha256_file",
                wraps=_sha256_file,
            ) as hasher,
        ):
            result = prepare_method_support_integrity_guard(
                workspace_root=self.ws,
                database_path=self.db,
            )
            tree.assert_not_called()
            full.assert_not_called()
            # Fast path nesmí parsovat payloady přes json.loads v full verify
            # (loads může být volán jinde — full verify neběžel).
            self.assertTrue(result.checked)
            self.assertEqual(result.skipped_reason, "fast_ok")
            self.assertIsNotNone(result.fast)
            self.assertTrue(result.fast.ok)
            self.assertGreaterEqual(result.fast.sql_statements, 5)
            self.assertEqual(hasher.call_count, 0)

        # Opakovaný prepare_database — bez nové zálohy a bez get_knowledge_tree
        backups_before = set((self.ws / "zalohy").glob("pre_audit_method_support_snapshot_*"))
        with patch.object(
            audit_knowledge_service,
            "get_knowledge_tree",
            wraps=audit_knowledge_service.get_knowledge_tree,
        ) as tree2:
            prepare_database_for_startup(workspace_root=self.ws, database_path=self.db)
            prepare_database_for_startup(workspace_root=self.ws, database_path=self.db)
            tree2.assert_not_called()
        backups_after = set((self.ws / "zalohy").glob("pre_audit_method_support_snapshot_*"))
        self.assertEqual(backups_before, backups_after)

    def test_02_detect_missing_support_row(self) -> None:
        import sqlite3

        audit = self._create_audit()
        conn = sqlite3.connect(str(self.db))
        try:
            qid = conn.execute(
                "SELECT audit_question_snapshot_id FROM audit_question_support_snapshots "
                "WHERE audit_id=? LIMIT 1",
                (int(audit.id),),
            ).fetchone()
            self.assertIsNotNone(qid)
            conn.execute(
                "DELETE FROM audit_question_support_snapshots WHERE audit_question_snapshot_id=?",
                (qid[0],),
            )
            conn.commit()
        finally:
            conn.close()
        fast = run_method_support_fast_integrity_check(self.db)
        self.assertFalse(fast.ok, fast.problems)
        self.assertTrue(
            any("chybí support" in p or "počtu" in p for p in fast.problems),
            fast.problems,
        )
        with self.assertRaises(MethodSupportIntegrityError):
            prepare_method_support_integrity_guard(
                workspace_root=self.ws, database_path=self.db
            )
        # Nic se nemazalo z otázkových snapshotů
        conn = sqlite3.connect(str(self.db))
        try:
            snaps = conn.execute(
                "SELECT COUNT(*) FROM audit_question_snapshots WHERE audit_id=?",
                (int(audit.id),),
            ).fetchone()[0]
            self.assertGreaterEqual(int(snaps), 1)
        finally:
            conn.close()

    def test_03_detect_count_and_hash_mismatch(self) -> None:
        import sqlite3

        audit = self._create_audit()
        conn = sqlite3.connect(str(self.db))
        try:
            conn.execute(
                "UPDATE audits SET support_snapshot_count=999, "
                "support_integrity_hash=? WHERE id=?",
                ("0" * 64, int(audit.id)),
            )
            conn.commit()
        finally:
            conn.close()
        fast = run_method_support_fast_integrity_check(self.db)
        self.assertFalse(fast.ok, fast.problems)
        joined = " ".join(fast.problems)
        self.assertIn("počtu", joined)
        self.assertIn("support_integrity_hash", joined)

    def test_04_full_check_catches_corrupt_payload(self) -> None:
        import sqlite3

        audit = self._create_audit()
        conn = sqlite3.connect(str(self.db))
        try:
            conn.execute(
                "UPDATE audit_question_support_snapshots "
                "SET support_payload_json=?, integrity_hash=? "
                "WHERE audit_id=?",
                ("{not-json", payload_integrity_hash("{}"), int(audit.id)),
            )
            conn.commit()
        finally:
            conn.close()
        problems = run_method_support_full_integrity_check(self.db)
        self.assertTrue(problems)
        joined = " ".join(problems)
        self.assertTrue(
            "JSON" in joined
            or "Neplatný" in joined
            or "integrity_hash" in joined
            or "support_integrity_hash" in joined,
            joined,
        )

    def test_05_fast_path_does_not_scan_all_payload_bytes(self) -> None:
        """Výkonový assert: fast path neprochází obsah support_payload_json."""
        import inspect

        self._create_audit()
        source = inspect.getsource(run_method_support_fast_integrity_check)
        self.assertNotIn("support_payload_json", source)
        self.assertNotIn("json.loads", source)
        self.assertNotIn("_sha256_file", source)
        self.assertNotIn("get_knowledge_tree", source)
        fast = run_method_support_fast_integrity_check(self.db)
        self.assertTrue(fast.ok, fast.problems)
        self.assertGreaterEqual(fast.sql_statements, 5)
        self.assertLess(fast.elapsed_ms, 2000.0)

    def test_06_missing_schema_detected_when_completed(self) -> None:
        # Simulace: completed, ale tabulka „chybí“ přes needs_* True
        with patch(
            "moduly.audity.sluzby.audit_method_support_integrity_guard."
            "needs_method_support_snapshot_1_schema",
            return_value=True,
        ):
            fast = run_method_support_fast_integrity_check(self.db)
        self.assertFalse(fast.ok)
        self.assertTrue(any("schema" in p.lower() for p in fast.problems))


if __name__ == "__main__":
    unittest.main()
