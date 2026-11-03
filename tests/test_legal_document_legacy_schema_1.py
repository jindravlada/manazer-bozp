"""Doplnění schématu legal_documents ze starší databáze bez vymyšlených údajů."""

from __future__ import annotations

import importlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class LegalDocumentLegacySchemaTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="legal-legacy-schema-"))
        self._home_patch = patch.object(Path, "home", return_value=self.home)
        self._home_patch.start()
        import core.services.storage_service as storage_module
        import core.database.session as session_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.dispose_database_engine()
        self.session = session_module
        self.database = storage_module.storage_service.database_path
        self.database.parent.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self.session.dispose_database_engine()
        self._home_patch.stop()
        shutil.rmtree(self.home, ignore_errors=True)

    def _write_legacy(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.executescript(
                """
                CREATE TABLE legal_documents (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(250) DEFAULT '',
                    document_type VARCHAR(50) DEFAULT '',
                    local_file_path TEXT DEFAULT ''
                );
                CREATE TABLE legal_requirements (
                    id INTEGER PRIMARY KEY,
                    regulation_name VARCHAR(250) DEFAULT '',
                    title VARCHAR(250) DEFAULT '',
                    process_code VARCHAR(50) DEFAULT '',
                    active BOOLEAN DEFAULT 1
                );
                """
            )
            connection.execute(
                "INSERT INTO legal_documents(id, title, document_type, local_file_path) "
                "VALUES (3, ?, ?, ?)",
                ("NV 361/2007", "regulation", "/home/user/docs/predpis.pdf"),
            )
            connection.execute(
                "INSERT INTO legal_requirements(id, regulation_name, title, process_code) "
                "VALUES (5, ?, ?, ?)",
                ("ZV 262/2006", "BOZP povinnost", "P01"),
            )
            connection.commit()
        finally:
            connection.close()

    def _ensure(self) -> None:
        self.session.reconfigure_database_engine(force=True)
        from core.database.database_initializer import (
            _ensure_legal_document_columns,
            _ensure_legal_requirement_columns,
        )

        _ensure_legal_document_columns()
        _ensure_legal_requirement_columns()

    def test_legacy_table_keeps_documents_and_can_be_read(self) -> None:
        self._write_legacy()
        self._ensure()
        self._ensure()

        connection = sqlite3.connect(str(self.database))
        try:
            document = connection.execute(
                "SELECT id, title, document_type, local_file_path, number, year, "
                "short_title, source_url, note, active, included_in_processes "
                "FROM legal_documents"
            ).fetchall()
            requirement = connection.execute(
                "SELECT id, title, process_code, legal_document_id FROM legal_requirements"
            ).fetchall()
            count = connection.execute(
                "SELECT COUNT(*) FROM legal_documents"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)
        self.assertEqual(
            document,
            [(
                3,
                "NV 361/2007",
                "regulation",
                "/home/user/docs/predpis.pdf",
                "",
                None,
                "",
                "",
                "",
                1,
                0,
            )],
        )
        self.assertEqual(requirement, [(5, "BOZP povinnost", "P01", None)])

        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.pravni_pozadavky.sluzby.legal_opendata_baseline_service import (
            legal_opendata_baseline_service,
        )
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        loaded = legal_document_service.get_by_id(3)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.title, "NV 361/2007")
        self.assertEqual(loaded.local_file_path, "/home/user/docs/predpis.pdf")
        self.assertEqual(loaded.number, "")
        self.assertIsNone(loaded.year)
        listed = legal_document_service.list_all()
        self.assertEqual([item.id for item in listed], [3])
        requirement_loaded = legal_requirement_service.get_by_id(5)
        self.assertIsNotNone(requirement_loaded)
        assert requirement_loaded is not None
        self.assertEqual(requirement_loaded.process_code, "P01")
        self.assertIsNone(requirement_loaded.legal_document_id)

        with patch(
            "moduly.pravni_pozadavky.sluzby.legal_opendata_baseline_service."
            "open_data_http_session",
            side_effect=AssertionError("síť se nesmí volat"),
        ):
            first = legal_opendata_baseline_service.apply_if_needed()
            second = legal_opendata_baseline_service.apply_if_needed()
        self.assertFalse(first.applied)
        self.assertFalse(second.applied)
        self.assertEqual(
            [item.id for item in legal_document_service.list_all()],
            [3],
        )

    def test_existing_number_and_link_are_kept(self) -> None:
        connection = sqlite3.connect(str(self.database))
        try:
            connection.executescript(
                """
                CREATE TABLE legal_documents (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(300) NOT NULL,
                    document_type VARCHAR(50) NOT NULL,
                    number VARCHAR(100) NOT NULL,
                    year INTEGER,
                    local_file_path VARCHAR(500) NOT NULL
                );
                CREATE TABLE legal_requirements (
                    id INTEGER PRIMARY KEY,
                    title VARCHAR(250) DEFAULT '',
                    regulation_name VARCHAR(250) DEFAULT '',
                    process_code VARCHAR(50) DEFAULT '',
                    legal_document_id INTEGER,
                    active BOOLEAN DEFAULT 1
                );
                """
            )
            connection.execute(
                "INSERT INTO legal_documents("
                "id, title, document_type, number, year, local_file_path"
                ") VALUES (1, ?, ?, ?, ?, ?)",
                ("Zákoník práce", "zakon", "262", 2006, "/docs/zp.pdf"),
            )
            connection.execute(
                "INSERT INTO legal_requirements(id, title, process_code, legal_document_id) "
                "VALUES (9, ?, ?, ?)",
                ("Pracovní doba", "P02", 1),
            )
            connection.commit()
        finally:
            connection.close()

        self._ensure()

        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
            legal_requirement_service,
        )

        document = legal_document_service.get_by_id(1)
        requirement = legal_requirement_service.get_by_id(9)
        self.assertIsNotNone(document)
        self.assertIsNotNone(requirement)
        assert document is not None and requirement is not None
        self.assertEqual(document.number, "262")
        self.assertEqual(document.year, 2006)
        self.assertEqual(document.title, "Zákoník práce")
        self.assertEqual(document.local_file_path, "/docs/zp.pdf")
        self.assertEqual(requirement.legal_document_id, 1)
        self.assertEqual(requirement.process_code, "P02")
        connection = sqlite3.connect(str(self.database))
        try:
            count = connection.execute(
                "SELECT COUNT(*) FROM legal_documents"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
