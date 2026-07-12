"""Fáze 97m – Index procesu: skóre prověrek."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.services.editable_catalog_service import editable_catalog_service
    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_INDEX_AREA_PROVERKY,
        PROCESS_INDEX_INSPECTION_SCORE_POINTS,
        PROCESS_INDEX_PLACEHOLDER,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service

_AREA_ID = "prvni_pomoc"
_SECTION_ID = "lekarnicka"
_QUESTIONS = (
    "umisteni",
    "oznaceni",
    "pristupnost",
    "obsah",
    "expirace",
)


class LegalRequirementProcessIndexPhase97mTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.shared.modely.control_result import ControlResult
        from core.shared.modely.finding import Finding
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.proverky.modely.bozp_inspection import BozpInspection

        import core.services.editable_catalog_service as editable_catalog_module
        import moduly.proverky.sluzby.proverky_knowledge_service as proverky_module

        importlib.reload(editable_catalog_module)
        importlib.reload(proverky_module)

        self._proverky = proverky_module.proverky_knowledge_service
        self._proverky.ensure_catalogs()

        area = self._proverky.get_area_by_id(_AREA_ID)
        self.assertIsNotNone(area)
        self._area_name = area.nazev
        self._path = self._proverky.proverky_dir / area.soubor_znalosti
        bundled = editable_catalog_service.bundled_path(f"proverky/{area.soubor_znalosti}")
        shutil.copy2(bundled, self._path)
        with self._path.open(encoding="utf-8") as handle:
            self._original = json.load(handle)

        section = self._proverky.get_section(_AREA_ID, _SECTION_ID)
        self.assertIsNotNone(section)
        self._section_name = str(section.get("nazev") or _SECTION_ID)

        with get_session() as session:
            session.execute(delete(Finding))
            session.execute(delete(ControlResult))
            session.execute(delete(BozpInspection))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._requirement = legal_requirement_service.create_requirement(
            title="První pomoc",
            process_code="P-006",
        )

    def tearDown(self) -> None:
        self._path.write_text(
            json.dumps(self._original, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _link_section(self) -> None:
        section = self._proverky.get_section(_AREA_ID, _SECTION_ID)
        self.assertIsNotNone(section)
        payload = dict(section)
        payload["legal_requirement_id"] = self._requirement.id
        ok, errors = self._proverky.save_section(_AREA_ID, _SECTION_ID, payload)
        self.assertTrue(ok, msg="; ".join(errors))

    def _create_inspection(
        self,
        *,
        finished_at: date | None,
        inspection_date: date | None = None,
        title: str = "Prověrka BOZP",
    ):
        return bozp_inspection_service.create_inspection(
            title=title,
            inspection_date=inspection_date or finished_at or date(2026, 1, 1),
            started_at=date(2026, 1, 1),
            finished_at=finished_at,
            workplace_name="Provoz A",
            year=2026,
        )

    def _set_result(self, inspection_id: int, *, question_id: str, result: str) -> None:
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection_id,
            ControlPointContext(
                area_id=_AREA_ID,
                area_label=self._area_name,
                section_id=_SECTION_ID,
                section_label=self._section_name,
                control_point_id=question_id,
                control_point_label="Otázka",
            ),
            result=result,
        )

    def _proverky_area(self, requirement_id: int | None = None):
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            requirement_id if requirement_id is not None else self._requirement.id,
        )
        by_id = {item.area_id: item for item in breakdown.areas}
        return breakdown, by_id[PROCESS_INDEX_AREA_PROVERKY]

    def test_missing_inspection_data_keeps_score_none(self) -> None:
        breakdown, proverky = self._proverky_area()
        self.assertIsNone(proverky.score)
        self.assertIsNone(proverky.contribution)
        self.assertIsNone(breakdown.index_value)

    def test_inspection_score_average_and_contribution(self) -> None:
        self._link_section()
        inspection = self._create_inspection(
            finished_at=date(2026, 3, 15),
            title="Jarní prověrka",
        )
        results = (
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            CONTROL_RESULT_NEVYHOVUJE,
        )
        for question_id, result in zip(_QUESTIONS, results, strict=True):
            self._set_result(inspection.id, question_id=question_id, result=result)

        # Zjištění nesmí ovlivnit skóre.
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            description="Nález",
            finding_type=FINDING_TYPE_ZJISTENI,
            status=FINDING_STATUS_OTEVRENE,
            source_area_label=self._area_name,
            source_section_label=self._section_name,
            source_control_point_id=_QUESTIONS[0],
            source_control_point_label="Otázka",
        )

        breakdown, proverky = self._proverky_area()

        self.assertEqual(proverky.score, 75.0)
        self.assertEqual(proverky.contribution, 22.5)
        self.assertIsNone(breakdown.index_value)
        self.assertIsNotNone(proverky.score_detail)
        self.assertEqual(proverky.score_detail.countable_count, 5)
        self.assertEqual(proverky.score_detail.source_entity_id, inspection.id)
        self.assertEqual(proverky.score_detail.source_entity_date, date(2026, 3, 15))
        self.assertEqual(
            {
                item.result_code: item.points
                for item in proverky.score_detail.point_mappings
            },
            PROCESS_INDEX_INSPECTION_SCORE_POINTS,
        )
        by_code = {
            item.result_code: item.count for item in proverky.score_detail.result_counts
        }
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE], 3)
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM], 1)
        self.assertEqual(by_code[CONTROL_RESULT_NEVYHOVUJE], 1)
        self.assertIn("75.0 %", proverky.score_detail.calculation_summary)

    def test_zero_score_is_not_missing(self) -> None:
        self._link_section()
        inspection = self._create_inspection(finished_at=date(2026, 4, 1))
        self._set_result(
            inspection.id,
            question_id=_QUESTIONS[0],
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        _, proverky = self._proverky_area()
        self.assertEqual(proverky.score, 0.0)
        self.assertEqual(proverky.contribution, 0.0)

    def test_excludes_unevaluated_and_cannot_assess(self) -> None:
        self._link_section()
        inspection = self._create_inspection(finished_at=date(2026, 5, 1))
        self._set_result(
            inspection.id,
            question_id=_QUESTIONS[0],
            result=CONTROL_RESULT_VYHOVUJE,
        )
        self._set_result(
            inspection.id,
            question_id=_QUESTIONS[1],
            result=CONTROL_RESULT_NEKONTROLOVANO,
        )
        self._set_result(
            inspection.id,
            question_id=_QUESTIONS[2],
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )

        _, proverky = self._proverky_area()
        self.assertEqual(proverky.score, 100.0)
        self.assertEqual(proverky.contribution, 30.0)
        self.assertEqual(proverky.score_detail.countable_count, 1)

    def test_uses_latest_completed_inspection_only(self) -> None:
        self._link_section()
        older = self._create_inspection(finished_at=date(2026, 1, 10), title="Stará")
        newer = self._create_inspection(finished_at=date(2026, 6, 1), title="Nová")
        self._set_result(older.id, question_id=_QUESTIONS[0], result=CONTROL_RESULT_NEVYHOVUJE)
        self._set_result(newer.id, question_id=_QUESTIONS[0], result=CONTROL_RESULT_VYHOVUJE)

        _, proverky = self._proverky_area()
        self.assertEqual(proverky.score, 100.0)
        self.assertEqual(proverky.score_detail.source_entity_id, newer.id)

    def test_widget_shows_formatted_inspection_score(self) -> None:
        self._link_section()
        inspection = self._create_inspection(finished_at=date(2026, 3, 15))
        self._set_result(
            inspection.id,
            question_id=_QUESTIONS[0],
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        widget = LegalRequirementProcessIndexWidget(self._requirement.id)
        self.assertEqual(widget.table.item(1, 0).text(), "Prověrky")
        self.assertEqual(widget.table.item(1, 2).text(), "75,0")
        self.assertEqual(widget.table.item(1, 3).text(), "22,5")
        self.assertEqual(widget.table.item(2, 2).text(), PROCESS_INDEX_PLACEHOLDER)
        self.assertIn(PROCESS_INDEX_PLACEHOLDER, widget.index_label.text())


if __name__ == "__main__":
    unittest.main()
