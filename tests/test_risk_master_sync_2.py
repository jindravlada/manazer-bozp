"""RISK-MASTER-SYNC-2: náhrada stromu Master → instance a idempotentní M:N apply."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, select

_TMP = Path(tempfile.mkdtemp(prefix="risk-master-sync-2-"))
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
    from core.version import APP_VERSION
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
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
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        SOURCE_TYPE_ROLE,
        hazard_group_ref,
        role_ref,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_update_service import (
        hazard_catalog_instance_update_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
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
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
        bump_template_content_version,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _ref_tuples(refs) -> list[tuple[str, int]]:
    return [(ref.source_type, ref.source_id) for ref in refs]


def _sorted_ref_tuples(refs) -> list[tuple[str, int]]:
    return sorted(_ref_tuples(refs), key=lambda item: (item[0], item[1]))


class RiskMasterSync2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app_version = APP_VERSION

    def setUp(self) -> None:
        with get_session() as session:
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

        self.group_a = ensure_exposed_group("RMS2 skupina A")
        self.group_b = ensure_exposed_group("RMS2 skupina B")
        self.ref_a = hazard_group_ref(self.group_a.id)
        self.ref_b = hazard_group_ref(self.group_b.id)
        self.role = self._ensure_role("RMS2 role analog")
        self.ref_role = role_ref(self.role.id)

    def _create_site(self, name: str):
        operation = settings_service.save_workplace(
            name=f"RMS2 {name} provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name=f"RMS2 {name} pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        return hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

    def _ensure_role(self, name: str):
        for role in responsibility_role_service.get_all(include_inactive=True):
            if role.name == name:
                return role
        return responsibility_role_service.create_role(name=name)

    def _create_template_tree(self, *, name: str, measure_text: str):
        template = hazard_library_template_service.create_template(
            name=name,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="udalost M1",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[self.ref_a],
            severity=RISK_SEVERITY_MODERATE,
        )
        measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description=measure_text,
        )
        return template, event, assessment, measure

    def _instance_events(self, item_id: int) -> list[HazardEvent]:
        return hazard_event_service.get_for_inventory_item(item_id, include_inactive=True)

    def _instance_measure_texts(self, item_id: int) -> list[str]:
        texts: list[str] = []
        for event in self._instance_events(item_id):
            for assessment in hazard_risk_assessment_service.repository.get_for_event(
                event.id,
                include_inactive=True,
            ):
                for measure in hazard_existing_measure_service.get_for_assessment(
                    assessment.id,
                    include_inactive=True,
                ):
                    texts.append(measure.description)
        return texts

    def _instance_event_names(self, item_id: int) -> list[str]:
        return [event.name for event in self._instance_events(item_id)]

    def _assessment_group_rows(self, assessment_id: int) -> list[tuple[str, int]]:
        return _sorted_ref_tuples(
            hazard_risk_assessment_service.get_target_refs(assessment_id)
        )

    def _count_rows(self, model, **filters) -> int:
        with get_session() as session:
            stmt = select(model)
            for column, value in filters.items():
                stmt = stmt.where(getattr(model, column) == value)
            return len(list(session.scalars(stmt)))

    def _has_orphans(self) -> bool:
        with get_session() as session:
            checks = [
                session.execute(
                    select(HazardRiskAssessment.id).where(
                        ~HazardRiskAssessment.hazard_event_id.in_(select(HazardEvent.id))
                    )
                ).first(),
                session.execute(
                    select(HazardExistingMeasure.id).where(
                        ~HazardExistingMeasure.hazard_risk_assessment_id.in_(
                            select(HazardRiskAssessment.id)
                        )
                    )
                ).first(),
                session.execute(
                    select(HazardRiskAssessmentExposedGroup.id).where(
                        ~HazardRiskAssessmentExposedGroup.assessment_id.in_(
                            select(HazardRiskAssessment.id)
                        )
                    )
                ).first(),
                session.execute(
                    select(HazardExistingMeasureExposedGroup.id).where(
                        ~HazardExistingMeasureExposedGroup.measure_id.in_(
                            select(HazardExistingMeasure.id)
                        )
                    )
                ).first(),
            ]
        return any(row is not None for row in checks)

    def test_version_remains_403(self) -> None:
        self.assertEqual(APP_VERSION, "4.0.3")

    def test_apply_mn_groups_a_and_b_exactly_once(self) -> None:
        identification = self._create_site("ApplyAB")
        template = hazard_library_template_service.create_template(
            name="RMS2 zdroj AB",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="RMS2 událost AB",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[self.ref_a, self.ref_b],
            severity=RISK_SEVERITY_MODERATE,
        )
        item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        assessment = hazard_risk_assessment_service.repository.get_for_event(
            self._instance_events(item.id)[0].id,
            include_inactive=True,
        )[0]
        self.assertEqual(
            self._assessment_group_rows(assessment.id),
            _sorted_ref_tuples([self.ref_a, self.ref_b]),
        )
        self.assertEqual(
            self._count_rows(HazardRiskAssessmentExposedGroup, assessment_id=assessment.id),
            2,
        )

    def test_apply_mn_is_idempotent_after_parent_wipe_with_leftover_links(self) -> None:
        identification = self._create_site("Leftover")
        template = hazard_library_template_service.create_template(
            name="RMS2 leftover",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="RMS2 leftover událost",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[self.ref_a, self.ref_b],
            severity=RISK_SEVERITY_MODERATE,
        )
        first = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        first_assessment = hazard_risk_assessment_service.repository.get_for_event(
            self._instance_events(first.id)[0].id,
            include_inactive=True,
        )[0]
        self.assertEqual(
            self._count_rows(
                HazardRiskAssessmentExposedGroup,
                assessment_id=first_assessment.id,
            ),
            2,
        )

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        identification = self._create_site("Leftover2")
        template = hazard_library_template_service.create_template(
            name="RMS2 leftover 2",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="RMS2 leftover událost",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[self.ref_a, self.ref_b],
            severity=RISK_SEVERITY_MODERATE,
        )
        second = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        second_assessment = hazard_risk_assessment_service.repository.get_for_event(
            self._instance_events(second.id)[0].id,
            include_inactive=True,
        )[0]
        self.assertEqual(
            self._assessment_group_rows(second_assessment.id),
            _sorted_ref_tuples([self.ref_a, self.ref_b]),
        )
        self.assertEqual(
            self._count_rows(
                HazardRiskAssessmentExposedGroup,
                assessment_id=second_assessment.id,
            ),
            2,
        )

    def test_group_and_role_with_same_numeric_id_stay_distinct(self) -> None:
        from moduly.rizeni_rizik.sluzby.exposed_target_ref import ExposedTargetRef

        self.assertNotEqual(
            ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, 1).key,
            ExposedTargetRef(SOURCE_TYPE_ROLE, 1).key,
        )
        identification = self._create_site("GroupRole")
        template = hazard_library_template_service.create_template(
            name="RMS2 group-role",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="RMS2 GR",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[self.ref_a, self.ref_role],
            severity=RISK_SEVERITY_MODERATE,
        )
        item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        local_event = self._instance_events(item.id)[0]
        assessment = hazard_risk_assessment_service.repository.get_for_event(
            local_event.id,
            include_inactive=True,
        )[0]
        keys = _sorted_ref_tuples(
            hazard_risk_assessment_service.get_target_refs(assessment.id)
        )
        self.assertEqual(
            keys,
            _sorted_ref_tuples([self.ref_a, self.ref_role]),
        )
        self.assertEqual(len(keys), 2)
        self.assertEqual(len({key[0] for key in keys}), 2)

    def test_wc_sync_is_deferred_until_commit(self) -> None:
        identification = self._create_site("Hodonín")
        template, event, assessment, old_measure = self._create_template_tree(
            name="RMS2 strom",
            measure_text="zasada OLD",
        )
        item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        original_event_ids = {event.id for event in self._instance_events(item.id)}
        original_texts = self._instance_measure_texts(item.id)
        original_version = item.source_template_version

        hazard_library_template_existing_measure_service.deactivate_measure(old_measure.id)
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="zasada NEW",
        )
        event_m2 = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="udalost M2",
        )
        assessment_b = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event_m2.id,
            target_refs=[self.ref_b],
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment_b.id,
            description="zasada B1",
        )
        bump_template_content_version(template.id)
        master = hazard_library_template_service.get_by_id(template.id)
        assert master is not None
        new_version = master.version_number
        self.assertGreater(new_version, original_version)

        store = HazardIdentificationWorkingCopy.load(identification.id)
        store.sync_item_from_template(item.id)
        wc_item = store.get_item(item.id)
        assert wc_item is not None
        self.assertIn(item.id, store._replaced_from_master_item_ids)
        self.assertTrue(all(event.id < 0 for event in wc_item.events))
        self.assertEqual(
            sorted(event.name for event in wc_item.events),
            ["udalost M1", "udalost M2"],
        )
        wc_texts = [
            measure.description
            for event in wc_item.events
            for assessment_row in event.assessments
            for measure in assessment_row.existing_measures
        ]
        self.assertEqual(sorted(wc_texts), ["zasada B1", "zasada NEW"])

        db_item = hazard_inventory_item_service.get_by_id(item.id)
        assert db_item is not None
        self.assertEqual(db_item.source_template_version, original_version)
        self.assertEqual(
            {event.id for event in self._instance_events(item.id)},
            original_event_ids,
        )
        self.assertEqual(self._instance_measure_texts(item.id), original_texts)
        self.assertEqual(self._instance_event_names(item.id), ["udalost M1"])

        store.commit()
        self.assertEqual(store._replaced_from_master_item_ids, set())

        saved = hazard_inventory_item_service.get_by_id(item.id)
        assert saved is not None
        self.assertEqual(saved.source_template_id, template.id)
        self.assertEqual(saved.source_template_version, new_version)
        self.assertEqual(
            sorted(self._instance_event_names(item.id)),
            ["udalost M1", "udalost M2"],
        )
        self.assertEqual(
            sorted(self._instance_measure_texts(item.id)),
            ["zasada B1", "zasada NEW"],
        )
        self.assertNotIn("zasada OLD", self._instance_measure_texts(item.id))
        self.assertEqual(len(self._instance_events(item.id)), 2)
        self.assertFalse(self._has_orphans())

    def test_wc_sync_without_commit_leaves_revision_1(self) -> None:
        identification = self._create_site("Neukladat")
        template, _event, assessment, old_measure = self._create_template_tree(
            name="RMS2 neukladat",
            measure_text="zasada OLD",
        )
        item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        original_version = item.source_template_version
        original_event_ids = {event.id for event in self._instance_events(item.id)}

        hazard_library_template_existing_measure_service.deactivate_measure(old_measure.id)
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="zasada NEW",
        )
        bump_template_content_version(template.id)

        store = HazardIdentificationWorkingCopy.load(identification.id)
        store.sync_item_from_template(item.id)
        del store

        reloaded = hazard_inventory_item_service.get_by_id(item.id)
        assert reloaded is not None
        self.assertEqual(reloaded.source_template_id, template.id)
        self.assertEqual(reloaded.source_template_version, original_version)
        self.assertEqual(
            {event.id for event in self._instance_events(item.id)},
            original_event_ids,
        )
        self.assertEqual(self._instance_measure_texts(item.id), ["zasada OLD"])
        self.assertNotIn("zasada NEW", self._instance_measure_texts(item.id))

    def test_wc_sync_isolates_hodonin_from_breclav_and_master(self) -> None:
        template, _event, assessment, old_measure = self._create_template_tree(
            name="RMS2 izolace",
            measure_text="zasada OLD",
        )
        hodonin = self._create_site("Hodonín")
        breclav = self._create_site("Břeclav")
        hodonin_item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=hodonin.id,
            template_id=template.id,
        ).item
        breclav_item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=breclav.id,
            template_id=template.id,
        ).item
        original_master_event_name = hazard_library_template_event_service.get_for_template(
            template.id
        )[0].name

        hazard_library_template_existing_measure_service.deactivate_measure(old_measure.id)
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="zasada NEW",
        )
        event_m2 = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="udalost M2",
        )
        assessment_b = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event_m2.id,
            target_refs=[self.ref_b],
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment_b.id,
            description="zasada B1",
        )
        bump_template_content_version(template.id)

        store = HazardIdentificationWorkingCopy.load(hodonin.id)
        store.sync_item_from_template(hodonin_item.id)
        store.commit()

        hodonin_saved = hazard_inventory_item_service.get_by_id(hodonin_item.id)
        breclav_saved = hazard_inventory_item_service.get_by_id(breclav_item.id)
        master = hazard_library_template_service.get_by_id(template.id)
        assert hodonin_saved is not None
        assert breclav_saved is not None
        assert master is not None
        self.assertEqual(hodonin_saved.source_template_version, master.version_number)
        self.assertEqual(
            sorted(self._instance_event_names(hodonin_item.id)),
            ["udalost M1", "udalost M2"],
        )
        self.assertEqual(
            sorted(self._instance_measure_texts(hodonin_item.id)),
            ["zasada B1", "zasada NEW"],
        )
        self.assertEqual(breclav_saved.source_template_version, 1)
        self.assertEqual(self._instance_event_names(breclav_item.id), ["udalost M1"])
        self.assertEqual(self._instance_measure_texts(breclav_item.id), ["zasada OLD"])
        self.assertEqual(
            hazard_library_template_event_service.get_for_template(template.id)[0].name,
            original_master_event_name,
        )
        master_measures = {
            measure.description
            for master_event in hazard_library_template_event_service.get_for_template(
                template.id,
                include_inactive=True,
            )
            for master_assessment in hazard_library_template_assessment_service.repository.get_for_event(
                master_event.id,
                include_inactive=True,
            )
            for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                master_assessment.id,
                include_inactive=True,
            )
        }
        self.assertIn("zasada OLD", master_measures)
        self.assertIn("zasada NEW", master_measures)

    def test_update_from_master_still_replaces_tree(self) -> None:
        identification = self._create_site("DB cesta")
        template, event, assessment, old_measure = self._create_template_tree(
            name="RMS2 update_from_master",
            measure_text="zasada OLD",
        )
        item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        previous = item.source_template_version
        hazard_library_template_existing_measure_service.deactivate_measure(old_measure.id)
        hazard_library_template_existing_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="zasada NEW",
        )
        hazard_library_template_event_service.update_event(
            event.id,
            template_id=template.id,
            name="udalost M1 po revizi",
        )
        bump_template_content_version(template.id)
        result = hazard_catalog_instance_update_service.update_from_master(item.id)
        self.assertGreater(result.new_version, previous)
        saved = hazard_inventory_item_service.get_by_id(item.id)
        assert saved is not None
        self.assertEqual(saved.source_template_id, template.id)
        self.assertEqual(saved.source_template_version, result.new_version)
        self.assertEqual(self._instance_event_names(item.id), ["udalost M1 po revizi"])
        self.assertEqual(self._instance_measure_texts(item.id), ["zasada NEW"])
        self.assertFalse(self._has_orphans())

    def test_local_edit_commit_does_not_delete_existing_tree(self) -> None:
        identification = self._create_site("Lokální")
        template, _event, _assessment, _measure = self._create_template_tree(
            name="RMS2 lokalni",
            measure_text="zasada OLD",
        )
        item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=identification.id,
            template_id=template.id,
        ).item
        original_ids = {event.id for event in self._instance_events(item.id)}
        store = HazardIdentificationWorkingCopy.load(identification.id)
        wc_event = store.get_item(item.id).events[0]
        store.update_event(
            wc_event.id,
            inventory_item_id=item.id,
            name="udalost M1",
            description="lokální popis",
        )
        self.assertEqual(store._replaced_from_master_item_ids, set())
        store.commit()
        self.assertEqual(
            {event.id for event in self._instance_events(item.id)},
            original_ids,
        )
        self.assertEqual(self._instance_measure_texts(item.id), ["zasada OLD"])
        reloaded_event = self._instance_events(item.id)[0]
        self.assertEqual(reloaded_event.description, "lokální popis")
