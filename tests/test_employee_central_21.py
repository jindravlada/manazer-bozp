"""EMPLOYEE-CENTRAL-21: oprava cizích klíčů po tabulce test_exams__kept."""

from __future__ import annotations

import importlib
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="employee-central-21-"))
_STAMP = "2024-06-01 08:30:00"
_EXAM_ID = 91026
_REFERENCE = re.compile(
    r"REFERENCES\s+(?:\"([A-Za-z_][A-Za-z0-9_]*)\""
    r"|'([A-Za-z_][A-Za-z0-9_]*)'"
    r"|([A-Za-z_][A-Za-z0-9_]*))",
    re.IGNORECASE,
)
_KEPT_TABLES = (
    "test_exam_examiners",
    "test_exam_written_questions",
    "test_exam_written_choices",
    "test_exam_oral_questions",
)
_WATCHED = (
    "workplaces",
    "thp_workers",
    "test_employees",
    "test_employee_central_links",
    "test_definitions",
    "test_written_question_topics",
    "test_written_questions",
    "test_oral_question_topics",
    "test_oral_questions",
    "test_exams",
    "test_exam_examiners",
    "test_exam_written_questions",
    "test_exam_written_answers",
    "test_exam_written_choices",
    "test_exam_oral_questions",
    "test_exam_validity_tracking",
)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    import core.database.database_initializer as database_initializer
    from core.database.session import engine


def _db_path() -> Path:
    return storage_module.storage_service.database_path


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(str(_db_path()))
    connection.row_factory = sqlite3.Row
    return connection


def _insert_row(connection: sqlite3.Connection, table: str, values: dict) -> None:
    columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    known = {column[1] for column in columns}
    missing = [
        column[1]
        for column in columns
        if column[3] and column[4] is None and column[1] not in values
    ]
    if missing:
        raise AssertionError(f"{table}: chybí povinné sloupce {missing}")
    used = [name for name in values if name in known]
    placeholders = ", ".join("?" for _ in used)
    names = ", ".join(f'"{name}"' for name in used)
    connection.execute(
        f'INSERT INTO "{table}" ({names}) VALUES ({placeholders})',
        [values[name] for name in used],
    )


