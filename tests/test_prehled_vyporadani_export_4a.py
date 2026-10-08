"""AUDIT-VYPOŘÁDÁNÍ-4a: stručný manažerský export přehledu vypořádání."""

from __future__ import annotations

import html
import importlib
import os
import re
import shutil
import subprocess
import unittest
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database import session as session_module
    from core.shared.constants import (
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_POZOROVANI,
        SETTLEMENT_SOURCE_AUDITY,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_settlement_overview_service import (
        finding_settlement_overview_service,
    )
    from moduly.audity.constants import AUDIT_STATUS_DOKONCENO
    from moduly.audity.modely.audit import Audit
    from moduly.audity.repository.audit_repository import AuditRepository
    from moduly.audity.sluzby.prehled_vyporadani_export_service import (
        EMPTY_SECTION,
        SECTION_NEW,
        SECTION_REOPENED,
        count_with_percent,
        format_audit_reference,
        prehled_vyporadani_export_service,
    )


def _wipe() -> None:
    session_module.reconfigure_database_engine()
    with session_module.engine.begin() as connection:
        connection.execute(text("DELETE FROM finding_settlement_overview_items"))
        connection.execute(text("DELETE FROM finding_settlement_overviews"))
        connection.execute(text("DELETE FROM finding_status_events"))
        connection.execute(text("DELETE FROM findings"))
        connection.execute(text("DELETE FROM tasks"))
        connection.execute(text("DELETE FROM audits"))


def _odt_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _odt_text(path: Path) -> str:
    xml = _odt_xml(path)
    text_value = re.sub(r"<text:line-break\s*/>", "\n", xml)
    text_value = re.sub(r"<[^>]+>", "", text_value)
    return html.unescape(text_value)


def _pdf_page_count(odt_path: Path) -> int:
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        raise AssertionError("LibreOffice není k dispozici pro ověření počtu stran.")
    # Snap LibreOffice nečte skryté adresáře ani soubory mimo domovský adresář.
    work = Path.home() / "manazer-bozp-export-test"
    work.mkdir(parents=True, exist_ok=True)
    try:
        source = work / odt_path.name
        shutil.copy2(odt_path, source)
        completed = subprocess.run(
            [
                soffice,
                "--headless",
                "--norestore",
                "--convert-to",
                "pdf",
                "--outdir",
                str(work),
                str(source),
            ],
            check=False,
            capture_output=True,
            timeout=120,
        )
        pdf_path = work / f"{source.stem}.pdf"
        if completed.returncode != 0 or not pdf_path.exists():
            detail = (completed.stdout or b"").decode("utf-8", errors="replace")[-500:]
            detail += (completed.stderr or b"").decode("utf-8", errors="replace")[-500:]
            raise AssertionError(f"ODT se nepodařilo otevřít v LibreOffice.\n{detail}")
        pages = len(re.findall(rb"/Type\s*/Page(?!s)", pdf_path.read_bytes()))
        if pages <= 0:
            raise AssertionError("PDF přehledu neobsahuje žádnou stranu.")
        return pages
    finally:
        shutil.rmtree(work, ignore_errors=True)


class PrehledVyporadaniExport4aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _wipe()
        self.audits = AuditRepository()
        self.service = finding_settlement_overview_service
        self.export = prehled_vyporadani_export_service

    def test_audit_reference_does_not_repeat_year(self) -> None:
        self.assertEqual(format_audit_reference("3/2026", 2026), "3/2026")
        self.assertEqual(format_audit_reference("2026/3", 2026), "2026/3")
        self.assertEqual(format_audit_reference("3", 2026), "3/2026")
        self.assertEqual(format_audit_reference("IA-3", 2025), "IA-3/2025")
        self.assertEqual(count_with_percent(1, 0), "1")
        self.assertEqual(count_with_percent(0, 0), "0")
        self.assertEqual(count_with_percent(1, 3), "1 (33 %)")

    def test_zero_findings_and_long_text_keep_snapshot(self) -> None:
        empty_audit = self.audits.add(
            Audit(
                number="9/2024",
                year=2024,
                status=AUDIT_STATUS_DOKONCENO,
                workplace_name="Prázdný provoz",
                title="Audit bez zjištění",
            )
        )
        overview = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 10, 8),
        )
        path = self.export.generate(overview.id, output_path=_TMP / "prazdny.odt")
        text_value = _odt_text(path)
        xml = _odt_xml(path)
        self.assertIn("Celkem zjištění: 0", text_value)
        self.assertIn("Vypořádáno: 0", text_value)
        self.assertNotIn("Vypořádáno: 0 (", text_value)
        self.assertIn(EMPTY_SECTION, text_value)
        self.assertNotIn(SECTION_NEW, text_value)
        self.assertNotIn(SECTION_REOPENED, text_value)
        self.assertNotIn("<table:table", xml)
        self.assertNotIn("9/2024/2024", text_value)
        self._assert_odt_valid(path)

        long_text = (
            "Na dopravním školení je potřeba znovu projít zajištění vozů "
            "a uložení záznamu & dokladu <1 m od stanoviště. "
            + ("doplnění " * 30)
        ).strip()
        audit = self.audits.add(
            Audit(
                number="3/2026",
                year=2026,
                status=AUDIT_STATUS_DOKONCENO,
                workplace_name="Provoz Trmice",
                title="Audit 3",
            )
        )
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description=long_text,
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 3, 1),
            source_area_label="Údržba",
            source_section_label="Zábradlí",
            recommended_action="Doplnit zábradlí",
        )
        filled = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 10, 9),
        )
        stored = self.service.items_for(filled.id)
        self.assertEqual(len(stored), 1)
        before = (
            stored[0].description,
            stored[0].process_label,
            stored[0].recommended_action,
            stored[0].audit_number,
            stored[0].audit_year,
        )
        exported = self.export.generate(filled.id, output_path=_TMP / "dlouhy.odt")
        after = self.service.items_for(filled.id)[0]
        self.assertEqual(
            (
                after.description,
                after.process_label,
                after.recommended_action,
                after.audit_number,
                after.audit_year,
            ),
            before,
        )
        text_value = _odt_text(exported)
        self.assertIn(long_text, text_value)
        self.assertIn("3/2026", text_value)
        self.assertNotIn("3/2026/2026", text_value)
        self.assertIn("Provoz Trmice", text_value)
        self.assertNotIn("Řídicí proces:", text_value)
        self.assertNotIn("Doporučené opatření:", text_value)
        self.assertIn(SECTION_NEW, text_value)
        self.assertIn(EMPTY_SECTION, text_value)
        finding_service.update(finding.id, description="Živá úprava po exportu")
        repeated = _odt_text(
            self.export.generate(filled.id, output_path=_TMP / "dlouhy-znovu.odt")
        )
        self.assertIn(long_text, repeated)
        self.assertNotIn("Živá úprava po exportu", repeated)
        self.assertEqual(
            self.service.items_for(filled.id)[0].description,
            long_text,
        )
        self._assert_odt_valid(exported)
        self.assertIsNotNone(empty_audit.id)

    def test_eight_findings_fit_one_a4_page(self) -> None:
        samples = (
            (
                "2/2026",
                2026,
                "Provoz Hodonín",
                FINDING_STATUS_V_PROCESU,
                "Záznamy z kontrol BOZP a PO jsou uloženy jen u zaměstnanců provozu a bez nich je nelze zpětně doložit.",
            ),
            (
                "3/2026",
                2026,
                "Provoz Trmice",
                FINDING_STATUS_VYPORADANO,
                "Politika BOZP a QMS není zaměstnancům přímo dostupná.",
            ),
            (
                "3/2026",
                2026,
                "Provoz Trmice",
                FINDING_STATUS_VYPORADANO,
                "Plán svolávání vyvěšený na provoze není aktuální.",
            ),
            (
                "3/2026",
                2026,
                "Provoz Trmice",
                FINDING_STATUS_VYPORADANO,
                "Není možné zpětně doložit provádění kontrol a jejich četnost.",
            ),
            (
                "4/2026",
                2026,
                "Provoz Ledvice",
                FINDING_STATUS_V_PROCESU,
                "Na dopravním školení zdůraznit postup zajištění vozů na důlní vlečce.",
            ),
            (
                "4/2026",
                2026,
                "Provoz Ledvice",
                FINDING_STATUS_VYPORADANO,
                "Nastavený systém hodnocení dodavatelů není vždy využíván.",
            ),
            (
                "4/2026",
                2026,
                "Provoz Ledvice",
                FINDING_STATUS_VYPORADANO,
                "Zavést sledování realizace opatření po pracovním úrazu a mimořádné události.",
            ),
            (
                "5",
                2024,
                "Správa",
                FINDING_STATUS_OTEVRENE,
                "Výsledky ověření účinnosti opatření nejsou dokumentovány.",
            ),
        )
        self.assertEqual(len(samples), 8)
        for number, year, workplace, status, description in samples:
            self.assertGreaterEqual(len(description), 45)
            self.assertLessEqual(len(description), 160)
            audit = self.audits.add(
                Audit(
                    number=number,
                    year=year,
                    status=AUDIT_STATUS_DOKONCENO,
                    workplace_name=workplace,
                    title=f"Audit {number}",
                )
            )
            resolved = date(2026, 4, 2) if status == FINDING_STATUS_VYPORADANO else None
            finding_service.create(
                ENTITY_AUDITY,
                audit.id,
                finding_type=(
                    FINDING_TYPE_POZOROVANI
                    if status == FINDING_STATUS_OTEVRENE
                    else FINDING_TYPE_NESHODA
                ),
                description=description,
                status=status,
                resolved_at=resolved,
                source_area_label="Řízení provozu",
                source_section_label="Dokumentace",
                recommended_action="Doplnit evidenci",
            )
        overview = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 10, 8),
        )
        self.assertEqual(overview.total_count, 8)
        self.assertEqual(overview.settled_count, 5)
        self.assertEqual(overview.in_process_count, 2)
        self.assertEqual(overview.open_count, 1)
        path = self.export.generate(overview.id, output_path=_TMP / "osmi.odt")
        text_value = _odt_text(path)
        self.assertIn("Stav k: 08.10.2026", text_value)
        self.assertIn("Celkem zjištění: 8", text_value)
        self.assertIn("Vypořádáno: 5 (63 %)", text_value)
        self.assertIn("V procesu: 2 (25 %)", text_value)
        self.assertIn("Otevřeno: 1 (13 %)", text_value)
        self.assertIn("Neshoda: 7, Pozorování: 1", text_value)
        self.assertIn("3/2026", text_value)
        self.assertNotIn("3/2026/2026", text_value)
        self.assertIn("5/2024", text_value)
        self.assertIn("Otevřené", text_value)
        self.assertIn("V procesu", text_value)
        self.assertNotIn(SECTION_NEW, text_value)
        self._assert_odt_valid(path)
        self.assertEqual(_pdf_page_count(path), 1)

    def _assert_odt_valid(self, path: Path) -> None:
        self.assertTrue(zipfile.is_zipfile(path))
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            self.assertIn("content.xml", names)
            self.assertIn("styles.xml", names)
            self.assertIn("META-INF/manifest.xml", names)
            content = archive.read("content.xml")
            styles = archive.read("styles.xml").decode("utf-8")
        ET.fromstring(content)
        ET.fromstring(styles.encode("utf-8"))
        self.assertIn('fo:page-width="21.001cm"', styles)
        self.assertIn('fo:page-height="29.7cm"', styles)
        self.assertIn('style:print-orientation="portrait"', styles)
        self.assertIn("Přehled vypořádání zjištění z interních auditů", styles)
