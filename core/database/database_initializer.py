from sqlalchemy import text

from core.database.session import create_database


def _db_engine():
    from core.database.session import engine

    return engine


def initialize_database() -> None:
    from core.models.attachment import Attachment  # noqa: F401
    from core.shared.modely.finding import Finding  # noqa: F401
    from moduly.audity.modely.audit import Audit  # noqa: F401
    from moduly.audity.modely.audit_commission_member import AuditCommissionMember  # noqa: F401
    from moduly.audity.modely.audit_program import (  # noqa: F401
        AuditProgram,
        AuditProgramVisit,
        AuditProgramVisitProcess,
        AuditProgramWorkplace,
    )
    from moduly.ukoly.modely.task import Task  # noqa: F401
    from moduly.kontroly.modely.control import Control  # noqa: F401
    from moduly.kontroly.modely.thp_monthly_control import ThpMonthlyControl  # noqa: F401
    from moduly.kontroly.modely.thp_yearly_kl_usage import ThpYearlyKlUsage  # noqa: F401
    from moduly.nastaveni.modely.employer import Employer  # noqa: F401
    from moduly.nastaveni.modely.thp_worker import ThpWorker  # noqa: F401
    from moduly.nastaveni.modely.person import Person  # noqa: F401
    from moduly.nastaveni.modely.workplace import Workplace  # noqa: F401
    from moduly.kniha_urazu.modely.accident import Accident  # noqa: F401
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation  # noqa: F401
    from moduly.vysetrovani_mu.modely.mu_investigation import MuInvestigation  # noqa: F401
    from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport  # noqa: F401
    from moduly.audity.modely.audit_annual_report import AuditAnnualReport  # noqa: F401
    from moduly.audity.modely.audit_program_final_report import AuditProgramFinalReport  # noqa: F401
    from moduly.audity.modely.audit_process_maturity_snapshot import (  # noqa: F401
        AuditProcessMaturitySnapshot,
    )
    from moduly.proverky.modely.bozp_inspection import BozpInspection  # noqa: F401
    from moduly.proverky.modely.bozp_inspection_commission_member import (  # noqa: F401
        BozpInspectionCommissionMember,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_requirement_check import (  # noqa: F401
        LegalRequirementCheck,
    )
    from moduly.pravni_pozadavky.modely.legal_requirement_sanction import (  # noqa: F401
        LegalRequirementSanction,
    )
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_document_version import (  # noqa: F401
        LegalDocumentVersion,
    )
    from moduly.pravni_pozadavky.modely.legal_section import LegalSection  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_change import LegalChange  # noqa: F401
    from core.shared.modely.entity_link import EntityLink  # noqa: F401
    from core.shared.modely.control_result import ControlResult  # noqa: F401

    create_database()
    _ensure_thp_worker_title_columns()
    _ensure_task_columns()
    _ensure_accident_columns()
    _ensure_investigation_columns()
    _ensure_control_columns()
    _ensure_person_columns()
    _ensure_mu_investigation_columns()
    _ensure_finding_columns()
    _ensure_control_result_columns()
    _ensure_audit_commission_table()
    _ensure_bozp_inspection_commission_table()
    _ensure_bozp_inspection_columns()
    _ensure_bozp_annual_report_table()
    _ensure_audit_annual_report_table()
    _ensure_audit_process_maturity_snapshot_table()
    _ensure_audit_program_final_report_table()
    _ensure_workplace_audit_columns()
    _ensure_audit_program_columns()
    _ensure_audit_program_workplace_columns()
    _ensure_audit_program_link_columns()
    _ensure_audit_columns()
    _ensure_legal_requirement_columns()
    _normalize_task_status_values()
    _normalize_accident_legacy_values()


def _table_columns(table_name: str) -> set[str]:
    with _db_engine().connect() as connection:
        columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {column[1] for column in columns}


def _add_column(table_name: str, column_sql: str) -> None:
    with _db_engine().connect() as connection:
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
        "task_type": "task_type VARCHAR(50) DEFAULT 'corrective'",
        "source_check_code": "source_check_code VARCHAR(100) DEFAULT ''",
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


def _ensure_audit_commission_table() -> None:
    columns = _table_columns("audit_commission_members")
    if columns and "record_type" not in columns:
        with _db_engine().connect() as connection:
            connection.execute(text("DROP TABLE audit_commission_members"))
            connection.commit()
        columns = set()

    if columns and "note_text" not in columns:
        _add_column("audit_commission_members", "note_text VARCHAR(250)")

    if not columns:
        from moduly.audity.modely.audit_commission_member import AuditCommissionMember

        AuditCommissionMember.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_person_columns() -> None:
    columns = _table_columns("persons")
    if "is_employee" not in columns:
        _add_column("persons", "is_employee BOOLEAN DEFAULT 0")


def _ensure_mu_investigation_columns() -> None:
    columns = _table_columns("mu_investigations")
    additions = {
        "ohledani_mista_json": "ohledani_mista_json TEXT DEFAULT ''",
        "zajisteni_dukazu_json": "zajisteni_dukazu_json TEXT DEFAULT ''",
        "svedci_json": "svedci_json TEXT DEFAULT ''",
        "casova_osa_json": "casova_osa_json TEXT DEFAULT ''",
        "dodrzovani_predpisu_json": "dodrzovani_predpisu_json TEXT DEFAULT ''",
        "kontrola_souladu_json": "kontrola_souladu_json TEXT DEFAULT ''",
        "zaver_json": "zaver_json TEXT DEFAULT ''",
        "ishikawa_json": "ishikawa_json TEXT DEFAULT ''",
        "oznameni_kdo": "oznameni_kdo VARCHAR(200) DEFAULT ''",
        "oznameni_komu": "oznameni_komu VARCHAR(200) DEFAULT ''",
        "oznameni_datum": "oznameni_datum DATE",
        "oznameni_cas": "oznameni_cas VARCHAR(20) DEFAULT ''",
        "oznameni_bezodkladne": "oznameni_bezodkladne VARCHAR(10) DEFAULT ''",
        "oznameni_duvod_pozde": "oznameni_duvod_pozde TEXT DEFAULT ''",
        "oznameni_popis": "oznameni_popis TEXT DEFAULT ''",
        "opatreni_prvni_pomoc": "opatreni_prvni_pomoc VARCHAR(10) DEFAULT ''",
        "opatreni_zzs": "opatreni_zzs VARCHAR(10) DEFAULT ''",
        "opatreni_policie": "opatreni_policie VARCHAR(10) DEFAULT ''",
        "opatreni_hzs": "opatreni_hzs VARCHAR(10) DEFAULT ''",
        "opatreni_zastavena_cinnost": "opatreni_zastavena_cinnost VARCHAR(10) DEFAULT ''",
        "opatreni_zajisteno_misto": "opatreni_zajisteno_misto VARCHAR(10) DEFAULT ''",
        "opatreni_zabraneno_manipulaci": "opatreni_zabraneno_manipulaci VARCHAR(10) DEFAULT ''",
        "opatreni_informovan_nadrizeny": "opatreni_informovan_nadrizeny VARCHAR(10) DEFAULT ''",
        "opatreni_informovan_bozp": "opatreni_informovan_bozp VARCHAR(10) DEFAULT ''",
        "oznameni_bozp_datum": "oznameni_bozp_datum DATE",
        "oznameni_bozp_cas": "oznameni_bozp_cas VARCHAR(20) DEFAULT ''",
        "opatreni_informovany_dalsi": "opatreni_informovany_dalsi VARCHAR(10) DEFAULT ''",
        "dalsi_postup": "dalsi_postup VARCHAR(250) DEFAULT ''",
        "dalsi_postup_jiny": "dalsi_postup_jiny TEXT DEFAULT ''",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("mu_investigations", column_sql)


def _ensure_finding_columns() -> None:
    columns = _table_columns("findings")
    additions = {
        "source_area_label": "source_area_label VARCHAR(150) DEFAULT ''",
        "source_section_label": "source_section_label VARCHAR(150) DEFAULT ''",
        "source_control_point_id": "source_control_point_id VARCHAR(80) DEFAULT ''",
        "source_control_point_label": "source_control_point_label VARCHAR(200) DEFAULT ''",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("findings", column_sql)


def _ensure_control_result_columns() -> None:
    columns = _table_columns("control_results")
    if "shared_experience" not in columns:
        _add_column("control_results", "shared_experience BOOLEAN DEFAULT 0 NOT NULL")
    if "photo_path" not in columns:
        _add_column("control_results", "photo_path VARCHAR(500) DEFAULT ''")


def _ensure_bozp_inspection_commission_table() -> None:
    columns = _table_columns("bozp_inspection_commission_members")
    if columns and "record_type" not in columns:
        with _db_engine().connect() as connection:
            connection.execute(text("DROP TABLE bozp_inspection_commission_members"))
            connection.commit()
        columns = set()

    if columns and "note_text" not in columns:
        _add_column("bozp_inspection_commission_members", "note_text VARCHAR(250)")

    if not columns:
        from moduly.proverky.modely.bozp_inspection_commission_member import (
            BozpInspectionCommissionMember,
        )

        BozpInspectionCommissionMember.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_bozp_inspection_columns() -> None:
    columns = _table_columns("bozp_inspections")
    if not columns:
        return
    if "silne_stranky" not in columns:
        _add_column("bozp_inspections", "silne_stranky TEXT DEFAULT '' NOT NULL")
    if "doporuceni_vedouciho" not in columns:
        _add_column("bozp_inspections", "doporuceni_vedouciho TEXT DEFAULT '' NOT NULL")


def _ensure_bozp_annual_report_table() -> None:
    columns = _table_columns("bozp_annual_reports")
    if not columns:
        from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport

        BozpAnnualReport.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "zpracoval_worker_id" not in columns:
        _add_column("bozp_annual_reports", "zpracoval_worker_id INTEGER")


def _ensure_audit_annual_report_table() -> None:
    from moduly.audity.modely.audit_annual_report import AuditAnnualReport

    columns = _table_columns("audit_annual_reports")
    if not columns:
        AuditAnnualReport.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "audit_program_id" not in columns:
        _add_column("audit_annual_reports", "audit_program_id INTEGER")
    if _audit_annual_reports_has_year_only_unique():
        _migrate_audit_annual_reports_year_program_unique()


def _audit_annual_reports_has_year_only_unique() -> bool:
    with _db_engine().connect() as connection:
        table_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'audit_annual_reports'"
            )
        ).scalar()
        if table_sql and "uq_audit_annual_reports_year_program" in table_sql:
            return False
        if table_sql and "uq_audit_annual_reports_year" in table_sql:
            return True

        indexes = connection.execute(text("PRAGMA index_list(audit_annual_reports)")).fetchall()
        for index in indexes:
            if not index[2]:
                continue
            index_name = index[1]
            if index_name == "uq_audit_annual_reports_year_program":
                continue
            columns = connection.execute(text(f"PRAGMA index_info({index_name})")).fetchall()
            column_names = [column[2] for column in columns]
            if column_names == ["year"]:
                return True
    return False


def _migrate_audit_annual_reports_year_program_unique() -> None:
    from moduly.audity.modely.audit_annual_report import AuditAnnualReport
    from moduly.audity.sluzby.audit_annual_program_service import audit_annual_program_service

    with _db_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, year, audit_program_id, silne_stranky, top_priority, "
                "doporuceni_specialisty, zpracoval, zpracoval_worker_id, created_at, updated_at "
                "FROM audit_annual_reports"
            )
        ).mappings().all()

    migrated_rows: list[dict] = []
    for row in rows:
        program_id = row["audit_program_id"]
        if program_id is None:
            programs = audit_annual_program_service.list_programs_for_year(row["year"])
            if len(programs) != 1:
                continue
            program_id = programs[0].id
        migrated_rows.append({**row, "audit_program_id": program_id})

    with _db_engine().connect() as connection:
        connection.execute(text("DROP TABLE audit_annual_reports"))
        connection.commit()

    AuditAnnualReport.__table__.create(bind=_db_engine(), checkfirst=True)

    if not migrated_rows:
        return

    with _db_engine().connect() as connection:
        for row in migrated_rows:
            connection.execute(
                text(
                    "INSERT INTO audit_annual_reports "
                    "(id, year, audit_program_id, silne_stranky, top_priority, "
                    "doporuceni_specialisty, zpracoval, zpracoval_worker_id, created_at, updated_at) "
                    "VALUES "
                    "(:id, :year, :audit_program_id, :silne_stranky, :top_priority, "
                    ":doporuceni_specialisty, :zpracoval, :zpracoval_worker_id, :created_at, :updated_at)"
                ),
                row,
            )
        connection.commit()


