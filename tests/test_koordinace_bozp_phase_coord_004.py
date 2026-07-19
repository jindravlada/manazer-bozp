"""Fáze COORD-004 – platnost koordinace."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete, text

_TMP = Path(tempfile.mkdtemp(prefix="coord-004-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_bozp_coordinations_table,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from core.widgets.typed_table_sort import TYPED_SORT_ROLE
    from moduly.koordinace_bozp.constants import (
        COL_VALIDITY,
        VALIDITY_FILTER_EXPIRED,
        VALIDITY_FILTER_EXPIRING,
        VALIDITY_FILTER_VALID,
        VALIDITY_STATE_COLORS,
        VALIDITY_STATE_EXPIRED,
        VALIDITY_STATE_EXPIRING,
        VALIDITY_STATE_VALID,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_validity import (
        add_one_year,
        coordination_validity_label,
        coordination_validity_sort_order,
        coordination_validity_state,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage


class KoordinaceBozpPhaseCoord004TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

    def test_auto_valid_to_plus_one_year(self) -> None:
        meeting = date(2026, 7, 19)
        created = bozp_coordination_service.create_coordination(
            subject="Auto platnost",
            meeting_date=meeting,
        )
        self.assertEqual(created.valid_from, meeting)
        self.assertEqual(created.valid_to, date(2027, 7, 19))
        self.assertEqual(created.valid_to, add_one_year(meeting))

    def test_manual_valid_to_change(self) -> None:
        meeting = date(2026, 3, 1)
        created = bozp_coordination_service.create_coordination(
            subject="Ruční platnost",
            meeting_date=meeting,
            valid_to=date(2026, 6, 30),
        )
        self.assertEqual(created.valid_from, meeting)
        self.assertEqual(created.valid_to, date(2026, 6, 30))

        updated = bozp_coordination_service.update_coordination(
            created.id,
            meeting_date=meeting,
            subject=created.subject,
            status=created.status,
            note="",
            valid_from=meeting,
            valid_to=date(2026, 8, 15),
        )
        assert updated is not None
        self.assertEqual(updated.valid_to, date(2026, 8, 15))

    def test_validity_states(self) -> None:
        today = date(2026, 7, 19)
        valid_to_ok = today + timedelta(days=60)
        valid_to_expiring = today + timedelta(days=15)
        valid_to_expired = today - timedelta(days=1)

        self.assertEqual(
            coordination_validity_state(valid_to_ok, today=today),
            VALIDITY_STATE_VALID,
        )
        self.assertEqual(
            coordination_validity_label(valid_to_ok, today=today),
            "Platná",
        )

        self.assertEqual(
            coordination_validity_state(valid_to_expiring, today=today),
            VALIDITY_STATE_EXPIRING,
        )
        self.assertEqual(
            coordination_validity_label(valid_to_expiring, today=today),
            "Končí 03.08.2026",
        )

        self.assertEqual(
            coordination_validity_state(valid_to_expired, today=today),
            VALIDITY_STATE_EXPIRED,
        )
        self.assertEqual(
            coordination_validity_label(valid_to_expired, today=today),
            "Po platnosti",
        )

        # Hranice: přesně valid_to - 30 dnů je ještě Platná.
        boundary = today + timedelta(days=30)
        self.assertEqual(
            coordination_validity_state(boundary, today=today),
            VALIDITY_STATE_VALID,
        )
        self.assertEqual(
            coordination_validity_state(boundary - timedelta(days=1), today=today),
            VALIDITY_STATE_EXPIRING,
        )

    def test_filter_by_validity(self) -> None:
        today = date(2026, 7, 19)
        valid_item = bozp_coordination_service.create_coordination(
            subject="Platná",
            meeting_date=today,
            valid_to=today + timedelta(days=90),
        )
        expiring_item = bozp_coordination_service.create_coordination(
            subject="Končící",
            meeting_date=today,
            valid_to=today + timedelta(days=10),
        )
        expired_item = bozp_coordination_service.create_coordination(
            subject="Po platnosti",
            meeting_date=today - timedelta(days=400),
            valid_from=today - timedelta(days=400),
            valid_to=today - timedelta(days=5),
        )

        valid_rows = bozp_coordination_service.get_all(
            include_inactive=True,
            validity_filter=VALIDITY_FILTER_VALID,
            today=today,
        )
        expiring_rows = bozp_coordination_service.get_all(
            include_inactive=True,
            validity_filter=VALIDITY_FILTER_EXPIRING,
            today=today,
        )
        expired_rows = bozp_coordination_service.get_all(
            include_inactive=True,
            validity_filter=VALIDITY_FILTER_EXPIRED,
            today=today,
        )
        self.assertEqual([row.id for row in valid_rows], [valid_item.id])
        self.assertEqual([row.id for row in expiring_rows], [expiring_item.id])
        self.assertEqual([row.id for row in expired_rows], [expired_item.id])

    def test_sort_by_validity(self) -> None:
        today = date(2026, 7, 19)
        expired = bozp_coordination_service.create_coordination(
            subject="A expired",
            meeting_date=today - timedelta(days=400),
            valid_from=today - timedelta(days=400),
            valid_to=today - timedelta(days=1),
        )
        valid = bozp_coordination_service.create_coordination(
            subject="B valid",
            meeting_date=today,
            valid_to=today + timedelta(days=90),
        )
        expiring = bozp_coordination_service.create_coordination(
            subject="C expiring",
            meeting_date=today,
            valid_to=today + timedelta(days=10),
        )
        table = BozpCoordinationTable()
        table.load_coordinations([expired, valid, expiring], today=today)
        table.sortItems(COL_VALIDITY, Qt.SortOrder.AscendingOrder)

        labels = [table.item(row, COL_VALIDITY).text() for row in range(table.rowCount())]
        self.assertEqual(labels[0], "Platná")
        self.assertTrue(labels[1].startswith("Končí "))
        self.assertEqual(labels[2], "Po platnosti")

        orders = [
            table.item(row, COL_VALIDITY).data(TYPED_SORT_ROLE).payload[0]
            for row in range(table.rowCount())
        ]
        self.assertEqual(
            orders,
            [
                coordination_validity_sort_order(VALIDITY_STATE_VALID),
                coordination_validity_sort_order(VALIDITY_STATE_EXPIRING),
                coordination_validity_sort_order(VALIDITY_STATE_EXPIRED),
            ],
        )

        color = table.item(0, COL_VALIDITY).foreground().color()
        self.assertEqual(color, QColor(VALIDITY_STATE_COLORS[VALIDITY_STATE_VALID]))

    def test_page_validity_filter_and_dialog_fields(self) -> None:
        today = date(2026, 7, 19)
        bozp_coordination_service.create_coordination(
            subject="Platná UI",
            meeting_date=today,
            valid_to=today + timedelta(days=120),
        )
        bozp_coordination_service.create_coordination(
            subject="Končící UI",
            meeting_date=today,
            valid_to=today + timedelta(days=5),
        )
        page = KoordinaceBozpPage()
        page.validity_filter.setCurrentIndex(
            page.validity_filter.findData(VALIDITY_FILTER_EXPIRING)
        )
        # refresh is connected; force with known today via service filter check
        rows = bozp_coordination_service.get_all(
            include_inactive=True,
            validity_filter=VALIDITY_FILTER_EXPIRING,
            today=today,
        )
        page.table.load_coordinations(rows, today=today)
        self.assertEqual(page.table.rowCount(), 1)
        self.assertTrue(page.table.item(0, COL_VALIDITY).text().startswith("Končí "))

        dialog = BozpCoordinationDialog(None)
        data = dialog.get_data()
        self.assertEqual(data["valid_from"], data["meeting_date"])
        self.assertEqual(data["valid_to"], add_one_year(data["meeting_date"]))

    def test_migration_backfills_existing_rows(self) -> None:
        meeting = date(2025, 1, 10)
        with get_session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO bozp_coordinations (
                        coordination_number, meeting_date, place, subject,
                        status, note, active, created_at, updated_at
                    ) VALUES (
                        '2025-0099', :meeting, '', 'Legacy',
                        'draft', '', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"meeting": meeting.isoformat()},
            )
            session.commit()

        with get_session() as session:
            session.execute(
                text("UPDATE bozp_coordinations SET valid_from = NULL, valid_to = NULL")
            )
            session.commit()

        _ensure_bozp_coordinations_table()
        columns = _table_columns("bozp_coordinations")
        self.assertIn("valid_from", columns)
        self.assertIn("valid_to", columns)

        with get_session() as session:
            row = session.execute(
                text(
                    """
                    SELECT valid_from, valid_to FROM bozp_coordinations
                    WHERE coordination_number = '2025-0099'
                    """
                )
            ).mappings().one()
        self.assertEqual(str(row["valid_from"])[:10], "2025-01-10")
        self.assertEqual(str(row["valid_to"])[:10], "2026-01-10")


if __name__ == "__main__":
    unittest.main()
