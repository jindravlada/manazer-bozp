"""UX-STANDARD-APPLY-010: dokončení UX STANDARD 001 v Nastavení (+ Kontroly změn)."""

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
    )
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.ui import nastaveni_page as nastaveni_module
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
        legal_check_run_service,
    )
    from moduly.pravni_pozadavky.ui import kontroly_legislativy_tab as kontroly_module
    from moduly.pravni_pozadavky.ui.kontroly_legislativy_tab import KontrolyLegislativyTab


class UxStandardApply010TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.nastaveni.modely.exposed_group import ExposedGroup
        from moduly.nastaveni.modely.person import Person
        from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole
        from moduly.nastaveni.modely.thp_worker import ThpWorker
        from moduly.nastaveni.modely.workplace import Workplace

        with get_session() as session:
            session.execute(delete(LegalCheckRun))
            session.execute(delete(ExposedGroup))
            session.execute(delete(ResponsibilityRole))
            session.execute(delete(Person))
            session.execute(delete(ThpWorker))
            session.execute(delete(Workplace))
            session.commit()

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

    def _assert_no_combined_toggle(self, page: NastaveniPage) -> None:
        labels = [btn.text() for btn in page.findChildren(QPushButton)]
        self.assertNotIn("Deaktivovat / Aktivovat", labels)

    # --- Kontroly změn ---

    def test_kontroly_without_and_with_selection(self) -> None:
        legal_check_run_service.create(
            title="Kontrola A",
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
        )
        legal_check_run_service.create(
            title="Kontrola B",
            period_from=date(2026, 2, 1),
            period_to=date(2026, 2, 28),
        )
        tab = KontrolyLegislativyTab()
        self.assertTrue(tab.perform_check_btn.isEnabled())
        self.assertFalse(tab.open_btn.isEnabled())
        self.assertFalse(tab.toggle_btn.isEnabled())

        self.assertEqual(
            tab.table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )
        self._select_rows(tab.table, [0], tab._refresh_action_buttons)
        self.assertTrue(tab.open_btn.isEnabled())
        self.assertTrue(tab.toggle_btn.isEnabled())
        self.assertEqual(tab.toggle_btn.text(), "Deaktivovat")

        self._select_rows(tab.table, [0, 1], tab._refresh_action_buttons)
        self.assertFalse(tab.open_btn.isEnabled())
        self.assertFalse(tab.toggle_btn.isEnabled())

        source = inspect.getsource(kontroly_module)
        self.assertNotIn('"Vyberte kontrolu."', source)

        tab.table.clearSelection()
        tab._refresh_action_buttons()
        with patch(
            "moduly.pravni_pozadavky.ui.kontroly_legislativy_tab.QMessageBox.information"
        ) as info:
            tab.open_selected_run()
            tab.toggle_selected_run()
            info.assert_not_called()

    def test_kontroly_double_click_and_context_menu(self) -> None:
        init_source = inspect.getsource(KontrolyLegislativyTab.__init__)
        self.assertIn(
            "self.open_btn.clicked.connect(self.open_selected_run)",
            init_source,
        )
        self.assertIn(
            "self.table.doubleClicked.connect(self.open_selected_run)",
            init_source,
        )

        legal_check_run_service.create(
            title="Kontrola menu",
            period_from=date(2026, 3, 1),
            period_to=date(2026, 3, 31),
        )
        tab = KontrolyLegislativyTab()
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
            patch(
                "moduly.pravni_pozadavky.ui.kontroly_legislativy_tab.QMenu",
                FakeMenu,
            ),
        ):
            tab._show_table_context_menu(QPoint(10, 10))

        self.assertEqual(labels[0], "Otevřít")
        self.assertIn("Deaktivovat", labels)

    # --- Nastavení číselníky ---

    def test_workers_buttons(self) -> None:
        settings_service.save_worker(first_name="Jan", last_name="Aktivní")
        inactive = settings_service.save_worker(first_name="Eva", last_name="Neaktivní")
        settings_service.deactivate_worker(inactive.id)

        page = NastaveniPage()
        page.worker_filter.setCurrentText("Všichni")
        page.refresh_workers()
        self._assert_no_combined_toggle(page)

        self.assertFalse(page.worker_edit_button.isEnabled())
        self.assertFalse(page.worker_activate_button.isEnabled())
        self.assertFalse(page.worker_deactivate_button.isEnabled())
        self.assertEqual(
            page.worker_table.selectionMode(),
            QAbstractItemView.SelectionMode.ExtendedSelection,
        )

        # Najdi aktivní řádek
        for row in range(page.worker_table.rowCount()):
            if page.worker_table.item(row, 9).text() == "Ano":
                self._select_rows(page.worker_table, [row], page.update_worker_buttons)
                break
        self.assertTrue(page.worker_edit_button.isEnabled())
        self.assertFalse(page.worker_activate_button.isEnabled())
        self.assertTrue(page.worker_deactivate_button.isEnabled())

        for row in range(page.worker_table.rowCount()):
            if page.worker_table.item(row, 9).text() == "Ne":
                self._select_rows(page.worker_table, [row], page.update_worker_buttons)
                break
        self.assertTrue(page.worker_activate_button.isEnabled())
        self.assertFalse(page.worker_deactivate_button.isEnabled())

        self._select_rows(page.worker_table, [0, 1], page.update_worker_buttons)
        self.assertFalse(page.worker_edit_button.isEnabled())

        init_source = inspect.getsource(NastaveniPage._workers_tab)
        self.assertIn("self.worker_table.doubleClicked.connect(self.edit_selected_worker)", init_source)

        page.worker_table.selectRow(0)
        page.update_worker_buttons()
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

        with (
            patch.object(
                page.worker_table,
                "indexAt",
                return_value=page.worker_table.model().index(0, 0),
            ),
            patch("moduly.nastaveni.ui.nastaveni_page.QMenu", FakeMenu),
        ):
            page._show_worker_context_menu(QPoint(5, 5))
        self.assertEqual(labels[0], "Upravit")

    def test_persons_buttons(self) -> None:
        person_service.create_person(first_name="A", last_name="Aktivní")
        inactive = person_service.create_person(first_name="N", last_name="Neaktivní")
        person_service.deactivate(inactive.id)

        page = NastaveniPage()
        page.person_filter.setCurrentText("Vše")
        page.refresh_persons()
        self.assertFalse(page.person_edit_button.isEnabled())
        self.assertFalse(page.person_activate_button.isEnabled())
        self.assertFalse(page.person_deactivate_button.isEnabled())

        for row in range(page.person_table.rowCount()):
            if page.person_table.item(row, 7).text() == "Aktivní":
                self._select_rows(page.person_table, [row], page.update_person_buttons)
                break
        self.assertTrue(page.person_edit_button.isEnabled())
        self.assertTrue(page.person_deactivate_button.isEnabled())
        self.assertFalse(page.person_activate_button.isEnabled())

    def test_workplaces_buttons(self) -> None:
        op = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        page = NastaveniPage()
        page.workplace_filter.setCurrentText("Všechna")
        page.refresh_workplaces()
        self.assertFalse(page.workplace_edit_button.isEnabled())
        self.assertFalse(page.workplace_activate_button.isEnabled())
        self.assertFalse(page.workplace_deactivate_button.isEnabled())

        item = page.workplace_tree.topLevelItem(0)
        self.assertIsNotNone(item)
        page.workplace_tree.setCurrentItem(item)
        page.update_workplace_buttons()
        self.assertTrue(page.workplace_edit_button.isEnabled())
        self.assertTrue(page.workplace_deactivate_button.isEnabled())
        self.assertFalse(page.workplace_activate_button.isEnabled())

        settings_service.deactivate_workplace(op.id)
        page.refresh_workplaces()
        page.workplace_tree.setCurrentItem(page.workplace_tree.topLevelItem(0))
        page.update_workplace_buttons()
        self.assertTrue(page.workplace_activate_button.isEnabled())
        self.assertFalse(page.workplace_deactivate_button.isEnabled())

    def test_roles_and_exposed_groups_buttons(self) -> None:
        responsibility_role_service.create_role(name="Role A")
        exposed_group_service.create_group(name="Skupina A")

        page = NastaveniPage()
        page.responsibility_role_filter.setCurrentText("Všechny")
        page.exposed_group_filter.setCurrentText("Všechny")
        page.refresh_responsibility_roles()
        page.refresh_exposed_groups()

        self.assertFalse(page.responsibility_role_edit_button.isEnabled())
        self.assertFalse(page.responsibility_role_activate_button.isEnabled())
        self.assertFalse(page.responsibility_role_deactivate_button.isEnabled())
        self.assertFalse(page.exposed_group_edit_button.isEnabled())
        self.assertFalse(page.exposed_group_activate_button.isEnabled())
        self.assertFalse(page.exposed_group_deactivate_button.isEnabled())

        self._select_rows(
            page.responsibility_role_table,
            [0],
            page.update_responsibility_role_buttons,
        )
        self.assertTrue(page.responsibility_role_edit_button.isEnabled())
        self.assertTrue(page.responsibility_role_deactivate_button.isEnabled())

        self._select_rows(
            page.exposed_group_table,
            [0],
            page.update_exposed_group_buttons,
        )
        self.assertTrue(page.exposed_group_edit_button.isEnabled())
        self.assertTrue(page.exposed_group_deactivate_button.isEnabled())

    def test_nastaveni_no_select_dialogs(self) -> None:
        source = inspect.getsource(nastaveni_module)
        for phrase in (
            '"Vyberte pracovníka."',
            '"Vyberte osobu."',
            '"Vyberte položku."',
            '"Vyberte roli."',
            '"Vyberte skupinu."',
        ):
            self.assertNotIn(phrase, source)

        page = NastaveniPage()
        with patch("moduly.nastaveni.ui.nastaveni_page.QMessageBox.information") as info:
            page.edit_selected_worker()
            page.activate_selected_worker()
            page.deactivate_selected_worker()
            page.edit_selected_person()
            page.activate_selected_person()
            page.deactivate_selected_person()
            page.edit_selected_workplace()
            page.activate_selected_workplace()
            page.deactivate_selected_workplace()
            page.edit_selected_responsibility_role()
            page.activate_selected_responsibility_role()
            page.deactivate_selected_responsibility_role()
            page.edit_selected_exposed_group()
            page.activate_selected_exposed_group()
            page.deactivate_selected_exposed_group()
            info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
