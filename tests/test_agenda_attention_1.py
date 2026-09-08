"""AGENDA-ATTENTION-1: AttentionItem v centrální Agendě a řazení Termín → Priorita."""

from __future__ import annotations

import importlib
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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
        ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION,
        SOURCE_LABEL_KNIHA_URAZU,
    )
    from core.dashboard.widget_upcoming_tasks import (
        COL_TYPE as UPCOMING_COL_TYPE,
        UpcomingTasksWidget,
    )
    from core.windows.main_window import MainWindow
    from moduly.agenda.constants import (
        COL_TITLE,
        ITEM_TYPE_TASK,
        PRIORITY_COLORS,
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_NORMAL,
        STATUS_MODE_ACTIVE,
    )
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.audity.sluzby.audit_service import audit_service
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
        DPN_DISTRIBUTION_TITLES,
        DPN_RECORD_UPDATE_KEY,
        METHOD_PORTAL_SUIP,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_AKTUALIZACE_ZP,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.tabs.tab_po_ukonceni_dpn import TAB_PO_UKONCENI_DPN
    from moduly.ukoly.constants import TASK_STATUS_ACTIVE
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"


def _kniha_items(items):
    return [
        item
        for item in items
        if item.source == SOURCE_LABEL_KNIHA_URAZU or item.item_type.startswith("accident_")
    ]


