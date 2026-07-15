"""HOTFIX R18f.1 – výběr THP a ohrožených skupin."""

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
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
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
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
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
    from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
        HazardIdentificationBasicsWidget,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_assessment_dialog import (
        HazardLibraryTemplateAssessmentDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardSelectionHotfixR18f1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.active_worker = settings_service.save_worker(
            first_name="Jan",
            last_name="Novák",
            active=True,
        )
        self.inactive_worker = settings_service.save_worker(
            first_name="Petr",
            last_name="Starý",
            active=True,
        )
        settings_service.deactivate_worker(self.inactive_worker.id)

        operation = settings_service.save_workplace(
            name="Provoz A",
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
            responsible_person_id=self.active_worker.id,
        )
        self.inactive_identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=self.inactive_worker.id,
        )

        self.template = hazard_library_template_service.create_template(
            name="Jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        self.event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        self.active_group = ensure_exposed_group("Zaměstnanci")
        self.inactive_group = exposed_group_service.create_group(
            name="Dočasní pracovníci",
            active=True,
        )
        exposed_group_service.deactivate(self.inactive_group.id)

    def _selector_worker_ids(self, widget: HazardIdentificationBasicsWidget) -> set[int]:
        selector = widget.responsible_person
        return {
            selector.itemData(index)
            for index in range(selector.count())
            if isinstance(selector.itemData(index), int)
        }

    def test_responsible_person_lists_only_active_thp(self) -> None:
        widget = HazardIdentificationBasicsWidget()
        worker_ids = self._selector_worker_ids(widget)
        self.assertIn(self.active_worker.id, worker_ids)
        self.assertNotIn(self.inactive_worker.id, worker_ids)

    def test_responsible_person_prefills_existing_active_worker(self) -> None:
        widget = HazardIdentificationBasicsWidget()
        widget.load_identification(self.identification)
        self.assertEqual(
            widget.responsible_person.current_person_id(),
            self.active_worker.id,
        )
        self.assertEqual(
            widget.get_data()["responsible_person_id"],
            self.active_worker.id,
        )

    def test_responsible_person_shows_inactive_saved_worker_on_edit(self) -> None:
        fresh_widget = HazardIdentificationBasicsWidget()
        self.assertNotIn(self.inactive_worker.id, self._selector_worker_ids(fresh_widget))

        widget = HazardIdentificationBasicsWidget()
        widget.load_identification(self.inactive_identification)
        self.assertEqual(
            widget.responsible_person.current_person_id(),
            self.inactive_worker.id,
        )
        self.assertIn("(neaktivní)", widget.responsible_person.currentText())

    def test_catalog_assessment_dialog_opens_without_crash(self) -> None:
        dialog = HazardLibraryTemplateAssessmentDialog(
            template_id=self.template.id,
            template_event_id=self.event.id,
        )
        self.assertGreater(dialog.exposed_group.count(), 0)

    def test_catalog_assessment_dialog_loads_active_exposed_groups(self) -> None:
        dialog = HazardLibraryTemplateAssessmentDialog(
            template_id=self.template.id,
            template_event_id=self.event.id,
        )
        group_ids = {
            dialog.exposed_group.itemData(index)
            for index in range(dialog.exposed_group.count())
            if isinstance(dialog.exposed_group.itemData(index), int)
        }
        self.assertIn(self.active_group.id, group_ids)
        self.assertNotIn(self.inactive_group.id, group_ids)

    def test_catalog_assessment_can_be_created(self) -> None:
        dialog = HazardLibraryTemplateAssessmentDialog(
            template_id=self.template.id,
            template_event_id=self.event.id,
        )
        dialog.exposed_group.set_group_id(self.active_group.id)
        self.assertEqual(dialog.exposed_group.current_group_id(), self.active_group.id)
        dialog.consequence.setPlainText("Úraz končetiny")
        dialog.accept()

        rows = hazard_library_template_assessment_service.get_for_event(
            self.event.id,
            include_inactive=False,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].assessment.consequence, "Úraz končetiny")
        self.assertEqual(rows[0].assessment.exposed_group_id, self.active_group.id)


if __name__ == "__main__":
    unittest.main()
