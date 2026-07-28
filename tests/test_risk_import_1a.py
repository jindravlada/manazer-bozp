"""RISK-IMPORT-1a: validace ohrožených skupin podle vazební tabulky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-import-1a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

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
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        SOURCE_TYPE_ROLE,
        ExposedTargetRef,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_apply_service import (
        HazardLibraryTemplateApplyError,
        hazard_library_template_apply_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskImport1aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
        from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
            HazardLibraryTemplateAssessmentExposedGroup,
        )
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        with get_session() as session:
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz IMPORT-1a",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna IMPORT-1a",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci IMPORT-1a")
        roles = responsibility_role_service.get_all(include_inactive=False)
        self.assertTrue(roles)
        self.role = roles[0]

    def _create_template(self, name: str = "Šablona IMPORT-1a"):
        return hazard_library_template_service.create_template(
            name=name,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
            operation_ids=[],
        )

    def _create_event(self, template_id: int, name: str = "Událost"):
        return hazard_library_template_event_service.create_event(
            template_id=template_id,
            name=name,
        )

    def test_apply_active_hazard_group_only_passes(self) -> None:
        template = self._create_template("Jen hazard_group")
        event = self._create_event(template.id)
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group.id)],
            severity=RISK_SEVERITY_MODERATE,
        )
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        self.assertEqual(result.assessment_count, 1)
        refs = hazard_risk_assessment_service.get_target_refs(
            hazard_risk_assessment_service.repository.get_for_event(
                hazard_event_service.get_for_inventory_item(result.item.id)[0].id,
            )[0].id,
        )
        self.assertEqual(
            [(ref.source_type, ref.source_id) for ref in refs],
            [(SOURCE_TYPE_HAZARD_GROUP, self.group.id)],
        )

    def test_apply_active_role_only_passes(self) -> None:
        template = self._create_template("Jen role")
        event = self._create_event(template.id)
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id)],
            severity=RISK_SEVERITY_MODERATE,
        )
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        self.assertEqual(result.assessment_count, 1)
        assessment = hazard_risk_assessment_service.repository.get_for_event(
            hazard_event_service.get_for_inventory_item(result.item.id)[0].id,
        )[0]
        self.assertIsNone(assessment.exposed_group_id)
        refs = hazard_risk_assessment_service.get_target_refs(assessment.id)
        self.assertEqual(
            [(ref.source_type, ref.source_id) for ref in refs],
            [(SOURCE_TYPE_ROLE, self.role.id)],
        )

    def test_apply_active_hazard_group_and_role_passes(self) -> None:
        template = self._create_template("Skupina i role")
        event = self._create_event(template.id)
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[
                ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group.id),
                ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id),
            ],
            severity=RISK_SEVERITY_MODERATE,
        )
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        self.assertEqual(result.assessment_count, 1)
        refs = hazard_risk_assessment_service.get_target_refs(
            hazard_risk_assessment_service.repository.get_for_event(
                hazard_event_service.get_for_inventory_item(result.item.id)[0].id,
            )[0].id,
        )
        self.assertEqual(
            {(ref.source_type, ref.source_id) for ref in refs},
            {
                (SOURCE_TYPE_HAZARD_GROUP, self.group.id),
                (SOURCE_TYPE_ROLE, self.role.id),
            },
        )

    def test_apply_active_without_refs_fails(self) -> None:
        template = self._create_template("Bez vazby")
        event = self._create_event(template.id)
        from core.database.session import get_session

        with get_session() as session:
            assessment = HazardLibraryTemplateAssessment(
                template_event_id=event.id,
                exposed_group_id=None,
                severity=RISK_SEVERITY_MODERATE,
                conclusion="",
                note="",
                active=True,
                sort_order=1,
            )
            session.add(assessment)
            session.commit()

        with self.assertRaises(HazardLibraryTemplateApplyError) as ctx:
            hazard_library_template_apply_service.apply_template(
                hazard_identification_id=self.identification.id,
                template_id=template.id,
            )
        self.assertIn("nemá přiřazenou ohroženou skupinu", str(ctx.exception))

    def test_apply_inactive_without_refs_does_not_block(self) -> None:
        template = self._create_template("Neaktivní bez vazby")
        event = self._create_event(template.id)
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id)],
            severity=RISK_SEVERITY_MODERATE,
        )
        from core.database.session import get_session

        with get_session() as session:
            orphan = HazardLibraryTemplateAssessment(
                template_event_id=event.id,
                exposed_group_id=None,
                severity=RISK_SEVERITY_MODERATE,
                conclusion="",
                note="",
                active=False,
                sort_order=2,
            )
            session.add(orphan)
            session.commit()

        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
            include_inactive=False,
        )
        self.assertEqual(result.assessment_count, 1)

    def test_apply_drazni_vozidla_like_source_with_roles_passes(self) -> None:
        """Převzetí zdroje s posouzeními typu role (jako katalog „Drážní vozidla“)."""
        template = self._create_template("Drážní vozidla")
        event = self._create_event(template.id, name="Sražení osobou")
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group.id)],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Skupina",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            target_refs=[ExposedTargetRef(SOURCE_TYPE_ROLE, self.role.id)],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Role",
        )

        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=template.id,
        )
        self.assertEqual(result.item.name, "Drážní vozidla")
        self.assertEqual(result.assessment_count, 2)

        event_row = hazard_event_service.get_for_inventory_item(result.item.id)[0]
        assessments = hazard_risk_assessment_service.repository.get_for_event(event_row.id)
        all_refs = {
            (ref.source_type, ref.source_id)
            for assessment in assessments
            for ref in hazard_risk_assessment_service.get_target_refs(assessment.id)
        }
        self.assertEqual(
            all_refs,
            {
                (SOURCE_TYPE_HAZARD_GROUP, self.group.id),
                (SOURCE_TYPE_ROLE, self.role.id),
            },
        )


if __name__ == "__main__":
    unittest.main()
