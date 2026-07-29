"""INSPECTION-REPORT-1 – sjednocení protokolu prověrky s protokolem auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PIL import Image

_TMP = Path(tempfile.mkdtemp(prefix="inspection-report-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.export.odt_engine import ODT_IMAGE_MARKER_RE
    from core.services.control_result_photo_service import control_result_photo_service
    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
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
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _ensure_proverky_protocol_template() -> Path:
    import shutil

    import moduly.proverky.sluzby.protokol_proverky_service as protokol_module

    importlib.reload(protokol_module)
    path = protokol_module.protokol_proverky_service.template_path()
    bundled = (
        Path(__file__).resolve().parents[1]
        / "moduly"
        / "proverky"
        / "templates"
        / "exporty"
        / "ProtokolProverkyBOZP.odt"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    if bundled.exists():
        shutil.copy2(bundled, path)
    return path


class InspectionReport1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
            nace="62.01",
        )
        _ensure_proverky_protocol_template()

    def _create_full_commission_inspection(self, **fields):
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        member_id = settings_service.save_worker(first_name="Petr", last_name="Svoboda").id
        invited_id = person_service.create_person(first_name="Host", last_name="Hostovič").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        workplace = settings_service.save_workplace(name="Hala Montáž")
        payload = {
            "workplace_id": workplace.id,
            "workplace_name": workplace.name,
            "year": 2026,
            "planned_month": 6,
            "started_at": date(2026, 6, 1),
            "finished_at": date(2026, 6, 3),
            "inspection_type": "Řádná",
        }
        payload.update(fields)
        inspection = bozp_inspection_service.create_inspection(**payload)
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": workplace_id,
                    "display_name": "Eva Králová",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": "prizvana_osoba",
                    "person_id": invited_id,
                    "display_name": "Host Hostovič",
                    "display_order": 40,
                    "active": True,
                },
            ],
        )
        return bozp_inspection_service.get_by_id(inspection.id)

    def test_basic_info_uses_workplace_as_controlled_operation(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertIn("Kontrolovaný provoz", content)
        self.assertIn("Hala Montáž", content)
        self.assertNotIn("Kontrolované pracoviště", content)
        # Zaměstnavatel už není v řádku provozu.
        context = bozp_inspection_export_context_service.build(inspection)
        self.assertEqual(context.controlled_operation_label(), "Hala Montáž")

    def test_start_and_end_dates_in_output(self) -> None:
        inspection = self._create_full_commission_inspection(
            started_at=date(2026, 6, 1),
            finished_at=date(2026, 6, 3),
        )
        assert inspection is not None
        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        self.assertIn("Datum zahájení prověrky", content)
        self.assertIn("Datum ukončení prověrky", content)
        self.assertIn("01.06.2026", content)
        self.assertIn("03.06.2026", content)
        stripped = content.replace("Datum zahájení prověrky", "").replace(
            "Datum ukončení prověrky", ""
        )
        self.assertNotIn("Datum prověrky", stripped)

    def test_unfinished_end_date_label(self) -> None:
        inspection = self._create_full_commission_inspection(finished_at=None)
        assert inspection is not None
        context = bozp_inspection_export_context_service.build(inspection)
        self.assertEqual(context.inspection_end_date_text(), "Dosud neukončena")

    def test_full_commission_listing(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)

        for expected in (
            "Vedoucí prověrky",
            "Jan Novák",
            "Zástupce provozu",
            "Eva Králová",
            "Zástupce odborové organizace",
            "Lucie Horáková",
            "Členové komise",
            "Petr Svoboda",
            "Přizvané osoby",
            "Host Hostovič",
        ):
            self.assertIn(expected, content)

    def test_empty_commission_sections_omitted(self) -> None:
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Jen povinní",
            started_at=date(2026, 6, 1),
            finished_at=date(2026, 6, 2),
        )
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": workplace_id,
                    "display_name": "Eva Králová",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        context = bozp_inspection_export_context_service.build(loaded)
        text = context.commission_text()
        self.assertIn("Vedoucí prověrky", text)
        self.assertIn("Zástupce provozu", text)
        self.assertIn("Zástupce odborové organizace", text)
        self.assertNotIn("Členové komise", text)
        self.assertNotIn("Přizvané osoby", text)

    def test_reference_removed_from_findings_detail(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Chybí ochranné prvky",
            source_area_label="BOZP",
            source_section_label="Sekce",
            source_control_point_label="Bod A",
            reference_label="REF-SAME-AS-BOD",
            status=FINDING_STATUS_OTEVRENE,
        )
        context = bozp_inspection_export_context_service.build(inspection)
        detail = context.findings_detail_text()
        self.assertIn("Kontrolní bod", detail)
        self.assertIn("Bod A", detail)
        self.assertNotIn("Reference", detail)
        self.assertNotIn("REF-SAME-AS-BOD", detail)

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)
        self.assertIn("Bod A", content)
        self.assertNotIn("Reference", content)

    def test_zavada_instead_of_neshoda(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="cp_bad",
                control_point_label="Chybí označení.",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        context = bozp_inspection_export_context_service.build(inspection)
        text = context.overall_assessment_text()
        self.assertIn("závada", text.casefold())
        self.assertNotIn("neshoda", text.casefold())
        self.assertNotIn("neshody", text.casefold())

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)
        self.assertNotIn("neshoda", content.casefold())
        self.assertNotIn("neshody", content.casefold())

    def test_appendix_a_controlled_areas(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="a1",
                area_label="Požární ochrana",
                section_id="s1",
                section_label="Sekce",
                control_point_id="cp1",
                control_point_label="Hasicí přístroje",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )
        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="a2",
                area_label="Ergonomie",
                section_id="s2",
                section_label="Sekce",
                control_point_id="cp2",
                control_point_label="Pracovní polohy",
            ),
            result=CONTROL_RESULT_VYHOVUJE,
        )

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)
        self.assertIn("Příloha A – Kontrolované oblasti", content)
        self.assertIn("Požární ochrana", content)
        self.assertIn("Ergonomie", content)
        self.assertIn("fo:break-before", content)
        # Příloha A: netučné odrážky (stejně jako protokol auditu).
        appendix_a = content.split("Příloha A", 1)[1].split("Příloha B", 1)[0]
        self.assertNotIn('text:style-name="AuditBold"', appendix_a)
        self.assertNotIn('fo:font-weight="bold"', appendix_a)

    def test_appendix_b_colored_results_and_comment(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        samples = [
            ("cp_ok", "Bod vyhovuje", CONTROL_RESULT_VYHOVUJE, "🟢", "Vyhovuje"),
            (
                "cp_rec",
                "Bod s doporučením",
                CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                "🟡",
                "Vyhovuje s doporučením",
            ),
            ("cp_bad", "Bod nevyhovuje", CONTROL_RESULT_NEVYHOVUJE, "🔴", "Nevyhovuje"),
            (
                "cp_na",
                "Bod nehodnocen",
                CONTROL_RESULT_NEKONTROLOVANO,
                "○",
                "Nehodnoceno",
            ),
        ]
        for cp_id, label, result, _emoji, _word in samples:
            control_result_service.set_result(
                ENTITY_PROVERKY,
                inspection.id,
                ControlPointContext(
                    area_id="bozp",
                    area_label="BOZP oblast",
                    section_id="sekce",
                    section_label="Sekce",
                    control_point_id=cp_id,
                    control_point_label=label,
                ),
                result=result,
                note=f"Komentář k {cp_id}",
            )

        context = bozp_inspection_export_context_service.build(inspection)
        appendix = context.appendix_control_points_text().plain_text()
        self.assertIn("BOZP oblast", appendix)
        for _cp_id, label, _result, emoji, _word in samples:
            self.assertIn(f"{emoji} {label}", appendix)
            self.assertNotIn(f"Komentář k {_cp_id}", appendix)
        self.assertNotIn("Komentář:", appendix)
        self.assertNotIn(" — Vyhovuje", appendix)

        path = protokol_proverky_service.generate_for_inspection(inspection)
        content = _odt_content(path)
        appendix_b = content.split("Příloha B", 1)[1]
        self.assertIn("Příloha B – Kontrolní body", content)
        self.assertIn("🟢", appendix_b)
        self.assertIn("🟡", appendix_b)
        self.assertIn("🔴", appendix_b)
        self.assertIn("Bod nehodnocen", appendix_b)
        self.assertNotIn("Komentář:", appendix_b)
        self.assertNotIn("draw:frame", appendix_b)

    def test_appendix_b_includes_photo(self) -> None:
        inspection = self._create_full_commission_inspection()
        assert inspection is not None
        relative = control_result_photo_service.relative_photo_path(
            ENTITY_PROVERKY,
            inspection.id,
            area_id="bozp",
            section_id="sekce",
            control_point_id="photo_cp",
        )
        absolute = control_result_photo_service.absolute_photo_path(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (120, 80), color=(20, 120, 200)).save(absolute, format="JPEG")

        control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection.id,
            ControlPointContext(
                area_id="bozp",
                area_label="BOZP",
                section_id="sekce",
                section_label="Sekce",
                control_point_id="photo_cp",
                control_point_label="Bod s fotografií",
            ),
            result=CONTROL_RESULT_NEVYHOVUJE,
            note="Viz foto",
            photo_path=relative,
        )

        # Protokol: bez fotografií a komentářů.
        protocol_context = bozp_inspection_export_context_service.build(inspection)
        protocol_plain = protocol_context.appendix_control_points_text().plain_text()
        self.assertIn("Bod s fotografií", protocol_plain)
        self.assertFalse(ODT_IMAGE_MARKER_RE.search(protocol_plain))
        self.assertNotIn("Viz foto", protocol_plain)
        self.assertNotIn("Komentář:", protocol_plain)

        protocol_path = protokol_proverky_service.generate_for_inspection(inspection)
        with zipfile.ZipFile(protocol_path, "r") as archive:
            protocol_names = archive.namelist()
        self.assertFalse(any(name.startswith("Pictures/") for name in protocol_names))
        protocol_content = _odt_content(protocol_path)
        protocol_appendix_b = protocol_content.split("Příloha B", 1)[1]
        self.assertIn("Bod s fotografií", protocol_appendix_b)
        self.assertNotIn("draw:frame", protocol_appendix_b)
        self.assertNotIn("Komentář:", protocol_appendix_b)

        # Podrobná zpráva: fotografie a komentáře zůstávají.
        from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
            DETAILED_REPORT_DOCUMENT_CONFIG,
        )

        detailed_context = bozp_inspection_export_context_service.build(
            inspection, config=DETAILED_REPORT_DOCUMENT_CONFIG
        )
        detailed_plain = detailed_context.appendix_control_points_text().plain_text()
        self.assertTrue(ODT_IMAGE_MARKER_RE.search(detailed_plain))
        self.assertIn("Viz foto", detailed_plain)

        detailed_path = (
            protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        )
        with zipfile.ZipFile(detailed_path, "r") as archive:
            detailed_names = archive.namelist()
        self.assertTrue(any(name.startswith("Pictures/") for name in detailed_names))
        detailed_content = _odt_content(detailed_path)
        self.assertIn("Bod s fotografií", detailed_content)
        self.assertIn("draw:frame", detailed_content)
        self.assertIn("Komentář:", detailed_content)


if __name__ == "__main__":
    unittest.main()
