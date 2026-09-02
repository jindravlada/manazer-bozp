"""CONTROL-REPORT-STRENGTHS-HEADING-6: neutrální nadpis silných stránek."""

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

_TMP = Path(tempfile.mkdtemp(prefix="control-report-strengths-heading-6-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import AUDIT_STRENGTHS_EXPORT_SECTION
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import INSPECTION_STRENGTHS_EXPORT_SECTION
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


REPO_ROOT = Path(__file__).resolve().parents[1]
HEADING = "Silné stránky"
OLD_HEADING = "Silné stránky systému"
PLACEHOLDER = "${silne_stranky_text}"
HEADING_XML = f'<text:p text:style-name="H">{HEADING}</text:p>'
USER_LINE = "Stabilní dokumentace BOZP bez úprav textu."

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


class ControlReportStrengthsHeading6TestCase(unittest.TestCase):
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

    def _create_inspection(self, **fields):
        workplace = settings_service.save_workplace(name="Poříčí")
        return bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=1,
            started_at=date(2026, 1, 10),
            finished_at=date(2026, 1, 12),
            notes_mode=None,
            **fields,
        )

    def _create_audit(self, **fields):
        workplace = settings_service.save_workplace(name="Provoz Audit")
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=2,
            started_at=date(2026, 2, 1),
            finished_at=date(2026, 2, 3),
            notes_mode=None,
            **fields,
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

    def test_export_constants_are_canonical_heading(self) -> None:
        self.assertEqual(HEADING, INSPECTION_STRENGTHS_EXPORT_SECTION)
        self.assertEqual(HEADING, AUDIT_STRENGTHS_EXPORT_SECTION)

    def test_templates_keep_placeholder_without_hardcoded_heading(self) -> None:
        for path in _INSPECTION_TEMPLATES + _AUDIT_TEMPLATES:
            xml = _odt_content(path)
            self.assertIn(PLACEHOLDER, xml, msg=path.name)
            self.assertNotIn(OLD_HEADING, xml, msg=path.name)
            self.assertNotIn(f">{HEADING}</text:p>", xml, msg=path.name)

    def test_yearly_reports_keep_system_heading(self) -> None:
        for path in _YEARLY_TEMPLATES:
            xml = _odt_content(path)
            self.assertIn(OLD_HEADING, xml, msg=path.name)

    def test_inspection_filled_heading_and_user_text(self) -> None:
        inspection = self._create_inspection(silne_stranky=USER_LINE)
        for path in self._inspection_outputs(inspection):
            content = _odt_content(path)
            self.assertIn(HEADING_XML, content, msg=path.name)
            self.assertIn(USER_LINE, content, msg=path.name)
            self.assertNotIn(OLD_HEADING, content, msg=path.name)
            positions = [
                content.find("Přehled výsledků"),
                content.find(HEADING),
                content.find("Oblasti vyžadující pozornost"),
            ]
            self.assertTrue(all(pos >= 0 for pos in positions), msg=path.name)
            self.assertEqual(positions, sorted(positions), msg=path.name)

    def test_audit_filled_heading_and_user_text(self) -> None:
        audit = self._create_audit(silne_stranky=USER_LINE)
        for path in self._audit_outputs(audit):
            content = _odt_content(path)
            self.assertIn(HEADING_XML, content, msg=path.name)
            self.assertIn(USER_LINE, content, msg=path.name)
            self.assertNotIn(OLD_HEADING, content, msg=path.name)
            positions = [
                content.find("Přehled výsledků"),
                content.find(HEADING),
                content.find("Oblasti vyžadující pozornost"),
            ]
            self.assertTrue(all(pos >= 0 for pos in positions), msg=path.name)
            self.assertEqual(positions, sorted(positions), msg=path.name)

    def test_empty_strengths_omit_section(self) -> None:
        inspection = self._create_inspection(silne_stranky="  \n  ")
        audit = self._create_audit(silne_stranky="")
        paths = self._inspection_outputs(inspection) + self._audit_outputs(audit)
        for path in paths:
            content = _odt_content(path)
            self.assertNotIn(HEADING_XML, content, msg=path.name)
            self.assertNotIn(OLD_HEADING, content, msg=path.name)
            self.assertIn("Přehled výsledků", content, msg=path.name)
            self.assertIn("Oblasti vyžadující pozornost", content, msg=path.name)

    def test_pdf_smoke_uses_odt_heading_if_libreoffice_available(self) -> None:
        lo = _find_libreoffice()
        if lo is None:
            self.skipTest("LibreOffice není v testovacím prostředí dostupný.")

        inspection = self._create_inspection(silne_stranky=USER_LINE)
        odt_path = protokol_proverky_service.generate_for_inspection(inspection)
        self.assertIn(HEADING, _odt_content(odt_path))
        self.assertNotIn(OLD_HEADING, _odt_content(odt_path))

        out_dir = Path(tempfile.mkdtemp(prefix="strengths-heading-6-pdf-"))
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
        self.assertGreater(pdf_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
