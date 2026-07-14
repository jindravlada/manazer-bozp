"""Fáze R11.8 – zkvalitnění zadání pro AI oponenturu."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_DEFAULT_OBJECTIVES,
        AI_PEER_REVIEW_DEFAULT_ROLE,
        AI_PEER_REVIEW_FOCUS_CONTRACTORS,
        AI_PEER_REVIEW_FOCUS_EMERGENCY,
        AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS,
        AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES,
        AI_PEER_REVIEW_ROLE_DEVILS_ADVOCATE,
        AI_PEER_REVIEW_ROLE_LABELS,
        AI_PEER_REVIEW_ROLE_OIP_INSPECTOR,
        AI_PEER_REVIEW_ZIP_FILES,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal
    from core.ai_oponentni.sluzby.prompt_builder import build_ai_peer_review_prompt
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewExportOptionsDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_ASSESSMENT_STATUS_COMPLETED,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )


class AiPeerReviewPromptPhaseR118TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

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
            name="Provoz R118",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna R118",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Eva", last_name="Oponent")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=self.workplace.id,
            responsible_person_id=person.id,
        )
        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Portálový jeřáb",
        )
        self.provider = hazard_identification_peer_review_provider
        self.export_dir = Path(tempfile.mkdtemp())

    def test_dialog_defaults_role_and_objectives(self) -> None:
        dialog = AiPeerReviewExportOptionsDialog()
        self.assertEqual(dialog.opponent_role.currentData(), AI_PEER_REVIEW_DEFAULT_ROLE)
        options = dialog.get_options()
        self.assertEqual(options.opponent_role, AI_PEER_REVIEW_DEFAULT_ROLE)
        self.assertEqual(set(options.objectives or []), set(AI_PEER_REVIEW_DEFAULT_OBJECTIVES))
        self.assertEqual(options.focus_areas, [])
        self.assertEqual(options.workplace_characteristics, "")
        self.assertFalse(hasattr(dialog, "include_responsible_person"))
        self.assertFalse(hasattr(options, "include_responsible_person"))

    def test_options_store_role_objectives_and_characteristics(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(
                opponent_role=AI_PEER_REVIEW_ROLE_OIP_INSPECTOR,
                objectives=[
                    AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES,
                    AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS,
                ],
                focus_areas=[
                    AI_PEER_REVIEW_FOCUS_EMERGENCY,
                    AI_PEER_REVIEW_FOCUS_CONTRACTORS,
                ],
                workplace_characteristics=(
                    "Dílna oprav kolejových vozidel. Probíhá údržba a svařování."
                ),
            ),
        )
        zadani = content.batches[0].zadani_json
        self.assertEqual(zadani["opponent_role"], AI_PEER_REVIEW_ROLE_OIP_INSPECTOR)
        self.assertEqual(
            zadani["opponent_role_label"],
            AI_PEER_REVIEW_ROLE_LABELS[AI_PEER_REVIEW_ROLE_OIP_INSPECTOR],
        )
        self.assertEqual(
            zadani["peer_review_objectives"],
            [
                AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES,
                AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS,
            ],
        )
        self.assertEqual(
            zadani["peer_review_focus_areas"],
            [AI_PEER_REVIEW_FOCUS_EMERGENCY, AI_PEER_REVIEW_FOCUS_CONTRACTORS],
        )
        self.assertIn("Dílna oprav kolejových vozidel", zadani["workplace_characteristics"])
        self.assertEqual(
            zadani["consultation_request"]["opponent_role"],
            AI_PEER_REVIEW_ROLE_OIP_INSPECTOR,
        )

        prompt = content.prompt_text
        self.assertIn("Inspektor OIP", prompt)
        self.assertIn("Dílna oprav kolejových vozidel", prompt)
        self.assertIn("Hledat chybějící zdroje analýzy", prompt)
        self.assertIn("Hledat chybějící nežádoucí události", prompt)
        self.assertIn("Zaměřit se na mimořádné situace", prompt)
        self.assertIn("Zaměřit se na dodavatele", prompt)
        self.assertIn(
            "Posuzuj podle aktuálně platných právních předpisů České republiky",
            prompt,
        )
        self.assertIn("Nenavrhuj zjevně nereálné scénáře", prompt)
        self.assertIn("Jsou v analýze všechny významné zdroje?", prompt)

    def test_prompt_contains_identification_status_notes(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        prompt = content.prompt_text
        self.assertIn("první identifikaci", prompt.casefold())
        self.assertIn("Posouzení rizik zatím nebyla provedena.", prompt)
        context = content.batches[0].zadani_json["identification_context"]
        self.assertEqual(context["kind"], "first")
        self.assertEqual(context["risk_assessment_status"], "none")

        event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Pád břemene",
        )
        hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=event.id,
            exposed_group="Jeřábník",
            consequence="Zranění",
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        content2 = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn(
            "Všechna aktivní posouzení rizik jsou označena jako dokončená.",
            content2.prompt_text,
        )
        self.assertEqual(
            content2.batches[0].zadani_json["identification_context"][
                "risk_assessment_status"
            ],
            "completed",
        )

        # Druhá identifikace na stejném pracovišti = revize
        revision = hazard_identification_service.create_identification(
            operation_id=self.identification.operation_id,
            workplace_id=self.workplace.id,
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=revision.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Svářečka",
        )
        content3 = self.provider.build_export_content(
            revision.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn("revizi existující identifikace", content3.prompt_text)
        self.assertEqual(
            content3.batches[0].zadani_json["identification_context"]["kind"],
            "revision",
        )

    def test_export_structure_backwards_compatible(self) -> None:
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(
                opponent_role=AI_PEER_REVIEW_ROLE_DEVILS_ADVOCATE,
            ),
        )
        zadani = content.batches[0].zadani_json
        for key in (
            "schema_version",
            "export_type",
            "export_scope",
            "workplace_analysis",
            "identification",
            "hierarchy",
            "change_tracking",
        ):
            self.assertIn(key, zadani)
        self.assertIsInstance(zadani["workplace_analysis"], list)
        self.assertEqual(zadani["workplace_analysis"][0]["name"], "Portálový jeřáb")
        self.assertNotIn("relations", zadani["workplace_analysis"][0])

        target = self.export_dir / "r118.zip"
        from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service

        ai_peer_review_service.export_package(
            self.provider,
            self.identification.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        with zipfile.ZipFile(target, "r") as zf:
            self.assertEqual(set(zf.namelist()), set(AI_PEER_REVIEW_ZIP_FILES))
            prompt = zf.read("pokyn_pro_AI.txt").decode("utf-8")
            loaded = json.loads(zf.read("zadani.json").decode("utf-8"))
        self.assertIn("ROLE ODBORNÉHO OPONENTA", prompt)
        self.assertIn("opponent_role", loaded)

    def test_prompt_builder_unit(self) -> None:
        text = build_ai_peer_review_prompt(
            role=AI_PEER_REVIEW_ROLE_DEVILS_ADVOCATE,
            objectives=[AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES],
            focus_areas=[AI_PEER_REVIEW_FOCUS_EMERGENCY],
            workplace_characteristics="Svářovna",
            identification_kind_note="Jde o první identifikaci rizik na tomto pracovišti.",
            risk_assessment_note="Posouzení rizik zatím nebyla provedena.",
        )
        self.assertIn("Ďáblův advokát", text)
        self.assertIn("Svářovna", text)
        self.assertIn("Hledat chybějící zdroje analýzy", text)
        self.assertNotIn("Hledat chybějící nežádoucí události", text)


if __name__ == "__main__":
    unittest.main()
