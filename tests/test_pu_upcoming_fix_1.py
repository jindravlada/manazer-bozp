"""PU-UPCOMING-FIX-1: Aktualizace záznamu v Nadcházejících událostech."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

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
        ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE,
        SOURCE_LABEL_KNIHA_URAZU,
        TYPE_LABELS,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import get_attention_items
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        POST_DPN_OBLIGATION_KEYS,
        applicable_obligations,
        dpn_record_update_belongs_in_upcoming,
        dpn_record_update_overview_from_saved_data,
        is_dpn_record_update_relevant,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import TAB_PO_UKONCENI_DPN
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"


def _update_items(items=None, *, today=None):
    if items is None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            items = get_attention_items(today=today)
    return [
        item
        for item in items
        if item.item_type == ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE
    ]


class PuUpcomingFix1TestCase(unittest.TestCase):
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
            "dpn_do": None,
            "vrchni_dozor": "OIP",
        }
        data.update(overrides)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            return accident_service.create_accident(**data)

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not str(raw).strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _write_saved(self, accident_id: int, payload: dict) -> dict:
        current = self._saved_data(accident_id)
        current.update(payload)
        investigation_service.save_zajisteni_dukazu(
            accident_id,
            json.dumps(current, ensure_ascii=False),
        )
        return self._saved_data(accident_id)

    def _complete_update(self, accident) -> dict:
        saved = self._saved_data(accident.id)
        zaslani = [
            row
            for row in (saved.get("admin_zaslani") or [])
            if row.get("key") not in POST_DPN_OBLIGATION_KEYS
        ]
        keys = [
            item.key
            for item in applicable_obligations(
                accident,
                saved_data=saved,
                union_organization_active=True,
            )
            if item.key in POST_DPN_OBLIGATION_KEYS
        ]
        for key in keys:
            row = {"key": key, "datum": "2026-04-16"}
            if key == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL:
                row["zpusob"] = METHOD_PORTAL_SUIP
            zaslani.append(row)
        return self._write_saved(accident.id, {"admin_zaslani": zaslani})

    def test_required_unfinished_with_deadline_appears_in_upcoming(self) -> None:
        due = date.today() - timedelta(days=3)
        accident = self._create(dpn_do=due)
        self.assertTrue(is_dpn_record_update_relevant(accident))
        saved = self._saved_data(accident.id)
        self.assertTrue(dpn_record_update_belongs_in_upcoming(accident, saved))

        items = _update_items()
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.date, due)
        self.assertEqual(item.date, accident.dpn_do)
        self.assertEqual(item.subtitle, SOURCE_LABEL_KNIHA_URAZU)
        self.assertEqual(item.type_label, "Aktualizace záznamu")
        self.assertEqual(
            TYPE_LABELS[ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE],
            "Aktualizace záznamu",
        )
        self.assertIn("Aktualizace záznamu", item.title)
        self.assertIn(f"č. {accident.number}", item.title)
        self.assertEqual(item.open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)
        self.assertEqual(
            item.identity_key,
            f"accident-dpn-record-update:{accident.id}",
        )

    def test_fulfilled_update_disappears_from_upcoming(self) -> None:
        accident = self._create(dpn_do=date.today() - timedelta(days=2))
        self.assertEqual(len(_update_items()), 1)

        saved = self._complete_update(accident)
        overview = dpn_record_update_overview_from_saved_data(
            accident,
            saved,
            union_organization_active=True,
        )
        self.assertTrue(overview["portal_suip_done"])
        self.assertFalse(
            dpn_record_update_belongs_in_upcoming(
                accident,
                saved,
                union_organization_active=True,
            )
        )
        self.assertEqual(_update_items(), [])

    def test_not_required_does_not_appear(self) -> None:
        without_end = self._create()
        self.assertFalse(is_dpn_record_update_relevant(without_end))
        self.assertFalse(
            dpn_record_update_belongs_in_upcoming(
                without_end,
                self._saved_data(without_end.id),
            )
        )

        short_pn = self._create(
            jmeno_prijmeni="Petr Krátký",
            druh_urazu=KIND_UP_TO_3,
            dpn_od=date.today() - timedelta(days=2),
            dpn_do=date.today() - timedelta(days=1),
        )
        self.assertFalse(is_dpn_record_update_relevant(short_pn))
        self.assertFalse(
            dpn_record_update_belongs_in_upcoming(
                short_pn,
                self._saved_data(short_pn.id),
            )
        )
        self.assertEqual(_update_items(), [])

    def test_tab_json_alone_does_not_hide_item(self) -> None:
        accident = self._create(dpn_do=date.today() - timedelta(days=1))
        accident_service.update_accident(
            accident.id,
            dpn_record_update={
                "portal_suip_done": True,
                "portal_suip_date": "2026-04-16",
                "signed_record_done": True,
                "signed_record_date": "2026-04-17",
            },
        )
        reloaded = accident_service.get_by_id(accident.id)
        saved = self._saved_data(accident.id)
        self.assertTrue(
            dpn_record_update_belongs_in_upcoming(
                reloaded,
                saved,
                union_organization_active=True,
            )
        )
        self.assertEqual(len(_update_items()), 1)

    def test_upcoming_rules_before_and_after_today(self) -> None:
        today = date.today()
        past = self._create(
            jmeno_prijmeni="Minulý",
            dpn_do=today - timedelta(days=5),
        )
        current = self._create(
            jmeno_prijmeni="Dnes",
            dpn_do=today,
        )
        future = self._create(
            jmeno_prijmeni="Budoucí",
            dpn_do=today + timedelta(days=4),
        )

        items = {item.source_id: item for item in _update_items(today=today)}
        self.assertEqual(set(items), {past.id, current.id, future.id})

        self.assertTrue(attention_item_is_overdue(items[past.id], today=today))
        self.assertFalse(attention_item_is_overdue(items[current.id], today=today))
        self.assertFalse(attention_item_is_overdue(items[future.id], today=today))
        self.assertEqual(items[past.id].date, past.dpn_do)
        self.assertEqual(items[future.id].date, future.dpn_do)

        ordered = _update_items(today=today)
        dates = [item.date for item in ordered]
        self.assertEqual(dates, sorted(dates))

    def test_dialog_opens_po_ukonceni_dpn_tab(self) -> None:
        accident = self._create(dpn_do=date.today())
        dialog = AccidentDialog(accident=accident, focus_tab=TAB_PO_UKONCENI_DPN)
        self.assertEqual(dialog.tabs.tabText(dialog.tabs.currentIndex()), TAB_PO_UKONCENI_DPN)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
