"""AGENDA-EVENT-UX-7: odstranění stavu Proběhlo."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import text

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _db_engine,
        _normalize_meeting_status_values,
        initialize_database,
    )

    initialize_database()

    from moduly.rocni_plan.constants import DISPLAY_DONE, DISPLAY_PLANNED, DISPLAY_VIA_MEETING
    from moduly.rocni_plan.sluzby.yearly_plan_service import (
        resolve_display_status,
        yearly_plan_service,
    )
    from moduly.schuzky.constants import (
        LEGACY_STATUS_HELD,
        MEETING_STATUSES,
        STATUS_CANCELLED,
        STATUS_CLOSED,
        STATUS_PLANNED,
    )
    from moduly.schuzky.sluzby.meeting_item_task_service import meeting_item_task_service
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.ukoly.sluzby.task_service import task_service


class AgendaEventUx7TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_offers_only_three_statuses(self) -> None:
        dialog = MeetingDialog()
        statuses = [
            dialog.status_combo.itemText(i)
            for i in range(dialog.status_combo.count())
        ]
        self.assertEqual(statuses, list(MEETING_STATUSES))
        self.assertEqual(
            statuses,
            [STATUS_PLANNED, STATUS_CLOSED, STATUS_CANCELLED],
        )
        self.assertNotIn(LEGACY_STATUS_HELD, statuses)
        self.assertNotIn("Proběhlo", statuses)

    def test_planned_to_closed_and_cancelled(self) -> None:
        start = datetime.now() + timedelta(days=3)
        meeting = meeting_service.create_meeting(
            title="Lifecycle",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        meeting_service.update_meeting(
            meeting.id,
            title="Lifecycle",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_CLOSED,
        )
        self.assertEqual(meeting_service.get_by_id(meeting.id).status, STATUS_CLOSED)

        meeting_service.update_meeting(
            meeting.id,
            title="Lifecycle",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        meeting_service.update_meeting(
            meeting.id,
            title="Lifecycle",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_CANCELLED,
        )
        self.assertEqual(meeting_service.get_by_id(meeting.id).status, STATUS_CANCELLED)

    def test_close_with_open_tasks_keeps_tasks_open(self) -> None:
        start = datetime.now() + timedelta(days=4)
        meeting = meeting_service.create_meeting(
            title="S úkoly",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_PLANNED,
        )
        from moduly.schuzky.sluzby.meeting_agenda_item_service import (
            meeting_agenda_item_service,
        )

        items = meeting_agenda_item_service.save_items(
            meeting.id,
            [{"title": "Bod", "zaver": ""}],
        )
        task = meeting_item_task_service.create_for_item(
            meeting_id=meeting.id,
            item_id=items[0].id,
            title="Otevřený úkol z události",
        )
        self.assertFalse(task.completed)

        meeting_service.update_meeting(
            meeting.id,
            title="S úkoly",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            status=STATUS_CLOSED,
        )
        reloaded_meeting = meeting_service.get_by_id(meeting.id)
        reloaded_task = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded_meeting.status, STATUS_CLOSED)
        self.assertIsNotNone(reloaded_task)
        self.assertFalse(reloaded_task.completed)
        self.assertNotEqual(reloaded_task.computed_status, "Ukončeno")

    def test_yearly_plan_closed_is_done_cancelled_is_not(self) -> None:
        closed_item = yearly_plan_service.create(
            year=2026, month=5, title="UX7 uzavřená"
        )
        closed_meeting = meeting_service.create_meeting(
            title="Uzavřená vazba",
            starts_at=datetime(2026, 5, 10, 10, 0),
            status=STATUS_CLOSED,
        )
        yearly_plan_service.link_meeting(closed_item.id, closed_meeting.id)
        closed_item = yearly_plan_service.get_by_id(closed_item.id)
        self.assertEqual(
            resolve_display_status(closed_item, today=date(2026, 5, 15)),
            DISPLAY_DONE,
        )

        cancelled_item = yearly_plan_service.create(
            year=2026, month=5, title="UX7 zrušená"
        )
        cancelled_meeting = meeting_service.create_meeting(
            title="Zrušená vazba",
            starts_at=datetime(2026, 5, 11, 10, 0),
            status=STATUS_CANCELLED,
        )
        yearly_plan_service.link_meeting(cancelled_item.id, cancelled_meeting.id)
        cancelled_item = yearly_plan_service.get_by_id(cancelled_item.id)
        self.assertNotEqual(
            resolve_display_status(cancelled_item, today=date(2026, 5, 15)),
            DISPLAY_DONE,
        )
        self.assertEqual(
            resolve_display_status(cancelled_item, today=date(2026, 5, 15)),
            DISPLAY_PLANNED,
        )

        planned_item = yearly_plan_service.create(
            year=2026, month=5, title="UX7 plán"
        )
        planned_meeting = meeting_service.create_meeting(
            title="Plán vazba",
            starts_at=datetime(2026, 5, 12, 10, 0),
            status=STATUS_PLANNED,
        )
        yearly_plan_service.link_meeting(planned_item.id, planned_meeting.id)
        planned_item = yearly_plan_service.get_by_id(planned_item.id)
        self.assertEqual(
            resolve_display_status(planned_item, today=date(2026, 5, 15)),
            DISPLAY_VIA_MEETING,
        )

    def test_legacy_held_normalizes_to_closed(self) -> None:
        self.assertEqual(
            meeting_service.normalize_status(LEGACY_STATUS_HELD),
            STATUS_CLOSED,
        )
        meeting = meeting_service.create_meeting(
            title="Legacy create",
            starts_at=datetime.now() + timedelta(days=1),
            status=LEGACY_STATUS_HELD,
        )
        self.assertEqual(meeting.status, STATUS_CLOSED)

        # Přímý zápis historické hodnoty + migrace.
        engine = _db_engine()
        with engine.connect() as connection:
            connection.execute(
                text("UPDATE meetings SET status = :held WHERE id = :id"),
                {"held": LEGACY_STATUS_HELD, "id": meeting.id},
            )
            connection.commit()
            row = connection.execute(
                text("SELECT status FROM meetings WHERE id = :id"),
                {"id": meeting.id},
            ).fetchone()
            self.assertEqual(row[0], LEGACY_STATUS_HELD)

        _normalize_meeting_status_values()
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT status FROM meetings WHERE id = :id"),
                {"id": meeting.id},
            ).fetchone()
        self.assertEqual(row[0], STATUS_CLOSED)

    def test_no_held_in_public_constants(self) -> None:
        self.assertNotIn(LEGACY_STATUS_HELD, MEETING_STATUSES)
        source = Path("moduly/agenda/constants.py").read_text(encoding="utf-8")
        self.assertNotIn("STATUS_MODE_HELD", source)
        self.assertNotIn("Proběhlé", source)
        schuzky = Path("moduly/schuzky/constants.py").read_text(encoding="utf-8")
        self.assertIn("LEGACY_STATUS_HELD", schuzky)
        self.assertNotRegex(schuzky, r"(?m)^STATUS_HELD\s*=")


if __name__ == "__main__":
    unittest.main()
