"""INSPECTION-REPORT-2a – sjednocení zobrazení komise s auditem."""

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

_TMP = Path(tempfile.mkdtemp(prefix="inspection-report-2a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.export.commission_display import (
        COMMISSION_LABEL_INVITED,
        COMMISSION_LABEL_LEADER_INSPECTION,
        COMMISSION_LABEL_MEMBERS,
        COMMISSION_LABEL_UNION,
        COMMISSION_LABEL_WORKPLACE,
        build_commission_sections,
        commission_sections_text,
    )
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


REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_EXPORT = REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty"


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _basic_info(content: str) -> str:
    return content.split("Základní informace", 1)[1].split("CELKOVÉ HODNOCENÍ", 1)[0]


def _sync_templates() -> None:
    import moduly.proverky.sluzby.protokol_proverky_service as protokol_module

    importlib.reload(protokol_module)
    for name in ("ProtokolProverkyBOZP.odt", "PodrobnaZpravaProverky.odt"):
        bundled = BUNDLED_EXPORT / name
        target = protokol_module.protokol_proverky_service.template_path(
            detailed=name.startswith("Podrobna")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)


class InspectionReport2aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_templates()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
        )

    def _ids(self) -> dict[str, int]:
        return {
            "leader": settings_service.save_worker(
                first_name="Jan", last_name="Novák"
            ).id,
            "workplace": settings_service.save_worker(
                first_name="Eva", last_name="Králová"
            ).id,
            "union": person_service.create_person(
                first_name="Lucie", last_name="Horáková"
            ).id,
            "member": settings_service.save_worker(
                first_name="Petr", last_name="Svoboda"
            ).id,
            "member2": settings_service.save_worker(
                first_name="Adam", last_name="Dvořák"
            ).id,
            "invited": person_service.create_person(
                first_name="Host", last_name="Hostovič"
            ).id,
            "invited2": person_service.create_person(
                first_name="Host", last_name="Druhý"
            ).id,
        }

    def _save_members(self, inspection_id: int, members: list[dict]) -> None:
        bozp_inspection_commission_service.save_members(inspection_id, members)

    def _create_inspection(self, *, members: list[dict] | None = None):
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Hala Komise",
            title="Prověrka komise 2026",
            started_at=date(2026, 7, 1),
            finished_at=date(2026, 7, 5),
        )
        ids = self._ids()
        if members is None:
            members = [
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": ids["leader"],
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": ids["workplace"],
                    "display_name": "Eva Králová",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": ids["union"],
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": ids["member"],
                    "display_name": "Petr Svoboda",
                    "display_order": 40,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": ids["member2"],
                    "display_name": "Adam Dvořák",
                    "display_order": 50,
                    "active": True,
                },
                {
                    "record_type": "prizvana_osoba",
                    "person_id": ids["invited"],
                    "display_name": "Host Hostovič",
                    "display_order": 60,
                    "active": True,
                },
                {
                    "record_type": "prizvana_osoba",
                    "person_id": ids["invited2"],
                    "display_name": "Host Druhý",
                    "display_order": 70,
                    "active": True,
                },
            ]
        self._save_members(inspection.id, members)
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        return loaded

    def _required_only_members(self) -> list[dict]:
        ids = self._ids()
        return [
            {
                "record_type": "vedouci_komise",
                "thp_worker_id": ids["leader"],
                "display_name": "Jan Novák",
                "display_order": 10,
                "active": True,
            },
            {
                "record_type": "zastupce_pracoviste",
                "thp_worker_id": ids["workplace"],
                "display_name": "Eva Králová",
                "display_order": 20,
                "active": True,
            },
            {
                "record_type": "zastupce_odboru",
                "person_id": ids["union"],
                "display_name": "Lucie Horáková",
                "display_order": 30,
                "active": True,
            },
        ]

    def test_shared_builder_order_and_empty_skip(self) -> None:
        sections = build_commission_sections(
            leader_label=COMMISSION_LABEL_LEADER_INSPECTION,
            leader_names=["Jan Novák"],
            workplace_names=["Eva Králová"],
            union_names=[],
            member_names=["Petr Svoboda", "Adam Dvořák"],
            invited_names=[],
        )
        self.assertEqual(
            [section.key for section in sections],
            ["leader", "workplace", "members"],
        )
        self.assertEqual(
            [section.label for section in sections],
            [
                COMMISSION_LABEL_LEADER_INSPECTION,
                COMMISSION_LABEL_WORKPLACE,
                COMMISSION_LABEL_MEMBERS,
            ],
        )
        text = commission_sections_text(sections)
        self.assertIn("Petr Svoboda\nAdam Dvořák", text)
        self.assertNotIn(COMMISSION_LABEL_UNION, text)
        self.assertNotIn(COMMISSION_LABEL_INVITED, text)
        self.assertNotIn("•", text)

    def test_full_commission_in_protocol_and_detailed_report(self) -> None:
        inspection = self._create_inspection()
        order = [
            COMMISSION_LABEL_LEADER_INSPECTION,
            COMMISSION_LABEL_WORKPLACE,
            COMMISSION_LABEL_UNION,
            COMMISSION_LABEL_MEMBERS,
            COMMISSION_LABEL_INVITED,
        ]

        for generate in (
            protokol_proverky_service.generate_for_inspection,
            protokol_proverky_service.generate_detailed_report_for_inspection,
        ):
            content = _odt_content(generate(inspection))
            basic = _basic_info(content)
            positions = [basic.find(label) for label in order]
            self.assertTrue(all(pos >= 0 for pos in positions), basic)
            self.assertEqual(positions, sorted(positions))

            self.assertIn("Jan Novák", basic)
            self.assertIn("Eva Králová", basic)
            self.assertIn("Lucie Horáková", basic)
            self.assertIn("Petr Svoboda", basic)
            self.assertIn("Adam Dvořák", basic)
            self.assertIn("Host Hostovič", basic)
            self.assertIn("Host Druhý", basic)
            self.assertNotIn(">Komise</text:p>", content)
            # oddělené řádky tabulky – ne společný blob s odrážkami
            self.assertNotIn("•", basic)

    def test_commission_without_union_omits_section(self) -> None:
        ids = self._ids()
        inspection = self._create_inspection(
            members=[
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": ids["leader"],
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": ids["workplace"],
                    "display_name": "Eva Králová",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": ids["union"],
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": ids["member"],
                    "display_name": "Petr Svoboda",
                    "display_order": 40,
                    "active": True,
                },
                {
                    "record_type": "prizvana_osoba",
                    "person_id": ids["invited"],
                    "display_name": "Host Hostovič",
                    "display_order": 60,
                    "active": True,
                },
            ]
        )
        # UI union je povinný; pro exportní scénář bez odborů odstraň záznam.
        remaining = [
            bozp_inspection_commission_service.member_to_dict(member)
            for member in bozp_inspection_commission_service.get_for_inspection(
                inspection.id
            )
            if member.record_type != "zastupce_odboru"
        ]
        with patch.object(
            bozp_inspection_commission_service,
            "validate_members",
            side_effect=lambda members: members,
        ):
            bozp_inspection_commission_service.save_members(inspection.id, remaining)
        inspection = bozp_inspection_service.get_by_id(inspection.id)
        assert inspection is not None

        for generate in (
            protokol_proverky_service.generate_for_inspection,
            protokol_proverky_service.generate_detailed_report_for_inspection,
        ):
            basic = _basic_info(_odt_content(generate(inspection)))
            self.assertIn(COMMISSION_LABEL_LEADER_INSPECTION, basic)
            self.assertIn(COMMISSION_LABEL_WORKPLACE, basic)
            self.assertIn(COMMISSION_LABEL_MEMBERS, basic)
            self.assertIn(COMMISSION_LABEL_INVITED, basic)
            self.assertNotIn(COMMISSION_LABEL_UNION, basic)
            self.assertNotIn("Lucie Horáková", basic)

    def test_commission_without_invited_omits_section(self) -> None:
        ids = self._ids()
        inspection = self._create_inspection(
            members=[
                {
                    "record_type": "vedouci_komise",
                    "thp_worker_id": ids["leader"],
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": "zastupce_pracoviste",
                    "thp_worker_id": ids["workplace"],
                    "display_name": "Eva Králová",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": "zastupce_odboru",
                    "person_id": ids["union"],
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": "clen_komise",
                    "thp_worker_id": ids["member"],
                    "display_name": "Petr Svoboda",
                    "display_order": 40,
                    "active": True,
                },
            ]
        )

        for generate in (
            protokol_proverky_service.generate_for_inspection,
            protokol_proverky_service.generate_detailed_report_for_inspection,
        ):
            basic = _basic_info(_odt_content(generate(inspection)))
            self.assertIn(COMMISSION_LABEL_UNION, basic)
            self.assertIn(COMMISSION_LABEL_MEMBERS, basic)
            self.assertNotIn(COMMISSION_LABEL_INVITED, basic)
            self.assertNotIn("Host Hostovič", basic)

    def test_empty_optional_sections_omitted(self) -> None:
        inspection = self._create_inspection(members=self._required_only_members())
        context = bozp_inspection_export_context_service.build(inspection)
        text = context.commission_text()
        self.assertIn(COMMISSION_LABEL_LEADER_INSPECTION, text)
        self.assertIn(COMMISSION_LABEL_WORKPLACE, text)
        self.assertIn(COMMISSION_LABEL_UNION, text)
        self.assertNotIn(COMMISSION_LABEL_MEMBERS, text)
        self.assertNotIn(COMMISSION_LABEL_INVITED, text)

        for generate in (
            protokol_proverky_service.generate_for_inspection,
            protokol_proverky_service.generate_detailed_report_for_inspection,
        ):
            basic = _basic_info(_odt_content(generate(inspection)))
            self.assertIn(COMMISSION_LABEL_LEADER_INSPECTION, basic)
            self.assertIn(COMMISSION_LABEL_WORKPLACE, basic)
            self.assertIn(COMMISSION_LABEL_UNION, basic)
            self.assertNotIn(COMMISSION_LABEL_MEMBERS, basic)
            self.assertNotIn(COMMISSION_LABEL_INVITED, basic)


if __name__ == "__main__":
    unittest.main()
