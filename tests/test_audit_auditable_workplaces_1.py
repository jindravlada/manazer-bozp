"""AUDIT-AUDITABLE-WORKPLACES-1: jednotný filtr auditovatelných provozů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import select, text

_TMP = Path(tempfile.mkdtemp(prefix="audit-auditable-wp-1-"))
_WS = _TMP / ".local" / "share" / "manazer-bozp"
_DB = _WS / "databaze" / "manager_bozp.db"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.sluzby.audit_extraordinary_schema_migration import (
        apply_audit_extraordinary_schema_ddl,
    )

    apply_audit_extraordinary_schema_ddl(_DB)

    from core.database.session import get_session
    from moduly.audity.constants import (
        AUDITABLE_WORKPLACE_REQUIRED_MESSAGE,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
        EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED,
        EXTRAORDINARY_TARGET_STATUS_CANCELLED,
        EXTRAORDINARY_TARGET_STATUS_PENDING,
        SYSTEM_AUDIT_WORKPLACE_INVALID_MESSAGE,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_extraordinary_question import (
        AuditExtraordinaryQuestionTarget,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_auditable_workplace_service import (
        is_auditable_workplace,
        list_auditable_workplaces,
        require_auditable_workplace_id,
    )
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        AuditExtraordinaryError,
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import KnowledgeTreeNode
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_v2_create_service import (
        AuditV2CreateError,
        create_audit_with_v2_snapshot,
        create_manual_audit_with_v2_snapshot,
    )
    from moduly.audity.sluzby.system_audit_workplace_service import (
        SystemAuditWorkplaceError,
        system_audit_workplace_service,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _question(qid: str, text: str) -> dict:
    return {
        "id": qid,
        "text": text,
        "aktivni": True,
        "poradi": 10,
        "verification_type": "dokumentace",
        "zavaznost": "stredni",
        "question_kind": "operation",
    }


def _minimal_tree() -> list[KnowledgeTreeNode]:
    section = {
        "id": "sec_aw",
        "nazev": "Sekce AW",
        "aktivni": True,
        "auditni_tvrzeni": [_question("q_aw", "Otázka AW")],
        "sekce": [],
    }
    section_node = KnowledgeTreeNode(
        node_type="section",
        node_id=section["id"],
        label=section["nazev"],
        process_id="proc_aw",
        process_label="Proces AW",
        section=section,
        children=(),
    )
    return [
        KnowledgeTreeNode(
            node_type="process",
            node_id="proc_aw",
            label="Proces AW",
            process_id="proc_aw",
            process_label="Proces AW",
            section=None,
            children=(section_node,),
        )
    ]


class AuditableWorkplaceFilterTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(text("DELETE FROM audit_extraordinary_question_targets"))
            session.execute(text("DELETE FROM audit_extraordinary_questions"))
            session.commit()

        self.ok = settings_service.save_workplace(
            name="AW OK Provoz",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.off = settings_service.save_workplace(
            name="AW Bez Auditovat",
            active=True,
            audit_enabled=False,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.inactive = settings_service.save_workplace(
            name="AW Neaktivní",
            active=False,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="AW Pracoviště",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.ok.id,
        )
        self.part = settings_service.save_workplace(
            name="AW Část",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.system = settings_service.save_workplace(
            name="AW Systém",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        system_audit_workplace_service.set_system_audit_workplace_id(self.system.id)

    def test_01_active_operation_audit_enabled_listed(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces()}
        self.assertIn(self.ok.id, ids)
        self.assertTrue(is_auditable_workplace(self.ok))

    def test_02_operation_without_audit_not_listed(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces()}
        self.assertNotIn(self.off.id, ids)
        self.assertFalse(is_auditable_workplace(self.off))

    def test_03_inactive_operation_not_listed(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces(include_inactive=True)}
        # list_auditable stále filtruje active=true
        self.assertNotIn(self.inactive.id, ids)
        self.assertFalse(is_auditable_workplace(self.inactive))

    def test_04_workplace_type_not_listed(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces()}
        self.assertNotIn(self.workplace.id, ids)

    def test_05_workplace_part_not_listed(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces()}
        self.assertNotIn(self.part.id, ids)

    def test_06_extraordinary_all_creates_only_auditable(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Všechny AW",
            all_workplaces=True,
        )
        targets = {
            int(t.workplace_id)
            for t in audit_extraordinary_question_service.repository.list_targets_for_question(
                question.id
            )
        }
        selectable = {
            item.workplace_id
            for item in audit_extraordinary_question_service.list_selectable_workplaces()
        }
        self.assertEqual(targets, selectable)
        self.assertNotIn(self.off.id, targets)
        self.assertNotIn(self.workplace.id, targets)
        self.assertNotIn(self.part.id, targets)
        self.assertNotIn(self.inactive.id, targets)

    def test_07_selected_list_excludes_lower_structure(self) -> None:
        selectable = {
            item.workplace_id
            for item in audit_extraordinary_question_service.list_selectable_workplaces()
        }
        self.assertNotIn(self.workplace.id, selectable)
        self.assertNotIn(self.part.id, selectable)

    def test_08_service_rejects_non_auditable_target(self) -> None:
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.create_question(
                question_text="Špatný cíl",
                workplace_ids=[self.workplace.id],
            )
        self.assertEqual(str(ctx.exception), AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)

    def test_09_existing_non_auditable_target_not_deleted(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Historie",
            workplace_ids=[self.ok.id],
        )
        now = datetime.now()
        with get_session() as session:
            session.add(
                AuditExtraordinaryQuestionTarget(
                    question_id=question.id,
                    workplace_id=self.workplace.id,
                    status=EXTRAORDINARY_TARGET_STATUS_PENDING,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        targets = audit_extraordinary_question_service.repository.list_targets_for_question(
            question.id
        )
        ids = {int(t.workplace_id) for t in targets}
        self.assertIn(self.workplace.id, ids)
        self.assertIn(self.ok.id, ids)

    def test_10_pending_non_auditable_can_cancel(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Cancel hist",
            workplace_ids=[self.ok.id],
        )
        now = datetime.now()
        with get_session() as session:
            session.add(
                AuditExtraordinaryQuestionTarget(
                    question_id=question.id,
                    workplace_id=self.part.id,
                    status=EXTRAORDINARY_TARGET_STATUS_PENDING,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        audit_extraordinary_question_service.update_question(
            question.id,
            cancel_workplace_ids=[self.part.id],
        )
        targets = {
            int(t.workplace_id): t.status
            for t in audit_extraordinary_question_service.repository.list_targets_for_question(
                question.id
            )
        }
        self.assertEqual(targets[self.part.id], EXTRAORDINARY_TARGET_STATUS_CANCELLED)

    def test_11_cancelled_non_auditable_cannot_restore(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="Restore hist",
            workplace_ids=[self.ok.id],
        )
        now = datetime.now()
        with get_session() as session:
            session.add(
                AuditExtraordinaryQuestionTarget(
                    question_id=question.id,
                    workplace_id=self.workplace.id,
                    status=EXTRAORDINARY_TARGET_STATUS_CANCELLED,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        with self.assertRaises(AuditExtraordinaryError) as ctx:
            audit_extraordinary_question_service.update_question(
                question.id,
                restore_workplace_ids=[self.workplace.id],
            )
        self.assertEqual(str(ctx.exception), EXTRAORDINARY_NON_AUDITABLE_RESTORE_BLOCKED)
        with self.assertRaises(AuditExtraordinaryError):
            audit_extraordinary_question_service.restore_target(
                question.id, self.workplace.id
            )

    def test_12_manual_selector_loader_only_auditable(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces()}
        self.assertEqual(
            ids,
            {
                int(w.id)
                for w in list_auditable_workplaces()
                if is_auditable_workplace(w)
            },
        )
        self.assertTrue(all(is_auditable_workplace(w) for w in list_auditable_workplaces()))

    def test_13_14_manual_create_rejects_workplace_no_partial(self) -> None:
        with get_session() as session:
            before_audits = len(list(session.scalars(select(Audit))))
            before_count = len(
                list(session.scalars(select(AuditQuestionSnapshot)))
            )

        with self.assertRaises(AuditV2CreateError) as ctx:
            create_manual_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.workplace.id,
                    "workplace_name": self.workplace.name,
                    "year": 2026,
                    "started_at": date(2026, 3, 1),
                    "title": "Nesmí vzniknout",
                },
            )
        self.assertEqual(str(ctx.exception), AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)
        with get_session() as session:
            after_audits = len(list(session.scalars(select(Audit))))
            after_count = len(list(session.scalars(select(AuditQuestionSnapshot))))
        self.assertEqual(after_audits, before_audits)
        self.assertEqual(after_count, before_count)

    def test_15_system_combo_source_only_auditable(self) -> None:
        ids = {int(w.id) for w in list_auditable_workplaces()}
        self.assertIn(self.system.id, ids)
        self.assertNotIn(self.off.id, ids)
        self.assertNotIn(self.workplace.id, ids)

    def test_16_system_service_rejects_non_auditable_save(self) -> None:
        with self.assertRaises(SystemAuditWorkplaceError) as ctx:
            system_audit_workplace_service.set_system_audit_workplace_id(
                self.workplace.id
            )
        self.assertEqual(str(ctx.exception), AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)
        self.assertEqual(
            system_audit_workplace_service.get_system_audit_workplace_id(),
            self.system.id,
        )

    def test_17_invalid_saved_system_not_auto_cleared(self) -> None:
        # Ulož neplatné nastavení přímo do souboru (obejití validace).
        path = system_audit_workplace_service.settings_path()
        path.write_text(
            '{"system_audit_workplace_id": %d}\n' % self.off.id,
            encoding="utf-8",
        )
        self.assertEqual(
            system_audit_workplace_service.get_system_audit_workplace_id(),
            self.off.id,
        )
        self.assertFalse(system_audit_workplace_service.is_saved_system_workplace_valid())

    def test_18_invalid_system_blocks_new_audit(self) -> None:
        path = system_audit_workplace_service.settings_path()
        path.write_text(
            '{"system_audit_workplace_id": %d}\n' % self.off.id,
            encoding="utf-8",
        )
        with self.assertRaises(SystemAuditWorkplaceError) as ctx:
            system_audit_workplace_service.require_system_audit_workplace_id()
        self.assertEqual(str(ctx.exception), SYSTEM_AUDIT_WORKPLACE_INVALID_MESSAGE)
        with self.assertRaises(SystemAuditWorkplaceError):
            create_audit_with_v2_snapshot(
                fields={
                    "workplace_id": self.ok.id,
                    "workplace_name": self.ok.name,
                    "year": 2026,
                    "started_at": date(2026, 3, 1),
                    "title": "Blocked",
                },
                workplace_id=self.ok.id,
                knowledge_tree=_minimal_tree(),
                ensure_knowledge=False,
            )

    def test_19_program_generation_uses_auditable_rule(self) -> None:
        program = audit_program_service.create_program(
            name="AW Program nový",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            standards=DEFAULT_AUDIT_PROGRAM_STANDARDS,
        )
        created = audit_program_service.sync_workplaces_from_settings(program.id)
        self.assertGreaterEqual(created, 1)
        wp_ids = {
            int(w.workplace_id)
            for w in audit_program_service.repository.list_workplaces(program.id)
            if w.workplace_id is not None
        }
        self.assertIn(self.ok.id, wp_ids)
        self.assertNotIn(self.off.id, wp_ids)
        self.assertNotIn(self.workplace.id, wp_ids)
        self.assertNotIn(self.part.id, wp_ids)
        missing = {
            item.workplace_id
            for item in audit_program_service.list_missing_auditable_workplaces(program.id)
        }
        self.assertNotIn(self.off.id, missing)
        self.assertNotIn(self.workplace.id, missing)

    def test_20_existing_program_not_auto_changed(self) -> None:
        program = audit_program_service.create_program(
            name="AW Program existující",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
            standards=DEFAULT_AUDIT_PROGRAM_STANDARDS,
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self.ok.id,
            workplace_name=self.ok.name,
            audit_interval_months=12,
            preferred_months_json="[3]",
            active=True,
        )
        visits_before = audit_program_service.generate_visits(program.id)
        before_wp = [
            (w.workplace_id, w.workplace_name, w.active)
            for w in audit_program_service.repository.list_workplaces(program.id)
        ]
        before_visits = [
            (v.id, v.workplace_id, v.planned_year, v.planned_month, v.audit_id)
            for v in audit_program_service.repository.list_visits(program.id)
        ]
        # Změna nastavení / nový provoz nesmí automaticky přepsat existující program.
        settings_service.save_workplace(
            id=self.ok.id,
            name=self.ok.name,
            active=True,
            audit_enabled=False,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        after_wp = [
            (w.workplace_id, w.workplace_name, w.active)
            for w in audit_program_service.repository.list_workplaces(program.id)
        ]
        after_visits = [
            (v.id, v.workplace_id, v.planned_year, v.planned_month, v.audit_id)
            for v in audit_program_service.repository.list_visits(program.id)
        ]
        self.assertEqual(after_wp, before_wp)
        self.assertEqual(after_visits, before_visits)
        self.assertGreaterEqual(len(before_visits), 1)
        self.assertGreaterEqual(len(visits_before.created_visits), 1)

    def test_21_historical_audit_on_lower_structure_readable(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            started_at=date(2025, 6, 1),
            title="Historie nižší struktura",
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.workplace_id, self.workplace.id)
        self.assertEqual(loaded.title, "Historie nižší struktura")

    def test_require_helper_message(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            require_auditable_workplace_id(self.part.id)
        self.assertEqual(str(ctx.exception), AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)


if __name__ == "__main__":
    unittest.main()
