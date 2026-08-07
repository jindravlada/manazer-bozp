"""Izolace testovací databáze vůči sdílenému SQLAlchemy engine a schématu."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

# Sloupce, jejichž absence v celé sadě typicky znamená otrávené / legacy schéma.
_REQUIRED_SCHEMA = (
    ("hazard_identifications", "identification_number"),
    ("hazard_events", "modified"),
    ("persons", "organization"),
    ("bozp_inspections", "number"),
    ("audits", "number"),
    ("accidents", "employee_personal_number"),
    ("legal_requirements", "id"),
)


def rebind_engine_to_storage() -> None:
    """Přepojí SQLAlchemy engine na aktuální ``storage_service.database_path``."""
    import core.database.session as session_module

    session_module.reconfigure_database_engine()


def schema_is_current() -> bool:
    """True, pokud aktivní DB má očekávané tabulky a klíčové sloupce."""
    try:
        import core.database.session as session_module

        rebind_engine_to_storage()
        with session_module.engine.connect() as connection:
            for table_name, column_name in _REQUIRED_SCHEMA:
                exists = connection.execute(
                    text(
                        "SELECT 1 FROM sqlite_master "
                        "WHERE type = 'table' AND name = :name"
                    ),
                    {"name": table_name},
                ).fetchone()
                if not exists:
                    return False
                rows = connection.execute(
                    text(f"PRAGMA table_info({table_name})")
                ).fetchall()
                if column_name not in {row[1] for row in rows}:
                    return False
        return True
    except Exception:
        return False


def ensure_current_schema_if_needed() -> None:
    """
    Obnoví aktuální schéma, pokud sdílená testovací DB chybí nebo je legacy.

    Volá se z háčku unittest (před/po každém testu). Nemění produkční start aplikace.
    Nikdy nesmí shodit běh sady (např. po smazání tmp home v tearDown).
    """
    if os.environ.get("MANAGER_BOZP_TEST_AUTO_SCHEMA") != "1":
        return
    try:
        if schema_is_current():
            return
        reset_database_schema()
    except Exception:
        try:
            from core.services import storage_service as storage_module

            storage_module.storage_service.ensure_structure()
            reset_database_schema()
        except Exception:
            return


def reset_database_schema() -> None:
    """Znovu vytvoří aktuální schéma na právě aktivní databázi."""
    from core.database.database_initializer import initialize_database

    rebind_engine_to_storage()
    initialize_database()


def activate_isolated_home(home: Path) -> None:
    """Nastaví Path.home na ``home``, reloadne storage/session a inicializuje DB."""
    with patch.object(Path, "home", return_value=Path(home)):
        import core.services.storage_service as storage_module

        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()

        import core.database.session as session_module

        importlib.reload(session_module)
        from core.database.database_initializer import initialize_database

        initialize_database()
