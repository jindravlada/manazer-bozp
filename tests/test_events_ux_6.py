"""EVENTS-UX-6: našeptávání místa z pracovišť."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCompleter

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

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.schuzky.constants import STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.schuzky.ui.meeting_location_typeahead import (
        LOCATION_PATH_SEPARATOR,
        MeetingLocationTypeahead,
        build_workplace_location_suggestions,
        workplace_location_path,
    )


class EventsUx6TestCase(unittest.TestCase):
    _seq = 0

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        EventsUx6TestCase._seq += 1
        suffix = f" UX6-{self._seq}"

        self.operation = settings_service.save_workplace(
            name=f"Provoz B{suffix}",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
            active=True,
        )
        self.workplace = settings_service.save_workplace(
            name=f"Vlečka{suffix}",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
            active=True,
        )
        self.part = settings_service.save_workplace(
            name=f"Kolejiště{suffix}",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
            active=True,
        )
        self.expected_operation = f"Provoz B{suffix}"
        self.expected_workplace = (
            f"Provoz B{suffix}{LOCATION_PATH_SEPARATOR}Vlečka{suffix}"
        )
        self.expected_part = (
            f"Provoz B{suffix}{LOCATION_PATH_SEPARATOR}Vlečka{suffix}"
            f"{LOCATION_PATH_SEPARATOR}Kolejiště{suffix}"
        )

    def test_path_for_operation_workplace_and_part(self) -> None:
        items = settings_service.get_workplaces(False)
        by_id = {int(item.id): item for item in items}
        self.assertEqual(
            workplace_location_path(self.operation, by_id),
            self.expected_operation,
        )
        self.assertEqual(
            workplace_location_path(self.workplace, by_id),
            self.expected_workplace,
        )
        self.assertEqual(
            workplace_location_path(self.part, by_id),
            self.expected_part,
        )

    def test_suggestions_include_full_paths(self) -> None:
        labels = {label for label, _ in build_workplace_location_suggestions()}
        self.assertIn(self.expected_operation, labels)
        self.assertIn(self.expected_workplace, labels)
        self.assertIn(self.expected_part, labels)

    def test_typeahead_suggests_by_any_name_part(self) -> None:
        selector = MeetingLocationTypeahead()
        completer = selector.completer()
        self.assertIsInstance(completer, QCompleter)
        self.assertEqual(completer.filterMode(), Qt.MatchFlag.MatchContains)

        completer.setCompletionPrefix("Kolej")
        model = completer.completionModel()
        matches = [
            model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(model.rowCount())
        ]
        self.assertTrue(any(self.expected_part == m for m in matches))

        completer.setCompletionPrefix(f"Provoz B UX6-{self._seq}")
        model = completer.completionModel()
        matches = [
            model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(model.rowCount())
        ]
        self.assertTrue(any(self.expected_operation == m for m in matches))
        self.assertTrue(any(self.expected_part == m for m in matches))

        completer.setCompletionPrefix(f"Vlečka UX6-{self._seq}")
        model = completer.completionModel()
        matches = [
            model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(model.rowCount())
        ]
        self.assertTrue(any(self.expected_workplace == m for m in matches))

    def test_save_selected_suggestion(self) -> None:
        dialog = MeetingDialog()
        dialog.title_edit.setText("Kontrola kolejiště")
        starts = datetime.now() + timedelta(days=2)
        dialog.starts_at_edit.set_datetime(starts)
        dialog.ends_at_edit.set_datetime(starts + timedelta(hours=1))
        dialog.status_combo.setCurrentText(STATUS_PLANNED)
        dialog.location_edit.set_location_text(self.expected_part)

        data = dialog.get_data()
        self.assertEqual(data["location"], self.expected_part)
        self.assertEqual(dialog.location_edit.current_workplace_id(), self.part.id)

        meeting = meeting_service.create_meeting(**data)
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.location, self.expected_part)

        again = MeetingDialog(meeting=reloaded)
        self.assertEqual(again.location_edit.display_text(), self.expected_part)

    def test_save_custom_location_text(self) -> None:
        custom = "Hotel Grand, nám. Míru 1 / Online Teams"
        dialog = MeetingDialog()
        dialog.title_edit.setText("Externí jednání")
        starts = datetime.now() + timedelta(days=3)
        dialog.starts_at_edit.set_datetime(starts)
        dialog.ends_at_edit.set_datetime(starts + timedelta(hours=1))
        dialog.location_edit.set_location_text(custom)

        self.assertIsNone(dialog.location_edit.current_workplace_id())
        data = dialog.get_data()
        self.assertEqual(data["location"], custom)

        meeting = meeting_service.create_meeting(**data)
        reloaded = meeting_service.get_by_id(meeting.id)
        assert reloaded is not None
        self.assertEqual(reloaded.location, custom)

        again = MeetingDialog(meeting=reloaded)
        self.assertEqual(again.location_edit.display_text(), custom)
        self.assertIsNone(again.location_edit.current_workplace_id())

    def test_dialog_uses_typeahead_not_plain_line_edit(self) -> None:
        dialog = MeetingDialog()
        self.assertIsInstance(dialog.location_edit, MeetingLocationTypeahead)
        self.assertTrue(dialog.location_edit.isEditable())
        self.assertTrue(dialog.location_edit.allow_custom_value)


if __name__ == "__main__":
    unittest.main()
