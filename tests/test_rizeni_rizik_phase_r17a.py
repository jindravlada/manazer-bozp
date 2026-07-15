"""Fáze R17a – základ firemní knihovny vzorů."""

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
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_PAGE_TITLE,
        HAZARD_LIBRARY_SCOPE_ALL,
        HAZARD_LIBRARY_SCOPE_MANUAL,
        HAZARD_LIBRARY_SCOPE_SELECTED,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        HazardLibraryTemplateError,
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage


class HazardLibraryTemplateR17aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.operation_a = settings_service.save_workplace(
            name="Vlečka A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.operation_b = settings_service.save_workplace(
            name="Vlečka B",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.operation_c = settings_service.save_workplace(
            name="Opravna kolejových vozidel",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna pod A",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation_a.id,
        )

    def test_create_template(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Pohyb po komunikacích",
            description="Obecný vzor",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.assertEqual(template.name, "Pohyb po komunikacích")
        self.assertTrue(template.active)
        self.assertEqual(
            hazard_library_template_service.get_operation_ids(template.id),
            [],
        )

    def test_edit_template(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Provoz na kolejích",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        updated = hazard_library_template_service.update_template(
            template.id,
            name="Provoz na kolejích – upraveno",
            description="Popis",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            version_number=2,
            note="Pozn.",
            active=True,
            operation_ids=[self.operation_a.id, self.operation_b.id],
        )
        assert updated is not None
        self.assertEqual(updated.name, "Provoz na kolejích – upraveno")
        self.assertEqual(updated.version_number, 2)
        self.assertEqual(
            hazard_library_template_service.get_operation_ids(updated.id),
            [self.operation_a.id, self.operation_b.id],
        )

    def test_activate_and_deactivate(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Dočasný vzor",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        self.assertTrue(hazard_library_template_service.deactivate(template.id))
        reloaded = hazard_library_template_service.get_by_id(template.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)
        self.assertTrue(hazard_library_template_service.activate(template.id))

    def test_reject_empty_name(self) -> None:
        with self.assertRaises(HazardLibraryTemplateError):
            hazard_library_template_service.create_template(
                name="   ",
                application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            )

    def test_reject_active_duplicate_name(self) -> None:
        hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        with self.assertRaises(HazardLibraryTemplateError):
            hazard_library_template_service.create_template(
                name="  portálový jeřáb ",
                application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            )

    def test_scope_all_operations(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Pohyb po komunikacích",
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        row = next(
            row
            for row in hazard_library_template_service.get_all_rows(include_inactive=True)
            if row.template.id == template.id
        )
        self.assertEqual(row.operation_count_label, "Všechny")
        with self.assertRaises(HazardLibraryTemplateError):
            hazard_library_template_service.update_template(
                template.id,
                name=template.name,
                application_scope=HAZARD_LIBRARY_SCOPE_ALL,
                operation_ids=[self.operation_a.id],
            )

    def test_scope_selected_operations(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Provoz na kolejích",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            operation_ids=[
                self.operation_a.id,
                self.operation_b.id,
                self.operation_c.id,
            ],
        )
        self.assertEqual(
            len(hazard_library_template_service.get_operation_ids(template.id)),
            3,
        )

    def test_selected_scope_requires_operation(self) -> None:
        with self.assertRaises(HazardLibraryTemplateError):
            hazard_library_template_service.create_template(
                name="Bez provozu",
                application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
                operation_ids=[],
            )

    def test_operation_must_be_operation_type(self) -> None:
        with self.assertRaises(HazardLibraryTemplateError):
            hazard_library_template_service.create_template(
                name="Špatný rozsah",
                application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
                operation_ids=[self.workplace.id],
            )

    def test_duplicate_operation_link_is_deduplicated(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Duplicitní vazba",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            operation_ids=[self.operation_a.id, self.operation_a.id],
        )
        self.assertEqual(
            hazard_library_template_service.get_operation_ids(template.id),
            [self.operation_a.id],
        )

    def test_scope_manual(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Práce s portálovým jeřábem",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        row = next(
            row
            for row in hazard_library_template_service.get_all_rows(include_inactive=True)
            if row.template.id == template.id
        )
        self.assertEqual(row.operation_count_label, "—")

    def test_scope_change_removes_invalid_links(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Změna rozsahu",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            operation_ids=[self.operation_a.id, self.operation_b.id],
        )
        updated = hazard_library_template_service.update_template(
            template.id,
            name="Změna rozsahu",
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        assert updated is not None
        self.assertEqual(
            hazard_library_template_service.get_operation_ids(updated.id),
            [],
        )

    def test_operation_count_in_rows(self) -> None:
        hazard_library_template_service.create_template(
            name="Počítání provozů",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            operation_ids=[self.operation_a.id, self.operation_c.id],
        )
        row = hazard_library_template_service.get_all_rows(include_inactive=True)[0]
        self.assertEqual(row.operation_count_label, "2")

    def test_library_page_exists(self) -> None:
        page = RizeniRizikPage()
        tab_texts = [page.tabs.tabText(index) for index in range(page.tabs.count())]
        self.assertIn(HAZARD_LIBRARY_PAGE_TITLE, tab_texts)
        self.assertIsInstance(page.library_page, HazardLibraryPage)

    def test_preview_scope_change_lists_removed_operations(self) -> None:
        template = hazard_library_template_service.create_template(
            name="Preview",
            application_scope=HAZARD_LIBRARY_SCOPE_SELECTED,
            operation_ids=[self.operation_a.id],
        )
        preview = hazard_library_template_service.preview_scope_change(
            template.id,
            new_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            operation_ids=[],
        )
        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertIn("Vlečka A", preview.removed_operation_names)


if __name__ == "__main__":
    unittest.main()
