"""UX-CATALOG-1 – filtr kategorií v dialogu Převzít z Katalogu."""

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
        HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_APPLY_ALL_CATEGORIES,
        HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE,
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
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_apply_to_inventory_dialog import (
        HazardLibraryApplyToInventoryDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class HazardLibraryApplyCategoryFilterUxCatalog1TestCase(unittest.TestCase):
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

        operation = settings_service.save_workplace(
            name="Provoz UX-CATALOG-1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Dílna UX-CATALOG-1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        self.group = ensure_exposed_group("Zaměstnanci")

    def _create_template(
        self,
        *,
        name: str,
        category: str = HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        active: bool = True,
    ):
        template = hazard_library_template_service.create_template(
            name=name,
            category=category,
            description="Popis",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            operation_ids=[],
        )
        if not active:
            hazard_library_template_service.deactivate(template.id)
            template = hazard_library_template_service.get_by_id(template.id)
        event = hazard_library_template_event_service.create_event(
            template_id=template.id,
            name=f"Událost {name}",
        )
        assessment = hazard_library_template_assessment_service.create_assessment(
            template_id=template.id,
            template_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Závěr",
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
            description="Existující",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=template.id,
            template_assessment_id=assessment.id,
            description="Potřebné",
        )
        return hazard_library_template_service.get_by_id(template.id)

    def _open_dialog(self) -> HazardLibraryApplyToInventoryDialog:
        return HazardLibraryApplyToInventoryDialog(
            None,
            hazard_identification_id=self.identification.id,
            default_category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )

    def _list_names(self, dialog: HazardLibraryApplyToInventoryDialog) -> set[str]:
        return {
            dialog.sources_list.item(i).text().split(" (", 1)[0]
            for i in range(dialog.sources_list.count())
        }

    def _set_category(self, dialog: HazardLibraryApplyToInventoryDialog, category: str | None) -> None:
        index = dialog.category_filter.findData(category)
        self.assertGreaterEqual(index, 0)
        dialog.category_filter.setCurrentIndex(index)

    def test_default_is_all_categories(self) -> None:
        self._create_template(name="Vrtačka")
        self._create_template(
            name="Montážní jáma",
            category=HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        )
        dialog = self._open_dialog()
        try:
            self.assertEqual(
                dialog.category_filter.currentText(),
                HAZARD_LIBRARY_APPLY_ALL_CATEGORIES,
            )
            self.assertIsNone(dialog.category_filter.currentData())
            self.assertEqual(
                self._list_names(dialog),
                {"Vrtačka", "Montážní jáma"},
            )
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=2, total=2),
            )
            # Combo obsahuje všechny kategorie + „Všechny“.
            from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
                hazard_source_category_service,
            )

            categories = hazard_source_category_service.get_all(include_inactive=True)
            self.assertEqual(
                dialog.category_filter.count(),
                1 + len(categories),
            )
            for category in categories:
                self.assertGreaterEqual(
                    dialog.category_filter.findData(category.code),
                    0,
                )
                self.assertGreaterEqual(
                    dialog.category_filter.findText(category.name),
                    0,
                )
        finally:
            dialog.close()

    def test_switch_category_and_back_updates_list_and_counts(self) -> None:
        self._create_template(name="Vrtačka")
        self._create_template(name="Fréza")
        self._create_template(
            name="Montážní jáma",
            category=HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        )
        self._create_template(
            name="Hluk",
            category=HAZARD_INVENTORY_CATEGORY_ENVIRONMENT,
        )
        dialog = self._open_dialog()
        try:
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=4, total=4),
            )

            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
            self.assertEqual(self._list_names(dialog), {"Vrtačka", "Fréza"})
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=2, total=4),
            )

            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_STRUCTURE)
            self.assertEqual(self._list_names(dialog), {"Montážní jáma"})
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=1, total=4),
            )

            self._set_category(dialog, None)
            self.assertEqual(
                self._list_names(dialog),
                {"Vrtačka", "Fréza", "Montážní jáma", "Hluk"},
            )
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=4, total=4),
            )
        finally:
            dialog.close()

    def test_applied_sources_still_hidden_with_all_categories(self) -> None:
        first = self._create_template(name="Vrtačka")
        self._create_template(
            name="Montážní jáma",
            category=HAZARD_INVENTORY_CATEGORY_STRUCTURE,
        )
        hazard_library_template_apply_service.apply_template(
            hazard_identification_id=self.identification.id,
            template_id=first.id,
        )
        dialog = self._open_dialog()
        try:
            self.assertEqual(self._list_names(dialog), {"Montážní jáma"})
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=1, total=1),
            )
            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
            self.assertEqual(self._list_names(dialog), set())
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=0, total=1),
            )
        finally:
            dialog.close()

    def test_include_inactive_still_works_with_category_filter(self) -> None:
        self._create_template(name="Aktivní", active=True)
        self._create_template(name="Neaktivní", active=False)
        self._create_template(
            name="Jáma",
            category=HAZARD_INVENTORY_CATEGORY_STRUCTURE,
            active=False,
        )
        dialog = self._open_dialog()
        try:
            self.assertEqual(self._list_names(dialog), {"Aktivní"})
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=1, total=1),
            )

            dialog.include_inactive.setChecked(True)
            self.assertEqual(
                self._list_names(dialog),
                {"Aktivní", "Neaktivní", "Jáma"},
            )
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=3, total=3),
            )

            self._set_category(dialog, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
            self.assertEqual(self._list_names(dialog), {"Aktivní", "Neaktivní"})
            self.assertEqual(
                dialog.shown_count_label.text(),
                HAZARD_LIBRARY_APPLY_SHOWN_COUNT_TEMPLATE.format(shown=2, total=3),
            )
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
