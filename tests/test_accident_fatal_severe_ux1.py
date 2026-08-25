"""ACCIDENT-FATAL-SEVERE-UX1: Portál SÚIP u ohlášení, Policie u smrtelného, barvy."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QRadioButton

_TMP = Path(tempfile.mkdtemp(prefix="accident-fatal-severe-ux1-"))
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
    from core.shared.constants import ENTITY_ACCIDENT
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        METHOD_PORTAL_SUIP,
        OBLIGATION_OIP_OBU_OHLASENI,
        OBLIGATION_POLICIE_OHLASENI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_ZP_OHLASENI,
        applicable_obligations,
        collect_obligation_rows_from_saved_data,
        obligation_key_from_row,
        row_is_done,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
        OHLASENI_TASK_TITLE_PREFIX,
        accident_reporting_task_service,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.accident_table import (
        AccidentTable,
        _INJURY_COLOR_DEFAULT,
        _INJURY_COLOR_FATAL,
        _INJURY_COLOR_LEGEND,
        _INJURY_COLOR_OVER_3_DAYS,
        _INJURY_COLOR_SERIOUS,
        _INJURY_COLOR_UP_TO_3_DAYS,
    )
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.sluzby.task_service import task_service


KIND_FATAL = "smrtelný"
KIND_SERIOUS = "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)"
KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"


def _color_hex(item) -> str:
    color = item.background().color()
    return f"#{color.red():02x}{color.green():02x}{color.blue():02x}"


class AccidentFatalSevereUx1TestCase(unittest.TestCase):
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

    def _create(self, **kwargs):
        data = {
            "jmeno_prijmeni": "Test Úraz",
            "accident_date": date(2026, 3, 10),
            "vrchni_dozor": "OIP",
        }
        data.update(kwargs)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            return accident_service.create_accident(**data)

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _dump(self, accident_id: int) -> str:
        return json.dumps(self._saved_data(accident_id), ensure_ascii=False, sort_keys=True)

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

    def _saved_rows(self, accident_id: int, key: str) -> list[dict]:
        return [
            item
            for item in collect_obligation_rows_from_saved_data(self._saved_data(accident_id))
            if obligation_key_from_row(item) == key
        ]

    def _assert_portal_only_notice(self, dialog: SetreniDialog, *, inspect_group: bool = True) -> dict:
        row = self._row_by_key(dialog, OBLIGATION_OIP_OBU_OHLASENI)
        self.assertEqual(self._method_labels(row), [METHOD_PORTAL_SUIP])
        self.assertNotIn("Datová schránka", self._method_labels(row))
        self.assertNotIn("Jiný způsob", self._method_labels(row))
        self.assertEqual(dialog._radio_choice_value(row["zpusob"]), METHOD_PORTAL_SUIP)
        self.assertEqual(row.get("fixed_sending_method"), METHOD_PORTAL_SUIP)
        self.assertTrue(row.get("show_method_upresneni"))
        self.assertTrue(row["upresneni"].isEnabled())
        if inspect_group:
            group = dialog._admin_row_group(row, "ohlášení")
            group_text = " ".join(child.text() for child in group.findChildren(QLabel))
            self.assertIn(METHOD_PORTAL_SUIP, group_text)
            self.assertIn("Upřesnění", group_text)
            self.assertFalse(row["zpusob"].isVisibleTo(group))
            dialog._portal_notice_group = group
        return row

    def test_serious_2026_oip_notice_is_portal_suip_only(self) -> None:
        accident = self._create(
            jmeno_prijmeni="Závažný Portál",
            druh_urazu=KIND_SERIOUS,
        )
        dialog = SetreniDialog(accident=accident)
        self._assert_portal_only_notice(dialog)
        dialog.close()

    def test_fatal_2026_oip_notice_is_portal_suip_only(self) -> None:
        accident = self._create(
            jmeno_prijmeni="Smrtelný Portál",
            druh_urazu=KIND_FATAL,
        )
        dialog = SetreniDialog(accident=accident)
        self._assert_portal_only_notice(dialog)
        dialog.close()

    def test_oip_notice_upresneni_saves_without_manual_method(self) -> None:
        accident = self._create(
            jmeno_prijmeni="Ohlášení poznámka",
            druh_urazu=KIND_SERIOUS,
        )
        before = self._dump(accident.id)
        dialog = SetreniDialog(accident=accident)
        row = self._assert_portal_only_notice(dialog, inspect_group=False)
        after_open = self._dump(accident.id)
        self.assertEqual(after_open, before)

        row["upresneni"].setText("podání 2026/88")
        dialog._set_date_widget(row["datum"], accident.accident_date)
        row["cas"].setText("09:15")
        self.assertTrue(row_is_done(dialog._admin_row_state_dict(row)))
        dialog._save_administrativa()
        dialog.close()

        saved = self._saved_rows(accident.id, OBLIGATION_OIP_OBU_OHLASENI)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["zpusob"], METHOD_PORTAL_SUIP)
        self.assertEqual(saved[0]["upresneni"], "podání 2026/88")
        self.assertEqual(saved[0]["cas"], "09:15")
        self.assertEqual(saved[0]["datum"], accident.accident_date.isoformat())

    def test_opening_does_not_write_oip_notice_method(self) -> None:
        accident = self._create(
            jmeno_prijmeni="Bez zápisu",
            druh_urazu=KIND_FATAL,
        )
        before = self._dump(accident.id)
        dialog = SetreniDialog(accident=accident)
        self._row_by_key(dialog, OBLIGATION_OIP_OBU_OHLASENI)
        dialog.close()
        self.assertEqual(self._dump(accident.id), before)
        self.assertFalse(
            any(
                (item.get("zpusob") or "")
                for item in self._saved_rows(accident.id, OBLIGATION_OIP_OBU_OHLASENI)
            )
        )

    def test_pre_2026_oip_notice_keeps_legacy_methods(self) -> None:
        accident = self._create(
            jmeno_prijmeni="Starý závažný",
            accident_date=date(2025, 12, 15),
            druh_urazu=KIND_SERIOUS,
        )
        dialog = SetreniDialog(accident=accident)
        row = self._row_by_key(dialog, OBLIGATION_OIP_OBU_OHLASENI)
        self.assertEqual(
            self._method_labels(row),
            [METHOD_PORTAL_SUIP, "Datová schránka", "Jiný způsob"],
        )
        self.assertFalse(row.get("fixed_sending_method"))
        dialog._set_radio_choice(row["zpusob"], "Datová schránka")
        row["upresneni"].setText("starý kanál")
        dialog._save_administrativa()
        dialog.close()

        saved = self._saved_rows(accident.id, OBLIGATION_OIP_OBU_OHLASENI)
        self.assertEqual(saved[0]["zpusob"], "Datová schránka")
        self.assertEqual(saved[0]["upresneni"], "starý kanál")

        again = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        row = self._row_by_key(again, OBLIGATION_OIP_OBU_OHLASENI)
        self.assertEqual(
            self._method_labels(row),
            [METHOD_PORTAL_SUIP, "Datová schránka", "Jiný způsob"],
        )
        self.assertEqual(again._radio_choice_value(row["zpusob"]), "Datová schránka")
        again.close()

    def test_fatal_without_suspicion_creates_police_duties(self) -> None:
        accident = self._create(jmeno_prijmeni="Smrt bez TČ", druh_urazu=KIND_FATAL)
        self.assertNotEqual((accident.podezreni_trestny_cin or "").strip().upper(), "ANO")

        keys = {item.key for item in applicable_obligations(accident)}
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)
        self.assertIn(OBLIGATION_ZP_OHLASENI, keys)

        dialog = SetreniDialog(accident=accident)
        ohlaseni = self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI)
        zaslani = self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI)
        self.assertTrue(dialog._admin_row_relevant(ohlaseni))
        self.assertTrue(dialog._admin_row_relevant(zaslani))
        self.assertEqual(
            sum(1 for row in dialog.admin_ohlaseni_rows if row.get("key") == OBLIGATION_POLICIE_OHLASENI),
            1,
        )
        self.assertEqual(
            sum(1 for row in dialog.admin_odeslani_rows if row.get("key") == OBLIGATION_POLICIE_ZASLANI),
            1,
        )
        dialog.close()

        reloaded = accident_service.get_by_id(accident.id)
        self.assertNotEqual((reloaded.podezreni_trestny_cin or "").strip().upper(), "ANO")

        tasks = [
            task
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident.id
            and (task.title or "").startswith(OHLASENI_TASK_TITLE_PREFIX)
        ]
        self.assertEqual(len(tasks), 1)
        self.assertIn("Policie ČR", tasks[0].description)
        titles = {item.title for item in get_attention_items()}
        self.assertIn(tasks[0].title, titles)

    def test_fatal_with_suspicion_has_same_police_duties_without_duplicate(self) -> None:
        accident = self._create(
            jmeno_prijmeni="Smrt s TČ",
            druh_urazu=KIND_FATAL,
            podezreni_trestny_cin="ANO",
        )
        dialog = SetreniDialog(accident=accident)
        police_keys = [
            row["key"]
            for row in (dialog.admin_ohlaseni_rows + dialog.admin_odeslani_rows)
            if row.get("key") in {OBLIGATION_POLICIE_OHLASENI, OBLIGATION_POLICIE_ZASLANI}
        ]
        self.assertEqual(
            sorted(police_keys),
            [OBLIGATION_POLICIE_OHLASENI, OBLIGATION_POLICIE_ZASLANI],
        )
        dialog._save_administrativa()
        dialog.close()
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        dialog._save_administrativa()
        dialog.close()

        saved_ohlaseni = self._saved_rows(accident.id, OBLIGATION_POLICIE_OHLASENI)
        saved_zaslani = self._saved_rows(accident.id, OBLIGATION_POLICIE_ZASLANI)
        self.assertEqual(len(saved_ohlaseni), 1)
        self.assertEqual(len(saved_zaslani), 1)

    def test_serious_police_depends_on_suspicion(self) -> None:
        without = self._create(jmeno_prijmeni="Závažný bez TČ", druh_urazu=KIND_SERIOUS)
        dialog = SetreniDialog(accident=without)
        self.assertFalse(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI))
        )
        self.assertFalse(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI))
        )
        dialog.close()

        with_suspicion = self._create(
            jmeno_prijmeni="Závažný s TČ",
            druh_urazu=KIND_SERIOUS,
            podezreni_trestny_cin="ANO",
        )
        dialog = SetreniDialog(accident=with_suspicion)
        self.assertTrue(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI))
        )
        self.assertTrue(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI))
        )
        dialog.close()

    def test_other_kind_with_suspicion_keeps_current_police_rule(self) -> None:
        short = self._create(
            jmeno_prijmeni="Krátká PN s TČ",
            druh_urazu=KIND_UP_TO_3,
            dpn_od=date(2026, 3, 10),
            dpn_do=date(2026, 3, 11),
            podezreni_trestny_cin="ANO",
        )
        dialog = SetreniDialog(accident=short)
        self.assertTrue(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI))
        )
        self.assertFalse(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI))
        )
        dialog.close()

        over = self._create(
            jmeno_prijmeni="PN nad 3 s TČ",
            druh_urazu=KIND_OVER_3,
            dpn_od=date(2026, 3, 10),
            dpn_do=date(2026, 3, 20),
            podezreni_trestny_cin="ANO",
        )
        dialog = SetreniDialog(accident=over)
        self.assertTrue(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI))
        )
        self.assertTrue(
            dialog._admin_row_relevant(self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI))
        )
        dialog.close()

    def test_kind_change_preserves_filled_police_without_duplicates(self) -> None:
        accident = self._create(jmeno_prijmeni="Změna druhu", druh_urazu=KIND_FATAL)
        dialog = SetreniDialog(accident=accident)
        ohlaseni = self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI)
        zaslani = self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI)
        dialog._set_date_widget(ohlaseni["datum"], accident.accident_date)
        ohlaseni["cas"].setText("11:20")
        dialog._set_radio_choice(ohlaseni["zpusob"], "E-mail")
        ohlaseni["upresneni"].setText("ohlášeno na OO")
        dialog._set_date_widget(zaslani["datum"], accident.accident_date + timedelta(days=2))
        zaslani["upresneni"].setText("záznam doručen")
        dialog._save_administrativa()
        dialog.close()

        accident_service.update_accident(
            accident.id,
            druh_urazu=KIND_SERIOUS,
            podezreni_trestny_cin="NE",
        )
        changed = accident_service.get_by_id(accident.id)
        dialog = SetreniDialog(accident=changed)
        ohlaseni = self._row_by_key(dialog, OBLIGATION_POLICIE_OHLASENI)
        zaslani = self._row_by_key(dialog, OBLIGATION_POLICIE_ZASLANI)
        self.assertFalse(dialog._admin_row_relevant(ohlaseni))
        self.assertFalse(dialog._admin_row_relevant(zaslani))
        self.assertEqual(ohlaseni["cas"].text(), "11:20")
        self.assertEqual(ohlaseni["upresneni"].text(), "ohlášeno na OO")
        self.assertEqual(dialog._radio_choice_value(ohlaseni["zpusob"]), "E-mail")
        self.assertEqual(zaslani["upresneni"].text(), "záznam doručen")
        dialog._save_administrativa()
        dialog.close()

        self.assertEqual(len(self._saved_rows(accident.id, OBLIGATION_POLICIE_OHLASENI)), 1)
        self.assertEqual(len(self._saved_rows(accident.id, OBLIGATION_POLICIE_ZASLANI)), 1)
        saved = self._saved_rows(accident.id, OBLIGATION_POLICIE_OHLASENI)[0]
        self.assertEqual(saved["cas"], "11:20")
        self.assertEqual(saved["upresneni"], "ohlášeno na OO")
        self.assertEqual(saved["zpusob"], "E-mail")

        accident_reporting_task_service.sync_for_accident(changed)
        self.assertEqual(len(self._saved_rows(accident.id, OBLIGATION_POLICIE_OHLASENI)), 1)

    def test_injury_indicator_colors_follow_kind_after_sort_and_select(self) -> None:
        fatal = self._create(jmeno_prijmeni="C-smrt", druh_urazu=KIND_FATAL)
        serious = self._create(jmeno_prijmeni="B-zavaz", druh_urazu=KIND_SERIOUS)
        over = self._create(
            jmeno_prijmeni="D-nad",
            druh_urazu=KIND_OVER_3,
            dpn_od=date(2026, 3, 10),
            dpn_do=date(2026, 3, 20),
        )
        up_to = self._create(
            jmeno_prijmeni="A-do",
            druh_urazu=KIND_UP_TO_3,
            dpn_od=date(2026, 3, 10),
            dpn_do=date(2026, 3, 11),
        )
        other = self._create(jmeno_prijmeni="E-jiny", druh_urazu="")

        expected = {
            fatal.id: _INJURY_COLOR_FATAL,
            serious.id: _INJURY_COLOR_SERIOUS,
            over.id: _INJURY_COLOR_OVER_3_DAYS,
            up_to.id: _INJURY_COLOR_UP_TO_3_DAYS,
            other.id: _INJURY_COLOR_DEFAULT,
        }

        table = AccidentTable()
        self.assertIn("černá", table.horizontalHeaderItem(0).toolTip())
        self.assertEqual(table.horizontalHeaderItem(0).toolTip(), _INJURY_COLOR_LEGEND)
        table.load_accidents([serious, other, fatal, up_to, over])

        def colors_by_id() -> dict[int, str]:
            mapping = {}
            for row in range(table.rowCount()):
                record_id = int(table.item(row, 1).text())
                mapping[record_id] = _color_hex(table.item(row, 0))
            return mapping

        self.assertEqual(colors_by_id(), expected)

        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(colors_by_id(), expected)
        names = [table.item(row, 4).text() for row in range(table.rowCount())]
        self.assertEqual(names, ["A-do", "B-zavaz", "C-smrt", "D-nad", "E-jiny"])
        self.assertEqual(_color_hex(table.item(2, 0)), _INJURY_COLOR_FATAL)
        self.assertEqual(_color_hex(table.item(1, 0)), _INJURY_COLOR_SERIOUS)

        table.selectRow(2)
        self.assertEqual(_color_hex(table.item(2, 0)), _INJURY_COLOR_FATAL)
        self.assertEqual(int(table.item(2, 1).text()), fatal.id)
        self.assertIn("černá", table.item(2, 0).toolTip())
        self.assertIn("červená", table.item(1, 0).toolTip())

        table.sortItems(3, Qt.SortOrder.DescendingOrder)
        self.assertEqual(colors_by_id(), expected)
        table.selectRow(0)
        selected_id = int(table.item(0, 1).text())
        self.assertEqual(_color_hex(table.item(0, 0)), expected[selected_id])