def _ensure_audit_process_maturity_snapshot_table() -> None:
    columns = _table_columns("audit_process_maturity_snapshots")
    if not columns:
        from moduly.audity.modely.audit_process_maturity_snapshot import AuditProcessMaturitySnapshot

        AuditProcessMaturitySnapshot.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "note" not in columns:
        _add_column("audit_process_maturity_snapshots", "note TEXT DEFAULT '' NOT NULL")
    with _db_engine().connect() as connection:
        connection.execute(
            text("UPDATE audit_process_maturity_snapshots SET note = '' WHERE note IS NULL")
        )
        connection.commit()


def _ensure_workplace_audit_columns() -> None:
    columns = _table_columns("workplaces")
    if not columns:
        return
    additions = {
        "audit_enabled": "audit_enabled BOOLEAN DEFAULT 1 NOT NULL",
        "audit_interval_months": "audit_interval_months INTEGER DEFAULT 6 NOT NULL",
        "preferred_months_json": "preferred_months_json TEXT DEFAULT '[3,4,5,9,10,11]' NOT NULL",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("workplaces", column_sql)


def _ensure_audit_program_columns() -> None:
    columns = _table_columns("audit_programs")
    if columns and "manual_planning" not in columns:
        _add_column("audit_programs", "manual_planning BOOLEAN DEFAULT 0 NOT NULL")
    if columns and "previous_program_id" not in columns:
        _add_column("audit_programs", "previous_program_id INTEGER")


def _ensure_audit_program_final_report_table() -> None:
    from moduly.audity.modely.audit_program_final_report import AuditProgramFinalReport

    columns = _table_columns("audit_program_final_reports")
    if not columns:
        AuditProgramFinalReport.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_audit_program_workplace_columns() -> None:
    columns = _table_columns("audit_program_workplaces")
    if not columns:
        return
    if "preferred_months_json" not in columns:
        _add_column("audit_program_workplaces", "preferred_months_json TEXT DEFAULT '[]' NOT NULL")


def _ensure_audit_program_link_columns() -> None:
    columns = _table_columns("audits")
    if columns and "program_id" not in columns:
        _add_column("audits", "program_id INTEGER")
    if columns and "program_visit_id" not in columns:
        _add_column("audits", "program_visit_id INTEGER")


def _ensure_audit_columns() -> None:
    columns = _table_columns("audits")
    if not columns:
        return
    if "silne_stranky" not in columns:
        _add_column("audits", "silne_stranky TEXT DEFAULT '' NOT NULL")


def _ensure_legal_requirement_columns() -> None:
    columns = _table_columns("legal_requirements")
    if not columns:
        return
    if "legal_document_id" not in columns:
        _add_column("legal_requirements", "legal_document_id INTEGER")
    if "legal_section_id" not in columns:
        _add_column("legal_requirements", "legal_section_id INTEGER")


def _normalize_task_status_values() -> None:
    columns = _table_columns("tasks")
    if "status" not in columns:
        return
    with _db_engine().connect() as connection:
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

    with _db_engine().connect() as connection:
        for column in legacy_defaults:
            if column in columns:
                connection.execute(text(f"UPDATE accidents SET {column} = '' WHERE {column} IS NULL"))
        connection.commit()
