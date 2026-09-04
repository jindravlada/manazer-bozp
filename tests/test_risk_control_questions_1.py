"""RISK-CONTROL-QUESTIONS-1: required_measures jako kontrolní otázky pro revizi rizik."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import delete, func, select

_TMP = Path(tempfile.mkdtemp(prefix="risk-control-questions-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QGroupBox

    from core.ai_oponentni.constants import (
        AI_MEASURE_REC_EDIT_EXISTING,
        AI_MEASURE_REC_EDIT_REQUIRED,
        AI_MEASURE_REC_NEW_REQUIRED,
        AI_PEER_REVIEW_PACKAGE_TYPE_LABELS,
        AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_REJECTED,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.proposal_package_types import AiProposalPackage
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.prompt_builder import (
        build_catalog_ai_instruction,
        build_catalog_source_ai_peer_review_prompt,
        catalog_universal_processing_rules,
        measure_formulation_style_section,
    )
    from core.ai_oponentni.sluzby.proposal_package_parser import (
        parse_ai_proposal_packages_response,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.database.session import get_session
    from core.shared.modely.finding import Finding
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        CONTROL_QUESTION_SINGULAR,
        CONTROL_QUESTIONS_COLUMN_TITLE,
        CONTROL_QUESTIONS_SECTION_TITLE,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        HAZARD_REQUIRED_MEASURE_DIALOG_TITLE,
        REQUIRED_MEASURE_TABLE_HEADERS,
        REQUIRED_MEASURES_TITLE,
        RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_CONTROL_QUESTION_EDIT_DIALOG_TITLE,
        CATALOG_AI_CONTROL_QUESTION_NEW_DIALOG_TITLE,
        CATALOG_AI_CONTROL_QUESTION_PROPOSED_REQUIRED,
        CATALOG_AI_MEASURE_REC_EDIT_DIALOG_TITLE,
        HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE,
        HAZARD_LIBRARY_SCOPE_ALL,
        HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
        HazardLibraryTemplateAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
        CATALOG_PROPOSAL_KIND_ASSESSMENT,
        CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
        CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
        classify_catalog_proposal,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        catalog_source_reference,
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
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
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.hazard_catalog_ai_measure_recommendation_edit_dialog import (
        HazardCatalogAiMeasureRecommendationEditDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_assessments_dialog import (
        _TemplateMeasuresSection,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_measure_dialog import (
        HazardLibraryTemplateMeasureDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_required_measure_dialog import (
        HazardRequiredMeasureDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_required_measures_widget import (
        HazardRequiredMeasuresWidget,
    )
    from moduly.ukoly.modely.task import Task
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _recommendation(
    *,
    rec_id: str,
    rec_type: str,
    proposed_text: str,
    target_export_id: str | None = None,
) -> AiProposalPackage:
    return AiProposalPackage(
        package_id=rec_id,
        package_type=rec_type,
        target_event_export_id=None,
        event=None,
        assessments=(),
        reasoning="Zdůvodnění.",
        target_export_id=target_export_id,
        proposed_text=proposed_text,
    )


def _count_rows(model) -> int:
    with get_session() as session:
        return int(session.scalar(select(func.count()).select_from(model)) or 0)


class RiskControlQuestions1NamingTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_02_no_migration_and_internal_names_stay(self) -> None:
        columns = set(_table_columns("hazard_required_measures"))
        self.assertTrue(
            {"id", "description", "title", "hazard_risk_assessment_id"} <= columns
        )
        self.assertEqual(
            HazardRequiredMeasure.__tablename__,
            "hazard_required_measures",
        )
        self.assertEqual(
            HazardLibraryTemplateRequiredMeasure.__tablename__,
            "hazard_library_template_required_measures",
        )
        self.assertEqual(AI_MEASURE_REC_EDIT_REQUIRED, "upravit_navazujici_opatreni")
        self.assertEqual(AI_MEASURE_REC_NEW_REQUIRED, "nove_navazujici_opatreni")
        enum_values = AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0["$defs"][
            "measure_recommendation"
        ]["properties"]["typ"]["enum"]
        self.assertEqual(
            enum_values,
            [
                "beze_zmen",
                "upravit_navazujici_opatreni",
                "upravit_zasady_bezpecne_prace",
                "nove_navazujici_opatreni",
            ],
        )
        self.assertEqual(
            set(_table_columns("hazard_control_questions")),
            set(),
        )

    def test_03_catalog_shows_control_questions_section(self) -> None:
        self.assertEqual(
            HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
            "Kontrolní otázky pro revizi rizik",
        )
        section = _TemplateMeasuresSection(
            title=HAZARD_LIBRARY_TEMPLATE_REQUIRED_MEASURES_TITLE,
            measure_type="required",
        )
        group = section.findChild(QGroupBox)
        assert group is not None
        self.assertEqual(group.title(), CONTROL_QUESTIONS_SECTION_TITLE)
        dialog = HazardLibraryTemplateMeasureDialog(
            template_id=1,
            template_assessment_id=1,
            measure_type="required",
        )
        self.assertEqual(
            dialog.windowTitle(),
            HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE,
        )
        self.assertIn(CONTROL_QUESTION_SINGULAR, HAZARD_LIBRARY_REQUIRED_MEASURE_DIALOG_TITLE)

    def test_04_identification_uses_the_same_meaning(self) -> None:
        self.assertEqual(REQUIRED_MEASURES_TITLE, CONTROL_QUESTIONS_SECTION_TITLE)
        self.assertEqual(HAZARD_REQUIRED_MEASURE_DIALOG_TITLE, CONTROL_QUESTION_SINGULAR)
        self.assertEqual(
            REQUIRED_MEASURE_TABLE_HEADERS[1],
            CONTROL_QUESTION_SINGULAR,
        )
        widget = HazardRequiredMeasuresWidget()
        group = widget.findChild(QGroupBox)
        assert group is not None
        self.assertEqual(group.title(), "Kontrolní otázky pro revizi rizik")
        dialog = HazardRequiredMeasureDialog(
            hazard_identification_id=1,
            hazard_risk_assessment_id=1,
        )
        self.assertEqual(dialog.windowTitle(), "Kontrolní otázka")

    def test_05_ai_queue_labels_required_as_control_questions(self) -> None:
        self.assertEqual(
            AI_PEER_REVIEW_PACKAGE_TYPE_LABELS[AI_MEASURE_REC_NEW_REQUIRED],
            "Nová kontrolní otázka",
        )
        self.assertEqual(
            AI_PEER_REVIEW_PACKAGE_TYPE_LABELS[AI_MEASURE_REC_EDIT_REQUIRED],
            "Úprava kontrolní otázky",
        )
        new_dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=_recommendation(
                rec_id="MR-NEW",
                rec_type=AI_MEASURE_REC_NEW_REQUIRED,
                proposed_text="Jsou kontroly prováděny ve stanovených termínech?",
                target_export_id="ASSESSMENT-001",
            )
        )
        self.assertEqual(
            new_dialog.windowTitle(),
            CATALOG_AI_CONTROL_QUESTION_NEW_DIALOG_TITLE,
        )
        self.assertEqual(new_dialog.type_field.text(), "Nová kontrolní otázka")
        self.assertTrue(new_dialog.type_field.isReadOnly())
        self.assertTrue(new_dialog.target_field.isReadOnly())
        edit_dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=_recommendation(
                rec_id="MR-EDIT",
                rec_type=AI_MEASURE_REC_EDIT_REQUIRED,
                proposed_text="Jsou OOPP používány?",
                target_export_id="REQUIRED-MEASURE-001",
            )
        )
        self.assertEqual(
            edit_dialog.windowTitle(),
            CATALOG_AI_CONTROL_QUESTION_EDIT_DIALOG_TITLE,
        )
        self.assertEqual(CATALOG_AI_CONTROL_QUESTION_PROPOSED_REQUIRED, (
            "Zadejte navrhované znění kontrolní otázky."
        ))

    def test_06_existing_measure_recommendations_stay_principles(self) -> None:
        self.assertEqual(
            AI_PEER_REVIEW_PACKAGE_TYPE_LABELS[AI_MEASURE_REC_EDIT_EXISTING],
            "Úprava Zásad bezpečné práce",
        )
        dialog = HazardCatalogAiMeasureRecommendationEditDialog(
            package=_recommendation(
                rec_id="MR-ZASADY",
                rec_type=AI_MEASURE_REC_EDIT_EXISTING,
                proposed_text="Používejte ochrannou přilbu.",
                target_export_id="EXISTING-MEASURE-001",
            )
        )
        self.assertEqual(
            dialog.windowTitle(),
            CATALOG_AI_MEASURE_REC_EDIT_DIALOG_TITLE,
        )
        self.assertEqual(dialog.type_field.text(), "Úprava Zásad bezpečné práce")
        self.assertEqual(
            classify_catalog_proposal(
                SimpleNamespace(area="Zásady bezpečné práce")
            ),
            CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
        )

    def test_07_ai_instructions_require_yes_no_not_applicable_questions(self) -> None:
        style = "\n".join(measure_formulation_style_section())
        prompt = build_catalog_source_ai_peer_review_prompt()
        instruction = json.dumps(build_catalog_ai_instruction(), ensure_ascii=False)
        for text in (style, prompt, instruction):
            self.assertIn("umožňovat odpověď Ano / Ne / Netýká se", text)
            self.assertIn("být formulována jako otázka", text)
            self.assertIn("Kontrolní otázka není úkol", text)
            self.assertNotIn("Navazující opatření nejsou pokyny zaměstnanci", text)
        schema_required = AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0["$defs"]["assessment"][
            "properties"
        ]["required_measures"]["description"]
        self.assertIn("Kontrolní otázky pro revizi rizik", schema_required)
        self.assertIn("required_measures", schema_required)

    def test_08_empty_catalog_allows_first_questions(self) -> None:
        rules = "\n".join(catalog_universal_processing_rules())
        self.assertIn(
            "navrhni spolu s nimi i první kontrolní otázky",
            rules,
        )
        style = "\n".join(measure_formulation_style_section())
        self.assertIn(
            "Pokud katalog neobsahuje žádné události, navrhni kontrolní otázky "
            "spolu s novými událostmi.",
            style,
        )

    def test_09_filled_catalog_allows_add_and_edit(self) -> None:
        style = "\n".join(measure_formulation_style_section())
        self.assertIn(
            "Pokud katalog již obsahuje data, hledej chybějící nebo nevhodně "
            "formulované kontrolní otázky.",
            style,
        )
        enum_values = AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0["$defs"][
            "measure_recommendation"
        ]["properties"]["typ"]["enum"]
        self.assertIn("nove_navazujici_opatreni", enum_values)
        self.assertIn("upravit_navazujici_opatreni", enum_values)

    def test_10_legacy_schema_2_0_types_remain_importable(self) -> None:
        payload = {
            "schema_version": "2.0",
            "source_reference": "CATALOG-1",
            "proposal_packages": [],
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-OLD-EDIT",
                    "typ": "upravit_navazujici_opatreni",
                    "target_export_id": "REQUIRED-MEASURE-001",
                    "proposed_text": "Jsou kontroly prováděny ve stanovených termínech?",
                    "reasoning": "Historická odpověď.",
                },
                {
                    "recommendation_id": "MR-OLD-NEW",
                    "typ": "nove_navazujici_opatreni",
                    "target_export_id": "ASSESSMENT-001",
                    "proposed_text": "Jsou OOPP používány?",
                    "reasoning": "Doplnění.",
                },
            ],
        }
        parsed = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference="CATALOG-1",
        )
        types = [pkg.package_type for pkg in parsed.packages]
        self.assertEqual(
            types,
            [AI_MEASURE_REC_EDIT_REQUIRED, AI_MEASURE_REC_NEW_REQUIRED],
        )
        self.assertTrue(all(pkg.target_export_id for pkg in parsed.packages))

    def test_control_question_area_is_not_classified_as_assessment(self) -> None:
        self.assertEqual(
            classify_catalog_proposal(
                SimpleNamespace(area="Kontrolní otázky pro revizi rizik")
            ),
            CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
        )
        self.assertEqual(
            classify_catalog_proposal(SimpleNamespace(area="Posouzení rizik")),
            CATALOG_PROPOSAL_KIND_ASSESSMENT,
        )


class RiskControlQuestions1DataTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz CQ1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna CQ1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = settings_service.save_worker(
            first_name="Petr",
            last_name="Revize",
        )
        self.group = ensure_exposed_group("Skupina CQ1")

    def _create_historical_required_measure(self) -> HazardRequiredMeasure:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Jeřáb CQ1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Pád břemene",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        return hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title="Provést revizi do 30. 6.",
        )

    def _prepare_catalog(self):
        template = hazard_library_template_service.create_template(
            name="Zdroj CQ1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Katalog pro kontrolní otázky.",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Pád břemene",
            description="Událost CQ1.",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="K ověření.",
        )
        existing = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=int(assessment.id),
            description="Používejte OOPP při manipulaci.",
        )
        required = hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=int(assessment.id),
            description="Kontrolujte uchycení břemene.",
        )
        export_dir = Path(tempfile.mkdtemp(prefix="risk-cq1-export-"))
        export_result = ai_peer_review_service.export_package(
            hazard_catalog_source_peer_review_provider,
            template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        export_id_map = json.loads(export_result.review.export_id_map_json or "{}")
        return template, assessment, existing, required, export_result.review, export_id_map

    def _export_id_for(self, export_id_map: dict, kind: str, entity_id: int) -> str:
        for export_id, meta in export_id_map.items():
            if meta.get("kind") == kind and int(meta.get("id")) == int(entity_id):
                return export_id
        self.fail(f"Export ID pro {kind}/{entity_id} nenalezeno")

    def test_01_existing_data_stay_unchanged(self) -> None:
        measure = self._create_historical_required_measure()
        reloaded = hazard_required_measure_service.get_by_id(measure.id)
        assert reloaded is not None
        self.assertEqual(reloaded.title, "Provést revizi do 30. 6.")
        self.assertEqual(reloaded.description, "Provést revizi do 30. 6.")
        self.assertEqual(reloaded.display_title(), "Provést revizi do 30. 6.")

        _template, _assessment, existing, required, _review, _export_id_map = (
            self._prepare_catalog()
        )
        stored_existing = hazard_library_template_existing_measure_service.get_by_id(
            existing.id
        )
        stored_required = hazard_library_template_required_measure_service.get_by_id(
            required.id
        )
        assert stored_existing is not None and stored_required is not None
        self.assertEqual(
            stored_existing.description,
            "Používejte OOPP při manipulaci.",
        )
        self.assertEqual(
            stored_required.description,
            "Kontrolujte uchycení břemene.",
        )

    def test_08_empty_catalog_export_includes_first_question_instruction(self) -> None:
        empty = hazard_library_template_service.create_template(
            name="Prázdný CQ1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        content = hazard_catalog_source_peer_review_provider.build_export_content(
            empty.id,
            options=AiPeerReviewExportOptions(),
        )
        dumped = json.dumps(content.zadani_json or {}, ensure_ascii=False)
        self.assertIn("první kontrolní otázky", dumped)

    def test_11_manual_incorporate_and_reject_still_work(self) -> None:
        template, assessment, existing, required, review, export_id_map = (
            self._prepare_catalog()
        )
        required_export = self._export_id_for(
            export_id_map, "required_measure", required.id
        )
        assessment_export = self._export_id_for(
            export_id_map, "assessment", assessment.id
        )
        existing_export = self._export_id_for(
            export_id_map, "existing_measure", existing.id
        )
        payload = {
            "schema_version": "2.0",
            "source_reference": catalog_source_reference(template.id),
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-EDIT-Q",
                    "typ": "upravit_navazujici_opatreni",
                    "target_export_id": required_export,
                    "proposed_text": "Je břemeno před zdvihem řádně uchyceno?",
                    "reasoning": "Otázka místo pokynu.",
                },
                {
                    "recommendation_id": "MR-NEW-Q",
                    "typ": "nove_navazujici_opatreni",
                    "target_export_id": assessment_export,
                    "proposed_text": "Jsou zaměstnanci mimo dosah zavěšeného břemene?",
                    "reasoning": "Chybějící ověření.",
                },
                {
                    "recommendation_id": "MR-SKIP-Q",
                    "typ": "nove_navazujici_opatreni",
                    "target_export_id": assessment_export,
                    "proposed_text": "Zamítnutá otázka.",
                    "reasoning": "Test zamítnutí.",
                },
                {
                    "recommendation_id": "MR-ZASADY",
                    "typ": "upravit_zasady_bezpecne_prace",
                    "target_export_id": existing_export,
                    "proposed_text": "Při manipulaci používejte ochrannou přilbu.",
                    "reasoning": "Úprava zásady.",
                },
            ],
        }
        packages = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=catalog_source_reference(template.id),
        ).packages
        ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=template.id,
            review_id=review.id,
            response_text=json.dumps(payload, ensure_ascii=False),
            ai_model="test-model",
            accepted=list(packages),
            rejected=[],
        )
        records = {
            record.package_id: record
            for record in ai_peer_review_service.get_packages_for_review(review.id)
        }
        before_required = [
            item.description
            for item in hazard_library_template_required_measure_service.get_for_assessment(
                int(assessment.id),
                include_inactive=False,
            )
        ]
        self.assertEqual(before_required, ["Kontrolujte uchycení břemene."])

        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=template.id,
            package_record_id=int(records["MR-EDIT-Q"].id),
        )
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=template.id,
            package_record_id=int(records["MR-NEW-Q"].id),
        )
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=template.id,
            package_record_id=int(records["MR-ZASADY"].id),
        )
        self.assertTrue(
            hazard_catalog_package_incorporate_service.reject_package(
                int(records["MR-SKIP-Q"].id)
            )
        )
        updated_required = hazard_library_template_required_measure_service.get_by_id(
            required.id
        )
        assert updated_required is not None
        self.assertEqual(
            updated_required.description,
            "Je břemeno před zdvihem řádně uchyceno?",
        )
        descriptions = [
            item.description
            for item in hazard_library_template_required_measure_service.get_for_assessment(
                int(assessment.id),
                include_inactive=False,
            )
        ]
        self.assertIn("Jsou zaměstnanci mimo dosah zavěšeného břemene?", descriptions)
        self.assertNotIn("Zamítnutá otázka.", descriptions)
        updated_existing = hazard_library_template_existing_measure_service.get_by_id(
            existing.id
        )
        assert updated_existing is not None
        self.assertEqual(
            updated_existing.description,
            "Při manipulaci používejte ochrannou přilbu.",
        )
        skipped = ai_peer_review_service.package_repository.get_by_id(
            int(records["MR-SKIP-Q"].id)
        )
        assert skipped is not None
        self.assertEqual(skipped.status, PACKAGE_STATUS_REJECTED)

    def test_12_incorporate_does_not_create_task_or_finding(self) -> None:
        template, _assessment, _existing, required, review, export_id_map = (
            self._prepare_catalog()
        )
        required_export = self._export_id_for(
            export_id_map, "required_measure", required.id
        )
        payload = {
            "schema_version": "2.0",
            "source_reference": catalog_source_reference(template.id),
            "measure_recommendations": [
                {
                    "recommendation_id": "MR-NO-TASK",
                    "typ": "upravit_navazujici_opatreni",
                    "target_export_id": required_export,
                    "proposed_text": "Jsou kontroly a údržba prováděny ve stanovených termínech?",
                    "reasoning": "Ověření zásady.",
                }
            ],
        }
        packages = parse_ai_proposal_packages_response(
            json.dumps(payload, ensure_ascii=False),
            expected_source_reference=catalog_source_reference(template.id),
        ).packages
        ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=template.id,
            review_id=review.id,
            response_text=json.dumps(payload, ensure_ascii=False),
            ai_model="test-model",
            accepted=list(packages),
            rejected=[],
        )
        records = ai_peer_review_service.get_packages_for_review(review.id)
        self.assertEqual(len(records), 1)
        tasks_before = _count_rows(Task)
        findings_before = _count_rows(Finding)
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=template.id,
            package_record_id=int(records[0].id),
        )
        self.assertEqual(_count_rows(Task), tasks_before)
        self.assertEqual(_count_rows(Finding), findings_before)

    def test_13_checklist_keeps_function_and_shows_new_labels(self) -> None:
        self.assertEqual(
            RISK_MEASURE_REVIEW_ITEM_TABLE_HEADERS[1],
            CONTROL_QUESTIONS_COLUMN_TITLE,
        )
        measure = self._create_historical_required_measure()
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].follow_up_measure_id, measure.id)
        self.assertEqual(rows[0].measure_title, "Provést revizi do 30. 6.")
        widget = HazardRequiredMeasuresWidget()
        self.assertEqual(
            widget.findChild(QGroupBox).title(),
            "Kontrolní otázky pro revizi rizik",
        )


if __name__ == "__main__":
    unittest.main()
