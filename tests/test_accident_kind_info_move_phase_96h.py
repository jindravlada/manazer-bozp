"""Fáze 96h – informace o druhu úrazu pod PN na kartě Zaměstnanec."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFormLayout

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        FATAL_KIND_INFO,
        SERIOUS_KIND_INFO,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_uraz import TabUraz
    from moduly.kniha_urazu.ui.tabs.tab_zamestnanec import TabZamestnanec


KIND_SERIOUS = "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)"
KIND_FATAL = "smrtelný"
KIND_PN = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


class AccidentKindInfoMovePhase96hTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_ordinary_accident_hides_kind_info(self) -> None:
        employee = TabZamestnanec()
        employee.refresh_dpn_kind_warning(KIND_PN)
        self.assertTrue(employee.druh_urazu_info_label.isHidden())

        uraz = TabUraz()
        self.assertFalse(hasattr(uraz, "druh_urazu_info_label"))

    def test_serious_info_under_dpn_duration(self) -> None:
        employee = TabZamestnanec()
        employee.refresh_dpn_kind_warning(KIND_SERIOUS)

        self.assertFalse(employee.druh_urazu_info_label.isHidden())
        self.assertEqual(employee.druh_urazu_info_label.text(), SERIOUS_KIND_INFO)
        self.assertNotIn("ℹ", employee.druh_urazu_info_label.text())

        form = employee.findChild(QFormLayout)
        duration_row = -1
        info_row = -1
        for row in range(form.rowCount()):
            field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
            if field is None or field.widget() is None:
                continue
            if field.widget() is employee.dpn_duration_label:
                duration_row = row
            if field.widget() is employee.druh_urazu_info_label:
                info_row = row
        self.assertGreaterEqual(duration_row, 0)
        self.assertEqual(info_row, duration_row + 1)

    def test_fatal_info_under_dpn(self) -> None:
        employee = TabZamestnanec()
        employee.refresh_dpn_kind_warning(KIND_FATAL)
        self.assertFalse(employee.druh_urazu_info_label.isHidden())
        self.assertEqual(employee.druh_urazu_info_label.text(), FATAL_KIND_INFO)

    def test_kind_change_updates_or_hides_info(self) -> None:
        dialog = AccidentDialog()
        employee = dialog.tab_zamestnanec_widget
        uraz = dialog.tab_uraz_widget

        uraz.druh_urazu.set_value(KIND_SERIOUS)
        dialog._refresh_dpn_kind_warning()
        self.assertEqual(employee.druh_urazu_info_label.text(), SERIOUS_KIND_INFO)
        self.assertFalse(employee.druh_urazu_info_label.isHidden())

        uraz.druh_urazu.set_value(KIND_FATAL)
        dialog._refresh_dpn_kind_warning()
        self.assertEqual(employee.druh_urazu_info_label.text(), FATAL_KIND_INFO)

        uraz.druh_urazu.set_value(KIND_PN)
        dialog._refresh_dpn_kind_warning()
        self.assertTrue(employee.druh_urazu_info_label.isHidden())


if __name__ == "__main__":
    unittest.main()
