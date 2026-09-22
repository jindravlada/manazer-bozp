"""RISK-INSTANCE-EDIT-1: lokální Upravit v provozu nesmí měnit Master."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="risk-instance-edit-1-"))
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
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import hazard_group_ref
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
    from moduly.rizeni_rizik.ui.hazard_existing_measure_dialog import (
        HazardExistingMeasureDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_item_dialog import (
        HazardInventoryItemDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _keys(refs) -> set[tuple[str, int]]:
    return {ref.key for ref in refs}


class RiskInstanceEdit1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

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

        self.group_a = ensure_exposed_group("RIE1 řidiči zemních strojů")
        self.group_b = ensure_exposed_group("RIE1 dodavatelé")
        self.ref_a = hazard_group_ref(self.group_a.id)
        self.ref_b = hazard_group_ref(self.group_b.id)
        self.template = hazard_library_template_service.create_template(
            name="RIE1 zemní stroj",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.catalog_event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="RIE1 pohyb stroje",
        )
        self.catalog_assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.catalog_event.id,
            exposed_group_ids=[self.group_a.id, self.group_b.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        self.catalog_measure = hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=self.catalog_assessment.id,
            description="MASTER",
            note="MASTER",
            active=True,
            target_refs=[self.ref_a, self.ref_b],
        )
        self.master_version = hazard_library_template_service.get_by_id(
            self.template.id
        ).version_number

        self.hodonin = self._create_site("Hodonín")
        self.breclav = self._create_site("Břeclav")
        self.hodonin_item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.hodonin.id,
            template_id=self.template.id,
        ).item
        self.breclav_item = hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.breclav.id,
            template_id=self.template.id,
        ).item

    def _create_site(self, name: str):
        operation = settings_service.save_workplace(
            name=f"RIE1 {name} provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name=f"RIE1 {name} pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        return hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )

    def _instance_measure(self, item_id: int) -> HazardExistingMeasure:
        event = hazard_event_service.get_for_inventory_item(item_id)[0]
        assessment = hazard_risk_assessment_service.repository.get_for_event(event.id)[0]
        return hazard_existing_measure_service.get_for_assessment(assessment.id)[0]

    def _assert_measure(
        self,
        measure,
        *,
        description: str,
        note: str,
        active: bool,
        refs: set[tuple[str, int]],
        service,
    ) -> None:
        self.assertEqual(measure.description, description)
        self.assertEqual(measure.note, note)
        self.assertEqual(bool(measure.active), active)
        self.assertEqual(_keys(service.get_target_refs(measure.id)), refs)

    def test_edit_selected_item_opens_local_instance_dialog(self) -> None:
        source = inspect.getsource(HazardInventoryWidget.edit_selected_item)
        self.assertIn("HazardInventoryItemDialog", source)
        self.assertNotIn("HazardLibraryTemplateDialog", source)
        self.assertNotIn("_on_master_edited", source)
        self.assertEqual(APP_VERSION, "4.0.3")

    def test_hodonin_edit_does_not_change_master_or_breclav(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.hodonin)
        widget = dialog.inventory_widget
        widget._current_category = HAZARD_INVENTORY_CATEGORY_EQUIPMENT
        widget.refresh()
        self.assertGreater(widget.table.rowCount(), 0)
        widget.table.selectRow(0)
        selected = widget._selected_item()
        assert selected is not None
        self.assertEqual(selected.source_template_id, self.template.id)

        opened: list[str] = []

        def _accept_local_editor(self_dialog):
            opened.append(type(self_dialog).__name__)
            self_dialog.accept()
            return self_dialog.result()

        with (
            patch.object(HazardInventoryItemDialog, "exec", _accept_local_editor),
            patch.object(
                widget,
                "_on_master_edited",
                side_effect=AssertionError("Upravit nesmí volat _on_master_edited."),
            ),
            patch.object(
                HazardIdentificationWorkingCopy,
                "sync_item_from_template",
                side_effect=AssertionError("Lokální editace nesmí synchronizovat z Masteru."),
            ),
            patch.object(
                HazardLibraryTemplateDialog,
                "__init__",
                side_effect=AssertionError("Upravit nesmí otevřít editor Masteru."),
            ),
        ):
            widget.edit_selected_item()

        self.assertEqual(opened, ["HazardInventoryItemDialog"])
        wc_item = dialog._identification_store.get_item(self.hodonin_item.id)
        assert wc_item is not None
        self.assertEqual(wc_item.source_template_id, self.template.id)

        wc_assessment = dialog._identification_store.get_items()[0].events[0].assessments[0]
        wc_measure = wc_assessment.existing_measures[0]
        measure_dialog = HazardExistingMeasureDialog(
            dialog,
            hazard_identification_id=self.hodonin.id,
            hazard_risk_assessment_id=wc_assessment.id,
            measure=wc_measure,
        )
        measure_dialog.description.setPlainText("HODONÍN")
        measure_dialog.note.setPlainText("HODONÍN")
        measure_dialog.active_checkbox.setChecked(False)
        for ref, checkbox in measure_dialog.relevance._checkboxes:
            checkbox.setChecked(ref.key == self.ref_a.key)
        measure_dialog.accept()
        self.assertEqual(measure_dialog.description.toPlainText(), "HODONÍN")
        measure_dialog.close()

        with patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        ):
            self.assertTrue(dialog._save_all())

        dialog._closing = True
        dialog.close()

        catalog = hazard_library_template_existing_measure_service.get_by_id(
            self.catalog_measure.id
        )
        assert catalog is not None
        self._assert_measure(
            catalog,
            description="MASTER",
            note="MASTER",
            active=True,
            refs={self.ref_a.key, self.ref_b.key},
            service=hazard_library_template_existing_measure_service,
        )
        master = hazard_library_template_service.get_by_id(self.template.id)
        assert master is not None
        self.assertEqual(master.version_number, self.master_version)

        reloaded_hodonin = hazard_inventory_item_service.get_by_id(self.hodonin_item.id)
        assert reloaded_hodonin is not None
        self.assertEqual(reloaded_hodonin.source_template_id, self.template.id)
        self.assertEqual(reloaded_hodonin.source_template_version, self.master_version)
        hodonin_measure = self._instance_measure(self.hodonin_item.id)
        self._assert_measure(
            hodonin_measure,
            description="HODONÍN",
            note="HODONÍN",
            active=False,
            refs={self.ref_a.key},
            service=hazard_existing_measure_service,
        )

        breclav_measure = self._instance_measure(self.breclav_item.id)
        self._assert_measure(
            breclav_measure,
            description="MASTER",
            note="MASTER",
            active=True,
            refs={self.ref_a.key, self.ref_b.key},
            service=hazard_existing_measure_service,
        )

    def test_explicit_update_from_master_still_copies_master_to_instance(self) -> None:
        hodonin_measure = self._instance_measure(self.hodonin_item.id)
        hazard_existing_measure_service.update_measure(
            hodonin_measure.id,
            hazard_identification_id=self.hodonin.id,
            hazard_risk_assessment_id=hodonin_measure.hazard_risk_assessment_id,
            description="HODONÍN",
            note="HODONÍN",
            active=False,
            target_refs=[self.ref_a],
        )
        hazard_library_template_existing_measure_service.update_measure(
            self.catalog_measure.id,
            template_id=self.template.id,
            template_assessment_id=self.catalog_assessment.id,
            description="MASTER po revizi",
            note="MASTER po revizi",
            active=True,
            target_refs=[self.ref_a, self.ref_b],
        )
        bump_template_content_version(self.template.id)
        result = hazard_catalog_instance_update_service.update_from_master(
            self.breclav_item.id
        )
        self.assertGreater(result.new_version, result.previous_version)

        catalog = hazard_library_template_existing_measure_service.get_by_id(
            self.catalog_measure.id
        )
        assert catalog is not None
        self._assert_measure(
            catalog,
            description="MASTER po revizi",
            note="MASTER po revizi",
            active=True,
            refs={self.ref_a.key, self.ref_b.key},
            service=hazard_library_template_existing_measure_service,
        )
        breclav_measure = self._instance_measure(self.breclav_item.id)
        self._assert_measure(
            breclav_measure,
            description="MASTER po revizi",
            note="MASTER po revizi",
            active=True,
            refs={self.ref_a.key, self.ref_b.key},
            service=hazard_existing_measure_service,
        )
        hodonin_after = self._instance_measure(self.hodonin_item.id)
        self._assert_measure(
            hodonin_after,
            description="HODONÍN",
            note="HODONÍN",
            active=False,
            refs={self.ref_a.key},
            service=hazard_existing_measure_service,
        )
        reloaded_hodonin = hazard_inventory_item_service.get_by_id(self.hodonin_item.id)
        assert reloaded_hodonin is not None
        self.assertEqual(reloaded_hodonin.source_template_id, self.template.id)


if __name__ == "__main__":
    unittest.main()
