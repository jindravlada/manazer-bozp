"""Fáze 96a – rychlé akce Dashboardu, kalendář a dialog O programu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.widget_calendar_placeholder import (
        _CALENDAR_HEIGHT,
        _CALENDAR_WIDTH,
        _PANEL_MIN_HEIGHT,
        CalendarPlaceholderWidget,
    )
    from core.version import APP_AUTHOR, APP_COPYRIGHT, APP_VERSION, app_display_name
    from core.windows.about_dialog import AboutDialog
    from moduly.dashboard.ui.dashboard_page import DashboardPage


class DashboardAboutPhase96aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_quick_actions_without_kontrola_in_expected_order(self) -> None:
        dashboard = DashboardPage()
        quick_buttons = [
            button.text()
            for button in dashboard.findChildren(QPushButton)
            if button.objectName() == "QuickButton"
        ]

        self.assertEqual(
            quick_buttons,
            ["+ Úraz", "Nový úkol", "Nová událost", "💾 Záloha", "♻ Obnova"],
        )
        self.assertNotIn("📋 Kontrola", quick_buttons)
        self.assertNotIn("Kontrola", quick_buttons)
        self.assertFalse(hasattr(dashboard, "show_kontroly_info"))

    def test_calendar_has_larger_minimum_height_and_compact_width(self) -> None:
        calendar_panel = CalendarPlaceholderWidget()

        self.assertEqual(calendar_panel.minimumHeight(), _PANEL_MIN_HEIGHT)
        self.assertGreaterEqual(calendar_panel.minimumHeight(), 280)
        self.assertEqual(calendar_panel.calendar.width(), _CALENDAR_WIDTH)
        self.assertEqual(calendar_panel.calendar.height(), _CALENDAR_HEIGHT)
        self.assertLessEqual(_CALENDAR_WIDTH, 520)
        self.assertGreaterEqual(_CALENDAR_HEIGHT, 260)
        # Nesmí být Fixed – jinak drží minimální šířku dashboardu / okna.
        from PySide6.QtWidgets import QSizePolicy

        self.assertNotEqual(
            calendar_panel.calendar.sizePolicy().horizontalPolicy(),
            QSizePolicy.Policy.Fixed,
        )

    def test_about_dialog_size_and_central_version(self) -> None:
        dialog = AboutDialog()

        self.assertGreaterEqual(dialog.minimumWidth(), 520)
        self.assertLessEqual(dialog.minimumWidth(), 600)
        self.assertGreaterEqual(dialog.minimumHeight(), 260)
        self.assertLessEqual(dialog.minimumHeight(), 320)

        labels = {label.objectName(): label.text() for label in dialog.findChildren(QLabel)}
        self.assertEqual(labels.get("AboutTitle"), app_display_name())
        self.assertEqual(labels.get("AboutAuthor"), APP_AUTHOR)
        self.assertEqual(labels.get("AboutCopyright"), APP_COPYRIGHT)
        self.assertIn(APP_VERSION, dialog.windowTitle())
        self.assertIn(APP_VERSION, labels.get("AboutTitle", ""))


if __name__ == "__main__":
    unittest.main()
