"""Test jednorázového nástroje AUDIT-DATA-CLEANUP-1 (celá DB)."""

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

    def _add_orphan_and_valid(self, audit_id: int) -> tuple[int, int]:
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
        questions = cleanup_module._audit_questions_from_section(section)
        self.assertTrue(questions)
        current = questions[0]
        current_id = str(current.get("id") or "").strip()
        current_text = str(current.get("text") or current.get("nazev") or "").strip()

        orphan = control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
            ControlPointContext(
                area_id="bezpecnostni_kultura",
                area_label="Bezpečnostní kultura",
                section_id="postoj_vedeni",
                section_label="Postoj vedení k BOZP",
                control_point_id=f"legacy_cleanup_orphan_{audit_id}",
                control_point_label="Staré testovací tvrzení ze starší metodiky.",
            ),
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )
        valid = control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
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
        return orphan.id, valid.id

    def test_apply_cleans_entire_database_without_audit_filter(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz Cleanup")
        audit_a = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=7,
        )
        audit_b = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2027,
            planned_month=1,
        )
        orphan_a, valid_a = self._add_orphan_and_valid(audit_a.id)
        orphan_b, valid_b = self._add_orphan_and_valid(audit_b.id)

        live_db = storage_module.storage_service.database_path
        work_dir = Path(tempfile.mkdtemp())
        db_copy = work_dir / "manager_bozp.db"
        shutil.copy2(live_db, db_copy)
        data_dir = _TMP / ".local" / "share" / "manazer-bozp"

        # Bez --audit = celá databáze.
        exit_dry = cleanup_module.main(
            [
                "--db",
                str(db_copy),
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
                    "SELECT id FROM control_results WHERE entity_type=?",
                    (ENTITY_AUDITY,),
                )
            }
        self.assertEqual(ids, {orphan_a, valid_a, orphan_b, valid_b})

        exit_apply = cleanup_module.main(
            [
                "--db",
                str(db_copy),
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
                    "SELECT id FROM control_results WHERE entity_type=?",
                    (ENTITY_AUDITY,),
                )
            }
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(ids, {valid_a, valid_b})
        self.assertNotIn(orphan_a, ids)
        self.assertNotIn(orphan_b, ids)
        self.assertEqual(integrity, "ok")
        self.assertEqual(len(list(work_dir.glob("manager_bozp.cleanup-orphans-*.db"))), 1)

        with sqlite3.connect(live_db) as connection:
            live_ids = {
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM control_results WHERE entity_type=?",
                    (ENTITY_AUDITY,),
                )
            }
        self.assertEqual(live_ids, {orphan_a, valid_a, orphan_b, valid_b})


if __name__ == "__main__":
    unittest.main()
