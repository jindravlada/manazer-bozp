"""Fáze R20e – ergonomie editoru Katalogu zdrojů rizik."""

from __future__ import annotations

import importlib
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

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QHeaderView, QLabel

    from core.widgets.dialog_utils import exec_maximized, prepare_work_dialog_maximized
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import (
        DEFAULT_HAZARD_LIBRARY_SCOPE,
        HAZARD_LIBRARY_COL_ACTIVE,
        HAZARD_LIBRARY_COLUMN_COUNT,
        HAZARD_LIBRARY_TABLE_HEADERS,
        HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE,
        HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME,
        HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE,
        HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE,
        HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage
    from moduly.rizeni_rizik.ui.hazard_library_save_from_inventory_dialog import (
        HazardLibrarySaveFromInventoryDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_content_widget import (
        HazardLibraryTemplateContentWidget,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions


class PhaseR20eTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.session import get_session

        with get_session() as session:
            session.query(HazardLibraryTemplateOperation).delete()
            session.query(HazardLibraryTemplateEvent).delete()
            session.query(HazardLibraryTemplate).delete()
            session.commit()

        self.template = hazard_library_template_service.create_template(
            name="Kladivo",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            description="Popis",
            application_scope=DEFAULT_HAZARD_LIBRARY_SCOPE,
        )
        hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name=(
                "Velmi dlouhý název nežádoucí události, který musí být čitelný "
                "nebo alespoň dostupný v tooltipu při zobrazení v tabulce"
            ),
        )

    def test_catalog_headers_without_scope(self) -> None:
        self.assertEqual(HAZARD_LIBRARY_COLUMN_COUNT, 5)
        joined = " | ".join(HAZARD_LIBRARY_TABLE_HEADERS)
        self.assertNotIn("Rozsah použití", joined)
        self.assertNotIn("Počet provozů", joined)
        self.assertIn("Kategorie", HAZARD_LIBRARY_TABLE_HEADERS)
        self.assertEqual(HAZARD_LIBRARY_TABLE_HEADERS[HAZARD_LIBRARY_COL_ACTIVE], "Aktivní")

    def test_editor_has_no_scope_ui(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        labels: list[str] = []
        for label in dialog.findChildren(QLabel):
            text = (label.text() or "").strip()
            if text:
                labels.append(text)
        joined = " ".join(labels)
        self.assertNotIn("Rozsah použití", joined)
        self.assertNotIn("Vybrané provozy", joined)
        self.assertFalse(hasattr(dialog, "scope_combo"))
        self.assertFalse(hasattr(dialog, "operations_list"))

    def test_save_new_source_without_scope_uses_manual(self) -> None:
        dialog = HazardLibraryTemplateDialog()
        dialog.name.setText("Nový zdroj bez rozsahu")
        dialog.category.setCurrentIndex(0)
        data = dialog.get_data()
        self.assertEqual(data["application_scope"], DEFAULT_HAZARD_LIBRARY_SCOPE)
        self.assertEqual(data["operation_ids"], [])

        with patch(
            "moduly.rizeni_rizik.ui.hazard_library_template_dialog.QMessageBox.information"
        ):
            dialog._save_all()
        saved = dialog.saved_template
        assert saved is not None
        self.assertEqual(saved.application_scope, DEFAULT_HAZARD_LIBRARY_SCOPE)
        self.assertEqual(
            hazard_library_template_service.get_operation_ids(saved.id),
            [],
        )

    def test_save_from_inventory_dialog_has_no_scope_ui(self) -> None:
        dialog = HazardLibrarySaveFromInventoryDialog(
            hazard_identification_id=1,
            inventory_item_id=1,
            default_name="Test",
        )
        labels = [
            (label.text() or "").strip()
            for label in dialog.findChildren(QLabel)
            if (label.text() or "").strip()
        ]
        joined = " ".join(labels)
        self.assertNotIn("Rozsah použití", joined)
        self.assertNotIn("Vybrané provozy", joined)

    def test_page_opens_editor_maximized(self) -> None:
        page = HazardLibraryPage()
        with (
            patch(
                "moduly.rizeni_rizik.ui.hazard_library_page.exec_maximized",
                wraps=exec_maximized,
            ) as mock_exec,
            patch.object(
                HazardLibraryTemplateDialog,
                "exec",
                return_value=0,
            ),
        ):
            page.new_template()
            page.open_template_editor(self.template.id)

        self.assertEqual(mock_exec.call_count, 2)
        for call in mock_exec.call_args_list:
            dialog = call.args[0]
            self.assertIsInstance(dialog, HazardLibraryTemplateDialog)

    def test_prepare_editor_maximized_sets_window_state(self) -> None:
        dialog = HazardLibraryTemplateDialog(template=self.template)
        prepare_work_dialog_maximized(dialog)
        QApplication.processEvents()
        self.assertTrue(dialog.windowState() & Qt.WindowState.WindowMaximized)

    def test_content_tables_use_full_width_column_modes(self) -> None:
        widget = HazardLibraryTemplateContentWidget()
        widget.set_template(self.template.id, read_only=False)
        QApplication.processEvents()

        events_header = widget.events_table.horizontalHeader()
        self.assertEqual(
            events_header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            events_header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE),
            QHeaderView.ResizeMode.Fixed,
        )
        self.assertEqual(
            widget.events_table.columnWidth(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_ACTIVE),
            70,
        )

        legal_header = widget.legal_links_table.horizontalHeader()
        self.assertEqual(
            legal_header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_REQUIREMENT),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            legal_header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_NOTE),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            legal_header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE),
            QHeaderView.ResizeMode.Fixed,
        )
        self.assertEqual(
            widget.legal_links_table.columnWidth(HAZARD_LIBRARY_TEMPLATE_LEGAL_LINK_COL_ACTIVE),
            70,
        )

        # Příprava šířky okna ověří, že roztahovací sloupec není „pár centimetrů“.
        widget.resize(900, 600)
        QApplication.processEvents()
        name_width = widget.events_table.columnWidth(HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME)
        self.assertGreater(name_width, 400)

    def test_long_event_name_has_tooltip(self) -> None:
        widget = HazardLibraryTemplateContentWidget()
        widget.set_template(self.template.id, read_only=False)
        name_item = widget.events_table.item(0, HAZARD_LIBRARY_TEMPLATE_EVENT_COL_NAME)
        assert name_item is not None
        self.assertTrue(name_item.toolTip())
        self.assertIn("Velmi dlouhý název", name_item.toolTip())

    def test_events_section_gets_larger_splitter_share(self) -> None:
        widget = HazardLibraryTemplateContentWidget()
        widget.resize(800, 700)
        QApplication.processEvents()
        sizes = widget.content_splitter.sizes()
        self.assertEqual(len(sizes), 2)
        self.assertGreater(sizes[0], sizes[1])
        # Splitter zůstává uživatelsky nastavitelný.
        self.assertTrue(widget.content_splitter.isEnabled())
        self.assertFalse(widget.content_splitter.childrenCollapsible())
        before = list(widget.content_splitter.sizes())
        widget.content_splitter.setSizes([120, 480])
        QApplication.processEvents()
        after = widget.content_splitter.sizes()
        self.assertNotEqual(before, after)
        self.assertLess(after[0], after[1])

    def test_ai_export_omits_application_scope(self) -> None:
        content = hazard_catalog_source_peer_review_provider.build_export_content(
            self.template.id,
            options=AiPeerReviewExportOptions(),
        )
        assert content.zadani_json is not None
        catalog_source = content.zadani_json["catalog_source"]
        risk_source = content.zadani_json["risk_source"]
        self.assertNotIn("application_scope", catalog_source)
        self.assertNotIn("application_scope_label", catalog_source)
        self.assertNotIn("application_scope", risk_source)
        self.assertNotIn("application_scope_label", risk_source)
        briefing = content.data_text or ""
        self.assertNotIn("Rozsah použití", briefing)


if __name__ == "__main__":
    unittest.main()
