"""AI-RISK-OP-2: lingvistická pravidla pro formulaci opatření v AI pokynu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="ai-risk-op-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import AI_PEER_REVIEW_ZIP_FILES
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.prompt_builder import (
        MEASURE_FORMULATION_STYLE_HEADING,
        MEASURE_REVIEW_ORDER_HEADING,
        build_ai_peer_review_prompt,
        build_catalog_source_ai_peer_review_prompt,
        measure_formulation_style_section,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )


_LEGACY_PROMPT_SECTIONS = (
    "ROLE ODBORNÉHO OPONENTA",
    "KONTEXT IDENTIFIKACE",
    "PRÁVNÍ RÁMEC",
    "CÍL OPONENTURY",
    "STRUKTURA PODKLADŮ",
    "PRAVIDLA",
    "OTÁZKY K POSOUZENÍ",
    "FORMÁT ODPOVĚDI",
)

_LEGACY_CATALOG_PROMPT_SECTIONS = (
    "ROLE ODBORNÉHO OPONENTA",
    "KONTEXT ZDROJE RIZIKA",
    "PRÁVNÍ RÁMEC",
    "CÍL OPONENTURY",
    "STRUKTURA PODKLADŮ",
    "PRAVIDLA",
    "OTÁZKY K POSOUZENÍ",
    "FORMÁT ODPOVĚDI",
)

_STYLE_MARKERS = (
    MEASURE_FORMULATION_STYLE_HEADING,
    "Zásady bezpečné práce jsou určeny zaměstnanci",
    "přímé pokyny zaměstnanci",
    "Pravidla bezpečné práce",
    "Nepoužívejte pouze jmenné fráze",
    "umožňovat odpověď Ano / Ne / Netýká se",
    "Kontrolní otázka není úkol",
    "Je text pokynem zaměstnanci?",
    "takový návrh nesmíte navrhnout",
    "Zakázané formulace",
    "Preferujte aktivní věty",
    "vhodně",
    "Nepopisujte organizaci práce zaměstnavatele",
    "raději ji vůbec nenavrhujte",
    "Používejte...",
    "Riziko je zřejmé.",
)


class AiRiskOp2MeasureFormulationPromptTestCase(unittest.TestCase):
    def test_new_chapter_present_in_identification_prompt(self) -> None:
        prompt = build_ai_peer_review_prompt()
        for marker in _STYLE_MARKERS:
            self.assertIn(marker, prompt)

    def test_new_chapter_present_in_catalog_prompt(self) -> None:
        prompt = build_catalog_source_ai_peer_review_prompt()
        for marker in _STYLE_MARKERS:
            self.assertIn(marker, prompt)

    def test_legacy_identification_instructions_preserved(self) -> None:
        prompt = build_ai_peer_review_prompt()
        for section in _LEGACY_PROMPT_SECTIONS:
            self.assertIn(section, prompt)
        self.assertIn("Nehodnoť závažnost rizik.", prompt)
        self.assertIn(
            "Pokud jsou stávající zásady a kontrolní otázky dostatečné",
            prompt,
        )
        self.assertIn(
            "Nenavrhuj novou kontrolní otázku, pokud lze stejné ověření pokrýt",
            prompt,
        )
        self.assertIn("Oblast: <název oblasti>", prompt)
        # Nová kapitola stylu je mezi posouzením opatření a OTÁZKY.
        rules_idx = prompt.find("PRAVIDLA")
        review_idx = prompt.find(MEASURE_REVIEW_ORDER_HEADING)
        style_idx = prompt.find(MEASURE_FORMULATION_STYLE_HEADING)
        questions_idx = prompt.find("OTÁZKY K POSOUZENÍ")
        self.assertTrue(0 <= rules_idx < review_idx < style_idx < questions_idx)

    def test_legacy_catalog_instructions_preserved(self) -> None:
        prompt = build_catalog_source_ai_peer_review_prompt()
        for section in _LEGACY_CATALOG_PROMPT_SECTIONS:
            self.assertIn(section, prompt)
        self.assertIn("izolovaná opatření", prompt.casefold())
        self.assertIn("BALÍK:", prompt)
        self.assertIn("schema 2.0", prompt.casefold())

    def test_style_section_helper_is_complete(self) -> None:
        text = "\n".join(measure_formulation_style_section())
        self.assertTrue(text.startswith(MEASURE_FORMULATION_STYLE_HEADING))
        self.assertIn("Umísťujte nábytek na rovný a stabilní podklad.", text)
        self.assertIn("podle potřeby", text)


class AiRiskOp2ExportZipTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz AI-RISK-OP-2",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště AI-RISK-OP-2",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="AI", last_name="Op2")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb OP2",
        )
        self.export_dir = Path(tempfile.mkdtemp(prefix="ai-risk-op-2-zip-"))

    def test_export_zip_format_unchanged_and_contains_style_chapter(self) -> None:
        target = self.export_dir / "op2.zip"
        ai_peer_review_service.export_package(
            hazard_identification_peer_review_provider,
            self.identification.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        with zipfile.ZipFile(target, "r") as zf:
            self.assertEqual(set(zf.namelist()), set(AI_PEER_REVIEW_ZIP_FILES))
            prompt = zf.read("pokyn_pro_AI.txt").decode("utf-8")
        self.assertIn(MEASURE_FORMULATION_STYLE_HEADING, prompt)
        for section in _LEGACY_PROMPT_SECTIONS:
            self.assertIn(section, prompt)


if __name__ == "__main__":
    unittest.main()
