"""CONTROL-REPORT-CZECH-SENTENCES-2: věty CELKOVÉHO HODNOCENÍ v kontextech."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="control-report-czech-sentences-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import (
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
    )
    from core.shared.sluzby.control_report_language import (
        AUDIT_EMPTY_FOUND_SENTENCE,
        INSPECTION_EMPTY_FOUND_SENTENCE,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


REPO_ROOT = Path(__file__).resolve().parents[1]

_FORBIDDEN = (
    r"byla zjištěna 5",
    r"5 příležitosti(?!í)",
    r"5 neshody",
    r"21 příležitost(?!í)",
    r"22 příležitosti(?!í)",
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _sync_templates() -> None:
    import moduly.audity.sluzby.protokol_audit_service as audit_protokol
    import moduly.proverky.sluzby.protokol_proverky_service as inspection_protokol

    importlib.reload(inspection_protokol)
    importlib.reload(audit_protokol)
    pairs = (
        (
            REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty",
            inspection_protokol.protokol_proverky_service,
            ("ProtokolProverkyBOZP.odt", "PodrobnaZpravaProverky.odt"),
        ),
        (
            REPO_ROOT / "moduly" / "audity" / "templates" / "exporty",
            audit_protokol.protokol_audit_service,
            ("ProtokolAudit.odt", "PodrobnaZpravaAudit.odt"),
        ),
    )
    for bundled_root, service, names in pairs:
        for name in names:
            target = service.template_path(detailed="Podrobna" in name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_root / name, target)


def _assert_forbidden_absent(test: unittest.TestCase, text: str) -> None:
    for pattern in _FORBIDDEN:
        test.assertNotRegex(text, pattern)


class ControlReportCzechSentences2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_templates()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_inspection(self):
        workplace = settings_service.save_workplace(name="Poříčí")
        return bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=1,
            started_at=date(2026, 1, 10),
            finished_at=date(2026, 1, 12),
            notes_mode=None,
        )

    def _create_audit(self):
        workplace = settings_service.save_workplace(name="Provoz Audit")
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=2,
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 3),
            notes_mode=None,
        )

    def _add_results(
        self,
        entity_type: str,
        entity_id: int,
        *,
        result: str,
        count: int,
        prefix: str,
    ) -> None:
        for index in range(count):
            control_result_service.set_result(
                entity_type,
                entity_id,
                ControlPointContext(
                    area_id="oblast",
                    area_label="Oblast",
                    section_id="sekce",
                    section_label="Sekce",
                    control_point_id=f"{prefix}_{index}",
                    control_point_label=f"Bod {prefix} {index}",
                ),
                result=result,
            )

    def test_inspection_only_one_defect(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=1,
            prefix="bad",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertIn(
            "Prověrka BOZP prokázala nedostatky vyžadující nápravu",
            text,
        )
        self.assertIn("Prověrka neprokázala systémové selhání.", text)
        self.assertNotIn("Během prověrky", text)
        self.assertNotIn("neshoda", text.casefold())
        _assert_forbidden_absent(self, text)

    def test_inspection_only_few_opportunities(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=3,
            prefix="pkz",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertIn(
            "Prověrka BOZP potvrdila obecně vyhovující stav s doporučeními",
            text,
        )
        self.assertIn("Prověrka neprokázala systémové selhání.", text)
        _assert_forbidden_absent(self, text)

    def test_inspection_only_five_opportunities(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=5,
            prefix="pkz",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertNotIn("závada", text.casefold())
        _assert_forbidden_absent(self, text)

        protocol = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        detailed = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        for content in (protocol, detailed):
            self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, content)
            _assert_forbidden_absent(self, content)

    def test_inspection_only_21_and_22_opportunities(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=21,
            prefix="pkz21",
        )
        text_21 = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text_21)
        _assert_forbidden_absent(self, text_21)

        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=1,
            prefix="pkz22",
        )
        text_22 = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text_22)
        _assert_forbidden_absent(self, text_22)

    def test_inspection_combination_one_and_five(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=1,
            prefix="bad",
        )
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=5,
            prefix="pkz",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertIn(
            "Prověrka BOZP prokázala nedostatky vyžadující nápravu",
            text,
        )
        self.assertIn("Prověrka neprokázala systémové selhání.", text)
        _assert_forbidden_absent(self, text)

    def test_inspection_combination_two_and_one(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=2,
            prefix="bad",
        )
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=1,
            prefix="pkz",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        _assert_forbidden_absent(self, text)

    def test_inspection_both_zero_keeps_empty_wording(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE,
            count=1,
            prefix="ok",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertNotIn("bylo zjištěno 0", text)
        self.assertIn("Prověrka neprokázala systémové selhání.", text)

    def test_inspection_system_failure_sentence_unchanged(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=5,
            prefix="bad",
        )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertIn(
            "Bylo prokázáno systémové selhání v některých oblastech.",
            text,
        )
        _assert_forbidden_absent(self, text)

    def test_audit_only_one_nonconformity(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=1,
            prefix="nc",
        )
        text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, text)
        self.assertIn("Systém řízení vykazuje neshody vyžadující nápravu.", text)
        self.assertIn("Audit neprokázal systémové selhání.", text)
        self.assertNotIn("závada", text.casefold())
        _assert_forbidden_absent(self, text)

    def test_audit_only_few_nonconformities(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=3,
            prefix="nc",
        )
        text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, text)
        self.assertIn(
            "Bylo prokázáno systémové selhání v některých oblastech.",
            text,
        )
        _assert_forbidden_absent(self, text)

    def test_audit_only_five_opportunities_in_odt(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=5,
            prefix="pkz",
        )
        text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, text)
        _assert_forbidden_absent(self, text)

        protocol = _odt_content(protokol_audit_service.generate_for_audit(audit))
        detailed = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        for content in (protocol, detailed):
            self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, content)
            _assert_forbidden_absent(self, content)

    def test_audit_combination_two_and_one(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=2,
            prefix="nc",
        )
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=1,
            prefix="pkz",
        )
        text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, text)
        self.assertIn("Audit neprokázal systémové selhání.", text)
        _assert_forbidden_absent(self, text)

    def test_audit_both_zero_keeps_empty_wording(self) -> None:
        audit = self._create_audit()
        text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, text)
        self.assertNotIn("bylo zjištěno 0", text)
        self.assertIn("Audit neprokázal systémové selhání.", text)


if __name__ == "__main__":
    unittest.main()
