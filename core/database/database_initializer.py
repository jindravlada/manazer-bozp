from sqlalchemy import text

from core.database.session import create_database, engine


def initialize_database() -> None:
    from core.models.attachment import Attachment  # noqa: F401
    from core.shared.modely.finding import Finding  # noqa: F401
    from moduly.audity.modely.internal_audit import InternalAudit  # noqa: F401
    from moduly.ukoly.modely.task import Task  # noqa: F401
    from moduly.kontroly.modely.control import Control  # noqa: F401
    from moduly.kontroly.modely.thp_monthly_control import ThpMonthlyControl  # noqa: F401
    from moduly.kontroly.modely.thp_yearly_kl_usage import ThpYearlyKlUsage  # noqa: F401
    from moduly.nastaveni.modely.employer import Employer  # noqa: F401
    from moduly.nastaveni.modely.thp_worker import ThpWorker  # noqa: F401
    from moduly.nastaveni.modely.workplace import Workplace  # noqa: F401
    from moduly.kniha_urazu.modely.accident import Accident  # noqa: F401
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation  # noqa: F401

    create_database()
    _ensure_thp_worker_title_columns()
    _ensure_task_columns()
    _ensure_accident_columns()
    _ensure_investigation_columns()
    _ensure_control_columns()
    _normalize_task_status_values()
    _normalize_accident_legacy_values()


def _table_columns(table_name: str) -> set[str]:
    with engine.connect() as connection:
        columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {column[1] for column in columns}


def _add_column(table_name: str, column_sql: str) -> None:
    with engine.connect() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
        connection.commit()


def _ensure_thp_worker_title_columns() -> None:
    columns = _table_columns("thp_workers")
    if "title_before" not in columns:
        _add_column("thp_workers", "title_before VARCHAR(50) DEFAULT ''")
    if "title_after" not in columns:
        _add_column("thp_workers", "title_after VARCHAR(50) DEFAULT ''")
    if "performs_controls" not in columns:
        _add_column("thp_workers", "performs_controls BOOLEAN DEFAULT 0")


def _ensure_task_columns() -> None:
    columns = _table_columns("tasks")
    additions = {
        "responsible_person_id": "responsible_person_id INTEGER",
        "workplace_id": "workplace_id INTEGER",
        "workplace_name": "workplace_name VARCHAR(150) DEFAULT ''",
        "completed_date": "completed_date DATE",
        "requires_verification": "requires_verification BOOLEAN DEFAULT 0",
        "check_due_date": "check_due_date DATE",
        "checked_date": "checked_date DATE",
        "checked_by_id": "checked_by_id INTEGER",
        "checked_by_name": "checked_by_name VARCHAR(150) DEFAULT ''",
        "canceled": "canceled BOOLEAN DEFAULT 0",
        "note": "note TEXT DEFAULT ''",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("tasks", column_sql)


def _ensure_accident_columns() -> None:
    columns = _table_columns("accidents")
    additions = {
        "datum_zapisu": "datum_zapisu DATE",
        "podatel_jmeno": "podatel_jmeno VARCHAR(150) DEFAULT ''",
        "podatel_email": "podatel_email VARCHAR(150) DEFAULT ''",
        "podatel_telefon": "podatel_telefon VARCHAR(80) DEFAULT ''",
        "podatel_pracovni_zarazeni": "podatel_pracovni_zarazeni VARCHAR(150) DEFAULT ''",
        "zamestnavatel_nazev": "zamestnavatel_nazev VARCHAR(250) DEFAULT ''",
        "zamestnavatel_ico": "zamestnavatel_ico VARCHAR(20) DEFAULT ''",
        "zamestnavatel_adresa": "zamestnavatel_adresa TEXT DEFAULT ''",
        "jmeno_prijmeni": "jmeno_prijmeni VARCHAR(200) DEFAULT ''",
        "pohlavi": "pohlavi VARCHAR(20) DEFAULT ''",
        "datum_narozeni": "datum_narozeni DATE",
        "osobni_cislo": "osobni_cislo VARCHAR(50) DEFAULT ''",
        "druh_urazu": "druh_urazu VARCHAR(80) DEFAULT ''",
        "druh_zraneni": "druh_zraneni TEXT DEFAULT ''",
        "zranena_cast_tela": "zranena_cast_tela TEXT DEFAULT ''",
        "popis_urazoveho_deje": "popis_urazoveho_deje TEXT DEFAULT ''",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("accidents", column_sql)



def _ensure_investigation_columns() -> None:
    columns = _table_columns("accident_investigations")
    additions = {
        "dalsi_postup_jiny": "dalsi_postup_jiny TEXT DEFAULT ''",
        "zajisteni_dukazu_json": "zajisteni_dukazu_json TEXT DEFAULT ''",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("accident_investigations", column_sql)


def _ensure_control_columns() -> None:
    columns = _table_columns("controls")
    if "sd_reference" not in columns:
        _add_column("controls", "sd_reference VARCHAR(200) DEFAULT ''")


def _normalize_task_status_values() -> None:
    columns = _table_columns("tasks")
    if "status" not in columns:
        return
    with engine.connect() as connection:
        connection.execute(text("UPDATE tasks SET status = 'Aktivní' WHERE status IS NULL OR status = ''"))
        connection.commit()


def _normalize_accident_legacy_values() -> None:
    columns = _table_columns("accidents")

    legacy_defaults = [
        "employee_first_name",
        "employee_last_name",
        "employee_personal_number",
        "injury_type",
        "injured_body_part",
        "description",
        "measures_summary",
    ]

    with engine.connect() as connection:
        for column in legacy_defaults:
            if column in columns:
                connection.execute(text(f"UPDATE accidents SET {column} = '' WHERE {column} IS NULL"))
        connection.commit()
