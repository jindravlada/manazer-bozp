"""PROVERKY-PLANNED-SECTION-SUMMARY-MIGRATION-1: čisté plánované Prověrky."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import unittest
import uuid
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="proverky-planned-ss-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.upgrade_guard import (
        MigrationGuardError,
        PreMigrationBackupError,
        is_migration_failed,
        is_transition_complete,
        prepare_database_for_startup,
    )
    from core.services.attachment_service import attachment_service
    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_VYHOVUJE,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.section_summary import NOTES_MODE_SECTION_SUMMARY_V1
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.widgets.control_result_selector import ControlResultSelectorWidget
    from core.widgets.section_summary_edit import SectionSummaryEdit
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        INSPECTION_STATUS_DOKONCENO,
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_STATUS_PROBIHA,
        VERIFICATION_TYPE_DOCUMENTATION,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.proverky_planned_section_summary_migration import (
        BACKUP_NAME_PREFIX,
        SKIP_ATTACHMENTS,
        SKIP_COMMENTS,
        SKIP_FINDINGS,
        SKIP_OTHER_DATA,
        SKIP_OTHER_STATUS,
        SKIP_PHOTOS,
        SKIP_RESULTS,
        SKIP_STARTED_FINISHED,
        SKIP_TASKS,
        TRANSITION_ID,
        collect_planned_section_summary_inventory,
        prepare_proverky_planned_section_summary_migration,
    )
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget
    from moduly.ukoly.sluzby.task_service import task_service


def _db() -> Path:
    return storage_module.storage_service.database_path


def _ws() -> Path:
    return storage_module.storage_service.base


def _sql(query: str, params=()):
    connection = sqlite3.connect(str(_db()))
    try:
        cursor = connection.execute(query, params)
        rows = cursor.fetchall()
        connection.commit()
        return rows
    finally:
        connection.close()


def _count(table: str) -> int:
    return int(_sql(f'SELECT COUNT(*) FROM "{table}"')[0][0])


def _notes_mode(inspection_id: int):
    return _sql("SELECT notes_mode FROM bozp_inspections WHERE id = ?", (inspection_id,))[0][0]


def _inspection_row(inspection_id: int) -> tuple:
    return _sql(
        "SELECT id, number, year, planned_month, inspection_date, started_at, "
        "finished_at, status, inspection_type, workplace_id, workplace_name, "
        "title, silne_stranky, doporuceni_vedouciho, created_at, updated_at "
        "FROM bozp_inspections WHERE id = ?",
        (inspection_id,),
    )[0]


def _point(suffix: str = "1") -> ControlPointContext:
    return ControlPointContext(
        area_id="a1",
        area_label="Oblast",
        section_id="s1",
        section_label="Okruh",
        control_point_id=f"k{suffix}",
        control_point_label=f"Bod {suffix}",
    )


def _section() -> dict:
    return {
        "id": "s1",
        "nazev": "Okruh",
        "popis": "Popis okruhu.",
        "aktivni": True,
        "kontrolni_body": [
            {
                "id": "k1",
                "nazev": "Bod 1",
                "popis": "Popis bodu",
                "aktivni": True,
                "poradi": 10,
                "verification_type": VERIFICATION_TYPE_DOCUMENTATION,
                "zavaznost": "stredni",
            }
        ],
        "typicke_zavady": [],
        "doporucene_postupy": [],
        "legislativa": [],
        "historie": [],
        "referencni_fotografie": [],
        "postup_kontroly": [],
    }


class ProverkyPlannedSectionSummaryMigration1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        state_path = _ws() / "konfigurace" / "migration_state.json"
        if state_path.exists():
            state_path.unlink()
        for backup in (_ws() / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"):
            backup.unlink()
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        _sql(
            "DELETE FROM attachments WHERE entity_type IN (?, ?)",
            (ENTITY_PROVERKY, "inspection"),
        )
        _sql(
            "DELETE FROM tasks WHERE source_module IN (?, ?, ?)",
            (ENTITY_PROVERKY, "inspection", "finding"),
        )
        _sql(
            "DELETE FROM control_results WHERE entity_type = ?",
            (ENTITY_PROVERKY,),
        )
        _sql("DELETE FROM inspection_section_summaries")

    def _legacy(self, **fields):
        fields.setdefault("title", f"Legacy {uuid.uuid4().hex[:6]}")
        fields["notes_mode"] = None
        return bozp_inspection_service.create_inspection(**fields)

    def _run(self):
        return prepare_proverky_planned_section_summary_migration(
            workspace_root=_ws(),
            database_path=_db(),
        )

    def _backups(self) -> list[Path]:
        return list((_ws() / "zalohy").glob(f"{BACKUP_NAME_PREFIX}*"))

    def _insert_technical_result(self, inspection_id: int) -> None:
        _sql(
            "INSERT INTO control_results ("
            "entity_type, entity_id, source_area_id, source_area_label, "
            "source_section_id, source_section_label, source_control_point_id, "
            "source_control_point_label, result, note, shared_experience, "
            "photo_path, recorded_by_name, created_at, updated_at"
            ") VALUES (?, ?, 'a1', 'Oblast', 's1', 'Okruh', 'k1', 'Bod 1', "
            "?, '', 0, '', '', ?, ?)",
            (
                ENTITY_PROVERKY,
                inspection_id,
                CONTROL_RESULT_NEKONTROLOVANO,
                datetime.now().isoformat(sep=" ", timespec="seconds"),
                datetime.now().isoformat(sep=" ", timespec="seconds"),
            ),
        )

    def test_clean_planned_converts(self) -> None:
        inspection = self._legacy()
        result = self._run()
        self.assertTrue(result.migrated)
        self.assertEqual(result.converted_ids, (inspection.id,))
        self.assertEqual(_notes_mode(inspection.id), NOTES_MODE_SECTION_SUMMARY_V1)
        self.assertEqual(
            bozp_inspection_service.get_by_id(inspection.id).status,
            INSPECTION_STATUS_PLANOVANO,
        )

    def test_technical_nekontrolovano_rows_convert(self) -> None:
        inspection = self._legacy()
        self._insert_technical_result(inspection.id)
        result = self._run()
        self.assertIn(inspection.id, result.converted_ids)
        self.assertEqual(_notes_mode(inspection.id), NOTES_MODE_SECTION_SUMMARY_V1)
        row = _sql(
            "SELECT result, note, photo_path, shared_experience, recorded_by_name "
            "FROM control_results WHERE entity_id = ?",
            (inspection.id,),
        )[0]
        self.assertEqual(row[0], CONTROL_RESULT_NEKONTROLOVANO)
        self.assertEqual(row[1], "")
        self.assertEqual(row[2], "")
        self.assertFalse(row[3])
        self.assertEqual(row[4], "")

    def test_evaluated_point_skipped(self) -> None:
        inspection = self._legacy()
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            _point(),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        result = self._run()
        self.assertNotIn(inspection.id, result.converted_ids)
        self.assertEqual(result.skipped[inspection.id], SKIP_RESULTS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_individual_comment_skipped(self) -> None:
        inspection = self._legacy()
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            _point(),
            result=CONTROL_RESULT_NEKONTROLOVANO,
            note="Komentář",
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_COMMENTS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_shared_experience_skipped(self) -> None:
        inspection = self._legacy()
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            _point(),
            result=CONTROL_RESULT_NEKONTROLOVANO,
            shared_experience=True,
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_OTHER_DATA)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_photo_skipped(self) -> None:
        inspection = self._legacy()
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            _point(),
            result=CONTROL_RESULT_NEKONTROLOVANO,
            photo_path="fotografie/bod.jpg",
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_PHOTOS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_finding_skipped(self) -> None:
        inspection = self._legacy()
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_FINDINGS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_task_skipped(self) -> None:
        inspection = self._legacy()
        task_service.create_task(
            title="Úkol z prověrky",
            source_module=ENTITY_PROVERKY,
            source_record_id=inspection.id,
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_TASKS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_attachment_skipped(self) -> None:
        inspection = self._legacy()
        source = _TMP / f"priloha-{uuid.uuid4().hex[:6]}.txt"
        source.write_text("priloha", encoding="utf-8")
        self.assertIsNotNone(
            attachment_service.add_file(ENTITY_PROVERKY, inspection.id, str(source))
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_ATTACHMENTS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_started_skipped(self) -> None:
        inspection = self._legacy(started_at=date(2026, 3, 1))
        self.assertEqual(inspection.status, INSPECTION_STATUS_PROBIHA)
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_OTHER_STATUS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_completed_skipped(self) -> None:
        inspection = self._legacy(
            started_at=date(2026, 3, 1),
            finished_at=date(2026, 3, 2),
        )
        self.assertEqual(inspection.status, INSPECTION_STATUS_DOKONCENO)
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_OTHER_STATUS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_cancelled_skipped(self) -> None:
        inspection = self._legacy()
        _sql(
            "UPDATE bozp_inspections SET status = ? WHERE id = ?",
            ("Zrušeno", inspection.id),
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_OTHER_STATUS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_already_section_summary_unchanged(self) -> None:
        inspection = bozp_inspection_service.create_inspection(title="Nová v1")
        self.assertEqual(inspection.notes_mode, NOTES_MODE_SECTION_SUMMARY_V1)
        before = _inspection_row(inspection.id)
        result = self._run()
        self.assertNotIn(inspection.id, result.converted_ids)
        self.assertNotIn(inspection.id, result.skipped)
        self.assertEqual(_notes_mode(inspection.id), NOTES_MODE_SECTION_SUMMARY_V1)
        self.assertEqual(_inspection_row(inspection.id), before)

    def test_unclear_status_skipped(self) -> None:
        inspection = self._legacy()
        _sql(
            "UPDATE bozp_inspections SET status = ? WHERE id = ?",
            ("neznamy", inspection.id),
        )
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_OTHER_STATUS)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_planned_with_dates_inconsistent_skipped(self) -> None:
        inspection = self._legacy()
        _sql(
            "UPDATE bozp_inspections SET started_at = ? WHERE id = ?",
            ("2026-04-01", inspection.id),
        )
        status = _sql(
            "SELECT status FROM bozp_inspections WHERE id = ?", (inspection.id,)
        )[0][0]
        self.assertEqual(status, INSPECTION_STATUS_PLANOVANO)
        result = self._run()
        self.assertEqual(result.skipped[inspection.id], SKIP_STARTED_FINISHED)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_preserves_planning_fields_and_commission(self) -> None:
        workplace = settings_service.save_workplace(name=f"Provoz {uuid.uuid4().hex[:6]}")
        suffix = uuid.uuid4().hex[:6]
        leader = settings_service.save_worker(first_name="Jan", last_name=f"L-{suffix}").id
        workplace_rep = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        union = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id
        inspection = self._legacy(
            year=2026,
            planned_month=5,
            inspection_date=date(2026, 5, 12),
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            title=f"Prověrka BOZP – {workplace.name}",
        )
        bozp_inspection_commission_service.save_members(
            inspection.id,
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
                    "thp_worker_id": workplace_rep,
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
        before = _inspection_row(inspection.id)
        members_before = [
            (row.record_type, row.thp_worker_id, row.person_id, row.display_name)
            for row in bozp_inspection_commission_service.get_for_inspection(inspection.id)
        ]
        result = self._run()
        self.assertIn(inspection.id, result.converted_ids)
        self.assertEqual(_inspection_row(inspection.id), before)
        self.assertEqual(_notes_mode(inspection.id), NOTES_MODE_SECTION_SUMMARY_V1)
        members_after = [
            (row.record_type, row.thp_worker_id, row.person_id, row.display_name)
            for row in bozp_inspection_commission_service.get_for_inspection(inspection.id)
        ]
        self.assertEqual(members_after, members_before)

    def test_backup_before_write(self) -> None:
        inspection = self._legacy()
        result = self._run()
        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.pre_migration_backup_path)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(result.pre_migration_backup_path.name.startswith(BACKUP_NAME_PREFIX))
        self.assertEqual(result.pre_migration_backup_path.suffix, ".mbbackup")
        self.assertEqual(_notes_mode(inspection.id), NOTES_MODE_SECTION_SUMMARY_V1)

    def test_backup_failure_no_write(self) -> None:
        inspection = self._legacy()
        with patch(
            "moduly.proverky.sluzby.proverky_planned_section_summary_migration."
            "create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("záloha selhala"),
        ):
            with self.assertRaises(MigrationGuardError):
                self._run()
        self.assertIsNone(_notes_mode(inspection.id))
        self.assertFalse(is_transition_complete(_ws(), TRANSITION_ID))
        self.assertEqual(self._backups(), [])

    def test_convert_error_full_rollback(self) -> None:
        inspection = self._legacy()
        with patch(
            "moduly.proverky.sluzby.proverky_planned_section_summary_migration."
            "_validate_conversion",
            side_effect=RuntimeError("umělá chyba převodu"),
        ):
            with self.assertRaises(MigrationGuardError):
                self._run()
        self.assertIsNone(_notes_mode(inspection.id))
        self.assertFalse(is_transition_complete(_ws(), TRANSITION_ID))
        self.assertTrue(is_migration_failed(_ws(), TRANSITION_ID))

    def test_idempotent_repeat_no_second_backup(self) -> None:
        inspection = self._legacy()
        first = self._run()
        self.assertTrue(first.migrated)
        backups_first = self._backups()
        self.assertEqual(len(backups_first), 1)
        second = self._run()
        self.assertFalse(second.migrated)
        self.assertEqual(second.skipped_reason, "already_complete")
        self.assertEqual(self._backups(), backups_first)
        self.assertEqual(_notes_mode(inspection.id), NOTES_MODE_SECTION_SUMMARY_V1)

    def test_no_eligible_no_backup_no_db_change(self) -> None:
        inspection = self._legacy(started_at=date(2026, 2, 1))
        before = _inspection_row(inspection.id)
        result = self._run()
        self.assertFalse(result.migrated)
        self.assertEqual(result.skipped_reason, "no_eligible")
        self.assertEqual(self._backups(), [])
        self.assertTrue(is_transition_complete(_ws(), TRANSITION_ID))
        self.assertEqual(_inspection_row(inspection.id), before)
        self.assertIsNone(_notes_mode(inspection.id))

    def test_audits_not_converted(self) -> None:
        audit = audit_service.create_audit(title="Legacy audit", notes_mode=None)
        inspection = self._legacy()
        result = self._run()
        self.assertIn(inspection.id, result.converted_ids)
        mode = _sql("SELECT notes_mode FROM audits WHERE id = ?", (audit.id,))[0][0]
        self.assertIsNone(mode)

    def test_converted_ui_is_section_summary(self) -> None:
        inspection = self._legacy()
        result = self._run()
        self.assertIn(inspection.id, result.converted_ids)
        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        widget = BozpKnowledgeSectionWidget()
        widget.set_notes_mode(reloaded.notes_mode)
        widget.set_inspection_id(reloaded.id)
        widget.set_section(_section(), area_id="a1", area_label="Oblast", section_label="Okruh")
        self.assertTrue(widget.uses_section_summary())
        self.assertIsNotNone(widget.findChild(SectionSummaryEdit))
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertTrue(selectors[0]._note_edit.isHidden())

    def test_skipped_legacy_ui_kept(self) -> None:
        inspection = self._legacy()
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            _point(),
            result=CONTROL_RESULT_VYHOVUJE,
            note="Komentář",
        )
        self._run()
        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        widget = BozpKnowledgeSectionWidget()
        widget.set_notes_mode(reloaded.notes_mode)
        widget.set_inspection_id(reloaded.id)
        widget.set_section(_section(), area_id="a1", area_label="Oblast", section_label="Okruh")
        self.assertFalse(widget.uses_section_summary())
        self.assertIsNone(widget.findChild(SectionSummaryEdit))
        selectors = widget.findChildren(ControlResultSelectorWidget)
        self.assertTrue(selectors)
        self.assertFalse(selectors[0]._note_edit.isHidden())

    def test_opening_converted_inspection_does_not_write(self) -> None:
        inspection = self._legacy()
        result = self._run()
        self.assertIn(inspection.id, result.converted_ids)
        inspection_id = inspection.id
        before_row = _inspection_row(inspection_id)
        before_mode = _notes_mode(inspection_id)
        self.assertEqual(before_mode, NOTES_MODE_SECTION_SUMMARY_V1)
        before_summaries = _count("inspection_section_summaries")
        before_results = _count("control_results")
        dialog = BozpInspectionDialog(
            inspection=bozp_inspection_service.get_by_id(inspection_id)
        )
        dialog.tabs.setCurrentWidget(dialog.areas_widget)
        dialog.tabs.setCurrentWidget(dialog.terrain_widget)
        self._app.processEvents()
        dialog._closing = True
        dialog.close()
        self.assertEqual(_inspection_row(inspection_id), before_row)
        self.assertEqual(_notes_mode(inspection_id), before_mode)
        self.assertEqual(_count("inspection_section_summaries"), before_summaries)
        self.assertEqual(_count("control_results"), before_results)

    def test_inventory_not_n_plus_one(self) -> None:
        for index in range(6):
            self._legacy(title=f"Bulk A {index}")
        connection = sqlite3.connect(str(_db()))
        try:
            traced: list[str] = []
            connection.set_trace_callback(traced.append)
            first = collect_planned_section_summary_inventory(connection)
            first_count = len(traced)
        finally:
            connection.close()
        for index in range(14):
            self._legacy(title=f"Bulk B {index}")
        connection = sqlite3.connect(str(_db()))
        try:
            traced = []
            connection.set_trace_callback(traced.append)
            second = collect_planned_section_summary_inventory(connection)
            second_count = len(traced)
        finally:
            connection.close()
        self.assertEqual(len(first.legacy_ids), 6)
        self.assertEqual(len(second.legacy_ids), 20)
        self.assertEqual(first.query_count, second.query_count)
        self.assertEqual(first_count, second_count)
        self.assertLessEqual(first_count, 40)

    def test_upgrade_guard_calls_migration_after_schema(self) -> None:
        source = inspect.getsource(prepare_database_for_startup)
        self.assertIn("prepare_proverky_planned_section_summary_migration", source)
        schema_pos = source.rfind("prepare_audit_proverky_section_note_schema(")
        data_pos = source.rfind("prepare_proverky_planned_section_summary_migration(")
        self.assertGreater(schema_pos, 0)
        self.assertGreater(data_pos, schema_pos)

    def test_only_notes_mode_changes(self) -> None:
        clean = self._legacy(title="Čistá")
        dirty = self._legacy(title="Špinavá")
        control_result_service.set_result(
            ENTITY_PROVERKY,
            dirty.id,
            _point(),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        before_clean = _inspection_row(clean.id)
        before_dirty = _inspection_row(dirty.id)
        result = self._run()
        self.assertEqual(result.converted_ids, (clean.id,))
        self.assertEqual(_inspection_row(clean.id), before_clean)
        self.assertEqual(_inspection_row(dirty.id), before_dirty)
        self.assertEqual(_notes_mode(clean.id), NOTES_MODE_SECTION_SUMMARY_V1)
        self.assertIsNone(_notes_mode(dirty.id))


if __name__ == "__main__":
    unittest.main()
