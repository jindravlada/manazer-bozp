"""PU-UPCOMING-FIX-3: Aktualizace, evidence podpisů a kritická priorita."""

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
        ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE,
        ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
        ITEM_TYPE_ACCIDENT_SIGNED_RECORD,
        SOURCE_LABEL_KNIHA_URAZU,
        TYPE_LABELS,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_dpn_care import (
        CARE_RETURN_DATE,
        CARE_RETURN_MODE,
        CARE_SEVERE_CONSEQUENCES,
        EXAM_REQUIRED_YES,
        RETURN_MODE_SAME,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        DPN_RECORD_UPDATE_KEY,
        DPN_SIGNED_RECORD_REMINDER_CALENDAR_DAYS,
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        dpn_record_update_belongs_in_upcoming,
        dpn_record_update_from_saved_data,
        dpn_record_update_is_done,
        dpn_record_update_is_submitted,
        dpn_record_update_overview_from_saved_data,
        dpn_signed_record_belongs_in_upcoming,
        dpn_signed_record_reminder_due,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import TAB_PO_UKONCENI_DPN
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


def _items(item_type, *, today=None):
    with patch(
        "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
        return_value=True,
    ):
        items = get_attention_items(today=today)
    return [item for item in items if item.item_type == item_type]


def _update_items(*, today=None):
    return _items(ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE, today=today)


def _exam_items(*, today=None):
    return _items(ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM, today=today)


def _sign_items(*, today=None):
    return _items(ITEM_TYPE_ACCIDENT_SIGNED_RECORD, today=today)


class PuUpcomingFix3TestCase(unittest.TestCase):
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

    def _overview(self, accident, saved=None):
        return dpn_record_update_overview_from_saved_data(
            accident,
            saved if saved is not None else self._saved_data(accident.id),
            union_organization_active=True,
        )

    def _mark_portal_sent(self, accident, sent_on: date) -> dict:
        saved = self._saved_data(accident.id)
        zaslani = [
            row
            for row in (saved.get("admin_zaslani") or [])
            if row.get("key") != OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL
        ]
        zaslani.append(
            {
                "key": OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                "datum": sent_on.isoformat(),
                "zpusob": METHOD_PORTAL_SUIP,
                "predano": True,
            }
        )
        return self._write_saved(accident.id, {"admin_zaslani": zaslani})

    def test_required_unsubmitted_is_critical_in_upcoming(self) -> None:
        due = date(2026, 9, 4)
        accident = self._create(dpn_do=due)
        saved = self._saved_data(accident.id)
        overview = self._overview(accident, saved)
        self.assertFalse(dpn_record_update_is_submitted(overview))
        self.assertTrue(
            dpn_record_update_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )
        self.assertFalse(
            dpn_signed_record_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )

        items = _update_items(today=date(2026, 9, 8))
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.date, due)
        self.assertEqual(item.priority, PRIORITY_CRITICAL)
        self.assertEqual(PRIORITY_CRITICAL, "Kritická")
        self.assertEqual(_sign_items(today=date(2026, 9, 8)), [])

    def test_portal_sent_hides_update_even_without_signed_record(self) -> None:
        accident = self._create(dpn_do=date(2026, 9, 4))
        self.assertEqual(len(_update_items(today=date(2026, 9, 8))), 1)

        saved = self._mark_portal_sent(accident, date(2026, 9, 7))
        overview = self._overview(accident, saved)
        self.assertTrue(overview["portal_suip_done"])
        self.assertFalse(overview["signed_record_done"])
        self.assertTrue(dpn_record_update_is_submitted(overview))
        self.assertFalse(dpn_record_update_is_done(overview))
        self.assertFalse(
            dpn_record_update_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )
        self.assertEqual(_update_items(today=date(2026, 9, 8)), [])

    def test_sent_creates_signature_reminder_plus_two_calendar_days(self) -> None:
        self.assertEqual(DPN_SIGNED_RECORD_REMINDER_CALENDAR_DAYS, 2)
        accident = self._create(dpn_do=date(2026, 9, 4))
        saved = self._mark_portal_sent(accident, date(2026, 9, 7))
        due = dpn_signed_record_reminder_due(
            accident, saved, union_organization_active=True
        )
        self.assertEqual(due, date(2026, 9, 9))

        items = _sign_items(today=date(2026, 9, 8))
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.date, date(2026, 9, 9))
        self.assertEqual(item.priority, PRIORITY_CRITICAL)
        self.assertEqual(item.subtitle, SOURCE_LABEL_KNIHA_URAZU)
        self.assertEqual(
            item.type_label,
            "Podpisy aktualizovaného záznamu",
        )
        self.assertEqual(
            TYPE_LABELS[ITEM_TYPE_ACCIDENT_SIGNED_RECORD],
            "Podpisy aktualizovaného záznamu",
        )
        self.assertIn("Zajistit podpisy aktualizovaného záznamu", item.title)
        self.assertIn(f"č. {accident.number}", item.title)
        self.assertEqual(item.open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)
        self.assertEqual(
            item.identity_key,
            f"accident-signed-record:{accident.id}",
        )
        self.assertNotIn("zákonn", item.title.casefold())
        self.assertNotIn("zákonn", item.type_label.casefold())

    def test_ensured_signatures_hide_reminder_and_store_date(self) -> None:
        accident = self._create(dpn_do=date(2026, 9, 4))
        self._mark_portal_sent(accident, date(2026, 9, 7))
        self.assertEqual(len(_sign_items(today=date(2026, 9, 8))), 1)

        dialog = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        tab = dialog.tab_po_ukonceni_dpn_widget
        self.assertTrue(tab.signed_record_done.isEnabled())
        self.assertTrue(tab.signed_record_date.isEnabled())
        self.assertFalse(tab.portal_suip_done.isEnabled())
        tab.signed_record_done.setChecked(True)
        tab.signed_record_date.set_date_value(date(2026, 9, 8))
        accident_service.update_accident(accident.id, **dialog.get_data())
        dialog.close()

        saved = self._saved_data(accident.id)
        stored = dpn_record_update_from_saved_data(saved)
        self.assertTrue(stored["signed_record_done"])
        self.assertEqual(stored["signed_record_date"], "2026-09-08")
        self.assertEqual(saved[DPN_RECORD_UPDATE_KEY]["signed_record_date"], "2026-09-08")
        self.assertFalse(
            dpn_signed_record_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )
        self.assertEqual(_sign_items(today=date(2026, 9, 8)), [])

        reopened = AccidentDialog(accident=accident_service.get_by_id(accident.id))
        reopened_tab = reopened.tab_po_ukonceni_dpn_widget
        self.assertTrue(reopened_tab.signed_record_done.isChecked())
        self.assertEqual(reopened_tab.signed_record_date.get_date(), date(2026, 9, 8))
        reopened.close()

    def test_extraordinary_exam_is_critical(self) -> None:
        accident = accident_service.update_accident(
            self._create(dpn_do=date(2026, 4, 20)).id,
            dpn_care_return={
                CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
                CARE_RETURN_DATE: date.today() + timedelta(days=10),
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
        )
        items = _exam_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_id, accident.id)
        self.assertEqual(items[0].priority, PRIORITY_CRITICAL)

    def test_late_update_does_not_stay_overdue_after_sending(self) -> None:
        today = date(2026, 9, 8)
        accident = self._create(dpn_do=date(2026, 9, 4))
        items = _update_items(today=today)
        self.assertEqual(len(items), 1)
        self.assertTrue(attention_item_is_overdue(items[0], today=today))
        self.assertEqual(items[0].priority, PRIORITY_CRITICAL)

        self._mark_portal_sent(accident, date(2026, 9, 7))
        self.assertEqual(_update_items(today=today), [])
        sign_items = _sign_items(today=today)
        self.assertEqual(len(sign_items), 1)
        self.assertEqual(sign_items[0].date, date(2026, 9, 9))

    def test_opening_signature_reminder_leads_to_dpn_tab(self) -> None:
        accident = self._create(dpn_do=date(2026, 9, 4))
        self._mark_portal_sent(accident, date(2026, 9, 7))
        item = _sign_items(today=date(2026, 9, 8))[0]
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
