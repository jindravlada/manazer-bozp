"""AUDIT-SNAPSHOT-1a-fix: ověření stavu backfillu proti DB + rozsah *.mbbackup."""

from __future__ import annotations

import importlib
import os
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-snapshot-1a-fix-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
session_module.reconfigure_database_engine(force=True)

from core.database.database_initializer import (  # noqa: E402
    _ensure_control_result_columns,
    initialize_database,
)

initialize_database()

from core.backup.package_create import create_instance_backup  # noqa: E402
from core.database.upgrade_guard import (  # noqa: E402
    is_transition_complete,
    mark_migration_complete,
    read_migration_state,
    write_migration_state,
)
from core.shared.constants import (  # noqa: E402
    CONTROL_RESULT_VYHOVUJE,
    ENTITY_AUDITY,
)
from core.shared.sluzby.control_result_service import (  # noqa: E402
    ControlPointContext,
    control_result_service,
)
from moduly.audity.constants import (  # noqa: E402
    AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
    AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
)
from moduly.audity.modely.audit import Audit  # noqa: E402
from moduly.audity.modely.audit_question_snapshot import (  # noqa: E402
    AuditQuestionSnapshot,
)
from moduly.audity.sluzby.audit_knowledge_service import (  # noqa: E402
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.audit_snapshot_backfill_service import (  # noqa: E402
    TRANSITION_ID as BACKFILL_TRANSITION,
    AuditSnapshotBackfillError,
    prepare_audit_snapshot_backfill,
)
from moduly.audity.sluzby.audit_snapshot_schema_migration import (  # noqa: E402
    prepare_audit_snapshot_schema,
)
from sqlalchemy import create_engine, select  # noqa: E402

from core.database.session import get_session  # noqa: E402

_WS = storage_module.storage_service.base
_DB = storage_module.storage_service.database_path


def _count(table: str) -> int:
    conn = sqlite3.connect(str(_DB))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _clear_backfill_state() -> None:
    state = read_migration_state(_WS)
    completed = [
        item
        for item in (state.get("completed_transitions") or [])
        if item != BACKFILL_TRANSITION
    ]
    state["completed_transitions"] = completed
    state["in_progress"] = None
    if (state.get("last_completed") or {}).get("transition_id") == BACKFILL_TRANSITION:
        state["last_completed"] = None
    if (state.get("last_failed") or {}).get("transition_id") == BACKFILL_TRANSITION:
        state["last_failed"] = None
    write_migration_state(_WS, state)
    for backup in (_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"):
        backup.unlink()


def _delete_all_snapshots_and_reset_audits() -> None:
    with get_session() as session:
        for row in list(session.scalars(select(AuditQuestionSnapshot))):
            session.delete(row)
        for audit in list(session.scalars(select(Audit))):
            audit.methodology_source = None
            audit.questions_frozen_at = None
            audit.methodology_generation = None
        session.commit()


def _cr_fingerprint() -> list[tuple]:
    conn = sqlite3.connect(str(_DB))
    try:
        cols = [
            "id",
            "entity_type",
            "entity_id",
            "source_area_id",
            "source_area_label",
            "source_section_id",
            "source_section_label",
            "source_control_point_id",
            "source_control_point_label",
            "result",
            "shared_experience",
            "photo_path",
            "note",
            "recorded_by_name",
        ]
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM control_results ORDER BY id"
        ).fetchall()
        return [tuple(r) for r in rows]
    finally:
        conn.close()


def _first_assertion(process_id: str):
    tree = audit_knowledge_service.get_knowledge_tree(ensure=False)
    for root in tree:
        if root.process_id != process_id:
            continue
        for node in root.children:
            section = node.section or {}
            questions = audit_knowledge_service.get_audit_questions(section)
            if questions:
                q = questions[0]
                return (
                    process_id,
                    root.label,
                    str(section.get("id") or node.node_id),
                    str(section.get("nazev") or node.label),
                    str(q.get("id")),
                    str(q.get("text") or q.get("nazev")),
                )
    raise AssertionError(f"Žádné tvrzení v procesu {process_id}")


class AuditSnapshot1aFixTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._home = patch.object(Path, "home", return_value=_HOME)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        initialize_database()
        prepare_audit_snapshot_schema(
            workspace_root=storage_module.storage_service.base,
            database_path=storage_module.storage_service.database_path,
        )
        cls.processes = [
            p
            for p in audit_knowledge_service.get_processes(ensure=True)
            if p.has_knowledge_file
        ]
        if not cls.processes:
            raise AssertionError("Očekáván alespoň 1 proces s knowledge souborem")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self._home_ctx = patch.object(Path, "home", return_value=_HOME)
        self._home_ctx.start()
        importlib.reload(storage_module)
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)
        global _WS, _DB
        _WS = storage_module.storage_service.base
        _DB = storage_module.storage_service.database_path
        _clear_backfill_state()
        _delete_all_snapshots_and_reset_audits()
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def tearDown(self) -> None:
        self._home_ctx.stop()

    def test_complete_state_with_correct_db_is_noop(self) -> None:
        audit = audit_service.create_audit(title="Complete OK")
        first = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertTrue(first.migrated)
        snaps = _count("audit_question_snapshots")
        backups_before = list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"))
        self.assertEqual(len(backups_before), 1)
        fp_before = _cr_fingerprint()

        second = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertFalse(second.migrated)
        self.assertEqual(second.skipped_reason, "transition_already_complete")
        self.assertIsNone(second.pre_migration_backup_path)
        self.assertEqual(_count("audit_question_snapshots"), snaps)
        self.assertEqual(
            list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*")),
            backups_before,
        )
        self.assertEqual(_cr_fingerprint(), fp_before)
        reloaded = audit_service.get_by_id(audit.id)
        self.assertEqual(
            reloaded.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )

    def test_complete_state_with_db_restored_pre_backfill_repairs(self) -> None:
        """Stav completed + DB před backfillem → invalidace, nová záloha, backfill."""
        audit = audit_service.create_audit(title="Restore DB only")
        info = _first_assertion(self.processes[0].id)
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label=info[5],
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="zachovat",
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertTrue(is_transition_complete(_WS, BACKFILL_TRANSITION))
        fp_before = _cr_fingerprint()

        # Simulace obnovy pouze DB před backfillem (migration_state zůstává completed).
        with get_session() as session:
            for row in list(session.scalars(select(AuditQuestionSnapshot))):
                session.delete(row)
            db_audit = session.get(Audit, audit.id)
            assert db_audit is not None
            db_audit.methodology_source = None
            db_audit.questions_frozen_at = None
            db_audit.methodology_generation = None
            session.commit()

        self.assertTrue(is_transition_complete(_WS, BACKFILL_TRANSITION))
        backups_before = list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"))

        result = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertTrue(result.migrated)
        self.assertEqual(result.processed_audits, 1)
        self.assertIsNotNone(result.pre_migration_backup_path)
        self.assertTrue(result.pre_migration_backup_path.is_file())
        backups_after = list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"))
        self.assertGreater(len(backups_after), len(backups_before))
        self.assertTrue(is_transition_complete(_WS, BACKFILL_TRANSITION))
        self.assertEqual(_cr_fingerprint(), fp_before)

        reloaded = audit_service.get_by_id(audit.id)
        self.assertEqual(reloaded.methodology_source, AUDIT_METHODOLOGY_SOURCE_SNAPSHOT)
        self.assertEqual(
            reloaded.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )
        snaps_after = _count("audit_question_snapshots")
        self.assertGreater(snaps_after, 0)

        # Bez duplicit po opravě.
        third = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertFalse(third.migrated)
        self.assertEqual(_count("audit_question_snapshots"), snaps_after)

    def test_partial_snapshot_stops_without_rewrite(self) -> None:
        audit = audit_service.create_audit(title="Partial")
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        snaps_before = _count("audit_question_snapshots")
        fp_before = _cr_fingerprint()
        with get_session() as session:
            snap = session.scalar(
                select(AuditQuestionSnapshot).where(
                    AuditQuestionSnapshot.audit_id == audit.id
                )
            )
            self.assertIsNotNone(snap)
            session.delete(snap)
            session.commit()

        self.assertTrue(is_transition_complete(_WS, BACKFILL_TRANSITION))
        with self.assertRaises(AuditSnapshotBackfillError) as ctx:
            prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertIn("nekonzistentní", str(ctx.exception).lower())

        self.assertEqual(_count("audit_question_snapshots"), snaps_before - 1)
        self.assertEqual(_cr_fingerprint(), fp_before)
        reloaded = audit_service.get_by_id(audit.id)
        self.assertEqual(reloaded.methodology_source, AUDIT_METHODOLOGY_SOURCE_SNAPSHOT)
        self.assertEqual(
            reloaded.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )

    def test_other_generation_untouched(self) -> None:
        legacy = audit_service.create_audit(title="Legacy")
        future = audit_service.create_audit(title="Future gen")
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)

        frozen = datetime(2030, 1, 2, 3, 4, 5)
        with get_session() as session:
            fut = session.get(Audit, future.id)
            assert fut is not None
            fut.methodology_generation = "future-v9"
            fut.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
            fut.questions_frozen_at = frozen
            # Nahraď snapshoty future auditu unikátními řádky jiné generace.
            for row in list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == future.id
                    )
                )
            ):
                session.delete(row)
            session.flush()
            session.add(
                AuditQuestionSnapshot(
                    audit_id=future.id,
                    process_id="future_p",
                    process_name="Future process",
                    section_id="future_s",
                    section_name="Future section",
                    assertion_id="future_q",
                    assertion_text="Future question",
                    verification_type="dokumentace",
                    severity="stredni",
                    question_kind="future",
                    display_order=1,
                    created_at=frozen,
                )
            )
            session.commit()

        snaps_future_before = _count("audit_question_snapshots")
        # Simuluj chybějící legacy backfill u legacy auditu + completed stav.
        with get_session() as session:
            for row in list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == legacy.id
                    )
                )
            ):
                session.delete(row)
            leg = session.get(Audit, legacy.id)
            assert leg is not None
            leg.methodology_source = None
            leg.questions_frozen_at = None
            leg.methodology_generation = None
            session.commit()
        mark_migration_complete(
            _WS, backup_path=None, transition_id=BACKFILL_TRANSITION
        )

        result = prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertTrue(result.migrated)
        self.assertEqual(result.processed_audits, 1)

        reloaded_future = audit_service.get_by_id(future.id)
        self.assertEqual(reloaded_future.methodology_generation, "future-v9")
        self.assertEqual(reloaded_future.questions_frozen_at, frozen)
        with get_session() as session:
            fut_snaps = list(
                session.scalars(
                    select(AuditQuestionSnapshot).where(
                        AuditQuestionSnapshot.audit_id == future.id
                    )
                )
            )
        self.assertEqual(len(fut_snaps), 1)
        self.assertEqual(fut_snaps[0].assertion_id, "future_q")
        self.assertEqual(fut_snaps[0].question_kind, "future")
        self.assertGreater(_count("audit_question_snapshots"), snaps_future_before - 100)

        reloaded_legacy = audit_service.get_by_id(legacy.id)
        self.assertEqual(
            reloaded_legacy.methodology_generation, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
        )

    def test_control_results_values_unchanged_after_repair(self) -> None:
        audit = audit_service.create_audit(title="CR intact")
        info = _first_assertion(self.processes[0].id)
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id=info[0],
                area_label=info[1],
                section_id=info[2],
                section_label=info[3],
                control_point_id=info[4],
                control_point_label=info[5],
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="poznámka X",
            photo_path="photos/a.jpg",
        )
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        fp = _cr_fingerprint()

        with get_session() as session:
            for row in list(session.scalars(select(AuditQuestionSnapshot))):
                session.delete(row)
            db_audit = session.get(Audit, audit.id)
            assert db_audit is not None
            db_audit.methodology_source = None
            db_audit.questions_frozen_at = None
            db_audit.methodology_generation = None
            session.commit()
        mark_migration_complete(
            _WS, backup_path=None, transition_id=BACKFILL_TRANSITION
        )

        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        self.assertEqual(_cr_fingerprint(), fp)

    def test_repeated_start_idempotent(self) -> None:
        audit_service.create_audit(title="Idem 1")
        audit_service.create_audit(title="Idem 2")
        prepare_audit_snapshot_backfill(workspace_root=_WS, database_path=_DB)
        snaps = _count("audit_question_snapshots")
        backups = list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*"))
        for _ in range(3):
            result = prepare_audit_snapshot_backfill(
                workspace_root=_WS, database_path=_DB
            )
            self.assertFalse(result.migrated)
            self.assertEqual(result.skipped_reason, "transition_already_complete")
            self.assertEqual(_count("audit_question_snapshots"), snaps)
            self.assertEqual(
                list((_WS / "zalohy").glob("pre_audit_snapshot_backfill_*")),
                backups,
            )


