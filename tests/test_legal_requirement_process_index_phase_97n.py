"""Fáze 97n – Index procesu: skóre právních požadavků."""

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
        COMPLIANCE_CASTECNE_SPLNENO,
        COMPLIANCE_NENI_RELEVANTNI,
        COMPLIANCE_NESPLNENO,
        COMPLIANCE_SPLNENO,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_INDEX_AREA_PRAVNI_POZADAVKY,
        PROCESS_INDEX_LEGAL_SCORE_POINTS,
        PROCESS_INDEX_PLACEHOLDER,
        PROCESS_STATUS_UNEVALUATED_LABEL,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )
    from moduly.ukoly.modely.task import Task


class LegalRequirementProcessIndexPhase97nTestCase(unittest.TestCase):
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
            process_code="P-020",
        )

    def _create_child(
        self,
        *,
        title: str,
        process_code: str,
        compliance_status: str,
        active: bool = True,
    ):
        child = legal_requirement_service.create_requirement(
            title=title,
            process_code=process_code,
            parent_requirement_id=self._parent.id,
            compliance_status=compliance_status,
            active=active,
        )
        if compliance_status == "":
            with get_session() as session:
                row = session.get(LegalRequirement, child.id)
                assert row is not None
                row.compliance_status = ""
                session.commit()
            reloaded = legal_requirement_service.get_by_id(child.id)
            assert reloaded is not None
            return reloaded
        return child

    def _legal_area(self):
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            self._parent.id,
        )
        by_id = {item.area_id: item for item in breakdown.areas}
        return breakdown, by_id[PROCESS_INDEX_AREA_PRAVNI_POZADAVKY]

    def test_missing_requirements_keeps_score_none(self) -> None:
        breakdown, legal = self._legal_area()
        self.assertIsNone(legal.score)
        self.assertIsNone(legal.contribution)
        self.assertIsNone(breakdown.index_value)

    def test_legal_score_average_and_contribution(self) -> None:
        # 4× Splněno + 1× Nesplněno → 80 %; váha 25 % → přínos 20,0
        for index in range(1, 5):
            self._create_child(
                title=f"Splněný {index}",
                process_code=f"P-020.{index}",
                compliance_status=COMPLIANCE_SPLNENO,
            )
        self._create_child(
            title="Nesplněný",
            process_code="P-020.5",
            compliance_status=COMPLIANCE_NESPLNENO,
        )
        self._create_child(
            title="Nerelevantní",
            process_code="P-020.6",
            compliance_status=COMPLIANCE_NENI_RELEVANTNI,
        )
        self._create_child(
            title="Bez vyhodnocení",
            process_code="P-020.7",
            compliance_status="",
        )
        self._create_child(
            title="Neaktivní",
            process_code="P-020.8",
            compliance_status=COMPLIANCE_SPLNENO,
            active=False,
        )

        breakdown, legal = self._legal_area()

        self.assertEqual(legal.score, 80.0)
        self.assertEqual(legal.contribution, 20.0)
        self.assertEqual(breakdown.index_value, 80.0)
        self.assertEqual(breakdown.data_coverage_percent, 25)
        self.assertIsNotNone(legal.score_detail)
        self.assertEqual(legal.score_detail.total_count, 7)
        self.assertEqual(legal.score_detail.countable_count, 5)
        self.assertEqual(
            {
                item.result_code: item.points
                for item in legal.score_detail.point_mappings
            },
            PROCESS_INDEX_LEGAL_SCORE_POINTS,
        )
        by_code = {
            item.result_code: item.count for item in legal.score_detail.result_counts
        }
        self.assertEqual(by_code[COMPLIANCE_SPLNENO], 4)
        self.assertEqual(by_code[COMPLIANCE_CASTECNE_SPLNENO], 0)
        self.assertEqual(by_code[COMPLIANCE_NESPLNENO], 1)
        self.assertEqual(by_code[COMPLIANCE_NENI_RELEVANTNI], 1)
        self.assertEqual(by_code[""], 1)
        self.assertIn("80.0 %", legal.score_detail.calculation_summary)

        for area in breakdown.areas:
            if area.area_id == PROCESS_INDEX_AREA_PRAVNI_POZADAVKY:
                continue
            # Audity/Prověrky/Úkoly bez dat zůstávají None
            if area.area_id == "ukoly":
                self.assertIsNone(area.score)

    def test_partial_and_zero_scores(self) -> None:
        self._create_child(
            title="Částečný",
            process_code="P-020.1",
            compliance_status=COMPLIANCE_CASTECNE_SPLNENO,
        )
        _, legal = self._legal_area()
        self.assertEqual(legal.score, 50.0)
        self.assertEqual(legal.contribution, 12.5)

        self._create_child(
            title="Nesplněný",
            process_code="P-020.2",
            compliance_status=COMPLIANCE_NESPLNENO,
        )
        _, legal = self._legal_area()
        self.assertEqual(legal.score, 25.0)
        self.assertEqual(legal.contribution, 6.25)

    def test_only_excluded_statuses_keep_score_none(self) -> None:
        self._create_child(
            title="Nerelevantní",
            process_code="P-020.1",
            compliance_status=COMPLIANCE_NENI_RELEVANTNI,
        )
        self._create_child(
            title="Bez vyhodnocení",
            process_code="P-020.2",
            compliance_status="",
        )

        _, legal = self._legal_area()
        self.assertIsNone(legal.score)
        self.assertIsNone(legal.contribution)
        self.assertEqual(legal.score_detail.total_count, 2)
        self.assertEqual(legal.score_detail.countable_count, 0)
        by_code = {
            item.result_code: item.count for item in legal.score_detail.result_counts
        }
        self.assertEqual(by_code[COMPLIANCE_NENI_RELEVANTNI], 1)
        self.assertEqual(by_code[""], 1)
        unevaluated = next(
            item
            for item in legal.score_detail.result_counts
            if item.result_code == ""
        )
        self.assertEqual(unevaluated.result_label, PROCESS_STATUS_UNEVALUATED_LABEL)

    def test_widget_shows_formatted_legal_score(self) -> None:
        self._create_child(
            title="Splněný",
            process_code="P-020.1",
            compliance_status=COMPLIANCE_SPLNENO,
        )
        self._create_child(
            title="Částečný",
            process_code="P-020.2",
            compliance_status=COMPLIANCE_CASTECNE_SPLNENO,
        )

        widget = LegalRequirementProcessIndexWidget(self._parent.id)
        self.assertEqual(widget.table.item(2, 0).text(), "Právní požadavky")
        # (100 + 50) / 2 = 75; přínos 75 × 25 / 100 = 18,75
        self.assertEqual(widget.table.item(2, 2).text(), "75,0")
        self.assertEqual(widget.table.item(2, 3).text(), "18,8")
        self.assertEqual(widget.table.item(3, 2).text(), PROCESS_INDEX_PLACEHOLDER)
        self.assertIn("75,0 %", widget.index_label.text())
        self.assertEqual(widget.coverage_label.text(), "Pokrytí dat: 25 %")


if __name__ == "__main__":
    unittest.main()
