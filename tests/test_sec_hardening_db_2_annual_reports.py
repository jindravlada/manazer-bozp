"""SEC-HARDENING-DB-2: atomická migrace unique ročních zpráv auditů."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="sec-hardening-db-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

from core.database import database_initializer as initializer  # noqa: E402
from core.database.database_initializer import (  # noqa: E402
    _audit_annual_reports_has_year_only_unique,
    _ensure_audit_annual_report_table,
    _migrate_audit_annual_reports_year_program_unique,
)
from core.database.session import (  # noqa: E402
    dispose_database_engine,
    reconfigure_database_engine,
)
from core.services.storage_service import storage_service  # noqa: E402

LEGACY_CREATE_SQL = """
CREATE TABLE audit_annual_reports (
    id INTEGER NOT NULL PRIMARY KEY,
    year INTEGER NOT NULL,
    audit_program_id INTEGER,
    silne_stranky TEXT DEFAULT '' NOT NULL,
    top_priority TEXT DEFAULT '' NOT NULL,
    doporuceni_specialisty TEXT DEFAULT '' NOT NULL,
    zpracoval VARCHAR(150) DEFAULT '' NOT NULL,
    zpracoval_worker_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    CONSTRAINT uq_audit_annual_reports_year UNIQUE (year)
)
"""

CANARY_ROWS = (
    (11, 2024, 101, "CANARY-2024", "prio-24", "dopor-24", "Jan", None, "2024-01-01 00:00:00", "2024-01-02 00:00:00"),
    (12, 2025, 102, "CANARY-2025", "prio-25", "dopor-25", "Eva", 7, "2025-01-01 00:00:00", "2025-01-02 00:00:00"),
)


def _db_path() -> Path:
    return storage_service.database_path


def _connect() -> sqlite3.Connection:
    dispose_database_engine()
    return sqlite3.connect(str(_db_path().resolve()))


def _table_sql(table: str) -> str:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        return str(row[0] or "") if row else ""
    finally:
        conn.close()
        reconfigure_database_engine(force=True)


def _table_names() -> set[str]:
    conn = _connect()
    try:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()
        reconfigure_database_engine(force=True)


def _report_rows() -> list[tuple]:
    conn = _connect()
    try:
        return list(
            conn.execute(
                "SELECT id, year, audit_program_id, silne_stranky, top_priority, "
                "doporuceni_specialisty, zpracoval, zpracoval_worker_id "
                "FROM audit_annual_reports ORDER BY id"
            ).fetchall()
        )
    finally:
        conn.close()
        reconfigure_database_engine(force=True)


def _install_legacy(*, rows: tuple = CANARY_ROWS, extra_sql: str = "") -> None:
    conn = _connect()
    try:
        conn.execute("DROP TABLE IF EXISTS audit_annual_reports")
        conn.execute("DROP TABLE IF EXISTS audit_annual_reports_new")
        conn.execute(LEGACY_CREATE_SQL)
        conn.executemany(
            """
            INSERT INTO audit_annual_reports (
                id, year, audit_program_id, silne_stranky, top_priority,
                doporuceni_specialisty, zpracoval, zpracoval_worker_id,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        if extra_sql:
            conn.executescript(extra_sql)
        conn.commit()
    finally:
        conn.close()
        reconfigure_database_engine(force=True)


def _has_year_program_unique() -> bool:
    return "uq_audit_annual_reports_year_program" in _table_sql("audit_annual_reports")


def _has_year_only_unique() -> bool:
    sql = _table_sql("audit_annual_reports")
    return "uq_audit_annual_reports_year" in sql and "year_program" not in sql


class SecHardeningDb2AnnualReportsTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        initializer._AUDIT_ANNUAL_REPORTS_FAIL_AFTER = None
        reconfigure_database_engine(force=True)

    def test_a_migrates_all_rows_and_new_unique(self) -> None:
        _install_legacy()
        _ensure_audit_annual_report_table()
        self.assertTrue(_has_year_program_unique())
        self.assertFalse(_audit_annual_reports_has_year_only_unique())
        self.assertNotIn("audit_annual_reports_new", _table_names())
        self.assertEqual(
            _report_rows(),
            [
                (11, 2024, 101, "CANARY-2024", "prio-24", "dopor-24", "Jan", None),
                (12, 2025, 102, "CANARY-2025", "prio-25", "dopor-25", "Eva", 7),
            ],
        )

    def test_b_fail_before_drop_rolls_back(self) -> None:
        _install_legacy()
        initializer._AUDIT_ANNUAL_REPORTS_FAIL_AFTER = "before_drop"
        with self.assertRaisesRegex(RuntimeError, "before_drop"):
            _migrate_audit_annual_reports_year_program_unique()
        self.assertTrue(_has_year_only_unique())
        self.assertNotIn("audit_annual_reports_new", _table_names())
        self.assertEqual(len(_report_rows()), 2)
        self.assertEqual(_report_rows()[0][3], "CANARY-2024")

    def test_c_fail_after_drop_rolls_back(self) -> None:
        _install_legacy()
        initializer._AUDIT_ANNUAL_REPORTS_FAIL_AFTER = "after_drop"
        with self.assertRaisesRegex(RuntimeError, "after_drop"):
            _migrate_audit_annual_reports_year_program_unique()
        self.assertIn("audit_annual_reports", _table_names())
        self.assertNotIn("audit_annual_reports_new", _table_names())
        self.assertTrue(_has_year_only_unique())
        self.assertEqual(len(_report_rows()), 2)
        self.assertEqual(_report_rows()[1][3], "CANARY-2025")

    def test_d_fail_after_rename_rolls_back(self) -> None:
        _install_legacy()
        initializer._AUDIT_ANNUAL_REPORTS_FAIL_AFTER = "after_rename"
        with self.assertRaisesRegex(RuntimeError, "after_rename"):
            _migrate_audit_annual_reports_year_program_unique()
        self.assertTrue(_has_year_only_unique())
        self.assertNotIn("audit_annual_reports_new", _table_names())
        self.assertEqual(len(_report_rows()), 2)
        self.assertEqual(_report_rows()[0][3], "CANARY-2024")

    def test_e_second_start_is_idempotent(self) -> None:
        _install_legacy()
        _ensure_audit_annual_report_table()
        first = _report_rows()
        _ensure_audit_annual_report_table()
        initialize_database()
        self.assertEqual(_report_rows(), first)
        self.assertTrue(_has_year_program_unique())

    def test_f_empty_helper_leftover_is_dropped_and_migrated(self) -> None:
        _install_legacy(
            extra_sql="CREATE TABLE audit_annual_reports_new (id INTEGER PRIMARY KEY);"
        )
        self.assertIn("audit_annual_reports_new", _table_names())
        _ensure_audit_annual_report_table()
        self.assertNotIn("audit_annual_reports_new", _table_names())
        self.assertTrue(_has_year_program_unique())
        self.assertEqual(len(_report_rows()), 2)

    def test_g_never_replaces_populated_source_with_empty_live(self) -> None:
        _install_legacy()
        initializer._AUDIT_ANNUAL_REPORTS_FAIL_AFTER = "after_drop"
        with self.assertRaises(RuntimeError):
            _migrate_audit_annual_reports_year_program_unique()
        self.assertEqual(len(_report_rows()), 2)
        initializer._AUDIT_ANNUAL_REPORTS_FAIL_AFTER = None
        _ensure_audit_annual_report_table()
        self.assertEqual(len(_report_rows()), 2)
        self.assertTrue(_has_year_program_unique())

    def test_helper_with_data_and_live_table_fails_safely(self) -> None:
        _install_legacy(
            extra_sql="""
            CREATE TABLE audit_annual_reports_new (
                id INTEGER PRIMARY KEY,
                payload TEXT
            );
            INSERT INTO audit_annual_reports_new (id, payload) VALUES (1, 'keep');
            """
        )
        with self.assertRaisesRegex(RuntimeError, "už obsahuje data"):
            _migrate_audit_annual_reports_year_program_unique()
        self.assertTrue(_has_year_only_unique())
        self.assertEqual(len(_report_rows()), 2)
        self.assertIn("audit_annual_reports_new", _table_names())

    def test_missing_live_table_with_helper_data_does_not_create_empty(self) -> None:
        conn = _connect()
        try:
            conn.execute("DROP TABLE IF EXISTS audit_annual_reports")
            conn.execute("DROP TABLE IF EXISTS audit_annual_reports_new")
            conn.execute(
                "CREATE TABLE audit_annual_reports_new (id INTEGER PRIMARY KEY, silne_stranky TEXT)"
            )
            conn.execute(
                "INSERT INTO audit_annual_reports_new (id, silne_stranky) VALUES (1, 'ORPHAN')"
            )
            conn.commit()
        finally:
            conn.close()
            reconfigure_database_engine(force=True)

        with self.assertRaisesRegex(RuntimeError, "živá tabulka audit_annual_reports chybí"):
            _ensure_audit_annual_report_table()
        names = _table_names()
        self.assertNotIn("audit_annual_reports", names)
        self.assertIn("audit_annual_reports_new", names)
        conn = _connect()
        try:
            payload = conn.execute(
                "SELECT silne_stranky FROM audit_annual_reports_new WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
            reconfigure_database_engine(force=True)
        self.assertEqual(payload, ("ORPHAN",))

    def test_fills_null_program_id_when_exactly_one_program(self) -> None:
        _install_legacy(
            rows=(
                (21, 2023, None, "NULL-PROG", "", "", "", None, None, None),
            )
        )
        fake = SimpleNamespace(id=555)
        with patch(
            "moduly.audity.sluzby.audit_annual_program_service."
            "audit_annual_program_service.list_programs_for_year",
            return_value=[fake],
        ):
            _migrate_audit_annual_reports_year_program_unique()
        rows = _report_rows()
        self.assertEqual(rows, [(21, 2023, 555, "NULL-PROG", "", "", "", None)])
        self.assertTrue(_has_year_program_unique())

    def test_unresolved_program_id_keeps_original_table(self) -> None:
        _install_legacy(
            rows=(
                (22, 2022, None, "UNRESOLVED", "", "", "", None, None, None),
            )
        )
        with patch(
            "moduly.audity.sluzby.audit_annual_program_service."
            "audit_annual_program_service.list_programs_for_year",
            return_value=[],
        ):
            with self.assertRaisesRegex(RuntimeError, "nemůže doplnit audit_program_id"):
                _migrate_audit_annual_reports_year_program_unique()
        self.assertTrue(_has_year_only_unique())
        self.assertEqual(_report_rows()[0][3], "UNRESOLVED")


if __name__ == "__main__":
    unittest.main()
