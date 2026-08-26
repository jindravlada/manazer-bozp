"""AUDIT-REPORT-1a – oprava fotografií a formátování podrobné zprávy."""

from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from PIL import Image
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="audit-report-1a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.export.odt_engine import ODT_IMAGE_MARKER_RE, OdtExportEngine
    from core.shared.constants import (
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        FINDING_TYPE_PRILEZITOST,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.services.control_result_photo_service import control_result_photo_service
    from moduly.audity.sluzby.audit_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        PROTOCOL_DOCUMENT_CONFIG,
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _find_libreoffice() -> str | None:
    for candidate in ("soffice", "libreoffice"):
        path = shutil.which(candidate)
        if path:
            return path
    snap = Path("/snap/bin/libreoffice")
    if snap.exists():
        return str(snap)
    return None


class AudityDetailedReportFormattingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Finding))
            session.execute(delete(ControlResult))
            session.commit()
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _create_finished_audit(self):
        workplace = settings_service.save_workplace(name="Provoz Report 1a")
        return audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            year=2026,
            planned_month=7,
            started_at=date(2026, 7, 1),
            finished_at=date(2026, 7, 10),
            notes_mode=None,
        )

    def _set_result(
        self,
        audit_id: int,
        *,
        control_point_id: str,
        label: str,
        result: str,
        note: str = "",
        photo_path: str | None = None,
    ):
        return control_result_service.set_result(
            ENTITY_AUDITY,
            audit_id,
            ControlPointContext(
                area_id="rizeni_rizik",
                area_label="Řízení rizik",
                section_id="sekce",
                section_label="Sekce",
                control_point_id=control_point_id,
                control_point_label=label,
            ),
            result=result,
            note=note,
            photo_path=photo_path,
        )

    def _attach_photo(self, audit_id: int, control_point_id: str, size=(800, 600)):
        relative = control_result_photo_service.relative_photo_path(
            ENTITY_AUDITY,
            audit_id,
            area_id="rizeni_rizik",
            section_id="sekce",
            control_point_id=control_point_id,
        )
        absolute = control_result_photo_service.absolute_photo_path(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, color=(20, 120, 200)).save(absolute, format="JPEG")
        return relative, absolute

    def test_protocol_appendix_b_uses_bold_section_headings(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="t1",
            label="Tvrzení protokol",
            result=CONTROL_RESULT_VYHOVUJE,
            note="Nemá být u tvrzení",
        )
        context = audit_export_context_service.build(
            audit, config=PROTOCOL_DOCUMENT_CONFIG
        )
        appendix = context.appendix_assertions_text()
        from core.export.odt_engine import OdtRichContent

        self.assertIsInstance(appendix, OdtRichContent)
        plain = appendix.plain_text()
        self.assertIn("🟢 Tvrzení protokol", plain)
        self.assertNotIn("Poznámka auditora", plain)

        path = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(path)
        self.assertIn("Tvrzení protokol", content)
        self.assertNotIn('draw:style-name="ExportImage"', content)
        # Nadpisy sekcí v příloze B jsou tučné (AuditCriterion), stejně jako u prověrek.
        appendix_b = content.split("Příloha B", 1)[1]
        self.assertIn('text:style-name="AuditCriterion"', appendix_b)
        self.assertNotIn('text:style-name="AuditNote"', appendix_b)

    def test_photo_odt_structure_styles_manifest_and_aspect_ratio(self) -> None:
        audit = self._create_finished_audit()
        relative, absolute = self._attach_photo(
            audit.id, "photo_cp", size=(1600, 900)
        )
        self._set_result(
            audit.id,
            control_point_id="photo_cp",
            label="Tvrzení s fotkou",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="Poznámka u fotky",
            photo_path=relative,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="PKZ",
            source_control_point_id="photo_cp",
            source_control_point_label="Tvrzení s fotkou",
            recommended_action="Doporučení text",
        )
        self._set_result(
            audit.id,
            control_point_id="no_photo",
            label="Bez fotky",
            result=CONTROL_RESULT_VYHOVUJE,
        )

        detailed = audit_export_context_service.build(
            audit, config=DETAILED_REPORT_DOCUMENT_CONFIG
        ).detailed_appendix_assertions_text()
        assertion_idx = detailed.index("🟡 Tvrzení s fotkou")
        rec_idx = detailed.index("Doporučení:", assertion_idx)
        note_idx = detailed.index("Poznámka auditora:", assertion_idx)
        img_idx = detailed.index("[[[ODT_IMAGE|", assertion_idx)
        self.assertLess(assertion_idx, rec_idx)
        self.assertLess(rec_idx, note_idx)
        self.assertLess(note_idx, img_idx)
        self.assertNotIn("    Poznámka auditora:", detailed)

        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            picture_names = [n for n in names if n.startswith("Pictures/")]
            self.assertTrue(picture_names)
            picture_name = picture_names[0]
            self.assertTrue(picture_name.lower().endswith((".jpg", ".jpeg")))
            self.assertGreater(len(archive.read(picture_name)), 100)

            manifest = archive.read("META-INF/manifest.xml").decode("utf-8")
            self.assertIn(f'manifest:full-path="{picture_name}"', manifest)
            self.assertIn('manifest:media-type="image/jpeg"', manifest)

            content = archive.read("content.xml").decode("utf-8")

        self.assertIn("xmlns:draw=", content)
        self.assertIn("xmlns:xlink=", content)
        self.assertIn(f'xlink:href="{picture_name}"', content)
        self.assertIn("draw:image", content)

        root = ET.fromstring(content.encode("utf-8"))
        frames = root.findall(".//draw:frame", NS)
        self.assertEqual(len(frames), 1)
        frame = frames[0]
        style_name = frame.attrib.get(
            "{urn:oasis:names:tc:opendocument:xmlns:drawing:1.0}style-name"
        )
        self.assertTrue(style_name)
        graphic_styles = {
            style.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name")
            for style in root.findall(".//office:automatic-styles/style:style", NS)
            if style.attrib.get(
                "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}family"
            )
            == "graphic"
        }
        self.assertIn(style_name, graphic_styles)

        parent = None
        for paragraph in root.findall(".//text:p", NS):
            if paragraph.find("draw:frame", NS) is not None:
                parent = paragraph
                break
        self.assertIsNotNone(parent)
        # Fotografie je jediný obsah odstavce (samostatný text:p).
        children = list(parent)
        self.assertEqual(len(children), 1)
        self.assertTrue(children[0].tag.endswith("frame"))

        width = float(frame.attrib["{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}width"].replace("cm", ""))
        height = float(frame.attrib["{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}height"].replace("cm", ""))
        self.assertLessEqual(width, OdtExportEngine._MAX_IMAGE_WIDTH_CM + 0.01)
        self.assertLessEqual(height, OdtExportEngine._MAX_IMAGE_HEIGHT_CM + 0.01)
        self.assertAlmostEqual(width / height, 1600 / 900, places=2)

        # Pořadí v Příloze B: tvrzení → doporučení → poznámka → fotografie
        appendix_b = content.split("Příloha B", 1)[-1]
        assertion_pos = appendix_b.index("Tvrzení s fotkou")
        rec_pos = appendix_b.index("Doporučení:", assertion_pos)
        note_pos = appendix_b.index("Poznámka auditora:", assertion_pos)
        img_pos = appendix_b.index("draw:image", assertion_pos)
        self.assertLess(assertion_pos, rec_pos)
        self.assertLess(rec_pos, note_pos)
        self.assertLess(note_pos, img_pos)
        self.assertLess(appendix_b.index("Bez fotky"), assertion_pos)

        del absolute  # použito jen k vytvoření souboru

    def test_note_uses_paragraph_style_not_spaces(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="with_note",
            label="S poznámkou",
            result=CONTROL_RESULT_VYHOVUJE,
            note="Kontrola na místě",
        )
        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        content = _odt_content(path)

        self.assertIn('text:style-name="AuditNote"', content)
        self.assertIn("Poznámka auditora:", content)
        self.assertIn("Kontrola na místě", content)
        self.assertNotIn("    Poznámka auditora:", content)
        self.assertNotIn(">    Kontrola", content)

        root = ET.fromstring(content.encode("utf-8"))
        note_paras = [
            p
            for p in root.findall(".//text:p", NS)
            if p.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name")
            == "AuditNote"
        ]
        self.assertGreaterEqual(len(note_paras), 2)
        note_style = None
        for style in root.findall(".//office:automatic-styles/style:style", NS):
            if (
                style.attrib.get("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name")
                == "AuditNote"
            ):
                note_style = style
                break
        self.assertIsNotNone(note_style)
        props = note_style.find("style:paragraph-properties", NS)
        self.assertIsNotNone(props)
        margin_left = props.attrib.get(
            "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}margin-left"
        )
        self.assertEqual(margin_left, "0.7cm")

    def test_appendix_a_process_names_are_not_bold(self) -> None:
        audit = self._create_finished_audit()
        # Bez plánovaných procesů builder vezme názvy z control_results.
        self._set_result(
            audit.id,
            control_point_id="t1",
            label="Libovolné tvrzení",
            result=CONTROL_RESULT_VYHOVUJE,
        )
        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        content = _odt_content(path)

        appendix_a = content.split("Příloha A", 1)[1].split("Příloha B", 1)[0]
        self.assertIn("• Řízení rizik", appendix_a)
        self.assertNotIn('text:style-name="AuditBold"', appendix_a)
        self.assertNotIn('fo:font-weight="bold"', appendix_a)

        protocol_path = protokol_audit_service.generate_for_audit(audit)
        protocol_content = _odt_content(protocol_path)
        protocol_a = protocol_content.split("Příloha A", 1)[1].split("Příloha B", 1)[0]
        self.assertNotIn('text:style-name="AuditBold"', protocol_a)
        # Příloha B protokolu: nadpisy sekcí tučně (stejně jako u prověrek).
        self.assertIn('text:style-name="AuditCriterion"', protocol_content)

    def test_detailed_appendix_uses_separate_paragraphs(self) -> None:
        audit = self._create_finished_audit()
        self._set_result(
            audit.id,
            control_point_id="t1",
            label="Oddělené tvrzení",
            result=CONTROL_RESULT_VYHOVUJE,
            note="Oddělená poznámka",
        )
        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        content = _odt_content(path)

        # Příloha B není jeden odstavec s line-break mezi kritériem a tvrzením.
        criterion_match = re.search(
            r'<text:p text:style-name="AuditCriterion">Sekce</text:p>',
            content,
        )
        self.assertIsNotNone(criterion_match)
        after = content[criterion_match.end() :]
        self.assertTrue(
            after.lstrip().startswith("<text:p"),
            "Po kritériu má následovat nový odstavec, ne line-break",
        )
        self.assertIn("Oddělené tvrzení", after.split("</text:p>", 1)[0] + "</text:p>")

    def test_appendix_b_has_no_nested_text_paragraphs(self) -> None:
        """Příloha B musí být sourozenci text:p, nikoli text:p uvnitř text:p."""
        audit = self._create_finished_audit()
        relative, _ = self._attach_photo(audit.id, "nested_check")
        self._set_result(
            audit.id,
            control_point_id="nested_check",
            label="Tvrzení bez vnoření",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="Poznámka bez vnoření",
            photo_path=relative,
        )
        finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_PRILEZITOST,
            description="PKZ",
            source_control_point_id="nested_check",
            source_control_point_label="Tvrzení bez vnoření",
            recommended_action="Doporučení bez vnoření",
        )

        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        content = _odt_content(path)

        # Surowy XML: otevřený text:p nesmí obsahovat další text:p před svým uzavřením.
        nested_raw = re.search(
            r"<text:p\b[^>]*(?<!/)>(?:(?!</text:p>).)*?<text:p\b",
            content,
            re.DOTALL,
        )
        self.assertIsNone(
            nested_raw,
            "content.xml obsahuje vnořené <text:p> (neplatné ODF): "
            + (nested_raw.group(0)[:180] if nested_raw else ""),
        )

        root = ET.fromstring(content.encode("utf-8"))
        for paragraph in root.findall(".//text:p", NS):
            nested = paragraph.findall("text:p", NS)
            self.assertEqual(
                nested,
                [],
                f"Odstavec obsahuje vnořené text:p: {ET.tostring(paragraph, encoding='unicode')[:200]}",
            )

        appendix_b = content.split("Příloha B", 1)[-1]
        for needle in (
            "AuditCriterion",
            "Tvrzení bez vnoření",
            "Doporučení",
            "Poznámka auditora",
            "draw:frame",
        ):
            self.assertIn(needle, appendix_b)

    def test_tall_photo_respects_max_height(self) -> None:
        audit = self._create_finished_audit()
        relative, _ = self._attach_photo(audit.id, "tall", size=(600, 2400))
        self._set_result(
            audit.id,
            control_point_id="tall",
            label="Vysoká fotka",
            result=CONTROL_RESULT_VYHOVUJE,
            photo_path=relative,
        )
        path = protokol_audit_service.generate_detailed_report_for_audit(audit)
        content = _odt_content(path)
        root = ET.fromstring(content.encode("utf-8"))
        frame = root.find(".//draw:frame", NS)
        self.assertIsNotNone(frame)
        width = float(frame.attrib["{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}width"].replace("cm", ""))
        height = float(frame.attrib["{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}height"].replace("cm", ""))
        self.assertLessEqual(height, 15.01)
        self.assertAlmostEqual(width / height, 600 / 2400, places=2)

    def test_pdf_export_contains_embedded_image_if_libreoffice_available(self) -> None:
        lo = _find_libreoffice()
        if lo is None:
            self.skipTest("LibreOffice není v testovacím prostředí dostupný.")

        audit = self._create_finished_audit()
        relative, _ = self._attach_photo(audit.id, "pdf_photo", size=(640, 480))
        self._set_result(
            audit.id,
            control_point_id="pdf_photo",
            label="Foto pro PDF",
            result=CONTROL_RESULT_VYHOVUJE,
            photo_path=relative,
        )
        odt_path = protokol_audit_service.generate_detailed_report_for_audit(audit)

        out_dir = Path(tempfile.mkdtemp(prefix="audit-report-1a-pdf-"))
        env = os.environ.copy()
        env["HOME"] = str(out_dir / "home")
        (out_dir / "home").mkdir(parents=True, exist_ok=True)
        # LibreOffice (snap) často neumí číst přímo z cizího TMP – použij kopii.
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
        # Rasterový obrázek v PDF z LO obvykle jako XObject / DCTDecode (JPEG).
        self.assertTrue(
            b"/Subtype /Image" in pdf_bytes or b"/DCTDecode" in pdf_bytes,
            "PDF neobsahuje vložený rastrový obrázek",
        )


if __name__ == "__main__":
    unittest.main()
