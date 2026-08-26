"""INSPECTION-REPORT-2 – podrobná zpráva z prověrky BOZP."""

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

from PIL import Image

_TMP = Path(tempfile.mkdtemp(prefix="inspection-report-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.export.control_point_appendix import (
        ControlPointAppendixItem,
        build_detailed_control_points_appendix,
    )
    from core.export.odt_engine import ODT_IMAGE_MARKER_RE
    from core.services.control_result_photo_service import control_result_photo_service
    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_PROVERKY,
    )
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        INSPECTION_DETAILED_REPORT_BUTTON_LABEL,
        INSPECTION_PROTOCOL_BUTTON_LABEL,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        DETAILED_REPORT_DOCUMENT_CONFIG,
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service
    from moduly.proverky.ui.bozp_inspection_conclusion_widget import (
        BozpInspectionConclusionWidget,
    )


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _ensure_templates() -> None:
    import moduly.proverky.sluzby.protokol_proverky_service as protokol_module

    importlib.reload(protokol_module)
    bundled_root = (
        Path(__file__).resolve().parents[1]
        / "moduly"
        / "proverky"
        / "templates"
        / "exporty"
    )
    for name in ("ProtokolProverkyBOZP.odt", "PodrobnaZpravaProverky.odt"):
        path = protokol_module.protokol_proverky_service.template_path(
            detailed=name.startswith("Podrobna")
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        bundled = bundled_root / name
        if bundled.exists():
            shutil.copy2(bundled, path)


class InspectionReport2TestCase(unittest.TestCase):
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
        _ensure_templates()

    def _create_inspection(self, **fields):
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        member_id = settings_service.save_worker(first_name="Petr", last_name="Svoboda").id
        invited_id = person_service.create_person(first_name="Host", last_name="Hostovič").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        workplace = settings_service.save_workplace(name="Hala Detail")
        payload = {
            "workplace_id": workplace.id,
            "workplace_name": workplace.name,
            "title": "Prověrka Hala Detail 2026",
            "year": 2026,
            "planned_month": 7,
            "started_at": date(2026, 7, 1),
            "finished_at": date(2026, 7, 5),
            "inspection_type": "Řádná",
            "notes_mode": None,
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

    def _set_result(
        self,
        inspection_id: int,
        *,
        control_point_id: str,
        label: str,
        result: str,
        note: str = "",
        area_label: str = "BOZP",
        photo_path: str | None = None,
    ):
        return control_result_service.set_result(
            ENTITY_PROVERKY,
            inspection_id,
            ControlPointContext(
                area_id="bozp",
                area_label=area_label,
                section_id="sekce",
                section_label="Sekce",
                control_point_id=control_point_id,
                control_point_label=label,
            ),
            result=result,
            note=note,
            photo_path=photo_path,
        )

    def _make_photo(self, inspection_id: int, control_point_id: str, color=(20, 120, 200)):
        relative = control_result_photo_service.relative_photo_path(
            ENTITY_PROVERKY,
            inspection_id,
            area_id="bozp",
            section_id="sekce",
            control_point_id=control_point_id,
        )
        absolute = control_result_photo_service.absolute_photo_path(relative)
        absolute.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (100, 60), color=color).save(absolute, format="JPEG")
        return relative, absolute

    def test_conclusion_widget_has_detailed_report_button(self) -> None:
        widget = BozpInspectionConclusionWidget()
        self.assertEqual(widget.protocol_btn.text(), INSPECTION_PROTOCOL_BUTTON_LABEL)
        self.assertEqual(
            widget.detailed_report_btn.text(), INSPECTION_DETAILED_REPORT_BUTTON_LABEL
        )

    def test_detailed_report_template_resolves(self) -> None:
        path = protokol_proverky_service.template_path(detailed=True)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "PodrobnaZpravaProverky.odt")

    def test_generate_detailed_report_creates_odt(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        self.assertTrue(path.exists())
        self.assertEqual(path.suffix.lower(), ".odt")
        self.assertIn("PodrobnaZpravaProverky", path.name)

    def test_detailed_report_basic_info_and_title(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        content = _odt_content(path)

        self.assertIn("PODROBNÁ ZPRÁVA Z PROVĚRKY BOZP", content)
        # Název záznamu se do šablony nevkládá (jen číslo / provoz / data).
        self.assertIn(inspection.number, content)
        self.assertIn("Hala Detail", content)
        self.assertIn("01.07.2026", content)
        self.assertIn("05.07.2026", content)
        self.assertIn("Jan Novák", content)
        self.assertNotIn("Podpisy", content)

    def test_detailed_report_full_commission(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        content = _odt_content(path)
        for expected in (
            "Vedoucí prověrky",
            "Zástupce provozu",
            "Zástupce odborové organizace",
            "Členové komise",
            "Přizvané osoby",
            "Jan Novák",
            "Eva Králová",
            "Lucie Horáková",
            "Petr Svoboda",
            "Host Hostovič",
        ):
            self.assertIn(expected, content)

    def test_detailed_report_uses_zavada_not_neshoda(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        self._set_result(
            inspection.id,
            control_point_id="bad",
            label="Chybí označení",
            result=CONTROL_RESULT_NEVYHOVUJE,
        )
        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        content = _odt_content(path)
        self.assertIn("Závada", content)
        self.assertNotIn("neshoda", content.casefold())
        self.assertIn("Významná zjištění", content)
        self.assertNotIn("Přehled zjištění", content)

    def test_appendix_a_and_b_in_detailed_report(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        self._set_result(
            inspection.id,
            control_point_id="a1",
            label="Hasicí přístroje",
            result=CONTROL_RESULT_VYHOVUJE,
            area_label="Požární ochrana",
        )
        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        content = _odt_content(path)
        self.assertIn("Příloha A – Kontrolované oblasti", content)
        self.assertIn("Příloha B – Kontrolní body", content)
        self.assertIn("Požární ochrana", content)
        self.assertIn("Hasicí přístroje", content)
        self.assertIn("fo:break-before", content)

    def test_appendix_b_colored_results(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        samples = [
            ("ok", "Vyhovuje bod", CONTROL_RESULT_VYHOVUJE, "🟢", "Vyhovuje"),
            (
                "rec",
                "Doporučení bod",
                CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
                "🟡",
                "Vyhovuje s doporučením",
            ),
            ("bad", "Nevyhovuje bod", CONTROL_RESULT_NEVYHOVUJE, "🔴", "Nevyhovuje"),
            ("na", "Nehodnoceno bod", CONTROL_RESULT_NEKONTROLOVANO, "○", "Nehodnoceno"),
        ]
        for cp_id, label, result, _emoji, _word in samples:
            self._set_result(
                inspection.id,
                control_point_id=cp_id,
                label=label,
                result=result,
                note=f"Poznámka {cp_id}",
            )

        context = bozp_inspection_export_context_service.build(
            inspection, config=DETAILED_REPORT_DOCUMENT_CONFIG
        )
        plain = context.appendix_control_points_text().plain_text()
        for _cp_id, label, _result, emoji, word in samples:
            self.assertIn(f"{emoji} {label} — {word}", plain)

        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        content = _odt_content(path)
        self.assertIn("🟢", content)
        self.assertIn("🟡", content)
        self.assertIn("🔴", content)
        self.assertIn("Nehodnoceno", content)
        self.assertIn("Komentář:", content)

    def test_export_without_photos(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        self._set_result(
            inspection.id,
            control_point_id="no_photo",
            label="Bez fotografie",
            result=CONTROL_RESULT_VYHOVUJE,
            note="Jen text",
        )
        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        with zipfile.ZipFile(path, "r") as archive:
            picture_names = [n for n in archive.namelist() if n.startswith("Pictures/")]
        self.assertEqual(picture_names, [])
        content = _odt_content(path)
        self.assertIn("Bez fotografie", content)
        self.assertIn("Jen text", content)

    def test_export_with_multiple_photos(self) -> None:
        inspection = self._create_inspection()
        assert inspection is not None

        rel1, abs1 = self._make_photo(inspection.id, "photo1", color=(200, 20, 20))
        rel2, abs2 = self._make_photo(inspection.id, "photo2", color=(20, 20, 200))
        self._set_result(
            inspection.id,
            control_point_id="photo1",
            label="První foto bod",
            result=CONTROL_RESULT_NEVYHOVUJE,
            note="Komentář 1",
            photo_path=rel1,
        )
        self._set_result(
            inspection.id,
            control_point_id="photo2",
            label="Druhý foto bod",
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            note="Komentář 2",
            photo_path=rel2,
        )

        # Více fotografií u jednoho bodu – sdílený builder.
        multi = build_detailed_control_points_appendix(
            [
                ControlPointAppendixItem(
                    area_label="BOZP",
                    control_point_label="Bod se dvěma fotkami",
                    result=CONTROL_RESULT_NEVYHOVUJE,
                    note="Dvě fotografie",
                    photo_paths=(abs1, abs2),
                )
            ]
        ).plain_text()
        self.assertEqual(len(ODT_IMAGE_MARKER_RE.findall(multi)), 2)

        path = protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        with zipfile.ZipFile(path, "r") as archive:
            picture_names = [n for n in archive.namelist() if n.startswith("Pictures/")]
        self.assertGreaterEqual(len(picture_names), 2)
        content = _odt_content(path)
        self.assertIn("První foto bod", content)
        self.assertIn("Druhý foto bod", content)
        self.assertIn("draw:frame", content)

    @patch(
        "moduly.proverky.ui.bozp_inspection_conclusion_widget.protokol_proverky_service.open_detailed_report_for_inspection"
    )
    @patch("moduly.proverky.ui.bozp_inspection_conclusion_widget.QMessageBox.warning")
    def test_ui_exports_detailed_report(self, mock_warning, mock_open) -> None:
        inspection = self._create_inspection()
        assert inspection is not None
        widget = BozpInspectionConclusionWidget()
        widget.load_inspection(inspection)
        widget._export_detailed_report()
        mock_warning.assert_not_called()
        mock_open.assert_called_once_with(inspection)


if __name__ == "__main__":
    unittest.main()
