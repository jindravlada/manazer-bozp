"""HOTFIX R18g.0 – verzování Master zdroje rizika po editační relaci."""

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
    )
    from moduly.rizeni_rizik.constants_library import (
        DEFAULT_HAZARD_LIBRARY_VERSION,
        HAZARD_LIBRARY_SCOPE_MANUAL,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
        bump_template_content_version,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import HazardLibraryTemplateDialog
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryTemplateVersionR18g0TestCase(unittest.TestCase):
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
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )

    def test_new_template_starts_at_version_one(self) -> None:
        self.assertEqual(self.template.version_number, DEFAULT_HAZARD_LIBRARY_VERSION)

    def test_multiple_events_in_session_bump_once(self) -> None:
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost 1",
        )
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost 2",
        )
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)

        bump_template_content_version(self.template.id)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)

    def test_multiple_measures_in_session_bump_once(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        for index in range(3):
            hazard_library_template_existing_measure_service.create_measure(
                template_id=self.template.id,
                template_assessment_id=assessment.id,
                description=f"Existující {index + 1}",
            )
        for index in range(2):
            hazard_library_template_required_measure_service.create_measure(
                template_id=self.template.id,
                template_assessment_id=assessment.id,
                description=f"Potřebné {index + 1}",
            )

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)

        bump_template_content_version(self.template.id)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)

    def test_combined_content_changes_bump_once(self) -> None:
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád břemene",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Těžký úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=assessment.id,
            description="Kontrola lan",
        )

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)

        bump_template_content_version(self.template.id)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)

    def test_open_editor_without_changes_does_not_bump(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog.reject()
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)

    def test_editor_session_bumps_once_on_close(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Nová událost",
        )
        dialog._on_content_changed()
        dialog.reject()

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)

    def test_separate_sessions_bump_incrementally(self) -> None:
        dialog_first = HazardLibraryTemplateDialog(template=self.template)
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Relace 1",
        )
        dialog_first._on_content_changed()
        dialog_first.reject()

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)

        dialog_second = HazardLibraryTemplateDialog(template=reloaded)
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Relace 2",
        )
        dialog_second._on_content_changed()
        dialog_second.reject()

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 3)

    def test_bulk_operation_bumps_once(self) -> None:
        """Simulace hromadného převzetí návrhů AI – více zápisů, jeden bump."""
        event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="AI událost 1",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            consequence="Úraz",
            severity=RISK_SEVERITY_MODERATE,
        )
        for index in range(21):
            hazard_library_template_required_measure_service.create_measure(
                template_id=self.template.id,
                template_assessment_id=assessment.id,
                description=f"AI opatření {index + 1}",
            )

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 1)

        bump_template_content_version(self.template.id)
        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)


if __name__ == "__main__":
    unittest.main()
