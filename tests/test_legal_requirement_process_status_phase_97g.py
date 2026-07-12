"""Fáze 97g – Stav procesu: výsledky prověrek."""

from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel

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
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.control_result_display import control_result_label
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_STATUS_NO_INSPECTION_QUESTIONS,
        PROCESS_STATUS_NOT_INSPECTED,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_status_widget import (
        LegalRequirementProcessStatusWidget,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service

_AREA_ID = "prvni_pomoc"
_SECTION_ID = "lekarnicka"
_QUESTION_ID = "umisteni"
_QUESTION_ID_2 = "oznaceni"


class LegalRequirementProcessStatusPhase97gTestCase(unittest.TestCase):
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

    def _link_section(self, requirement_id: int | None = None) -> None:
        requirement_id = requirement_id if requirement_id is not None else self._requirement.id
        section = self._proverky.get_section(_AREA_ID, _SECTION_ID)
        self.assertIsNotNone(section)
        payload = dict(section)
        payload["legal_requirement_id"] = requirement_id
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

    def _set_result(
        self,
        inspection_id: int,
        *,
        question_id: str,
        result: str,
        label: str = "Otázka",
    ) -> None:
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection_id,
            ControlPointContext(
                area_id=_AREA_ID,
                area_label=self._area_name,
                section_id=_SECTION_ID,
                section_label=self._section_name,
                control_point_id=question_id,
                control_point_label=label,
            ),
            result=result,
        )

    def _create_finding(
        self,
        inspection_id: int,
        *,
        question_id: str = _QUESTION_ID,
        status: str = FINDING_STATUS_OTEVRENE,
    ):
        return finding_service.create(
            ENTITY_PROVERKY,
            inspection_id,
            description="Nález u lékárničky",
            finding_type=FINDING_TYPE_ZJISTENI,
            status=status,
            source_area_label=self._area_name,
            source_section_label=self._section_name,
            source_control_point_id=question_id,
            source_control_point_label="Lékárnička je na určeném místě",
        )

    def test_no_linked_questions_shows_empty_message(self) -> None:
        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )
        self.assertEqual(status.question_count, 0)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NO_INSPECTION_QUESTIONS)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Prověrky", labels)
        self.assertIn(PROCESS_STATUS_NO_INSPECTION_QUESTIONS, labels)

    def test_linked_but_never_inspected_shows_empty_message(self) -> None:
        self._link_section()
        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )
        self.assertGreater(status.question_count, 0)
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_INSPECTED)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn(PROCESS_STATUS_NOT_INSPECTED, labels)

    def test_last_completed_inspection_results_are_summarized(self) -> None:
        self._link_section()
        inspection = self._create_inspection(
            finished_at=date(2026, 3, 15),
            title="Jarní prověrka",
        )
        self._set_result(
            inspection.id,
            question_id=_QUESTION_ID,
            result=CONTROL_RESULT_VYHOVUJE,
        )
        self._set_result(
            inspection.id,
            question_id=_QUESTION_ID_2,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._create_finding(inspection.id, question_id=_QUESTION_ID)
        self._create_finding(
            inspection.id,
            question_id=_QUESTION_ID_2,
            status=FINDING_STATUS_VYPORADANO,
        )

        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )

        self.assertIsNone(status.empty_message)
        self.assertEqual(status.last_inspection_id, inspection.id)
        self.assertEqual(status.last_inspection_date, date(2026, 3, 15))
        self.assertEqual(status.last_inspection_number, inspection.number)
        self.assertEqual(status.evaluated_count, 2)
        self.assertEqual(status.findings_total, 2)
        self.assertEqual(status.findings_open, 1)

        by_code = {item.result_code: item.count for item in status.result_counts}
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE], 1)
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM], 1)

        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Poslední dokončená prověrka: 15.03.2026", labels)
        self.assertTrue(any(inspection.number in text for text in labels))
        self.assertIn(f"• {control_result_label(CONTROL_RESULT_VYHOVUJE)}: 1", labels)
        self.assertIn("Zjištění z otázek procesu: 2", labels)
        self.assertIn("Z toho otevřená zjištění: 1", labels)

    def test_uses_latest_completed_inspection_only(self) -> None:
        self._link_section()
        older = self._create_inspection(finished_at=date(2026, 1, 10), title="Stará")
        newer = self._create_inspection(finished_at=date(2026, 4, 20), title="Nová")
        self._set_result(older.id, question_id=_QUESTION_ID, result=CONTROL_RESULT_NEVYHOVUJE)
        self._set_result(newer.id, question_id=_QUESTION_ID, result=CONTROL_RESULT_VYHOVUJE)

        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )
        self.assertEqual(status.last_inspection_id, newer.id)
        by_code = {item.result_code: item.count for item in status.result_counts}
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE], 1)
        self.assertEqual(by_code[CONTROL_RESULT_NEVYHOVUJE], 0)

    def test_in_progress_inspection_is_ignored(self) -> None:
        self._link_section()
        open_inspection = self._create_inspection(
            finished_at=None,
            inspection_date=date(2026, 5, 1),
        )
        self._set_result(
            open_inspection.id,
            question_id=_QUESTION_ID,
            result=CONTROL_RESULT_VYHOVUJE,
        )

        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_INSPECTED)

    def test_nekontrolovano_alone_does_not_count_as_verified(self) -> None:
        self._link_section()
        inspection = self._create_inspection(finished_at=date(2026, 2, 1))
        self._set_result(
            inspection.id,
            question_id=_QUESTION_ID,
            result=CONTROL_RESULT_NEKONTROLOVANO,
        )

        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_INSPECTED)

    def test_unrelated_question_results_are_ignored(self) -> None:
        self._link_section()
        inspection = self._create_inspection(finished_at=date(2026, 3, 1))
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="jina_oblast",
                area_label="Jiná oblast",
                section_id="jina_sekce",
                section_label="Jiná sekce",
                control_point_id="cizi_otazka",
                control_point_label="Cizí",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        status = legal_requirement_process_status_service.get_inspection_status(
            self._requirement.id,
        )
        self.assertEqual(status.empty_message, PROCESS_STATUS_NOT_INSPECTED)

    def test_audit_and_inspection_sections_both_visible(self) -> None:
        widget = LegalRequirementProcessStatusWidget(self._requirement.id)
        labels = [label.text() for label in widget.findChildren(QLabel)]
        self.assertIn("Audity", labels)
        self.assertIn("Prověrky", labels)


if __name__ == "__main__":
    unittest.main()
