"""Fáze 97i – Stav procesu: úkoly."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.constants import ENTITY_FINDING, ENTITY_LEGAL_REQUIREMENT
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_STATUS_NO_TASKS,
        TASK_STATUS_ACTIVE,
        TASK_STATUS_CANCELED,
        TASK_STATUS_DONE,
        TASK_STATUS_WAITING_CHECK,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_status_widget import (
        LegalRequirementProcessStatusWidget,
    )
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


class LegalRequirementProcessStatusPhase97iTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._requirement = legal_requirement_service.create_requirement(
            title="Řídicí proces",
            process_code="P-030",
        )
        self._other = legal_requirement_service.create_requirement(
            title="Jiný proces",
            process_code="P-031",
        )
        self._today = date.today()

    def _create_linked_task(self, **fields):
        payload = {
            "title": "Úkol procesu",
            "description": "Popis",
            "due_date": self._today + timedelta(days=7),
            "completed": False,
            "canceled": False,
            "source_module": ENTITY_LEGAL_REQUIREMENT,
            "source_record_id": self._requirement.id,
        }
        payload.update(fields)
        return task_service.create_task(**payload)

    def test_no_tasks_shows_empty_message(self) -> None:
        status = legal_requirement_process_status_service.get_task_status(self._requirement.id)
        self.assertEqual(status.task_count, 0)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NO_TASKS)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Úkoly", labels)
        self.assertIn(PROCESS_STATUS_NO_TASKS, labels)

    def test_summarizes_direct_tasks_by_computed_status(self) -> None:
        self._create_linked_task(title="Aktivní úkol")
        waiting = self._create_linked_task(
            title="Čeká na kontrolu",
            completed=True,
            completed_date=self._today,
            requires_verification=True,
        )
        self.assertEqual(waiting.computed_status, TASK_STATUS_WAITING_CHECK)
        self._create_linked_task(
            title="Ukončený",
            completed=True,
            completed_date=self._today,
            requires_verification=False,
        )
        self._create_linked_task(title="Zrušený", canceled=True)

        status = legal_requirement_process_status_service.get_task_status(self._requirement.id)

        self.assertIsNone(status.empty_message)
        self.assertEqual(status.task_count, 4)
        self.assertEqual(status.open_count, 2)
        by_label = {item.result_label: item.count for item in status.status_counts}
        self.assertEqual(by_label[TASK_STATUS_ACTIVE], 1)
        self.assertEqual(by_label[TASK_STATUS_WAITING_CHECK], 1)
        self.assertEqual(by_label[TASK_STATUS_DONE], 1)
        self.assertEqual(by_label[TASK_STATUS_CANCELED], 1)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Celkem: 4", labels)
        self.assertIn("Otevřené: 2", labels)
        self.assertIn(f"• {TASK_STATUS_ACTIVE}: 1", labels)

    def test_overdue_and_nearest_due_among_open_tasks(self) -> None:
        self._create_linked_task(
            title="Po termínu",
            due_date=self._today - timedelta(days=2),
        )
        self._create_linked_task(
            title="Blížší termín",
            due_date=self._today + timedelta(days=3),
        )
        self._create_linked_task(
            title="Pozdější termín",
            due_date=self._today + timedelta(days=10),
        )
        self._create_linked_task(
            title="Ukončený po termínu",
            due_date=self._today - timedelta(days=5),
            completed=True,
            completed_date=self._today,
            requires_verification=False,
        )

        status = legal_requirement_process_status_service.get_task_status(self._requirement.id)

        self.assertEqual(status.overdue_open_count, 1)
        self.assertEqual(status.nearest_due_date, self._today - timedelta(days=2))

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Otevřené po termínu: 1", labels)
        expected_due = (self._today - timedelta(days=2)).strftime("%d.%m.%Y")
        self.assertIn(f"Nejbližší termín otevřeného úkolu: {expected_due}", labels)

    def test_ignores_tasks_of_other_processes_and_indirect_sources(self) -> None:
        self._create_linked_task(title="Přímý úkol")
        task_service.create_task(
            title="Úkol jiného procesu",
            due_date=self._today,
            source_module=ENTITY_LEGAL_REQUIREMENT,
            source_record_id=self._other.id,
        )
        task_service.create_task(
            title="Úkol ze zjištění",
            due_date=self._today,
            source_module=ENTITY_FINDING,
            source_record_id=999,
        )

        status = legal_requirement_process_status_service.get_task_status(self._requirement.id)
        self.assertEqual(status.task_count, 1)
        self.assertEqual(status.open_count, 1)

    def test_all_sections_remain_visible(self) -> None:
        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Audity", labels)
        self.assertIn("Prověrky", labels)
        self.assertIn("Právní požadavky", labels)
        self.assertIn("Úkoly", labels)


if __name__ == "__main__":
    unittest.main()
