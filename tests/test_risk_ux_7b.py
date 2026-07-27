"""RISK-UX-7b – filtr Aktivní/Neaktivní/Vše v katalogu zdrojů rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ux-7b-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication
    from sqlalchemy import delete

    from moduly.rizeni_rizik.constants import (
        RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER,
        RISK_LIST_FILTER_ACTIVE,
        RISK_LIST_FILTER_ALL,
        RISK_LIST_FILTER_INACTIVE,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage


def _visible_names(page: HazardLibraryPage) -> list[str]:
    names: list[str] = []
    for row in range(page.table.rowCount()):
        if page.table.isRowHidden(row):
            continue
        item = page.table.item(row, 1)
        names.append(item.text() if item is not None else "")
    return names


class RiskUx7bCatalogActiveFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        hazard_library_template_service.create_template(name="Aktivní zdroj A")
        inactive = hazard_library_template_service.create_template(
            name="Neaktivní zdroj B",
            active=False,
        )
        hazard_library_template_service.create_template(name="Aktivní zdroj C")
        self.assertFalse(inactive.active)

    def test_default_filter_is_active(self) -> None:
        page = HazardLibraryPage()
        self.assertEqual(page.active_filter.currentData(), RISK_IDENTIFICATION_DEFAULT_ACTIVE_FILTER)
        self.assertEqual(page.active_filter.currentData(), RISK_LIST_FILTER_ACTIVE)
        self.assertEqual(
            _visible_names(page),
            ["Aktivní zdroj A", "Aktivní zdroj C"],
        )
        self.assertIn("Zobrazeno: 2 / 2", page.text_filter.count_label.text())

    def test_inactive_filter_shows_only_inactive(self) -> None:
        page = HazardLibraryPage()
        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_INACTIVE))
        self.assertEqual(_visible_names(page), ["Neaktivní zdroj B"])
        self.assertIn("Zobrazeno: 1 / 1", page.text_filter.count_label.text())

    def test_all_filter_shows_active_and_inactive(self) -> None:
        page = HazardLibraryPage()
        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_ALL))
        self.assertCountEqual(
            _visible_names(page),
            ["Aktivní zdroj A", "Neaktivní zdroj B", "Aktivní zdroj C"],
        )
        self.assertIn("Zobrazeno: 3 / 3", page.text_filter.count_label.text())

    def test_active_filter_combines_with_text_search(self) -> None:
        page = HazardLibraryPage()
        page.text_filter.search_edit.setText("zdroj A")
        self.assertEqual(_visible_names(page), ["Aktivní zdroj A"])
        self.assertIn("Zobrazeno: 1 / 2", page.text_filter.count_label.text())

        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_ALL))
        page.text_filter.search_edit.setText("zdroj")
        self.assertCountEqual(
            _visible_names(page),
            ["Aktivní zdroj A", "Neaktivní zdroj B", "Aktivní zdroj C"],
        )
        self.assertIn("Zobrazeno: 3 / 3", page.text_filter.count_label.text())

        page.text_filter.search_edit.setText("Neaktivní")
        self.assertEqual(_visible_names(page), ["Neaktivní zdroj B"])
        self.assertIn("Zobrazeno: 1 / 3", page.text_filter.count_label.text())


if __name__ == "__main__":
    unittest.main()
