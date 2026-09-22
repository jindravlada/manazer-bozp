"""RISK-GROUP-MEASURES-2: relevance zásad bezpečné práce podle ohrožené skupiny."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QWidget
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="risk-group-measures-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL,
        _backfill_existing_measure_relevance,
        initialize_database,
    )

    initialize_database()

    from core.ai_oponentni.constants import AI_PEER_REVIEW_SCHEMA_VERSION_2_0
    from core.ai_oponentni.proposal_package_types import AiProposalPackageMeasure
    from core.database.session import get_session
    from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
        CoordinationPbpAttachmentService,
        merge_pbp_rules,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        EXISTING_MEASURE_RELEVANCE_LABEL,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_existing_measure_exposed_group import (
        HazardExistingMeasureExposedGroup,
    )
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
    from moduly.rizeni_rizik.modely.hazard_library_template_existing_measure_exposed_group import (
        HazardLibraryTemplateExistingMeasureExposedGroup,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
        PravidlaBezpecnePraceEdition,
        PravidlaBezpecnePraceEditionRule,
    )
    from moduly.rizeni_rizik.sluzby.existing_measure_relevance import (
        EXISTING_MEASURE_RELEVANCE_REQUIRED,
    )
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        ExposedTargetRef,
        hazard_group_ref,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_update_service import (
        hazard_catalog_instance_update_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        HazardExistingMeasureError,
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_working_copy import (
        HazardIdentificationWorkingCopy,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_apply_service import (
        hazard_library_template_apply_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        HazardLibraryTemplateExistingMeasureError,
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_import_service import (
        hazard_library_template_import_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
        bump_template_content_version,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
        HazardLibraryTemplateWorkingCopy,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        HazardRiskAssessmentError,
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
        pravidla_bezpecne_prace_edition_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.existing_measure_relevance_selector import (
        EXISTING_MEASURE_ACTIVE_GAP_OBJECT_NAME,
        EXISTING_MEASURE_ACTIVE_GAP_PX,
    )
    from moduly.rizeni_rizik.ui.hazard_existing_measure_dialog import (
        HazardExistingMeasureDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_measure_dialog import (
        HazardLibraryTemplateMeasureDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _keys(refs) -> set[tuple[str, int]]:
    return {ref.key for ref in refs}


class RiskGroupMeasures2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(PravidlaBezpecnePraceEditionRule))
            session.execute(delete(PravidlaBezpecnePraceEdition))
            session.execute(delete(HazardExistingMeasureExposedGroup))
            session.execute(delete(HazardLibraryTemplateExistingMeasureExposedGroup))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group_a = ensure_exposed_group("RGM2 řidiči")
        self.group_b = ensure_exposed_group("RGM2 dodavatelé")
        self.group_c = ensure_exposed_group("RGM2 obsluha")
        self.ref_a = hazard_group_ref(self.group_a.id)
        self.ref_b = hazard_group_ref(self.group_b.id)
        self.ref_c = hazard_group_ref(self.group_c.id)
        self.operation = settings_service.save_workplace(
            name="RGM2 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="RGM2 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_identification(self):
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="RGM2 stroj",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="RGM2 pád",
        )
        return identification, item, event

    def _create_assessment(self, identification, event, groups):
        return hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[group.id for group in groups],
            severity=RISK_SEVERITY_MODERATE,
        )

    def _create_catalog(self, groups):
        template = hazard_library_template_service.create_template(
            name="RGM2 katalog",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="RGM2 pád",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_ids=[group.id for group in groups],
            severity=RISK_SEVERITY_MODERATE,
        )
        return template, event, assessment

    def test_a_migration_instance_fills_all_groups(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure_1 = hazard_existing_measure_service.repository.add(
            HazardExistingMeasure(
                hazard_risk_assessment_id=assessment.id,
                description="Zásada 1",
                sort_order=1,
            )
        )
        measure_2 = hazard_existing_measure_service.repository.add(
            HazardExistingMeasure(
                hazard_risk_assessment_id=assessment.id,
                description="Zásada 2",
                sort_order=2,
            )
        )
        counts = _backfill_existing_measure_relevance()
        self.assertEqual(counts, LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL)
        self.assertEqual(counts["instance"], 4)
        expected = {self.ref_a.key, self.ref_b.key}
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure_1.id)),
            expected,
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure_2.id)),
            expected,
        )
        second = _backfill_existing_measure_relevance()
        self.assertEqual(second["instance"], 0)

    def test_b_migration_catalog_fills_all_groups(self) -> None:
        template, _event, assessment = self._create_catalog([self.group_a, self.group_b])
        measure_1 = hazard_library_template_existing_measure_service.repository.add(
            HazardLibraryTemplateExistingMeasure(
                template_assessment_id=assessment.id,
                description="Katalog 1",
                sort_order=1,
            )
        )
        measure_2 = hazard_library_template_existing_measure_service.repository.add(
            HazardLibraryTemplateExistingMeasure(
                template_assessment_id=assessment.id,
                description="Katalog 2",
                sort_order=2,
            )
        )
        counts = _backfill_existing_measure_relevance()
        self.assertEqual(counts["catalog"], 4)
        expected = {self.ref_a.key, self.ref_b.key}
        self.assertEqual(
            _keys(hazard_library_template_existing_measure_service.get_target_refs(measure_1.id)),
            expected,
        )
        self.assertEqual(
            _keys(hazard_library_template_existing_measure_service.get_target_refs(measure_2.id)),
            expected,
        )
        del template

    def test_c_new_measure_defaults_to_all_groups(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Nová zásada",
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key, self.ref_b.key},
        )

    def test_d_e_save_and_reopen_narrowed_relevance(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Zúžená zásada",
        )
        hazard_existing_measure_service.update_measure(
            measure.id,
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Zúžená zásada",
            target_refs=[self.ref_a],
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key},
        )
        dialog = HazardExistingMeasureDialog(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            measure=hazard_existing_measure_service.get_by_id(measure.id),
        )
        self.assertEqual(_keys(dialog.relevance.selected_refs()), {self.ref_a.key})
        self.assertEqual(
            [ref.key for ref in dialog.relevance.available_refs()],
            [self.ref_a.key, self.ref_b.key],
        )
        self.assertEqual(dialog.relevance._checkboxes[0][1].text(), self.group_a.name)
        dialog.close()

    def test_f_empty_relevance_rejected(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Musí mít skupinu",
        )
        with self.assertRaises(HazardExistingMeasureError) as raised:
            hazard_existing_measure_service.update_measure(
                measure.id,
                hazard_identification_id=identification.id,
                hazard_risk_assessment_id=assessment.id,
                description="Musí mít skupinu",
                target_refs=[],
            )
        self.assertEqual(str(raised.exception), EXISTING_MEASURE_RELEVANCE_REQUIRED)

    def test_g_adding_group_adds_relevance_to_existing_measures(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Původní zásada",
        )
        hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group_a.id, self.group_b.id, self.group_c.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key, self.ref_b.key, self.ref_c.key},
        )

    def test_h_removing_group_drops_only_relevance_links(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Zůstane",
        )
        hazard_risk_assessment_service.update_assessment(
            assessment.id,
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group_a.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        reloaded = hazard_existing_measure_service.get_by_id(measure.id)
        assert reloaded is not None
        self.assertEqual(reloaded.description, "Zůstane")
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key},
        )

    def test_i_catalog_apply_copies_exact_relevance(self) -> None:
        identification, _item, _event = self._create_identification()
        template, _event, assessment = self._create_catalog([self.group_a, self.group_b])
        shared = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Společná",
        )
        drivers = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Jen řidiči",
            target_refs=[self.ref_a],
        )
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        )
        instance_assessment = hazard_risk_assessment_service.repository.get_for_event(
            hazard_event_service.get_for_inventory_item(result.item.id)[0].id,
        )[0]
        by_text = {
            measure.description: measure
            for measure in hazard_existing_measure_service.get_for_assessment(
                instance_assessment.id
            )
        }
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(by_text["Společná"].id)),
            {self.ref_a.key, self.ref_b.key},
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(by_text["Jen řidiči"].id)),
            {self.ref_a.key},
        )
        del shared, drivers

    def test_j_update_from_master_copies_exact_relevance(self) -> None:
        identification, _item, _event = self._create_identification()
        template, _event, assessment = self._create_catalog([self.group_a, self.group_b])
        measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Master zásada",
            target_refs=[self.ref_a, self.ref_b],
        )
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        )
        hazard_library_template_existing_measure_service.update_measure(
            measure.id,
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Master zásada",
            target_refs=[self.ref_a],
        )
        bump_template_content_version(template.id)
        hazard_catalog_instance_update_service.update_from_master(result.item.id)
        instance_event = hazard_event_service.get_for_inventory_item(result.item.id)[0]
        instance_assessment = hazard_risk_assessment_service.repository.get_for_event(
            instance_event.id
        )[0]
        instance_measure = hazard_existing_measure_service.get_for_assessment(
            instance_assessment.id
        )[0]
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(instance_measure.id)),
            {self.ref_a.key},
        )

    def test_k_l_pbp_filters_by_measure_relevance(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        shared = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Společná PBP",
        )
        drivers = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Jen řidiči PBP",
            target_refs=[self.ref_a],
        )
        rules_a = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rules_b = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_b.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual(
            {rule.measure_id for rule in rules_a},
            {shared.id, drivers.id},
        )
        self.assertEqual({rule.measure_id for rule in rules_b}, {shared.id})

    def test_m_coordination_uses_same_generate_filter(self) -> None:
        source = inspect.getsource(
            CoordinationPbpAttachmentService.collect_rules_for_coordination
        )
        self.assertIn("pravidla_bezpecne_prace_service.generate", source)
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        shared = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Koordinace společná",
        )
        drivers = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Koordinace řidiči",
            target_refs=[self.ref_a],
        )
        collected = []
        for group in (self.group_a, self.group_b):
            collected.extend(
                pravidla_bezpecne_prace_service.generate(
                    endangered_group_id=group.id,
                    operation_id=self.operation.id,
                    workplace_id=self.workplace.id,
                )
            )
        merged = merge_pbp_rules(collected)
        self.assertEqual({rule.measure_id for rule in merged}, {shared.id, drivers.id})
        only_b = [
            rule
            for rule in collected
            if rule.measure_id == drivers.id
        ]
        self.assertEqual(len(only_b), 1)

    def test_n_historical_pbp_edition_unchanged(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        shared = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Historická společná",
        )
        drivers = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Historická řidiči",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_b.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual({rule.measure_id for rule in rules}, {shared.id, drivers.id})
        edition = pravidla_bezpecne_prace_edition_service.record_edition(
            operation_id=self.operation.id,
            endangered_group_id=self.group_b.id,
            workplace_id=self.workplace.id,
            rules=rules,
        )
        snapshot = [row.display_text for row in edition.rules]
        hazard_existing_measure_service.update_measure(
            drivers.id,
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Historická řidiči",
            target_refs=[self.ref_a],
        )
        stored = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            operation_id=self.operation.id,
            endangered_group_id=self.group_b.id,
            workplace_id=self.workplace.id,
        )
        assert stored is not None
        self.assertEqual([row.display_text for row in stored.rules], snapshot)
        current = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_b.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertEqual({rule.measure_id for rule in current}, {shared.id})

    def test_o_ai_new_measure_gets_all_groups(self) -> None:
        self.assertEqual(
            {item.name for item in fields(AiProposalPackageMeasure)},
            {"description", "note"},
        )
        self.assertEqual(AI_PEER_REVIEW_SCHEMA_VERSION_2_0, "2.0")
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Zásada z AI",
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key, self.ref_b.key},
        )
        template, _event, catalog_assessment = self._create_catalog(
            [self.group_a, self.group_b]
        )
        catalog_measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=catalog_assessment.id,
            description="Katalog AI",
        )
        self.assertEqual(
            _keys(
                hazard_library_template_existing_measure_service.get_target_refs(
                    catalog_measure.id
                )
            ),
            {self.ref_a.key, self.ref_b.key},
        )

    def test_p_q_deferred_save(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Odložené uložení",
        )
        original = _keys(hazard_existing_measure_service.get_target_refs(measure.id))
        wc = HazardIdentificationWorkingCopy.load(identification.id)
        wc.update_existing_measure(
            measure.id,
            hazard_risk_assessment_id=assessment.id,
            description="Odložené uložení",
            target_refs=[self.ref_a],
        )
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            original,
        )
        wc = HazardIdentificationWorkingCopy.load(identification.id)
        wc.update_existing_measure(
            measure.id,
            hazard_risk_assessment_id=assessment.id,
            description="Odložené uložení",
            target_refs=[self.ref_a],
        )
        wc.commit()
        self.assertEqual(
            _keys(hazard_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key},
        )

        template, _event, catalog_assessment = self._create_catalog(
            [self.group_a, self.group_b]
        )
        catalog_measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=catalog_assessment.id,
            description="Katalog odložené",
        )
        catalog_original = _keys(
            hazard_library_template_existing_measure_service.get_target_refs(
                catalog_measure.id
            )
        )
        catalog_wc = HazardLibraryTemplateWorkingCopy.load(template.id)
        catalog_wc.update_existing_measure(
            catalog_measure.id,
            template_id=template.id,
            template_assessment_id=catalog_assessment.id,
            description="Katalog odložené",
            target_refs=[self.ref_a],
        )
        self.assertEqual(
            _keys(
                hazard_library_template_existing_measure_service.get_target_refs(
                    catalog_measure.id
                )
            ),
            catalog_original,
        )
        catalog_wc.commit(bump_revision=False)
        self.assertEqual(
            _keys(
                hazard_library_template_existing_measure_service.get_target_refs(
                    catalog_measure.id
                )
            ),
            {self.ref_a.key},
        )

    def test_r_uniqueness_of_groups_unchanged(self) -> None:
        identification, _item, event = self._create_identification()
        self._create_assessment(identification, event, [self.group_a, self.group_b])
        with self.assertRaises(HazardRiskAssessmentError):
            self._create_assessment(identification, event, [self.group_a])

    def test_catalog_new_measure_and_empty_validation(self) -> None:
        template, _event, assessment = self._create_catalog([self.group_a, self.group_b])
        measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Katalog nová",
        )
        self.assertEqual(
            _keys(hazard_library_template_existing_measure_service.get_target_refs(measure.id)),
            {self.ref_a.key, self.ref_b.key},
        )
        with self.assertRaises(HazardLibraryTemplateExistingMeasureError) as raised:
            hazard_library_template_existing_measure_service.update_measure(
                measure.id,
                template_id=template.id,
                template_assessment_id=assessment.id,
                description="Katalog nová",
                target_refs=[],
            )
        self.assertEqual(str(raised.exception), EXISTING_MEASURE_RELEVANCE_REQUIRED)
        dialog = HazardLibraryTemplateMeasureDialog(
            template_id=template.id,
            template_assessment_id=assessment.id,
            measure=measure,
            measure_type="existing",
        )
        self.assertEqual(dialog.windowTitle() != "", True)
        self.assertIsNotNone(dialog.relevance)
        self.assertIn(EXISTING_MEASURE_RELEVANCE_LABEL, "Platí pro")
        dialog.close()

    def test_import_inventory_copies_relevance(self) -> None:
        identification, item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Import společná",
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Import řidiči",
            target_refs=[self.ref_a],
        )
        imported = hazard_library_template_import_service.import_inventory_item(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="RGM2 import",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        catalog_event = hazard_library_template_event_service.get_for_template(
            imported.template.id
        )[0]
        catalog_assessment = (
            hazard_library_template_assessment_service.repository.get_for_event(
                catalog_event.id
            )[0]
        )
        by_text = {
            measure.description: measure
            for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                catalog_assessment.id
            )
        }
        self.assertEqual(
            _keys(
                hazard_library_template_existing_measure_service.get_target_refs(
                    by_text["Import společná"].id
                )
            ),
            {self.ref_a.key, self.ref_b.key},
        )
        self.assertEqual(
            _keys(
                hazard_library_template_existing_measure_service.get_target_refs(
                    by_text["Import řidiči"].id
                )
            ),
            {self.ref_a.key},
        )

    def _assert_active_separated_from_relevance(self, dialog) -> None:
        dialog.show()
        self._app.processEvents()
        gap = dialog.findChild(QWidget, EXISTING_MEASURE_ACTIVE_GAP_OBJECT_NAME)
        self.assertIsNotNone(gap)
        self.assertEqual(gap.height(), EXISTING_MEASURE_ACTIVE_GAP_PX)
        self.assertFalse(dialog.relevance.isAncestorOf(dialog.active_checkbox))
        self.assertEqual(dialog.active_checkbox.text(), "Aktivní")
        last_group = dialog.relevance._checkboxes[-1][1]
        group_bottom = last_group.mapTo(dialog, last_group.rect().bottomLeft()).y()
        active_top = dialog.active_checkbox.mapTo(
            dialog,
            dialog.active_checkbox.rect().topLeft(),
        ).y()
        self.assertGreaterEqual(active_top - group_bottom, EXISTING_MEASURE_ACTIVE_GAP_PX)
        dialog.close()

    def test_active_checkbox_is_separated_from_relevance(self) -> None:
        identification, _item, event = self._create_identification()
        assessment = self._create_assessment(
            identification, event, [self.group_a, self.group_b]
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Oddělení Aktivní",
        )
        instance_dialog = HazardExistingMeasureDialog(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            measure=measure,
        )
        self._assert_active_separated_from_relevance(instance_dialog)

        template, _event, catalog_assessment = self._create_catalog(
            [self.group_a, self.group_b]
        )
        catalog_measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=catalog_assessment.id,
            description="Oddělení Aktivní katalog",
        )
        catalog_dialog = HazardLibraryTemplateMeasureDialog(
            template_id=template.id,
            template_assessment_id=catalog_assessment.id,
            measure=catalog_measure,
            measure_type="existing",
        )
        self._assert_active_separated_from_relevance(catalog_dialog)


if __name__ == "__main__":
    unittest.main()
