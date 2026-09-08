"""PU-UPCOMING-FIX-3: kritická priorita a odeslání Aktualizace záznamu."""

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
        ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
        attention_item_is_overdue,
    )
    from core.dashboard.attention_service import get_attention_items
    from moduly.agenda.constants import PRIORITY_CRITICAL
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_dpn_care import (
        CARE_EXAM_DATE,
        CARE_RETURN_DATE,
        CARE_RETURN_MODE,
        CARE_SEVERE_CONSEQUENCES,
        EXAM_REQUIRED_YES,
        RETURN_MODE_SAME,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        dpn_record_update_belongs_in_upcoming,
        dpn_record_update_is_done,
        dpn_record_update_is_submitted,
        dpn_record_update_overview_from_saved_data,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
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

    def _required_exam(self, accident, *, return_date: date, exam_date=None):
        fields = {
            CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
            CARE_RETURN_DATE: return_date,
            CARE_RETURN_MODE: RETURN_MODE_SAME,
        }
        if exam_date is not None:
            fields[CARE_EXAM_DATE] = exam_date
        return accident_service.update_accident(accident.id, dpn_care_return=fields)

    def test_required_unsubmitted_is_critical_in_upcoming(self) -> None:
        due = date(2026, 9, 4)
        accident = self._create(dpn_do=due)
        saved = self._saved_data(accident.id)
        overview = self._overview(accident, saved)
        self.assertFalse(dpn_record_update_is_submitted(overview))
        self.assertFalse(dpn_record_update_is_done(overview))
        self.assertTrue(
            dpn_record_update_belongs_in_upcoming(
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

    def test_portal_sent_hides_item_even_without_signed_record(self) -> None:
        accident = self._create(dpn_do=date(2026, 9, 4))
        self.assertEqual(len(_update_items(today=date(2026, 9, 8))), 1)

        saved = self._mark_portal_sent(accident, date(2026, 9, 7))
        overview = self._overview(accident, saved)
        self.assertTrue(overview["portal_suip_done"])
        self.assertEqual(overview["portal_suip_date"], "2026-09-07")
        self.assertFalse(overview["signed_record_done"])
        self.assertTrue(dpn_record_update_is_submitted(overview))
        self.assertFalse(dpn_record_update_is_done(overview))
        self.assertFalse(
            dpn_record_update_belongs_in_upcoming(
                accident, saved, union_organization_active=True
            )
        )
        self.assertEqual(_update_items(today=date(2026, 9, 8)), [])

    def test_sent_after_deadline_does_not_stay_overdue(self) -> None:
        today = date(2026, 9, 8)
        accident = self._create(dpn_do=date(2026, 9, 4))
        items = _update_items(today=today)
        self.assertEqual(len(items), 1)
        self.assertTrue(attention_item_is_overdue(items[0], today=today))
        self.assertEqual(items[0].priority, PRIORITY_CRITICAL)

        self._mark_portal_sent(accident, date(2026, 9, 7))
        self.assertEqual(_update_items(today=today), [])

    def test_extraordinary_exam_is_critical(self) -> None:
        accident = self._required_exam(
            self._create(dpn_do=date(2026, 4, 20)),
            return_date=date.today() + timedelta(days=10),
        )
        items = _exam_items()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source_id, accident.id)
        self.assertEqual(items[0].priority, PRIORITY_CRITICAL)
        self.assertFalse(attention_item_is_overdue(items[0]))

    def test_overdue_exam_stays_critical_and_overdue(self) -> None:
        today = date.today()
        accident = self._required_exam(
            self._create(dpn_do=date(2026, 4, 20), jmeno_prijmeni="Po termínu"),
            return_date=today - timedelta(days=20),
        )
        items = _exam_items(today=today)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.source_id, accident.id)
        self.assertEqual(item.priority, PRIORITY_CRITICAL)
        self.assertTrue(attention_item_is_overdue(item, today=today))


if __name__ == "__main__":
    unittest.main()
