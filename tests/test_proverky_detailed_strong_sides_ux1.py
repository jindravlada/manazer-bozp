"""PROVERKY-DETAILED-STRONG-SIDES-UX1: skrýt prázdné Silné stránky v ODT."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="proverky-strong-sides-ux1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import (
        AUDIT_STRENGTHS_EXPORT_SECTION,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import INSPECTION_STRENGTHS_EXPORT_SECTION
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service

REPO_ROOT = Path(__file__).resolve().parents[1]
_EMPTY_PLACEHOLDER = "—"


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _region(content: str) -> str:
    return content.split("Přehled výsledků", 1)[1].split(
        "Oblasti vyžadující pozornost", 1
    )[0]


def _sync_templates() -> None:
    import moduly.proverky.sluzby.protokol_proverky_service as inspection_module
    import moduly.audity.sluzby.protokol_audit_service as audit_module

    importlib.reload(inspection_module)
    importlib.reload(audit_module)
    for name, detailed in (
        ("ProtokolProverkyBOZP.odt", False),
        ("PodrobnaZpravaProverky.odt", True),
    ):
        bundled = REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / name
        target = inspection_module.protokol_proverky_service.template_path(
            detailed=detailed
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)
    for name, detailed in (
        ("ProtokolAudit.odt", False),
        ("PodrobnaZpravaAudit.odt", True),
    ):
        bundled = REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / name
        target = audit_module.protokol_audit_service.template_path(detailed=detailed)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)


class ProverkyDetailedStrongSidesUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_templates()

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
        )
        suffix = uuid.uuid4().hex[:6]
        self.leader = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        )
        self.workplace_rep = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        )
        self.union = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        )
        self.workplace = settings_service.save_workplace(name=f"Provoz-{suffix}")

    def _save_inspection_commission(self, inspection_id: int) -> None:
        bozp_inspection_commission_service.save_members(
            inspection_id,
            [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": self.leader.id,
                    "display_name": "Jan L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": self.workplace_rep.id,
                    "display_name": "Eva W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": self.union.id,
                    "display_name": "Lucie U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )

    def _create_inspection(self, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
            "started_at": date(2026, 8, 1),
            "finished_at": date(2026, 8, 2),
            "title": "Prověrka silné stránky",
        }
        payload.update(fields)
        inspection = bozp_inspection_service.create_inspection(**payload)
        self._save_inspection_commission(inspection.id)
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        return loaded

    def _create_audit(self, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
            "started_at": date(2026, 8, 1),
            "title": "Audit silné stránky",
        }
        payload.update(fields)
        audit = audit_service.create_audit(**payload)
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader.id,
                    "display_name": "Jan L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep.id,
                    "display_name": "Eva W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union.id,
                    "display_name": "Lucie U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return audit

    def _assert_strengths_omitted(self, content: str) -> None:
        self.assertNotIn(INSPECTION_STRENGTHS_EXPORT_SECTION, content)
        region = _region(content)
        self.assertNotIn(_EMPTY_PLACEHOLDER, region)
        self.assertNotIn('<text:p text:style-name="Standard"/>', region)
        self.assertNotIn('fo:break-before="page"', region)
        self.assertNotIn("<table:table", region)

    def _assert_strengths_present(self, content: str, *items: str) -> None:
        self.assertIn(INSPECTION_STRENGTHS_EXPORT_SECTION, content)
        for item in items:
            self.assertIn(f"✔ {item}", content)
        heading_pos = content.find(INSPECTION_STRENGTHS_EXPORT_SECTION)
        first_item_pos = content.find(f"✔ {items[0]}")
        self.assertLess(heading_pos, first_item_pos)
        for previous, current in zip(items, items[1:]):
            self.assertLess(
                content.find(f"✔ {previous}"),
                content.find(f"✔ {current}"),
            )

    def test_detailed_empty_default_omits_section(self) -> None:
        inspection = self._create_inspection()
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_omitted(content)

    def test_detailed_none_omits_section(self) -> None:
        inspection = self._create_inspection()
        inspection.silne_stranky = None
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_omitted(content)

    def test_detailed_empty_string_omits_section(self) -> None:
        inspection = self._create_inspection(silne_stranky="")
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_omitted(content)

    def test_detailed_whitespace_and_blank_lines_omit_section(self) -> None:
        inspection = self._create_inspection()
        inspection.silne_stranky = "  \n\n\t  \n"
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_omitted(content)

    def test_detailed_placeholder_dash_omits_section(self) -> None:
        inspection = self._create_inspection(silne_stranky=_EMPTY_PLACEHOLDER)
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_omitted(content)

    def test_detailed_mixed_blank_lines_keep_only_valid(self) -> None:
        inspection = self._create_inspection(
            silne_stranky=f"\n  \nPlatná položka\n{_EMPTY_PLACEHOLDER}\n"
        )
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_present(content, "Platná položka")
        self.assertEqual(content.count("✔"), 1)

    def test_detailed_mixed_list_keeps_only_valid(self) -> None:
        inspection = self._create_inspection()
        inspection.silne_stranky = ["", "  ", "Platná položka", "\n", _EMPTY_PLACEHOLDER]
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_present(content, "Platná položka")
        self.assertEqual(content.count("✔"), 1)

    def test_detailed_one_strength_keeps_heading_and_text(self) -> None:
        inspection = self._create_inspection(
            silne_stranky="Funkční systém řízení."
        )
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_present(content, "Funkční systém řízení.")

    def test_detailed_multiple_strengths_keep_order(self) -> None:
        inspection = self._create_inspection(
            silne_stranky="První stránka.\nDruhá stránka.\nTřetí stránka."
        )
        content = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                inspection
            )
        )
        self._assert_strengths_present(
            content, "První stránka.", "Druhá stránka.", "Třetí stránka."
        )

    def test_protocol_empty_omits_section(self) -> None:
        inspection = self._create_inspection(silne_stranky=" \n ")
        content = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        self._assert_strengths_omitted(content)

    def test_protocol_filled_keeps_section(self) -> None:
        inspection = self._create_inspection(
            silne_stranky="Dobře vedená dokumentace BOZP."
        )
        content = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        self._assert_strengths_present(content, "Dobře vedená dokumentace BOZP.")

    def test_audit_empty_omits_section_in_protocol_and_detailed(self) -> None:
        audit = self._create_audit(silne_stranky="  \n\n  ")
        protocol = _odt_content(protokol_audit_service.generate_for_audit(audit))
        detailed = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        for content in (protocol, detailed):
            self.assertNotIn(AUDIT_STRENGTHS_EXPORT_SECTION, content)
            region = _region(content)
            self.assertNotIn(_EMPTY_PLACEHOLDER, region)

    def test_audit_filled_keeps_section_in_protocol_and_detailed(self) -> None:
        audit = self._create_audit(
            silne_stranky="Funkční systém řízení.\nDobře vedená dokumentace."
        )
        protocol = _odt_content(protokol_audit_service.generate_for_audit(audit))
        detailed = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        for content in (protocol, detailed):
            self.assertIn(AUDIT_STRENGTHS_EXPORT_SECTION, content)
            self.assertIn("✔ Funkční systém řízení.", content)
            self.assertIn("✔ Dobře vedená dokumentace.", content)
            self.assertLess(
                content.find(AUDIT_STRENGTHS_EXPORT_SECTION),
                content.find("✔ Funkční systém řízení."),
            )
            self.assertLess(
                content.find("✔ Funkční systém řízení."),
                content.find("✔ Dobře vedená dokumentace."),
            )


if __name__ == "__main__":
    unittest.main()
