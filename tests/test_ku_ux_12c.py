"""KU-UX-12c – logika kontrolního úkolu a navigace tabulátorem."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit

_TMP = Path(tempfile.mkdtemp(prefix="ku-ux-12c-"))
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
    from moduly.kniha_urazu.sluzby.accident_service import (
        VERIFY_ACCIDENT_KIND_TASK_TITLE_PREFIX,
        accident_service,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.ukoly.sluzby.task_service import task_service


KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_SERIOUS = "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)"
KIND_FATAL = "smrtelný"


class KuUx12cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

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

    def _create_up_to_3(self, **extra):
        today = date.today()
        data = {
            "jmeno_prijmeni": "Kontrola 12c",
            "accident_date": today,
            "druh_urazu": KIND_UP_TO_3,
            "dpn_od": today,
        }
        data.update(extra)
        return accident_service.create_accident(**data)

    def test_creates_task_only_for_up_to_3_with_pn(self) -> None:
        accident = self._create_up_to_3()
        tasks = self._open_verify_tasks(accident.id)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].due_date, accident.accident_date + timedelta(days=5))

    def test_no_task_without_up_to_3_kind(self) -> None:
        accident = accident_service.create_accident(
            jmeno_prijmeni="Bez druhu",
            accident_date=date.today(),
            dpn_od=date.today(),
        )
        self.assertEqual(self._open_verify_tasks(accident.id), [])

        over = accident_service.create_accident(
            jmeno_prijmeni="Nad 3",
            accident_date=date.today(),
            druh_urazu=KIND_OVER_3,
            dpn_od=date.today(),
        )
        self.assertEqual(self._open_verify_tasks(over.id), [])

    def test_no_task_for_serious_or_fatal(self) -> None:
        serious = accident_service.create_accident(
            jmeno_prijmeni="Závažný",
            accident_date=date.today(),
            druh_urazu=KIND_SERIOUS,
            dpn_od=date.today(),
        )
        fatal = accident_service.create_accident(
            jmeno_prijmeni="Smrtelný",
            accident_date=date.today(),
            druh_urazu=KIND_FATAL,
        )
        self.assertEqual(self._open_verify_tasks(serious.id), [])
        self.assertEqual(self._open_verify_tasks(fatal.id), [])

    def test_no_task_when_delayed_4_days(self) -> None:
        accident = accident_service.create_accident(
            jmeno_prijmeni="Pozdní",
            accident_date=date.today() - timedelta(days=4),
            druh_urazu=KIND_UP_TO_3,
            dpn_od=date.today() - timedelta(days=4),
        )
        self.assertEqual(self._open_verify_tasks(accident.id), [])

    def test_changing_kind_to_over_3_completes_without_dpn_end(self) -> None:
        accident = self._create_up_to_3()
        self.assertEqual(len(self._open_verify_tasks(accident.id)), 1)

        accident_service.update_accident(
            accident.id,
            druh_urazu=KIND_OVER_3,
            dpn_od=accident.accident_date,
            dpn_do=None,
        )
        self.assertEqual(self._open_verify_tasks(accident.id), [])

    def test_changing_to_serious_or_fatal_completes_task(self) -> None:
        accident = self._create_up_to_3(jmeno_prijmeni="Na závažný")
        accident_service.update_accident(accident.id, druh_urazu=KIND_SERIOUS)
        self.assertEqual(self._open_verify_tasks(accident.id), [])

        accident2 = self._create_up_to_3(jmeno_prijmeni="Na smrtelný")
        accident_service.update_accident(accident2.id, druh_urazu=KIND_FATAL)
        self.assertEqual(self._open_verify_tasks(accident2.id), [])

    def test_changing_back_to_up_to_3_does_not_recreate_task(self) -> None:
        accident = self._create_up_to_3()
        accident_service.update_accident(accident.id, druh_urazu=KIND_OVER_3)
        self.assertEqual(self._open_verify_tasks(accident.id), [])

        accident_service.update_accident(
            accident.id,
            druh_urazu=KIND_UP_TO_3,
            dpn_od=accident.accident_date,
        )
        self.assertEqual(self._open_verify_tasks(accident.id), [])

    def test_should_create_helper(self) -> None:
        today = date(2026, 7, 27)
        ok = SimpleNamespace(
            accident_date=today - timedelta(days=2),
            druh_urazu=KIND_UP_TO_3,
            dpn_od=today - timedelta(days=2),
            dpn_do=None,
            podezreni_trestny_cin="",
        )
        self.assertTrue(accident_service.should_create_verify_kind_task(ok, today=today))

        delayed = SimpleNamespace(
            accident_date=today - timedelta(days=4),
            druh_urazu=KIND_UP_TO_3,
            dpn_od=today - timedelta(days=4),
            dpn_do=None,
            podezreni_trestny_cin="",
        )
        self.assertFalse(accident_service.should_create_verify_kind_task(delayed, today=today))

    def test_tab_moves_focus_between_text_edits(self) -> None:
        dialog = AccidentDialog()
        dialog.tabs.setCurrentIndex(4)  # Další údaje

        source = dialog.tab_dalsi_widget.porusene_predpisy
        target = dialog.tab_dalsi_widget.opatreni
        self.assertTrue(source.tabChangesFocus())
        self.assertTrue(target.tabChangesFocus())

        source.setFocus()
        QApplication.processEvents()
        self.assertIs(dialog.focusWidget(), source)

        source.focusNextChild()
        QApplication.processEvents()
        self.assertIs(dialog.focusWidget(), target)

        target.focusPreviousChild()
        QApplication.processEvents()
        self.assertIs(dialog.focusWidget(), source)

        for label in dialog.tab_dalsi_widget.findChildren(QLabel):
            self.assertEqual(label.focusPolicy(), Qt.FocusPolicy.NoFocus)

        for edit in dialog.findChildren(QTextEdit):
            self.assertTrue(edit.tabChangesFocus())


if __name__ == "__main__":
    unittest.main()
