"""AUDIT-INTRO-2: Úvod v podrobné, roční a závěrečné zprávě."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete, select

_TMP = Path(tempfile.mkdtemp(prefix="audit-intro-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import (
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.constants import (
        AUDIT_INTRO_CHANGES_EMPTY,
        AUDIT_INTRO_CHANGES_LABEL,
        AUDIT_INTRO_CONTINUITY_SECTION,
        AUDIT_INTRO_EXPORT_SECTION,
        AUDIT_INTRO_FINDINGS_GROUP,
        AUDIT_INTRO_FIRST_AUDIT_MESSAGE,
        AUDIT_INTRO_NO_HISTORICAL_FINDINGS,
        AUDIT_INTRO_NO_HISTORICAL_TASKS,
        AUDIT_INTRO_PREVIOUS_AUDITS_GROUP,
        AUDIT_INTRO_TASKS_GROUP,
        AUDIT_METHODOLOGY_GENERATION_LEGACY_V1,
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_history_service import audit_history_service
    from moduly.audity.sluzby.audit_intro_export_service import audit_intro_export_service
    from moduly.audity.sluzby.audit_annual_export_context_service import (
        audit_annual_export_context_service,
    )
    from moduly.audity.sluzby.audit_annual_report_service import audit_annual_report_service
    from moduly.audity.sluzby.audit_program_final_export_context_service import (
        audit_program_final_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.audit_terrain_checklist_service import (
        audit_terrain_checklist_service,
    )
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.sluzby.rocni_zprava_auditu_service import rocni_zprava_auditu_service
    from moduly.audity.sluzby.zaverecna_zprava_programu_auditu_service import (
        zaverecna_zprava_programu_auditu_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class AuditIntro2ExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()
        cls.workplace = settings_service.save_workplace(name="Provoz INTRO-2")
        cls.workplace_b = settings_service.save_workplace(name="Provoz INTRO-2 B")
        cls.worker = settings_service.save_worker(
            first_name="Auditor",
            last_name="INTRO-2",
        )

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Finding))
            session.commit()
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_audit(self, *, workplace=None, year=2026, month=4, **fields):
        workplace = workplace or self.workplace
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=year,
            planned_month=month,
            **fields,
        )

    def test_detailed_report_contains_intro_section(self) -> None:
        audit = self._create_audit(
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 10),
        )
        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        content = _odt_text(path)
        self.assertIn(AUDIT_INTRO_EXPORT_SECTION, content)
        self.assertIn(AUDIT_INTRO_CHANGES_LABEL, content)
        self.assertIn(AUDIT_INTRO_FIRST_AUDIT_MESSAGE, content)

    def test_detailed_report_shows_saved_changes(self) -> None:
        audit = self._create_audit()
        audit = audit_service.update_audit(
            audit.id,
            changes_since_last="Nová linka.\n\nDruhý odstavec.",
        )
        text = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).intro_text()
        self.assertIn("Nová linka.", text)
        self.assertIn("Druhý odstavec.", text)
        self.assertNotIn(AUDIT_INTRO_CHANGES_EMPTY, text)

    def test_detailed_report_empty_changes_message(self) -> None:
        audit = self._create_audit()
        text = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).intro_text()
        self.assertIn(AUDIT_INTRO_CHANGES_EMPTY, text)

    def test_first_audit_no_empty_history_tables(self) -> None:
        audit = self._create_audit()
        text = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).intro_text()
        self.assertIn(AUDIT_INTRO_FIRST_AUDIT_MESSAGE, text)
        self.assertNotIn(AUDIT_INTRO_PREVIOUS_AUDITS_GROUP, text)
        self.assertNotIn(AUDIT_INTRO_FINDINGS_GROUP, text)
        self.assertNotIn(AUDIT_INTRO_TASKS_GROUP, text)
        self.assertIn(AUDIT_INTRO_CHANGES_LABEL, text)

    def test_previous_audits_findings_tasks_exclude_current(self) -> None:
        previous = self._create_audit(
            year=2025,
            month=3,
            audit_date=date(2025, 3, 1),
            finished_at=date(2025, 3, 1),
        )
        older = self._create_audit(
            year=2024,
            month=2,
            audit_date=date(2024, 2, 1),
            finished_at=date(2024, 2, 1),
        )
        open_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Otevřené zjištění historie",
            status=FINDING_STATUS_OTEVRENE,
        )
        closed_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Vypořádané zjištění historie",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2025, 4, 1),
        )
        active_task = task_service.create_task(
            title="Aktivní úkol historie",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 5, 1),
        )
        done_task = task_service.create_task(
            title="Hotový úkol historie",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 5, 2),
            completed=True,
            completed_date=date(2025, 5, 3),
        )
        canceled_task = task_service.create_task(
            title="Zrušený úkol historie",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 5, 4),
        )
        task_service.cancel_task(canceled_task.id)
        finding_service.update(open_finding.id, task_id=active_task.id)
        finding_service.update(closed_finding.id, task_id=done_task.id)
        cancel_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění se zrušeným úkolem",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.update(cancel_finding.id, task_id=canceled_task.id)

        current = self._create_audit(
            year=2026,
            month=4,
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 10),
            changes_since_last="Změna organizace směn.",
        )
        current_finding = finding_service.create(
            ENTITY_AUDITY,
            current.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Zjištění aktuálního auditu",
            status=FINDING_STATUS_OTEVRENE,
        )
        current_task = task_service.create_task(
            title="Úkol aktuálního auditu",
            responsible_person_id=self.worker.id,
            due_date=date(2026, 6, 1),
        )
        finding_service.update(current_finding.id, task_id=current_task.id)

        values = audit_export_context_service.build(
            current, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).placeholder_values()
        intro = values["uvod_text"]
        self.assertIn("Změna organizace směn.", intro)
        self.assertIn(AUDIT_INTRO_PREVIOUS_AUDITS_GROUP, intro)
        self.assertIn(str(previous.number or previous.id), intro)
        self.assertIn(str(older.number or older.id), intro)
        self.assertNotIn(str(current.number or current.id) + "\n", intro.split(AUDIT_INTRO_PREVIOUS_AUDITS_GROUP, 1)[-1][:200])
        # Aktuální číslo nesmí být v seznamu předchozích jako položka historie
        history_audits = audit_history_service.get_workplace_history(
            self.workplace.id, exclude_audit_id=current.id
        )
        self.assertNotIn(current.id, [item.audit_id for item in history_audits.previous_audits])

        self.assertIn("Otevřené zjištění historie", intro)
        self.assertIn("Vypořádané zjištění historie", intro)
        self.assertNotIn("Zjištění aktuálního auditu", intro)
        self.assertIn("Aktivní úkol historie", intro)
        self.assertIn("Hotový úkol historie", intro)
        self.assertIn("Zrušený úkol historie", intro)
        self.assertNotIn("Úkol aktuálního auditu", intro)

        path = protokol_audit_service.generate_detailed_report_for_audit(current)
        content = _odt_text(path)
        self.assertIn("Otevřené zjištění historie", content)
        self.assertIn("Změna organizace směn.", content)

    def test_missing_findings_and_tasks_messages(self) -> None:
        previous = self._create_audit(
            year=2025,
            month=1,
            audit_date=date(2025, 1, 1),
            finished_at=date(2025, 1, 1),
        )
        current = self._create_audit(year=2026, month=4)
        text = audit_export_context_service.build(
            current, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).intro_text()
        self.assertIn(str(previous.number or previous.id), text)
        self.assertIn(AUDIT_INTRO_NO_HISTORICAL_FINDINGS, text)
        self.assertIn(AUDIT_INTRO_NO_HISTORICAL_TASKS, text)

    def test_protocol_and_terrain_without_intro(self) -> None:
        previous = self._create_audit(
            year=2025,
            month=1,
            audit_date=date(2025, 1, 1),
            finished_at=date(2025, 1, 1),
        )
        finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Historické zjištění protokol",
            status=FINDING_STATUS_OTEVRENE,
        )
        current = self._create_audit(
            year=2026,
            month=4,
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 10),
            changes_since_last="Text změn jen pro podrobnou zprávu.",
        )
        protocol_values = audit_export_context_service.build(
            current, config=PROTOCOL_DOCUMENT_CONFIG
        ).placeholder_values()
        self.assertNotIn("uvod_text", protocol_values)

        protocol_path = protokol_audit_service.generate_for_audit(current)
        protocol_content = _odt_text(protocol_path)
        self.assertNotIn(AUDIT_INTRO_EXPORT_SECTION, protocol_content)
        self.assertNotIn("Text změn jen pro podrobnou zprávu.", protocol_content)
        self.assertNotIn(AUDIT_INTRO_CHANGES_EMPTY, protocol_content)
        self.assertNotIn("Historické zjištění protokol", protocol_content)

        checklist_path = audit_terrain_checklist_service.generate_for_audit(current)
        checklist_content = _odt_text(checklist_path)
        self.assertNotIn(AUDIT_INTRO_EXPORT_SECTION, checklist_content)
        self.assertNotIn(AUDIT_INTRO_CONTINUITY_SECTION, checklist_content)
        self.assertNotIn("Text změn jen pro podrobnou zprávu.", checklist_content)
        self.assertNotIn("Historické zjištění protokol", checklist_content)

    def test_annual_and_final_continuity_counts_deduped(self) -> None:
        previous = self._create_audit(
            year=2025,
            month=1,
            audit_date=date(2025, 1, 1),
            finished_at=date(2025, 1, 1),
        )
        open_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Historické otevřené",
            status=FINDING_STATUS_OTEVRENE,
        )
        closed_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Historické vypořádané",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2025, 2, 1),
        )
        active_task = task_service.create_task(
            title="Historický aktivní",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 3, 1),
        )
        done_task = task_service.create_task(
            title="Historický hotový",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 3, 2),
            completed=True,
            completed_date=date(2025, 3, 3),
        )
        canceled_task = task_service.create_task(
            title="Historický zrušený",
            responsible_person_id=self.worker.id,
            due_date=date(2025, 3, 4),
        )
        task_service.cancel_task(canceled_task.id)
        finding_service.update(open_finding.id, task_id=active_task.id)
        finding_service.update(closed_finding.id, task_id=done_task.id)
        cancel_finding = finding_service.create(
            ENTITY_AUDITY,
            previous.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Pro zrušený úkol",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.update(cancel_finding.id, task_id=canceled_task.id)

        current_a = self._create_audit(
            year=2026,
            month=4,
            audit_date=date(2026, 4, 1),
            finished_at=date(2026, 4, 1),
        )
        current_b = self._create_audit(
            workplace=self.workplace,
            year=2026,
            month=5,
            audit_date=date(2026, 5, 1),
            finished_at=date(2026, 5, 1),
        )
        # Zjištění aktuálních auditů nesmí vstoupit do agregace.
        finding_service.create(
            ENTITY_AUDITY,
            current_a.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Aktuální zjištění A",
            status=FINDING_STATUS_OTEVRENE,
        )

        aggregate = audit_history_service.aggregate_continuity_for_audits(
            [current_a, current_b]
        )
        self.assertEqual(aggregate.previous_audits_count, 1)
        self.assertEqual(aggregate.findings_total_count, 3)
        self.assertEqual(aggregate.findings_open_count, 2)
        self.assertEqual(aggregate.findings_resolved_count, 1)
        self.assertEqual(aggregate.tasks_total_count, 3)
        self.assertEqual(aggregate.tasks_active_count, 1)
        self.assertEqual(aggregate.tasks_completed_count, 1)
        self.assertEqual(aggregate.tasks_canceled_count, 1)

        with patch.object(
            audit_history_service,
            "get_workplace_history",
            wraps=audit_history_service.get_workplace_history,
        ) as mocked:
            text = audit_intro_export_service.build_continuity_text_for_audits(
                [current_a, current_b]
            )
            # Jedno volání na provoz, ne na každý audit.
            self.assertEqual(mocked.call_count, 1)

        self.assertIn("Počet dohledaných předchozích auditů: 1", text)
        self.assertIn("Počet historických zjištění celkem: 3", text)
        self.assertNotIn("Historické otevřené", text)
        self.assertNotIn("Aktuální zjištění A", text)

        program = audit_program_service.create_program(
            name="Program INTRO-2",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            audit_interval_months=6,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=self.workplace.id,
            planned_year=2026,
            planned_month=4,
        )
        audit_service.update_audit(current_a.id, program_id=program.id)
        audit_service.update_audit(current_b.id, program_id=program.id)
        audit_annual_report_service.save_for_year(2026, audit_program_id=program.id)

        annual = audit_annual_export_context_service.build(2026)
        annual_text = annual.continuity_previous_audits_text
        self.assertIn("Počet dohledaných předchozích auditů: 1", annual_text)
        self.assertNotIn("Historické otevřené", annual_text)
        annual_path = rocni_zprava_auditu_service.generate_for_year(2026)
        annual_content = _odt_text(annual_path)
        self.assertIn(AUDIT_INTRO_CONTINUITY_SECTION, annual_content)
        self.assertIn("Počet historických zjištění celkem: 3", annual_content)

        final = audit_program_final_export_context_service.build(program.id)
        self.assertIn(
            "Počet dohledaných předchozích auditů: 1",
            final.continuity_previous_audits_text,
        )
        final_path = zaverecna_zprava_programu_auditu_service.generate_for_program(
            program.id
        )
        final_content = _odt_text(final_path)
        self.assertIn(AUDIT_INTRO_CONTINUITY_SECTION, final_content)
        self.assertIn("Počet historických úkolů celkem: 3", final_content)

    def test_export_does_not_write_db(self) -> None:
        audit = self._create_audit(
            started_at=date(2026, 4, 1),
            finished_at=date(2026, 4, 10),
            changes_since_last="Bez zápisu.",
        )
        before = audit_service.get_by_id(audit.id)
        assert before is not None
        before_updated = before.updated_at
        before_changes = before.changes_since_last

        audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).placeholder_values()
        protokol_audit_service.generate_detailed_report_for_audit(audit)

        after = audit_service.get_by_id(audit.id)
        assert after is not None
        self.assertEqual(after.updated_at, before_updated)
        self.assertEqual(after.changes_since_last, before_changes)

    def test_snapshots_untouched_for_legacy_and_v2(self) -> None:
        legacy = self._create_audit(year=2025, month=1)
        v2 = self._create_audit(year=2026, month=2)
        with get_session() as session:
            for audit, generation in (
                (legacy, AUDIT_METHODOLOGY_GENERATION_LEGACY_V1),
                (v2, AUDIT_METHODOLOGY_GENERATION_V2),
            ):
                row = session.get(Audit, audit.id)
                assert row is not None
                row.methodology_source = AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
                row.methodology_generation = generation
                session.add(
                    AuditQuestionSnapshot(
                        audit_id=audit.id,
                        process_id="p",
                        process_name="P",
                        section_id="s",
                        section_name="S",
                        assertion_id=f"q-{audit.id}",
                        assertion_text="Snapshot text",
                        verification_type="dokumentace",
                        severity="stredni",
                        question_kind=(
                            "legacy"
                            if generation == AUDIT_METHODOLOGY_GENERATION_LEGACY_V1
                            else "operation"
                        ),
                        display_order=1,
                        is_in_scope=True,
                    )
                )
            session.commit()

        before = {}
        with get_session() as session:
            for audit_id in (legacy.id, v2.id):
                rows = list(
                    session.scalars(
                        select(AuditQuestionSnapshot).where(
                            AuditQuestionSnapshot.audit_id == audit_id
                        )
                    )
                )
                before[audit_id] = [
                    (row.assertion_id, row.assertion_text, row.is_in_scope)
                    for row in rows
                ]
                audit_row = session.get(Audit, audit_id)
                assert audit_row is not None
                before[(audit_id, "meta")] = (
                    audit_row.methodology_source,
                    audit_row.methodology_generation,
                )

        for audit in (legacy, v2):
            audit_export_context_service.build(
                audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
            ).intro_text()

        with get_session() as session:
            for audit_id in (legacy.id, v2.id):
                rows = list(
                    session.scalars(
                        select(AuditQuestionSnapshot).where(
                            AuditQuestionSnapshot.audit_id == audit_id
                        )
                    )
                )
                self.assertEqual(
                    [
                        (row.assertion_id, row.assertion_text, row.is_in_scope)
                        for row in rows
                    ],
                    before[audit_id],
                )
                audit_row = session.get(Audit, audit_id)
                assert audit_row is not None
                self.assertEqual(
                    (audit_row.methodology_source, audit_row.methodology_generation),
                    before[(audit_id, "meta")],
                )


if __name__ == "__main__":
    unittest.main()
