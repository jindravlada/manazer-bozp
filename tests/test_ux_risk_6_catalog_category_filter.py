"""UX-RISK-6 – filtr kategorií v přehledu katalogu zdrojů rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="ux-risk-6-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QHeaderView
    from sqlalchemy import delete

    from core.widgets.table_utils import table_cell_text_is_elided
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_LIST_FILTER_ACTIVE,
        RISK_LIST_FILTER_ALL,
        RISK_LIST_FILTER_INACTIVE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_APPLY_ALL_CATEGORIES,
        HAZARD_LIBRARY_CATEGORY_COLUMN_FIT_TEXT,
        HAZARD_LIBRARY_COL_CATEGORY,
        HAZARD_LIBRARY_COL_NAME,
        HAZARD_LIBRARY_SCOPE_MANUAL,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
        hazard_source_category_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage


def _visible_names(page: HazardLibraryPage) -> list[str]:
    names: list[str] = []
    for row in range(page.table.rowCount()):
        if page.table.isRowHidden(row):
            continue
        item = page.table.item(row, HAZARD_LIBRARY_COL_NAME)
        names.append(item.text() if item is not None else "")
    return names


class UxRisk6CatalogCategoryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        existing = [
            item
            for item in hazard_source_category_service.get_active_all()
            if item.name == "Kolejiště"
        ]
        cls.track_category = existing[0] if existing else hazard_source_category_service.create_category(
            name="Kolejiště",
            description="Koleje a kolejové stavby",
        )

    def setUp(self) -> None:
        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        hazard_library_template_service.create_template(
            name="Kolejová brzda",
            category=self.track_category.code,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        hazard_library_template_service.create_template(
            name="Výhybka",
            category=self.track_category.code,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        inactive = hazard_library_template_service.create_template(
            name="Neaktivní kolej",
            category=self.track_category.code,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
            active=False,
        )
        hazard_library_template_service.create_template(
            name="Fréza",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_MANUAL,
        )
        self.assertFalse(inactive.active)

    def _select_category(self, page: HazardLibraryPage, code: str | None) -> None:
        if code is None:
            page.category_filter.setCurrentIndex(0)
            return
        index = page.category_filter.findData(code)
        self.assertGreaterEqual(index, 0)
        page.category_filter.setCurrentIndex(index)

    def test_default_all_categories_shows_matching_sources(self) -> None:
        page = HazardLibraryPage()
        self.assertEqual(page.category_filter.currentText(), HAZARD_LIBRARY_APPLY_ALL_CATEGORIES)
        self.assertIsNone(page.category_filter.currentData())
        self.assertCountEqual(_visible_names(page), ["Kolejová brzda", "Výhybka", "Fréza"])
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 3 / 3")

    def test_one_category_shows_only_its_sources(self) -> None:
        page = HazardLibraryPage()
        self._select_category(page, self.track_category.code)
        self.assertCountEqual(_visible_names(page), ["Kolejová brzda", "Výhybka"])
        self.assertNotIn("Fréza", _visible_names(page))

    def test_category_and_text_search_combine(self) -> None:
        page = HazardLibraryPage()
        self._select_category(page, self.track_category.code)
        page.text_filter.search_edit.setText("brzda")
        self.assertEqual(_visible_names(page), ["Kolejová brzda"])
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 1 / 3")

    def test_category_and_active_filter_combine(self) -> None:
        page = HazardLibraryPage()
        self._select_category(page, self.track_category.code)
        self.assertEqual(page.active_filter.currentData(), RISK_LIST_FILTER_ACTIVE)
        self.assertCountEqual(_visible_names(page), ["Kolejová brzda", "Výhybka"])
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 2 / 3")

        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_ALL))
        self._select_category(page, self.track_category.code)
        self.assertCountEqual(
            _visible_names(page),
            ["Kolejová brzda", "Výhybka", "Neaktivní kolej"],
        )
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 3 / 4")

        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_INACTIVE))
        self._select_category(page, self.track_category.code)
        self.assertEqual(_visible_names(page), ["Neaktivní kolej"])
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 1 / 1")

    def test_category_change_updates_shown_count(self) -> None:
        page = HazardLibraryPage()
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 3 / 3")
        self._select_category(page, self.track_category.code)
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 2 / 3")
        self._select_category(page, HAZARD_INVENTORY_CATEGORY_EQUIPMENT)
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 1 / 3")
        self._select_category(page, None)
        self.assertEqual(page.text_filter.count_label.text(), "Zobrazeno: 3 / 3")

    def test_category_column_fits_long_name_without_ellipsis(self) -> None:
        page = HazardLibraryPage()
        header = page.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(HAZARD_LIBRARY_COL_CATEGORY),
            QHeaderView.ResizeMode.Fixed,
        )
        self.assertEqual(
            header.sectionResizeMode(HAZARD_LIBRARY_COL_NAME),
            QHeaderView.ResizeMode.Stretch,
        )
        needed = page.table.fontMetrics().horizontalAdvance(
            HAZARD_LIBRARY_CATEGORY_COLUMN_FIT_TEXT,
        )
        self.assertGreaterEqual(
            page.table.columnWidth(HAZARD_LIBRARY_COL_CATEGORY),
            needed,
        )

        item = page.table.item(0, HAZARD_LIBRARY_COL_CATEGORY)
        assert item is not None
        original = item.text()
        item.setText(HAZARD_LIBRARY_CATEGORY_COLUMN_FIT_TEXT)
        try:
            self.assertFalse(
                table_cell_text_is_elided(
                    page.table,
                    0,
                    HAZARD_LIBRARY_COL_CATEGORY,
                )
            )
        finally:
            item.setText(original)


if __name__ == "__main__":
    unittest.main()
