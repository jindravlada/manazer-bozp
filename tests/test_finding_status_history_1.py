"""AUDIT-VYPOŘÁDÁNÍ-2: historie stavů zjištění a datum vypořádání."""

from __future__ import annotations

import importlib
import os
import sqlite3
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

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
        _ensure_finding_status_events_table,
        initialize_database,
    )

    initialize_database()

    from core.database.session import engine, get_session
    from core.services.storage_service import storage_service
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_ORIGIN_MANUAL,
        FINDING_STATUS_ORIGIN_TASK,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_status_history import finding_status_history_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )
    from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
        state_supervision_finding_service,
    )
    from moduly.statni_dozor.sluzby.state_supervision_service import (
        state_supervision_service,
    )
    from moduly.ukoly.sluzby.task_service import task_service


def _wipe() -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM finding_status_events"))
        connection.execute(text("DELETE FROM findings"))


def _finding_rows() -> list[tuple]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text(
                    "SELECT id, entity_type, entity_id, status, resolved_at, description "
                    "FROM findings ORDER BY id"
                )
            )
        )


class FindingStatusHistoryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()

    def _create(self, **fields):
        payload = {
            "finding_type": FINDING_TYPE_NESHODA,
            "description": "Zjištění",
            "status": FINDING_STATUS_OTEVRENE,
        }
        payload.update(fields)
        return finding_service.create(ENTITY_AUDITY, 1, **payload)

    def test_status_transitions_dates_and_history_order(self) -> None:
        finding = self._create(resolved_at=date(2020, 1, 1))
        self.assertEqual(finding.resolved_at, date(2020, 1, 1))
        self.assertEqual(finding_service.status_history(finding.id), [])

        in_process = finding_service.update(
            finding.id,
            status=FINDING_STATUS_V_PROCESU,
            description="Beze změny data",
        )
        assert in_process is not None
        self.assertEqual(in_process.status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(in_process.resolved_at, date(2020, 1, 1))

        settled = finding_service.update(finding.id, status=FINDING_STATUS_VYPORADANO)
        assert settled is not None
        first_settlement = settled.resolved_at
        self.assertEqual(first_settlement, date.today())

        untouched = finding_service.update(
            finding.id,
            description="Jen text",
            resolution_note="Poznámka",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(1999, 1, 1),
        )
        assert untouched is not None
        self.assertEqual(untouched.resolved_at, first_settlement)
        self.assertEqual(untouched.description, "Jen text")

        reopened = finding_service.update(finding.id, status=FINDING_STATUS_OTEVRENE)
        assert reopened is not None
        self.assertIsNone(reopened.resolved_at)

        again_process = finding_service.update(
            finding.id,
            status=FINDING_STATUS_V_PROCESU,
        )
        assert again_process is not None
        self.assertIsNone(again_process.resolved_at)

        finding_service.update(again_process.id, status=FINDING_STATUS_VYPORADANO)
        later = date(2031, 6, 15)

        class _Later:
            @staticmethod
            def today() -> date:
                return later

        with patch("core.shared.sluzby.finding_service.date", _Later):
            finding_service.update(finding.id, status=FINDING_STATUS_V_PROCESU)
            repeated = finding_service.update(
                finding.id,
                status=FINDING_STATUS_VYPORADANO,
            )
        assert repeated is not None
        self.assertEqual(repeated.resolved_at, later)

        history = finding_service.status_history(finding.id)
        pairs = [(row.old_status, row.new_status) for row in history]
        self.assertEqual(
            pairs,
            [
                (FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU),
                (FINDING_STATUS_V_PROCESU, FINDING_STATUS_VYPORADANO),
                (FINDING_STATUS_VYPORADANO, FINDING_STATUS_OTEVRENE),
                (FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU),
                (FINDING_STATUS_V_PROCESU, FINDING_STATUS_VYPORADANO),
                (FINDING_STATUS_VYPORADANO, FINDING_STATUS_V_PROCESU),
                (FINDING_STATUS_V_PROCESU, FINDING_STATUS_VYPORADANO),
            ],
        )
        self.assertEqual([row.origin for row in history], [FINDING_STATUS_ORIGIN_MANUAL] * 7)
        self.assertEqual(history[0].resolved_at_before, date(2020, 1, 1))
        self.assertEqual(history[0].resolved_at_after, date(2020, 1, 1))
        self.assertEqual(history[1].resolved_at_before, date(2020, 1, 1))
        self.assertEqual(history[1].resolved_at_after, first_settlement)
        self.assertEqual(history[2].resolved_at_before, first_settlement)
        self.assertIsNone(history[2].resolved_at_after)
        self.assertEqual(history[-1].resolved_at_after, later)
        self.assertEqual(history[1].resolved_at_after, first_settlement)
        changed = [row.changed_at for row in history]
        self.assertEqual(changed, sorted(changed))
        self.assertEqual([row.id for row in history], sorted(row.id for row in history))
        self.assertEqual(len({row.id for row in history}), len(history))

        stored_first = history[1].id
        finding_service.update(finding.id, description="Stále stejný stav")
        kept = finding_service.status_history(finding.id)
        self.assertEqual(len(kept), len(history))
        self.assertEqual(kept[1].id, stored_first)
        self.assertEqual(kept[1].resolved_at_after, first_settlement)
        self.assertEqual(kept[1].new_status, FINDING_STATUS_VYPORADANO)

    def test_direct_reopen_to_in_process_clears_date(self) -> None:
        finding = self._create()
        finding_service.update(finding.id, status=FINDING_STATUS_VYPORADANO)
        reopened = finding_service.update(finding.id, status=FINDING_STATUS_V_PROCESU)
        assert reopened is not None
        self.assertEqual(reopened.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(reopened.resolved_at)
        history = finding_service.status_history(finding.id)
        self.assertEqual(history[-1].old_status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(history[-1].resolved_at_before, date.today())
        self.assertIsNone(history[-1].resolved_at_after)

    def test_task_link_verification_and_reopen(self) -> None:
        finding = self._create()
        task = finding_task_service.create_task_from_finding(finding.id)
        linked = finding_service.get_by_id(finding.id)
        assert linked is not None
        self.assertEqual(linked.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(linked.resolved_at)
        self.assertEqual(linked.task_id, task.id)

        self.assertTrue(task_service.mark_completed(task.id))
        after_complete = finding_service.get_by_id(finding.id)
        assert after_complete is not None
        self.assertEqual(after_complete.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(after_complete.resolved_at)
        self.assertEqual(len(finding_service.status_history(finding.id)), 1)

        completed = task_service.get_task_by_id(task.id)
        assert completed is not None
        task_service.update_task(
            completed.id,
            title=completed.title,
            description=completed.description,
            priority=completed.priority,
            due_date=completed.due_date,
            remind_from=completed.remind_from,
            responsible_person_id=completed.responsible_person_id,
            workplace_id=completed.workplace_id,
            completed=True,
            completed_date=completed.completed_date,
            requires_verification=True,
            check_due_date=completed.check_due_date,
            checked_date=date.today(),
            checked_by_id=completed.checked_by_id,
            canceled=False,
            note=completed.note,
        )
        verified = finding_service.get_by_id(finding.id)
        assert verified is not None
        self.assertEqual(verified.status, FINDING_STATUS_VYPORADANO)
        self.assertEqual(verified.resolved_at, date.today())

        self.assertTrue(task_service.reopen_task(task.id))
        reopened = finding_service.get_by_id(finding.id)
        assert reopened is not None
        self.assertEqual(reopened.status, FINDING_STATUS_V_PROCESU)
        self.assertIsNone(reopened.resolved_at)

        later = date(2032, 3, 4)

        class _Later:
            @staticmethod
            def today() -> date:
                return later

        with patch("core.shared.sluzby.finding_service.date", _Later):
            task_service.update_task(
                task.id,
                title=completed.title,
                description=completed.description,
                priority=completed.priority,
                due_date=completed.due_date,
                remind_from=completed.remind_from,
                responsible_person_id=completed.responsible_person_id,
                workplace_id=completed.workplace_id,
                completed=True,
                completed_date=date.today(),
                requires_verification=True,
                check_due_date=None,
                checked_date=later,
                checked_by_id=None,
                canceled=False,
                note="",
            )
        settled_again = finding_service.get_by_id(finding.id)
        assert settled_again is not None
        self.assertEqual(settled_again.resolved_at, later)

        history = finding_service.status_history(finding.id)
        self.assertEqual(
            [(row.old_status, row.new_status, row.origin) for row in history],
            [
                (FINDING_STATUS_OTEVRENE, FINDING_STATUS_V_PROCESU, FINDING_STATUS_ORIGIN_TASK),
                (FINDING_STATUS_V_PROCESU, FINDING_STATUS_VYPORADANO, FINDING_STATUS_ORIGIN_TASK),
                (FINDING_STATUS_VYPORADANO, FINDING_STATUS_V_PROCESU, FINDING_STATUS_ORIGIN_TASK),
                (FINDING_STATUS_V_PROCESU, FINDING_STATUS_VYPORADANO, FINDING_STATUS_ORIGIN_TASK),
            ],
        )
        self.assertEqual(history[1].resolved_at_after, date.today())
        self.assertEqual(history[2].resolved_at_before, date.today())
        self.assertEqual(history[3].resolved_at_after, later)
        self.assertLess(history[1].id, history[2].id)
        self.assertLess(history[2].id, history[3].id)

        self.assertTrue(task_service.reopen_task(task.id))
        unlinked = finding_service.update(finding.id, task_id=None)
        assert unlinked is not None
        self.assertEqual(unlinked.status, FINDING_STATUS_OTEVRENE)
        self.assertIsNone(unlinked.resolved_at)
        full_history = finding_service.status_history(finding.id)
        self.assertEqual(full_history[3].resolved_at_after, later)
        unlink_event = full_history[-1]
        self.assertEqual(unlink_event.origin, FINDING_STATUS_ORIGIN_TASK)
        self.assertEqual(unlink_event.old_status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(unlink_event.new_status, FINDING_STATUS_OTEVRENE)
        self.assertIsNone(unlink_event.resolved_at_before)
        self.assertIsNone(unlink_event.resolved_at_after)

    def test_proverky_use_the_same_history(self) -> None:
        finding = finding_service.create(
            ENTITY_PROVERKY,
            1,
            finding_type=FINDING_TYPE_NESHODA,
            description="Prověrka",
            status=FINDING_STATUS_OTEVRENE,
        )
        updated = finding_service.update(finding.id, status=FINDING_STATUS_VYPORADANO)
        assert updated is not None
        self.assertEqual(updated.resolved_at, date.today())
        history = finding_service.status_history(finding.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].origin, FINDING_STATUS_ORIGIN_MANUAL)
        self.assertEqual(history[0].new_status, FINDING_STATUS_VYPORADANO)

    def test_rollback_keeps_status_date_and_history_together(self) -> None:
        finding = self._create()
        with patch.object(
            finding_status_history_service,
            "record",
            side_effect=RuntimeError("historie selhala"),
        ):
            with self.assertRaises(RuntimeError):
                finding_service.update(finding.id, status=FINDING_STATUS_VYPORADANO)

        reloaded = finding_service.get_by_id(finding.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, FINDING_STATUS_OTEVRENE)
        self.assertIsNone(reloaded.resolved_at)
        self.assertEqual(finding_service.status_history(finding.id), [])

        session = get_session()
        try:
            finding_service.update(
                finding.id,
                session=session,
                status=FINDING_STATUS_VYPORADANO,
            )
            session.rollback()
        finally:
            session.close()

        after = finding_service.get_by_id(finding.id)
        assert after is not None
        self.assertEqual(after.status, FINDING_STATUS_OTEVRENE)
        self.assertEqual(finding_service.status_history(finding.id), [])

    def test_state_supervision_records_manual_history_and_keeps_dialog_date(self) -> None:
        parent = state_supervision_service.create_supervision(authority_name="OIP historie")
        created = state_supervision_finding_service.save_state_supervision_findings_batch(
            parent.id,
            [
                StateSupervisionFindingDraft(
                    finding_type=FINDING_TYPE_ZAVADA,
                    description="Původní",
                    status=FINDING_STATUS_OTEVRENE,
                    resolved_at=date(2024, 5, 5),
                )
            ],
        )
        self.assertEqual(created[0].resolved_at, date(2024, 5, 5))
        self.assertEqual(finding_service.status_history(created[0].id), [])

        state_supervision_finding_service.save_state_supervision_findings_batch(
            parent.id,
            [
                StateSupervisionFindingDraft(
                    id=created[0].id,
                    finding_type=FINDING_TYPE_ZAVADA,
                    description="Jen text",
                    status=FINDING_STATUS_OTEVRENE,
                    resolved_at=date(2024, 5, 5),
                )
            ],
        )
        self.assertEqual(finding_service.status_history(created[0].id), [])

        changed = state_supervision_finding_service.save_state_supervision_findings_batch(
            parent.id,
            [
                StateSupervisionFindingDraft(
                    id=created[0].id,
                    finding_type=FINDING_TYPE_ZAVADA,
                    description="Jen text",
                    status=FINDING_STATUS_V_PROCESU,
                    resolved_at=date(2024, 5, 5),
                )
            ],
        )
        self.assertEqual(changed[0].status, FINDING_STATUS_V_PROCESU)
        self.assertEqual(changed[0].resolved_at, date(2024, 5, 5))
        history = finding_service.status_history(created[0].id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].origin, FINDING_STATUS_ORIGIN_MANUAL)
        self.assertEqual(history[0].resolved_at_before, date(2024, 5, 5))
        self.assertEqual(history[0].resolved_at_after, date(2024, 5, 5))

    def test_migration_is_repeatable_and_preserves_historical_rows(self) -> None:
        legacy_open = self._create(description="otevřené s datem", resolved_at=date(2019, 2, 2))
        legacy_closed = self._create(
            description="vypořádané bez data",
            status=FINDING_STATUS_VYPORADANO,
        )
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE findings SET resolved_at = NULL WHERE id = :finding_id"),
                {"finding_id": legacy_closed.id},
            )
        self.assertEqual(finding_service.count_resolution_inconsistencies(), 2)
        self.assertEqual(finding_service.status_history(legacy_open.id), [])
        self.assertEqual(finding_service.status_history(legacy_closed.id), [])

        moved = finding_service.update(legacy_open.id, status=FINDING_STATUS_V_PROCESU)
        assert moved is not None
        before_rows = _finding_rows()
        before_history = finding_service.status_history(legacy_open.id)
        self.assertEqual(len(before_history), 1)

        initialize_database()
        _ensure_finding_status_events_table()
        self.assertEqual(_finding_rows(), before_rows)
        kept = finding_service.status_history(legacy_open.id)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].id, before_history[0].id)
        self.assertEqual(kept[0].resolved_at_before, date(2019, 2, 2))
        closed = finding_service.get_by_id(legacy_closed.id)
        assert closed is not None
        self.assertEqual(closed.status, FINDING_STATUS_VYPORADANO)
        self.assertIsNone(closed.resolved_at)
        self.assertEqual(finding_service.status_history(legacy_closed.id), [])
        self.assertEqual(finding_service.count_resolution_inconsistencies(), 2)

        with engine.begin() as connection:
            connection.execute(text("DROP TABLE finding_status_events"))
        _ensure_finding_status_events_table()
        _ensure_finding_status_events_table()
        initialize_database()

        self.assertEqual(_finding_rows(), before_rows)
        self.assertEqual(finding_service.status_history(legacy_open.id), [])
        self.assertEqual(finding_service.count_resolution_inconsistencies(), 2)
        with engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(finding_status_events)"))
            }
        self.assertIn("resolved_at_before", columns)
        self.assertIn("resolved_at_after", columns)
        self.assertTrue(storage_service.database_path.exists())
        connection = sqlite3.connect(storage_service.database_path)
        try:
            row = connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'finding_status_events'"
            ).fetchone()
        finally:
            connection.close()
        self.assertIsNotNone(row)
