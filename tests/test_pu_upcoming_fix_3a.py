"""PU-UPCOMING-FIX-3a: legacy data podpisů po Aktualizaci záznamu."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import date
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
        ITEM_TYPE_ACCIDENT_SIGNED_RECORD,
        SOURCE_LABEL_KNIHA_URAZU,
    )
    from core.dashboard.attention_service import (
        get_attention_items,
        kniha_urazu_reminder_items,
    )
    from core.dashboard.widget_today import classify_reminder_attention_items
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        DPN_RECORD_UPDATE_KEY,
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_AKTUALIZACE_OO,
        OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
        OBLIGATION_AKTUALIZACE_ZP,
        dpn_record_update_belongs_in_upcoming,
        dpn_record_update_is_done,
        dpn_record_update_is_submitted,
        dpn_record_update_overview_from_saved_data,
        dpn_signed_record_belongs_in_upcoming,
        dpn_signed_record_reminder_due,
        parse_saved_date,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


def _items(item_type, *, today=None):
    with patch(
        "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
        return_value=True,
    ):
        items = get_attention_items(today=today)
    return [item for item in items if item.item_type == item_type]


def _sign_items(*, today=None):
    return _items(ITEM_TYPE_ACCIDENT_SIGNED_RECORD, today=today)


def _update_items(*, today=None):
    return _items(ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE, today=today)


class PuUpcomingFix3aTestCase(unittest.TestCase):
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
            "jmeno_prijmeni": "Daniel Macho",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": KIND_OVER_3,
            "accident_date": date(2026, 8, 21),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád",
            "dpn_od": date(2026, 8, 21),
            "dpn_do": date(2026, 9, 4),
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

    def _legacy_post_dpn_row(self, key: str, datum: str = "", cas: str = "") -> dict:
        """Tvar Ohlašovací povinnosti z PU-DPN: datum bez predano/kompletni."""
        return {
            "key": key,
            "predano": False,
            "kompletni": False,
            "lhuta": "",
            "datum": datum,
            "cas": cas,
            "zpusob": METHOD_PORTAL_SUIP if key == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL else "",
            "upresneni": "",
        }

    def _write_live_like_update(
        self,
        accident,
        *,
        portal_datum: str = "2026-09-07",
        portal_cas: str = "10:52",
    ) -> dict:
        saved = self._saved_data(accident.id)
        other = [
            row
            for row in (saved.get("admin_zaslani") or [])
            if row.get("key")
            not in {
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                OBLIGATION_AKTUALIZACE_ZP,
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                OBLIGATION_AKTUALIZACE_OO,
            }
        ]
        zaslani = other + [
            self._legacy_post_dpn_row(
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                datum=portal_datum,
                cas=portal_cas,
            ),
            self._legacy_post_dpn_row(OBLIGATION_AKTUALIZACE_ZP),
            self._legacy_post_dpn_row(
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                datum="2026-09-07",
                cas="10:55",
            ),
            self._legacy_post_dpn_row(
                OBLIGATION_AKTUALIZACE_OO,
                datum="2026-09-07",
                cas="13:35",
            ),
        ]
        return self._write_saved(
            accident.id,
            {
                "admin_zaslani": zaslani,
                DPN_RECORD_UPDATE_KEY: {
                    "portal_suip_done": True,
                    "portal_suip_date": "2026-09-07",
                    "signed_record_done": False,
                    "signed_record_date": None,
                },
            },
        )

    def test_parse_saved_date_accepts_iso_and_czech(self) -> None:
        self.assertEqual(parse_saved_date("2026-09-07"), date(2026, 9, 7))
        self.assertEqual(parse_saved_date("07.09.2026"), date(2026, 9, 7))
        self.assertEqual(parse_saved_date("7.9.2026"), date(2026, 9, 7))
        self.assertEqual(parse_saved_date("07.09.2026 10:52"), date(2026, 9, 7))

    def test_legacy_portal_row_without_predano_creates_signature_reminder(
        self,
    ) -> None:
        accident = self._create()
        saved = self._write_live_like_update(accident)
        overview = self._overview(accident, saved)

        self.assertTrue(dpn_record_update_is_submitted(overview))
        self.assertEqual(overview["portal_suip_date"], "2026-09-07")
        self.assertFalse(overview["signed_record_done"])
        self.assertFalse(dpn_record_update_is_done(overview))
        self.assertFalse(
            dpn_record_update_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )
        self.assertEqual(
            dpn_signed_record_reminder_due(
                accident, saved, union_organization_active=True
            ),
            date(2026, 9, 9),
        )
        self.assertTrue(
            dpn_signed_record_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )

        today = date(2026, 9, 8)
        self.assertEqual(_update_items(today=today), [])
        items = _sign_items(today=today)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.date, date(2026, 9, 9))
        self.assertEqual(item.priority, PRIORITY_CRITICAL)
        self.assertEqual(item.subtitle, SOURCE_LABEL_KNIHA_URAZU)
        self.assertIn("Zajistit podpisy aktualizovaného záznamu", item.title)
        self.assertIn(f"č. {accident.number}", item.title)

        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            attention = get_attention_items(today=today)
        reminders = kniha_urazu_reminder_items(attention, today=today)
        self.assertEqual(
            [item.identity_key for item in reminders],
            [f"accident-signed-record:{accident.id}"],
        )
        burning, due_today = classify_reminder_attention_items(reminders, today)
        self.assertEqual(burning, [])
        self.assertEqual(len(due_today), 1)
        self.assertEqual(due_today[0].date, date(2026, 9, 9))

        reporting_tasks = [
            task
            for task in task_service.get_all_tasks()
            if "podpis" in (task.title or "").casefold()
        ]
        self.assertEqual(reporting_tasks, [])

    def test_czech_portal_date_without_iso_still_yields_due_9_sep(self) -> None:
        accident = self._create()
        saved = self._write_live_like_update(accident, portal_datum="07.09.2026")
        saved[DPN_RECORD_UPDATE_KEY]["portal_suip_date"] = None
        saved = self._write_saved(accident.id, saved)
        due = dpn_signed_record_reminder_due(
            accident, saved, union_organization_active=True
        )
        self.assertEqual(due, date(2026, 9, 9))
        items = _sign_items(today=date(2026, 9, 8))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].date, date(2026, 9, 9))

    def test_json_portal_flags_alone_do_not_create_or_hide_signature_reminder(
        self,
    ) -> None:
        accident = self._create()
        saved = self._write_saved(
            accident.id,
            {
                DPN_RECORD_UPDATE_KEY: {
                    "portal_suip_done": True,
                    "portal_suip_date": "2026-09-07",
                    "signed_record_done": False,
                    "signed_record_date": None,
                }
            },
        )
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
        self.assertEqual(_sign_items(today=date(2026, 9, 8)), [])
        self.assertEqual(len(_update_items(today=date(2026, 9, 8))), 1)


if __name__ == "__main__":
    unittest.main()