def _seed() -> None:
    connection = _connect()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        exists = connection.execute(
            "SELECT 1 FROM test_exams WHERE id = ?",
            (_EXAM_ID,),
        ).fetchone()
        if exists is not None:
            return
        _insert_row(
            connection,
            "workplaces",
            {
                "id": 91010,
                "item_type": "operation",
                "name": "Pracoviste SYN",
                "address": "",
                "note": "",
                "active": 1,
                "audit_enabled": 1,
                "audit_interval_months": 6,
                "preferred_months_json": "[]",
                "created_at": _STAMP,
            },
        )
        for employee_id, number, first_name, may_examine in (
            (91011, "SYN-91011", "Jan", 0),
            (91014, "SYN-91014", "Petr", 1),
        ):
            _insert_row(
                connection,
                "test_employees",
                {
                    "id": employee_id,
                    "personal_number": number,
                    "first_name": first_name,
                    "last_name": "Historicky",
                    "title_before": "Ing.",
                    "title_after": "",
                    "workplace_id": 91010,
                    "may_examine": may_examine,
                    "active": 1,
                    "created_at": _STAMP,
                    "updated_at": _STAMP,
                },
            )
        _insert_row(
            connection,
            "thp_workers",
            {
                "id": 91012,
                "title_before": "",
                "first_name": "Jan",
                "last_name": "Centralni",
                "title_after": "",
                "position": "technik",
                "phone": "123",
                "email": "syn@example.test",
                "personal_number": "SYN-91012",
                "workplace_id": 91010,
                "is_thp": 1,
                "may_examine": 0,
                "active": 1,
                "performs_controls": 0,
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )
        _insert_row(
            connection,
            "test_employee_central_links",
            {
                "id": 91013,
                "test_employee_id": 91011,
                "thp_worker_id": 91012,
                "created_at": _STAMP,
            },
        )
        _insert_row(
            connection,
            "test_written_question_topics",
            {
                "id": 91020,
                "name": "Okruh SYN",
                "description": "",
                "active": 1,
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )
        _insert_row(
            connection,
            "test_written_questions",
            {
                "id": 91022,
                "topic_id": 91020,
                "text": "Banka SYN",
                "answer_kind": "single",
                "note": "",
                "active": 1,
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )
        _insert_row(
            connection,
            "test_oral_question_topics",
            {
                "id": 91023,
                "name": "Ustni okruh SYN",
                "description": "",
                "active": 1,
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )
        _insert_row(
            connection,
            "test_oral_questions",
            {
                "id": 91024,
                "topic_id": 91023,
                "text": "Banka ustni SYN",
                "note": "",
                "active": 1,
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )
        _insert_row(
            connection,
            "test_definitions",
            {
                "id": 91025,
                "name": "Test SYN",
                "description": "",
                "active": 1,
                "uses_written": 1,
                "allowed_wrong_answers": 1,
                "seconds_per_question": 30,
                "uses_oral": 1,
                "examiner_mode": "single",
                "validity_value": 2,
                "validity_unit": "years",
                "created_at": _STAMP,
                "updated_at": _STAMP,
            },
        )
        _insert_exam_graph(connection, _EXAM_ID)
        _insert_row(
            connection,
            "test_exam_validity_tracking",
            {
                "id": 91032,
                "employee_id": 91011,
                "employee_source": "test_employee",
                "test_definition_id": 91025,
            },
        )
        connection.commit()
    finally:
        connection.close()


def _insert_exam_graph(connection: sqlite3.Connection, exam_id: int) -> None:
    question_id = exam_id + 2
    answer_id = exam_id + 3
    _insert_row(
        connection,
        "test_exams",
        {
            "id": exam_id,
            "employee_id": 91011,
            "employee_source": "test_employee",
            "test_definition_id": 91025,
            "exam_date": "2024-06-01",
            "valid_until": "2026-06-01",
            "status": "finished",
            "examiner_mode": "single",
            "created_at": _STAMP,
            "employee_personal_number": "SYN-91011",
            "employee_first_name": "Jan",
            "employee_last_name": "Historicky",
            "employee_title_before": "Ing.",
            "employee_title_after": "",
            "employee_display_name": "Ing. Jan Historicky",
            "employee_workplace_name": "Pracoviste SYN",
            "employee_roles_text": "technik",
            "test_name": "Test SYN",
            "uses_written": 1,
            "uses_oral": 1,
            "allowed_wrong_answers": 1,
            "seconds_per_question": 30,
            "written_duration_seconds": 120,
            "validity_value": 2,
            "validity_unit": "years",
            "written_started_at": _STAMP,
            "written_time_mark": _STAMP,
            "written_finished_at": _STAMP,
            "written_finish_reason": "completed",
            "written_question_count": 4,
            "written_correct_count": 3,
            "written_incorrect_count": 1,
            "written_unanswered_count": 0,
            "written_allowed_wrong_answers": 1,
            "written_result": "vyhovel",
            "exam_result": "vyhovel",
            "written_evaluated_at": _STAMP,
            "written_mode": "paper",
            "signed_protocol_attachment_id": 91033,
            "written_technical_detail": "detail SYN",
        },
    )
    _insert_row(
        connection,
        "test_exam_examiners",
        {
            "id": exam_id + 1,
            "exam_id": exam_id,
            "employee_id": 91014,
            "employee_source": "test_employee",
            "display_name": "Ing. Petr Historicky",
            "role": "examiner",
            "position": 1,
        },
    )
    _insert_row(
        connection,
        "test_exam_written_questions",
        {
            "id": question_id,
            "exam_id": exam_id,
            "source_question_id": 91022,
            "topic_name": "Okruh SYN",
            "text": "Otazka snimku SYN",
            "answer_kind": "single",
            "position": 1,
            "image_stored_path": "snimek/syn.png",
            "image_sha256": "abc123",
        },
    )
    _insert_row(
        connection,
        "test_exam_written_answers",
        {
            "id": answer_id,
            "exam_question_id": question_id,
            "letter": "A",
            "position": 1,
            "text": "Odpoved SYN",
            "is_correct": 1,
            "image_stored_path": "",
            "image_sha256": "",
        },
    )
    _insert_row(
        connection,
        "test_exam_written_choices",
        {
            "id": exam_id + 4,
            "exam_id": exam_id,
            "exam_question_id": question_id,
            "exam_answer_id": answer_id,
            "selected_letter": "A",
            "saved_at": _STAMP,
        },
    )
    _insert_row(
        connection,
        "test_exam_oral_questions",
        {
            "id": exam_id + 5,
            "exam_id": exam_id,
            "source_question_id": 91024,
            "topic_name": "Ustni okruh SYN",
            "text": "Ustni SYN",
            "position": 1,
        },
    )


def _rows() -> dict[str, list[tuple]]:
    connection = _connect()
    try:
        return {
            table: [
                tuple(row)
                for row in connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                )
            ]
            for table in _WATCHED
        }
    finally:
        connection.close()


def _schema_sql() -> list[tuple]:
    names = _KEPT_TABLES + (
        "test_exams",
        "test_exam_written_answers",
        "test_exam_validity_tracking",
    )
    placeholders = ", ".join("?" for _ in names)
    connection = _connect()
    try:
        return [
            tuple(row)
            for row in connection.execute(
                f"""
                SELECT type, name, tbl_name, sql
                FROM sqlite_master
                WHERE tbl_name IN ({placeholders}) OR name IN ({placeholders})
                ORDER BY type, name
                """,
                names + names,
            )
        ]
    finally:
        connection.close()


def _create_sql(table: str) -> str:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    finally:
        connection.close()
    return "" if row is None else str(row[0])


def _rename_create(create_sql: str, table_name: str) -> str:
    updated, count = re.subn(
        r"^(\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?)"
        r'(?:"[^"]+"|\'[^\']+\'|[A-Za-z_][A-Za-z0-9_]*)',
        lambda match: f'{match.group(1)}"{table_name}"',
        create_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1:
        raise AssertionError(create_sql)
    return updated


def _replace_table_sql(table: str, new_sql: str) -> None:
    connection = _connect()
    try:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("PRAGMA legacy_alter_table=ON")
        indexes = [
            row[0]
            for row in connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL
                ORDER BY name
                """,
                (table,),
            )
        ]
        triggers = [
            row[0]
            for row in connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'trigger' AND tbl_name = ? AND sql IS NOT NULL
                ORDER BY name
                """,
                (table,),
            )
        ]
        temporary = f"{table}__setup"
        connection.execute("BEGIN")
        connection.execute(_rename_create(new_sql, temporary))
        connection.execute(f'INSERT INTO "{temporary}" SELECT * FROM "{table}"')
        connection.execute(f'DROP TABLE "{table}"')
        connection.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
        for statement in indexes:
            connection.execute(statement)
        for statement in triggers:
            connection.execute(statement)
        connection.execute("COMMIT")
        connection.execute("PRAGMA legacy_alter_table=OFF")
    finally:
        connection.close()


def _point_exam_at_kept(sql: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2) or match.group(3)
        if name != "test_exams":
            return match.group(0)
        return 'REFERENCES "test_exams__kept"'

    updated = _REFERENCE.sub(replace, sql)
    if "test_exams__kept" not in updated:
        raise AssertionError(sql)
    return updated


def _break_kept_references() -> None:
    for table in _KEPT_TABLES:
        _replace_table_sql(table, _point_exam_at_kept(_create_sql(table)))


def _add_employee_fk(sql: str) -> str:
    body = sql.rstrip().rstrip(";")
    if not body.endswith(")"):
        raise AssertionError(body)
    return (
        body[:-1]
        + ", FOREIGN KEY(employee_id) REFERENCES test_employees (id))"
    )


def _foreign_keys(table: str) -> set[tuple[str, str, str]]:
    connection = _connect()
    try:
        return {
            (str(row[3]), str(row[2]), str(row[4]))
            for row in connection.execute(f'PRAGMA foreign_key_list("{table}")')
        }
    finally:
        connection.close()


def _assert_exam_targets(test: unittest.TestCase) -> None:
    test.assertEqual(
        _foreign_keys("test_exams"),
        {("test_definition_id", "test_definitions", "id")},
    )
    test.assertEqual(
        _foreign_keys("test_exam_examiners"),
        {("exam_id", "test_exams", "id")},
    )
    test.assertEqual(
        _foreign_keys("test_exam_written_questions"),
        {
            ("exam_id", "test_exams", "id"),
            ("source_question_id", "test_written_questions", "id"),
        },
    )
    test.assertEqual(
        _foreign_keys("test_exam_written_choices"),
        {
            ("exam_id", "test_exams", "id"),
            ("exam_question_id", "test_exam_written_questions", "id"),
            ("exam_answer_id", "test_exam_written_answers", "id"),
        },
    )
    test.assertEqual(
        _foreign_keys("test_exam_oral_questions"),
        {
            ("exam_id", "test_exams", "id"),
            ("source_question_id", "test_oral_questions", "id"),
        },
    )
    test.assertEqual(
        _foreign_keys("test_exam_written_answers"),
        {("exam_question_id", "test_exam_written_questions", "id")},
    )
    test.assertEqual(
        _foreign_keys("test_exam_validity_tracking"),
        {("test_definition_id", "test_definitions", "id")},
    )


def _assert_database_sound(test: unittest.TestCase) -> None:
    connection = _connect()
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        kept = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE name LIKE '%__kept%' OR IFNULL(sql, '') LIKE '%__kept%'
            """
        ).fetchall()
        index_rows = connection.execute(
            'PRAGMA index_list("test_exam_written_choices")'
        ).fetchall()
        repair_tables = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE name LIKE '%__fkrepair%' OR name LIKE '%__setup%'
            """
        ).fetchall()
    finally:
        connection.close()
    test.assertEqual(integrity, "ok")
    test.assertEqual(violations, [])
    test.assertEqual(kept, [])
    test.assertEqual(repair_tables, [])
    index_names = {row[1] for row in index_rows}
    test.assertIn("ix_test_exam_written_choices_exam_id", index_names)
    test.assertTrue(any(row[2] for row in index_rows))
    test.assertIn(
        "uq_test_exam_written_choices_question",
        _create_sql("test_exam_written_choices"),
    )
    _assert_exam_targets(test)
    _assert_engine_foreign_keys_off(test)


def _assert_engine_foreign_keys_off(test: unittest.TestCase) -> None:
    with engine.connect() as connection:
        foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar()
        legacy = connection.exec_driver_sql("PRAGMA legacy_alter_table").scalar()
    test.assertEqual(foreign_keys, 0)
    test.assertEqual(legacy, 0)


class EmployeeCentral21TestCase(unittest.TestCase):
    def setUp(self) -> None:
        initialize_database()
        _seed()

    def tearDown(self) -> None:
        connection = _connect()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute('DROP TABLE IF EXISTS "test_exams__kept"')
            connection.commit()
        finally:
            connection.close()
        initialize_database()

    def test_restore_rewrites_only_missing_kept_parent(self) -> None:
        sql = (
            'FOREIGN KEY(exam_id) REFERENCES "test_exams__kept" (id), '
            "FOREIGN KEY(source_question_id) REFERENCES test_written_questions (id), "
            "FOREIGN KEY(exam_question_id) REFERENCES test_exam_written_questions (id), "
            "FOREIGN KEY(exam_answer_id) REFERENCES test_exam_written_answers (id)"
        )
        existing = {
            "test_exams",
            "test_written_questions",
            "test_exam_written_questions",
            "test_exam_written_answers",
        }
        updated = database_initializer._restore_dropped_kept_references(sql, existing)
        self.assertIn("REFERENCES test_exams (id)", updated)
        self.assertNotIn("__kept", updated)
        self.assertIn("REFERENCES test_written_questions (id)", updated)
        self.assertIn("REFERENCES test_exam_written_questions (id)", updated)
        self.assertIn("REFERENCES test_exam_written_answers (id)", updated)
        blocked = database_initializer._restore_dropped_kept_references(
            sql,
            existing | {"test_exams__kept"},
        )
        self.assertEqual(blocked, sql)

    def test_broken_schema_keeps_rows_and_accepts_foreign_keys(self) -> None:
        before = _rows()
        answers_sql = _create_sql("test_exam_written_answers")
        _break_kept_references()
        self.assertEqual(_rows(), before)
        self.assertIn("test_exams__kept", _create_sql("test_exam_written_choices"))
        self.assertIn(
            "REFERENCES test_written_questions",
            _create_sql("test_exam_written_questions"),
        )
        self.assertIn(
            "REFERENCES test_exam_written_answers",
            _create_sql("test_exam_written_choices"),
        )
        initialize_database()
        self.assertEqual(_rows(), before)
        self.assertEqual(len(before["test_exams"]), 1)
        self.assertEqual(len(before["test_exam_written_answers"]), 1)
        self.assertEqual(len(before["test_exam_validity_tracking"]), 1)
        self.assertEqual(len(before["test_employee_central_links"]), 1)
        self.assertEqual(_create_sql("test_exam_written_answers"), answers_sql)
        _assert_database_sound(self)
        self._insert_and_read_with_foreign_keys()
        after_insert = _rows()
        schema = _schema_sql()
        initialize_database()
        self.assertEqual(_rows(), after_insert)
        self.assertEqual(_schema_sql(), schema)
        _assert_database_sound(self)

    def test_pre_migration_does_not_recreate_kept_references(self) -> None:
        before = _rows()
        for table in ("test_exams", "test_exam_examiners"):
            _replace_table_sql(table, _add_employee_fk(_create_sql(table)))
        self.assertEqual(_rows(), before)
        self.assertIn(
            ("employee_id", "test_employees", "id"),
            _foreign_keys("test_exams"),
        )
        self.assertIn(
            ("exam_id", "test_exams", "id"),
            _foreign_keys("test_exam_written_questions"),
        )
        self.assertNotIn("__kept", _schema_text())
        initialize_database()
        self.assertEqual(_rows(), before)
        self.assertNotIn(
            ("employee_id", "test_employees", "id"),
            _foreign_keys("test_exams"),
        )
        self.assertNotIn(
            ("employee_id", "test_employees", "id"),
            _foreign_keys("test_exam_examiners"),
        )
        _assert_database_sound(self)
        again = _rows()
        schema = _schema_sql()
        initialize_database()
        self.assertEqual(_rows(), again)
        self.assertEqual(_schema_sql(), schema)
        _assert_database_sound(self)

    def test_repair_rolls_back_when_a_later_table_fails(self) -> None:
        _break_kept_references()
        before_rows = _rows()
        before_schema = _schema_sql()
        real = database_initializer._replace_table_keeping_rows
        calls = {"n": 0}

        def wrapped(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise RuntimeError("syntetická chyba migrace")
            return real(*args, **kwargs)

        with patch.object(
            database_initializer,
            "_replace_table_keeping_rows",
            wrapped,
        ):
            with self.assertRaises(RuntimeError):
                database_initializer._release_exam_employee_foreign_keys()
        self.assertEqual(calls["n"], 2)
        self.assertEqual(_rows(), before_rows)
        self.assertEqual(_schema_sql(), before_schema)
        for table in _KEPT_TABLES:
            self.assertIn("test_exams__kept", _create_sql(table))
        connection = _connect()
        try:
            leftovers = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE name LIKE '%__fkrepair%' OR name LIKE '%__kept%'
                   OR name LIKE '%__setup%'
                """
            ).fetchall()
        finally:
            connection.close()
        self.assertEqual(
            [row[0] for row in leftovers],
            [],
        )
        _assert_engine_foreign_keys_off(self)

    def test_existing_kept_table_is_not_retargeted(self) -> None:
        before = _rows()
        _break_kept_references()
        connection = _connect()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute(
                'CREATE TABLE "test_exams__kept" (id INTEGER PRIMARY KEY)'
            )
            connection.commit()
        finally:
            connection.close()
        initialize_database()
        self.assertEqual(_rows(), before)
        for table in _KEPT_TABLES:
            self.assertIn("test_exams__kept", _create_sql(table))
        connection = _connect()
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute('DROP TABLE "test_exams__kept"')
            connection.commit()
        finally:
            connection.close()
        initialize_database()
        self.assertEqual(_rows(), before)
        _assert_database_sound(self)

    def _insert_and_read_with_foreign_keys(self) -> None:
        exam_id = 91040
        connection = _connect()
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            _insert_exam_graph(connection, exam_id)
            exam = connection.execute(
                """
                SELECT employee_display_name, employee_personal_number,
                       written_result, exam_result, signed_protocol_attachment_id,
                       written_technical_detail, written_correct_count
                FROM test_exams WHERE id = ?
                """,
                (exam_id,),
            ).fetchone()
            examiner = connection.execute(
                "SELECT display_name, employee_id FROM test_exam_examiners WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()
            question = connection.execute(
                "SELECT text, source_question_id FROM test_exam_written_questions WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()
            answer = connection.execute(
                """
                SELECT text, is_correct FROM test_exam_written_answers
                WHERE exam_question_id = ?
                """,
                (exam_id + 2,),
            ).fetchone()
            choice = connection.execute(
                """
                SELECT selected_letter FROM test_exam_written_choices
                WHERE exam_id = ?
                """,
                (exam_id,),
            ).fetchone()
            oral = connection.execute(
                "SELECT text FROM test_exam_oral_questions WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()
            refused = False
            try:
                connection.execute(
                    """
                    INSERT INTO test_exam_examiners (
                        exam_id, employee_id, employee_source, display_name, role, position
                    ) VALUES (999999, 91014, 'test_employee', 'Nikdo', 'examiner', 2)
                    """
                )
            except sqlite3.IntegrityError:
                refused = True
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(tuple(exam), (
            "Ing. Jan Historicky",
            "SYN-91011",
            "vyhovel",
            "vyhovel",
            91033,
            "detail SYN",
            3,
        ))
        self.assertEqual(tuple(examiner), ("Ing. Petr Historicky", 91014))
        self.assertEqual(tuple(question), ("Otazka snimku SYN", 91022))
        self.assertEqual(tuple(answer), ("Odpoved SYN", 1))
        self.assertEqual(choice[0], "A")
        self.assertEqual(oral[0], "Ustni SYN")
        self.assertTrue(refused)


def _schema_text() -> str:
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT IFNULL(sql, '') FROM sqlite_master"
        ).fetchall()
    finally:
        connection.close()
    return "\n".join(str(row[0]) for row in rows)
