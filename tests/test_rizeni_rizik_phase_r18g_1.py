"""HOTFIX R18g.1 – revize odborného obsahu místo verzí."""

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
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_ASSESSMENT_STATUS_COMPLETED,
        RISK_SEVERITY_MODERATE,
        format_inventory_item_source_label,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_COMPARE_WITH_MASTER_VERSION_NOTE,
        CATALOG_UPDATE_OFFER_INTRO,
        CATALOG_UPDATE_SUCCESS_TEXT,
        DEFAULT_HAZARD_LIBRARY_VERSION,
        HAZARD_LIBRARY_COL_VERSION,
        HAZARD_LIBRARY_REVISION_FORM_LABEL,
        HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
        HAZARD_LIBRARY_REVISION_REASON_FROM_IDENTIFICATION,
        HAZARD_LIBRARY_REVISION_REASON_LABELS,
        HAZARD_LIBRARY_REVISION_REASON_MANUAL,
        HAZARD_LIBRARY_REVISION_REASON_MASTER_UPDATE,
        HAZARD_LIBRARY_SCOPE_MANUAL,
        HAZARD_LIBRARY_TABLE_HEADERS,
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
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_import_service import (
        hazard_library_template_import_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_revision_service import (
        hazard_library_template_revision_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_version import (
        bump_template_content_version,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import HazardLibraryTemplateDialog
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryTemplateRevisionR18g1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateRevision))
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

        self.template = hazard_library_template_service.create_template(
            name="Zdroj R18g.1",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        self.group = ensure_exposed_group("Skupina R18g.1")

    def test_catalog_uses_revision_terminology(self) -> None:
        self.assertEqual(HAZARD_LIBRARY_TABLE_HEADERS[HAZARD_LIBRARY_COL_VERSION], "Revize")
        self.assertNotIn("Verze", HAZARD_LIBRARY_TABLE_HEADERS)
        self.assertIn("revizi", CATALOG_COMPARE_WITH_MASTER_VERSION_NOTE)
        self.assertIn("revize", CATALOG_UPDATE_OFFER_INTRO)
        self.assertIn("Revize instance", CATALOG_UPDATE_SUCCESS_TEXT)
        self.assertNotIn("Verze instance", CATALOG_UPDATE_SUCCESS_TEXT)

    def test_dialog_shows_revision_number(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        self.assertEqual(dialog.version_number.value(), self.template.version_number)
        self.assertTrue(dialog.version_number.isReadOnly())
        self.assertEqual(HAZARD_LIBRARY_REVISION_FORM_LABEL, "Revize:")

    def test_manual_content_change_records_revision_history(self) -> None:
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Událost",
        )
        bump_template_content_version(self.template.id)

        rows = hazard_library_template_revision_service.get_rows(self.template.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].revision_number, 2)
        self.assertEqual(
            rows[0].reason_label,
            HAZARD_LIBRARY_REVISION_REASON_LABELS[HAZARD_LIBRARY_REVISION_REASON_MANUAL],
        )

        reloaded = hazard_library_template_service.get_by_id(self.template.id)
        assert reloaded is not None
        self.assertEqual(reloaded.version_number, 2)

    def test_import_records_revision_with_identification_reason(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz R18g.1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna R18g.1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Importovaný zdroj",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Událost importu",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Opatření",
        )

        result = hazard_library_template_import_service.import_inventory_item(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Importovaný zdroj",
        )

        self.assertEqual(result.template.version_number, DEFAULT_HAZARD_LIBRARY_VERSION)
        rows = hazard_library_template_revision_service.get_rows(result.template.id)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].revision_number, 1)
        self.assertEqual(
            rows[0].reason_label,
            HAZARD_LIBRARY_REVISION_REASON_LABELS[
                HAZARD_LIBRARY_REVISION_REASON_FROM_IDENTIFICATION
            ],
        )

    def test_automatic_reason_labels(self) -> None:
        self.assertEqual(
            hazard_library_template_revision_service.format_reason_label(
                HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
            ),
            "Převzaty návrhy AI",
        )
        self.assertEqual(
            hazard_library_template_revision_service.format_reason_label(
                HAZARD_LIBRARY_REVISION_REASON_MASTER_UPDATE,
            ),
            "Aktualizace z Master",
        )

    def test_ai_export_uses_revision_label(self) -> None:
        built = hazard_catalog_source_peer_review_provider._build_hierarchy(self.template)
        hierarchy = {
            "catalog_source": built["catalog_source"],
            "risk_source": built["risk_source"],
        }
        text = hazard_catalog_source_peer_review_provider._hierarchy_to_data_text(hierarchy)
        self.assertIn(f"Revize: {self.template.version_number}", text)
        self.assertNotIn(f"Verze: {self.template.version_number}", text)

    def test_inventory_source_label_uses_revision(self) -> None:
        label = format_inventory_item_source_label(
            source_template_id=12,
            source_template_version=3,
        )
        self.assertEqual(label, "Katalog zdrojů rizik (ID 12, revize 3)")


if __name__ == "__main__":
    unittest.main()
