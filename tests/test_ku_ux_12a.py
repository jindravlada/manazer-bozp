"""KU-UX-12a – dotažení systémového úkolu kontroly druhu pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="ku-ux-12a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import ENTITY_ACCIDENT
    from core.shared.task_source_display import task_source_label, task_source_short_label
    from moduly.kniha_urazu.sluzby.accident_service import (
        VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX,
        accident_service,
        verify_accident_kind_task_title,
    )
    from moduly.ukoly.sluzby.task_service import task_service


KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


class KuUx12aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(Accident))
            session.commit()

    def _open_verify_tasks(self, accident_id: int):
        return [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident_id
            and not task.completed
            and not task.canceled
            and task.title.startswith(VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX)
        ]

    def _create_eligible(self, **extra):
        today = date.today()
        data = {
            "jmeno_prijmeni": "Petr Nový",
            "accident_date": today,
            "druh_urazu": KIND_UP_TO_3,
            "dpn_od": today,
        }
        data.update(extra)
        return accident_service.create_accident(**data)

    def test_task_title_includes_accident_number(self) -> None:
        accident = self._create_eligible()
        tasks = self._open_verify_tasks(accident.id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, verify_accident_kind_task_title(accident.number))
        self.assertIn(accident.number, tasks[0].title)

    def test_task_source_label_is_uraz(self) -> None:
        accident = self._create_eligible(jmeno_prijmeni="Zdroj Úraz")
        task = self._open_verify_tasks(accident.id)[0]
        self.assertEqual(task_source_short_label(task), "Úraz")
        self.assertTrue(task_source_label(task).startswith("Úraz"))
        self.assertNotEqual(task_source_short_label(task), "accident")

    def test_no_task_when_recording_delayed_4_or_more_days(self) -> None:
        delayed = self._create_eligible(
            jmeno_prijmeni="Pozdní zápis",
            accident_date=date.today() - timedelta(days=4),
            dpn_od=date.today() - timedelta(days=4),
        )
        self.assertEqual(self._open_verify_tasks(delayed.id), [])

        later = self._create_eligible(
            jmeno_prijmeni="Ještě později",
            accident_date=date.today() - timedelta(days=10),
            dpn_od=date.today() - timedelta(days=10),
        )
        self.assertEqual(self._open_verify_tasks(later.id), [])

    def test_task_created_when_delay_is_at_most_3_days(self) -> None:
        for delay in (0, 1, 2, 3):
            with self.subTest(delay=delay):
                accident = self._create_eligible(
                    jmeno_prijmeni=f"Zápis +{delay}",
                    accident_date=date.today() - timedelta(days=delay),
                    dpn_od=date.today() - timedelta(days=delay),
                )
                self.assertEqual(len(self._open_verify_tasks(accident.id)), 1)

    def test_matching_kind_update_completes_verify_task(self) -> None:
        accident_date = date.today() - timedelta(days=1)
        accident = self._create_eligible(
            jmeno_prijmeni="Kontrola druhu",
            accident_date=accident_date,
            dpn_od=accident_date,
        )
        self.assertEqual(len(self._open_verify_tasks(accident.id)), 1)

        # Změna druhu na >3 dny dokončí úkol bez data ukončení DPN.
        accident_service.update_accident(
            accident.id,
            druh_urazu=KIND_OVER_3,
            dpn_od=accident_date,
            dpn_do=None,
        )
        self.assertEqual(self._open_verify_tasks(accident.id), [])

        completed = [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident.id
            and task.completed
        ]
        self.assertEqual(len(completed), 1)
        self.assertEqual(completed[0].completed_date, date.today())

    def test_should_create_helper_uses_delay_threshold(self) -> None:
        today = date(2026, 7, 27)
        eligible = SimpleNamespace(
            accident_date=today - timedelta(days=3),
            druh_urazu=KIND_UP_TO_3,
            dpn_od=today - timedelta(days=3),
            dpn_do=None,
            podezreni_trestny_cin="",
        )
        self.assertTrue(
            accident_service.should_create_verify_kind_task(eligible, today=today)
        )
        delayed = SimpleNamespace(
            accident_date=today - timedelta(days=4),
            druh_urazu=KIND_UP_TO_3,
            dpn_od=today - timedelta(days=4),
            dpn_do=None,
            podezreni_trestny_cin="",
        )
        self.assertFalse(
            accident_service.should_create_verify_kind_task(delayed, today=today)
        )


if __name__ == "__main__":
    unittest.main()
