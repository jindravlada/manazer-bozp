"""INSPECTION-REPORT-2b – sjednocení terminologie a podpisových částí."""

from __future__ import annotations

import html
import importlib
import os
import re
import shutil
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="inspection-report-2b-"))
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
        COMMISSION_LABEL_MEMBERS,
        COMMISSION_LABEL_UNION,
        COMMISSION_LABEL_WORKPLACE,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import INSPECTION_INVALID_DATE_ORDER_MESSAGE
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_export_context_service import (
        bozp_inspection_export_context_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


REPO_ROOT = Path(__file__).resolve().parents[1]


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_plain_text(content: str) -> str:
    """ODT content.xml → čitelný text (tagy, text:s, line-break)."""
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(
        r'<text:s\s+text:c="(\d+)"/>',
        lambda match: " " * int(match.group(1)),
        text,
    )
    text = re.sub(r"<text:s\s*/>", " ", text)
    text = re.sub(r"<text:tab\s*/>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _sync_inspection_templates() -> None:
    import moduly.proverky.sluzby.protokol_proverky_service as protokol_module

    importlib.reload(protokol_module)
    for name, detailed in (
        ("ProtokolProverkyBOZP.odt", False),
        ("PodrobnaZpravaProverky.odt", True),
    ):
        bundled = (
            REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / name
        )
        target = protokol_module.protokol_proverky_service.template_path(
            detailed=detailed
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)


def _sync_audit_templates() -> None:
    import moduly.audity.sluzby.protokol_audit_service as protokol_module

    importlib.reload(protokol_module)
    for name, detailed in (
        ("ProtokolAudit.odt", False),
        ("PodrobnaZpravaAudit.odt", True),
    ):
        bundled = REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / name
        target = protokol_module.protokol_audit_service.template_path(
            detailed=detailed
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)


class InspectionReport2bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_inspection_templates()
        _sync_audit_templates()

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        settings_service.save_employer(
            ico="12345678",
            name="Test Zaměstnavatel s.r.o.",
            address="Praha 1",
        )

    def _people(self) -> dict[str, int]:
        return {
            "leader": settings_service.save_worker(
                first_name="Jan", last_name="Novák"
            ).id,
            "workplace": settings_service.save_worker(
                first_name="Eva", last_name="Králová"
            ).id,
            "member": settings_service.save_worker(
                first_name="Petr", last_name="Svoboda"
            ).id,
            "union": person_service.create_person(
                first_name="Lucie", last_name="Horáková"
            ).id,
        }

    def _full_members(self, ids: dict[str, int], *, with_union: bool = True) -> list[dict]:
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
                "record_type": "clen_komise",
                "thp_worker_id": ids["member"],
                "display_name": "Petr Svoboda",
                "display_order": 40,
                "active": True,
            },
        ]
        if with_union:
            members.insert(
                2,
                {
                    "record_type": "zastupce_odboru",
                    "person_id": ids["union"],
                    "display_name": "Lucie Horáková",
                    "display_order": 30,
                    "active": True,
                },
            )
        return members

    def _create_inspection(self, *, with_union: bool = True, **kwargs):
        defaults = {
            "workplace_name": "Hala 2b",
            "started_at": date(2026, 7, 1),
            "finished_at": date(2026, 7, 5),
        }
        defaults.update(kwargs)
        inspection = bozp_inspection_service.create_inspection(**defaults)
        ids = self._people()
        members = self._full_members(ids, with_union=with_union)
        if with_union:
            bozp_inspection_commission_service.save_members(inspection.id, members)
        else:
            # union is required by validate; remove after save
            with_union_members = self._full_members(ids, with_union=True)
            bozp_inspection_commission_service.save_members(
                inspection.id, with_union_members
            )
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
                side_effect=lambda items: items,
            ):
                bozp_inspection_commission_service.save_members(
                    inspection.id, remaining
                )
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        return loaded

    def _create_audit(self):
        ids = self._people()
        audit = audit_service.create_audit(
            workplace_name="Provoz Audit",
            started_at=date(2026, 7, 1),
            finished_at=date(2026, 7, 5),
        )
        audit_commission_service.save_members(
            audit.id,
            [
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
            ],
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        return loaded

    def test_audit_uses_short_commission_terminology(self) -> None:
        audit = self._create_audit()
        for generate in (
            protokol_audit_service.generate_for_audit,
            protokol_audit_service.generate_detailed_report_for_audit,
        ):
            content = _odt_content(generate(audit))
            self.assertIn(COMMISSION_LABEL_WORKPLACE, content)
            self.assertIn(COMMISSION_LABEL_MEMBERS, content)
            self.assertIn(COMMISSION_LABEL_UNION, content)
            self.assertNotIn("Zástupce auditovaného provozu", content)
            self.assertNotIn("Členové auditorské komise", content)

    def test_inspection_protocol_includes_union_signature(self) -> None:
        inspection = self._create_inspection(with_union=True)
        content = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        signatures = _odt_plain_text(
            content.split("Podpisy", 1)[1].split("Příloha A", 1)[0]
        )
        self.assertIn("Vedoucí prověrky", signatures)
        self.assertIn("Zástupce provozu", signatures)
        self.assertIn(COMMISSION_LABEL_UNION, signatures)
        self.assertIn("Lucie Horáková", signatures)
        self.assertIn("Jan Novák", signatures)
        self.assertIn("Eva Králová", signatures)

        values = bozp_inspection_export_context_service.build(
            inspection
        ).placeholder_values()
        self.assertIn(COMMISSION_LABEL_UNION, values["podpis_odboru_blok"])
        self.assertIn("Lucie Horáková", values["podpis_odboru_blok"])

    def test_inspection_protocol_omits_missing_union_signature(self) -> None:
        inspection = self._create_inspection(with_union=False)
        content = _odt_content(
            protokol_proverky_service.generate_for_inspection(inspection)
        )
        signatures = _odt_plain_text(
            content.split("Podpisy", 1)[1].split("Příloha A", 1)[0]
        )
        self.assertIn("Vedoucí prověrky", signatures)
        self.assertIn("Zástupce provozu", signatures)
        self.assertNotIn(COMMISSION_LABEL_UNION, signatures)
        self.assertNotIn("Lucie Horáková", signatures)

        values = bozp_inspection_export_context_service.build(
            inspection
        ).placeholder_values()
        self.assertEqual(values["podpis_odboru_blok"], "")

    def test_appendix_b_and_significant_findings_labels(self) -> None:
        inspection = self._create_inspection(silne_stranky="Stabilní dokumentace.")
        for generate in (
            protokol_proverky_service.generate_for_inspection,
            protokol_proverky_service.generate_detailed_report_for_inspection,
        ):
            content = _odt_content(generate(inspection))
            self.assertIn("Příloha B – Kontrolní body", content)
            self.assertIn("Významná zjištění", content)
            self.assertNotIn("Přehled zjištění", content)
            self.assertNotIn(
                "Příloha B – Výsledky jednotlivých kontrolních bodů", content
            )

            # pořadí jako u auditu
            positions = [
                content.find("Přehled výsledků"),
                content.find("Silné stránky systému"),
                content.find("Oblasti vyžadující pozornost"),
                content.find("Významná zjištění"),
                content.find("Doporučení vedoucího prověrky"),
            ]
            self.assertTrue(all(pos >= 0 for pos in positions))
            self.assertEqual(positions, sorted(positions))

    def test_date_order_validation_on_save_and_export(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            bozp_inspection_service.create_inspection(
                started_at=date(2026, 7, 10),
                finished_at=date(2026, 7, 1),
            )
        self.assertEqual(str(ctx.exception), INSPECTION_INVALID_DATE_ORDER_MESSAGE)

        inspection = bozp_inspection_service.create_inspection(
            started_at=date(2026, 7, 10),
        )
        # bypass service normalize by repository-level finished_at set via update
        # that still validates
        with self.assertRaises(ValueError) as ctx_update:
            bozp_inspection_service.update_inspection(
                inspection.id,
                finished_at=date(2026, 7, 1),
            )
        self.assertEqual(
            str(ctx_update.exception), INSPECTION_INVALID_DATE_ORDER_MESSAGE
        )

        # Export musí odmítnout i při nekonzistentních datech v DB.
        from core.database.session import SessionLocal
        from moduly.proverky.modely.bozp_inspection import BozpInspection

        with SessionLocal() as session:
            row = session.get(BozpInspection, inspection.id)
            assert row is not None
            row.finished_at = date(2026, 7, 1)
            session.commit()

        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None
        self.assertEqual(loaded.finished_at, date(2026, 7, 1))
        self.assertEqual(loaded.started_at, date(2026, 7, 10))

        with self.assertRaises(ValueError) as ctx_export:
            protokol_proverky_service.generate_for_inspection(loaded)
        self.assertEqual(
            str(ctx_export.exception), INSPECTION_INVALID_DATE_ORDER_MESSAGE
        )

        with self.assertRaises(ValueError) as ctx_detailed:
            protokol_proverky_service.generate_detailed_report_for_inspection(loaded)
        self.assertEqual(
            str(ctx_detailed.exception), INSPECTION_INVALID_DATE_ORDER_MESSAGE
        )


if __name__ == "__main__":
    unittest.main()
