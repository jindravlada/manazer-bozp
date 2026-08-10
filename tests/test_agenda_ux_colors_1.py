"""AGENDA-UX-COLORS-1: zjemnění stavových barev Agendy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.agenda.constants import (
        COL_TITLE,
        DEFAULT_PRIORITY_COLOR,
        PRIORITY_COLORS,
        PRIORITY_CRITICAL,
        PRIORITY_HIGH,
        PRIORITY_LOW,
        PRIORITY_NORMAL,
        STATUS_MODE_ALL,
    )
    from moduly.agenda.ui.agenda_page import AgendaPage
    from moduly.kontroly.ui.control_summary_panel import ROW_LABEL_STYLES
    from moduly.schuzky.constants import STATUS_PLANNED
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.ukoly.sluzby.task_service import task_service


# Pastelová paleta Kontrol (pozadí / okraj stavových karet).
_KONTROLY_RED = ROW_LABEL_STYLES["Neprovedeno"][1]  # #ffcdd2
_KONTROLY_ORANGE = ROW_LABEL_STYLES["Se závadou"][1]  # #ffe0b2
_KONTROLY_GREEN = ROW_LABEL_STYLES["Provedeno"][1]  # #c8e6c9


class AgendaUxColors1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_palette_matches_kontroly_pastels(self) -> None:
        self.assertEqual(PRIORITY_COLORS[PRIORITY_CRITICAL], _KONTROLY_RED)
        self.assertEqual(PRIORITY_COLORS[PRIORITY_HIGH], _KONTROLY_ORANGE)
        self.assertEqual(PRIORITY_COLORS[PRIORITY_LOW], _KONTROLY_GREEN)
        self.assertEqual(PRIORITY_COLORS[PRIORITY_NORMAL], "#fff9c4")
        self.assertEqual(DEFAULT_PRIORITY_COLOR, "#eeeeee")

    def test_priority_colors_are_distinct(self) -> None:
        colors = [
            PRIORITY_COLORS[PRIORITY_CRITICAL],
            PRIORITY_COLORS[PRIORITY_HIGH],
            PRIORITY_COLORS[PRIORITY_NORMAL],
            PRIORITY_COLORS[PRIORITY_LOW],
            DEFAULT_PRIORITY_COLOR,
        ]
        self.assertEqual(len(colors), len(set(colors)))

    def test_rows_use_pastel_priority_colors(self) -> None:
        critical = task_service.create_task(
            title="Kritická pastel",
            due_date=date.today() + timedelta(days=3),
            priority=PRIORITY_CRITICAL,
        )
        high = meeting_service.create_meeting(
            title="Vysoká pastel",
            starts_at=datetime.now() + timedelta(days=4),
            status=STATUS_PLANNED,
            priority=PRIORITY_HIGH,
        )
        normal = task_service.create_task(
            title="Normální pastel",
            due_date=date.today() + timedelta(days=5),
            priority=PRIORITY_NORMAL,
        )
        low = task_service.create_task(
            title="Nízká pastel",
            due_date=date.today() + timedelta(days=6),
            priority=PRIORITY_LOW,
        )

        page = AgendaPage()
        page.status_filter.setCurrentText(STATUS_MODE_ALL)
        page.refresh()

        by_key: dict[tuple[str, int], QColor] = {}
        for row in range(page.table.rowCount()):
            payload = page.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            by_key[(payload.item_type, payload.source_id)] = (
                page.table.item(row, COL_TITLE).background().color()
            )
            # Celý řádek stejná barva.
            for col in range(page.table.columnCount()):
                self.assertEqual(
                    page.table.item(row, col).background().color(),
                    by_key[(payload.item_type, payload.source_id)],
                )

        self.assertEqual(
            by_key[("task", critical.id)],
            QColor(PRIORITY_COLORS[PRIORITY_CRITICAL]),
        )
        self.assertEqual(
            by_key[("meeting", high.id)],
            QColor(PRIORITY_COLORS[PRIORITY_HIGH]),
        )
        self.assertEqual(
            by_key[("task", normal.id)],
            QColor(PRIORITY_COLORS[PRIORITY_NORMAL]),
        )
        self.assertEqual(
            by_key[("task", low.id)],
            QColor(PRIORITY_COLORS[PRIORITY_LOW]),
        )

        # Odstíny zůstávají pastelové (vysoký kanál jasu).
        for color in (
            by_key[("task", critical.id)],
            by_key[("meeting", high.id)],
            by_key[("task", normal.id)],
            by_key[("task", low.id)],
        ):
            self.assertGreaterEqual(min(color.red(), color.green(), color.blue()), 170)


if __name__ == "__main__":
    unittest.main()