class AgendaAttention1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        self._union = patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        )
        self._union.start()
        self.addCleanup(self._union.stop)

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def _create_accident(self, **overrides):
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

    def _set_signed(self, accident, signed_on: date, *, done: bool = True) -> dict:
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
            zaslani.append(
                {
                    "key": key,
                    "predano": False,
                    "kompletni": False,
                    "lhuta": "",
                    "datum": sent_on.isoformat(),
                    "cas": "",
                    "zpusob": "",
                    "upresneni": "",
                }
            )
        return self._write_saved(accident.id, {"admin_zaslani": zaslani})

    def _required_exam(self, accident, *, return_date: date):
        return accident_service.update_accident(
            accident.id,
            dpn_care_return={
                CARE_SEVERE_CONSEQUENCES: EXAM_REQUIRED_YES,
                CARE_RETURN_DATE: return_date,
                CARE_RETURN_MODE: RETURN_MODE_SAME,
            },
        )

    def _find_agenda(self, items, *, item_type: str, source_id: int, obligation_key=None):
        matches = [
            item
            for item in items
            if item.item_type == item_type and int(item.source_id) == int(source_id)
        ]
        if obligation_key is not None:
            matches = [
                item
                for item in matches
                if item.open_metadata.get("obligation_key") == obligation_key
            ]
        self.assertTrue(matches, f"Chybí {item_type} / {source_id} / {obligation_key}")
        return matches[0]

    def _select_agenda_row(self, page: AgendaPage, *, item_type: str, source_id: int, obligation_key=None):
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if payload is None or payload.item_type != item_type:
                continue
            if int(payload.source_id) != int(source_id):
                continue
            if obligation_key is not None and payload.open_metadata.get("obligation_key") != obligation_key:
                continue
            page.table.selectRow(row)
            return payload
        self.fail(f"Řádek {item_type}/{source_id} v Agendě nenalezen")

    def test_accident_attention_appears_in_agenda(self) -> None:
        accident = self._create_accident()
        items = _kniha_items(agenda_service.get_items(today=date(2026, 9, 8)))
        item = self._find_agenda(
            items,
            item_type=ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE,
            source_id=accident.id,
        )
        self.assertIn("Aktualizace záznamu", item.title)
        self.assertEqual(item.due_date, date(2026, 9, 4))
        self.assertEqual(item.priority, PRIORITY_CRITICAL)
        self.assertEqual(item.source, SOURCE_LABEL_KNIHA_URAZU)
        self.assertEqual(item.status, TASK_STATUS_ACTIVE)
        self.assertIsNotNone(item.attention)

        page = AgendaPage()
        page.refresh()
        payload = self._select_agenda_row(
            page,
            item_type=ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE,
            source_id=accident.id,
        )
        self.assertEqual(
            page.table.item(page.table.currentRow(), COL_TITLE).background().color(),
            QColor(PRIORITY_COLORS[PRIORITY_CRITICAL]),
        )
        self.assertEqual(payload.due_date, date(2026, 9, 4))

    def test_signatures_zp_exam_regression_in_agenda(self) -> None:
        accident = self._create_accident()
        self._mark_portal_sent(accident, date(2026, 9, 7))
        exam_accident = self._required_exam(
            self._create_accident(jmeno_prijmeni="Petr Zkouška", dpn_do=date(2026, 4, 20)),
            return_date=date.today() - timedelta(days=10),
        )
        signed = self._create_accident(jmeno_prijmeni="Eva Podpis")
        self._mark_portal_sent(signed, date(2026, 9, 7))
        self._set_signed(signed, date(2026, 9, 9))

        items = agenda_service.get_items(today=date(2026, 9, 8))
        sign_item = self._find_agenda(
            items,
            item_type=ITEM_TYPE_ACCIDENT_SIGNED_RECORD,
            source_id=accident.id,
        )
        self.assertEqual(sign_item.due_date, date(2026, 9, 9))
        self.assertEqual(sign_item.priority, PRIORITY_CRITICAL)
        self.assertEqual(
            sign_item.open_metadata.get("focus_tab"),
            TAB_PO_UKONCENI_DPN,
        )

        zp_item = self._find_agenda(
            items,
            item_type=ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION,
            source_id=signed.id,
            obligation_key=OBLIGATION_AKTUALIZACE_ZP,
        )
        self.assertEqual(zp_item.title, DPN_DISTRIBUTION_TITLES[OBLIGATION_AKTUALIZACE_ZP])
        self.assertEqual(zp_item.due_date, date(2026, 9, 11))
        self.assertEqual(
            zp_item.open_metadata.get("obligation_key"),
            OBLIGATION_AKTUALIZACE_ZP,
        )

        exam_item = self._find_agenda(
            items,
            item_type=ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
            source_id=exam_accident.id,
        )
        self.assertIn("Mimořádná pracovnělékařská prohlídka", exam_item.title)
        self.assertEqual(exam_item.open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)
        self.assertEqual(exam_item.priority, PRIORITY_CRITICAL)

    def test_done_source_hides_agenda_row_without_creating_task(self) -> None:
        accident = self._create_accident()
        before_tasks = {task.id for task in task_service.get_all_tasks()}
        items = _kniha_items(agenda_service.get_items(today=date(2026, 9, 8)))
        self.assertTrue(
            any(i.item_type == ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE for i in items)
        )
        after_tasks = {task.id for task in task_service.get_all_tasks()}
        self.assertEqual(before_tasks, after_tasks)

        self._mark_portal_sent(accident, date(2026, 9, 7))
        hidden = _kniha_items(agenda_service.get_items(today=date(2026, 9, 8)))
        self.assertFalse(
            any(
                i.item_type == ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE
                and int(i.source_id) == accident.id
                for i in hidden
            )
        )
        self.assertFalse(
            any("aktualizovaný záznam" in (task.title or "").casefold() for task in task_service.get_all_tasks())
        )

        self._set_signed(accident, date(2026, 9, 9))
        zp = self._find_agenda(
            agenda_service.get_items(today=date(2026, 9, 10)),
            item_type=ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION,
            source_id=accident.id,
            obligation_key=OBLIGATION_AKTUALIZACE_ZP,
        )
        self.assertEqual(zp.due_date, date(2026, 9, 11))
        self._mark_row_done(accident, OBLIGATION_AKTUALIZACE_ZP, date(2026, 9, 10))
        remaining = agenda_service.get_items(today=date(2026, 9, 10))
        self.assertFalse(
            any(
                i.item_type == ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION
                and i.open_metadata.get("obligation_key") == OBLIGATION_AKTUALIZACE_ZP
                and int(i.source_id) == accident.id
                for i in remaining
            )
        )

    def test_existing_task_unchanged_and_not_duplicated(self) -> None:
        task = task_service.create_task(
            title="Úkol zůstane úkolem",
            due_date=date(2026, 9, 20),
            priority=PRIORITY_NORMAL,
        )
        self._create_accident()
        items = [
            item
            for item in agenda_service.get_items(today=date(2026, 9, 8))
            if item.title == "Úkol zůstane úkolem"
        ]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].item_type, ITEM_TYPE_TASK)
        self.assertEqual(items[0].source_id, task.id)
        self.assertIsNone(items[0].attention)

    def test_opening_uses_attention_navigation(self) -> None:
        accident = self._create_accident()
        self._mark_portal_sent(accident, date(2026, 9, 7))
        signed = self._create_accident(jmeno_prijmeni="Distribuce")
        self._mark_portal_sent(signed, date(2026, 9, 7))
        self._set_signed(signed, date(2026, 9, 9))
        exam_accident = self._required_exam(
            self._create_accident(jmeno_prijmeni="Prohlídka"),
            return_date=date.today() - timedelta(days=10),
        )

        opened: list = []
        page = AgendaPage(open_attention_callback=opened.append)
        page.refresh()

        self._select_agenda_row(
            page,
            item_type=ITEM_TYPE_ACCIDENT_SIGNED_RECORD,
            source_id=accident.id,
        )
        page.edit_selected()
        self.assertEqual(opened[-1].item_type, ITEM_TYPE_ACCIDENT_SIGNED_RECORD)
        self.assertEqual(opened[-1].open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)

        window = MagicMock()
        MainWindow._open_attention_item(window, opened[-1])
        window._open_accident_by_id.assert_called_once_with(
            accident.id,
            focus_tab=TAB_PO_UKONCENI_DPN,
        )

        opened.clear()
        self._select_agenda_row(
            page,
            item_type=ITEM_TYPE_ACCIDENT_UPDATED_RECORD_DISTRIBUTION,
            source_id=signed.id,
            obligation_key=OBLIGATION_AKTUALIZACE_ZP,
        )
        page.edit_selected()
        self.assertEqual(
            opened[-1].open_metadata.get("obligation_key"),
            OBLIGATION_AKTUALIZACE_ZP,
        )
        window = MagicMock()
        MainWindow._open_attention_item(window, opened[-1])
        window._open_accident_reporting_by_id.assert_called_once_with(
            signed.id,
            focus_obligation_key=OBLIGATION_AKTUALIZACE_ZP,
        )

        opened.clear()
        self._select_agenda_row(
            page,
            item_type=ITEM_TYPE_ACCIDENT_EXTRAORDINARY_EXAM,
            source_id=exam_accident.id,
        )
        page.edit_selected()
        self.assertEqual(opened[-1].open_metadata.get("focus_tab"), TAB_PO_UKONCENI_DPN)

    def test_due_then_priority_in_agenda_and_upcoming(self) -> None:
        critical_late = task_service.create_task(
            title="Kritická později",
            due_date=date(2026, 9, 15),
            priority=PRIORITY_CRITICAL,
        )
        critical_overdue = task_service.create_task(
            title="Kritická po termínu",
            due_date=date(2026, 9, 5),
            priority=PRIORITY_CRITICAL,
        )
        high_overdue = task_service.create_task(
            title="Vysoká po termínu",
            due_date=date(2026, 9, 1),
            priority=PRIORITY_HIGH,
        )
        normal = task_service.create_task(
            title="Normální termín",
            due_date=date(2026, 9, 8),
            priority=PRIORITY_NORMAL,
        )
        audit = audit_service.create_audit(
            workplace_name="Bez priority dříve",
            started_at=date(2026, 8, 20),
        )
        wanted_ids = {
            critical_late.id,
            critical_overdue.id,
            high_overdue.id,
            normal.id,
            audit.id,
        }
        expected = [
            audit.id,
            high_overdue.id,
            critical_overdue.id,
            normal.id,
            critical_late.id,
        ]

        agenda_ids = [
            item.source_id
            for item in agenda_service.get_items(today=date(2026, 9, 8))
            if item.source_id in wanted_ids and item.item_type in {ITEM_TYPE_TASK, "audit"}
        ]
        self.assertEqual(agenda_ids, expected)

        page = AgendaPage()
        page.refresh()
        page_ids = []
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id in wanted_ids:
                page_ids.append(payload.source_id)
        self.assertEqual(page_ids, expected)

        widget = UpcomingTasksWidget()
        widget.refresh()
        upcoming_ids = []
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, UPCOMING_COL_TYPE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.entity_id in wanted_ids:
                upcoming_ids.append(payload.entity_id)
        self.assertEqual(upcoming_ids, expected)
        self.assertEqual(
            widget.table.horizontalHeader().sortIndicatorSection(),
            1,
        )

        page.table.sortItems(COL_TITLE, Qt.SortOrder.AscendingOrder)
        page.refresh()
        restored = []
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if payload is not None and payload.source_id in wanted_ids:
                restored.append(payload.source_id)
        self.assertEqual(restored, expected)

    def test_attention_stays_in_active_filter(self) -> None:
        accident = self._create_accident()
        items = agenda_service.filter_items(
            agenda_service.get_items(today=date(2026, 9, 8)),
            type_filters={ITEM_TYPE_TASK},
            status_mode=STATUS_MODE_ACTIVE,
        )
        self.assertTrue(
            any(
                i.item_type == ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE
                and int(i.source_id) == accident.id
                for i in items
            )
        )


if __name__ == "__main__":
    unittest.main()
