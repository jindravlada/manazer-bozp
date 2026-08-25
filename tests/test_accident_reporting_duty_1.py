"""ACCIDENT-REPORTING-DUTY-1 – společná povinnost vyhotovení a zaslání záznamu."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp(prefix="accident-reporting-duty-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_today import task_should_appear_in_reminders
    from core.services.attachment_service import attachment_service
    from core.shared.constants import ENTITY_ACCIDENT
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_EZOP,
        OBLIGATION_OIP_OBU_OHLASENI,
        OBLIGATION_OIP_OBU_ZASLANI,
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_OO_PREDANI,
        OBLIGATION_POLICIE_OHLASENI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_RODINA_PREDANI,
        OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        OBLIGATION_ZAMESTNANEC_PREDANI,
        OBLIGATION_ZP_OHLASENI,
        OBLIGATION_ZP_ZASLANI,
        OBLIGATION_LABELS,
        RECORD_DUTY_GENERATION_COMBINED,
        RECORD_DUTY_GENERATION_KEY,
        RECORD_DUTY_GENERATION_LEGACY,
        SECTION_ODESLANI,
        SECTION_ZAZNAM,
        add_workdays,
        applicable_obligations,
        collect_obligation_rows_from_saved_data,
        combined_record_duty_deadline,
        obligation_default_deadline,
        obligation_key_from_row,
        obligation_rows_for_summary,
        resolve_record_duty_generation,
        row_is_done,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
        ZAZNAM_TASK_TITLE_PREFIX,
        accident_reporting_task_service,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
COMBINED_LABEL = "Vyhotovení + zaslání záznamu o pracovním úrazu"
LEGACY_VYHOTOVENI_LABEL = "Vyhotovení Záznamu o pracovním úrazu"
LEGACY_ZASLANI_LABEL = "OIP / OBÚ – zaslání záznamu o pracovním úrazu"

_OTHER_RECORD_KEYS = {
    OBLIGATION_ZP_ZASLANI,
    OBLIGATION_EZOP,
    OBLIGATION_ZAMESTNANEC_PREDANI,
    OBLIGATION_OO_PREDANI,
}


class AccidentReportingDuty1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create_new(self, *, vrchni_dozor: str, name: str = "Nový úraz") -> Accident:
        accident_date = date(2026, 7, 27)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            return accident_service.create_accident(
                jmeno_prijmeni=name,
                accident_date=accident_date,
                druh_urazu=KIND_OVER_3,
                dpn_od=accident_date,
                dpn_do=accident_date + timedelta(days=10),
                vrchni_dozor=vrchni_dozor,
            )

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _keys(self, accident, saved_data=None) -> set[str]:
        data = saved_data if saved_data is not None else self._saved_data(accident.id)
        return {
            item.key
            for item in applicable_obligations(accident, saved_data=data)
        }

    def _legacy_accident(self, *, vrchni_dozor: str = "OIP") -> Accident:
        accident_date = date(2026, 6, 1)
        accident = Accident(
            jmeno_prijmeni="Starý úraz",
            accident_date=accident_date,
            druh_urazu=KIND_OVER_3,
            dpn_od=accident_date,
            dpn_do=accident_date + timedelta(days=10),
            vrchni_dozor=vrchni_dozor,
            employee_first_name="Starý",
            employee_last_name="Úraz",
        )
        saved = accident_service.repository.add(accident)
        saved.number = accident_service._make_number(saved.id, saved.year)
        saved = accident_service.repository.update(saved)
        payload = {
            "admin_ohlaseni": [
                {
                    "key": OBLIGATION_OO_OHLASENI,
                    "nazev": "Odborová organizace – ohlášení pracovního úrazu",
                    "datum": "2026-06-02",
                    "upresneni": "historická poznámka ohlášení",
                }
            ],
            "admin_zaslani": [
                {
                    "key": OBLIGATION_VYHOTOVENI_ZAZNAMU,
                    "nazev": LEGACY_VYHOTOVENI_LABEL,
                    "datum": "2026-06-10",
                    "upresneni": "historická poznámka vyhotovení",
                    "zpusob": "Portál SÚIP",
                },
                {
                    "key": OBLIGATION_OIP_OBU_ZASLANI,
                    "nazev": LEGACY_ZASLANI_LABEL,
                    "datum": "",
                    "upresneni": "historická poznámka zaslání",
                },
                {
                    "key": OBLIGATION_EZOP,
                    "nazev": OBLIGATION_LABELS[OBLIGATION_EZOP],
                    "datum": "",
                },
            ],
        }
        investigation_service.save_zajisteni_dukazu(
            saved.id,
            json.dumps(payload, ensure_ascii=False),
        )
        accident_reporting_task_service.sync_for_accident(saved)
        return accident_service.get_by_id(saved.id)

    def _visible_record_titles(self, dialog: SetreniDialog) -> list[str]:
        rows = list(dialog.admin_zaznam_rows) + list(dialog.admin_odeslani_rows)
        return [row["nazev"] for row in rows if dialog._admin_row_relevant(row)]

    def _open_zaznam_tasks(self, accident_id: int):
        return [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident_id
            and not task.completed
            and not task.canceled
            and (task.title or "").startswith(ZAZNAM_TASK_TITLE_PREFIX)
        ]

    def test_catalog_keeps_historical_labels_and_adds_combined_code(self) -> None:
        self.assertEqual(
            OBLIGATION_LABELS[OBLIGATION_VYHOTOVENI_ZAZNAMU],
            LEGACY_VYHOTOVENI_LABEL,
        )
        self.assertEqual(
            OBLIGATION_LABELS[OBLIGATION_OIP_OBU_ZASLANI],
            LEGACY_ZASLANI_LABEL,
        )
        self.assertEqual(
            OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
            "vyhotoveni_zaslani_zaznamu",
        )
        self.assertEqual(
            OBLIGATION_LABELS[OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU],
            COMBINED_LABEL,
        )
        self.assertEqual(
            obligation_key_from_row({"nazev": COMBINED_LABEL}),
            OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
        )

    def test_unstamped_data_stays_legacy(self) -> None:
        self.assertEqual(resolve_record_duty_generation({}), RECORD_DUTY_GENERATION_LEGACY)
        self.assertEqual(resolve_record_duty_generation(None), RECORD_DUTY_GENERATION_LEGACY)

    def test_new_oip_accident_creates_one_combined_duty(self) -> None:
        accident = self._create_new(vrchni_dozor="OIP", name="OIP úraz")
        data = self._saved_data(accident.id)
        keys = self._keys(accident, data)

        self.assertEqual(data.get(RECORD_DUTY_GENERATION_KEY), RECORD_DUTY_GENERATION_COMBINED)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_ZASLANI, keys)
        self.assertTrue(_OTHER_RECORD_KEYS.issubset(keys))
        self.assertIn(OBLIGATION_OO_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_OHLASENI, keys)

        combined = next(
            item
            for item in applicable_obligations(accident, saved_data=data)
            if item.key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
        )
        self.assertEqual(combined.label, COMBINED_LABEL)
        self.assertEqual(combined.section, SECTION_ZAZNAM)

        expected_deadline = combined_record_duty_deadline(accident.accident_date)
        self.assertEqual(expected_deadline, add_workdays(accident.accident_date, 15))
        self.assertEqual(
            obligation_default_deadline(
                accident.accident_date,
                obligation_key=OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
                section=SECTION_ZAZNAM,
            ),
            expected_deadline,
        )
        self.assertEqual(
            obligation_default_deadline(
                accident.accident_date,
                obligation_key=OBLIGATION_VYHOTOVENI_ZAZNAMU,
                section=SECTION_ZAZNAM,
            ),
            expected_deadline,
        )
        self.assertEqual(
            obligation_default_deadline(
                accident.accident_date,
                obligation_key=OBLIGATION_OIP_OBU_ZASLANI,
                section=SECTION_ODESLANI,
            ),
            expected_deadline,
        )

    def test_new_obu_accident_creates_one_combined_duty(self) -> None:
        accident = self._create_new(vrchni_dozor="OBÚ", name="OBÚ úraz")
        keys = self._keys(accident)
        self.assertEqual(accident.vrchni_dozor, "OBÚ")
        self.assertIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_ZASLANI, keys)
        self.assertTrue(_OTHER_RECORD_KEYS.issubset(keys))

    def test_repeated_save_and_refresh_do_not_duplicate(self) -> None:
        accident = self._create_new(vrchni_dozor="OIP", name="Idempotence")
        first = self._saved_data(accident.id)
        accident_service.update_accident(accident.id, vrchni_dozor="OIP")
        accident_reporting_task_service.sync_for_accident(accident)
        accident_reporting_task_service.sync_for_accident(accident)
        accident_service._stamp_combined_record_duty_generation(accident)
        second = self._saved_data(accident.id)

        self.assertEqual(
            first.get(RECORD_DUTY_GENERATION_KEY),
            RECORD_DUTY_GENERATION_COMBINED,
        )
        self.assertEqual(first.get(RECORD_DUTY_GENERATION_KEY), second.get(RECORD_DUTY_GENERATION_KEY))
        self.assertEqual(
            collect_obligation_rows_from_saved_data(first),
            collect_obligation_rows_from_saved_data(second),
        )
        self.assertEqual(len(self._open_zaznam_tasks(accident.id)), 1)
        keys = self._keys(accident, second)
        self.assertEqual(
            [key for key in keys if key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU],
            [OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU],
        )

    def test_combined_fulfillment_notes_and_attachments(self) -> None:
        accident = self._create_new(vrchni_dozor="OIP", name="Splnění")
        accident_date = accident.accident_date
        saved = {
            RECORD_DUTY_GENERATION_KEY: RECORD_DUTY_GENERATION_COMBINED,
            "admin_ohlaseni": [
                {"key": OBLIGATION_OO_OHLASENI, "datum": accident_date.isoformat()}
            ],
            "admin_zaslani": [
                {
                    "key": OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
                    "nazev": COMBINED_LABEL,
                    "datum": accident_date.isoformat(),
                    "upresneni": "odesláno datovou schránkou",
                    "zpusob": "Datová schránka",
                    "predano": True,
                },
                {"key": OBLIGATION_ZP_ZASLANI, "datum": accident_date.isoformat()},
                {"key": OBLIGATION_EZOP, "datum": accident_date.isoformat()},
                {"key": OBLIGATION_ZAMESTNANEC_PREDANI, "datum": ""},
                {"key": OBLIGATION_OO_PREDANI, "datum": accident_date.isoformat()},
            ],
        }
        rows = obligation_rows_for_summary(accident, saved)
        combined_row = next(
            row for row in rows if row["key"] == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
        )
        self.assertTrue(row_is_done(combined_row))
        self.assertEqual(combined_row["upresneni"], "odesláno datovou schránkou")
        self.assertEqual(combined_row["nazev"], COMBINED_LABEL)

        accident_reporting_task_service.sync_for_accident(accident, saved_data=saved)
        self.assertEqual(len(self._open_zaznam_tasks(accident.id)), 1)

        saved["admin_zaslani"][3]["datum"] = accident_date.isoformat()
        accident_reporting_task_service.sync_for_accident(accident, saved_data=saved)
        self.assertEqual(len(self._open_zaznam_tasks(accident.id)), 0)

        source = _TMP / "priloha-zaznam.txt"
        source.write_text("příloha záznamu", encoding="utf-8")
        attachment_service.add_file_as(
            "accident",
            accident.id,
            str(source),
            "priloha-zaznam.txt",
        )
        names = [item.filename for item in attachment_service.get_for_entity("accident", accident.id)]
        self.assertIn("priloha-zaznam.txt", names)

        after_sync = self._saved_data(accident.id)
        self.assertEqual(
            after_sync.get(RECORD_DUTY_GENERATION_KEY),
            RECORD_DUTY_GENERATION_COMBINED,
        )

    def test_combined_duty_appears_in_reminders_and_upcoming(self) -> None:
        accident = self._create_new(vrchni_dozor="OBÚ", name="Připomínky")
        tasks = self._open_zaznam_tasks(accident.id)
        self.assertEqual(len(tasks), 1)
        self.assertIn(COMBINED_LABEL, tasks[0].description)
        self.assertNotIn(LEGACY_VYHOTOVENI_LABEL, tasks[0].description)
        self.assertNotIn(LEGACY_ZASLANI_LABEL, tasks[0].description)

        today = add_workdays(accident.accident_date, 16)
        self.assertTrue(task_should_appear_in_reminders(tasks[0], today))
        titles = {item.title for item in get_attention_items(today=today)}
        self.assertIn(tasks[0].title, titles)

    def test_legacy_accident_keeps_both_original_duties(self) -> None:
        accident = self._legacy_accident()
        original = self._saved_data(accident.id)
        original_dump = json.dumps(original, ensure_ascii=False, sort_keys=True)

        keys = self._keys(accident, original)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertIn(OBLIGATION_OIP_OBU_ZASLANI, keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, keys)
        self.assertEqual(resolve_record_duty_generation(original), RECORD_DUTY_GENERATION_LEGACY)

        accident_service.update_accident(accident.id, vrchni_dozor="OIP")
        accident_reporting_task_service.sync_for_accident(accident)
        accident_service._stamp_combined_record_duty_generation(accident)

        after = self._saved_data(accident.id)
        self.assertEqual(json.dumps(after, ensure_ascii=False, sort_keys=True), original_dump)
        self.assertNotIn(RECORD_DUTY_GENERATION_KEY, after)
        self.assertNotIn(
            OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
            {obligation_key_from_row(row) for row in collect_obligation_rows_from_saved_data(after)},
        )

        dialog = SetreniDialog(accident=accident)
        titles = self._visible_record_titles(dialog)
        self.assertIn(LEGACY_VYHOTOVENI_LABEL, titles)
        self.assertIn(LEGACY_ZASLANI_LABEL, titles)
        self.assertNotIn(COMBINED_LABEL, titles)
        dialog._save_administrativa()
        dialog.close()

        saved_after_ui = self._saved_data(accident.id)
        saved_keys = {
            obligation_key_from_row(row)
            for row in collect_obligation_rows_from_saved_data(saved_after_ui)
        }
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, saved_keys)
        self.assertIn(OBLIGATION_OIP_OBU_ZASLANI, saved_keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, saved_keys)
        vyhotoveni = next(
            row
            for row in collect_obligation_rows_from_saved_data(saved_after_ui)
            if obligation_key_from_row(row) == OBLIGATION_VYHOTOVENI_ZAZNAMU
        )
        self.assertEqual(vyhotoveni["nazev"], LEGACY_VYHOTOVENI_LABEL)
        self.assertEqual(vyhotoveni["datum"], "2026-06-10")
        self.assertEqual(vyhotoveni["upresneni"], "historická poznámka vyhotovení")

        restarted = accident_service.get_by_id(accident.id)
        restarted_data = self._saved_data(restarted.id)
        self.assertEqual(resolve_record_duty_generation(restarted_data), RECORD_DUTY_GENERATION_LEGACY)
        self.assertNotIn(
            OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
            self._keys(restarted, restarted_data),
        )

    def test_new_accident_dialog_shows_single_combined_row(self) -> None:
        accident = self._create_new(vrchni_dozor="OIP", name="UI nový")
        dialog = SetreniDialog(accident=accident)
        titles = self._visible_record_titles(dialog)
        self.assertIn(COMBINED_LABEL, titles)
        self.assertNotIn(LEGACY_VYHOTOVENI_LABEL, titles)
        self.assertNotIn(LEGACY_ZASLANI_LABEL, titles)
        self.assertEqual(titles.count(COMBINED_LABEL), 1)
        self.assertIn(OBLIGATION_LABELS[OBLIGATION_EZOP], titles)
        dialog._save_administrativa()
        dialog.close()

        saved = self._saved_data(accident.id)
        self.assertEqual(saved.get(RECORD_DUTY_GENERATION_KEY), RECORD_DUTY_GENERATION_COMBINED)
        saved_keys = {
            obligation_key_from_row(row)
            for row in collect_obligation_rows_from_saved_data(saved)
        }
        self.assertIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, saved_keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, saved_keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_ZASLANI, saved_keys)

    def test_failed_create_does_not_leave_orphan_duties(self) -> None:
        from sqlalchemy import func, select

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation

        with patch.object(accident_service.repository, "add", side_effect=RuntimeError("add fail")):
            with self.assertRaises(RuntimeError):
                self._create_new(vrchni_dozor="OIP", name="Selhání add")

        with get_session() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Accident)), 0)
            self.assertEqual(
                session.scalar(select(func.count()).select_from(AccidentInvestigation)),
                0,
            )

        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_task_service"
            ".AccidentReportingTaskService.sync_for_accident",
            side_effect=RuntimeError("sync fail"),
        ):
            with self.assertRaises(RuntimeError):
                accident_service.create_accident(
                    jmeno_prijmeni="Selhání sync",
                    accident_date=date(2026, 7, 27),
                    druh_urazu=KIND_OVER_3,
                    dpn_od=date(2026, 7, 27),
                    dpn_do=date(2026, 8, 6),
                    vrchni_dozor="OIP",
                )

        leftover = accident_service.get_all()
        self.assertEqual(len(leftover), 1)
        data = self._saved_data(leftover[0].id)
        self.assertEqual(data.get(RECORD_DUTY_GENERATION_KEY), RECORD_DUTY_GENERATION_COMBINED)
        self.assertEqual(collect_obligation_rows_from_saved_data(data), [])
        self.assertEqual(self._open_zaznam_tasks(leftover[0].id), [])

    def test_serious_combined_keeps_other_notification_duties(self) -> None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Závažný",
                accident_date=date(2026, 7, 27),
                druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
                vrchni_dozor="OIP",
            )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, keys)
        self.assertIn(OBLIGATION_OIP_OBU_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_ZASLANI, keys)

    def test_fatal_combined_keeps_police_and_family_duties(self) -> None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Smrtelný",
                accident_date=date(2026, 7, 27),
                druh_urazu="smrtelný",
                vrchni_dozor="OBÚ",
            )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, keys)
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)
        self.assertIn(OBLIGATION_ZP_OHLASENI, keys)
        self.assertIn(OBLIGATION_RODINA_PREDANI, keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_ZASLANI, keys)


if __name__ == "__main__":
    unittest.main()
