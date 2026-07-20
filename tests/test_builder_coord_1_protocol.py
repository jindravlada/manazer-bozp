"""BUILDER-COORD-1 – kanonický model dokumentu a export protokolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QLabel
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="builder-coord-1-"))
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
    from moduly.koordinace_bozp.constants import (
        CONTACT_TYPE_TECHNICAL,
        PROTOCOL_CONCLUSION_1_TITLE,
        PROTOCOL_CONCLUSION_8_TITLE,
        PROTOCOL_SECTION_BASICS,
        PROTOCOL_SECTION_CONCLUSIONS,
        PROTOCOL_TITLE,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
        CONTACT_EMPLOYER_UNSPECIFIED,
        coordination_contact_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
        build_protocol_document,
        render_blocks_to_plain_lines,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        PROTOCOL_ODT_CHAPTER_TITLES,
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


class BuilderCoord1ProtocolTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha 1",
            nace="",
            abbreviation="HL",
        )

    def test_document_has_title_basics_and_eight_conclusions(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="BUILDER-COORD-1",
            meeting_date=date(2026, 7, 20),
            place="Praha",
        )
        result = coordination_protocol_builder.build(coordination.id)
        document = result.protocol_data.get("document") or {}
        self.assertIn("blocks", document)
        lines = render_blocks_to_plain_lines(document["blocks"])
        joined = "\n".join(lines)

        self.assertIn(PROTOCOL_TITLE, joined)
        self.assertIn(PROTOCOL_SECTION_BASICS, joined)
        self.assertIn("Číslo:", joined)
        self.assertIn("Název akce: BUILDER-COORD-1", joined)
        self.assertIn("Místo:", joined)
        self.assertIn("Datum schůzky:", joined)
        self.assertNotIn("Stav:", joined)
        self.assertNotIn("Platnost", joined)
        self.assertNotIn("Poznámka:", joined)

        self.assertIn(PROTOCOL_SECTION_CONCLUSIONS, joined)
        self.assertIn(f"1. {PROTOCOL_CONCLUSION_1_TITLE}", joined)
        self.assertIn(f"8. {PROTOCOL_CONCLUSION_8_TITLE}", joined)

    def test_pbp_content_not_metadata(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="BUILDER-COORD-1 PBP",
            meeting_date=date.today(),
        )
        result = coordination_protocol_builder.build(coordination.id)
        pbp = result.protocol_data.get("pbp_snapshot")
        if pbp is None:
            self.skipTest("Bez PBP revize nelze ověřit obsah přílohy A.")
        lines = render_blocks_to_plain_lines(
            result.protocol_data["document"]["blocks"]
        )
        joined = "\n".join(lines)
        for line in pbp.get("content_lines") or []:
            if (line or "").strip():
                self.assertIn(line.strip(), joined)
        self.assertNotIn(pbp.get("stored_filename") or "", joined)

        target = _TMP / "pbp-content.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        content = _odt_content(target)
        self.assertNotIn("stored_filename", content)
        if pbp.get("stored_filename"):
            self.assertNotIn(pbp["stored_filename"], content)

    def test_contacts_skip_neuvedeno_employer(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="BUILDER-COORD-1 contacts",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_TECHNICAL,
            employer_id=main.id,
            custom_name="Technik",
            phone="+420100",
        )
        result = coordination_protocol_builder.build(coordination.id)
        lines = render_blocks_to_plain_lines(
            result.protocol_data["document"]["blocks"]
        )
        joined = "\n".join(lines)
        self.assertIn("Technik", joined)
        self.assertNotIn(CONTACT_EMPLOYER_UNSPECIFIED, joined)

    def test_preview_matches_odt_body(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="BUILDER-COORD-1 preview",
            meeting_date=date.today(),
            place="Brno",
        )
        result = coordination_protocol_builder.build(coordination.id)
        odt_lines = coordination_protocol_odt_renderer.plain_lines_from_protocol_data(
            result.protocol_data
        )
        odt_joined = "\n".join(line for line in odt_lines if line is not None)

        with patch(
            "moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog."
            "coordination_protocol_builder.build",
            return_value=result,
        ):
            preview = CoordinationProtocolPreviewDialog(
                None,
                coordination_id=coordination.id,
            )
        preview_lines = [
            label.text()
            for label in preview.body.findChildren(QLabel)
            if (label.text() or "").strip()
        ]
        preview_joined = "\n".join(preview_lines)
        for marker in (
            PROTOCOL_TITLE,
            PROTOCOL_SECTION_BASICS,
            "Název akce: BUILDER-COORD-1 preview",
            PROTOCOL_SECTION_CONCLUSIONS,
        ):
            self.assertIn(marker, odt_joined)
            self.assertIn(marker, preview_joined)
        self.assertNotIn("Souhrn", odt_joined)
        self.assertNotIn("Souhrn", preview_joined)
        preview.close()

    def test_chapter_titles_match_new_outline(self) -> None:
        self.assertEqual(
            PROTOCOL_ODT_CHAPTER_TITLES[0],
            PROTOCOL_TITLE,
        )
        self.assertIn(PROTOCOL_SECTION_CONCLUSIONS, PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertNotIn("Titulní strana", PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertNotIn("Souhrn", PROTOCOL_ODT_CHAPTER_TITLES)
        self.assertNotIn("Upozornění", PROTOCOL_ODT_CHAPTER_TITLES)

    def test_build_protocol_document_standalone(self) -> None:
        data = {
            "basics": {
                "coordination_number": "K-TEST",
                "subject": "Test",
                "meeting_date": "2026-07-20",
                "place": "Ostrava",
            },
            "employers": [],
            "participants_by_employer": [],
            "coordinator": None,
            "workplaces": [],
            "activities_by_employer": [],
            "measures_by_category": [],
            "contacts": [],
            "emergency_procedures": {},
            "risk_handovers": [],
            "pbp_snapshot": None,
            "attachments_by_group": [],
        }
        document = build_protocol_document(data)
        self.assertTrue(document.get("blocks"))


if __name__ == "__main__":
    unittest.main()
