"""Fáze R20e.1 – ergonomie editorů odborného obsahu katalogu."""

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
    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_NARIZENI_VLADY
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        DEFAULT_HAZARD_LIBRARY_SCOPE,
        HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE,
        HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP,
        HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY,
        HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE,
        HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_usage_service import (
        hazard_catalog_legal_requirement_usage_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
        hazard_library_template_legal_link_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_assessments_dialog import (
        HazardLibraryTemplateAssessmentsDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_content_widget import (
        HazardLibraryTemplateContentWidget,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group
    from moduly.rizeni_rizik.ui.hazard_library_template_legal_link_dialog import (
        HazardLibraryTemplateLegalLinkDialog,
    )


class PhaseR20e1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.session import get_session
        from sqlalchemy import delete

        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateOperation))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

        self.template = hazard_library_template_service.create_template(
            name="Fréza",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=DEFAULT_HAZARD_LIBRARY_SCOPE,
        )
        self.event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Zachycení rotujícími částmi",
        )
        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Bezpečnost práce",
        )
        self.group = ensure_exposed_group("Zaměstnanci")

    def test_legal_link_dialog_is_compact_not_maximized(self) -> None:
        dialog = HazardLibraryTemplateLegalLinkDialog(template_id=self.template.id)
        self.assertEqual(dialog.width(), 700)
        self.assertEqual(dialog.height(), 350)
        self.assertFalse(dialog.windowState() & Qt.WindowState.WindowMaximized)

        labels = [
            (label.text() or "").strip()
            for label in dialog.findChildren(QLabel)
            if (label.text() or "").strip()
        ]
        joined = " ".join(labels)
        self.assertIn("Právní předpis", joined)
        self.assertIn("Poznámka", joined)
        self.assertNotIn("Proces", joined)
        self.assertFalse(hasattr(dialog, "process_combo"))
        self.assertFalse(hasattr(dialog, "requirement_combo"))

    def test_create_link_stores_document_only(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Proces",
            process_code="P-901",
        )
        link = hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_document_id=self.document.id,
            legal_requirement_id=process.id,
            note="test",
        )
        self.assertEqual(link.legal_document_id, self.document.id)
        self.assertIsNone(link.legal_requirement_id)

    def test_process_usage_is_derived_via_document(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Proces BOZP",
            process_code="P-902",
        )
        legal_requirement_service.create_requirement(
            title="Požadavek",
            process_code=legal_requirement_service.allocate_child_process_code(process.id),
            parent_requirement_id=process.id,
            legal_document_id=self.document.id,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_document_id=self.document.id,
        )
        # Přímá vazba zdroj→proces nevzniká; použití je přes předpis požadavku.
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_process(
            process.id,
        )
        self.assertEqual([item.template_id for item in sources], [self.template.id])

    def test_assessments_dialog_opens_maximized_from_content(self) -> None:
        widget = HazardLibraryTemplateContentWidget()
        widget.set_template(self.template.id, read_only=False)
        widget.events_table.selectRow(0)

        with (
            patch(
                "moduly.rizeni_rizik.ui.hazard_library_template_content_widget.exec_maximized",
                wraps=exec_maximized,
            ) as mock_exec,
            patch.object(
                HazardLibraryTemplateAssessmentsDialog,
                "exec",
                return_value=0,
            ),
        ):
            widget.open_assessments_for_selected_event()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertIsInstance(dialog, HazardLibraryTemplateAssessmentsDialog)

    def test_assessments_dialog_tables_use_full_width(self) -> None:
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        dialog = HazardLibraryTemplateAssessmentsDialog(
            template_id=self.template.id,
            template_event_id=self.event.id,
            event_name=self.event.name,
        )
        prepare_work_dialog_maximized(dialog)
        QApplication.processEvents()
        self.assertTrue(dialog.windowState() & Qt.WindowState.WindowMaximized)

        panel = dialog._panel
        header = panel.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_GROUP),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_SEVERITY),
            QHeaderView.ResizeMode.Fixed,
        )
        self.assertEqual(
            header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE),
            QHeaderView.ResizeMode.Fixed,
        )
        self.assertEqual(
            panel.table.columnWidth(HAZARD_LIBRARY_TEMPLATE_ASSESSMENT_COL_ACTIVE),
            70,
        )

        for section in (panel.existing_measures, panel.required_measures):
            measure_header = section.table.horizontalHeader()
            self.assertEqual(
                measure_header.sectionResizeMode(
                    HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_DESCRIPTION
                ),
                QHeaderView.ResizeMode.Stretch,
            )
            self.assertEqual(
                measure_header.sectionResizeMode(HAZARD_LIBRARY_TEMPLATE_MEASURE_COL_ACTIVE),
                QHeaderView.ResizeMode.Fixed,
            )

        self.assertEqual(panel.content_splitter.count(), 3)
        self.assertFalse(panel.content_splitter.childrenCollapsible())
        before = list(panel.content_splitter.sizes())
        panel.content_splitter.setSizes([100, 300, 300])
        QApplication.processEvents()
        self.assertNotEqual(before, panel.content_splitter.sizes())


if __name__ == "__main__":
    unittest.main()
