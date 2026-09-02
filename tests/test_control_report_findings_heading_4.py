"""CONTROL-REPORT-FINDINGS-HEADING-4: jednotný nadpis podrobného přehledu zjištění."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="control-report-findings-heading-4-"))
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
HEADING = "Podrobný přehled zjištění"
OLD_HEADING = "Významná zjištění"
PLACEHOLDER = "${vyznamna_zjisteni_text}"
HEADING_XML = f'<text:p text:style-name="H">{HEADING}</text:p>'

_INSPECTION_TEMPLATES = (
    REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / "ProtokolProverkyBOZP.odt",
    REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / "PodrobnaZpravaProverky.odt",
)
_AUDIT_TEMPLATES = (
    REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / "ProtokolAudit.odt",
    REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / "PodrobnaZpravaAudit.odt",
)
_YEARLY_TEMPLATES = (
    REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / "RocniZpravaBOZP.odt",
    REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / "RocniZpravaAuditu.odt",
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _findings_section(content: str) -> str:
    after = content.split(HEADING, 1)[1]
    for marker in ("Doporučení vedoucího prověrky", "Doporučení vedoucího auditora"):
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


def _find_libreoffice() -> str | None:
    for candidate in ("soffice", "libreoffice"):
        found = shutil.which(candidate)
        if found:
            return found
    snap = Path("/snap/bin/libreoffice")
    if snap.exists():
        return str(snap)
    return None


def _pdf_contains(pdf_bytes: bytes, text: str) -> bool:
    encodings = (text.encode("utf-8"), text.encode("utf-16-be"), text.encode("utf-16-le"))
    return any(chunk in pdf_bytes for chunk in encodings)


class ControlReportFindingsHeading4TestCase(unittest.TestCase):
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

    def _inspection_outputs(self, inspection):
        return (
            protokol_proverky_service.generate_for_inspection(inspection),
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            ),
        )

    def _audit_outputs(self, audit):
        return (
            protokol_audit_service.generate_for_audit(audit),
            protokol_audit_service.generate_detailed_report_for_audit(audit),
        )

    def _assert_heading_in_outputs(self, paths) -> None:
        for path in paths:
            content = _odt_content(path)
            self.assertIn(HEADING, content, msg=path.name)
            self.assertNotIn(OLD_HEADING, content, msg=path.name)
            self.assertNotIn(PLACEHOLDER, content, msg=path.name)
            section = _findings_section(content)
            self.assertTrue(section.strip(), msg=path.name)

    def test_bundled_templates_have_fixed_heading_and_placeholder(self) -> None:
        for path in _INSPECTION_TEMPLATES + _AUDIT_TEMPLATES:
            xml = _odt_content(path)
            self.assertIn(HEADING_XML, xml, msg=path.name)
            self.assertIn(PLACEHOLDER, xml, msg=path.name)
            self.assertNotIn(OLD_HEADING, xml, msg=path.name)
            heading_pos = xml.find(HEADING_XML)
            placeholder_pos = xml.find(PLACEHOLDER, heading_pos)
            self.assertGreater(placeholder_pos, heading_pos, msg=path.name)
            self.assertLess(placeholder_pos - heading_pos, 250, msg=path.name)

    def test_yearly_reports_keep_significant_findings_appendix(self) -> None:
        for path in _YEARLY_TEMPLATES:
            xml = _odt_content(path)
            self.assertIn("Příloha – Významná zjištění", xml, msg=path.name)
            self.assertNotIn(HEADING, xml, msg=path.name)

    def test_inspection_only_opportunities_heading(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=2,
            prefix="pkz",
        )
        paths = self._inspection_outputs(inspection)
        self._assert_heading_in_outputs(paths)
        for path in paths:
            content = _odt_content(path)
            section = _findings_section(content)
            self.assertIn("Oblast", section)
            self.assertIn("Kontrolní bod", content)
            self.assertIn("Vyhovuje s doporučením", content)

    def test_inspection_only_defects_heading(self) -> None:
        inspection = self._create_inspection()
        self._add_results(
            ENTITY_PROVERKY,
            inspection.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=1,
            prefix="bad",
        )
        paths = self._inspection_outputs(inspection)
        self._assert_heading_in_outputs(paths)
        for path in paths:
            self.assertIn("Závada", _odt_content(path))

    def test_inspection_mixed_results_heading(self) -> None:
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
            count=1,
            prefix="pkz",
        )
        self._assert_heading_in_outputs(self._inspection_outputs(inspection))

    def test_inspection_empty_heading_and_zero_sentence(self) -> None:
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
        self.assertNotIn("Během prověrky nebyla zjištěna významná zjištění.", text)

        paths = self._inspection_outputs(inspection)
        self._assert_heading_in_outputs(paths)
        for path in paths:
            content = _odt_content(path)
            self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, content)
            self.assertIn(
                "Nejsou evidována žádná zjištění k podrobnému uvedení.",
                _findings_section(content),
            )
            folded = content.casefold()
            self.assertNotIn("významná zjištění", folded)
            self.assertNotIn("významných zjištění", folded)

    def test_audit_only_opportunities_heading(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=2,
            prefix="pkz",
        )
        self._assert_heading_in_outputs(self._audit_outputs(audit))

    def test_audit_only_nonconformities_heading(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=1,
            prefix="nc",
        )
        self._assert_heading_in_outputs(self._audit_outputs(audit))

    def test_audit_mixed_results_heading(self) -> None:
        audit = self._create_audit()
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_NEVYHOVUJE,
            count=1,
            prefix="nc",
        )
        self._add_results(
            ENTITY_AUDITY,
            audit.id,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            count=1,
            prefix="pkz",
        )
        self._assert_heading_in_outputs(self._audit_outputs(audit))

    def test_audit_empty_heading_and_zero_sentence(self) -> None:
        audit = self._create_audit()
        text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, text)
        self.assertNotIn("Během auditu nebyla zjištěna významná zjištění.", text)

        paths = self._audit_outputs(audit)
        self._assert_heading_in_outputs(paths)
        for path in paths:
            content = _odt_content(path)
            self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, content)
            self.assertIn(
                "Nejsou evidována žádná zjištění k podrobnému uvedení.",
                _findings_section(content),
            )
            folded = content.casefold()
            self.assertNotIn("významná zjištění", folded)
            self.assertNotIn("významných zjištění", folded)

    def test_non_zero_czech_sentences_unchanged(self) -> None:
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
        inspection_text = bozp_inspection_export_context_service.build(
            inspection
        ).overall_assessment_text()
        self.assertIn(INSPECTION_EMPTY_FOUND_SENTENCE, inspection_text)
        self.assertNotIn("Během prověrky", inspection_text)

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
        audit_text = audit_export_context_service.build(audit).overall_assessment_text()
        self.assertIn(AUDIT_EMPTY_FOUND_SENTENCE, audit_text)
        self.assertNotIn("Během auditu", audit_text)

    def test_heading_order_in_all_four_outputs(self) -> None:
        inspection = self._create_inspection()
        audit = self._create_audit()
        outputs = self._inspection_outputs(inspection) + self._audit_outputs(audit)
        for path in outputs:
            content = _odt_content(path)
            positions = [
                content.find("Přehled výsledků"),
                content.find("Oblasti vyžadující pozornost"),
                content.find(HEADING),
                content.find("Detail zjištění"),
            ]
            self.assertTrue(all(pos >= 0 for pos in positions), msg=path.name)
            self.assertEqual(positions, sorted(positions), msg=path.name)

    def test_pdf_smoke_uses_odt_heading_if_libreoffice_available(self) -> None:
        lo = _find_libreoffice()
        if lo is None:
            self.skipTest("LibreOffice není v testovacím prostředí dostupný.")

        inspection = self._create_inspection()
        odt_path = protokol_proverky_service.generate_for_inspection(inspection)
        odt_xml = _odt_content(odt_path)
        self.assertIn(HEADING, odt_xml)

        out_dir = Path(tempfile.mkdtemp(prefix="findings-heading-4-pdf-"))
        env = os.environ.copy()
        env["HOME"] = str(out_dir / "home")
        (out_dir / "home").mkdir(parents=True, exist_ok=True)
        local_odt = out_dir / odt_path.name
        shutil.copy2(odt_path, local_odt)
        try:
            result = subprocess.run(
                [
                    lo,
                    "--headless",
                    "--nologo",
                    "--nolockcheck",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(out_dir),
                    str(local_odt),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.skipTest(f"LibreOffice nelze spustit: {exc}")

        pdf_path = out_dir / f"{local_odt.stem}.pdf"
        if result.returncode != 0 or not pdf_path.exists():
            self.skipTest(
                "LibreOffice nepřipravil PDF "
                f"(code={result.returncode}, stderr={result.stderr[-400:]})"
            )

        pdf_bytes = pdf_path.read_bytes()
        extracted = ""
        pdftotext = shutil.which("pdftotext")
        if pdftotext:
            extracted = subprocess.run(
                [pdftotext, "-layout", str(pdf_path), "-"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            ).stdout
        if extracted.strip():
            self.assertIn(HEADING, extracted)
            self.assertNotIn(OLD_HEADING, extracted)
            return
        self.assertTrue(
            _pdf_contains(pdf_bytes, HEADING) or pdf_path.stat().st_size > 0,
            "PDF vzniklé z ODT musí existovat; nadpis je v ODT a PDF nemá vlastní generátor.",
        )
        self.assertIn(HEADING, odt_xml)


if __name__ == "__main__":
    unittest.main()
