"""Fáze 97o – Index procesu: skóre úkolů."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
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
        PROCESS_INDEX_AREA_UKOLY,
        PROCESS_INDEX_PLACEHOLDER,
        PROCESS_INDEX_TASK_ACTIVE_OVERDUE_CODE,
        PROCESS_INDEX_TASK_SCORE_POINTS,
        TASK_STATUS_ACTIVE,
        TASK_STATUS_CANCELED,
        TASK_STATUS_DONE,
        TASK_STATUS_WAITING_CHECK,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


class LegalRequirementProcessIndexPhase97oTestCase(unittest.TestCase):
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

    def _tasks_area(self):
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            self._requirement.id,
        )
        by_id = {item.area_id: item for item in breakdown.areas}
        return breakdown, by_id[PROCESS_INDEX_AREA_UKOLY]

    def test_missing_tasks_keeps_score_none(self) -> None:
        breakdown, ukoly = self._tasks_area()
        self.assertIsNone(ukoly.score)
        self.assertIsNone(ukoly.contribution)
        self.assertIsNone(breakdown.index_value)

    def test_task_score_average_and_contribution(self) -> None:
        # 4× Ukončeno + 1× Aktivní po termínu → 80 %; váha 15 % → 12,0
        for index in range(1, 5):
            self._create_linked_task(
                title=f"Ukončený {index}",
                completed=True,
                completed_date=self._today,
                requires_verification=False,
            )
        self._create_linked_task(
            title="Po termínu",
            due_date=self._today - timedelta(days=2),
        )
        self._create_linked_task(title="Zrušený", canceled=True)
        task_service.create_task(
            title="Cizí úkol",
            due_date=self._today,
            source_module=ENTITY_FINDING,
            source_record_id=999,
        )

        breakdown, ukoly = self._tasks_area()

        self.assertEqual(ukoly.score, 80.0)
        self.assertEqual(ukoly.contribution, 12.0)
        self.assertEqual(breakdown.index_value, 80.0)
        self.assertEqual(breakdown.data_coverage_percent, 15)
        self.assertIsNotNone(ukoly.score_detail)
        self.assertEqual(ukoly.score_detail.total_count, 6)
        self.assertEqual(ukoly.score_detail.countable_count, 5)
        self.assertEqual(
            {
                item.result_code: item.points
                for item in ukoly.score_detail.point_mappings
            },
            PROCESS_INDEX_TASK_SCORE_POINTS,
        )
        by_code = {
            item.result_code: item.count for item in ukoly.score_detail.result_counts
        }
        self.assertEqual(by_code[TASK_STATUS_DONE], 4)
        self.assertEqual(by_code[PROCESS_INDEX_TASK_ACTIVE_OVERDUE_CODE], 1)
        self.assertEqual(by_code[TASK_STATUS_ACTIVE], 0)
        self.assertEqual(by_code[TASK_STATUS_CANCELED], 1)
        self.assertIn("80.0 %", ukoly.score_detail.calculation_summary)

    def test_active_waiting_and_overdue_points(self) -> None:
        self._create_linked_task(title="Aktivní v termínu")
        self._create_linked_task(
            title="Aktivní po termínu",
            due_date=self._today - timedelta(days=1),
        )
        waiting = self._create_linked_task(
            title="Čeká na kontrolu",
            completed=True,
            completed_date=self._today,
            requires_verification=True,
            due_date=self._today - timedelta(days=3),
        )
        self.assertEqual(waiting.computed_status, TASK_STATUS_WAITING_CHECK)

        _, ukoly = self._tasks_area()
        # (50 + 0 + 90) / 3 = 46.666… → interně přesné, zobrazení 46,7
        self.assertAlmostEqual(ukoly.score, 140.0 / 3.0)
        self.assertAlmostEqual(ukoly.contribution, (140.0 / 3.0) * 15.0 / 100.0)
        by_code = {
            item.result_code: item.count for item in ukoly.score_detail.result_counts
        }
        self.assertEqual(by_code[TASK_STATUS_ACTIVE], 1)
        self.assertEqual(by_code[PROCESS_INDEX_TASK_ACTIVE_OVERDUE_CODE], 1)
        self.assertEqual(by_code[TASK_STATUS_WAITING_CHECK], 1)

        task_status = legal_requirement_process_status_service.get_task_status(
            self._requirement.id,
        )
        self.assertEqual(task_status.active_overdue_count, 1)
        # Čekající po termínu je v otevřených po termínu, ne v aktivních po termínu.
        self.assertEqual(task_status.overdue_open_count, 2)

    def test_only_canceled_keeps_score_none(self) -> None:
        self._create_linked_task(title="Zrušený", canceled=True)
        _, ukoly = self._tasks_area()
        self.assertIsNone(ukoly.score)
        self.assertIsNone(ukoly.contribution)
        self.assertEqual(ukoly.score_detail.total_count, 1)
        self.assertEqual(ukoly.score_detail.countable_count, 0)

    def test_widget_shows_formatted_task_score(self) -> None:
        self._create_linked_task(
            title="Ukončený",
            completed=True,
            completed_date=self._today,
            requires_verification=False,
        )
        self._create_linked_task(title="Aktivní")

        widget = LegalRequirementProcessIndexWidget(self._requirement.id)
        self.assertEqual(widget.table.item(3, 0).text(), "Úkoly")
        # (100 + 50) / 2 = 75; přínos 75 × 15 / 100 = 11,25 → 11,2
        self.assertEqual(widget.table.item(3, 2).text(), "75,0")
        self.assertEqual(widget.table.item(3, 3).text(), "11,2")
        self.assertIn("75,0 %", widget.index_label.text())
        self.assertEqual(widget.coverage_label.text(), "Pokrytí dat: 15 %")


if __name__ == "__main__":
    unittest.main()
