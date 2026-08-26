"""AUDIT-LEAD-RECOMMENDATION-1: doporučení vedoucího auditora."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

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


def _seed_pre_lead_rec_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
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
                conclusion_text TEXT,
                created_at DATETIME,
                updated_at DATETIME
            );
            INSERT INTO audits (id, number, year, title, status, conclusion_text)
            VALUES (1, '5/2026', 2026, 'Starý audit', 'Dokončeno', 'Závěr');
            """
        )
        conn.commit()
    finally:
        conn.close()


_MIG_HOME = Path(tempfile.mkdtemp(prefix="lead-rec-1-mig-"))
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
from moduly.audity.sluzby.audit_lead_recommendation_1_schema_migration import (  # noqa: E402
    AUDIT_LEAD_RECOMMENDATION_COLUMNS,
    BACKUP_NAME_PREFIX,
    TRANSITION_ID,
    allocate_audit_lead_recommendation_1_backup_path,
    apply_audit_lead_recommendation_1_schema_ddl,
    needs_audit_lead_recommendation_1_schema,
    prepare_audit_lead_recommendation_1_schema,
    schema_is_present,
)

_MIG_HOME_PATCHER.stop()


class AuditLeadRecommendation1MigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._home = patch.object(Path, "home", return_value=_MIG_HOME)
        self._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()

        self.db_path = storage_module.storage_service.database_path
        self.ws = storage_module.storage_service.base
        state_path = self.ws / "konfigurace" / "migration_state.json"
        if state_path.exists():
            state_path.unlink()
        for backup in (self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"):
            backup.unlink()
        _seed_pre_lead_rec_db(self.db_path)

    def tearDown(self) -> None:
        self._home.stop()

    def test_01_backup_before_ddl(self) -> None:
        result = prepare_audit_lead_recommendation_1_schema(
            workspace_root=self.ws,
            database_path=self.db_path,
        )
        self.assertTrue(result.migrated)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(
            result.pre_migration_backup_path.name.startswith(BACKUP_NAME_PREFIX)
        )
        self.assertEqual(result.pre_migration_backup_path.suffix, ".mbbackup")

    def test_02_backup_failure_no_schema_change(self) -> None:
        before_cols = _table_columns(self.db_path, "audits")
        with patch(
            "moduly.audity.sluzby.audit_lead_recommendation_1_schema_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_audit_lead_recommendation_1_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(needs_audit_lead_recommendation_1_schema(self.db_path))
        self.assertFalse(is_transition_complete(self.ws, TRANSITION_ID))
        self.assertFalse(is_migration_in_progress(self.ws, TRANSITION_ID))
        self.assertEqual(_table_columns(self.db_path, "audits"), before_cols)

    def test_03_ddl_failure_rolls_back(self) -> None:
        broken = (
            AUDIT_LEAD_RECOMMENDATION_COLUMNS[0],
            ("lead_auditor_recommendation_results_signature", "NOT A VALID COLUMN"),
        )
        with patch(
            "moduly.audity.sluzby.audit_lead_recommendation_1_schema_migration."
            "AUDIT_LEAD_RECOMMENDATION_COLUMNS",
            broken,
        ):
            with self.assertRaises(sqlite3.OperationalError):
                apply_audit_lead_recommendation_1_schema_ddl(self.db_path)
        cols = _table_columns(self.db_path, "audits")
        self.assertNotIn("lead_auditor_recommendation", cols)
        self.assertNotIn("lead_auditor_recommendation_results_signature", cols)

    def test_04_idempotent_and_existing_null(self) -> None:
        first = prepare_audit_lead_recommendation_1_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertTrue(first.migrated)
        self.assertTrue(schema_is_present(self.db_path))
        row = sqlite3.connect(str(self.db_path)).execute(
            "SELECT lead_auditor_recommendation, "
            "lead_auditor_recommendation_results_signature FROM audits WHERE id = 1"
        ).fetchone()
        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertEqual(_count(self.db_path, "audits"), 1)
        backups_first = list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))
        second = prepare_audit_lead_recommendation_1_schema(
            workspace_root=self.ws, database_path=self.db_path
        )
        self.assertFalse(second.migrated)
        self.assertEqual(
            list((self.ws / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*")),
            backups_first,
        )

    def test_05_allocate_backup_name(self) -> None:
        path = allocate_audit_lead_recommendation_1_backup_path(self.ws / "zalohy")
        self.assertTrue(path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertTrue(path.name.endswith(".mbbackup"))

    def test_06_prepare_ddl_failure_marks_failed(self) -> None:
        with patch(
            "moduly.audity.sluzby.audit_lead_recommendation_1_schema_migration."
            "apply_audit_lead_recommendation_1_schema_ddl",
            side_effect=RuntimeError("umělá chyba DDL"),
        ):
            with self.assertRaises(MigrationGuardError):
                prepare_audit_lead_recommendation_1_schema(
                    workspace_root=self.ws,
                    database_path=self.db_path,
                )
        self.assertTrue(is_migration_failed(self.ws, TRANSITION_ID))
        self.assertTrue(needs_audit_lead_recommendation_1_schema(self.db_path))


_SVC_HOME = Path(tempfile.mkdtemp(prefix="lead-rec-1-svc-"))
with patch.object(Path, "home", return_value=_SVC_HOME):
    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_LEAD_RECOMMENDATION_EMPTY_REVIEW_MESSAGE,
        AUDIT_LEAD_RECOMMENDATION_REQUIRED_MESSAGE,
        AUDIT_LEAD_RECOMMENDATION_SIGNATURE_INVALID_MESSAGE,
        AUDIT_LEAD_RECOMMENDATION_STATUS_CURRENT,
        AUDIT_LEAD_RECOMMENDATION_STATUS_STALE,
        AUDIT_LEAD_RECOMMENDATION_STATUS_UNCONFIRMED,
        AUDIT_LEAD_RECOMMENDATION_STALE_REVIEW_MESSAGE,
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PROBIHA,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_lead_recommendation_service import (
        compute_results_signature,
        confirmed_recommendation_fields,
        generate_lead_auditor_recommendation,
        recommendation_status_label,
        resolve_lead_auditor_recommendation_text,
    )
    from moduly.audity.sluzby.audit_service import (
        AuditCompletionError,
        audit_service,
    )
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class AuditLeadRecommendation1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_SVC_HOME)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(name=f"LeadRec-WP-{suffix}")
        self.leader = settings_service.save_worker(
            first_name="Jan", last_name=f"Lead-{suffix}"
        )
        self.workplace_rep = settings_service.save_worker(
            first_name="Eva", last_name=f"Provoz-{suffix}"
        )
        self.union = person_service.create_person(
            first_name="Lucie", last_name=f"Odbory-{suffix}"
        )

    def _create_audit(self, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
            "started_at": date(2026, 8, 1),
            "title": "Lead rec test",
        }
        payload.update(fields)
        audit = audit_service.create_audit(**payload)
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader.id,
                    "display_name": "Jan Lead",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep.id,
                    "display_name": "Eva Provoz",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union.id,
                    "display_name": "Lucie Odbory",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return audit

    def _set_result(self, audit_id: int, *, control_point_id: str, result: str):
        return control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id=control_point_id,
                control_point_label=control_point_id,
            ),
            result=result,
        )

    def test_schema_columns_present(self) -> None:
        from core.database.session import get_session
        from sqlalchemy import text

        with get_session() as session:
            rows = session.execute(text("PRAGMA table_info(audits)")).fetchall()
        columns = {str(row[1]) for row in rows}
        self.assertIn("lead_auditor_recommendation", columns)
        self.assertIn("lead_auditor_recommendation_results_signature", columns)

    def test_generator_clean_branch_contains_bozp_qms(self) -> None:
        audit = self._create_audit()
        text = generate_lead_auditor_recommendation(audit.id)
        self.assertIn("BOZP", text)
        self.assertIn("QMS", text)
        self.assertIn("bez závažných nedostatků", text)
        self.assertIn("průběžně sledovat", text)

    def test_generator_neshody_branch(self) -> None:
        audit = self._create_audit()
        self._set_result(audit.id, control_point_id="n1", result=CONTROL_RESULT_NEVYHOVUJE)
        text = generate_lead_auditor_recommendation(audit.id)
        self.assertIn("1 neshod", text)
        self.assertIn("BOZP", text)
        self.assertIn("QMS", text)

    def test_generator_recommendation_branch(self) -> None:
        audit = self._create_audit()
        self._set_result(
            audit.id,
            control_point_id="d1",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        text = generate_lead_auditor_recommendation(audit.id)
        self.assertIn("1 oblastech", text)
        self.assertIn("BOZP", text)
        self.assertIn("QMS", text)

    def test_generator_open_findings_branch(self) -> None:
        audit = self._create_audit()
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené",
            status=FINDING_STATUS_OTEVRENE,
        )
        text = generate_lead_auditor_recommendation(audit.id)
        self.assertIn("1 otevřených zjištění", text)
        self.assertIn("BOZP", text)
        self.assertIn("QMS", text)

    def test_signature_deterministic_and_ignores_timestamp(self) -> None:
        audit = self._create_audit()
        self._set_result(audit.id, control_point_id="t1", result=CONTROL_RESULT_VYHOVUJE)
        first = compute_results_signature(audit.id)
        second = compute_results_signature(audit.id)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        from core.database.session import get_session
        from sqlalchemy import text

        with get_session() as session:
            session.execute(
                text(
                    "UPDATE control_results SET recorded_at = :ts, updated_at = :ts "
                    "WHERE entity_id = :aid"
                ),
                {"ts": datetime(2020, 1, 1, 12, 0, 0), "aid": audit.id},
            )
            session.commit()
        self.assertEqual(first, compute_results_signature(audit.id))
        self._set_result(
            audit.id, control_point_id="t1", result=CONTROL_RESULT_NEVYHOVUJE
        )
        self.assertNotEqual(first, compute_results_signature(audit.id))

    def test_old_completed_fallback_not_dirty_no_write(self) -> None:
        audit = self._create_audit(
            finished_at=date(2025, 1, 15),
            conclusion_text="Starý závěr",
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.lead_auditor_recommendation)
        updated_at = loaded.updated_at
        dialog = AuditDialog(audit=loaded)
        self.assertFalse(dialog._is_dirty())
        fallback = generate_lead_auditor_recommendation(audit.id)
        self.assertEqual(
            dialog.conclusion_widget.recommendation_edit.toPlainText(),
            fallback,
        )
        self.assertEqual(
            dialog.conclusion_widget.recommendation_status_label.text(),
            AUDIT_LEAD_RECOMMENDATION_STATUS_UNCONFIRMED,
        )
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertIsNone(reloaded.lead_auditor_recommendation)
        self.assertEqual(reloaded.updated_at, updated_at)

    def test_generate_button_working_copy_only(self) -> None:
        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget._generate_recommendation_clicked()
        self.assertTrue(dialog._is_dirty())
        self.assertTrue(
            dialog.conclusion_widget.recommendation_edit.toPlainText().strip()
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.lead_auditor_recommendation)

    def test_generate_button_requires_confirm_and_cancel_keeps_text(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget.recommendation_edit.setPlainText("Ruční text")
        with patch(
            "moduly.audity.ui.audit_conclusion_widget.QMessageBox.question",
            return_value=QMessageBox.Cancel,
        ):
            dialog.conclusion_widget._generate_recommendation_clicked()
        self.assertEqual(
            dialog.conclusion_widget.recommendation_edit.toPlainText(),
            "Ruční text",
        )

    def test_save_persists_text_and_signature(self) -> None:
        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget.recommendation_edit.setPlainText("Potvrzený text")
        self.assertTrue(dialog._persist())
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.lead_auditor_recommendation, "Potvrzený text")
        self.assertEqual(
            loaded.lead_auditor_recommendation_results_signature,
            compute_results_signature(audit.id),
        )
        self.assertEqual(
            recommendation_status_label(loaded),
            AUDIT_LEAD_RECOMMENDATION_STATUS_CURRENT,
        )

    def test_discard_keeps_previous(self) -> None:
        audit = self._create_audit()
        audit_service.update_audit(
            audit.id,
            **confirmed_recommendation_fields(audit.id, "Původní"),
        )
        dialog = AuditDialog(audit=audit_service.get_by_id(audit.id))
        dialog.conclusion_widget.recommendation_edit.setPlainText("Zahozeno")
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._confirm_close())
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.lead_auditor_recommendation, "Původní")

    def test_reopen_loads_saved_text(self) -> None:
        audit = self._create_audit()
        audit_service.update_audit(
            audit.id,
            **confirmed_recommendation_fields(audit.id, "Uložené doporučení"),
        )
        dialog = AuditDialog(audit=audit_service.get_by_id(audit.id))
        self.assertEqual(
            dialog.conclusion_widget.recommendation_edit.toPlainText(),
            "Uložené doporučení",
        )

    def test_result_change_marks_stale(self) -> None:
        audit = self._create_audit()
        self._set_result(audit.id, control_point_id="t1", result=CONTROL_RESULT_VYHOVUJE)
        audit_service.update_audit(
            audit.id,
            **confirmed_recommendation_fields(audit.id, "Text"),
        )
        self._set_result(
            audit.id, control_point_id="t1", result=CONTROL_RESULT_NEVYHOVUJE
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        dialog = AuditDialog(audit=loaded)
        self.assertEqual(
            dialog.conclusion_widget.recommendation_status_label.text(),
            AUDIT_LEAD_RECOMMENDATION_STATUS_STALE,
        )
        self.assertEqual(
            dialog.conclusion_widget.recommendation_edit.toPlainText(),
            "Text",
        )

    def test_complete_empty_creates_draft_and_stays_open(self) -> None:
        audit = self._create_audit(conclusion_text="Závěr")
        dialog = AuditDialog(audit=audit)
        with patch(
            "moduly.audity.ui.audit_dialog.QMessageBox.information"
        ) as mock_info:
            dialog.conclusion_widget._complete_audit()
            mock_info.assert_called()
            self.assertEqual(
                mock_info.call_args.args[2],
                AUDIT_LEAD_RECOMMENDATION_EMPTY_REVIEW_MESSAGE,
            )
        self.assertEqual(dialog.tabs.currentWidget(), dialog.conclusion_widget)
        self.assertTrue(
            dialog.conclusion_widget.recommendation_edit.toPlainText().strip()
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)
        self.assertIsNone(loaded.lead_auditor_recommendation)

        dialog.conclusion_widget._complete_audit()
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.status, AUDIT_STATUS_DOKONCENO)
        self.assertTrue((loaded.lead_auditor_recommendation or "").strip())

    def test_stale_first_attempt_does_not_overwrite(self) -> None:
        audit = self._create_audit(conclusion_text="Závěr")
        self._set_result(audit.id, control_point_id="t1", result=CONTROL_RESULT_VYHOVUJE)
        audit_service.update_audit(
            audit.id,
            **confirmed_recommendation_fields(audit.id, "Ponechaný text"),
        )
        self._set_result(
            audit.id, control_point_id="t1", result=CONTROL_RESULT_NEVYHOVUJE
        )
        dialog = AuditDialog(audit=audit_service.get_by_id(audit.id))
        with patch(
            "moduly.audity.ui.audit_dialog.QMessageBox.warning"
        ) as mock_warn:
            dialog.conclusion_widget._complete_audit()
            mock_warn.assert_called()
            self.assertEqual(
                mock_warn.call_args.args[2],
                AUDIT_LEAD_RECOMMENDATION_STALE_REVIEW_MESSAGE,
            )
        self.assertEqual(
            dialog.conclusion_widget.recommendation_edit.toPlainText(),
            "Ponechaný text",
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)
        dialog.conclusion_widget._complete_audit()
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.status, AUDIT_STATUS_DOKONCENO)
        self.assertEqual(loaded.lead_auditor_recommendation, "Ponechaný text")
        self.assertEqual(
            loaded.lead_auditor_recommendation_results_signature,
            compute_results_signature(audit.id),
        )

    def test_service_rejects_missing_recommendation_and_bad_signature(self) -> None:
        audit = self._create_audit(conclusion_text="Závěr")
        with self.assertRaises(AuditCompletionError) as ctx:
            audit_service.update_audit(audit.id, finished_at=date(2026, 8, 20))
        self.assertEqual(str(ctx.exception), AUDIT_LEAD_RECOMMENDATION_REQUIRED_MESSAGE)
        with self.assertRaises(AuditCompletionError) as ctx2:
            audit_service.update_audit(
                audit.id,
                finished_at=date(2026, 8, 20),
                lead_auditor_recommendation="Text",
                lead_auditor_recommendation_results_signature="0" * 64,
            )
        self.assertEqual(
            str(ctx2.exception), AUDIT_LEAD_RECOMMENDATION_SIGNATURE_INVALID_MESSAGE
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)
        self.assertEqual(loaded.status, AUDIT_STATUS_PROBIHA)

    def test_save_failure_keeps_incomplete(self) -> None:
        audit = self._create_audit(conclusion_text="Závěr")
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget.recommendation_edit.setPlainText("Návrh")
        dialog.conclusion_widget.mark_recommendation_review_pending()
        with patch(
            "moduly.audity.sluzby.audit_service.audit_service.update_audit",
            side_effect=RuntimeError("uložení selhalo"),
        ):
            with self.assertRaises(RuntimeError):
                dialog.conclusion_widget._complete_audit()
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)
        self.assertIsNone(loaded.lead_auditor_recommendation)

    def test_reopen_completed_requires_new_check(self) -> None:
        audit = self._create_audit(
            finished_at=date(2026, 1, 1),
            conclusion_text="Závěr",
        )
        reopened = audit_service.update_audit(audit.id, finished_at=None)
        assert reopened is not None
        with self.assertRaises(AuditCompletionError):
            audit_service.update_audit(
                reopened.id,
                finished_at=date(2026, 8, 21),
                conclusion_text="Závěr",
            )
        done = audit_service.update_audit(
            reopened.id,
            finished_at=date(2026, 8, 21),
            conclusion_text="Závěr",
            **confirmed_recommendation_fields(reopened.id),
        )
        assert done is not None
        self.assertEqual(done.status, AUDIT_STATUS_DOKONCENO)

    def test_export_saved_text_and_null_fallback(self) -> None:
        audit = self._create_audit(conclusion_text="Závěr")
        custom = "Přesně uložený text doporučení."
        audit_service.update_audit(
            audit.id,
            finished_at=date(2026, 8, 13),
            conclusion_text="Závěr",
            **confirmed_recommendation_fields(audit.id, custom),
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        protocol = audit_export_context_service.build(
            loaded, config=PROTOCOL_DOCUMENT_CONFIG
        )
        detailed = audit_export_context_service.build(
            loaded, config=DETAILED_REPORT_DOCUMENT_CONFIG
        )
        self.assertEqual(protocol.auditor_recommendation_text(), custom)
        self.assertEqual(detailed.auditor_recommendation_text(), custom)
        content = _odt_text(protokol_audit_service.generate_for_audit(loaded))
        self.assertIn(custom, content)
        d_content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(loaded)
        )
        self.assertIn(custom, d_content)

        old = self._create_audit(
            finished_at=date(2025, 2, 1),
            conclusion_text="Starý",
        )
        fallback = generate_lead_auditor_recommendation(old.id)
        self.assertIn("BOZP", fallback)
        self.assertIn("QMS", fallback)
        ctx = audit_export_context_service.build(old)
        self.assertEqual(ctx.auditor_recommendation_text(), fallback)
        dialog = AuditDialog(audit=old)
        self.assertEqual(
            dialog.conclusion_widget.recommendation_edit.toPlainText(),
            fallback,
        )
        self.assertFalse(dialog._is_dirty())
        updated_at = old.updated_at
        protokol_audit_service.generate_detailed_report_for_audit(old)
        reloaded = audit_service.get_by_id(old.id)
        assert reloaded is not None
        self.assertIsNone(reloaded.lead_auditor_recommendation)
        self.assertEqual(reloaded.updated_at, updated_at)

    def test_open_export_no_knowledge_tree(self) -> None:
        audit = self._create_audit(
            finished_at=date(2026, 8, 14),
            conclusion_text="Závěr",
        )
        dialog = AuditDialog(audit=audit)
        dialog.tabs.setCurrentWidget(dialog.conclusion_widget)
        with patch(
            "moduly.audity.sluzby.audit_knowledge_service.AuditKnowledgeService.get_knowledge_tree"
        ) as mock_tree:
            protokol_audit_service.generate_for_audit(audit)
            protokol_audit_service.generate_detailed_report_for_audit(audit)
            mock_tree.assert_not_called()
