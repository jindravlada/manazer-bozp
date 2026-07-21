"""Test jednorázového nástroje AUDIT-DATA-CLEANUP-1."""

from __future__ import annotations

import importlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    import tools.cleanup_orphaned_audit_control_results as cleanup_module


class CleanupOrphanedAuditControlResultsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_audit_with_orphan_and_valid(self) -> tuple[int, int, int]:
        workplace = settings_service.save_workplace(name="Provoz Cleanup")
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=7,
        )

        process = audit_knowledge_service.get_process_by_id("bezpecnostni_kultura")
        self.assertIsNotNone(process)
        knowledge = audit_knowledge_service.load_process_knowledge(process)
        self.assertIsNotNone(knowledge)

        section = None
        for candidate in cleanup_module._iter_knowledge_sections(
            knowledge.get("sekce") or []
        ):
            if str(candidate.get("id") or "") == "postoj_vedeni":
                section = candidate
                break
        self.assertIsNotNone(section)
        questions = audit_knowledge_service.get_audit_questions(section)
        self.assertTrue(questions)
        current = questions[0]
        current_id = str(current.get("id") or "").strip()
        current_text = str(current.get("text") or current.get("nazev") or "").strip()

        orphan = control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="bezpecnostni_kultura",
                area_label="Bezpečnostní kultura",
                section_id="postoj_vedeni",
                section_label="Postoj vedení k BOZP",
                control_point_id="legacy_cleanup_orphan_assertion",
                control_point_label="Staré testovací tvrzení ze starší metodiky.",
            ),
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        valid = control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            ControlPointContext(
                area_id="bezpecnostni_kultura",
                area_label="Bezpečnostní kultura",
                section_id="postoj_vedeni",
                section_label="Postoj vedení k BOZP",
                control_point_id=current_id,
                control_point_label=current_text,
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        assert orphan is not None and valid is not None
        return audit.id, orphan.id, valid.id

    def test_dry_run_and_apply_on_temporary_db_copy(self) -> None:
        audit_id, orphan_id, valid_id = self._create_audit_with_orphan_and_valid()

        live_db = storage_module.storage_service.database_path
        self.assertTrue(live_db.is_file())

        work_dir = Path(tempfile.mkdtemp())
        db_copy = work_dir / "manager_bozp.db"
        shutil.copy2(live_db, db_copy)

        # Data dir must expose the same ciselniky as the live test home.
        data_dir = _TMP / ".local" / "share" / "manazer-bozp"

        exit_dry = cleanup_module.main(
            [
                "--db",
                str(db_copy),
                "--audit",
                str(audit_id),
                "--data-dir",
                str(data_dir),
                "--dry-run",
            ]
        )
        self.assertEqual(exit_dry, 0)

        with sqlite3.connect(db_copy) as connection:
            ids = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM control_results WHERE entity_type=? AND entity_id=?",
                    (ENTITY_AUDITY, audit_id),
                )
            }
        self.assertIn(orphan_id, ids)
        self.assertIn(valid_id, ids)

        exit_apply = cleanup_module.main(
            [
                "--db",
                str(db_copy),
                "--audit",
                str(audit_id),
                "--data-dir",
                str(data_dir),
                "--apply",
            ]
        )
        self.assertEqual(exit_apply, 0)

        with sqlite3.connect(db_copy) as connection:
            ids = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM control_results WHERE entity_type=? AND entity_id=?",
                    (ENTITY_AUDITY, audit_id),
                )
            }
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertNotIn(orphan_id, ids)
        self.assertIn(valid_id, ids)
        self.assertEqual(integrity, "ok")

        backups = list(work_dir.glob("manager_bozp.cleanup-orphans-*.db"))
        self.assertEqual(len(backups), 1)

        # Live DB must remain untouched.
        with sqlite3.connect(live_db) as connection:
            live_ids = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM control_results WHERE entity_type=? AND entity_id=?",
                    (ENTITY_AUDITY, audit_id),
                )
            }
        self.assertIn(orphan_id, live_ids)
        self.assertIn(valid_id, live_ids)


if __name__ == "__main__":
    unittest.main()
