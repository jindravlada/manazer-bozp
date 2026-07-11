"""Fáze 96f – ruční zadání pracoviště u pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.workplace_selector import WorkplaceSelector
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.tabs.tab_pracoviste import TabPracoviste
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AccidentWorkplaceManualPhase96fTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from core.database.session import get_session
        from moduly.kniha_urazu.modely.accident import Accident

        with get_session() as session:
            for accident in session.query(Accident).all():
                session.delete(accident)
            session.commit()

        for workplace in list(settings_service.get_workplaces(include_inactive=True)):
            settings_service.deactivate_workplace(workplace.id)

        self.workplace = settings_service.save_workplace(name="Dílna")

    def _fill_required_non_workplace(self, tab: TabPracoviste) -> None:
        tab.charakteristika_pracoviste.set_value("výrobní")
        tab.zdroj_urazu.set_value("stroj")
        tab.pricina_urazu.set_value("pád")
    def test_selector_is_editable_search_combo(self) -> None:
        selector = WorkplaceSelector()
        self.assertTrue(selector.isEditable())
        self.assertTrue(isinstance(selector, QComboBox))
        self.assertIsNotNone(selector.completer())

    def test_can_select_internal_workplace(self) -> None:
        tab = TabPracoviste()
        tab.workplace.set_workplace_id(self.workplace.id)

        data = tab.get_data()
        self.assertEqual(data["workplace_id"], self.workplace.id)
        self.assertEqual(data["workplace_name"], "Dílna")
        self.assertEqual(data["pracoviste"], "Dílna")

    def test_can_enter_custom_text(self) -> None:
        tab = TabPracoviste()
        tab.workplace.setCurrentText("Dílna firmy ABC")

        data = tab.get_data()
        self.assertIsNone(data["workplace_id"])
        self.assertEqual(data["workplace_name"], "Dílna firmy ABC")
        self.assertEqual(data["pracoviste"], "Dílna firmy ABC")
        self.assertFalse(tab._is_empty(tab.workplace))

    def test_completer_suggests_catalog_while_typing_custom(self) -> None:
        selector = WorkplaceSelector()
        completer = selector.completer()
        self.assertIsNotNone(completer)
        completer.setCompletionPrefix("Díl")
        model = completer.completionModel()
        self.assertIsNotNone(model)
        matches = [
            model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)
            for row in range(model.rowCount())
        ]
        self.assertIn("Dílna", matches)

        selector.setCurrentText("Dílna firmy ABC")
        self.assertIsNone(selector.current_workplace_id())
        self.assertEqual(selector.display_text(), "Dílna firmy ABC")

    def test_custom_text_is_not_added_to_workplace_catalog(self) -> None:
        before = {w.name for w in settings_service.get_workplaces(include_inactive=True)}

        tab = TabPracoviste()
        self._fill_required_non_workplace(tab)
        tab.workplace.setCurrentText("Stavba u zákazníka XY")

        accident = accident_service.create_accident(**tab.get_data())

        after = {w.name for w in settings_service.get_workplaces(include_inactive=True)}
        self.assertEqual(before, after)
        self.assertNotIn("Stavba u zákazníka XY", after)
        self.assertIsNone(accident.workplace_id)
        self.assertEqual(accident.workplace_name, "Stavba u zákazníka XY")

    def test_custom_text_persists_after_reload(self) -> None:
        tab = TabPracoviste()
        self._fill_required_non_workplace(tab)
        tab.workplace.setCurrentText("Železniční trať km 12")

        accident = accident_service.create_accident(**tab.get_data())

        reopened = TabPracoviste()
        reopened.load_data(accident_service.get_by_id(accident.id))

        self.assertEqual(reopened.workplace.display_text(), "Železniční trať km 12")
        self.assertIsNone(reopened.workplace.current_workplace_id())
        data = reopened.get_data()
        self.assertEqual(data["workplace_name"], "Železniční trať km 12")
        self.assertIsNone(data["workplace_id"])

    def test_internal_workplace_is_preselected_on_open(self) -> None:
        accident = accident_service.create_accident(
            workplace_id=self.workplace.id,
            workplace_name="Dílna",
            pracoviste="Dílna",
            charakteristika_pracoviste="výrobní",
            zdroj_urazu="stroj",
            pricina_urazu="pád",
        )

        tab = TabPracoviste()
        tab.load_data(accident_service.get_by_id(accident.id))

        self.assertEqual(tab.workplace.current_workplace_id(), self.workplace.id)
        self.assertEqual(tab.workplace.display_text(), "Dílna")

    def test_foreign_employer_choice_does_not_block_manual_entry(self) -> None:
        tab = TabPracoviste()
        self._fill_required_non_workplace(tab)
        tab.uraz_pracoviste_zamestnavatele_ne.setChecked(True)
        tab.workplace.setCurrentText("Prostory dodavatele")

        data = tab.get_data()
        self.assertEqual(data["uraz_pracoviste_zamestnavatele"], "NE")
        self.assertEqual(data["workplace_name"], "Prostory dodavatele")
        self.assertIsNone(data["workplace_id"])
        self.assertEqual(tab.validate(), [])


if __name__ == "__main__":
    unittest.main()
