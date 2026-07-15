"""Fáze R17c – uložení položky analýzy do katalogu zdrojů rizik."""

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
        HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_ASSESSMENT_STATUS_COMPLETED,
        RISK_SEVERITY_MODERATE,
        can_save_inventory_item_to_library,
    )
    from moduly.rizeni_rizik.constants_library import (
        DEFAULT_HAZARD_LIBRARY_VERSION,
        HAZARD_LIBRARY_SCOPE_MANUAL,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
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
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_import_service import (
        HazardLibraryTemplateImportError,
        hazard_library_template_import_service,
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
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryTemplateImportR17cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete, func, select

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R17c",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R17c",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Posunovač")
        self.item = hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Portálový jeřáb",
            description="Popis položky",
        )
        self.event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Pád břemene",
            description="Popis události",
            note="Poznámka události",
        )
        self.assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=self.identification.id,
            hazard_event_id=self.event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Nutná opatření",
            note="Poznámka posouzení",
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        self.existing_measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Ochranné zábradlí",
            note="Existující",
        )
        self.required_measure = hazard_required_measure_service.create_measure(
            hazard_identification_id=self.identification.id,
            hazard_risk_assessment_id=self.assessment.id,
            description="Doplnit zábradlí",
            note="Potřebné",
        )

    def _import(self, **kwargs):
        defaults = {
            "hazard_identification_id": self.identification.id,
            "inventory_item_id": self.item.id,
            "name": "Portálový jeřáb",
        }
        defaults.update(kwargs)
        return hazard_library_template_import_service.import_inventory_item(**defaults)

    def test_import_single_inventory_item(self) -> None:
        result = self._import()
        self.assertEqual(result.template.name, "Portálový jeřáb")
        self.assertEqual(result.template.category, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        self.assertEqual(result.template.description, "Popis položky")

    def _template_event(self, result):
        return hazard_library_template_event_service.get_for_template(result.template.id)[0]

    def test_import_events(self) -> None:
        result = self._import()
        self.assertEqual(result.event_count, 1)
        events = hazard_library_template_event_service.get_for_template(result.template.id)
        self.assertEqual(events[0].name, "Pád břemene")
        self.assertEqual(events[0].note, "Poznámka události")

    def test_import_assessments(self) -> None:
        result = self._import()
        self.assertEqual(result.assessment_count, 1)
        template_event = self._template_event(result)
        rows = hazard_library_template_assessment_service.get_for_event(template_event.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].assessment.severity, RISK_SEVERITY_MODERATE)
        self.assertEqual(rows[0].assessment.conclusion, "Nutná opatření")

    def test_import_existing_measures(self) -> None:
        result = self._import()
        self.assertEqual(result.existing_measure_count, 1)
        assessment = hazard_library_template_assessment_service.get_for_event(
            self._template_event(result).id
        )[0].assessment
        measures = hazard_library_template_existing_measure_service.get_for_assessment(
            assessment.id
        )
        self.assertEqual(measures[0].description, "Ochranné zábradlí")

    def test_import_required_measures(self) -> None:
        result = self._import()
        self.assertEqual(result.required_measure_count, 1)
        assessment = hazard_library_template_assessment_service.get_for_event(
            self._template_event(result).id
        )[0].assessment
        measures = hazard_library_template_required_measure_service.get_for_assessment(
            assessment.id
        )
        self.assertEqual(measures[0].description, "Doplnit zábradlí")

    def test_preserve_exposed_group_id(self) -> None:
        result = self._import()
        assessment = hazard_library_template_assessment_service.get_for_event(
            self._template_event(result).id
        )[0].assessment
        self.assertEqual(assessment.exposed_group_id, self.group.id)

    def test_template_assessment_has_no_completion_fields(self) -> None:
        result = self._import()
        assessment = hazard_library_template_assessment_service.get_for_event(
            self._template_event(result).id
        )[0].assessment
        self.assertFalse(hasattr(assessment, "assessment_status"))
        self.assertFalse(hasattr(assessment, "completed_at"))

    def test_copy_only_active_records_by_default(self) -> None:
        hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Neaktivní událost",
            active=False,
        )
        result = self._import()
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.assessment_count, 1)

    def test_include_inactive_records(self) -> None:
        inactive_event = hazard_event_service.create_event(
            hazard_identification_id=self.identification.id,
            inventory_item_id=self.item.id,
            name="Neaktivní událost",
            active=False,
        )
        result = self._import(include_inactive=True)
        self.assertEqual(result.event_count, 2)
        events = hazard_library_template_event_service.get_for_template(
            result.template.id,
            include_inactive=True,
        )
        inactive = next(event for event in events if event.name == "Neaktivní událost")
        self.assertFalse(inactive.active)

    def test_reject_duplicate_active_template_name(self) -> None:
        hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        with self.assertRaises(HazardLibraryTemplateImportError):
            self._import()

    def test_rollback_on_error(self) -> None:
        from sqlalchemy import func, select

        from core.database.session import get_session

        with get_session() as session:
            broken = HazardRiskAssessment(
                hazard_event_id=self.event.id,
                exposed_group_id=None,
                exposed_group="",
                severity=RISK_SEVERITY_MODERATE,
                active=True,
            )
            session.add(broken)
            session.commit()

        with self.assertRaises(HazardLibraryTemplateImportError):
            self._import(name="Rollback test")

        with get_session() as session:
            count = session.scalar(
                select(func.count())
                .select_from(HazardLibraryTemplate)
                .where(HazardLibraryTemplate.name == "Rollback test")
            )
        self.assertEqual(int(count or 0), 0)

    def test_version_number_is_one(self) -> None:
        result = self._import()
        self.assertEqual(result.template.version_number, DEFAULT_HAZARD_LIBRARY_VERSION)

    def test_source_fields_are_saved(self) -> None:
        result = self._import()
        reloaded = hazard_library_template_service.get_by_id(result.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.source_identification_id, self.identification.id)
        self.assertEqual(reloaded.source_inventory_item_id, self.item.id)

    def test_allowed_for_completed_identification(self) -> None:
        hazard_identification_service.update_identification(
            self.identification.id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        self.assertTrue(
            can_save_inventory_item_to_library(HAZARD_IDENTIFICATION_STATUS_COMPLETED)
        )
        result = self._import(name="Vzor z dokončené")
        self.assertEqual(result.event_count, 1)

    def test_reject_archived_identification(self) -> None:
        hazard_identification_service.update_identification(
            self.identification.id,
            status=HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        )
        self.assertFalse(
            can_save_inventory_item_to_library(HAZARD_IDENTIFICATION_STATUS_ARCHIVED)
        )
        with self.assertRaises(HazardLibraryTemplateImportError):
            self._import()

    def test_inventory_widget_save_button_for_completed(self) -> None:
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
        widget.table.selectRow(0)
        widget._update_save_to_library_enabled()
        self.assertTrue(widget.save_to_library_btn.isEnabled())

    def test_inventory_widget_save_button_disabled_for_archived(self) -> None:
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
        widget.table.selectRow(0)
        widget._update_save_to_library_enabled()
        self.assertFalse(widget.save_to_library_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
