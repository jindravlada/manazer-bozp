"""DASHBOARD-EVENT-SOURCE-ACCIDENT-DUTY-UX1: zdroj události a Portál SÚIP."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QRadioButton

_TMP = Path(tempfile.mkdtemp(prefix="dashboard-event-source-ux1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_MEETING,
        TYPE_LABELS,
        meeting_dashboard_source_label,
    )
    from core.dashboard.attention_service import get_attention_items
    from core.dashboard.widget_today import (
        TodayWidget,
        meeting_reminder_attention_item,
    )
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from core.shared.constants import ENTITY_ACCIDENT
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        METHOD_PORTAL_SUIP,
        OBLIGATION_EZOP,
        OBLIGATION_LABELS,
        OBLIGATION_OIP_OBU_OHLASENI,
        OBLIGATION_OIP_OBU_ZASLANI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        OBLIGATION_ZP_ZASLANI,
        RECORD_DUTY_GENERATION_COMBINED,
        RECORD_DUTY_GENERATION_KEY,
        applicable_obligations,
        collect_obligation_rows_from_saved_data,
        obligation_key_from_row,
        row_is_done,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
        ZAZNAM_TASK_TITLE_PREFIX,
        accident_reporting_task_service,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.schuzky.constants import STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.ui.meeting_dialog import MeetingDialog
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
COMBINED_LABEL = "Vyhotovení + zaslání záznamu o pracovním úrazu – OIP/OBÚ"
LEGACY_VYHOTOVENI_LABEL = "Vyhotovení Záznamu o pracovním úrazu"
LEGACY_ZASLANI_LABEL = "OIP / OBÚ – zaslání záznamu o pracovním úrazu"
LOCATION = "Tušimice – odbory"


class DashboardEventSourceAccidentDutyUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
        from moduly.schuzky.modely.meeting import Meeting
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.execute(delete(Meeting))
            session.commit()

        self.organizer = person_service.create_person(
            first_name="Vladimír",
            last_name="Jindra",
            title_before="Ing.",
        )

    def _create_meeting(self, **kwargs):
        data = {
            "title": "Porada BOZP",
            "starts_at": datetime.now() + timedelta(days=2, hours=3),
            "status": STATUS_PLANNED,
            "organizer_person_id": self.organizer.id,
        }
        data.update(kwargs)
        return meeting_service.create_meeting(**data)

    def _upcoming_source(self, meeting_id: int) -> str | None:
        widget = UpcomingTasksWidget()
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting_id:
                return widget.table.item(row, 4).text()
        return None

    def _attention_item(self, meeting_id: int):
        matches = [
            item
            for item in get_attention_items()
            if item.item_type == ITEM_TYPE_MEETING and item.source_id == meeting_id
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def _create_combined_accident(self, *, name: str = "Nový úraz"):
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
                vrchni_dozor="OIP",
            )

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _legacy_accident(self) -> Accident:
        accident_date = date(2026, 6, 1)
        accident = Accident(
            jmeno_prijmeni="Starý úraz",
            accident_date=accident_date,
            druh_urazu=KIND_OVER_3,
            dpn_od=accident_date,
            dpn_do=accident_date + timedelta(days=10),
            vrchni_dozor="OIP",
            employee_first_name="Starý",
            employee_last_name="Úraz",
        )
        saved = accident_service.repository.add(accident)
        saved.number = accident_service._make_number(saved.id, saved.year)
        saved = accident_service.repository.update(saved)
        payload = {
            "admin_zaslani": [
                {
                    "key": OBLIGATION_VYHOTOVENI_ZAZNAMU,
                    "nazev": LEGACY_VYHOTOVENI_LABEL,
                    "zpusob": "Datová schránka",
                },
                {
                    "key": OBLIGATION_OIP_OBU_ZASLANI,
                    "nazev": LEGACY_ZASLANI_LABEL,
                    "zpusob": "Jiný způsob",
                    "upresneni": "osobně na OIP",
                },
            ]
        }
        investigation_service.save_zajisteni_dukazu(
            saved.id,
            json.dumps(payload, ensure_ascii=False),
        )
        return accident_service.get_by_id(saved.id)

    def _row_by_key(self, dialog: SetreniDialog, key: str) -> dict:
        rows = (
            list(dialog.admin_ohlaseni_rows)
            + list(dialog.admin_zaznam_rows)
            + list(dialog.admin_odeslani_rows)
            + list(dialog.admin_predani_rows)
        )
        for row in rows:
            if row.get("key") == key:
                return row
        self.fail(f"Povinnost {key} nebyla nalezena.")

    def _method_labels(self, row: dict) -> list[str]:
        return [child.text() for child in row["zpusob"].findChildren(QRadioButton)]

    def test_event_source_uses_location_not_organizer(self) -> None:
        meeting = self._create_meeting(location=LOCATION)
        self.assertEqual(meeting_dashboard_source_label(meeting), LOCATION)
        item = self._attention_item(meeting.id)
        self.assertEqual(item.subtitle, LOCATION)
        self.assertNotIn(self.organizer.display_name, item.subtitle)
        self.assertEqual(self._upcoming_source(meeting.id), LOCATION)

        reminder = meeting_reminder_attention_item(meeting)
        self.assertEqual(reminder.subtitle, LOCATION)
        self.assertNotIn(self.organizer.display_name, reminder.subtitle)

        today = date.today()
        due = self._create_meeting(
            title="Dnes",
            location=LOCATION,
            starts_at=datetime(today.year, today.month, today.day, 10, 0),
        )
        widget = TodayWidget()
        widget.refresh(today=today)
        html = widget.content.text()
        self.assertIn(LOCATION, html)
        self.assertNotIn(due.organizer_name, html)

    def test_event_without_location_uses_impersonal_fallback(self) -> None:
        meeting = self._create_meeting(location="")
        fallback = TYPE_LABELS[ITEM_TYPE_MEETING]
        self.assertEqual(fallback, "Událost")
        self.assertEqual(meeting_dashboard_source_label(meeting), fallback)
        item = self._attention_item(meeting.id)
        self.assertEqual(item.subtitle, fallback)
        self.assertNotIn(self.organizer.display_name, item.subtitle)
        self.assertEqual(self._upcoming_source(meeting.id), fallback)

        reminder = meeting_reminder_attention_item(meeting)
        self.assertEqual(reminder.subtitle, fallback)
        self.assertNotIn(self.organizer.display_name, reminder.subtitle)

    def test_organizer_stays_in_event_detail_and_open_still_works(self) -> None:
        meeting = self._create_meeting(location=LOCATION)
        loaded = meeting_service.get_by_id(meeting.id)
        self.assertEqual(loaded.organizer_person_id, self.organizer.id)
        self.assertIn("Jindra", loaded.organizer_name)

        dialog = MeetingDialog(meeting=loaded)
        ref = dialog.organizer_selector.current_ref()
        self.assertIsNotNone(ref)
        self.assertEqual(int(ref["source_id"]), self.organizer.id)
        dialog.close()

        opened: list[tuple[str, int]] = []

        def on_open(item) -> None:
            opened.append((item.source_type, item.source_id))

        widget = UpcomingTasksWidget(open_attention_callback=on_open)
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id == meeting.id:
                widget.table.selectRow(row)
                widget._open_selected()
                break
        self.assertEqual(opened, [(ITEM_TYPE_MEETING, meeting.id)])

    def test_combined_duty_label_and_stable_code(self) -> None:
        self.assertEqual(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, "vyhotoveni_zaslani_zaznamu")
        self.assertEqual(
            OBLIGATION_LABELS[OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU],
            COMBINED_LABEL,
        )
        self.assertEqual(
            OBLIGATION_LABELS[OBLIGATION_VYHOTOVENI_ZAZNAMU],
            LEGACY_VYHOTOVENI_LABEL,
        )
        self.assertEqual(
            OBLIGATION_LABELS[OBLIGATION_OIP_OBU_ZASLANI],
            LEGACY_ZASLANI_LABEL,
        )
        accident = self._create_combined_accident()
        data = self._saved_data(accident.id)
        labels = [
            item.label
            for item in applicable_obligations(accident, saved_data=data)
            if item.key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
        ]
        self.assertEqual(labels, [COMBINED_LABEL])

        dialog = SetreniDialog(accident=accident)
        row = self._row_by_key(dialog, OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU)
        self.assertEqual(row["nazev"], COMBINED_LABEL)
        dialog.close()

        tasks = [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident.id
            and (task.title or "").startswith(ZAZNAM_TASK_TITLE_PREFIX)
        ]
        self.assertEqual(len(tasks), 1)
        self.assertIn(COMBINED_LABEL, tasks[0].description)
        titles = {item.title for item in get_attention_items()}
        self.assertIn(tasks[0].title, titles)

    def test_combined_duty_uses_only_portal_suip(self) -> None:
        accident = self._create_combined_accident(name="Portál")
        before = self._saved_data(accident.id)
        before_dump = json.dumps(before, ensure_ascii=False, sort_keys=True)

        dialog = SetreniDialog(accident=accident)
        row = self._row_by_key(dialog, OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU)
        self.assertEqual(self._method_labels(row), [METHOD_PORTAL_SUIP])
        self.assertNotIn("Datová schránka", self._method_labels(row))
        self.assertNotIn("Jiný způsob", self._method_labels(row))
        self.assertEqual(dialog._radio_choice_value(row["zpusob"]), METHOD_PORTAL_SUIP)
        self.assertEqual(row.get("fixed_sending_method"), METHOD_PORTAL_SUIP)

        group = dialog._admin_row_group(row, "vyhotovení / odeslání")
        group_text = " ".join(child.text() for child in group.findChildren(QLabel))
        self.assertIn(METHOD_PORTAL_SUIP, group_text)
        self.assertNotIn("Upřesnění", group_text)
        self.assertFalse(row["zpusob"].isVisibleTo(group))

        after_open = self._saved_data(accident.id)
        self.assertEqual(json.dumps(after_open, ensure_ascii=False, sort_keys=True), before_dump)
        self.assertFalse(any(
            obligation_key_from_row(item) == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
            and (item.get("zpusob") or "")
            for item in collect_obligation_rows_from_saved_data(after_open)
        ))

        dialog._set_date_widget(row["datum"], accident.accident_date)
        self.assertTrue(row_is_done(dialog._admin_row_state_dict(row)))
        dialog._save_administrativa()
        dialog.close()

        saved = self._saved_data(accident.id)
        combined = next(
            item
            for item in collect_obligation_rows_from_saved_data(saved)
            if obligation_key_from_row(item) == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
        )
        self.assertEqual(combined["zpusob"], METHOD_PORTAL_SUIP)
        self.assertEqual(combined["nazev"], COMBINED_LABEL)
        self.assertEqual(saved.get(RECORD_DUTY_GENERATION_KEY), RECORD_DUTY_GENERATION_COMBINED)

        accident_reporting_task_service.sync_for_accident(accident)
        accident_service.update_accident(accident.id, vrchni_dozor="OIP")
        again = self._saved_data(accident.id)
        keys = [
            obligation_key_from_row(item)
            for item in collect_obligation_rows_from_saved_data(again)
            if obligation_key_from_row(item) == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
        ]
        self.assertEqual(keys, [OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU])

    def test_opening_does_not_rewrite_saved_combined_method(self) -> None:
        accident = self._create_combined_accident(name="Testovací způsob")
        data = self._saved_data(accident.id)
        data.setdefault("admin_zaslani", []).append(
            {
                "key": OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
                "nazev": "Vyhotovení + zaslání záznamu o pracovním úrazu",
                "zpusob": "Datová schránka",
            }
        )
        investigation_service.save_zajisteni_dukazu(
            accident.id,
            json.dumps(data, ensure_ascii=False),
        )
        before = self._saved_data(accident.id)
        dialog = SetreniDialog(accident=accident)
        row = self._row_by_key(dialog, OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU)
        self.assertEqual(dialog._radio_choice_value(row["zpusob"]), METHOD_PORTAL_SUIP)
        self.assertEqual(row["nazev"], COMBINED_LABEL)
        dialog.close()
        after = self._saved_data(accident.id)
        combined = next(
            item
            for item in collect_obligation_rows_from_saved_data(after)
            if obligation_key_from_row(item) == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU
        )
        self.assertEqual(combined["zpusob"], "Datová schránka")
        self.assertEqual(
            json.dumps(after, ensure_ascii=False, sort_keys=True),
            json.dumps(before, ensure_ascii=False, sort_keys=True),
        )

    def test_legacy_accident_keeps_two_rows_and_original_methods(self) -> None:
        accident = self._legacy_accident()
        dialog = SetreniDialog(accident=accident)
        titles = [
            row["nazev"]
            for row in (dialog.admin_zaznam_rows + dialog.admin_odeslani_rows)
            if dialog._admin_row_relevant(row)
        ]
        self.assertIn(LEGACY_VYHOTOVENI_LABEL, titles)
        self.assertIn(LEGACY_ZASLANI_LABEL, titles)
        self.assertNotIn(COMBINED_LABEL, titles)

        vyhotoveni = self._row_by_key(dialog, OBLIGATION_VYHOTOVENI_ZAZNAMU)
        zaslani = self._row_by_key(dialog, OBLIGATION_OIP_OBU_ZASLANI)
        for row in (vyhotoveni, zaslani):
            self.assertEqual(
                self._method_labels(row),
                [METHOD_PORTAL_SUIP, "Datová schránka", "Jiný způsob"],
            )
        self.assertEqual(dialog._radio_choice_value(vyhotoveni["zpusob"]), "Datová schránka")
        self.assertEqual(dialog._radio_choice_value(zaslani["zpusob"]), "Jiný způsob")
        self.assertEqual(zaslani["upresneni"].text(), "osobně na OIP")
        dialog.close()

    def test_other_recipients_keep_current_sending_options(self) -> None:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            accident = accident_service.create_accident(
                jmeno_prijmeni="Závažný adresáti",
                accident_date=date(2026, 7, 27),
                druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
                podezreni_trestny_cin="ANO",
                vrchni_dozor="OBÚ",
            )
        dialog = SetreniDialog(accident=accident)
        zp = self._row_by_key(dialog, OBLIGATION_ZP_ZASLANI)
        self.assertEqual(
            self._method_labels(zp),
            ["Datová schránka", "E-mail", "Listinná podoba", "Jiný způsob"],
        )
        oip_notice = self._row_by_key(dialog, OBLIGATION_OIP_OBU_OHLASENI)
        self.assertEqual(
            self._method_labels(oip_notice),
            [METHOD_PORTAL_SUIP, "Datová schránka", "Jiný způsob"],
        )
        police = self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI)
        self.assertEqual(
            self._method_labels(police),
            ["Datová schránka", "E-mail", "Listinná podoba", "Jiný způsob"],
        )
        ezop = self._row_by_key(dialog, OBLIGATION_EZOP)
        group = dialog._admin_row_group(ezop, "ohlášení")
        group_text = " ".join(child.text() for child in group.findChildren(QLabel))
        self.assertNotIn("Způsob", group_text)
        self.assertFalse(any(
            child.isChecked()
            for child in zp["zpusob"].findChildren(QRadioButton)
        ))
        dialog.close()


if __name__ == "__main__":
    unittest.main()
