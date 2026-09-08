"""PU-UPCOMING-5: interní připomínky distribuce aktualizovaného záznamu."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import date
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
        ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION,
        SOURCE_LABEL_KNIHA_URAZU,
        TYPE_LABELS,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import (
        get_attention_items,
        kniha_urazu_reminder_items,
    )
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        DPN_DISTRIBUTION_REMINDER_CALENDAR_DAYS,
        DPN_DISTRIBUTION_TITLES,
        DPN_RECORD_UPDATE_KEY,
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OO,
        OBLIGATION_AKTUALIZACE_POLICIE,
        OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
        OBLIGATION_AKTUALIZACE_ZP,
        dpn_distribution_pending_keys,
        dpn_distribution_reminder_due,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


def _items(*, today=None):
    with patch(
        "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
        return_value=True,
    ):
        items = get_attention_items(today=today)
    return [
        item
        for item in items
        if item.item_type == ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION
    ]


class PuUpcoming5TestCase(unittest.TestCase):
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

    def _legacy_row(self, key: str, datum: str = "") -> dict:
        return {
            "key": key,
            "predano": False,
            "kompletni": False,
            "lhuta": "",
            "datum": datum,
            "cas": "",
            "zpusob": METHOD_PORTAL_SUIP if "portal" in key else "",
            "upresneni": "",
        }

    def _set_signed(self, accident, signed_on: date | None, *, done: bool = True) -> dict:
        saved = self._saved_data(accident.id)
        payload = dict(saved.get(DPN_RECORD_UPDATE_KEY) or {})
        payload["signed_record_done"] = done
        payload["signed_record_date"] = signed_on.isoformat() if signed_on else None
        return self._write_saved(accident.id, {DPN_RECORD_UPDATE_KEY: payload})

    def _mark_row_done(self, accident, key: str, sent_on: date) -> dict:
        saved = self._saved_data(accident.id)
        zaslani = list(saved.get("admin_zaslani") or [])
        replaced = False
        for row in zaslani:
            if row.get("key") == key:
                row["datum"] = sent_on.isoformat()
                replaced = True
                break
        if not replaced:
            zaslani.append(self._legacy_row(key, sent_on.isoformat()))
        return self._write_saved(accident.id, {"admin_zaslani": zaslani})

    def test_unsigned_does_not_create_distribution_reminders(self) -> None:
        accident = self._create()
        saved = self._saved_data(accident.id)
        self.assertIsNone(
            dpn_distribution_reminder_due(
                accident, saved, union_organization_active=True
            )
        )
        self.assertEqual(
            dpn_distribution_pending_keys(
                accident, saved, union_organization_active=True
            ),
            [],
        )
        self.assertEqual(_items(today=date(2026, 9, 10)), [])

    def test_signed_without_date_does_not_create_reminders(self) -> None:
        accident = self._create()
        self._set_signed(accident, None, done=True)
        saved = self._saved_data(accident.id)
        self.assertIsNone(
            dpn_distribution_reminder_due(
                accident, saved, union_organization_active=True
            )
        )
        self.assertEqual(_items(today=date(2026, 9, 10)), [])

    def test_signed_creates_relevant_undone_recipients_due_plus_two(self) -> None:
        self.assertEqual(DPN_DISTRIBUTION_REMINDER_CALENDAR_DAYS, 2)
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        saved = self._saved_data(accident.id)
        self.assertEqual(
            dpn_distribution_reminder_due(
                accident, saved, union_organization_active=True
            ),
            date(2026, 9, 11),
        )
        keys = dpn_distribution_pending_keys(
            accident, saved, union_organization_active=True
        )
        self.assertEqual(
            set(keys),
            {
                OBLIGATION_AKTUALIZACE_ZP,
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                OBLIGATION_AKTUALIZACE_OO,
            },
        )
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)

        items = _items(today=date(2026, 9, 10))
        titles = {item.title for item in items}
        self.assertEqual(
            titles,
            {
                DPN_DISTRIBUTION_TITLES[OBLIGATION_AKTUALIZACE_ZP],
                DPN_DISTRIBUTION_TITLES[OBLIGATION_AKTUALIZACE_ZAMESTNANEC],
                DPN_DISTRIBUTION_TITLES[OBLIGATION_AKTUALIZACE_OO],
            },
        )
        for item in items:
            self.assertEqual(item.source_id, accident.id)
            self.assertEqual(item.date, date(2026, 9, 11))
            self.assertEqual(item.priority, PRIORITY_CRITICAL)
            self.assertEqual(item.subtitle, SOURCE_LABEL_KNIHA_URAZU)
            self.assertEqual(
                item.type_label,
                TYPE_LABELS[ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION],
            )
            self.assertNotIn("zákonn", item.title.casefold())
            self.assertNotIn("zákonn", item.type_label.casefold())

        self.assertFalse(any(item.open_metadata.get("obligation_key") == OBLIGATION_AKTUALIZACE_POLICIE for item in items))

    def test_done_zp_hides_only_zp_employee_stays(self) -> None:
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        self._mark_row_done(accident, OBLIGATION_AKTUALIZACE_ZP, date(2026, 9, 10))
        items = _items(today=date(2026, 9, 10))
        keys = {item.open_metadata.get("obligation_key") for item in items}
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZP, keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_ZAMESTNANEC, keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_OO, keys)

    def test_recipients_disappear_independently(self) -> None:
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        self.assertEqual(len(_items(today=date(2026, 9, 10))), 3)

        self._mark_row_done(accident, OBLIGATION_AKTUALIZACE_ZAMESTNANEC, date(2026, 9, 10))
        keys = {item.open_metadata.get("obligation_key") for item in _items(today=date(2026, 9, 10))}
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAMESTNANEC, keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_ZP, keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_OO, keys)

        self._mark_row_done(accident, OBLIGATION_AKTUALIZACE_ZP, date(2026, 9, 10))
        keys = {item.open_metadata.get("obligation_key") for item in _items(today=date(2026, 9, 10))}
        self.assertEqual(keys, {OBLIGATION_AKTUALIZACE_OO})

        self._mark_row_done(accident, OBLIGATION_AKTUALIZACE_OO, date(2026, 9, 10))
        self.assertEqual(_items(today=date(2026, 9, 10)), [])

    def test_already_done_before_signatures_does_not_appear_after(self) -> None:
        accident = self._create()
        self._mark_row_done(accident, OBLIGATION_AKTUALIZACE_ZAMESTNANEC, date(2026, 9, 7))
        self.assertEqual(_items(today=date(2026, 9, 8)), [])
        self._set_signed(accident, date(2026, 9, 9))
        keys = {item.open_metadata.get("obligation_key") for item in _items(today=date(2026, 9, 10))}
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAMESTNANEC, keys)
        self.assertIn(OBLIGATION_AKTUALIZACE_ZP, keys)

    def test_overdue_uses_existing_po_terminu(self) -> None:
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        items = _items(today=date(2026, 9, 12))
        self.assertTrue(items)
        for item in items:
            self.assertTrue(attention_item_is_overdue(item, today=date(2026, 9, 12)))
            self.assertFalse(attention_item_is_overdue(item, today=date(2026, 9, 11)))

    def test_reminders_panel_includes_from_signed_date(self) -> None:
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            attention = get_attention_items(today=date(2026, 9, 9))
        reminders = kniha_urazu_reminder_items(attention, today=date(2026, 9, 9))
        dist = [
            item
            for item in reminders
            if item.item_type == ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION
        ]
        self.assertTrue(dist)
        self.assertTrue(all(item.source_id == accident.id for item in dist))

    def test_no_tasks_created(self) -> None:
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        _items(today=date(2026, 9, 10))
        self.assertFalse(
            any(
                "aktualizovaný záznam" in (task.title or "").casefold()
                for task in task_service.get_all_tasks()
            )
        )
        self.assertIsNotNone(accident.id)

    def test_opening_leads_to_reporting_obligations(self) -> None:
        accident = self._create()
        self._set_signed(accident, date(2026, 9, 9))
        item = next(
            row
            for row in _items(today=date(2026, 9, 10))
            if row.open_metadata.get("obligation_key") == OBLIGATION_AKTUALIZACE_ZP
        )
        self.assertEqual(item.open_metadata.get("obligation_key"), OBLIGATION_AKTUALIZACE_ZP)

        window = MagicMock()
        MainWindow._open_attention_item(window, item)
        window._open_accident_reporting_by_id.assert_called_once_with(
            accident.id,
            focus_obligation_key=OBLIGATION_AKTUALIZACE_ZP,
        )

        dialog = SetreniDialog(
            accident=accident,
            focus_obligation_key=OBLIGATION_AKTUALIZACE_ZP,
        )
        self.assertIn("Administrace úrazu", dialog.windowTitle())
        keys = [row.get("key") for row in dialog.admin_dpn_rows]
        self.assertIn(OBLIGATION_AKTUALIZACE_ZP, keys)
        dialog.close()

    def test_police_appears_only_when_relevant(self) -> None:
        accident = self._create(podezreni_trestny_cin="ANO", jmeno_prijmeni="S TČ")
        self._set_signed(accident, date(2026, 9, 9))
        keys = {
            item.open_metadata.get("obligation_key")
            for item in _items(today=date(2026, 9, 10))
        }
        self.assertIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)
        item = next(
            row
            for row in _items(today=date(2026, 9, 10))
            if row.open_metadata.get("obligation_key") == OBLIGATION_AKTUALIZACE_POLICIE
        )
        self.assertEqual(
            item.title,
            DPN_DISTRIBUTION_TITLES[OBLIGATION_AKTUALIZACE_POLICIE],
        )
        self.assertEqual(item.priority, PRIORITY_CRITICAL)


if __name__ == "__main__":
    unittest.main()
