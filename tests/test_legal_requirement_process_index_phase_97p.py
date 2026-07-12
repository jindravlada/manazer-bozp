"""Fáze 97p – Index procesu: celkový výpočet."""

from __future__ import annotations

import importlib
import tempfile
import unittest
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
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_NESPLNENO,
        COMPLIANCE_SPLNENO,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_INDEX_AREA_AUDITY,
        PROCESS_INDEX_AREA_PRAVNI_POZADAVKY,
        PROCESS_INDEX_AREA_PROVERKY,
        PROCESS_INDEX_AREA_UKOLY,
        PROCESS_INDEX_PLACEHOLDER,
        ProcessIndexAreaBreakdown,
        LegalRequirementProcessStatusService,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )
    from moduly.ukoly.modely.task import Task


class LegalRequirementProcessIndexPhase97pTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._parent = legal_requirement_service.create_requirement(
            title="Kořenový proces",
            process_code="P-050",
        )

    def test_full_index_is_sum_of_contributions(self) -> None:
        areas = (
            ProcessIndexAreaBreakdown("audity", "Audity", 30, score=80.0, contribution=24.0),
            ProcessIndexAreaBreakdown("proverky", "Prověrky", 30, score=90.0, contribution=27.0),
            ProcessIndexAreaBreakdown(
                "pravni_pozadavky", "Právní požadavky", 25, score=100.0, contribution=25.0
            ),
            ProcessIndexAreaBreakdown("ukoly", "Úkoly", 15, score=70.0, contribution=10.5),
        )
        index, coverage, available, included, excluded, summary = (
            LegalRequirementProcessStatusService._compute_total_process_index(areas)
        )
        self.assertEqual(index, 86.5)
        self.assertEqual(coverage, 100)
        self.assertEqual(available, 100)
        self.assertEqual(
            included,
            (
                PROCESS_INDEX_AREA_AUDITY,
                PROCESS_INDEX_AREA_PROVERKY,
                PROCESS_INDEX_AREA_PRAVNI_POZADAVKY,
                PROCESS_INDEX_AREA_UKOLY,
            ),
        )
        self.assertEqual(excluded, ())
        self.assertIn("86.5 %", summary)

    def test_missing_area_renormalizes_weights(self) -> None:
        areas = (
            ProcessIndexAreaBreakdown("audity", "Audity", 30, score=80.0, contribution=24.0),
            ProcessIndexAreaBreakdown("proverky", "Prověrky", 30, score=None, contribution=None),
            ProcessIndexAreaBreakdown(
                "pravni_pozadavky", "Právní požadavky", 25, score=100.0, contribution=25.0
            ),
            ProcessIndexAreaBreakdown("ukoly", "Úkoly", 15, score=70.0, contribution=10.5),
        )
        index, coverage, available, included, excluded, summary = (
            LegalRequirementProcessStatusService._compute_total_process_index(areas)
        )
        self.assertEqual(index, 85.0)
        self.assertEqual(coverage, 70)
        self.assertEqual(available, 70)
        self.assertEqual(
            included,
            (
                PROCESS_INDEX_AREA_AUDITY,
                PROCESS_INDEX_AREA_PRAVNI_POZADAVKY,
                PROCESS_INDEX_AREA_UKOLY,
            ),
        )
        self.assertEqual(excluded, (PROCESS_INDEX_AREA_PROVERKY,))
        self.assertIn("Prověrky", summary)
        self.assertIn("pokrytí 70 %", summary)

    def test_no_scores_returns_none(self) -> None:
        areas = (
            ProcessIndexAreaBreakdown("audity", "Audity", 30),
            ProcessIndexAreaBreakdown("proverky", "Prověrky", 30),
            ProcessIndexAreaBreakdown("pravni_pozadavky", "Právní požadavky", 25),
            ProcessIndexAreaBreakdown("ukoly", "Úkoly", 15),
        )
        index, coverage, available, included, excluded, summary = (
            LegalRequirementProcessStatusService._compute_total_process_index(areas)
        )
        self.assertIsNone(index)
        self.assertEqual(coverage, 0)
        self.assertEqual(available, 0)
        self.assertEqual(included, ())
        self.assertEqual(len(excluded), 4)
        self.assertIn("nelze spočítat", summary)

    def test_breakdown_uses_available_areas_and_keeps_original_contributions(self) -> None:
        # 4× Splněno + 1× Nesplněno → skóre PP 80, přínos 20; ostatní bez dat
        for index in range(1, 5):
            legal_requirement_service.create_requirement(
                title=f"Splněný {index}",
                process_code=f"P-050.{index}",
                parent_requirement_id=self._parent.id,
                compliance_status=COMPLIANCE_SPLNENO,
            )
        legal_requirement_service.create_requirement(
            title="Nesplněný",
            process_code="P-050.5",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_NESPLNENO,
        )

        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            self._parent.id,
        )
        by_id = {item.area_id: item for item in breakdown.areas}
        legal = by_id[PROCESS_INDEX_AREA_PRAVNI_POZADAVKY]
        self.assertEqual(legal.score, 80.0)
        self.assertEqual(legal.contribution, 20.0)
        self.assertEqual(legal.weight_percent, 25)

        # Index = 80 (jen PP, váha 25 z 25) = 80; pokrytí 25 %
        self.assertEqual(breakdown.index_value, 80.0)
        self.assertEqual(breakdown.data_coverage_percent, 25)
        self.assertEqual(breakdown.available_weight_percent, 25)
        self.assertEqual(breakdown.included_area_ids, (PROCESS_INDEX_AREA_PRAVNI_POZADAVKY,))
        self.assertIn(PROCESS_INDEX_AREA_PROVERKY, breakdown.excluded_area_ids)
        self.assertIn("80.0 %", breakdown.index_calculation_summary)

    def test_widget_shows_index_and_coverage(self) -> None:
        legal_requirement_service.create_requirement(
            title="Splněný",
            process_code="P-050.1",
            parent_requirement_id=self._parent.id,
            compliance_status=COMPLIANCE_SPLNENO,
        )

        widget = LegalRequirementProcessIndexWidget(self._parent.id)
        self.assertIn("100,0 %", widget.index_label.text())
        self.assertEqual(widget.coverage_label.text(), "Pokrytí dat: 25 %")
        self.assertEqual(widget.total_weight_label.text(), "Součet vah: 100 %")

    def test_widget_shows_placeholder_without_data(self) -> None:
        widget = LegalRequirementProcessIndexWidget(self._parent.id)
        self.assertIn(PROCESS_INDEX_PLACEHOLDER, widget.index_label.text())
        self.assertEqual(widget.coverage_label.text(), "Pokrytí dat: 0 %")


if __name__ == "__main__":
    unittest.main()
