"""CONTROL-REPORT-FINDINGS-SUMMARY-7: skutečné druhy zjištění v úvodu zpráv."""

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

_TMP = Path(tempfile.mkdtemp(prefix="control-report-findings-summary-7-"))
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
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NEDOSTATEK,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        FINDING_TYPE_ZAVADA,
    )
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_report_language import (
        AUDIT_EMPTY_FOUND_SENTENCE,
        INSPECTION_EMPTY_FOUND_SENTENCE,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG as AUDIT_DETAILED_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG as AUDIT_PROTOCOL_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG as INSPECTION_DETAILED_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG as INSPECTION_PROTOCOL_CONFIG,
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


REPO_ROOT = Path(__file__).resolve().parents[1]


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _overview_section(content: str) -> str:
    after = content.split("Přehled výsledků", 1)[1]
    for marker in ("Silné stránky", "Oblasti vyžadující pozornost"):
        if marker in after:
            return after.split(marker, 1)[0]
    return after


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


class ControlReportFindingsSummary7TestCase(unittest.TestCase):
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

    def _add_result(
        self,
        entity_type: str,
        entity_id: int,
        *,
        point_id: str,
        result: str,
    ) -> None:
        control_result_service.set_result(
            entity_type,
            entity_id,
            ControlPointContext(
                area_id="oblast",
                area_label="Oblast",
                section_id="sekce",
                section_label="Sekce",
                control_point_id=point_id,
                control_point_label=f"Bod {point_id}",
            ),
            result=result,
        )

    def _add_finding(
        self,
        entity_type: str,
        entity_id: int,
        *,
        finding_type: str,
        point_id: str = "",
        status: str = FINDING_STATUS_OTEVRENE,
        description: str = "zjištění",
    ):
        return finding_service.create(
            entity_type,
            entity_id,
            finding_type=finding_type,
            description=description,
            source_control_point_id=point_id,
            status=status,
        )

    def _add_historical_finding(
        self,
        entity_type: str,
        entity_id: int,
        finding_type: str = "historicky_xyz",
    ):
        return finding_service.repository.save(
            Finding(
                entity_type=entity_type,
                entity_id=entity_id,
                finding_type=finding_type,
                description="historické",
                display_order=99,
            )
        )

    def _overview_lines(self, text: str) -> list[str]:
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _assert_overview_total_matches_parts(self, overview: str) -> None:
        lines = self._overview_lines(overview)
        total_line = next(line for line in lines if line.startswith("Zjištění celkem:"))
        total = int(total_line.split(":", 1)[1].strip())
        start = lines.index(total_line) + 1
        end = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("Otevřené úkoly:")
        )
        parts = 0
        for line in lines[start:end]:
            parts += int(line.split(":", 1)[1].strip())
        self.assertEqual(total, parts)
        self.assertTrue(lines[-1].startswith("Otevřené úkoly:"))

    def test_inspection_no_findings(self) -> None:
        inspection = self._create_inspection()
        ctx = bozp_inspection_export_context_service.build(inspection)
        assessment = ctx.overall_assessment_text()
        overview = ctx.results_overview_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, assessment)
        self.assertIn("Zjištění celkem: 0", overview)
        self.assertNotIn("Příležitosti ke zlepšení:", overview)
        self.assertTrue(overview.splitlines()[-1].startswith("Otevřené úkoly:"))

    def test_inspection_one_finding(self) -> None:
        inspection = self._create_inspection()
        self._add_finding(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(
            "Evidence prověrky obsahuje 1 zjištění, z toho 1 závadu.",
            ctx.overall_assessment_text(),
        )
        overview = ctx.results_overview_text()
        self.assertIn("Zjištění celkem: 1", overview)
        self.assertIn("Závady: 1", overview)
        self._assert_overview_total_matches_parts(overview)

    def test_inspection_few_same_type(self) -> None:
        inspection = self._create_inspection()
        for index in range(3):
            self._add_finding(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_NEDOSTATEK,
                point_id=f"n{index}",
            )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(
            "Evidence prověrky obsahuje 3 zjištění, z toho 3 nedostatky.",
            text,
        )

    def test_inspection_five_or_more_pkz(self) -> None:
        inspection = self._create_inspection()
        for index in range(5):
            self._add_finding(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_PRILEZITOST,
                point_id=f"p{index}",
            )
        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(
            "Evidence prověrky obsahuje 5 zjištění, z toho 5 příležitostí ke zlepšení.",
            ctx.overall_assessment_text(),
        )
        overview = ctx.results_overview_text()
        self.assertIn("Zjištění celkem: 5", overview)
        self.assertIn("Příležitosti ke zlepšení: 5", overview)
        self.assertNotIn("Závady:", overview)

    def test_inspection_mixed_types_order(self) -> None:
        inspection = self._create_inspection()
        self._add_finding(
            ENTITY_PROVERKY, inspection.id, finding_type=FINDING_TYPE_PRILEZITOST
        )
        self._add_finding(
            ENTITY_PROVERKY, inspection.id, finding_type=FINDING_TYPE_NEDOSTATEK
        )
        self._add_finding(
            ENTITY_PROVERKY, inspection.id, finding_type=FINDING_TYPE_ZAVADA
        )
        for index in range(4):
            self._add_finding(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_PRILEZITOST,
                point_id=f"pkz{index}",
            )
        ctx = bozp_inspection_export_context_service.build(inspection)
        sentence = ctx.overall_assessment_text()
        self.assertIn(
            "Evidence prověrky obsahuje 7 zjištění, z toho 1 závadu, "
            "1 nedostatek a 5 příležitostí ke zlepšení.",
            sentence,
        )
        overview = ctx.results_overview_text()
        zavady = overview.find("Závady:")
        nedostatky = overview.find("Nedostatky:")
        pkz = overview.find("Příležitosti ke zlepšení:")
        self.assertLess(zavady, nedostatky)
        self.assertLess(nedostatky, pkz)
        self._assert_overview_total_matches_parts(overview)

    def test_inspection_open_and_resolved_count(self) -> None:
        inspection = self._create_inspection()
        self._add_finding(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            status=FINDING_STATUS_OTEVRENE,
        )
        self._add_finding(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZAVADA,
            status=FINDING_STATUS_VYPORADANO,
            point_id="done",
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(
            "Evidence prověrky obsahuje 2 zjištění, z toho 2 závady.",
            ctx.overall_assessment_text(),
        )
        self.assertIn("Zjištění celkem: 2", ctx.results_overview_text())

    def test_inspection_unknown_historical_type(self) -> None:
        inspection = self._create_inspection()
        self._add_finding(
            ENTITY_PROVERKY, inspection.id, finding_type=FINDING_TYPE_ZAVADA
        )
        self._add_historical_finding(ENTITY_PROVERKY, inspection.id)
        ctx = bozp_inspection_export_context_service.build(inspection)
        overview = ctx.results_overview_text()
        self.assertIn("Zjištění celkem: 2", overview)
        self.assertIn("Závady: 1", overview)
        self.assertIn("Ostatní zjištění: 1", overview)
        self.assertIn("1 ostatní zjištění", ctx.overall_assessment_text())
        self._assert_overview_total_matches_parts(overview)

    def test_recommended_result_without_finding_does_not_count(self) -> None:
        inspection = self._create_inspection()
        self._add_result(
            ENTITY_PROVERKY,
            inspection.id,
            point_id="pkz",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, ctx.overall_assessment_text())
        self.assertIn("Zjištění celkem: 0", ctx.results_overview_text())
        self.assertIn("Vyhovuje s doporučením: 1", ctx.results_overview_text())

    def test_finding_without_control_result_counts(self) -> None:
        inspection = self._create_inspection()
        self._add_finding(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            point_id="orphan",
        )
        ctx = bozp_inspection_export_context_service.build(inspection)
        self.assertIn(
            "Evidence prověrky obsahuje 1 zjištění, z toho 1 příležitost ke zlepšení.",
            ctx.overall_assessment_text(),
        )
        self.assertIn("Zjištění celkem: 1", ctx.results_overview_text())

    def test_inspection_no_n_plus_one(self) -> None:
        inspection = self._create_inspection()
        for index in range(5):
            self._add_finding(
                ENTITY_PROVERKY,
                inspection.id,
                finding_type=FINDING_TYPE_PRILEZITOST,
                point_id=f"p{index}",
            )
        context = bozp_inspection_export_context_service.build(inspection)
        with patch.object(
            finding_service,
            "get_by_id",
            side_effect=AssertionError("N+1 get_by_id"),
        ):
            assessment = context.overall_assessment_text()
            overview = context.results_overview_text()
            context.attention_areas_text()
        self.assertIn("5 příležitostí ke zlepšení", assessment)
        self.assertIn("Zjištění celkem: 5", overview)

    def test_inspection_protocol_and_detailed_same_data(self) -> None:
        inspection = self._create_inspection()
        self._add_finding(
            ENTITY_PROVERKY, inspection.id, finding_type=FINDING_TYPE_ZAVADA
        )
        protocol_ctx = bozp_inspection_export_context_service.build(
            inspection, INSPECTION_PROTOCOL_CONFIG
        )
        detailed_ctx = bozp_inspection_export_context_service.build(
            inspection, INSPECTION_DETAILED_CONFIG
        )
        self.assertEqual(
            protocol_ctx.overall_assessment_text(),
            detailed_ctx.overall_assessment_text(),
        )
        self.assertEqual(
            protocol_ctx.results_overview_text(),
            detailed_ctx.results_overview_text(),
        )
        protocol = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        detailed = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        sentence = "Evidence prověrky obsahuje 1 zjištění, z toho 1 závadu."
        for content in (protocol, detailed):
            self.assertIn(sentence, content)
            overview = _overview_section(content)
            self.assertIn("Zjištění celkem: 1", overview)
            self.assertIn("Závady: 1", overview)

    def test_audit_no_findings(self) -> None:
        audit = self._create_audit()
        ctx = audit_export_context_service.build(audit)
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, ctx.overall_assessment_text())
        overview = ctx.results_overview_text()
        self.assertIn("Zjištění celkem: 0", overview)
        self.assertTrue(overview.splitlines()[-1].startswith("Otevřené úkoly:"))

    def test_audit_one_and_few_and_many(self) -> None:
        audit = self._create_audit()
        self._add_finding(
            ENTITY_AUDITY, audit.id, finding_type=FINDING_TYPE_NESHODA
        )
        one = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(
            "Evidence auditu obsahuje 1 zjištění, z toho 1 neshodu.",
            one,
        )
        for index in range(2):
            self._add_finding(
                ENTITY_AUDITY,
                audit.id,
                finding_type=FINDING_TYPE_NESHODA,
                point_id=f"n{index}",
            )
        few = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(
            "Evidence auditu obsahuje 3 zjištění, z toho 3 neshody.",
            few,
        )
        for index in range(2):
            self._add_finding(
                ENTITY_AUDITY,
                audit.id,
                finding_type=FINDING_TYPE_NESHODA,
                point_id=f"n2{index}",
            )
        many = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(
            "Evidence auditu obsahuje 5 zjištění, z toho 5 neshod.",
            many,
        )

    def test_audit_pkz_only_and_mixed(self) -> None:
        audit = self._create_audit()
        for index in range(5):
            self._add_finding(
                ENTITY_AUDITY,
                audit.id,
                finding_type=FINDING_TYPE_PRILEZITOST,
                point_id=f"p{index}",
            )
        pkz_ctx = audit_export_context_service.build(audit)
        self.assertIn(
            "Evidence auditu obsahuje 5 zjištění, z toho 5 příležitostí ke zlepšení.",
            pkz_ctx.overall_assessment_text(),
        )
        self._add_finding(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            point_id="nc",
        )
        self._add_finding(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_POZOROVANI,
            point_id="obs",
        )
        mixed = audit_export_context_service.build(audit)
        sentence = mixed.overall_assessment_text()
        self.assertIn(
            "Evidence auditu obsahuje 7 zjištění, z toho 1 neshodu, "
            "1 pozorování a 5 příležitostí ke zlepšení.",
            sentence,
        )
        overview = mixed.results_overview_text()
        self.assertLess(overview.find("Neshody:"), overview.find("Pozorování:"))
        self.assertLess(
            overview.find("Pozorování:"),
            overview.find("Příležitosti ke zlepšení:"),
        )
        self._assert_overview_total_matches_parts(overview)

    def test_audit_open_resolved_and_unknown(self) -> None:
        audit = self._create_audit()
        self._add_finding(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            status=FINDING_STATUS_OTEVRENE,
        )
        self._add_finding(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            status=FINDING_STATUS_VYPORADANO,
            point_id="done",
        )
        self._add_historical_finding(ENTITY_AUDITY, audit.id)
        ctx = audit_export_context_service.build(audit)
        overview = ctx.results_overview_text()
        self.assertIn("Zjištění celkem: 3", overview)
        self.assertIn("Neshody: 2", overview)
        self.assertIn("Ostatní zjištění: 1", overview)
        self._assert_overview_total_matches_parts(overview)

    def test_audit_recommended_without_finding_and_orphan_finding(self) -> None:
        audit = self._create_audit()
        self._add_result(
            ENTITY_AUDITY,
            audit.id,
            point_id="pkz",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        ctx = audit_export_context_service.build(audit)
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, ctx.overall_assessment_text())
        self.assertIn("Zjištění celkem: 0", ctx.results_overview_text())
        self._add_finding(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            point_id="orphan",
        )
        ctx2 = audit_export_context_service.build(audit)
        self.assertIn("Zjištění celkem: 1", ctx2.results_overview_text())

    def test_audit_no_n_plus_one_and_same_outputs(self) -> None:
        audit = self._create_audit()
        for index in range(4):
            self._add_finding(
                ENTITY_AUDITY,
                audit.id,
                finding_type=FINDING_TYPE_NESHODA,
                point_id=f"n{index}",
            )
        context = audit_export_context_service.build(audit)
        with patch.object(
            finding_service,
            "get_by_id",
            side_effect=AssertionError("N+1 get_by_id"),
        ):
            assessment = context.overall_assessment_text()
            overview = context.results_overview_text()
            context.attention_areas_text()
        self.assertIn("4 neshody", assessment)
        self.assertIn("Zjištění celkem: 4", overview)

        protocol_ctx = audit_export_context_service.build(audit, AUDIT_PROTOCOL_CONFIG)
        detailed_ctx = audit_export_context_service.build(audit, AUDIT_DETAILED_CONFIG)
        self.assertEqual(
            protocol_ctx.overall_assessment_text(),
            detailed_ctx.overall_assessment_text(),
        )
        self.assertEqual(
            protocol_ctx.results_overview_text(),
            detailed_ctx.results_overview_text(),
        )
        protocol = _odt_content(protokol_audit_service.generate_for_audit(audit))
        detailed = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        sentence = "Evidence auditu obsahuje 4 zjištění, z toho 4 neshody."
        for content in (protocol, detailed):
            self.assertIn(sentence, content)

    def test_system_failure_still_from_ratings(self) -> None:
        inspection = self._create_inspection()
        for index in range(3):
            self._add_result(
                ENTITY_PROVERKY,
                inspection.id,
                point_id=f"bad{index}",
                result=CONTROL_RESULT_NEVYHOVUJE,
            )
        text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, text)
        self.assertIn(
            "Bylo prokázáno systémové selhání v některých oblastech.",
            text,
        )


if __name__ == "__main__":
    unittest.main()
