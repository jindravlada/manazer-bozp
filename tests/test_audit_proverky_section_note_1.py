"""AUDIT-PROVERKY-SECTION-NOTE-1: souhrnné sdělení za okruh, legacy režim NULL."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _table_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    finally:
        conn.close()


def _seed_pre_section_note_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.exists():
            side.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE audits (
                id INTEGER PRIMARY KEY,
                number VARCHAR(30) DEFAULT '',
                year INTEGER,
                title VARCHAR(250) DEFAULT '',
                status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL,
                silne_stranky TEXT DEFAULT '' NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE bozp_inspections (
                id INTEGER PRIMARY KEY,
                number VARCHAR(30) DEFAULT '',
                year INTEGER,
                title VARCHAR(250) DEFAULT '',
                status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL,
                silne_stranky TEXT DEFAULT '' NOT NULL,
                doporuceni_vedouciho TEXT DEFAULT '' NOT NULL,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE control_results (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50) NOT NULL,
                entity_id INTEGER NOT NULL,
                source_area_id VARCHAR(80) DEFAULT '',
                source_area_label VARCHAR(150) DEFAULT '',
                source_section_id VARCHAR(80) DEFAULT '',
                source_section_label VARCHAR(150) DEFAULT '',
                source_control_point_id VARCHAR(80) DEFAULT '',
                source_control_point_label VARCHAR(200) DEFAULT '',
                result VARCHAR(40) DEFAULT 'nekontrolovano' NOT NULL,
                note TEXT DEFAULT '',
                shared_experience BOOLEAN DEFAULT 0 NOT NULL,
                photo_path VARCHAR(500) DEFAULT '',
                recorded_by_name VARCHAR(150) DEFAULT '',
                recorded_at DATETIME,
                created_at DATETIME,
                updated_at DATETIME
            );
            INSERT INTO audits (id, number, year, title, status)
            VALUES (1, '1/2026', 2026, 'Legacy audit', 'Probíhá');
            INSERT INTO bozp_inspections (id, number, year, title, status)
            VALUES (1, '1/2026', 2026, 'Legacy prověrka', 'Probíhá');
            INSERT INTO control_results (
                id, entity_type, entity_id, source_area_id, source_area_label,
                source_section_id, source_section_label, source_control_point_id,
                source_control_point_label, result, note
            ) VALUES
            (1, 'audity', 1, 'p1', 'Proces', 's1', 'Sekce', 'q1', 'Tvrzení',
             'vyhovuje', 'Poznámka legacy auditu'),
            (2, 'proverky', 1, 'a1', 'Oblast', 's1', 'Sekce', 'k1', 'Bod',
             'vyhovuje', 'Komentář legacy prověrky');
            """
        )
        conn.commit()
    finally:
        conn.close()


_MIG_HOME = Path(tempfile.mkdtemp(prefix="section-note-1-mig-"))
_MIG_HOME_PATCHER = patch.object(Path, "home", return_value=_MIG_HOME)
_MIG_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)

