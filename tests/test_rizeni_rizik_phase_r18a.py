"""Fáze R18a – převzetí zdroje rizika z katalogu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
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

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        DEFAULT_RISK_ASSESSMENT_STATUS,
        HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_SCOPE_ALL,
        HAZARD_LIBRARY_SCOPE_MANUAL,
        HAZARD_LIBRARY_SCOPE_SELECTED,
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
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
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
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryTemplateApplyR18aTestCase(unittest.TestCase):
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

        self.operation_a = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.operation_b = settings_service.save_workplace(
            name="Provoz B",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna A",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation_a.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=self.operation_a.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = self._create_template_with_content(
            name="Portálový jeřáb",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )

    def _create_template_with_content(
        self,
        *,
        name: str,
        application_scope: str,
        operation_ids: list[int] | None = None,
    ):
        template = hazard_library_template_service.create_template(
            name=name,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis z katalogu",
            application_scope=application_scope,
            operation_ids=operation_ids or [],
        )
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name="Pád břemene",
            note="Poznámka události",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Těžký úraz",
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Nutná opatření",
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
            hazard_library_template_existing_measure_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
            hazard_library_template_required_measure_service,
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
        return template

    def test_apply_template_creates_full_tree(self) -> None:
        result = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=self.template.id,
        )
        self.assertEqual(result.item.name, "Portálový jeřáb")
        self.assertEqual(result.item.category, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.assessment_count, 1)
        self.assertEqual(result.existing_measure_count, 1)
        self.assertEqual(result.required_measure_count, 1)

        items = hazard_inventory_item_service.get_for_identification(self.identification.id)
        self.assertEqual(len(items), 1)
        events = hazard_event_service.get_for_inventory_item(items[0].id)
        self.assertEqual(events[0].name, "Pád břemene")
        assessments = hazard_risk_assessment_service.repository.get_for_event(events[0].id)
        self.assertEqual(assessments[0].consequence, "Těžký úraz")
        self.assertEqual(assessments[0].assessment_status, DEFAULT_RISK_ASSESSMENT_STATUS)
        self.assertIsNone(assessments[0].completed_at)
        existing = hazard_existing_measure_service.get_for_assessment(assessments[0].id)
        required = hazard_required_measure_service.get_for_assessment(assessments[0].id)
        self.assertEqual(existing[0].description, "Ochranné zábradlí")
        self.assertEqual(required[0].description, "Doplnit zábradlí")

    def test_recommended_templates_for_operation(self) -> None:
        selected = self._create_template_with_content(
            name="Vrtačka",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            operation_ids=[self.operation_a.id],
        )
        manual = self._create_template_with_content(
            name="Bruska",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )

        groups = hazard_library_template_apply_service.get_template_groups(
            operation_id=self.operation_a.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        recommended_names = {template.name for template in groups.recommended}
        other_names = {template.name for template in groups.other}

        self.assertIn("Portálový jeřáb", recommended_names)
        self.assertIn("Vrtačka", recommended_names)
        self.assertIn("Bruska", other_names)
        self.assertNotIn("Bruska", recommended_names)
        self.assertNotIn(selected.name, other_names)

    def test_reject_duplicate_active_item_name(self) -> None:
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Portálový jeřáb",
        )
        with self.assertRaises(HazardLibraryTemplateApplyError):
            hazard_library_template_apply_service.apply_template(
                hazard_identification_id=self.identification.id,
                template_id=self.template.id,
            )

    def test_reject_archived_identification(self) -> None:
        hazard_identification_service.update_identification(
            self.identification.id,
            status=HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        )
        with self.assertRaises(HazardLibraryTemplateApplyError):
            hazard_library_template_apply_service.apply_template(
                hazard_identification_id=self.identification.id,
                template_id=self.template.id,
            )

    def test_inventory_widget_apply_button_enabled(self) -> None:
        widget = HazardInventoryWidget()
        widget.set_identification(
            self.identification.id,
            read_only=False,
            identification_status=self.identification.status,
        )
        self.assertTrue(widget.apply_from_library_btn.isEnabled())

    def test_inventory_widget_apply_button_disabled_for_archived(self) -> None:
        hazard_identification_service.update_identification(
            self.identification.id,
            status=HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        )
        widget = HazardInventoryWidget()
        widget.set_identification(
            self.identification.id,
            read_only=True,
            identification_status=HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        )
        self.assertFalse(widget.apply_from_library_btn.isEnabled())

    def test_inventory_widget_apply_button_disabled_for_completed(self) -> None:
        hazard_identification_service.update_identification(
            self.identification.id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        widget = HazardInventoryWidget()
        widget.set_identification(
            self.identification.id,
            read_only=True,
            identification_status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        self.assertFalse(widget.apply_from_library_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
