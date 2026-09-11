"""AUDIT-EXPORT-FIX-1: zápatí exportu Plánu interních auditů."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="audit-export-fix-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
    from moduly.audity.sluzby.audit_program_plan_export_service import (
        audit_program_plan_export_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.zaverecna_zprava_programu_auditu_service import (
        zaverecna_zprava_programu_auditu_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = REPO_ROOT / "moduly" / "audity" / "templates" / "exporty"
PLAN_TEMPLATE = TEMPLATES / "PlanInternichAuditu.odt"
FINAL_TEMPLATE = TEMPLATES / "ZaverecnaZpravaProgramuAuditu.odt"

PLAN_FOOTER_PREFIX = "Plán interních auditů – "
WRONG_FOOTER_PREFIX = "Závěrečná zpráva programu interních auditů"


def _odt_part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read(name).decode("utf-8")


def _odt_plain(xml: str) -> str:
    text = re.sub(r"<text:line-break\s*/>", "\n", xml)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class AuditExportFix1TestCase(unittest.TestCase):

    def _create_program(self, *, name: str):
        workplace = settings_service.save_workplace(name=f"Provoz {name}")
        program = audit_program_service.create_program(
            name=name,
            date_from=date(2026, 1, 1),
            date_to=date(2029, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=12,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=workplace.id,
            planned_year=2026,
            planned_month=3,
        )
        return program

    def _export_plan(self, program_id: int) -> Path:
        target = Path(tempfile.mkdtemp()) / "plan.odt"
        return audit_program_plan_export_service.generate_for_program(program_id, target)

    def test_plan_template_footer_uses_plan_title_and_name_placeholder(self) -> None:
        styles = _odt_part(PLAN_TEMPLATE, "styles.xml")
        self.assertIn("Plán interních auditů – ${program_nazev}", styles)
        self.assertNotIn(WRONG_FOOTER_PREFIX, styles)
        self.assertNotIn(WRONG_FOOTER_PREFIX, _odt_part(PLAN_TEMPLATE, "content.xml"))

    def test_exported_plan_footer_uses_program_name(self) -> None:
        program = self._create_program(name="ZX-ZF 2026 - 2029")
        path = self._export_plan(program.id)
        styles = _odt_plain(_odt_part(path, "styles.xml"))
        content = _odt_plain(_odt_part(path, "content.xml"))
        expected = f"{PLAN_FOOTER_PREFIX}ZX-ZF 2026 - 2029"
        self.assertIn(expected, styles)
        self.assertNotIn(WRONG_FOOTER_PREFIX, styles)
        self.assertNotIn(WRONG_FOOTER_PREFIX, content)
        self.assertIn("Plán interních auditů", content)
        self.assertNotIn("${program_nazev}", styles)

    def test_footer_name_is_taken_from_exported_program(self) -> None:
        first = self._create_program(name="ZX-ZF 2026 - 2029")
        second = self._create_program(name="Jiný plán 2025")
        first_styles = _odt_plain(_odt_part(self._export_plan(first.id), "styles.xml"))
        second_styles = _odt_plain(_odt_part(self._export_plan(second.id), "styles.xml"))
        self.assertIn(f"{PLAN_FOOTER_PREFIX}ZX-ZF 2026 - 2029", first_styles)
        self.assertIn(f"{PLAN_FOOTER_PREFIX}Jiný plán 2025", second_styles)
        self.assertNotIn("Jiný plán 2025", first_styles)
        self.assertNotIn("ZX-ZF 2026 - 2029", second_styles)

    def test_final_report_template_footer_unchanged(self) -> None:
        styles = _odt_part(FINAL_TEMPLATE, "styles.xml")
        self.assertIn(
            "Závěrečná zpráva programu interních auditů – ${program_nazev}",
            styles,
        )
        self.assertEqual(
            zaverecna_zprava_programu_auditu_service.TEMPLATE_NAME,
            "ZaverecnaZpravaProgramuAuditu.odt",
        )


if __name__ == "__main__":
    unittest.main()
