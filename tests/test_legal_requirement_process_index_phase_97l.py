"""Fáze 97l – Index procesu: skóre auditů."""

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
        ENTITY_AUDITY,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
        PROCESS_INDEX_AREA_AUDITY,
        PROCESS_INDEX_AUDIT_SCORE_POINTS,
        PROCESS_INDEX_PLACEHOLDER,
        legal_requirement_process_status_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_process_index_widget import (
        LegalRequirementProcessIndexWidget,
    )

_RIZENI_RIZIK_PROCESS_ID = "rizeni_rizik"
_LINKED_SECTION_ID = "identifikace_nebezpeci"
_ASSERTIONS = (
    "id_proces_identifikace",
    "id_zapojeni_zamestnancu",
    "id_zmeny_hodnoceny",
    "id_evidence_nebezpeci",
    "id_nove_cinnosti",
)


class LegalRequirementProcessIndexPhase97lTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.shared.modely.control_result import ControlResult
        from moduly.audity.modely.audit import Audit
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        audit_knowledge_editor_service.ensure_user_catalogs()
        self._knowledge_path = audit_knowledge_service.audity_dir / "rizeni_rizik.json"
        bundled = editable_catalog_service.bundled_path("audity/rizeni_rizik.json")
        shutil.copy2(bundled, self._knowledge_path)
        with self._knowledge_path.open(encoding="utf-8") as handle:
            self._original_knowledge = json.load(handle)

        with get_session() as session:
            session.execute(delete(ControlResult))
            session.execute(delete(Audit))
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

        self._requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        self._process_name = "Řízení rizik"
        self._section_name = "Identifikace nebezpečí a rizik"

    def tearDown(self) -> None:
        self._knowledge_path.write_text(
            json.dumps(self._original_knowledge, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _link_section(self) -> None:
        with self._knowledge_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        section = next(
            item for item in payload.get("sekce") or [] if item.get("id") == _LINKED_SECTION_ID
        )
        errors = audit_knowledge_editor_service.save_section_metadata(
            _RIZENI_RIZIK_PROCESS_ID,
            _LINKED_SECTION_ID,
            {
                "nazev": section.get("nazev"),
                "popis": section.get("popis"),
                "cil_overeni": section.get("cil_overeni"),
                "poradi": section.get("poradi"),
                "aktivni": section.get("aktivni", True),
                "legal_requirement_id": self._requirement.id,
            },
        )
        self.assertEqual(errors, [])

    def _create_audit(
        self,
        *,
        finished_at: date | None,
        audit_date: date | None = None,
        title: str = "Audit procesu",
    ):
        return audit_service.create_audit(
            title=title,
            audit_date=audit_date or finished_at or date(2026, 1, 1),
            started_at=date(2026, 1, 1),
            finished_at=finished_at,
            workplace_name="Provoz A",
        )

    def _set_result(self, audit_id: int, *, assertion_id: str, result: str) -> None:
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
            ControlPointContext(
                area_id=_RIZENI_RIZIK_PROCESS_ID,
                area_label=self._process_name,
                section_id=_LINKED_SECTION_ID,
                section_label=self._section_name,
                control_point_id=assertion_id,
                control_point_label="Tvrzení",
            ),
            result=result,
        )

    def _audit_area(self, requirement_id: int | None = None):
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            requirement_id if requirement_id is not None else self._requirement.id,
        )
        by_id = {item.area_id: item for item in breakdown.areas}
        return breakdown, by_id[PROCESS_INDEX_AREA_AUDITY]

    def test_missing_audit_data_keeps_score_none(self) -> None:
        breakdown, audity = self._audit_area()
        self.assertIsNone(audity.score)
        self.assertIsNone(audity.contribution)
        self.assertIsNone(breakdown.index_value)
        for area in breakdown.areas:
            if area.area_id == PROCESS_INDEX_AREA_AUDITY:
                continue
            self.assertIsNone(area.score)
            self.assertIsNone(area.contribution)

    def test_audit_score_average_and_contribution(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 3, 15), title="Jarní audit")
        results = (
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            CONTROL_RESULT_NEVYHOVUJE,
        )
        for assertion_id, result in zip(_ASSERTIONS, results, strict=True):
            self._set_result(audit.id, assertion_id=assertion_id, result=result)

        breakdown, audity = self._audit_area()

        self.assertEqual(audity.score, 75.0)
        self.assertEqual(audity.contribution, 22.5)
        self.assertIsNone(breakdown.index_value)
        self.assertIsNotNone(audity.score_detail)
        self.assertEqual(audity.score_detail.countable_count, 5)
        self.assertEqual(audity.score_detail.source_entity_id, audit.id)
        self.assertEqual(audity.score_detail.source_entity_date, date(2026, 3, 15))
        self.assertEqual(
            {item.result_code: item.points for item in audity.score_detail.point_mappings},
            PROCESS_INDEX_AUDIT_SCORE_POINTS,
        )
        by_code = {
            item.result_code: item.count for item in audity.score_detail.result_counts
        }
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE], 3)
        self.assertEqual(by_code[CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM], 1)
        self.assertEqual(by_code[CONTROL_RESULT_NEVYHOVUJE], 1)
        self.assertIn("75.0 %", audity.score_detail.calculation_summary)

        for area in breakdown.areas:
            if area.area_id == PROCESS_INDEX_AREA_AUDITY:
                continue
            self.assertIsNone(area.score)
            self.assertIsNone(area.contribution)

    def test_zero_score_is_not_missing(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 4, 1))
        self._set_result(
            audit.id,
            assertion_id=_ASSERTIONS[0],
            result=CONTROL_RESULT_NEVYHOVUJE,
        )

        _, audity = self._audit_area()
        self.assertEqual(audity.score, 0.0)
        self.assertEqual(audity.contribution, 0.0)

    def test_excludes_unevaluated_and_cannot_assess(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 5, 1))
        self._set_result(
            audit.id,
            assertion_id=_ASSERTIONS[0],
            result=CONTROL_RESULT_VYHOVUJE,
        )
        self._set_result(
            audit.id,
            assertion_id=_ASSERTIONS[1],
            result=CONTROL_RESULT_NEKONTROLOVANO,
        )
        self._set_result(
            audit.id,
            assertion_id=_ASSERTIONS[2],
            result=CONTROL_RESULT_NELZE_POSOUDIT,
        )

        _, audity = self._audit_area()
        self.assertEqual(audity.score, 100.0)
        self.assertEqual(audity.contribution, 30.0)
        self.assertEqual(audity.score_detail.countable_count, 1)

    def test_uses_latest_completed_audit_only(self) -> None:
        self._link_section()
        older = self._create_audit(finished_at=date(2026, 1, 10), title="Starý")
        newer = self._create_audit(finished_at=date(2026, 6, 1), title="Nový")
        self._set_result(older.id, assertion_id=_ASSERTIONS[0], result=CONTROL_RESULT_NEVYHOVUJE)
        self._set_result(newer.id, assertion_id=_ASSERTIONS[0], result=CONTROL_RESULT_VYHOVUJE)

        _, audity = self._audit_area()
        self.assertEqual(audity.score, 100.0)
        self.assertEqual(audity.score_detail.source_entity_id, newer.id)

    def test_widget_shows_formatted_audit_score(self) -> None:
        self._link_section()
        audit = self._create_audit(finished_at=date(2026, 3, 15))
        self._set_result(
            audit.id,
            assertion_id=_ASSERTIONS[0],
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        widget = LegalRequirementProcessIndexWidget(self._requirement.id)
        self.assertEqual(widget.table.item(0, 0).text(), "Audity")
        self.assertEqual(widget.table.item(0, 2).text(), "75,0")
        self.assertEqual(widget.table.item(0, 3).text(), "22,5")
        self.assertEqual(widget.table.item(1, 2).text(), PROCESS_INDEX_PLACEHOLDER)
        self.assertIn(PROCESS_INDEX_PLACEHOLDER, widget.index_label.text())


if __name__ == "__main__":
    unittest.main()
