"""Fáze R19a – zdroje rizik ve Vazbách a použití u právních požadavků."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_NARIZENI_VLADY
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_usage_service import (
        hazard_catalog_legal_requirement_usage_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
        hazard_library_template_legal_link_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_navigation import open_hazard_library_template


class HazardCatalogLegalRequirementUsageR19aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="100",
            year=2000,
            title="Testovací předpis",
        )
        self.other_document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="101",
            year=2000,
            title="Druhý předpis",
        )
        self.process = legal_requirement_service.create_requirement(
            title="Proces BOZP",
            process_code="P-701",
        )
        self.child = legal_requirement_service.create_requirement(
            title="Požadavek školení",
            process_code=legal_requirement_service.allocate_child_process_code(self.process.id),
            parent_requirement_id=self.process.id,
            legal_document_id=self.document.id,
        )
        self.other_child = legal_requirement_service.create_requirement(
            title="Požadavek OOPP",
            process_code=legal_requirement_service.allocate_child_process_code(self.process.id),
            parent_requirement_id=self.process.id,
            legal_document_id=self.other_document.id,
        )
        self.template_a = hazard_library_template_service.create_template(
            name="Zdroj A",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.template_b = hazard_library_template_service.create_template(
            name="Zdroj B",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )

    def test_requirement_shows_linked_active_source(self) -> None:
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_requirement(
            self.child.id,
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].template_id, self.template_a.id)
        self.assertEqual(sources[0].name, "Zdroj A")

    def test_process_shows_source_from_active_child_requirement(self) -> None:
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_process(
            self.process.id,
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].template_id, self.template_a.id)

    def test_inactive_link_is_not_shown(self) -> None:
        link = hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        hazard_library_template_legal_link_service.deactivate_link(link.id)
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_requirement(
            self.child.id,
        )
        self.assertEqual(sources, ())

    def test_inactive_template_is_not_shown(self) -> None:
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        hazard_library_template_service.deactivate(self.template_a.id)
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_requirement(
            self.child.id,
        )
        self.assertEqual(sources, ())

    def test_process_deduplicates_sources_from_multiple_children(self) -> None:
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.other_document.id,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_b.id,
            legal_document_id=self.other_document.id,
        )
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_process(
            self.process.id,
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual(
            {item.template_id for item in sources},
            {self.template_a.id, self.template_b.id},
        )

    def test_widget_shows_source_for_requirement(self) -> None:
        from moduly.pravni_pozadavky.ui.legal_requirement_hazard_catalog_sources_widget import (
            LegalRequirementHazardCatalogSourcesWidget,
        )

        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        widget = LegalRequirementHazardCatalogSourcesWidget(
            requirement_id=self.child.id,
            usage_mode="requirement",
        )
        sources = widget.visible_sources()
        self.assertEqual(len(sources), 1)
        self.assertIn("Zdroje rizik (1)", widget._heading.text())

    def test_double_click_opens_source_in_catalog(self) -> None:
        from moduly.pravni_pozadavky.ui.legal_requirement_hazard_catalog_sources_widget import (
            LegalRequirementHazardCatalogSourcesWidget,
        )

        hazard_library_template_legal_link_service.create_link(
            template_id=self.template_a.id,
            legal_document_id=self.document.id,
        )
        widget = LegalRequirementHazardCatalogSourcesWidget(
            requirement_id=self.child.id,
            usage_mode="requirement",
        )
        widget.refresh()
        widget._table.selectRow(0)
        opened: list[int] = []

        with patch(
            "moduly.pravni_pozadavky.ui.legal_requirement_hazard_catalog_sources_widget.open_hazard_library_template",
            side_effect=lambda _parent, template_id: opened.append(template_id) or True,
        ):
            widget._open_selected_source()

        self.assertEqual(opened, [self.template_a.id])

    def test_navigation_helper_delegates_to_main_window(self) -> None:
        from PySide6.QtWidgets import QWidget

        host = QWidget()
        host.open_hazard_library_template = unittest.mock.MagicMock()
        child = QWidget(host)
        child.show()

        self.assertTrue(open_hazard_library_template(child, self.template_a.id))
        host.open_hazard_library_template.assert_called_once_with(self.template_a.id)


if __name__ == "__main__":
    unittest.main()
