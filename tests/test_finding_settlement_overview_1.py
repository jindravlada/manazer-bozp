"""AUDIT-VYPOŘÁDÁNÍ-3: historické snímky přehledů vypořádání."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_finding_settlement_overview_tables,
        initialize_database,
    )

    initialize_database()

    from core.database import session as session_module
    from core.database.session import get_session
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        SETTLEMENT_SOURCE_AUDITY,
        SETTLEMENT_SOURCE_PROVERKY,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_settlement_overview_service import (
        FindingSettlementOverviewError,
        finding_settlement_overview_service,
    )
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import (
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.repository.audit_repository import AuditRepository
    from moduly.proverky.constants import (
        INSPECTION_STATUS_DOKONCENO,
        INSPECTION_STATUS_PROBIHA,
    )
    from moduly.proverky.modely.bozp_inspection import BozpInspection
    from moduly.ukoly.sluzby.task_service import task_service


def _wipe() -> None:
    session_module.reconfigure_database_engine()
    with session_module.engine.begin() as connection:
        connection.execute(text("DELETE FROM finding_settlement_overview_items"))
        connection.execute(text("DELETE FROM finding_settlement_overviews"))
        connection.execute(text("DELETE FROM finding_status_events"))
        connection.execute(text("DELETE FROM findings"))
        connection.execute(text("DELETE FROM tasks"))
        connection.execute(text("DELETE FROM audits"))
        connection.execute(text("DELETE FROM bozp_inspections"))


class FindingSettlementOverviewTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()
        self.audits = AuditRepository()
        self.service = finding_settlement_overview_service

    def _audit(
        self,
        *,
        status: str,
        year: int,
        number: str,
        workplace: str,
    ) -> Audit:
        return self.audits.add(
            Audit(
                number=number,
                year=year,
                status=status,
                workplace_name=workplace,
                title=f"Audit {number}/{year}",
            )
        )

    def _finding(self, audit_id: int, **fields):
        payload = {
            "finding_type": FINDING_TYPE_NESHODA,
            "description": "Zjištění",
            "status": FINDING_STATUS_OTEVRENE,
            "source_area_label": "Údržba",
            "source_section_label": "Zábradlí",
            "recommended_action": "Doplnit zábradlí",
        }
        payload.update(fields)
        return finding_service.create(ENTITY_AUDITY, audit_id, **payload)

    def _items_by_finding(self, overview_id: int) -> dict[int, object]:
        return {item.finding_id: item for item in self.service.items_for(overview_id)}

    def test_baseline_includes_only_completed_audits_of_all_years(self) -> None:
        old = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2019,
            number="4",
            workplace="Dílna",
        )
        current = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2026,
            number="1",
            workplace="Sklad",
        )
        running = self._audit(
            status=AUDIT_STATUS_PROBIHA,
            year=2026,
            number="2",
            workplace="Dvůr",
        )
        planned = self._audit(
            status=AUDIT_STATUS_PLANOVANO,
            year=2024,
            number="3",
            workplace="Kancelář",
        )
        open_old = self._finding(
            old.id,
            description="Stará neshoda",
            finding_type=FINDING_TYPE_NESHODA,
            status=FINDING_STATUS_OTEVRENE,
        )
        settled = self._finding(
            current.id,
            description="Vypořádané pozorování",
            finding_type=FINDING_TYPE_POZOROVANI,
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 3, 1),
        )
        in_process = self._finding(
            current.id,
            description="Rozpracovaná příležitost",
            finding_type=FINDING_TYPE_PRILEZITOST,
            status=FINDING_STATUS_V_PROCESU,
        )
        self._finding(running.id, description="Z probíhajícího")
        self._finding(planned.id, description="Z plánovaného")

        presented = date(2026, 10, 1)
        overview = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=presented,
            note="Bod 0",
        )

        self.assertEqual(overview.sequence_number, 0)
        self.assertEqual(overview.source_type, SETTLEMENT_SOURCE_AUDITY)
        self.assertEqual(overview.presented_at, presented)
        self.assertIsNone(overview.period_from)
        self.assertEqual(overview.period_to, presented)
        self.assertEqual(overview.note, "Bod 0")
        self.assertEqual(overview.total_count, 3)
        self.assertEqual(overview.settled_count, 1)
        self.assertEqual(overview.in_process_count, 1)
        self.assertEqual(overview.open_count, 1)
        self.assertEqual(
            json.loads(overview.type_counts_json),
            {
                FINDING_TYPE_NESHODA: 1,
                FINDING_TYPE_POZOROVANI: 1,
                FINDING_TYPE_PRILEZITOST: 1,
            },
        )
        items = self._items_by_finding(overview.id)
        self.assertEqual(set(items), {open_old.id, settled.id, in_process.id})
        self.assertEqual(items[open_old.id].audit_number, "4")
        self.assertEqual(items[open_old.id].audit_year, 2019)
        self.assertEqual(items[open_old.id].workplace_name, "Dílna")
        self.assertEqual(items[open_old.id].process_label, "Údržba")
        self.assertEqual(items[open_old.id].verification_area_label, "Zábradlí")
        self.assertEqual(items[settled.id].resolved_at, date(2026, 3, 1))
        self.assertTrue(
            all(
                not item.settled_since_previous
                and not item.still_unsettled
                and not item.is_new
                and not item.reopened
                and not item.resettled
                for item in items.values()
            )
        )

    def test_next_overview_compares_with_previous_snapshot(self) -> None:
        old = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2020,
            number="10",
            workplace="Halda",
        )
        fresh = self._audit(
            status=AUDIT_STATUS_PROBIHA,
            year=2026,
            number="11",
            workplace="Rampa",
        )
        will_settle = self._finding(old.id, description="K vypořádání")
        will_reopen = self._finding(
            old.id,
            description="K znovuotevření",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 1, 15),
        )
        stays = self._finding(
            old.id,
            description="Zůstává v procesu",
            status=FINDING_STATUS_V_PROCESU,
            finding_type=FINDING_TYPE_PRILEZITOST,
        )
        hidden = self._finding(fresh.id, description="Ještě ne")

        first = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 6, 1),
        )
        finding_service.update(will_settle.id, status=FINDING_STATUS_VYPORADANO)
        finding_service.update(will_reopen.id, status=FINDING_STATUS_OTEVRENE)
        self.audits.update_fields(fresh.id, status=AUDIT_STATUS_DOKONCENO)
        added = self._finding(old.id, description="Nové po bodu 0")
        self.audits.update_fields(old.id, workplace_name="Přejmenováno")
        finding_service.update(stays.id, description="Upravený text")

        second = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 9, 1),
            note="Druhý",
        )

        self.assertEqual(second.sequence_number, 1)
        self.assertEqual(second.period_from, date(2026, 6, 1))
        self.assertEqual(second.period_to, date(2026, 9, 1))
        later = self._items_by_finding(second.id)
        self.assertEqual(
            set(later),
            {will_settle.id, will_reopen.id, stays.id, hidden.id, added.id},
        )
        self.assertTrue(later[will_settle.id].settled_since_previous)
        self.assertEqual(later[will_settle.id].resolved_at, date.today())
        self.assertFalse(later[will_settle.id].still_unsettled)
        self.assertTrue(later[will_reopen.id].reopened)
        self.assertTrue(later[will_reopen.id].still_unsettled)
        self.assertIsNone(later[will_reopen.id].resolved_at)
        self.assertTrue(later[stays.id].still_unsettled)
        self.assertFalse(later[stays.id].is_new)
        self.assertTrue(later[hidden.id].is_new)
        self.assertTrue(later[hidden.id].still_unsettled)
        self.assertTrue(later[added.id].is_new)
        self.assertTrue(later[added.id].still_unsettled)

        frozen = self._items_by_finding(first.id)
        self.assertEqual(frozen[stays.id].description, "Zůstává v procesu")
        self.assertEqual(frozen[will_reopen.id].status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(frozen[will_reopen.id].resolved_at, date(2026, 1, 15))
        self.assertEqual(frozen[stays.id].workplace_name, "Halda")
        self.assertNotIn(hidden.id, frozen)
        self.assertEqual(len(self.service.items_for(first.id)), 3)

        with self.assertRaises(FindingSettlementOverviewError):
            self.service.create_overview(
                SETTLEMENT_SOURCE_AUDITY,
                presented_at=date(2026, 5, 1),
            )
        self.assertEqual(
            [row.sequence_number for row in self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY)],
            [0, 1],
        )

    def test_repeated_settlement_keeps_latest_date_and_old_snapshot(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2025,
            number="7",
            workplace="Most",
        )
        finding = self._finding(
            audit.id,
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 2, 2),
        )
        first = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 4, 1),
        )
        finding_service.update(finding.id, status=FINDING_STATUS_V_PROCESU)
        later = date(2026, 8, 20)

        class _Later:
            @staticmethod
            def today() -> date:
                return later

        with patch("core.shared.sluzby.finding_service.date", _Later):
            finding_service.update(finding.id, status=FINDING_STATUS_VYPORADANO)
        second = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 8, 21),
        )
        old_item = self._items_by_finding(first.id)[finding.id]
        new_item = self._items_by_finding(second.id)[finding.id]
        self.assertEqual(old_item.resolved_at, date(2026, 2, 2))
        self.assertEqual(old_item.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(new_item.resolved_at, later)
        self.assertTrue(new_item.resettled)
        self.assertFalse(new_item.settled_since_previous)
        self.assertFalse(new_item.reopened)
        history = finding_service.status_history(finding.id)
        self.assertTrue(
            any(
                event.old_status == FINDING_STATUS_VYPORADANO
                and event.new_status == FINDING_STATUS_V_PROCESU
                for event in history
            )
        )

        same_day = self._finding(
            audit.id,
            description="Stejný den",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 5, 5),
        )
        marker = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 8, 22),
        )
        finding_service.update(same_day.id, status=FINDING_STATUS_OTEVRENE)

        class _SameDay:
            @staticmethod
            def today() -> date:
                return date(2026, 5, 5)

        with patch("core.shared.sluzby.finding_service.date", _SameDay):
            finding_service.update(same_day.id, status=FINDING_STATUS_VYPORADANO)
        again = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 8, 23),
        )
        repeated = self._items_by_finding(again.id)[same_day.id]
        self.assertEqual(repeated.resolved_at, date(2026, 5, 5))
        self.assertEqual(
            self._items_by_finding(marker.id)[same_day.id].resolved_at,
            date(2026, 5, 5),
        )
        self.assertTrue(repeated.resettled)
        self.assertFalse(repeated.settled_since_previous)

    def test_task_snapshot_does_not_follow_later_task_changes(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2026,
            number="8",
            workplace="Jeřáb",
        )
        finding = self._finding(audit.id, recommended_action="Doplnit zábradlí")
        task = finding_task_service.create_task_from_finding(finding.id)
        first = self.service.create_overview(SETTLEMENT_SOURCE_AUDITY)
        task_service.update_task(
            task.id,
            title="Nový název úkolu",
            description=task.description,
            priority=task.priority,
            due_date=task.due_date,
            remind_from=task.remind_from,
            responsible_person_id=task.responsible_person_id,
            workplace_id=task.workplace_id,
            completed=True,
            completed_date=date.today(),
            requires_verification=True,
            check_due_date=None,
            checked_date=None,
            checked_by_id=None,
            canceled=False,
            note="",
        )
        frozen = self._items_by_finding(first.id)[finding.id]
        self.assertEqual(frozen.task_id, task.id)
        self.assertEqual(frozen.task_title, "Doplnit zábradlí")
        self.assertEqual(frozen.task_status, "Aktivní")
        reloaded = finding_service.get_by_id(finding.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, FINDING_STATUS_V_PROCESU)
        second = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date.today() + timedelta(days=1),
        )
        changed = self._items_by_finding(second.id)[finding.id]
        self.assertEqual(changed.task_title, "Nový název úkolu")
        self.assertEqual(changed.task_status, "Splněno - čeká na kontrolu")
        self.assertEqual(self._items_by_finding(first.id)[finding.id].task_status, "Aktivní")

    def test_failed_create_rolls_back_the_whole_overview(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2026,
            number="9",
            workplace="Váha",
        )
        self._finding(audit.id)
        with patch.object(self.service, "_build_item", side_effect=RuntimeError("stop")):
            with self.assertRaises(RuntimeError):
                self.service.create_overview(SETTLEMENT_SOURCE_AUDITY)
        self.assertEqual(self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY), [])
        created = self.service.create_overview(SETTLEMENT_SOURCE_AUDITY)
        self.assertEqual(created.sequence_number, 0)
        self.assertEqual(created.total_count, 1)

    def test_sequence_is_unique_per_source_and_series_are_independent(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2026,
            number="1",
            workplace="Auditovna",
        )
        audit_finding = self._finding(audit.id, description="Jen audit")
        session = get_session()
        inspection = BozpInspection(
            number="P-1",
            year=2023,
            status=INSPECTION_STATUS_DOKONCENO,
            workplace_name="Prověrkovna",
            title="Prověrka",
        )
        running = BozpInspection(
            number="P-2",
            year=2026,
            status=INSPECTION_STATUS_PROBIHA,
            workplace_name="Jiná",
            title="Nedokončená",
        )
        session.add(inspection)
        session.add(running)
        session.commit()
        inspection_id = int(inspection.id)
        running_id = int(running.id)
        session.close()
        inspection_finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection_id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Z prověrky",
            status=FINDING_STATUS_OTEVRENE,
        )
        finding_service.create(
            ENTITY_PROVERKY,
            running_id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Z nedokončené prověrky",
            status=FINDING_STATUS_OTEVRENE,
        )

        audit_baseline = self.service.create_overview(SETTLEMENT_SOURCE_AUDITY)
        inspection_baseline = self.service.create_overview(SETTLEMENT_SOURCE_PROVERKY)
        audit_next = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date.today() + timedelta(days=1),
        )

        self.assertEqual(audit_baseline.sequence_number, 0)
        self.assertEqual(inspection_baseline.sequence_number, 0)
        self.assertEqual(audit_next.sequence_number, 1)
        self.assertEqual(
            [row.sequence_number for row in self.service.list_overviews(SETTLEMENT_SOURCE_PROVERKY)],
            [0],
        )
        audit_ids = {item.finding_id for item in self.service.items_for(audit_baseline.id)}
        inspection_ids = {
            item.finding_id for item in self.service.items_for(inspection_baseline.id)
        }
        self.assertEqual(audit_ids, {audit_finding.id})
        self.assertEqual(inspection_ids, {inspection_finding.id})
        inspection_item = self.service.items_for(inspection_baseline.id)[0]
        self.assertEqual(inspection_item.audit_id, inspection_id)
        self.assertEqual(inspection_item.audit_number, "P-1")
        self.assertEqual(inspection_item.audit_year, 2023)
        self.assertEqual(inspection_item.workplace_name, "Prověrkovna")

        with self.assertRaises(IntegrityError):
            with session_module.engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO finding_settlement_overviews ("
                        "source_type, sequence_number, created_at, presented_at, "
                        "period_to, note, total_count, settled_count, in_process_count, "
                        "open_count, type_counts_json"
                        ") VALUES ("
                        "'audity', 0, '2026-01-01 00:00:00', '2026-01-01', "
                        "'2026-01-01', '', 0, 0, 0, 0, '{}'"
                        ")"
                    )
                )

    def test_migration_is_repeatable_and_does_not_rewrite_snapshots(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2018,
            number="2",
            workplace="Archiv",
        )
        finding = self._finding(audit.id, description="Původní text")
        overview = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 1, 10),
            note="Zachovat",
        )
        before_items = [
            (
                item.finding_id,
                item.description,
                item.status,
                item.workplace_name,
            )
            for item in self.service.items_for(overview.id)
        ]
        initialize_database()
        _ensure_finding_settlement_overview_tables()
        _ensure_finding_settlement_overview_tables()
        loaded = self.service.get_overview(overview.id)
        assert loaded is not None
        self.assertEqual(loaded.note, "Zachovat")
        self.assertEqual(loaded.sequence_number, 0)
        self.assertEqual(
            [
                (
                    item.finding_id,
                    item.description,
                    item.status,
                    item.workplace_name,
                )
                for item in self.service.items_for(overview.id)
            ],
            before_items,
        )
        finding_service.update(finding.id, description="Nový text", status=FINDING_STATUS_V_PROCESU)
        self.assertEqual(
            self.service.items_for(overview.id)[0].description,
            "Původní text",
        )

        with session_module.engine.begin() as connection:
            connection.execute(text("DROP TABLE finding_settlement_overview_items"))
            connection.execute(text("DROP TABLE finding_settlement_overviews"))
        _ensure_finding_settlement_overview_tables()
        _ensure_finding_settlement_overview_tables()
        self.assertEqual(self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY), [])
        kept = finding_service.get_by_id(finding.id)
        assert kept is not None
        self.assertEqual(kept.description, "Nový text")
        self.assertEqual(kept.status, FINDING_STATUS_V_PROCESU)