class MbbackupScopeTestCase(unittest.TestCase):
    """Skutečný rozsah *.mbbackup — DB + workspace/konfigurace včetně migration_state."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mbbackup-scope-"))
        self.ws = self.tmp / "ws"
        self.db_dir = self.tmp / "db"
        self.settings_dir = self.tmp / "settings"
        for path in (self.ws, self.db_dir, self.settings_dir):
            path.mkdir(parents=True)
        for name in ("prilohy", "control_results", "ciselniky", "templates", "konfigurace"):
            (self.ws / name).mkdir()
        self.db = self.db_dir / "manager_bozp.db"
        conn = sqlite3.connect(str(self.db))
        try:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO t(id) VALUES (1)")
            conn.commit()
        finally:
            conn.close()
        (self.ws / "konfigurace" / "migration_state.json").write_text(
            '{"completed_transitions": ["audit-snapshot-1a"], "in_progress": null}\n',
            encoding="utf-8",
        )
        (self.settings_dir / "settings.json").write_text("{}", encoding="utf-8")
        self.backup_path = self.tmp / "scope.mbbackup"

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mbbackup_contains_db_and_migration_state(self) -> None:
        create_instance_backup(
            target_path=self.backup_path,
            workspace_root=self.ws,
            database_path=self.db,
            settings_path=self.settings_dir / "settings.json",
            verify=True,
        )
        with zipfile.ZipFile(self.backup_path, "r") as zf:
            names = set(zf.namelist())
            self.assertIn("database/manager_bozp.db", names)
            self.assertIn("workspace/konfigurace/migration_state.json", names)
            self.assertIn("settings/settings.json", names)
            raw = zf.read("workspace/konfigurace/migration_state.json").decode("utf-8")
            self.assertIn("audit-snapshot-1a", raw)

    def test_db_only_restore_leaves_migration_state_completed(self) -> None:
        """Obnova pouze DB ze zálohy nevrátí migration_state — typický drift."""
        create_instance_backup(
            target_path=self.backup_path,
            workspace_root=self.ws,
            database_path=self.db,
            settings_path=self.settings_dir / "settings.json",
            verify=True,
        )
        # „Live“ DB po backfillu + completed state.
        live_db = self.tmp / "live.db"
        shutil.copy2(self.db, live_db)
        conn = sqlite3.connect(str(live_db))
        try:
            conn.execute("CREATE TABLE audit_question_snapshots (id INTEGER)")
            conn.commit()
        finally:
            conn.close()
        (self.ws / "konfigurace" / "migration_state.json").write_text(
            '{"completed_transitions": ["audit-snapshot-1a"], "in_progress": null}\n',
            encoding="utf-8",
        )

        # Obnova pouze DB z balíčku (bez konfigurace).
        with zipfile.ZipFile(self.backup_path, "r") as zf:
            zf.extract("database/manager_bozp.db", path=self.tmp / "extract")
        restored_db = self.tmp / "extract" / "database" / "manager_bozp.db"
        shutil.copy2(restored_db, live_db)

        conn = sqlite3.connect(str(live_db))
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()
        self.assertNotIn("audit_question_snapshots", tables)
        state = (self.ws / "konfigurace" / "migration_state.json").read_text(
            encoding="utf-8"
        )
        self.assertIn("audit-snapshot-1a", state)


class ControlResultsEnsureAdditiveTestCase(unittest.TestCase):
    def test_ensure_adds_missing_columns_without_changing_existing_values(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="cr-ensure-"))
        db = tmp / "t.db"
        try:
            conn = sqlite3.connect(str(db))
            try:
                conn.execute(
                    """
                    CREATE TABLE control_results (
                        id INTEGER PRIMARY KEY,
                        entity_type VARCHAR(50) NOT NULL,
                        entity_id INTEGER NOT NULL,
                        photo_path VARCHAR(500) DEFAULT '',
                        note TEXT DEFAULT ''
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO control_results(id, entity_type, entity_id, photo_path, note) "
                    "VALUES (1, 'audity', 9, 'p.jpg', 'původní')"
                )
                conn.commit()
            finally:
                conn.close()

            engine = create_engine(f"sqlite:///{db}", future=True)
            with patch(
                "core.database.database_initializer._db_engine", return_value=engine
            ):
                _ensure_control_result_columns()

            conn = sqlite3.connect(str(db))
            try:
                cols = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(control_results)")
                }
                for required in (
                    "source_area_id",
                    "source_area_label",
                    "source_section_id",
                    "source_section_label",
                    "source_control_point_id",
                    "source_control_point_label",
                    "result",
                    "shared_experience",
                    "photo_path",
                    "note",
                    "recorded_by_name",
                    "recorded_at",
                    "created_at",
                    "updated_at",
                ):
                    self.assertIn(required, cols)
                row = conn.execute(
                    "SELECT photo_path, note, entity_type, entity_id FROM control_results WHERE id=1"
                ).fetchone()
                self.assertEqual(row, ("p.jpg", "původní", "audity", 9))
            finally:
                conn.close()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
