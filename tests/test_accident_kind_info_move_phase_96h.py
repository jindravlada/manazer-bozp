"""Fáze 96h – informace o druhu úrazu pod PN na kartě Údaje o úrazu."""

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
        uraz = TabUraz()
        uraz.refresh_dpn_kind_warning(KIND_PN)
        self.assertTrue(uraz.druh_urazu_info_label.isHidden())

        employee = TabZamestnanec()
        self.assertFalse(hasattr(employee, "druh_urazu_info_label"))
        self.assertFalse(hasattr(employee, "dpn_od"))

    def test_serious_info_under_dpn_duration(self) -> None:
        uraz = TabUraz()
        uraz.refresh_dpn_kind_warning(KIND_SERIOUS)

        self.assertFalse(uraz.druh_urazu_info_label.isHidden())
        self.assertEqual(uraz.druh_urazu_info_label.text(), SERIOUS_KIND_INFO)
        self.assertNotIn("ℹ", uraz.druh_urazu_info_label.text())

        form = uraz.layout().itemAt(0).layout()
        self.assertIsInstance(form, QFormLayout)
        duration_row = -1
        info_row = -1
        for row in range(form.rowCount()):
            widget = None
            for role in (
                QFormLayout.ItemRole.FieldRole,
                QFormLayout.ItemRole.SpanningRole,
            ):
                field = form.itemAt(row, role)
                if field is not None and field.widget() is not None:
                    widget = field.widget()
                    break
            if widget is uraz.dpn_duration_label:
                duration_row = row
            if widget is uraz.druh_urazu_info_label:
                info_row = row
        self.assertGreaterEqual(duration_row, 0)
        self.assertEqual(info_row, duration_row + 1)

    def test_fatal_info_under_dpn(self) -> None:
        uraz = TabUraz()
        uraz.refresh_dpn_kind_warning(KIND_FATAL)
        self.assertFalse(uraz.druh_urazu_info_label.isHidden())
        self.assertEqual(uraz.druh_urazu_info_label.text(), FATAL_KIND_INFO)

    def test_kind_change_updates_or_hides_info(self) -> None:
        dialog = AccidentDialog()
        uraz = dialog.tab_uraz_widget

        uraz.druh_urazu.set_value(KIND_SERIOUS)
        dialog._refresh_dpn_kind_warning()
        self.assertEqual(uraz.druh_urazu_info_label.text(), SERIOUS_KIND_INFO)
        self.assertFalse(uraz.druh_urazu_info_label.isHidden())

        uraz.druh_urazu.set_value(KIND_FATAL)
        dialog._refresh_dpn_kind_warning()
        self.assertEqual(uraz.druh_urazu_info_label.text(), FATAL_KIND_INFO)

        uraz.druh_urazu.set_value(KIND_PN)
        dialog._refresh_dpn_kind_warning()
        self.assertTrue(uraz.druh_urazu_info_label.isHidden())


if __name__ == "__main__":
    unittest.main()
