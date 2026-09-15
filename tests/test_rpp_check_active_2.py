"""RPP-CHECK-ACTIVE-2: ovládání Aktivní jen pryč z UI Kontrol změn."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel, Qt
from PySide6.QtWidgets import QApplication, QPushButton

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

    from moduly.pravni_pozadavky.constants import CHECK_RUN_COMPLETED
    from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
    from moduly.pravni_pozadavky.repository import legal_check_run_repository as repo_module
    from moduly.pravni_pozadavky.sluzby import legal_check_run_service as service_module
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
        legal_check_run_service,
    )
    from moduly.pravni_pozadavky.ui import kontroly_legislativy_tab as kontroly_module
    from moduly.pravni_pozadavky.ui import pravni_predpisy_tab as docs_module
    from moduly.pravni_pozadavky.ui import zmeny_legislativy_tab as changes_module
    from moduly.pravni_pozadavky.ui.kontroly_legislativy_tab import KontrolyLegislativyTab
    from moduly.pravni_pozadavky.ui.pravni_predpisy_tab import PravniPredpisyTab
    from moduly.pravni_pozadavky.ui.zmeny_legislativy_tab import ZmenyLegislativyTab


class RppCheckActive2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument

        with get_session() as session:
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalDocument))
            session.commit()

    def _select_row(self, table, row: int, refresh_cb) -> None:
        model = table.selectionModel()
        model.clearSelection()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        model.select(table.model().index(row, 0), flags)
        refresh_cb()

    def _titles(self, tab: KontrolyLegislativyTab) -> list[str]:
        return [
            tab.table.item(row, 1).text()
            for row in range(tab.table.rowCount())
        ]

    def test_a_table_has_no_active_column(self) -> None:
        tab = KontrolyLegislativyTab()
        headers = [
            tab.table.horizontalHeaderItem(column).text()
            for column in range(tab.table.columnCount())
        ]
        self.assertEqual(
            headers,
            ["ID", "Název", "Období od", "Období do", "Datum kontroly", "Stav"],
        )
        self.assertNotIn("Aktivní", headers)

    def test_b_toolbar_has_no_deactivate_or_restore(self) -> None:
        tab = KontrolyLegislativyTab()
        labels = [btn.text() for btn in tab.findChildren(QPushButton)]
        self.assertIn("Provést kontrolu", labels)
        self.assertIn("Otevřít", labels)
        self.assertNotIn("Deaktivovat", labels)
        self.assertNotIn("Obnovit", labels)
        self.assertNotIn("Aktivovat", labels)
        self.assertFalse(hasattr(tab, "toggle_btn"))
        source = inspect.getsource(kontroly_module)
        self.assertNotIn("toggle_selected_run", source)
        self.assertIn("include_inactive=True", inspect.getsource(tab.refresh))

    def test_c_inactive_runs_remain_visible_without_graying(self) -> None:
        legal_check_run_service.create(
            title="Aktivní kontrola",
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
        )
        inactive = legal_check_run_service.create(
            title="Historicky neaktivní",
            period_from=date(2026, 2, 1),
            period_to=date(2026, 2, 28),
        )
        legal_check_run_service.deactivate(inactive.id)
        self.assertFalse(legal_check_run_service.get_by_id(inactive.id).active)

        tab = KontrolyLegislativyTab()
        titles = self._titles(tab)
        self.assertIn("Aktivní kontrola", titles)
        self.assertIn("Historicky neaktivní", titles)
        self.assertEqual(len(titles), 2)

        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, 1)
            self.assertEqual(item.background().style(), Qt.BrushStyle.NoBrush)

        self.assertFalse(legal_check_run_service.get_by_id(inactive.id).active)

    def test_d_open_selected_run_preserves_active_flag(self) -> None:
        run = legal_check_run_service.create(
            title="Kontrola k otevření",
            period_from=date(2026, 3, 1),
            period_to=date(2026, 3, 31),
            status=CHECK_RUN_COMPLETED,
        )
        legal_check_run_service.deactivate(run.id)
        tab = KontrolyLegislativyTab()
        row = next(
            index
            for index in range(tab.table.rowCount())
            if tab.table.item(index, 1).text() == "Kontrola k otevření"
        )
        self._select_row(tab.table, row, tab._refresh_action_buttons)
        self.assertTrue(tab.open_btn.isEnabled())

        dialog_data = {
            "title": "Kontrola k otevření",
            "period_from": date(2026, 3, 1),
            "period_to": date(2026, 3, 31),
            "checked_at": None,
            "checked_by": "",
            "started_at": None,
            "status": CHECK_RUN_COMPLETED,
            "note": "",
            "error_message": "",
            "documents_checked_count": None,
            "changes_found_count": None,
        }
        with (
            patch(
                "moduly.pravni_pozadavky.ui.kontroly_legislativy_tab.exec_maximized",
                return_value=True,
            ),
            patch(
                "moduly.pravni_pozadavky.ui.kontroly_legislativy_tab.LegalCheckRunDialog",
            ) as dialog_cls,
        ):
            dialog_cls.return_value.get_data.return_value = dialog_data
            tab.open_selected_run()

        fresh = legal_check_run_service.get_by_id(run.id)
        assert fresh is not None
        self.assertFalse(fresh.active)
        self.assertEqual(fresh.title, "Kontrola k otevření")

    def test_e_new_run_is_active_true(self) -> None:
        run = legal_check_run_service.create(
            title="Nová kontrola",
            period_from=date(2026, 4, 1),
            period_to=date(2026, 4, 30),
        )
        self.assertTrue(run.active)
        completed = legal_check_run_service.complete_run(run.id)
        assert completed is not None
        self.assertTrue(completed.active)

    def test_f_new_completed_run_does_not_deactivate_older(self) -> None:
        older = legal_check_run_service.create(
            title="Starší",
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
        )
        legal_check_run_service.complete_run(older.id)
        newer = legal_check_run_service.create(
            title="Novější",
            period_from=date(2026, 2, 1),
            period_to=date(2026, 2, 28),
        )
        legal_check_run_service.complete_run(newer.id)

        self.assertTrue(legal_check_run_service.get_by_id(older.id).active)
        self.assertTrue(legal_check_run_service.get_by_id(newer.id).active)

    def test_g_period_and_first_check_logic_still_use_active(self) -> None:
        repo_source = inspect.getsource(repo_module.LegalCheckRunRepository.get_last_completed)
        self.assertIn("LegalCheckRun.active.is_(True)", repo_source)
        self.assertIn("CHECK_RUN_COMPLETED", repo_source)

        service_source = inspect.getsource(service_module.LegalCheckRunService)
        self.assertIn("def is_first_automatic_check", service_source)
        self.assertIn("return self.get_last_completed_run() is None", service_source)
        self.assertIn("def deactivate", service_source)
        self.assertIn("def restore", service_source)

        ui_source = inspect.getsource(kontroly_module.KontrolyLegislativyTab.perform_check)
        self.assertIn("get_last_completed_run", ui_source)
        self.assertIn("get_run_completion_date", ui_source)

        older = legal_check_run_service.create(
            title="První dokončená",
            period_from=date(2026, 1, 1),
            period_to=date(2026, 1, 31),
        )
        legal_check_run_service.complete_run(older.id)
        self.assertFalse(legal_check_run_service.is_first_automatic_check())
        last = legal_check_run_service.get_last_completed_run()
        assert last is not None
        self.assertEqual(
            legal_check_run_service.get_run_completion_date(last),
            last.checked_at.date(),
        )

        legal_check_run_service.deactivate(older.id)
        self.assertTrue(legal_check_run_service.is_first_automatic_check())
        self.assertIsNone(legal_check_run_service.get_last_completed_run())

    def test_h_active_remains_in_model(self) -> None:
        self.assertIn("active", LegalCheckRun.__table__.c)
        self.assertTrue(LegalCheckRun.__table__.c.active.default.arg)

    def test_i_other_modules_still_have_deactivate(self) -> None:
        self.assertIn('QPushButton("Deaktivovat")', inspect.getsource(docs_module))
        self.assertIn('QPushButton("Deaktivovat")', inspect.getsource(changes_module))
        docs = PravniPredpisyTab()
        changes = ZmenyLegislativyTab()
        self.assertEqual(docs.toggle_btn.text(), "Deaktivovat")
        self.assertEqual(changes.toggle_btn.text(), "Deaktivovat")


if __name__ == "__main__":
    unittest.main()
