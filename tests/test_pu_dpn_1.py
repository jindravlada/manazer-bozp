"""PU-DPN-1 – základ záložky Po ukončení DPN ve spisu pracovního úrazu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import inspect as sa_inspect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import is_dpn_ended
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import (
        DPN_NOT_ENDED_MESSAGE,
        SECTION_TITLES,
        TAB_PO_UKONCENI_DPN,
    )


class PuDpn1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(Accident))
            session.commit()

    def _create_accident(self, **overrides):
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": (
                "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
            ),
            "accident_date": date(2026, 4, 1),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád z žebříku",
            "dpn_od": date(2026, 4, 1),
            "dpn_do": None,
            "opatreni": "Kontrola žebříků",
            "zranena_cast_tela": "Levé zápěstí",
        }
        data.update(overrides)
        return accident_service.create_accident(**data)

    def _tab_titles(self, dialog: AccidentDialog) -> list[str]:
        return [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]

    def _last_tab_index(self, dialog: AccidentDialog) -> int:
        return dialog.tabs.count() - 1

    def _snapshot(self, accident: Accident) -> dict:
        mapper = sa_inspect(Accident)
        return {
            attr.key: getattr(accident, attr.key)
            for attr in mapper.column_attrs
            if attr.key != "updated_at"
        }

    def _assert_inactive(self, dialog: AccidentDialog) -> None:
        tab = dialog.tab_po_ukonceni_dpn_widget
        index = self._last_tab_index(dialog)
        self.assertEqual(dialog.tabs.tabText(index), TAB_PO_UKONCENI_DPN)
        self.assertTrue(dialog.tabs.isTabEnabled(index))
        self.assertFalse(tab.info_panel.isHidden())
        self.assertEqual(tab.info_label.text(), DPN_NOT_ENDED_MESSAGE)
        self.assertFalse(tab.sections_widget.isEnabled())
        self.assertTrue(tab.sections_widget.isHidden())
        self.assertFalse(tab.is_content_active())

    def _assert_active(self, dialog: AccidentDialog) -> None:
        tab = dialog.tab_po_ukonceni_dpn_widget
        index = self._last_tab_index(dialog)
        self.assertEqual(dialog.tabs.tabText(index), TAB_PO_UKONCENI_DPN)
        self.assertTrue(dialog.tabs.isTabEnabled(index))
        self.assertTrue(tab.info_panel.isHidden())
        self.assertTrue(tab.sections_widget.isEnabled())
        self.assertFalse(tab.sections_widget.isHidden())
        self.assertTrue(tab.is_content_active())
        titles = [group.title() for group in tab.section_groups]
        self.assertEqual(tuple(titles), SECTION_TITLES)

    def test_is_dpn_ended_uses_existing_dpn_do(self) -> None:
        self.assertFalse(is_dpn_ended(None))
        self.assertTrue(is_dpn_ended(date(2026, 4, 20)))

    def test_tab_is_last_and_inactive_without_dpn_end(self) -> None:
        accident = self._create_accident()
        dialog = AccidentDialog(accident=accident)
        titles = self._tab_titles(dialog)
        self.assertEqual(titles[-1], TAB_PO_UKONCENI_DPN)
        self.assertGreater(titles.index("Svědci"), 0)
        self._assert_inactive(dialog)

    def test_tab_activates_when_dpn_end_is_set(self) -> None:
        accident = self._create_accident()
        dialog = AccidentDialog(accident=accident)
        self._assert_inactive(dialog)

        dialog.tab_zamestnanec_widget.dpn_do.set_date_value(date(2026, 4, 20))
        self._assert_active(dialog)

    def test_tab_returns_inactive_when_dpn_end_is_cleared(self) -> None:
        accident = self._create_accident(dpn_do=date(2026, 4, 20))
        dialog = AccidentDialog(accident=accident)
        self._assert_active(dialog)

        dialog.tab_zamestnanec_widget.dpn_do.clear_date()
        self._assert_inactive(dialog)

    def test_existing_accident_opens_without_changing_other_data(self) -> None:
        accident = self._create_accident(
            dpn_do=None,
            osobni_cislo="123",
            misto_urazu="Sklad",
        )
        before = self._snapshot(accident_service.get_by_id(accident.id))

        dialog = AccidentDialog(accident=accident)
        self._assert_inactive(dialog)

        after = self._snapshot(accident_service.get_by_id(accident.id))
        self.assertEqual(after, before)
        self.assertIsNone(after["dpn_do"])
        self.assertEqual(after["jmeno_prijmeni"], "Jan Novák")
        self.assertEqual(after["popis_urazoveho_deje"], "Pád z žebříku")
        self.assertEqual(after["opatreni"], "Kontrola žebříků")
        self.assertEqual(after["osobni_cislo"], "123")
        self.assertEqual(after["misto_urazu"], "Sklad")
        data = dialog.get_data()
        self.assertEqual(data["jmeno_prijmeni"], "Jan Novák")
        self.assertEqual(data["popis_urazoveho_deje"], "Pád z žebříku")
        self.assertEqual(data["opatreni"], "Kontrola žebříků")
        self.assertIsNone(data["dpn_do"])
        self.assertEqual(data["dpn_od"], date(2026, 4, 1))


if __name__ == "__main__":
    unittest.main()
