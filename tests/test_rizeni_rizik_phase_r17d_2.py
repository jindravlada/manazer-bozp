"""HOTFIX R17d.2 – pád dialogu události v Katalogu zdrojů rizik."""

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

    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_EVENT_DIALOG_TITLE,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_content_widget import (
        HazardLibraryTemplateContentWidget,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_event_dialog import (
        HazardLibraryTemplateEventDialog,
    )


class HazardLibraryTemplateEventDialogR17d2TestCase(unittest.TestCase):
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

        self.template = hazard_library_template_service.create_template(
            name="Portálový jeřáb",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )

    def test_dialog_creation_does_not_shadow_qt_event(self) -> None:
        dialog = HazardLibraryTemplateEventDialog(template_id=self.template.id)
        self.assertIsNone(dialog.template_event)
        self.assertTrue(callable(dialog.event))
        self.assertEqual(dialog.windowTitle(), HAZARD_LIBRARY_EVENT_DIALOG_TITLE)

    def test_create_event_via_dialog_accept(self) -> None:
        dialog = HazardLibraryTemplateEventDialog(template_id=self.template.id)
        dialog.name.setText("Pád břemene")
        dialog.description.setPlainText("Popis události")
        dialog.accept()

        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Pád břemene")
        self.assertEqual(events[0].description, "Popis události")

    def test_edit_event_via_dialog_accept(self) -> None:
        existing = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Původní název",
        )
        dialog = HazardLibraryTemplateEventDialog(
            template_id=self.template.id,
            event=existing,
        )
        dialog.name.setText("Upravený název")
        dialog.accept()

        reloaded = hazard_library_template_event_service.get_by_id(existing.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Upravený název")

    def test_content_widget_add_event_path(self) -> None:
        widget = HazardLibraryTemplateContentWidget()
        widget.set_template(self.template.id, read_only=False)

        dialog = HazardLibraryTemplateEventDialog(
            widget,
            template_id=self.template.id,
        )
        dialog.name.setText("Událost ze widgetu")
        dialog.accept()
        widget.refresh()

        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Událost ze widgetu")

    def test_content_widget_edit_event_path(self) -> None:
        existing = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Ke kontrole",
        )
        widget = HazardLibraryTemplateContentWidget()
        widget.set_template(self.template.id, read_only=False)
        widget._selected_event_id = existing.id
        widget._load_events_table()

        dialog = HazardLibraryTemplateEventDialog(
            widget,
            template_id=self.template.id,
            event=existing,
        )
        self.assertEqual(dialog.windowTitle(), HAZARD_LIBRARY_EVENT_DIALOG_TITLE)
        dialog.name.setText("Po kontrole")
        dialog.accept()
        widget.refresh()

        reloaded = hazard_library_template_event_service.get_by_id(existing.id)
        assert reloaded is not None
        self.assertEqual(reloaded.name, "Po kontrole")


if __name__ == "__main__":
    unittest.main()
