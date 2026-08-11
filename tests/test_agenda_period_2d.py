"""AGENDA-PERIOD-2d: upozornění periodických činností na Pracovní ploše."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import SOURCE_LABEL_PERIODIC
    from core.dashboard.attention_service import get_periodic_reminder_items
    from core.dashboard.widget_today import TodayWidget
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.periodicke_cinnosti.constants import (
        NEXT_FROM_PLANNED,
        PLACE_KIND_WORKPLACE,
        TAB_PERIODIC,
        UNIT_MONTHS,
        UNIT_YEARS,
    )
    from moduly.periodicke_cinnosti.sluzby.periodic_activity_service import (
        calculate_notify_date,
        periodic_activity_service,
        subtract_period,
    )


class AgendaPeriod2dTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for activity in list(periodic_activity_service.get_all()):
            periodic_activity_service.update_activity(
                activity.id,
                title=f"OLD-{activity.id}-{activity.title}",
                active=False,
                next_due_date=activity.next_due_date,
                repeat_every=activity.repeat_every,
                repeat_unit=activity.repeat_unit,
                notify_every=activity.notify_every,
                notify_unit=activity.notify_unit,
                next_from=activity.next_from,
                place_kind=activity.place_kind,
            )
        self.workplace = settings_service.save_workplace(name="Provoz Beta")

    def _create(
        self,
        *,
        title: str,
        due: date,
        notify_every: int,
        notify_unit: str = UNIT_MONTHS,
        active: bool = True,
        place: bool = False,
    ):
        return periodic_activity_service.create_activity(
            title=title,
            next_due_date=due,
            repeat_every=1,
            repeat_unit=UNIT_YEARS,
            notify_every=notify_every,
            notify_unit=notify_unit,
            next_from=NEXT_FROM_PLANNED,
            active=active,
            place_kind=PLACE_KIND_WORKPLACE if place else "none",
            workplace_id=self.workplace.id if place else None,
        )

    def _periodic_items(self, today: date):
        return get_periodic_reminder_items(today=today)

    def test_notify_date_calendar_months(self) -> None:
        due = date(2027, 10, 15)
        self.assertEqual(calculate_notify_date(due, 6, UNIT_MONTHS), date(2027, 4, 15))
        self.assertEqual(subtract_period(due, 0, UNIT_MONTHS), due)

    def test_hidden_before_notify_date(self) -> None:
        activity = self._create(
            title="Před upozorněním",
            due=date(2027, 10, 15),
            notify_every=6,
        )
        items = self._periodic_items(date(2027, 4, 14))
        self.assertNotIn(activity.id, {item.source_id for item in items})

    def test_shown_on_notify_date(self) -> None:
        activity = self._create(
            title="Den upozornění",
            due=date(2027, 10, 15),
            notify_every=6,
            place=True,
        )
        items = self._periodic_items(date(2027, 4, 15))
        by_id = {item.source_id: item for item in items}
        self.assertIn(activity.id, by_id)
        item = by_id[activity.id]
        self.assertEqual(item.title, "Den upozornění")
        self.assertEqual(item.date, date(2027, 10, 15))
        self.assertEqual(item.type_label, "Periodická činnost")
        self.assertIn(SOURCE_LABEL_PERIODIC, item.subtitle)
        self.assertIn("Provoz Beta", item.subtitle)

    def test_shown_between_notify_and_due(self) -> None:
        activity = self._create(
            title="Mezi",
            due=date(2027, 10, 15),
            notify_every=6,
        )
        items = self._periodic_items(date(2027, 7, 1))
        self.assertIn(activity.id, {item.source_id for item in items})

    def test_shown_as_overdue_after_due(self) -> None:
        activity = self._create(
            title="Po termínu",
            due=date(2027, 10, 15),
            notify_every=6,
        )
        items = self._periodic_items(date(2027, 10, 16))
        item = next(i for i in items if i.source_id == activity.id)
        self.assertEqual(item.date, date(2027, 10, 15))

        widget = TodayWidget()
        widget.refresh(today=date(2027, 10, 16))
        text = widget.content.text()
        self.assertIn("Po termínu", text)
        self.assertIn("15.10.2027", text)
        self.assertIn("🔴", text)
        widget.close()

    def test_inactive_never_shown(self) -> None:
        activity = self._create(
            title="Neaktivní",
            due=date(2027, 10, 15),
            notify_every=6,
            active=False,
        )
        items = self._periodic_items(date(2027, 10, 16))
        self.assertNotIn(activity.id, {item.source_id for item in items})

    def test_after_perform_old_due_disappears_until_new_notify(self) -> None:
        activity = self._create(
            title="Po provedení",
            due=date(2026, 6, 1),
            notify_every=6,
        )
        today = date(2026, 5, 1)
        self.assertIn(activity.id, {i.source_id for i in self._periodic_items(today)})

        periodic_activity_service.record_performance(
            activity.id,
            performed_at=date(2026, 5, 15),
        )
        reloaded = periodic_activity_service.get_by_id(activity.id)
        self.assertEqual(reloaded.next_due_date, date(2027, 6, 1))
        # nové upozornění od 1. 12. 2026
        self.assertEqual(
            calculate_notify_date(reloaded.next_due_date, 6, UNIT_MONTHS),
            date(2026, 12, 1),
        )
        self.assertNotIn(activity.id, {i.source_id for i in self._periodic_items(today)})
        self.assertNotIn(
            activity.id,
            {i.source_id for i in self._periodic_items(date(2026, 11, 30))},
        )
        self.assertIn(
            activity.id,
            {i.source_id for i in self._periodic_items(date(2026, 12, 1))},
        )

    def test_open_leads_to_periodic_activity(self) -> None:
        activity = self._create(
            title="Otevření z plochy",
            due=date(2026, 8, 1),
            notify_every=0,
        )
        page = AgendaPage()
        opened: list[int] = []

        original = page.periodic_tab.open_activity

        def _track(activity_id: int) -> None:
            opened.append(activity_id)
            activity_obj = periodic_activity_service.get_by_id(activity_id)
            self.assertIsNotNone(activity_obj)
            index = page.tabs.indexOf(page.periodic_tab)
            self.assertEqual(page.tabs.currentIndex(), index)
            self.assertEqual(page.tabs.tabText(index), TAB_PERIODIC)

        with patch.object(page.periodic_tab, "open_activity", side_effect=_track):
            page.open_periodic_activity(activity.id)

        self.assertEqual(opened, [activity.id])
        page.close()


if __name__ == "__main__":
    unittest.main()
