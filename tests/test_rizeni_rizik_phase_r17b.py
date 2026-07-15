"""Fáze R17b – obsah firemního vzoru."""

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

    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
        RISK_SEVERITY_SERIOUS,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_MANUAL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_item import (
        HazardLibraryTemplateItem,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        HazardLibraryTemplateAssessmentError,
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        HazardLibraryTemplateEventError,
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_item_service import (
        HazardLibraryTemplateItemError,
        hazard_library_template_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_content_widget import (
        HazardLibraryTemplateContentWidget,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryTemplateR17bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateItem))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group_a = ensure_exposed_group("Zaměstnanci")
        self.group_b = ensure_exposed_group("Externisté")
        self.template = hazard_library_template_service.create_template(
            name="Vzor R17b",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )

    def _create_item(self, name: str = "Vrtačka", *, active: bool = True):
        return hazard_library_template_item_service.create_item(
            template_id=self.template.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name=name,
            active=active,
        )

    def _create_event(self, item, name: str = "Kontakt s rotující částí"):
        return hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            template_item_id=item.id,
            name=name,
        )

    def _create_assessment(self, event, *, group_id=None, consequence="Úraz"):
        return hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=group_id or self.group_a.id,
            consequence=consequence,
            severity=RISK_SEVERITY_MODERATE,
        )

    def test_create_template_item(self) -> None:
        item = self._create_item()
        self.assertEqual(item.name, "Vrtačka")
        self.assertTrue(item.active)
        self.assertEqual(item.template_id, self.template.id)

    def test_reject_duplicate_template_item(self) -> None:
        self._create_item("Kladivo")
        with self.assertRaises(HazardLibraryTemplateItemError):
            self._create_item("  kladivo ")

    def test_create_template_event(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        self.assertEqual(event.name, "Kontakt s rotující částí")
        self.assertEqual(event.template_item_id, item.id)

    def test_reject_duplicate_template_event(self) -> None:
        item = self._create_item()
        self._create_event(item, name="Pád")
        with self.assertRaises(HazardLibraryTemplateEventError):
            self._create_event(item, name="  pád ")

    def test_create_assessment_with_exposed_group(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        assessment = self._create_assessment(event)
        self.assertEqual(assessment.exposed_group_id, self.group_a.id)
        self.assertEqual(assessment.severity, RISK_SEVERITY_MODERATE)

    def test_reject_duplicate_assessment(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        self._create_assessment(event)
        with self.assertRaises(HazardLibraryTemplateAssessmentError):
            self._create_assessment(event, group_id=self.group_a.id)

    def test_validate_consequence_and_severity(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        with self.assertRaises(HazardLibraryTemplateAssessmentError):
            hazard_library_template_assessment_service.create_assessment(
                template_id=self.template.id,
                template_event_id=event.id,
                exposed_group_id=self.group_a.id,
                consequence="   ",
                severity=RISK_SEVERITY_MODERATE,
            )
        with self.assertRaises(HazardLibraryTemplateAssessmentError):
            hazard_library_template_assessment_service.create_assessment(
                template_id=self.template.id,
                template_event_id=event.id,
                exposed_group_id=self.group_a.id,
                consequence="Úraz",
                severity="invalid",
            )

    def test_create_existing_measure(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        assessment = self._create_assessment(event)
        measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Ochranný kryt",
        )
        self.assertEqual(measure.description, "Ochranný kryt")

    def test_create_required_measure(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        assessment = self._create_assessment(event)
        measure = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Doplnit kryt",
        )
        self.assertEqual(measure.description, "Doplnit kryt")

    def test_existing_and_required_measures_are_separate(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        assessment = self._create_assessment(event)
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Stejný popis",
        )
        required = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Stejný popis",
        )
        self.assertIsNotNone(required.id)
        existing = hazard_library_template_existing_measure_service.get_for_assessment(
            assessment.id
        )
        required_rows = hazard_library_template_required_measure_service.get_for_assessment(
            assessment.id
        )
        self.assertEqual(len(existing), 1)
        self.assertEqual(len(required_rows), 1)

    def test_activate_and_deactivate_all_record_types(self) -> None:
        item = self._create_item()
        hazard_library_template_item_service.deactivate_item(item.id)
        reloaded_item = hazard_library_template_item_service.get_by_id(item.id)
        assert reloaded_item is not None
        self.assertFalse(reloaded_item.active)
        hazard_library_template_item_service.activate_item(item.id)

        event = self._create_event(item)
        hazard_library_template_event_service.deactivate_event(event.id)
        hazard_library_template_event_service.activate_event(event.id)

        assessment = self._create_assessment(event, group_id=self.group_b.id)
        hazard_library_template_assessment_service.deactivate_assessment(assessment.id)
        hazard_library_template_assessment_service.activate_assessment(assessment.id)

        existing = hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Kryt",
        )
        hazard_library_template_existing_measure_service.deactivate_measure(existing.id)
        hazard_library_template_existing_measure_service.activate_measure(existing.id)

        required = hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Nový kryt",
        )
        hazard_library_template_required_measure_service.deactivate_measure(required.id)
        hazard_library_template_required_measure_service.activate_measure(required.id)

    def test_filter_events_by_template_item(self) -> None:
        item_a = self._create_item("A")
        item_b = self._create_item("B")
        self._create_event(item_a, name="Událost A")
        self._create_event(item_b, name="Událost B")

        events_a = hazard_library_template_event_service.get_for_template_item(item_a.id)
        events_b = hazard_library_template_event_service.get_for_template_item(item_b.id)
        self.assertEqual(len(events_a), 1)
        self.assertEqual(events_a[0].name, "Událost A")
        self.assertEqual(len(events_b), 1)
        self.assertEqual(events_b[0].name, "Událost B")

    def test_filter_assessments_by_event(self) -> None:
        item = self._create_item()
        event_a = self._create_event(item, name="A")
        event_b = self._create_event(item, name="B")
        self._create_assessment(event_a, group_id=self.group_a.id)
        self._create_assessment(event_b, group_id=self.group_b.id)

        rows_a = hazard_library_template_assessment_service.get_for_event(event_a.id)
        rows_b = hazard_library_template_assessment_service.get_for_event(event_b.id)
        self.assertEqual(len(rows_a), 1)
        self.assertEqual(len(rows_b), 1)
        self.assertEqual(rows_a[0].assessment.exposed_group_id, self.group_a.id)
        self.assertEqual(rows_b[0].assessment.exposed_group_id, self.group_b.id)

    def test_content_change_bumps_version(self) -> None:
        initial_version = self.template.version_number
        self._create_item()
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, initial_version + 1)

        item = hazard_library_template_item_service.get_for_template(self.template.id)[0]
        self._create_event(item)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, initial_version + 2)

    def test_basics_update_does_not_bump_version(self) -> None:
        self._create_item()
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        version_after_content = reloaded.version_number

        hazard_library_template_service.update_template(
            self.template.id,
            name="Vzor R17b upraven",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            version_number=version_after_content,
        )
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, version_after_content)

    def test_reading_content_does_not_bump_version(self) -> None:
        item = self._create_item()
        event = self._create_event(item)
        self._create_assessment(event)

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        version_after_writes = reloaded.version_number

        hazard_library_template_item_service.get_for_template(self.template.id)
        hazard_library_template_event_service.get_for_template_item(item.id)
        hazard_library_template_assessment_service.get_for_event(event.id)
        hazard_library_template_service.get_by_id(self.template.id)

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, version_after_writes)

    def test_inactive_template_content_is_read_only(self) -> None:
        hazard_library_template_service.deactivate(self.template.id)
        widget = HazardLibraryTemplateContentWidget()
        widget.set_template(self.template.id, read_only=True)

        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.add_event_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
