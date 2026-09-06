"""Fáze R18f – oponentura AI v Katalogu zdrojů rizik."""

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
        AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES,
        AI_PEER_REVIEW_TAB_TITLE,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_unassigned_proposal import (
        PROPOSAL_STATUS_PENDING,
        PROPOSAL_STATUS_REJECTED,
        AiUnassignedProposal,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.response_parser import parse_ai_peer_review_response
    from core.ai_oponentni.sluzby.response_zip_loader import load_response_from_zip
    from core.ai_oponentni.types import AiPeerReviewExportOptions, AiProposal
    from core.ai_oponentni.ui.ai_peer_review_widget import (
        AiPeerReviewExportOptionsDialog,
        AiPeerReviewWidget,
        catalog_peer_review_export_dialog_config,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_SCOPE_ALL,
        HAZARD_LIBRARY_TAB_AI_PEER_REVIEW,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        SOURCE_TYPE_HAZARD_CATALOG_SOURCE,
        catalog_source_reference,
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        SOURCE_TYPE_HAZARD_IDENTIFICATION,
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import HazardLibraryTemplateDialog
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


CATALOG_SAMPLE_RESPONSE = """\
Oblast: Nežádoucí událost
Návrh: Pád z výšky
Rodič: SOURCE-001
Zdůvodnění:
Typické riziko při práci ve výškě.

Oblast: Potřebné opatření
Návrh: Zábradlí na pracovní plošině
Rodič: ASSESSMENT-001
Zdůvodnění: Ochrana proti pádu.
"""


class HazardCatalogAiPeerReviewR18fTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment

        with get_session() as session:
            session.execute(delete(AiUnassignedProposal))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci")
        self.template, self.event, self.assessment = self._create_template_with_content()
        self.inactive_event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Neaktivní událost",
            active=False,
        )
        self.export_dir = Path(tempfile.mkdtemp())
        self.provider = hazard_catalog_source_peer_review_provider

        operation = settings_service.save_workplace(
            name="Provoz test",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.inventory_item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lokální zdroj",
        )

    def _create_template_with_content(self):
        template = hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis zdroje",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
            note="Poznámka zdroje",
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Pád břemene",
            description="Popis události",
            note="Poznámka události",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Nutná opatření",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Ochranné zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Doplnit zábradlí",
        )
        return template, event, assessment

    def test_provider_source_type(self) -> None:
        self.assertEqual(self.provider.source_type, SOURCE_TYPE_HAZARD_CATALOG_SOURCE)
        self.assertEqual(
            self.provider.get_source_label(self.template.id),
            catalog_source_reference(self.template.id),
        )

    def test_catalog_dialog_ai_tab_disabled_before_save(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertIn(HAZARD_LIBRARY_TAB_AI_PEER_REVIEW, labels)
        self.assertFalse(dialog.tabs.isTabEnabled(dialog.ai_peer_review_tab_index))
        self.assertFalse(dialog.ai_peer_review_widget.export_btn.isEnabled())

    def test_catalog_dialog_ai_tab_enabled_after_save(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        self.assertTrue(dialog.tabs.isTabEnabled(dialog.ai_peer_review_tab_index))
        self.assertTrue(dialog.ai_peer_review_widget.export_btn.isEnabled())
        self.assertTrue(dialog.ai_peer_review_widget.import_btn.isEnabled())

    def test_catalog_export_dialog_without_missing_sources_objective(self) -> None:
        dialog = AiPeerReviewExportOptionsDialog(
            dialog_config=catalog_peer_review_export_dialog_config(),
        )
        objective_ids = set(dialog._objective_checks)
        self.assertNotIn(AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES, objective_ids)
        self.assertFalse(dialog.scope_section_label.isVisible())
        self.assertFalse(dialog.source_list.isVisible())

    def test_export_master_hierarchy_and_stable_ids(self) -> None:
        content = self.provider.build_export_content(
            self.template.id,
            options=AiPeerReviewExportOptions(),
        )
        zadani = content.zadani_json
        assert zadani is not None
        self.assertNotIn("request_mode", zadani)
        self.assertEqual(
            zadani["export_type"],
            "hazard_catalog_source_ai_peer_review",
        )
        self.assertEqual(
            zadani["catalog_source"]["reference"],
            catalog_source_reference(self.template.id),
        )
        self.assertEqual(zadani["catalog_source"]["name"], "Portálový jeřáb")
        self.assertEqual(zadani["risk_source"]["export_id"], "SOURCE-001")
        self.assertEqual(zadani["risk_source"]["events"][0]["export_id"], "EVENT-001")
        self.assertEqual(
            zadani["risk_source"]["events"][0]["assessments"][0]["export_id"],
            "ASSESSMENT-001",
        )
        self.assertEqual(
            zadani["risk_source"]["events"][0]["assessments"][0]["existing_measures"][0][
                "export_id"
            ],
            "EXISTING-MEASURE-001",
        )
        self.assertEqual(
            zadani["risk_source"]["events"][0]["assessments"][0]["required_measures"][0][
                "export_id"
            ],
            "REQUIRED-MEASURE-001",
        )
        mapping = content.export_id_map
        self.assertEqual(mapping["SOURCE-001"]["kind"], "source")
        self.assertEqual(mapping["EVENT-001"]["id"], self.event.id)
        self.assertEqual(mapping["ASSESSMENT-001"]["id"], self.assessment.id)

    def test_export_only_active_content(self) -> None:
        content = self.provider.build_export_content(
            self.template.id,
            options=AiPeerReviewExportOptions(),
        )
        self.assertIn("Pád břemene", content.data_text)
        self.assertNotIn("Neaktivní událost", content.data_text)

    def test_export_excludes_personal_and_local_data(self) -> None:
        content = self.provider.build_export_content(
            self.template.id,
            options=AiPeerReviewExportOptions(
                workplace_characteristics="Kontext pro AI",
            ),
        )
        dumped = json.dumps(content.zadani_json, ensure_ascii=False)
        for forbidden in (
            "template_id",
            "operation_id",
            "workplace_id",
            "identification_number",
            "responsible_person",
            "inventory_item",
            "fotografie",
            "instance",
        ):
            self.assertNotIn(forbidden, dumped.casefold())
        self.assertNotIn(self.identification.identification_number, content.data_text)
        self.assertNotIn("Lokální zdroj", content.data_text)
        self.assertIn("Obecný kontext zdroje rizika", content.prompt_text)
        self.assertIn("Kontext pro AI", content.prompt_text)
        self.assertNotIn("Charakteristika pracoviště", content.prompt_text)

    def test_json_txt_zip_import_formats(self) -> None:
        target = self.export_dir / "AI_oponentura_KZR.zip"
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            target,
            options=AiPeerReviewExportOptions(),
        )
        self.assertTrue(target.is_file())
        self.assertTrue(zipfile.is_zipfile(target))
        with zipfile.ZipFile(target, "r") as zf:
            payload = json.loads(zf.read("zadani.json").decode("utf-8"))
        self.assertEqual(payload["schema_version"], "2.0")
        self.assertNotIn("request_mode", payload)
        self.assertIn("catalog_source", payload)
        self.assertIn("risk_source", payload)

        txt_path = self.export_dir / "odpoved.txt"
        txt_path.write_text(CATALOG_SAMPLE_RESPONSE, encoding="utf-8")
        parsed_txt = ai_peer_review_service.parse_response(
            txt_path.read_text(encoding="utf-8"),
            expected_source_identification_number=catalog_source_reference(self.template.id),
        )
        self.assertEqual(len(parsed_txt.proposals), 2)

        json_path = self.export_dir / "odpoved.json"
        json_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.1",
                    "source_identification_number": catalog_source_reference(self.template.id),
                    "generated_at": "2026-07-15T08:00:00",
                    "proposals": [
                        {
                            "proposal_id": "P-001",
                            "area": "Nežádoucí událost",
                            "name": "Pád z výšky",
                            "parent_export_id": "SOURCE-001",
                            "reasoning": "Test",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        parsed_json = ai_peer_review_service.parse_response(
            json_path.read_text(encoding="utf-8"),
            expected_source_identification_number=catalog_source_reference(self.template.id),
        )
        self.assertEqual(len(parsed_json.proposals), 1)

        zip_response = self.export_dir / "odpoved.zip"
        with zipfile.ZipFile(zip_response, "w") as zf:
            zf.writestr("odpoved.txt", CATALOG_SAMPLE_RESPONSE)
        loaded_zip = load_response_from_zip(zip_response)
        self.assertIn("Pád z výšky", loaded_zip.text)

        before_events = len(
            hazard_library_template_event_service.get_for_template(
                self.template.id,
                include_inactive=False,
            )
        )
        updated = ai_peer_review_service.finalize_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=export_result.review.id,
            response_text=CATALOG_SAMPLE_RESPONSE,
            ai_model="Claude",
            accepted=parsed_txt.proposals,
            rejected=[],
            loaded_proposals_count=len(parsed_txt.proposals),
        )
        self.assertEqual(updated.ai_model, "Claude")
        self.assertEqual(updated.accepted_count, 0)
        self.assertEqual(updated.pending_proposals_count, 2)
        self.assertEqual(updated.loaded_proposals_count, 2)
        self.assertIsNotNone(updated.response_loaded_at)
        self.assertIn("Pád z výšky", updated.response_text)
        stored = ai_peer_review_service.get_unassigned_for_review(updated.id)
        self.assertEqual(len(stored), 2)
        self.assertTrue(all(item.status == PROPOSAL_STATUS_PENDING for item in stored))
        after_events = hazard_library_template_event_service.get_for_template(
            self.template.id,
            include_inactive=False,
        )
        self.assertEqual(len(after_events), before_events)

    def test_identification_disables_new_peer_review_but_keeps_history(self) -> None:
        target = self.export_dir / "historie_identifikace.zip"
        ai_peer_review_service.export_package(
            hazard_identification_peer_review_provider,
            self.identification.id,
            target,
        )
        # Oponentura AI je v editoru identifikace záměrně odstraněna (pouze Katalog).
        dialog = HazardIdentificationDialog(identification=self.identification)
        self.assertFalse(hasattr(dialog, "ai_peer_review_widget"))

        widget = AiPeerReviewWidget(
            provider=hazard_identification_peer_review_provider,
            allow_new_exports=False,
        )
        widget.set_source(self.identification.id)
        self.assertFalse(widget.export_btn.isEnabled())
        self.assertFalse(widget.import_btn.isEnabled())
        self.assertEqual(widget.table.rowCount(), 1)


if __name__ == "__main__":
    unittest.main()
