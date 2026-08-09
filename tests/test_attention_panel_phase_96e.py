"""Fáze 96e/ Dashboard-1 – panel Nadcházející události a úkoly."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QTableWidget

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import (
        ITEM_TYPE_AUDIT,
        ITEM_TYPE_BOZP_INSPECTION,
        ITEM_TYPE_MEETING,
        ITEM_TYPE_PERIODIC,
        ITEM_TYPE_TASK,
        SOURCE_LABEL_AUDIT,
        SOURCE_LABEL_INSPECTION,
    )
    from core.dashboard.attention_service import build_sort_key, get_attention_items
    from core.dashboard.widget_upcoming_tasks import UpcomingTasksWidget
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service


class AttentionPanelPhase96eTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status not in ("Ukončeno", "Zrušeno"):
                task_service.cancel_task(task.id)
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        from moduly.schuzky.constants import STATUS_CANCELLED, STATUS_PLANNED
        from moduly.schuzky.sluzby.meeting_service import meeting_service

        for meeting in list(meeting_service.get_all()):
            if (meeting.status or "") != STATUS_PLANNED:
                continue
            meeting_service.update_meeting(
                meeting.id,
                title=meeting.title or "",
                starts_at=meeting.starts_at,
                ends_at=meeting.ends_at,
                location=meeting.location or "",
                organizer_person_id=meeting.organizer_person_id,
                participant_ids=meeting_service.parse_participant_ids(meeting),
                agenda=meeting.agenda or "",
                status=STATUS_CANCELLED,
            )

    def test_panel_title_requires_attention(self) -> None:
        widget = UpcomingTasksWidget()
        self.assertEqual(widget.title_label.text(), "Nadcházející události a úkoly")

    def test_empty_state_message(self) -> None:
        widget = UpcomingTasksWidget()
        labels = [
            label.text()
            for label in widget.findChildren(QLabel)
            if "nadcházející události ani úkoly" in label.text()
        ]
        self.assertTrue(labels)
        self.assertIn(
            "Nejsou evidovány žádné nadcházející události ani úkoly.",
            labels,
        )
        self.assertEqual(widget.table.rowCount(), 0)
        self.assertTrue(widget.empty_label.isVisibleTo(widget) or not widget.empty_label.isHidden())

    def test_active_task_is_shown(self) -> None:
        due = date.today() + timedelta(days=3)
        task = task_service.create_task(
            title="Aktivní úkol 96e",
            due_date=due,
            priority="Vysoká",
        )

        items = get_attention_items()
        match = next(item for item in items if item.entity_id == task.id)
        self.assertEqual(match.item_type, ITEM_TYPE_TASK)
        self.assertEqual(match.title, "Aktivní úkol 96e")
        self.assertEqual(match.due_date, due)
        self.assertEqual(match.priority, "Vysoká")
        self.assertEqual(match.type_label, "Úkol")

        widget = UpcomingTasksWidget()
        self.assertGreater(widget.table.rowCount(), 0)
        titles = [
            widget.table.item(row, 2).text()
            for row in range(widget.table.rowCount())
        ]
        self.assertIn("Aktivní úkol 96e", titles)

    def test_audit_with_date_is_shown(self) -> None:
        audit_date = date.today() + timedelta(days=10)
        audit = audit_service.create_audit(
            workplace_name="Testovací pracoviště",
            started_at=audit_date,
        )

        items = get_attention_items()
        match = next(item for item in items if item.entity_id == audit.id)
        self.assertEqual(match.item_type, ITEM_TYPE_AUDIT)
        self.assertEqual(match.title, "Audit – Testovací pracoviště")
        self.assertEqual(match.due_date, audit_date)
        self.assertEqual(match.source_label, SOURCE_LABEL_AUDIT)
        self.assertEqual(match.type_label, "Audit")

    def test_completed_audit_with_start_date_is_hidden(self) -> None:
        audit = audit_service.create_audit(
            workplace_name="Dokončený provoz",
            audit_date=date.today() + timedelta(days=2),
            started_at=date.today() + timedelta(days=1),
            finished_at=date.today(),
        )

        items = get_attention_items()
        self.assertFalse(any(item.entity_id == audit.id for item in items))

    def test_audit_without_date_is_hidden(self) -> None:
        audit = audit_service.create_audit(workplace_name="Bez data")

        items = get_attention_items()
        self.assertFalse(any(item.entity_id == audit.id for item in items))

    def test_inspection_with_date_is_shown(self) -> None:
        inspection_date = date.today() + timedelta(days=20)
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Provoz A",
            started_at=inspection_date,
        )

        items = get_attention_items()
        match = next(item for item in items if item.entity_id == inspection.id)
        self.assertEqual(match.item_type, ITEM_TYPE_BOZP_INSPECTION)
        self.assertEqual(match.title, "Prověrka BOZP – Provoz A")
        self.assertEqual(match.due_date, inspection_date)
        self.assertEqual(match.source_label, SOURCE_LABEL_INSPECTION)
        self.assertEqual(match.type_label, "Prověrka")

    def test_completed_inspection_with_start_date_is_hidden(self) -> None:
        inspection = bozp_inspection_service.create_inspection(
            workplace_name="Dokončená prověrka",
            inspection_date=date.today() + timedelta(days=5),
            started_at=date.today() - timedelta(days=1),
            finished_at=date.today(),
        )

        items = get_attention_items()
        self.assertFalse(any(item.entity_id == inspection.id for item in items))

    def test_items_sorted_by_due_date(self) -> None:
        today = date.today()
        future = task_service.create_task(
            title="Budoucí úkol",
            due_date=today + timedelta(days=5),
            priority="Nízká",
        )
        overdue = task_service.create_task(
            title="Po termínu",
            due_date=today - timedelta(days=2),
            priority="Normální",
        )
        due_today = task_service.create_task(
            title="Dnes",
            due_date=today,
            priority="Normální",
        )
        audit = audit_service.create_audit(
            workplace_name="Audit brzy",
            started_at=today + timedelta(days=1),
        )
        no_date = task_service.create_task(title="Bez termínu", priority="Kritická")

        items = get_attention_items(today=today)
        ids = [item.entity_id for item in items]

        self.assertEqual(ids[:4], [overdue.id, due_today.id, audit.id, future.id])
        self.assertEqual(ids[-1], no_date.id)

    def test_same_date_title_order_when_priorities_differ(self) -> None:
        """Při stejném termínu řadí služba podle typu/názvu/id – ne podle priority."""
        today = date.today()
        due = today + timedelta(days=4)
        low = task_service.create_task(
            title="Aaa nízká",
            due_date=due,
            priority="Nízká",
        )
        high = task_service.create_task(
            title="Zzz kritická",
            due_date=due,
            priority="Kritická",
        )

        items = [
            item
            for item in get_attention_items(today=today)
            if item.entity_id in (low.id, high.id)
        ]
        self.assertEqual([item.entity_id for item in items], [low.id, high.id])

    def test_sort_key_helpers(self) -> None:
        today = date.today()
        overdue = build_sort_key(today - timedelta(days=1), title="a", today=today)
        current = build_sort_key(today, title="a", today=today)
        future = build_sort_key(today + timedelta(days=1), title="a", today=today)
        missing = build_sort_key(None, title="a", today=today)
        self.assertLess(overdue, current)
        self.assertLess(current, future)
        self.assertLess(future, missing)

    def test_double_click_opens_correct_type(self) -> None:
        opened: list = []

        def on_open(item) -> None:
            opened.append((item.item_type, item.entity_id))

        task = task_service.create_task(
            title="Otevři mě",
            due_date=date.today() + timedelta(days=1),
        )
        widget = UpcomingTasksWidget(open_attention_callback=on_open)
        self.assertGreater(widget.table.rowCount(), 0)

        widget.table.selectRow(0)
        item = widget.table.item(0, 0)
        self.assertIsNotNone(item)
        widget._open_selected()

        self.assertEqual(opened, [(ITEM_TYPE_TASK, task.id)])

        opened.clear()
        audit = audit_service.create_audit(
            workplace_name="Otevři audit",
            started_at=date.today() + timedelta(days=2),
        )
        widget.refresh()
        for row in range(widget.table.rowCount()):
            payload = widget.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if payload.item_type == ITEM_TYPE_AUDIT and payload.entity_id == audit.id:
                widget.table.selectRow(row)
                widget._open_selected()
                break
        self.assertEqual(opened, [(ITEM_TYPE_AUDIT, audit.id)])

    def test_load_uses_light_list_queries_only(self) -> None:
        """Načtení nesmí sahat do těžkých detailních / exportních služeb spisů."""
        task_service.create_task(title="Lehký úkol", due_date=date.today())
        audit_service.create_audit(
            workplace_name="Lehký audit",
            audit_date=date.today() + timedelta(days=1),
        )
        bozp_inspection_service.create_inspection(
            workplace_name="Lehká prověrka",
            inspection_date=date.today() + timedelta(days=2),
        )

        forbidden = [
            "moduly.audity.sluzby.audit_export_context_service",
            "moduly.proverky.sluzby.bozp_inspection_export_context_service",
            "moduly.audity.sluzby.audit_annual_export_context_service",
        ]
        with patch.dict("sys.modules", {name: MagicMock() for name in forbidden}):
            items = get_attention_items()

        self.assertGreaterEqual(len(items), 1)
        types = {item.item_type for item in items}
        self.assertIn(ITEM_TYPE_TASK, types)
        self.assertTrue(
            types.issubset(
                {
                    ITEM_TYPE_TASK,
                    ITEM_TYPE_AUDIT,
                    ITEM_TYPE_BOZP_INSPECTION,
                    ITEM_TYPE_MEETING,
                    ITEM_TYPE_PERIODIC,
                }
            )
        )

    def test_widget_has_type_column(self) -> None:
        task_service.create_task(title="Typový úkol", due_date=date.today())
        widget = UpcomingTasksWidget()
        table = widget.findChild(QTableWidget)
        self.assertIsNotNone(table)
        headers = [
            table.horizontalHeaderItem(i).text()
            for i in range(table.columnCount())
        ]
        self.assertIn("Typ", headers)
        self.assertEqual(table.item(0, 0).text(), "Úkol")

    def test_widget_defaults_to_due_date_sort(self) -> None:
        today = date.today()
        future_task = task_service.create_task(
            title="Pozdější úkol",
            due_date=today + timedelta(days=10),
        )
        audit_service.create_audit(
            workplace_name="Brzký audit",
            started_at=today + timedelta(days=1),
        )
        task_service.create_task(
            title="Dnešní úkol",
            due_date=today,
        )

        widget = UpcomingTasksWidget()
        header = widget.table.horizontalHeader()
        self.assertEqual(header.sortIndicatorSection(), 1)  # Termín
        self.assertEqual(header.sortIndicatorOrder(), Qt.SortOrder.AscendingOrder)

        due_texts = [
            widget.table.item(row, 1).text()
            for row in range(widget.table.rowCount())
        ]
        self.assertEqual(
            due_texts[:3],
            [
                f"{today.day}. {today.month}. {today.year}",
                f"{(today + timedelta(days=1)).day}. {(today + timedelta(days=1)).month}. {(today + timedelta(days=1)).year}",
                f"{(today + timedelta(days=10)).day}. {(today + timedelta(days=10)).month}. {(today + timedelta(days=10)).year}",
            ],
        )
        # Pořadí není seskupené podle typu (Úkol by jinak byl nahoře před Auditem).
        types = [widget.table.item(row, 0).text() for row in range(3)]
        self.assertEqual(types[0], "Úkol")
        self.assertEqual(types[1], "Audit")
        self.assertEqual(types[2], "Úkol")
        self.assertEqual(
            widget.table.item(2, 0).data(Qt.ItemDataRole.UserRole).entity_id,
            future_task.id,
        )


if __name__ == "__main__":
    unittest.main()
