"""PU-UPCOMING-FIX-2: mimořádná prohlídka v Nadcházejících událostech."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
        SOURCE_LABEL_KNIHA_URAZU,
        TYPE_LABELS,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.windows.main_window import MainWindow
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_dpn_care import (
        CARE_EXAM_DATE,
        CARE_EXAM_DEADLINE,
        CARE_RETURN_DATE,
        CARE_RETURN_MODE,
        CARE_SEVERE_CONSEQUENCES,
        DPN_CARE_RETURN_KEY,
        EXAM_REQUIRED_YES,
        RETURN_MODE_SAME,
        evaluate_dpn_care_return,
        extraordinary_exam_belongs_in_upcoming,
        extraordinary_exam_required,
        extraordinary_exam_upcoming_deadline,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import TAB_PO_UKONCENI_DPN
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


def _exam_items(*, today=None):
    return [
        item
        for item in get_attention_items(today=today)
        if item.item_type == ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM
    ]


class PuUpcomingFix2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(self, **overrides):
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": KIND_OVER_3,
            "accident_date": date(2026, 4, 1),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád",
            "dpn_od": date(2026, 4, 1),
            "dpn_do": date(2026, 4, 20),
            "vrchni_dozor": "OIP",
        }
        data.update(overrides)
        return accident_service.create_accident(**data)

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not str(raw).strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _set_care(self, accident, **fields):
        return accident_service.update_accident(
            accident.id,
            dpn_care_return=fields,
        )

    def _required_unfinished(self, accident, *, return_date: date):
        return self._set_care(
            accident,
            **{
                CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
                CARE_RETURN_DATE: return_date,
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
        )

    def test_required_with_deadline_and_not_done_appears(self) -> None:
        return_date = date.today() - timedelta(days=10)
        accident = self._required_unfinished(self._create(), return_date=return_date)
        saved = self._saved_data(accident.id)
        care = saved[DPN_CARE_RETURN_KEY]
        expected = evaluate_dpn_care_return(
            care,
            dpn_od=accident.dpn_od,
            dpn_do=accident.dpn_do,
        )[CARE_EXAM_DEADLINE]
        self.assertTrue(extraordinary_exam_required(care, dpn_od=accident.dpn_od, dpn_do=accident.dpn_do))
        self.assertIsNotNone(expected)
        self.assertTrue(extraordinary_exam_belongs_in_upcoming(accident, saved))

        items = _exam_items()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.date.isoformat(), expected)
        self.assertEqual(item.subtitle, SOURCE_LABEL_KNIHA_URAZU)
        self.assertEqual(item.type_label, "Mimořádná prohlídka")
        self.assertEqual(
            TYPE_LABELS[ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM],
            "Mimořádná prohlídka",
        )
        self.assertIn("Mimořádná pracovnělékařská prohlídka", item.title)
        self.assertIn(f"č. {accident.number}", item.title)
        self.assertEqual(item.open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)
        self.assertEqual(
            item.identity_key,
            f"accident-extraordinary-exam:{accident.id}",
        )

    def test_exam_done_disappears(self) -> None:
        return_date = date.today() - timedelta(days=8)
        accident = self._required_unfinished(self._create(), return_date=return_date)
        self.assertEqual(len(_exam_items()), 1)

        self._set_care(
            accident,
            **{
                CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
                CARE_RETURN_DATE: return_date,
                CARE_RETURN_MODE: RETURN_MODE_SAME,
                CARE_EXAM_DATE: date.today(),
            },
        )
        saved = self._saved_data(accident.id)
        self.assertFalse(extraordinary_exam_belongs_in_upcoming(accident, saved))
        self.assertEqual(_exam_items(), [])

    def test_not_required_does_not_appear(self) -> None:
        accident = self._set_care(
            self._create(),
            **{
                CARE_RETURN_DATE: date.today() - timedelta(days=5),
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
        )
        saved = self._saved_data(accident.id)
        self.assertFalse(
            extraordinary_exam_required(
                saved.get(DPN_CARE_RETURN_KEY),
                dpn_od=accident.dpn_od,
                dpn_do=accident.dpn_do,
            )
        )
        self.assertFalse(extraordinary_exam_belongs_in_upcoming(accident, saved))
        self.assertEqual(_exam_items(), [])

    def test_without_return_date_or_deadline_does_not_appear(self) -> None:
        accident = self._set_care(
            self._create(),
            **{CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES},
        )
        saved = self._saved_data(accident.id)
        evaluated = evaluate_dpn_care_return(
            saved.get(DPN_CARE_RETURN_KEY),
            dpn_od=accident.dpn_od,
            dpn_do=accident.dpn_do,
        )
        self.assertTrue(
            extraordinary_exam_required(
                saved.get(DPN_CARE_RETURN_KEY),
                dpn_od=accident.dpn_od,
                dpn_do=accident.dpn_do,
            )
        )
        self.assertIsNone(evaluated[CARE_EXAM_DEADLINE])
        self.assertIsNone(extraordinary_exam_upcoming_deadline(accident, saved))
        self.assertEqual(_exam_items(), [])

    def test_overdue_and_future_follow_upcoming_rules(self) -> None:
        today = date.today()
        past = self._required_unfinished(
            self._create(jmeno_prijmeni="Minulý"),
            return_date=today - timedelta(days=20),
        )
        future = self._required_unfinished(
            self._create(jmeno_prijmeni="Budoucí"),
            return_date=today + timedelta(days=10),
        )
        items = {item.source_id: item for item in _exam_items(today=today)}
        self.assertEqual(set(items), {past.id, future.id})
        self.assertTrue(attention_item_is_overdue(items[past.id], today=today))
        self.assertFalse(attention_item_is_overdue(items[future.id], today=today))
        self.assertEqual(
            items[past.id].date,
            extraordinary_exam_upcoming_deadline(past, self._saved_data(past.id)),
        )
        self.assertEqual(
            items[future.id].date,
            extraordinary_exam_upcoming_deadline(future, self._saved_data(future.id)),
        )
        ordered = _exam_items(today=today)
        self.assertEqual(
            [item.date for item in ordered],
            sorted(item.date for item in ordered),
        )

    def test_opening_leads_to_accident_on_dpn_tab(self) -> None:
        accident = self._required_unfinished(
            self._create(),
            return_date=date.today() - timedelta(days=6),
        )
        item = _exam_items()[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)

        window = MagicMock()
        MainWindow._open_attention_item(window, item)
        window._open_accident_by_id.assert_called_once_with(
            accident.id,
            focus_tab=TAB_PO_UKONCENI_DPN,
        )

        dialog = AccidentDialog(accident=accident, focus_tab=TAB_PO_UKONCENI_DPN)
        self.assertEqual(dialog.tabs.tabText(dialog.tabs.currentIndex()), TAB_PO_UKONCENI_DPN)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
