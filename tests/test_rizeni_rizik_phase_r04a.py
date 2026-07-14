"""Fáze R04a – identifikace bez názvu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _migrate_hazard_identification_numbers,
        _remove_hazard_identification_title_column,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.repository.hazard_identification_repository import (
        HazardIdentificationRepository,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )


class HazardIdentificationNumberPhaseR04aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz A",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Kolejiště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        self.operation_id = operation.id
        self.workplace_id = self.workplace.id

    def test_table_has_identification_number_without_title(self) -> None:
        columns = _table_columns("hazard_identifications")
        self.assertIn("identification_number", columns)
        self.assertNotIn("title", columns)

    def test_auto_assign_identification_number(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation_id,
            workplace_id=self.workplace_id,
        )
        self.assertRegex(created.identification_number, r"^\d{4}-\d{4}$")
        self.assertEqual(created.identification_number, f"{datetime.now().year}-0001")

    def test_identification_number_uniqueness(self) -> None:
        first = hazard_identification_service.create_identification(
            operation_id=self.operation_id,
            workplace_id=self.workplace_id,
        )
        second = hazard_identification_service.create_identification(
            operation_id=self.operation_id,
            workplace_id=self.workplace_id,
        )
        self.assertNotEqual(first.identification_number, second.identification_number)
        self.assertEqual(second.identification_number, f"{datetime.now().year}-0002")

    def test_migration_assigns_numbers_and_removes_title(self) -> None:
        from core.database.session import get_session

        with get_session() as session:
            session.execute(text("DROP TABLE IF EXISTS hazard_identifications"))
            session.execute(
                text(
                    """
                    CREATE TABLE hazard_identifications (
                        id INTEGER PRIMARY KEY,
                        title VARCHAR(250) NOT NULL,
                        operation_id INTEGER,
                        operation_name VARCHAR(150) DEFAULT '',
                        workplace_id INTEGER,
                        workplace_name VARCHAR(150) DEFAULT '',
                        workplace_part_id INTEGER,
                        workplace_part_name VARCHAR(150) DEFAULT '',
                        responsible_person_id INTEGER,
                        responsible_person_name VARCHAR(150) DEFAULT '',
                        started_at DATE,
                        status VARCHAR(30) NOT NULL DEFAULT 'draft',
                        note TEXT DEFAULT '',
                        active BOOLEAN DEFAULT 1,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            session.execute(
                text(
                    """
                    INSERT INTO hazard_identifications (
                        title, operation_id, workplace_id, created_at, status, active
                    ) VALUES
                        ('Starší identifikace', :operation_id, :workplace_id, :created_at, 'draft', 1),
                        ('Novější identifikace', :operation_id, :workplace_id, :created_at, 'draft', 1)
                    """
                ),
                {
                    "operation_id": self.operation_id,
                    "workplace_id": self.workplace_id,
                    "created_at": datetime(2026, 1, 15),
                },
            )
            session.commit()

        from core.database.database_initializer import _add_column

        _add_column(
            "hazard_identifications",
            "identification_number VARCHAR(20) DEFAULT '' NOT NULL",
        )
        _migrate_hazard_identification_numbers()
        _remove_hazard_identification_title_column()

        columns = _table_columns("hazard_identifications")
        self.assertIn("identification_number", columns)
        self.assertNotIn("title", columns)

        with get_session() as session:
            numbers = list(
                session.scalars(
                    text(
                        "SELECT identification_number FROM hazard_identifications ORDER BY id"
                    )
                )
            )
        self.assertEqual(numbers, ["2026-0001", "2026-0002"])

    def test_basics_widget_shows_read_only_identification_number(self) -> None:
        from moduly.rizeni_rizik.ui.hazard_identification_basics_widget import (
            HazardIdentificationBasicsWidget,
        )

        created = hazard_identification_service.create_identification(
            operation_id=self.operation_id,
            workplace_id=self.workplace_id,
        )
        widget = HazardIdentificationBasicsWidget()
        widget.load_identification(created)
        self.assertEqual(widget.identification_number_label.text(), created.identification_number)

    def test_repository_lookup_by_identification_number(self) -> None:
        created = hazard_identification_service.create_identification(
            operation_id=self.operation_id,
            workplace_id=self.workplace_id,
        )
        repository = HazardIdentificationRepository()
        loaded = repository.get_by_identification_number(created.identification_number)
        assert loaded is not None
        self.assertEqual(loaded.id, created.id)


if __name__ == "__main__":
    unittest.main()