from core.database.upgrade_guard import (  # noqa: E402
    MigrationGuardError,
    PreMigrationBackupError,
    is_migration_failed,
    is_migration_in_progress,
    is_transition_complete,
)
from moduly.audity.sluzby.audit_proverky_section_note_schema_migration import (  # noqa: E402
    BACKUP_NAME_PREFIX,
    EXPECTED_TABLES,
    TRANSITION_ID,
    allocate_audit_proverky_section_note_backup_path,
    apply_audit_proverky_section_note_schema_ddl,
    needs_audit_proverky_section_note_schema,
    prepare_audit_proverky_section_note_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class AuditProverkySectionNoteMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_MIG_HOME)
        self._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

        self.db_path = storage_module.storage_service.database_path
        self.ws = storage_module.storage_service.base
        state_path = self.ws / "konfigurace" / "migration_state.json"
        if state_path.exists():
            state_path.unlink()
        for backup in (self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"):
            backup.unlink()
        _seed_pre_section_note_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_audit_proverky_section_note_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(result.pre_migration_backup_path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertEqual(result.pre_migration_backup_path.suffix, ".mbbackup")

    def test_02_backup_failure_no_schema_change(self) -> None:
        before_tables = _tables(self.db_path)
        before_cols = _table_columns(self.db_path, "audits")
        with patch(
            "moduly.audity.sluzby.audit_proverky_section_note_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_audit_proverky_section_note_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(needs_audit_proverky_section_note_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(_tables(self.db_path), before_tables)
        self.assertEqual(_table_columns(self.db_path, "audits"), before_cols)
        self.assertNotIn("notes_mode", before_cols)

    def test_03_additive_no_backfill_legacy_null(self) -> None:
        note_before = sqlite3.connect(str(self.db_path)).execute(
            "SELECT note FROM control_results WHERE id = 1"
        ).fetchone()[0]
        result = prepare_audit_proverky_section_note_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        self.assertTrue(schema_is_present(self.db_path))
        self.assertTrue(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertIn("notes_mode", _table_columns(self.db_path, "audits"))
        self.assertIn("notes_mode", _table_columns(self.db_path, "bozp_inspections"))
        for table in EXPECTED_TABLES:
            self.assertIn(table, _tables(self.db_path))
            self.assertEqual(_count(self.db_path, table), 0)
        mode = sqlite3.connect(str(self.db_path)).execute(
            "SELECT notes_mode FROM audits WHERE id = 1"
        ).fetchone()[0]
        self.assertIsNone(mode)
        insp_mode = sqlite3.connect(str(self.db_path)).execute(
            "SELECT notes_mode FROM bozp_inspections WHERE id = 1"
        ).fetchone()[0]
        self.assertIsNone(insp_mode)
        note_after = sqlite3.connect(str(self.db_path)).execute(
            "SELECT note FROM control_results WHERE id = 1"
        ).fetchone()[0]
        self.assertEqual(note_after, note_before)
        self.assertEqual(note_after, "Poznámka legacy auditu")

    def test_04_idempotent_repeat(self) -> None:
        first = prepare_audit_proverky_section_note_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))
        self.assertEqual(len(backups_first), 1)
        second = prepare_audit_proverky_section_note_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        backups_second = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))
        self.assertEqual(len(backups_second), 1)
        self.assertEqual(first.pre_migration_backup_path, backups_second[0])

    def test_05_ddl_failure_rolls_back(self) -> None:
        with patch(
            "moduly.audity.sluzby.audit_proverky_section_note_schema_migration."
            "CREATE_AUDIT_SUMMARIES_SQL",
            "CREATE TABLE IF NOT EXISTS audit_section_summaries (",
        ):
            with self.assertRaises(sqlite3.OperationalError):
                apply_audit_proverky_section_note_schema_ddl(self.db_path)
        self.assertNotIn("notes_mode", _table_columns(self.db_path, "audits"))
        self.assertNotIn("audit_section_summaries", _tables(self.db_path))

    def test_06_prepare_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.audity.sluzby.audit_proverky_section_note_schema_migration."
            "apply_audit_proverky_section_note_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_audit_proverky_section_note_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertTrue(needs_audit_proverky_section_note_schema(self.db_path))

    def test_07_allocate_backup_name(self) -> None:
        path = allocate_audit_proverky_section_note_backup_path(self.ws / "zalohy")
        self.assertTrue(path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertTrue(path.name.endswith(".mbbackup"))


_SVC_HOME = Path(tempfile.mkdtemp(prefix="section-note-1-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from sqlalchemy import delete

    from core.database.session import get_session
    from core.export.control_point_appendix import (
        ControlPointAppendixItem,
        build_detailed_control_points_appendix,
        section_summary_paragraphs,
    )
    from core.shared.constants import (
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.section_summary import (
        NOTES_MODE_SECTION_SUMMARY_V1,
        SECTION_SUMMARY_EXPORT_LABEL,
        SECTION_SUMMARY_LABEL,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.verification_type import (
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from core.widgets.control_result_selector import ControlResultSelectorWidget
    from core.widgets.section_summary_edit import SectionSummaryEdit
    from moduly.audity.constants import (
        AUDIT_QUESTION_KIND_SYSTEM,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode
    from moduly.audity.sluzby.audit_program_service import AuditProgramService
    from moduly.audity.sluzby.audit_section_summary_service import (
        audit_section_summary_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_v2_create_service import (
        create_audit_with_v2_snapshot,
        create_manual_audit_with_v2_snapshot,
    )
    from moduly.audity.sluzby.system_audit_workplace_service import (
        system_audit_workplace_service,
    )
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_knowledge_criterion_widget import (
        AuditKnowledgeCriterionWidget,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        COMMISSION_RECORD_LEADER as INSPECTION_LEADER,
        COMMISSION_RECORD_UNION as INSPECTION_UNION,
        COMMISSION_RECORD_WORKPLACE as INSPECTION_WORKPLACE,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG as INSPECTION_DETAILED_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG as INSPECTION_PROTOCOL_CONFIG,
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_generation_service import (
        BozpInspectionGenerationService,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.inspection_deferred_edits import InspectionDeferredEdits
    from moduly.proverky.sluzby.inspection_section_summary_service import (
        inspection_section_summary_service,
    )
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _audit_section(*, section_id: str, title: str, question_id: str, verification_type: str):
    return {
        "id": section_id,
        "nazev": title,
        "aktivni": True,
        "auditni_tvrzeni": [
            {
                "id": question_id,
                "text": f"Tvrzení {question_id}",
                "aktivni": True,
                "poradi": 10,
                "verification_type": verification_type,
                "zavaznost": "stredni",
                "question_kind": AUDIT_QUESTION_KIND_SYSTEM,
            }
        ],
    }


def _inspection_section(*, section_id: str, title: str, point_id: str, verification_type: str):
    return {
        "id": section_id,
        "nazev": title,
        "popis": f"Popis {title}",
        "aktivni": True,
        "kontrolni_body": [
            {
                "id": point_id,
                "nazev": f"Bod {point_id}",
                "aktivni": True,
                "poradi": 10,
                "verification_type": verification_type,
                "zavaznost": "stredni",
            }
        ],
    }


def _fake_tree() -> list:
    section = _audit_section(
        section_id="sec_sn1",
        title="Sekce SN1",
        question_id="q_sn1",
        verification_type=VERIFICATION_TYPE_DOCUMENTATION,
    )
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id="proc_sn1",
        process_label="Proces SN1",
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id="proc_sn1",
            label="Proces SN1",
            process_id="proc_sn1",
            process_label="Proces SN1",
            section=None,
            children=(section_node,),
        )
    ]


class AuditProverkySectionNoteFunctionalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(ControlResult))
            session.commit()
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)

    def _commission_ids(self):
        suffix = os.urandom(3).hex()
        leader = settings_service.save_worker(first_name="Jan", last_name=f"L-{suffix}").id
        workplace = settings_service.save_worker(first_name="Eva", last_name=f"W-{suffix}").id
        union = person_service.create_person(first_name="Lucie", last_name=f"U-{suffix}").id
        return leader, workplace, union

    def _fill_audit_commission(self, dialog: AuditDialog, ids) -> None:
        leader, workplace, union = ids
        dialog.commission_widget.leader_selector.set_person_id(leader)
        dialog.commission_widget.workplace_selector.set_person_id(workplace)
        dialog.commission_widget.union_selector.set_person_id(union)

    def _create_legacy_audit(self):
        return audit_service.create_audit(title="Legacy audit SN1", notes_mode=None)

    def _create_new_audit(self):
        return audit_service.create_audit(title="Nový audit SN1")

    def test_create_audit_paths_set_new_mode(self) -> None:
        via_service = audit_service.create_audit(title="Cesta service")
        self.assertEqual(via_service.notes_mode, NOTES_MODE_SECTION_SUMMARY_V1)

        system = settings_service.save_workplace(
            name="SN1 Systém", active=True, audit_enabled=True
        )
        workplace = settings_service.save_workplace(
            name="SN1 Provoz", active=True, audit_enabled=True
        )
        system_audit_workplace_service.set_system_audit_workplace_id(system.id)
        with patch(
            "moduly.audity.sluzby.audit_knowledge_service.audit_knowledge_service.get_knowledge_tree"
        ) as mocked_tree:
            snapshot_audit = create_audit_with_v2_snapshot(
                fields={"title": "Cesta snapshot", "year": 2026, "started_at": date.today()},
                workplace_id=int(workplace.id),
                knowledge_tree=_fake_tree(),
                ensure_knowledge=False,
            )
            mocked_tree.assert_not_called()
        self.assertEqual(snapshot_audit.notes_mode, NOTES_MODE_SECTION_SUMMARY_V1)
        self.assertIn(
            "create_audit_with_v2_snapshot",
            inspect.getsource(create_manual_audit_with_v2_snapshot),
        )
        source = inspect.getsource(AuditProgramService.create_audit_from_visit)
        self.assertIn("create_unfrozen_program_audit", source)

    def test_create_inspection_paths_set_new_mode(self) -> None:
        via_dialog = bozp_inspection_service.create_inspection(title="Cesta dialog")
        self.assertEqual(via_dialog.notes_mode, NOTES_MODE_SECTION_SUMMARY_V1)
        source = inspect.getsource(BozpInspectionGenerationService.generate_for_year)
        self.assertIn("create_inspection", source)

    def test_legacy_audit_keeps_question_notes_and_export(self) -> None:
        audit = self._create_legacy_audit()
        self.assertIsNone(audit.notes_mode)
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="p1",
                area_label="Proces A",
                section_id="s1",
                section_label="Okruh",
                control_point_id="q1",
                control_point_label="Tvrzení 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="Individuální poznámka",
        )
        widget = AuditKnowledgeCriterionWidget()
        widget.set_notes_mode(audit.notes_mode)
        widget.set_audit_id(audit.id)
        widget.set_criterion(
            _audit_section(
                section_id="s1",
                title="Okruh",
                question_id="q1",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            ),
            area_id="p1",
            area_label="Proces A",
            section_label="Okruh",
        )
        self.assertIsNone(widget.findChild(SectionSummaryEdit))
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertFalse(selectors[0]._note_edit.isHidden())

        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()
        self.assertIn("Poznámka auditora:", detailed)
        self.assertIn("Individuální poznámka", detailed)
        self.assertNotIn(SECTION_SUMMARY_EXPORT_LABEL, detailed)

    def test_legacy_inspection_keeps_question_notes_and_export(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            title="Legacy prověrka SN1", notes_mode=None
        )
        self.assertIsNone(inspection.notes_mode)
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="a1",
                area_label="Oblast",
                section_id="s1",
                section_label="Okruh",
                control_point_id="k1",
                control_point_label="Bod 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="Komentář bodu",
        )
        widget = BozpKnowledgeSectionWidget()
        widget.set_notes_mode(inspection.notes_mode)
        widget.set_inspection_id(inspection.id)
        widget.set_section(
            _inspection_section(
                section_id="s1",
                title="Okruh",
                point_id="k1",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            ),
            area_id="a1",
            area_label="Oblast",
            section_label="Okruh",
        )
        self.assertIsNone(widget.findChild(SectionSummaryEdit))
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertFalse(selectors[0]._note_edit.isHidden())

        detailed = bozp_inspection_export_context_service.build(
            inspection, config=INSPECTION_DETAILED_CONFIG
        ).detailed_appendix_control_points().plain_text()
        self.assertIn("Komentář:", detailed)
        self.assertIn("Komentář bodu", detailed)
        self.assertNotIn(SECTION_SUMMARY_EXPORT_LABEL, detailed)

    def test_new_audit_ui_summary_hides_question_note(self) -> None:
        audit = self._create_new_audit()
        widget = AuditKnowledgeCriterionWidget()
        widget.set_deferred_edits(AuditDeferredEdits())
        widget.set_notes_mode(audit.notes_mode)
        widget.set_audit_id(audit.id)
        widget.set_criterion(
            _audit_section(
                section_id="s1",
                title="Okruh",
                question_id="q1",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            ),
            area_id="p1",
            area_label="Proces A",
            section_label="Okruh",
        )
        summary = widget.findChild(SectionSummaryEdit)
        self.assertIsNotNone(summary)
        self.assertEqual(summary._label.text(), SECTION_SUMMARY_LABEL)
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertTrue(selectors[0]._note_edit.isHidden())

    def test_new_inspection_ui_summary_hides_question_note(self) -> None:
        inspection = bozp_inspection_service.create_inspection(title="Nová prověrka UI")
        widget = BozpKnowledgeSectionWidget()
        widget.set_deferred_edits(InspectionDeferredEdits())
        widget.set_notes_mode(inspection.notes_mode)
        widget.set_inspection_id(inspection.id)
        widget.set_section(
            _inspection_section(
                section_id="s1",
                title="Okruh",
                point_id="k1",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            ),
            area_id="a1",
            area_label="Oblast",
            section_label="Okruh",
        )
        self.assertIsNotNone(widget.findChild(SectionSummaryEdit))
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertTrue(selectors[0]._note_edit.isHidden())

    def test_shared_working_value_documentation_terrain(self) -> None:
        deferred = AuditDeferredEdits()
        section = _audit_section(
            section_id="s1",
            title="Okruh",
            question_id="q1",
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        terrain_section = _audit_section(
            section_id="s1",
            title="Okruh",
            question_id="q2",
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        docs = AuditKnowledgeCriterionWidget(
            verification_filter=VERIFICATION_TYPE_DOCUMENTATION
        )
        terrain = AuditKnowledgeCriterionWidget(
            verification_filter=VERIFICATION_TYPE_TERRAIN
        )
        for widget, payload in ((docs, section), (terrain, terrain_section)):
            widget.set_deferred_edits(deferred)
            widget.set_notes_mode(NOTES_MODE_SECTION_SUMMARY_V1)
            widget.set_criterion(
                payload,
                area_id="p1",
                area_label="Proces A",
                section_label="Okruh",
            )
        docs._section_summary_edit.set_text("Společný text")
        docs._on_section_summary_changed()
        terrain.reload_section_summary()
        self.assertEqual(terrain._section_summary_edit.text(), "Společný text")
        self.assertEqual(
            _count(storage_module.storage_service.database_path, "audit_section_summaries"),
            0,
        )

    def test_switch_section_keeps_unsaved_summary(self) -> None:
        deferred = AuditDeferredEdits()
        widget = AuditKnowledgeCriterionWidget()
        widget.set_deferred_edits(deferred)
        widget.set_notes_mode(NOTES_MODE_SECTION_SUMMARY_V1)
        first = _audit_section(
            section_id="s1",
            title="Okruh 1",
            question_id="q1",
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        second = _audit_section(
            section_id="s2",
            title="Okruh 2",
            question_id="q2",
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
        )
        widget.set_criterion(first, area_id="p1", area_label="Proces", section_label="Okruh 1")
        widget._section_summary_edit.set_text("Text okruhu 1")
        widget._on_section_summary_changed()
        widget.set_criterion(second, area_id="p1", area_label="Proces", section_label="Okruh 2")
        self.assertEqual(widget._section_summary_edit.text(), "")
        widget.set_criterion(first, area_id="p1", area_label="Proces", section_label="Okruh 1")
        self.assertEqual(widget._section_summary_edit.text(), "Text okruhu 1")

    def test_save_and_discard_dialog_paths(self) -> None:
        ids = self._commission_ids()
        leader, workplace, union = ids
        audit = audit_service.create_audit(title="Dialog SN1")
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader,
                    "display_name": "L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": workplace,
                    "display_name": "W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": union,
                    "display_name": "U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        audit = audit_service.get_by_id(audit.id)
        dialog = AuditDialog(audit=audit)
        self._fill_audit_commission(dialog, ids)
        criterion = dialog.processes_widget.knowledge_widget.criterion_widget
        criterion.set_criterion(
            _audit_section(
                section_id="s1",
                title="Okruh",
                question_id="q1",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            ),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        criterion._section_summary_edit.set_text("Uložený text")
        criterion._on_section_summary_changed()
        self.assertTrue(dialog._persist())
        self.assertEqual(
            audit_section_summary_service.get_text(audit.id, process_id="p1", section_id="s1"),
            "Uložený text",
        )

        criterion = dialog.processes_widget.knowledge_widget.criterion_widget
        criterion.set_criterion(
            _audit_section(
                section_id="s1",
                title="Okruh",
                question_id="q1",
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            ),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        criterion._section_summary_edit.set_text("Zahodit")
        criterion._on_section_summary_changed()
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            dialog._request_close()
        self.assertEqual(
            audit_section_summary_service.get_text(audit.id, process_id="p1", section_id="s1"),
            "Uložený text",
        )

    def test_open_and_tab_switch_do_not_write(self) -> None:
        audit = self._create_new_audit()
        before = _count(storage_module.storage_service.database_path, "audit_section_summaries")
        dialog = AuditDialog(audit=audit)
        dialog.tabs.setCurrentWidget(dialog.processes_widget)
        dialog.tabs.setCurrentWidget(dialog.terrain_widget)
        dialog.tabs.setCurrentWidget(dialog.spis_widget)
        after = _count(storage_module.storage_service.database_path, "audit_section_summaries")
        self.assertEqual(before, after)

        inspection = bozp_inspection_service.create_inspection(title="Tab SN1")
        before_i = _count(
            storage_module.storage_service.database_path, "inspection_section_summaries"
        )
        insp_dialog = BozpInspectionDialog(inspection=inspection)
        insp_dialog.tabs.setCurrentWidget(insp_dialog.areas_widget)
        insp_dialog.tabs.setCurrentWidget(insp_dialog.terrain_widget)
        after_i = _count(
            storage_module.storage_service.database_path, "inspection_section_summaries"
        )
        self.assertEqual(before_i, after_i)

    def test_same_section_name_different_processes(self) -> None:
        audit = self._create_new_audit()
        audit_section_summary_service.set_text(
            audit.id, process_id="proc_a", section_id="sec_x", summary_text="Text A"
        )
        audit_section_summary_service.set_text(
            audit.id, process_id="proc_b", section_id="sec_y", summary_text="Text B"
        )
        for process_id, section_id, label, qid, note in (
            ("proc_a", "sec_x", "Stejný název", "qa", "nesmí A"),
            ("proc_b", "sec_y", "Stejný název", "qb", "nesmí B"),
        ):
            control_result_service.set_result(
                ENTITY_AUDITY,
                audit.id,
                ControlPointContext(
                    area_id=process_id,
                    area_label=f"Proces {process_id}",
                    section_id=section_id,
                    section_label=label,
                    control_point_id=qid,
                    control_point_label=f"Tvrzení {qid}",
                    ),
                result=CONTROL_RESULT_VYHOVUJE,
                note=note,
            )
        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()
        self.assertEqual(detailed.count("Text A"), 1)
        self.assertEqual(detailed.count("Text B"), 1)
        self.assertNotIn("nesmí A", detailed)
        self.assertNotIn("nesmí B", detailed)
        self.assertNotIn("Poznámka auditora:", detailed)

    def test_export_summary_once_multiline_empty_omitted(self) -> None:
        empty = section_summary_paragraphs("   \n  ")
        self.assertEqual(empty, [])

        audit = self._create_new_audit()
        audit_section_summary_service.set_text(
            audit.id,
            process_id="p1",
            section_id="s1",
            summary_text="První odstavec\n\nDruhý odstavec",
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="p1",
                area_label="Proces",
                section_id="s1",
                section_label="Okruh",
                control_point_id="q1",
                control_point_label="Tvrzení 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="skrytá poznámka",
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="p1",
                area_label="Proces",
                section_id="s1",
                section_label="Okruh",
                control_point_id="q2",
                control_point_label="Tvrzení 2",
            ),
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="",
        )
        protocol = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        ).summary_appendix_assertions().plain_text()
        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()
        self.assertEqual(protocol.count(SECTION_SUMMARY_EXPORT_LABEL), 1)
        self.assertEqual(detailed.count(SECTION_SUMMARY_EXPORT_LABEL), 1)
        self.assertIn("První odstavec", detailed)
        self.assertIn("Druhý odstavec", detailed)
        self.assertNotIn("skrytá poznámka", detailed)
        self.assertNotIn("Poznámka auditora:", protocol)

        audit_section_summary_service.set_text(
            audit.id, process_id="p1", section_id="s1", summary_text="  "
        )
        empty_export = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()
        self.assertNotIn(SECTION_SUMMARY_EXPORT_LABEL, empty_export)

        inspection = bozp_inspection_service.create_inspection(title="Export SN1")
        inspection_section_summary_service.set_text(
            inspection.id,
            area_id="a1",
            section_id="s1",
            summary_text="Prověrka odstavec 1\nPrověrka odstavec 2",
        )
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="a1",
                area_label="Oblast",
                section_id="s1",
                section_label="Okruh",
                control_point_id="k1",
                control_point_label="Bod 1",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
            note="komentář skrytý",
        )
        insp_detailed = bozp_inspection_export_context_service.build(
            inspection, config=INSPECTION_DETAILED_CONFIG
        ).detailed_appendix_control_points().plain_text()
        insp_protocol = bozp_inspection_export_context_service.build(
            inspection, config=INSPECTION_PROTOCOL_CONFIG
        ).summary_appendix_control_points().plain_text()
        self.assertEqual(insp_detailed.count(SECTION_SUMMARY_EXPORT_LABEL), 1)
        self.assertEqual(insp_protocol.count(SECTION_SUMMARY_EXPORT_LABEL), 1)
        self.assertIn("Prověrka odstavec 1", insp_detailed)
        self.assertNotIn("komentář skrytý", insp_detailed)
        self.assertNotIn("Komentář:", insp_detailed)

    def test_empty_text_does_not_keep_row_and_delete_clears(self) -> None:
        audit = self._create_new_audit()
        self.assertIsNone(
            audit_section_summary_service.set_text(
                audit.id, process_id="p1", section_id="s1", summary_text=""
            )
        )
        self.assertEqual(
            _count(storage_module.storage_service.database_path, "audit_section_summaries"),
            0,
        )
        audit_section_summary_service.set_text(
            audit.id, process_id="p1", section_id="s1", summary_text="dočasně"
        )
        self.assertEqual(
            _count(storage_module.storage_service.database_path, "audit_section_summaries"),
            1,
        )
        audit_service.delete_audit(audit.id)
        self.assertEqual(
            _count(storage_module.storage_service.database_path, "audit_section_summaries"),
            0,
        )

        inspection = bozp_inspection_service.create_inspection(title="Delete SN1")
        inspection_section_summary_service.set_text(
            inspection.id, area_id="a1", section_id="s1", summary_text="x"
        )
        bozp_inspection_service.delete_inspection(inspection.id)
        self.assertEqual(
            _count(
                storage_module.storage_service.database_path, "inspection_section_summaries"
            ),
            0,
        )

    def test_regression_results_photos_findings_remain(self) -> None:
        audit = self._create_new_audit()
        context = ControlPointContext(
            area_id="p1",
            area_label="Proces",
            section_id="s1",
            section_label="Okruh",
            control_point_id="q1",
            control_point_label="Tvrzení 1",
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=CONTROL_RESULT_VYHOVUJE,
            shared_experience=True,
        )
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Zjištění SN1",
            status=FINDING_STATUS_OTEVRENE,
            source_control_point_id="q1",
        )
        row = control_result_service.get_for_control_point(ENTITY_AUDITY, audit.id, context)
        self.assertEqual(row.result, CONTROL_RESULT_VYHOVUJE)
        self.assertTrue(row.shared_experience)
        loaded = finding_service.get_by_id(finding.id)
        self.assertEqual(loaded.description, "Zjištění SN1")

    def test_new_dialog_uses_summary_mode_before_first_save(self) -> None:
        dialog = AuditDialog()
        self.assertTrue(
            dialog.processes_widget.knowledge_widget.criterion_widget.uses_section_summary()
        )
        insp = BozpInspectionDialog()
        self.assertTrue(
            insp.areas_widget.knowledge_widget.section_widget.uses_section_summary()
        )

    def test_criterion_widget_does_not_reload_live_methodology(self) -> None:
        with patch(
            "moduly.audity.sluzby.audit_knowledge_service.audit_knowledge_service.get_knowledge_tree"
        ) as mocked:
            widget = AuditKnowledgeCriterionWidget()
            widget.set_notes_mode(NOTES_MODE_SECTION_SUMMARY_V1)
            widget.set_criterion(
                _audit_section(
                    section_id="s1",
                    title="Okruh",
                    question_id="q1",
                    verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                ),
                area_id="p1",
                area_label="Proces",
                section_label="Okruh",
            )
            mocked.assert_not_called()

    def test_update_preserves_notes_mode(self) -> None:
        audit = self._create_new_audit()
        updated = audit_service.update_audit(audit.id, title="Po úpravě")
        self.assertEqual(updated.notes_mode, NOTES_MODE_SECTION_SUMMARY_V1)
        legacy = self._create_legacy_audit()
        legacy_updated = audit_service.update_audit(legacy.id, title="Legacy po úpravě")
        self.assertIsNone(legacy_updated.notes_mode)

    def test_legacy_appendix_builder_still_prints_notes(self) -> None:
        text = build_detailed_control_points_appendix(
            [
                ControlPointAppendixItem(
                    area_label="Okruh",
                    control_point_label="Tvrzení",
                    result=CONTROL_RESULT_VYHOVUJE,
                    note="Starý komentář",
                )
            ],
            note_label="Poznámka auditora:",
        ).plain_text()
        self.assertIn("Poznámka auditora:", text)
        self.assertIn("Starý komentář", text)
        self.assertNotIn(SECTION_SUMMARY_EXPORT_LABEL, text)


if __name__ == "__main__":
    unittest.main()
