"""MIGRATION-0: přechod schématu 3.1.0 → 3.2.0 s předmigrační zálohou."""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="migration-0-"))
_MIGRATION_HOME = _TMP
_MIGRATION_WS: Path

with patch.object(Path, "home", return_value=_MIGRATION_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()
    _MIGRATION_WS = storage_module.storage_service.base

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    # Import nesmí nechat prázdnou DB na sdíleném storage singletonu.
    initialize_database()

from core.backup import (  # noqa: E402
    create_instance_backup,
    inspect_backup_integrity,
    restore_instance_backup,
)
from core.database.upgrade_guard import (  # noqa: E402
    TRANSITION_ID,
    MigrationIncompleteError,
    PreMigrationBackupError,
    allocate_pre_migration_backup_path,
    is_migration_in_progress,
    is_transition_complete,
    mark_migration_in_progress,
    needs_legacy_upgrade_to_risk_registry,
    prepare_database_for_startup,
    read_migration_state,
    sqlite_table_exists,
)
from core.version import APP_VERSION  # noqa: E402


REQUIRED_HAZARD_TABLES = (
    "hazard_identifications",
    "hazard_inventory_items",
    "hazard_events",
    "hazard_risk_assessments",
    "hazard_risk_assessment_exposed_groups",
    "hazard_existing_measures",
    "hazard_required_measures",
    "hazard_identification_photos",
    "hazard_source_categories",
    "hazard_library_templates",
    "hazard_library_template_operations",
    "hazard_library_template_events",
    "hazard_library_template_assessments",
    "hazard_library_template_assessment_exposed_groups",
    "hazard_library_template_existing_measures",
    "hazard_library_template_required_measures",
    "hazard_library_template_revisions",
    "hazard_library_template_legal_links",
    "exposed_groups",
)

# Původní uživatelské tabulky 3.1.0 (bez Registru rizik).
LEGACY_USER_TABLES = (
    "employers",
    "persons",
    "workplaces",
    "tasks",
    "accidents",
    "accident_investigations",
    "mu_investigations",
    "audits",
    "bozp_inspections",
    "legal_requirements",
    "legal_documents",
    "attachments",
    "control_results",
)


def _count_rows(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _table_columns(db_path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return {str(r[1]) for r in rows}
    finally:
        conn.close()


def _build_schema_3_1_0(db_path: Path) -> None:
    """Reprezentativní SQLite schéma bez tabulek Registru rizik (release 3.1.0)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE employers (
                id INTEGER PRIMARY KEY,
                ico VARCHAR(20) DEFAULT '',
                name VARCHAR(250) NOT NULL,
                address VARCHAR(300) DEFAULT '',
                nace VARCHAR(50) DEFAULT '',
                active BOOLEAN DEFAULT 1,
                created_at DATETIME
            );
            CREATE TABLE persons (
                id INTEGER PRIMARY KEY,
                first_name VARCHAR(100) DEFAULT '',
                last_name VARCHAR(100) DEFAULT '',
                title_before VARCHAR(50) DEFAULT '',
                title_after VARCHAR(50) DEFAULT '',
                active BOOLEAN DEFAULT 1
            );
            CREATE TABLE workplaces (
                id INTEGER PRIMARY KEY,
                name VARCHAR(150) NOT NULL,
                address VARCHAR(250) DEFAULT '',
                note VARCHAR(250) DEFAULT '',
                active BOOLEAN DEFAULT 1,
                audit_enabled BOOLEAN DEFAULT 1,
                audit_interval_months INTEGER DEFAULT 12,
                preferred_months_json TEXT DEFAULT '[]',
                created_at DATETIME
            );
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY,
                title VARCHAR(250) NOT NULL,
                description TEXT DEFAULT '',
                status VARCHAR(50) DEFAULT 'open',
                completed BOOLEAN DEFAULT 0,
                due_date DATE,
                workplace_id INTEGER,
                workplace_name VARCHAR(150) DEFAULT ''
            );
            CREATE TABLE accidents (
                id INTEGER PRIMARY KEY,
                number VARCHAR(30) DEFAULT '',
                year INTEGER,
                employee_first_name VARCHAR(100) DEFAULT '',
                employee_last_name VARCHAR(100) DEFAULT '',
                description TEXT DEFAULT '',
                employee_name VARCHAR(150) DEFAULT ''
            );
            CREATE TABLE accident_investigations (
                id INTEGER PRIMARY KEY,
                accident_id INTEGER,
                status VARCHAR(50) DEFAULT '',
                note TEXT DEFAULT ''
            );
            CREATE TABLE mu_investigations (
                id INTEGER PRIMARY KEY,
                mu_number VARCHAR(50) DEFAULT '',
                description TEXT DEFAULT '',
                status VARCHAR(50) DEFAULT ''
            );
            CREATE TABLE audits (
                id INTEGER PRIMARY KEY,
                audit_date DATE,
                title VARCHAR(250) DEFAULT '',
                note TEXT DEFAULT ''
            );
            CREATE TABLE bozp_inspections (
                id INTEGER PRIMARY KEY,
                inspection_date DATE,
                title VARCHAR(250) DEFAULT '',
                note TEXT DEFAULT ''
            );
            CREATE TABLE legal_requirements (
                id INTEGER PRIMARY KEY,
                regulation_name VARCHAR(250) DEFAULT '',
                title VARCHAR(250) DEFAULT '',
                process_code VARCHAR(50) DEFAULT '',
                active BOOLEAN DEFAULT 1
            );
            CREATE TABLE legal_documents (
                id INTEGER PRIMARY KEY,
                title VARCHAR(250) DEFAULT '',
                document_type VARCHAR(50) DEFAULT '',
                local_file_path TEXT DEFAULT ''
            );
            CREATE TABLE attachments (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                stored_path TEXT,
                original_path TEXT,
                filename VARCHAR(250)
            );
            CREATE TABLE control_results (
                id INTEGER PRIMARY KEY,
                entity_type VARCHAR(50),
                entity_id INTEGER,
                photo_path VARCHAR(500) DEFAULT ''
            );
            """
        )
        conn.execute(
            "INSERT INTO employers(name, ico, address) VALUES (?,?,?)",
            ("Testovací firma s.r.o.", "12345678", "Praha 1"),
        )
        conn.execute(
            "INSERT INTO persons(first_name, last_name) VALUES (?,?)",
            ("Jan", "Novák"),
        )
        conn.execute(
            "INSERT INTO workplaces(name, address) VALUES (?,?)",
            ("Provozní hala", "Brno"),
        )
        conn.execute(
            "INSERT INTO tasks(title, status, workplace_name) VALUES (?,?,?)",
            ("Úkol BOZP 3.1.0", "open", "Provozní hala"),
        )
        conn.execute(
            "INSERT INTO accidents(number, year, description, employee_first_name, "
            "employee_last_name) VALUES (?,?,?,?,?)",
            ("1/2026", 2026, "Pád z výšky", "Jan", "Novák"),
        )
        conn.execute(
            "INSERT INTO accident_investigations(accident_id, status, note) VALUES (?,?,?)",
            (1, "open", "Šetření úrazu"),
        )
        conn.execute(
            "INSERT INTO mu_investigations(mu_number, description, status) VALUES (?,?,?)",
            ("MU-1/2026", "Vyšetřování MU", "open"),
        )
        conn.execute(
            "INSERT INTO audits(title, note) VALUES (?,?)",
            ("Audit BOZP", "Interní audit"),
        )
        conn.execute(
            "INSERT INTO bozp_inspections(title, note) VALUES (?,?)",
            ("Prověrka 2026", "Roční prověrka"),
        )
        conn.execute(
            "INSERT INTO legal_requirements(regulation_name, title, process_code) "
            "VALUES (?,?,?)",
            ("ZV 262/2006", "BOZP povinnost", "P01"),
        )
        conn.execute(
            "INSERT INTO legal_documents(title, document_type, local_file_path) "
            "VALUES (?,?,?)",
            ("NV 361/2007", "regulation", "/home/user/docs/predpis.pdf"),
        )
        conn.execute(
            "INSERT INTO attachments(entity_type, entity_id, stored_path, "
            "original_path, filename) VALUES (?,?,?,?,?)",
            (
                "accident",
                1,
                "accident/1/Protokol.pdf",
                "/import/originál.pdf",
                "Protokol.pdf",
            ),
        )
        conn.execute(
            "INSERT INTO control_results(entity_type, entity_id, photo_path) "
            "VALUES (?,?,?)",
            ("audity", 1, "control_results/audity/1/foto.jpg"),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_workspace_files(workspace: Path) -> Path:
    att = workspace / "prilohy" / "accident" / "1"
    att.mkdir(parents=True, exist_ok=True)
    (att / "Protokol.pdf").write_bytes(b"%PDF-310")

    photo = workspace / "control_results" / "audity" / "1"
    photo.mkdir(parents=True, exist_ok=True)
    (photo / "foto.jpg").write_bytes(b"\xff\xd8foto")

    cis = workspace / "ciselniky" / "modulove"
    cis.mkdir(parents=True, exist_ok=True)
    (cis / "vlastni.json").write_text(
        json.dumps({"polozky": ["A"]}, ensure_ascii=False), encoding="utf-8"
    )

    templates = workspace / "templates" / "kniha_urazu"
    templates.mkdir(parents=True, exist_ok=True)
    (templates / "sablona.odt").write_bytes(b"PK\x03\x04tpl")

    cfg = workspace / "konfigurace"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "sprava_dat.json").write_text(
        json.dumps(
            {
                "last_backup": {
                    "path": "/old/machine/zaloha.zip",
                    "created_at": "2026-01-01T00:00:00",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    settings = _MIGRATION_HOME / "data" / "nastaveni" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps({"theme": "default", "language": "cs"}, ensure_ascii=False),
        encoding="utf-8",
    )
    return settings


def _snapshot_legacy_counts(db_path: Path) -> dict[str, int]:
    return {table: _count_rows(db_path, table) for table in LEGACY_USER_TABLES}


class Migration0UpgradeTestCase(unittest.TestCase):
    # setUp maže DB a test staví záměrně legacy 3.1.0 – guard před testem by překážel.
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        # Izolovaný workspace zachycený při importu (nesdílet singleton s jinými testy).
        self.ws = _MIGRATION_WS
        db = self.ws / "databaze" / "manager_bozp.db"
        if db.exists():
            db.unlink()
        state = self.ws / "konfigurace" / "migration_state.json"
        if state.exists():
            state.unlink()
        for path in (self.ws / "zalohy").glob("pre-migration-*.mbbackup"):
            path.unlink()
        with patch.object(Path, "home", return_value=_MIGRATION_HOME):
            importlib.reload(storage_module)
            importlib.reload(session_module)
            session_module.dispose_database_engine()

    def tearDown(self) -> None:
        # Legacy / nedokončené schéma nesmí zůstat na sdíleném storage singletonu.
        with patch.object(Path, "home", return_value=_MIGRATION_HOME):
            importlib.reload(storage_module)
            importlib.reload(session_module)
            db = storage_module.storage_service.database_path
            if db.exists():
                db.unlink()
            session_module.reconfigure_database_engine(force=True)
            from core.database.database_initializer import initialize_database

            initialize_database()

    def _prepare_legacy_instance(self) -> tuple[Path, Path, dict[str, int]]:
        db = self.ws / "databaze" / "manager_bozp.db"
        _build_schema_3_1_0(db)
        settings = _seed_workspace_files(self.ws)
        self.assertTrue(needs_legacy_upgrade_to_risk_registry(db))
        self.assertFalse(sqlite_table_exists(db, "hazard_identifications"))
        counts = _snapshot_legacy_counts(db)
        return db, settings, counts

    def test_app_version_is_current_release(self) -> None:
        self.assertEqual(APP_VERSION, "3.4.0")

    def test_upgrade_preserves_data_and_creates_pre_migration_backup(self) -> None:
        db, settings, before = self._prepare_legacy_instance()
        abs_legal = sqlite3.connect(str(db)).execute(
            "SELECT local_file_path FROM legal_documents WHERE id=1"
        ).fetchone()[0]
        abs_original = sqlite3.connect(str(db)).execute(
            "SELECT original_path FROM attachments WHERE id=1"
        ).fetchone()[0]
        sprava_before = (self.ws / "konfigurace" / "sprava_dat.json").read_text(
            encoding="utf-8"
        )

        result = prepare_database_for_startup(
            workspace_root=self.ws,
            database_path=db,
            settings_path=settings,
        )

        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.pre_migration_backup_path)
        assert result.pre_migration_backup_path is not None
        self.assertTrue(result.pre_migration_backup_path.is_file())
        self.assertTrue(
            result.pre_migration_backup_path.name.startswith(
                f"pre-migration-{TRANSITION_ID}-"
            )
        )
        self.assertTrue(is_transition_complete(self.ws))
        self.assertFalse(is_migration_in_progress(self.ws))

        report = inspect_backup_integrity(result.pre_migration_backup_path)
        self.assertTrue(report.ok)

        after = _snapshot_legacy_counts(db)
        self.assertEqual(after, before)

        # Absolutní cesty nesmí být přepsány migrací
        conn = sqlite3.connect(str(db))
        try:
            self.assertEqual(
                conn.execute(
                    "SELECT local_file_path FROM legal_documents WHERE id=1"
                ).fetchone()[0],
                abs_legal,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT original_path FROM attachments WHERE id=1"
                ).fetchone()[0],
                abs_original,
            )
            self.assertEqual(
                conn.execute("SELECT name FROM employers WHERE id=1").fetchone()[0],
                "Testovací firma s.r.o.",
            )
            self.assertEqual(
                conn.execute("SELECT title FROM tasks WHERE id=1").fetchone()[0],
                "Úkol BOZP 3.1.0",
            )
        finally:
            conn.close()

        self.assertEqual(
            (self.ws / "konfigurace" / "sprava_dat.json").read_text(encoding="utf-8"),
            sprava_before,
        )
        self.assertTrue((self.ws / "prilohy" / "accident" / "1" / "Protokol.pdf").is_file())
        self.assertTrue((self.ws / "ciselniky" / "modulove" / "vlastni.json").is_file())
        self.assertTrue((self.ws / "templates" / "kniha_urazu" / "sablona.odt").is_file())

        for table in REQUIRED_HAZARD_TABLES:
            self.assertTrue(
                sqlite_table_exists(db, table), f"chybí tabulka {table}"
            )

        workplace_cols = _table_columns(db, "workplaces")
        self.assertIn("parent_id", workplace_cols)
        self.assertIn("item_type", workplace_cols)

    def test_second_start_is_idempotent_without_new_pre_backup(self) -> None:
        db, settings, before = self._prepare_legacy_instance()
        first = prepare_database_for_startup(
            workspace_root=self.ws,
            database_path=db,
            settings_path=settings,
        )
        backups_after_first = list((self.ws / "zalohy").glob("pre-migration-*.mbbackup"))
        self.assertEqual(len(backups_after_first), 1)

        second = prepare_database_for_startup(
            workspace_root=self.ws,
            database_path=db,
            settings_path=settings,
        )
        self.assertFalse(second.migrated)
        backups_after_second = list((self.ws / "zalohy").glob("pre-migration-*.mbbackup"))
        self.assertEqual(len(backups_after_second), 1)
        self.assertEqual(backups_after_second[0], first.pre_migration_backup_path)
        self.assertEqual(_snapshot_legacy_counts(db), before)

    def test_pre_migration_backup_failure_blocks_migration(self) -> None:
        db, settings, before = self._prepare_legacy_instance()

        def boom(*_args, **_kwargs):
            raise PreMigrationBackupError("simulační selhání zálohy")

        with patch(
            "core.database.upgrade_guard.create_verified_pre_migration_backup",
            side_effect=boom,
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_database_for_startup(
                    workspace_root=self.ws,
                    database_path=db,
                    settings_path=settings,
                )

        self.assertTrue(needs_legacy_upgrade_to_risk_registry(db))
        self.assertEqual(_snapshot_legacy_counts(db), before)
        self.assertFalse(is_migration_in_progress(self.ws))
        self.assertFalse(sqlite_table_exists(db, "hazard_identifications"))

    def test_mid_migration_failure_leaves_incomplete_marker(self) -> None:
        db, settings, _before = self._prepare_legacy_instance()

        def fail_after_schema_start() -> None:
            # Simulace zápisu uprostřed migrace + pád
            conn = sqlite3.connect(str(db))
            try:
                conn.execute(
                    "CREATE TABLE hazard_identifications ("
                    "id INTEGER PRIMARY KEY, identification_number INTEGER)"
                )
                conn.commit()
            finally:
                conn.close()
            raise RuntimeError("simulovaná chyba uprostřed migrace")

        with self.assertRaises(RuntimeError):
            prepare_database_for_startup(
                workspace_root=self.ws,
                database_path=db,
                settings_path=settings,
                initialize_fn=fail_after_schema_start,
            )

        self.assertTrue(is_migration_in_progress(self.ws))
        state = read_migration_state(self.ws)
        backup = Path((state.get("in_progress") or {})["pre_migration_backup"])
        self.assertTrue(backup.is_file())
        self.assertTrue(inspect_backup_integrity(backup).ok)

        with self.assertRaises(MigrationIncompleteError):
            prepare_database_for_startup(
                workspace_root=self.ws,
                database_path=db,
                settings_path=settings,
            )

    def test_post_migration_mbbackup_roundtrip(self) -> None:
        db, settings, before = self._prepare_legacy_instance()
        prepare_database_for_startup(
            workspace_root=self.ws,
            database_path=db,
            settings_path=settings,
        )

        package = _MIGRATION_HOME / "after-upgrade.mbbackup"
        create_instance_backup(
            package,
            workspace_root=self.ws,
            database_path=db,
            settings_path=settings,
        )
        self.assertTrue(inspect_backup_integrity(package).ok)

        clean = _MIGRATION_HOME / "clean-restore"
        clean_ws = clean / "manazer-bozp"
        clean_ws.mkdir(parents=True)
        clean_settings = clean / "settings.json"
        clean_settings.write_text("{}", encoding="utf-8")
        restore_instance_backup(
            package,
            workspace_root=clean_ws,
            settings_path=clean_settings,
        )
        restored_db = clean_ws / "databaze" / "manager_bozp.db"
        self.assertTrue(restored_db.is_file())
        self.assertEqual(_snapshot_legacy_counts(restored_db), before)
        for table in REQUIRED_HAZARD_TABLES:
            self.assertTrue(sqlite_table_exists(restored_db, table))
        self.assertTrue(
            (clean_ws / "prilohy" / "accident" / "1" / "Protokol.pdf").is_file()
        )

    def test_risk_module_usable_after_upgrade(self) -> None:
        db, settings, _ = self._prepare_legacy_instance()
        prepare_database_for_startup(
            workspace_root=self.ws,
            database_path=db,
            settings_path=settings,
        )

        from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
        from moduly.nastaveni.constants.workplace_hierarchy_constants import (
            WORKPLACE_ITEM_TYPE_OPERATION,
            WORKPLACE_ITEM_TYPE_WORKPLACE,
            WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
        )
        from moduly.nastaveni.sluzby.settings_service import settings_service
        from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
        from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
            hazard_identification_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
            hazard_inventory_item_service,
        )

        # Legacy workplace po migraci je provoz (item_type=operation).
        operation = settings_service.get_workplace_by_id(1)
        self.assertIsNotNone(operation)
        assert operation is not None
        self.assertEqual(operation.item_type, WORKPLACE_ITEM_TYPE_OPERATION)

        workplace = settings_service.save_workplace(
            name="Pracoviště migrace",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        part = settings_service.save_workplace(
            name="Část A",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=workplace.id,
        )
        identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            workplace_part_id=part.id,
            note="po upgrade",
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Lis",
            description="zdroj po migraci",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Přimáčknutí",
            description="nežádoucí událost",
        )
        self.assertGreater(identification.id, 0)
        self.assertGreater(item.id, 0)
        self.assertGreater(event.id, 0)

    def test_allocate_backup_path_never_overwrites(self) -> None:
        zalohy = self.ws / "zalohy"
        zalohy.mkdir(parents=True, exist_ok=True)
        first = allocate_pre_migration_backup_path(zalohy)
        first.write_bytes(b"x")
        second = allocate_pre_migration_backup_path(zalohy)
        self.assertNotEqual(first, second)
        self.assertFalse(second.exists())


if __name__ == "__main__":
    unittest.main()
