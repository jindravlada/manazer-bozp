"""UX-STANDARD-APPLY-007: Řízení rizik – STANDARD 001 + 002."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QItemSelectionModel, QPoint
from PySide6.QtWidgets import QAbstractItemView, QApplication, QPushButton

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
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        RISK_LIST_FILTER_ALL,
        RISK_MEASURE_REVIEW_FILTER_ALL,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui import hazard_library_page as library_module
    from moduly.rizeni_rizik.ui import risk_measure_reviews_tab as reviews_module
    from moduly.rizeni_rizik.ui import rizeni_rizik_page as ident_module
    from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage
    from moduly.rizeni_rizik.ui.risk_measure_reviews_tab import RiskMeasureReviewsTab
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import HazardIdentificationsTab


class UxStandardApply007RizeniRizikTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.operation = settings_service.save_workplace(
            name="Provoz APPLY-007",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        cls.workplace = settings_service.save_workplace(
            name="Pracoviště APPLY-007",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=cls.operation.id,
        )
        cls.person = settings_service.save_worker(first_name="Jan", last_name="Rizikový")

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardIdentification))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(RiskMeasureReview))
            session.commit()

    def _create_identification(self):
        return hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            responsible_person_id=self.person.id,
            started_at=date.today(),
        )

    def _create_review(self):
        return risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.person.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def _select_rows(self, table, rows: list[int], refresh_cb) -> None:
        model = table.selectionModel()
        model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        for row in rows:
            model.select(table.model().index(row, 0), flags)
        refresh_cb()

    # --- Identifikace ---

    def _prepare_identifications(self) -> HazardIdentificationsTab:
        tab = HazardIdentificationsTab()
        tab.active_filter.setCurrentIndex(tab.active_filter.findData(RISK_LIST_FILTER_ALL))
        tab.refresh()
        return tab

    def test_identifications_without_selection(self) -> None:
        self._create_identification()
        tab = self._prepare_identifications()
        self.assertEqual(tab._selected_row_count(), 0)
        self.assertTrue(tab.new_btn.isEnabled())
        self.assertTrue(tab.pravidla_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.activate_btn.isEnabled())
        self.assertFalse(tab.deactivate_btn.isEnabled())
        labels = [btn.text() for btn in tab.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(tab.edit_btn.text(), "Upravit")

    def test_identifications_one_and_multi_selection(self) -> None:
        self._create_identification()
        self._create_identification()
        tab = self._prepare_identifications()
        self.assertEqual(
            tab.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(tab.table, [0], tab._refresh_action_buttons)
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.deactivate_btn.isEnabled())
        self.assertFalse(tab.activate_btn.isEnabled())

        self._select_rows(tab.table, [0, 1], tab._refresh_action_buttons)
        self.assertEqual(tab._selected_row_count(), 2)
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.activate_btn.isEnabled())
        self.assertFalse(tab.deactivate_btn.isEnabled())

    def test_identifications_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(HazardIdentificationsTab.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_identification)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_identification)",
            init_source,
        )
        self.assertNotIn('"Otevřít"', init_source)

        self._create_identification()
        tab = self._prepare_identifications()
        labels: list[str] = []
        enabled_flags: list[bool] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()

                def set_enabled(value: bool) -> None:
                    enabled_flags.append(value)

                action.setEnabled = set_enabled
                return action

            def exec(self, *_args, **_kwargs):
                return None

        tab.table.selectRow(0)
        tab._refresh_action_buttons()
        with (
            patch.object(tab.table, "indexAt", return_value=tab.table.model().index(0, 0)),
            patch("moduly.rizeni_rizik.ui.rizeni_rizik_page.QMenu", FakeMenu),
        ):
            tab._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Upravit")
        self.assertIn("Aktivovat", labels)
        self.assertIn("Deaktivovat", labels)
        self.assertTrue(enabled_flags[0])

    def test_identifications_no_select_dialogs(self) -> None:
        source = inspect.getsource(ident_module)
        self.assertNotIn('"Vyberte identifikaci."', source)

        tab = self._prepare_identifications()
        with patch("moduly.rizeni_rizik.ui.rizeni_rizik_page.QMessageBox.information") as info:
            tab.edit_selected_identification()
            tab.activate_selected_identification()
            tab.deactivate_selected_identification()
            info.assert_not_called()

    # --- Katalog ---

    def _prepare_library(self) -> HazardLibraryPage:
        page = HazardLibraryPage()
        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_ALL))
        page.refresh()
        return page

    def test_library_without_selection(self) -> None:
        hazard_library_template_service.create_template(name="Zdroj A")
        page = self._prepare_library()
        self.assertEqual(page._selected_row_count(), 0)
        self.assertTrue(page.new_btn.isEnabled())
        self.assertTrue(page.manage_categories_btn.isEnabled())
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.activate_btn.isEnabled())
        self.assertFalse(page.deactivate_btn.isEnabled())
        labels = [btn.text() for btn in page.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(page.edit_btn.text(), "Upravit")

    def test_library_one_and_multi_selection(self) -> None:
        hazard_library_template_service.create_template(name="Zdroj 1")
        hazard_library_template_service.create_template(name="Zdroj 2")
        page = self._prepare_library()
        self.assertEqual(
            page.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(page.table, [0], page._refresh_action_buttons)
        self.assertTrue(page.edit_btn.isEnabled())
        self.assertTrue(page.deactivate_btn.isEnabled())
        self.assertFalse(page.activate_btn.isEnabled())

        self._select_rows(page.table, [0, 1], page._refresh_action_buttons)
        self.assertEqual(page._selected_row_count(), 2)
        self.assertFalse(page.edit_btn.isEnabled())
        self.assertFalse(page.activate_btn.isEnabled())
        self.assertFalse(page.deactivate_btn.isEnabled())

    def test_library_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(HazardLibraryPage.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_template)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_template)",
            init_source,
        )
        self.assertNotIn('"Otevřít"', init_source)

        hazard_library_template_service.create_template(name="Zdroj menu")
        page = self._prepare_library()
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()
                action.setEnabled = MagicMock()
                return action

            def exec(self, *_args, **_kwargs):
                return None

        page.table.selectRow(0)
        page._refresh_action_buttons()
        with (
            patch.object(page.table, "indexAt", return_value=page.table.model().index(0, 0)),
            patch("moduly.rizeni_rizik.ui.hazard_library_page.QMenu", FakeMenu),
        ):
            page._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Upravit")
        self.assertIn("Aktivovat", labels)
        self.assertIn("Deaktivovat", labels)

    def test_library_no_select_dialogs(self) -> None:
        source = inspect.getsource(library_module)
        self.assertNotIn('"Vyberte zdroj rizika."', source)

        page = self._prepare_library()
        with patch("moduly.rizeni_rizik.ui.hazard_library_page.QMessageBox.information") as info:
            page.edit_selected_template()
            page.activate_selected_template()
            page.deactivate_selected_template()
            info.assert_not_called()

    # --- Přezkoumání ---

    def _prepare_reviews(self) -> RiskMeasureReviewsTab:
        tab = RiskMeasureReviewsTab()
        tab.status_filter.setCurrentIndex(
            tab.status_filter.findData(RISK_MEASURE_REVIEW_FILTER_ALL)
        )
        tab.refresh()
        return tab

    def test_reviews_without_selection(self) -> None:
        self._create_review()
        tab = self._prepare_reviews()
        self.assertEqual(tab._selected_row_count(), 0)
        self.assertTrue(tab.new_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.execute_btn.isEnabled())
        self.assertFalse(tab.archive_btn.isEnabled())
        self.assertFalse(tab.restore_btn.isEnabled())
        labels = [btn.text() for btn in tab.findChildren(QPushButton)]
        self.assertNotIn("Otevřít", labels)
        self.assertEqual(tab.edit_btn.text(), "Upravit")

    def test_reviews_one_and_multi_selection(self) -> None:
        self._create_review()
        self._create_review()
        tab = self._prepare_reviews()
        self.assertEqual(
            tab.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(tab.table, [0], tab._refresh_action_buttons)
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.execute_btn.isEnabled())
        self.assertTrue(tab.archive_btn.isEnabled())
        self.assertFalse(tab.restore_btn.isEnabled())

        self._select_rows(tab.table, [0, 1], tab._refresh_action_buttons)
        self.assertEqual(tab._selected_row_count(), 2)
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.execute_btn.isEnabled())
        self.assertFalse(tab.archive_btn.isEnabled())
        self.assertFalse(tab.restore_btn.isEnabled())

    def test_reviews_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(RiskMeasureReviewsTab.__init__)
        self.assertIn(
            "self.edit_btn.clicked.connect(self.edit_selected_review)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.edit_selected_review)",
            init_source,
        )
        self.assertNotIn('"Otevřít"', init_source)

        self._create_review()
        tab = self._prepare_reviews()
        labels: list[str] = []

        class FakeMenu:
            def __init__(self, *_args, **_kwargs):
                pass

            def addAction(self, text, slot=None):
                labels.append(text)
                action = MagicMock()
                action.setEnabled = MagicMock()
                return action

            def exec(self, *_args, **_kwargs):
                return None

        tab.table.selectRow(0)
        tab._refresh_action_buttons()
        with (
            patch.object(tab.table, "indexAt", return_value=tab.table.model().index(0, 0)),
            patch("moduly.rizeni_rizik.ui.risk_measure_reviews_tab.QMenu", FakeMenu),
        ):
            tab._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Upravit")
        self.assertIn("Provést přezkoumání", labels)
        self.assertIn("Archivovat", labels)
        self.assertIn("Obnovit", labels)

    def test_reviews_no_select_dialogs(self) -> None:
        source = inspect.getsource(reviews_module)
        self.assertNotIn('"Vyberte přezkoumání."', source)

        tab = self._prepare_reviews()
        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_reviews_tab.QMessageBox.information"
        ) as info:
            tab.edit_selected_review()
            tab.execute_selected_review()
            tab.archive_selected_review()
            tab.restore_selected_review()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
