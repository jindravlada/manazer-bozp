from datetime import datetime

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
    from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole  # noqa: F401
    from moduly.nastaveni.modely.exposed_group import ExposedGroup  # noqa: F401
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
    from moduly.pravni_pozadavky.modely.legal_requirement_source import (  # noqa: F401
        LegalRequirementSource,
    )
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_document_version import (  # noqa: F401
        LegalDocumentVersion,
    )
    from moduly.pravni_pozadavky.modely.legal_section import LegalSection  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_change import LegalChange  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection  # noqa: F401
    from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun  # noqa: F401
    from core.shared.modely.entity_link import EntityLink  # noqa: F401
    from core.shared.modely.control_result import ControlResult  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_identification_photo import (  # noqa: F401
        HazardIdentificationPhoto,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_source_category import (  # noqa: F401
        HazardSourceCategory,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_operation import (  # noqa: F401
        HazardLibraryTemplateOperation,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (  # noqa: F401
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (  # noqa: F401
        HazardLibraryTemplateLegalLink,
    )
    from core.ai_oponentni.modely.ai_peer_review import (  # noqa: F401
        AiPeerReview,
        AiPeerReviewBatch,
    )
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal  # noqa: F401
    from core.ai_oponentni.modely.ai_proposal_package import AiProposalPackageRecord  # noqa: F401

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
    _ensure_workplace_hierarchy_columns()
    _ensure_responsibility_roles_table()
    _ensure_exposed_groups_table()
    _ensure_hazard_source_categories_table()
    _ensure_audit_program_columns()
    _ensure_audit_program_workplace_columns()
    _ensure_audit_program_link_columns()
    _ensure_audit_columns()
    _ensure_legal_requirement_columns()
    _ensure_legal_requirement_sources_table()
    _ensure_legal_change_columns()
    _ensure_legal_change_sections_table()
    _ensure_legal_document_columns()
    _ensure_legal_check_run_columns()
    _ensure_hazard_identifications_table()
    _ensure_hazard_inventory_items_table()
    _migrate_drop_hazard_inventory_relations()
    _ensure_hazard_events_table()
    _migrate_hazard_events_drop_identified_hazards()
    _ensure_hazard_risk_assessments_table()
    _ensure_hazard_risk_assessment_exposed_groups_table()
    _migrate_hazard_risk_assessment_groups_and_drop_consequence()
    _ensure_hazard_existing_measures_table()
    _ensure_hazard_required_measures_table()
    _ensure_hazard_identification_photos_table()
    _ensure_hazard_library_templates_table()
    _ensure_hazard_library_template_operations_table()
    _ensure_hazard_library_template_events_table()
    _migrate_hazard_library_template_master_catalog()
    _ensure_hazard_library_template_assessments_table()
    _ensure_hazard_library_template_assessment_exposed_groups_table()
    _migrate_hazard_library_template_assessment_groups_and_drop_consequence()
    _ensure_hazard_library_template_measures_tables()
    _ensure_hazard_library_template_revisions_table()
    _ensure_hazard_library_template_legal_links_table()
    _ensure_ai_peer_reviews_table()
    _ensure_ai_peer_review_batches_table()
    _ensure_ai_unassigned_proposals_table()
    _ensure_ai_proposal_packages_table()
    _migrate_legal_document_types()
    _normalize_task_status_values()
    _normalize_accident_legacy_values()


def _table_columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    with _db_engine().connect() as connection:
        columns = connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return {column[1] for column in columns}


def _table_exists(table_name: str) -> bool:
    with _db_engine().connect() as connection:
        row = connection.execute(
            text(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :table_name"
            ),
            {"table_name": table_name},
        ).fetchone()
        return row is not None


def _is_hazard_library_master_catalog_migration_complete() -> bool:
    if _table_exists("hazard_library_template_items"):
        return False

    template_columns = _table_columns("hazard_library_templates")
    if not template_columns or "category" not in template_columns:
        return False

    event_columns = _table_columns("hazard_library_template_events")
    if not event_columns or "template_id" not in event_columns:
        return False
    if "template_item_id" in event_columns:
        return False

    return True


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


def _ensure_workplace_hierarchy_columns() -> None:
    columns = _table_columns("workplaces")
    if not columns:
        return
    if "parent_id" not in columns:
        _add_column("workplaces", "parent_id INTEGER")
    if "item_type" not in columns:
        _add_column("workplaces", "item_type VARCHAR(32) DEFAULT 'operation' NOT NULL")
    with _db_engine().connect() as connection:
        connection.execute(
            text(
                "UPDATE workplaces SET item_type = 'operation' "
                "WHERE item_type IS NULL OR TRIM(item_type) = ''"
            )
        )
        connection.commit()


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
    if "source_section_id" not in columns:
        _add_column("legal_requirements", "source_section_id INTEGER")
    if "processing_status" not in columns:
        _add_column("legal_requirements", "processing_status VARCHAR(50) DEFAULT 'new'")
    if "responsible_role_id" not in columns:
        _add_column("legal_requirements", "responsible_role_id INTEGER")
    if "responsible_role_name" not in columns:
        _add_column("legal_requirements", "responsible_role_name VARCHAR(150) DEFAULT ''")
    if "title" not in columns:
        _add_column("legal_requirements", "title VARCHAR(250) DEFAULT ''")
        _migrate_legal_requirement_titles()
    if "process_code" not in columns:
        _add_column("legal_requirements", "process_code VARCHAR(20) DEFAULT ''")
        _migrate_legal_requirement_process_codes()
    if "merged_into_requirement_id" not in columns:
        _add_column("legal_requirements", "merged_into_requirement_id INTEGER")
    if "parent_requirement_id" not in columns:
        _add_column(
            "legal_requirements",
            "parent_requirement_id INTEGER REFERENCES legal_requirements(id)",
        )
    if "process_inputs" not in columns:
        _add_column("legal_requirements", "process_inputs TEXT DEFAULT ''")
    if "process_outputs" not in columns:
        _add_column("legal_requirements", "process_outputs TEXT DEFAULT ''")
    _ensure_legal_requirement_parent_index()


def _table_indexes(table_name: str) -> set[str]:
    with _db_engine().connect() as connection:
        indexes = connection.execute(text(f"PRAGMA index_list({table_name})")).fetchall()
        return {index[1] for index in indexes}


def _ensure_index(index_name: str, create_sql: str) -> None:
    with _db_engine().connect() as connection:
        connection.execute(text(create_sql))
        connection.commit()


def _ensure_legal_requirement_parent_index() -> None:
    columns = _table_columns("legal_requirements")
    if not columns or "parent_requirement_id" not in columns:
        return
    index_name = "ix_legal_requirements_parent_requirement_id"
    if index_name in _table_indexes("legal_requirements"):
        return
    _ensure_index(
        index_name,
        (
            "CREATE INDEX ix_legal_requirements_parent_requirement_id "
            "ON legal_requirements(parent_requirement_id)"
        ),
    )


def _migrate_legal_requirement_process_codes() -> None:
    from moduly.pravni_pozadavky.constants import format_process_code, parse_process_code_number

    with _db_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT id, process_code FROM legal_requirements ORDER BY id"),
        ).fetchall()

        max_number = 0
        for _row_id, process_code in rows:
            number = parse_process_code_number(process_code or "")
            if number is not None:
                max_number = max(max_number, number)

        for row_id, process_code in rows:
            if (process_code or "").strip():
                continue
            max_number += 1
            connection.execute(
                text(
                    """
                    UPDATE legal_requirements
                    SET process_code = :process_code
                    WHERE id = :row_id
                    """,
                ),
                {
                    "process_code": format_process_code(max_number),
                    "row_id": row_id,
                },
            )
        connection.commit()


def _migrate_legal_requirement_titles() -> None:
    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                UPDATE legal_requirements
                SET title = regulation_name
                WHERE COALESCE(title, '') = ''
                  AND COALESCE(regulation_name, '') != ''
                  AND (
                    legal_document_id IS NULL
                    OR regulation_name != COALESCE(
                      (
                        SELECT legal_documents.title
                        FROM legal_documents
                        WHERE legal_documents.id = legal_requirements.legal_document_id
                      ),
                      ''
                    )
                  )
                """,
            ),
        )
        connection.commit()


def _ensure_hazard_identifications_table() -> None:
    columns = _table_columns("hazard_identifications")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification

        HazardIdentification.__table__.create(bind=_db_engine(), checkfirst=True)
        return

    if "identification_number" not in columns:
        _add_column(
            "hazard_identifications",
            "identification_number VARCHAR(20) DEFAULT '' NOT NULL",
        )

    _migrate_hazard_identification_numbers()

    columns = _table_columns("hazard_identifications")
    if "title" in columns:
        _remove_hazard_identification_title_column()


def _migrate_hazard_identification_numbers() -> None:
    columns = _table_columns("hazard_identifications")
    if "identification_number" not in columns:
        return

    from datetime import datetime

    from sqlalchemy import or_, select

    from core.database.session import get_session
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification

    year_counters: dict[int, int] = {}
    with get_session() as session:
        for number in session.scalars(select(HazardIdentification.identification_number)):
            if not number or "-" not in number:
                continue
            try:
                year_str, suffix = number.split("-", 1)
                year = int(year_str)
                year_counters[year] = max(year_counters.get(year, 0), int(suffix))
            except ValueError:
                continue

    with get_session() as session:
        stmt = (
            select(HazardIdentification)
            .where(
                or_(
                    HazardIdentification.identification_number == "",
                    HazardIdentification.identification_number.is_(None),
                )
            )
            .order_by(HazardIdentification.created_at, HazardIdentification.id)
        )
        records = list(session.scalars(stmt))
        for record in records:
            year = record.created_at.year if record.created_at else datetime.now().year
            year_counters[year] = year_counters.get(year, 0) + 1
            record.identification_number = f"{year}-{year_counters[year]:04d}"
            session.merge(record)
        if records:
            session.commit()


def _remove_hazard_identification_title_column() -> None:
    columns = _table_columns("hazard_identifications")
    if "title" not in columns:
        return

    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE hazard_identifications_new (
                    id INTEGER PRIMARY KEY,
                    identification_number VARCHAR(20) NOT NULL,
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
        connection.execute(
            text(
                """
                INSERT INTO hazard_identifications_new (
                    id,
                    identification_number,
                    operation_id,
                    operation_name,
                    workplace_id,
                    workplace_name,
                    workplace_part_id,
                    workplace_part_name,
                    responsible_person_id,
                    responsible_person_name,
                    started_at,
                    status,
                    note,
                    active,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    identification_number,
                    operation_id,
                    operation_name,
                    workplace_id,
                    workplace_name,
                    workplace_part_id,
                    workplace_part_name,
                    responsible_person_id,
                    responsible_person_name,
                    started_at,
                    status,
                    note,
                    active,
                    created_at,
                    updated_at
                FROM hazard_identifications
                """
            )
        )
        connection.execute(text("DROP TABLE hazard_identifications"))
        connection.execute(
            text("ALTER TABLE hazard_identifications_new RENAME TO hazard_identifications")
        )
        connection.commit()


def _ensure_hazard_inventory_items_table() -> None:
    columns = _table_columns("hazard_inventory_items")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem

        HazardInventoryItem.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "source_template_id" not in columns:
        _add_column("hazard_inventory_items", "source_template_id INTEGER")
    if "source_template_version" not in columns:
        _add_column("hazard_inventory_items", "source_template_version INTEGER")


def _migrate_drop_hazard_inventory_relations() -> None:
    """R14: odstranění evidence Souvislostí – pouze DROP tabulky, bez převodů."""
    if not _table_columns("hazard_inventory_relations"):
        return
    with _db_engine().connect() as connection:
        connection.execute(text("DROP TABLE IF EXISTS hazard_inventory_relations"))
        connection.commit()


def _ensure_hazard_events_table() -> None:
    columns = _table_columns("hazard_events")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_event import HazardEvent

        HazardEvent.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "modified" not in columns:
        _add_column("hazard_events", "modified BOOLEAN DEFAULT 0")


def _migrate_hazard_events_drop_identified_hazards() -> None:
    """R12: Událost → přímo Zdroj analýzy; odstranění tabulky identified_hazards."""
    event_columns = _table_columns("hazard_events")
    if not event_columns:
        return

    hazard_columns = _table_columns("identified_hazards")
    needs_event_rebuild = "identified_hazard_id" in event_columns or (
        "inventory_item_id" not in event_columns
    )

    if needs_event_rebuild:
        with _db_engine().connect() as connection:
            if "inventory_item_id" not in event_columns:
                connection.execute(
                    text(
                        "ALTER TABLE hazard_events "
                        "ADD COLUMN inventory_item_id INTEGER NOT NULL DEFAULT 0"
                    )
                )
                connection.commit()

            if "identified_hazard_id" in _table_columns("hazard_events") and hazard_columns:
                connection.execute(
                    text(
                        """
                        UPDATE hazard_events
                        SET inventory_item_id = (
                            SELECT identified_hazards.inventory_item_id
                            FROM identified_hazards
                            WHERE identified_hazards.id = hazard_events.identified_hazard_id
                        )
                        WHERE identified_hazard_id IS NOT NULL
                        """
                    )
                )
                connection.commit()

            connection.execute(
                text(
                    """
                    CREATE TABLE hazard_events_new (
                        id INTEGER PRIMARY KEY,
                        inventory_item_id INTEGER NOT NULL,
                        name VARCHAR(200) NOT NULL,
                        description TEXT DEFAULT '',
                        note TEXT DEFAULT '',
                        active BOOLEAN DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO hazard_events_new (
                        id,
                        inventory_item_id,
                        name,
                        description,
                        note,
                        active,
                        sort_order,
                        created_at,
                        updated_at
                    )
                    SELECT
                        id,
                        inventory_item_id,
                        name,
                        description,
                        note,
                        active,
                        sort_order,
                        created_at,
                        updated_at
                    FROM hazard_events
                    """
                )
            )
            connection.execute(text("DROP TABLE hazard_events"))
            connection.execute(
                text("ALTER TABLE hazard_events_new RENAME TO hazard_events")
            )
            connection.commit()

    if hazard_columns:
        with _db_engine().connect() as connection:
            connection.execute(text("DROP TABLE identified_hazards"))
            connection.commit()


def _ensure_hazard_risk_assessments_table() -> None:
    columns = _table_columns("hazard_risk_assessments")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment

        HazardRiskAssessment.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "severity" not in columns:
        _add_column("hazard_risk_assessments", "severity VARCHAR(32) DEFAULT '' NOT NULL")
    if "assessment_status" not in columns:
        _add_column(
            "hazard_risk_assessments",
            "assessment_status VARCHAR(32) DEFAULT 'draft' NOT NULL",
        )
    if "conclusion" not in columns:
        _add_column("hazard_risk_assessments", "conclusion TEXT DEFAULT '' NOT NULL")
    if "completed_at" not in columns:
        _add_column("hazard_risk_assessments", "completed_at DATETIME")
    if "exposed_group_id" not in columns:
        _add_column("hazard_risk_assessments", "exposed_group_id INTEGER")
    if "modified" not in columns:
        _add_column("hazard_risk_assessments", "modified BOOLEAN DEFAULT 0")
    # consequence se přidává jen pro staré DB před R20c migrací
    if "consequence" not in columns and not _table_exists(
        "hazard_risk_assessment_exposed_groups",
    ):
        _add_column("hazard_risk_assessments", "consequence TEXT DEFAULT '' NOT NULL")
    _migrate_hazard_risk_assessment_exposed_group_ids()


def _ensure_hazard_risk_assessment_exposed_groups_table() -> None:
    columns = _table_columns("hazard_risk_assessment_exposed_groups")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        HazardRiskAssessmentExposedGroup.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )
    _ensure_index(
        "idx_hazard_risk_assessment_groups_assessment",
        """
        CREATE INDEX IF NOT EXISTS idx_hazard_risk_assessment_groups_assessment
        ON hazard_risk_assessment_exposed_groups (assessment_id)
        """,
    )


def _migrate_hazard_risk_assessment_groups_and_drop_consequence() -> None:
    """R20c: M:N skupiny + odstranění consequence."""
    assessment_columns = _table_columns("hazard_risk_assessments")
    if not assessment_columns:
        return
    if not _table_exists("hazard_risk_assessment_exposed_groups"):
        return

    with _db_engine().connect() as connection:
        if "exposed_group_id" in assessment_columns:
            connection.execute(
                text(
                    """
                    INSERT INTO hazard_risk_assessment_exposed_groups (
                        assessment_id,
                        exposed_group_id,
                        sort_order
                    )
                    SELECT
                        a.id,
                        a.exposed_group_id,
                        1
                    FROM hazard_risk_assessments AS a
                    WHERE a.exposed_group_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM hazard_risk_assessment_exposed_groups AS g
                          WHERE g.assessment_id = a.id
                      )
                    """
                ),
            )
            connection.commit()

        if "consequence" not in assessment_columns:
            return

        connection.execute(
            text(
                """
                CREATE TABLE hazard_risk_assessments_r20c (
                    id INTEGER NOT NULL PRIMARY KEY,
                    hazard_event_id INTEGER NOT NULL,
                    exposed_group_id INTEGER,
                    exposed_group VARCHAR(200) NOT NULL DEFAULT '',
                    severity VARCHAR(32) NOT NULL DEFAULT '',
                    note TEXT DEFAULT '',
                    assessment_status VARCHAR(32) NOT NULL DEFAULT 'draft',
                    conclusion TEXT DEFAULT '',
                    completed_at DATETIME,
                    active BOOLEAN DEFAULT 1,
                    modified BOOLEAN DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO hazard_risk_assessments_r20c (
                    id,
                    hazard_event_id,
                    exposed_group_id,
                    exposed_group,
                    severity,
                    note,
                    assessment_status,
                    conclusion,
                    completed_at,
                    active,
                    modified,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    hazard_event_id,
                    exposed_group_id,
                    COALESCE(exposed_group, ''),
                    COALESCE(severity, ''),
                    COALESCE(note, ''),
                    COALESCE(assessment_status, 'draft'),
                    COALESCE(conclusion, ''),
                    completed_at,
                    COALESCE(active, 1),
                    COALESCE(modified, 0),
                    created_at,
                    updated_at
                FROM hazard_risk_assessments
                """
            ),
        )
        connection.execute(text("DROP TABLE hazard_risk_assessments"))
        connection.execute(
            text(
                "ALTER TABLE hazard_risk_assessments_r20c "
                "RENAME TO hazard_risk_assessments"
            ),
        )
        connection.commit()


def _ensure_exposed_groups_table() -> None:
    columns = _table_columns("exposed_groups")
    if not columns:
        from moduly.nastaveni.modely.exposed_group import ExposedGroup

        ExposedGroup.__table__.create(bind=_db_engine(), checkfirst=True)
    _seed_exposed_groups()


DEFAULT_EXPOSED_GROUPS = (
    "Zaměstnanci daného pracoviště",
    "Dodavatelé",
)


def _seed_exposed_groups() -> None:
    """Vloží výchozí položky pouze do prázdné tabulky."""
    with _db_engine().connect() as connection:
        existing_count = connection.execute(
            text("SELECT COUNT(*) FROM exposed_groups"),
        ).scalar_one()
        if existing_count:
            return

        now = datetime.now()
        for index, name in enumerate(DEFAULT_EXPOSED_GROUPS, start=1):
            connection.execute(
                text(
                    """
                    INSERT INTO exposed_groups
                        (name, note, active, sort_order, created_at, updated_at)
                    VALUES
                        (:name, '', 1, :sort_order, :created_at, :updated_at)
                    """,
                ),
                {
                    "name": name,
                    "sort_order": index,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        connection.commit()


def _ensure_hazard_source_categories_table() -> None:
    columns = _table_columns("hazard_source_categories")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_source_category import HazardSourceCategory

        HazardSourceCategory.__table__.create(bind=_db_engine(), checkfirst=True)
    _seed_and_migrate_hazard_source_categories()


def _seed_and_migrate_hazard_source_categories() -> None:
    """Založí výchozí kategorie a přejmenuje legacy názvy podle kódu (UX-RISK-3)."""
    from moduly.rizeni_rizik.constants import (
        DEFAULT_HAZARD_SOURCE_CATEGORIES,
        LEGACY_HAZARD_SOURCE_CATEGORY_NAMES,
    )

    now = datetime.now()
    with _db_engine().connect() as connection:
        for code, name, description, sort_order in DEFAULT_HAZARD_SOURCE_CATEGORIES:
            existing = connection.execute(
                text(
                    """
                    SELECT id, name FROM hazard_source_categories
                    WHERE code = :code
                    """
                ),
                {"code": code},
            ).mappings().first()
            if existing is None:
                connection.execute(
                    text(
                        """
                        INSERT INTO hazard_source_categories
                            (code, name, description, sort_order, active, created_at, updated_at)
                        VALUES
                            (:code, :name, :description, :sort_order, 1, :created_at, :updated_at)
                        """
                    ),
                    {
                        "code": code,
                        "name": name,
                        "description": description,
                        "sort_order": sort_order,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                continue

            legacy_name = LEGACY_HAZARD_SOURCE_CATEGORY_NAMES.get(code, "")
            current_name = (existing["name"] or "").strip()
            if current_name == name:
                continue
            if current_name.casefold() == legacy_name.casefold():
                connection.execute(
                    text(
                        """
                        UPDATE hazard_source_categories
                        SET name = :name,
                            description = CASE
                                WHEN TRIM(COALESCE(description, '')) = '' THEN :description
                                ELSE description
                            END,
                            sort_order = :sort_order,
                            updated_at = :updated_at
                        WHERE code = :code
                        """
                    ),
                    {
                        "code": code,
                        "name": name,
                        "description": description,
                        "sort_order": sort_order,
                        "updated_at": now,
                    },
                )
        connection.commit()


def _migrate_hazard_risk_assessment_exposed_group_ids() -> None:
    columns = _table_columns("hazard_risk_assessments")
    if "exposed_group_id" not in columns:
        return

    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

    with _db_engine().connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT id, exposed_group
                FROM hazard_risk_assessments
                WHERE exposed_group_id IS NULL
                  AND trim(exposed_group) != ''
                """,
            ),
        ).fetchall()
        if not rows:
            return

    for row_id, group_text in rows:
        group = exposed_group_service.find_or_create_for_migration(str(group_text))
        with _db_engine().connect() as connection:
            connection.execute(
                text(
                    """
                    UPDATE hazard_risk_assessments
                    SET exposed_group_id = :group_id
                    WHERE id = :assessment_id
                    """,
                ),
                {"group_id": group.id, "assessment_id": row_id},
            )
            connection.commit()


def _ensure_hazard_existing_measures_table() -> None:
    columns = _table_columns("hazard_existing_measures")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure

        HazardExistingMeasure.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "modified" not in columns:
        _add_column("hazard_existing_measures", "modified BOOLEAN DEFAULT 0")


def _ensure_hazard_required_measures_table() -> None:
    columns = _table_columns("hazard_required_measures")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure

        HazardRequiredMeasure.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "modified" not in columns:
        _add_column("hazard_required_measures", "modified BOOLEAN DEFAULT 0")


def _ensure_hazard_identification_photos_table() -> None:
    columns = _table_columns("hazard_identification_photos")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_identification_photo import (
            HazardIdentificationPhoto,
        )

        HazardIdentificationPhoto.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_hazard_library_templates_table() -> None:
    columns = _table_columns("hazard_library_templates")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate

        HazardLibraryTemplate.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "source_identification_id" not in columns:
        _add_column("hazard_library_templates", "source_identification_id INTEGER")
    if "source_inventory_item_id" not in columns:
        _add_column("hazard_library_templates", "source_inventory_item_id INTEGER")
    if "category" not in columns:
        from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT

        _add_column(
            "hazard_library_templates",
            f"category VARCHAR(32) NOT NULL DEFAULT '{HAZARD_INVENTORY_CATEGORY_EQUIPMENT}'",
        )


def _ensure_hazard_library_template_operations_table() -> None:
    columns = _table_columns("hazard_library_template_operations")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
            HazardLibraryTemplateOperation,
        )

        HazardLibraryTemplateOperation.__table__.create(bind=_db_engine(), checkfirst=True)
    _ensure_index(
        "idx_hazard_library_template_operations_unique",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hazard_library_template_operations_unique
        ON hazard_library_template_operations (template_id, operation_id)
        """,
    )


def _migrate_hazard_library_template_master_catalog() -> None:
    """R17d: položka vzoru → přímo Master zdroj rizika; události navázány na template_id."""
    if _is_hazard_library_master_catalog_migration_complete():
        return

    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT

    template_columns = _table_columns("hazard_library_templates")
    if not template_columns:
        return

    if "category" not in template_columns:
        _add_column(
            "hazard_library_templates",
            f"category VARCHAR(32) NOT NULL DEFAULT '{HAZARD_INVENTORY_CATEGORY_EQUIPMENT}'",
        )

    items_table_exists = _table_exists("hazard_library_template_items")
    item_to_template: dict[int, int] = {}

    if items_table_exists:
        with _db_engine().connect() as connection:
            templates = connection.execute(
                text("SELECT id FROM hazard_library_templates ORDER BY id")
            ).fetchall()

            for (template_id,) in templates:
                items = connection.execute(
                    text(
                        """
                        SELECT id, category, name, description, active
                        FROM hazard_library_template_items
                        WHERE template_id = :template_id
                        ORDER BY sort_order, id
                        """
                    ),
                    {"template_id": template_id},
                ).fetchall()

                if not items:
                    continue

                first_id, first_category, first_name, first_description, first_active = items[0]
                connection.execute(
                    text(
                        """
                        UPDATE hazard_library_templates
                        SET category = :category,
                            name = :name,
                            description = :description,
                            active = :active
                        WHERE id = :template_id
                        """
                    ),
                    {
                        "category": first_category,
                        "name": first_name,
                        "description": first_description or "",
                        "active": first_active,
                        "template_id": template_id,
                    },
                )
                item_to_template[first_id] = template_id

                for item_id, category, name, description, active in items[1:]:
                    orig = connection.execute(
                        text(
                            """
                            SELECT application_scope, version_number, note,
                                   source_identification_id, source_inventory_item_id,
                                   created_at, updated_at
                            FROM hazard_library_templates
                            WHERE id = :template_id
                            """
                        ),
                        {"template_id": template_id},
                    ).fetchone()
                    assert orig is not None

                    result = connection.execute(
                        text(
                            """
                            INSERT INTO hazard_library_templates (
                                name, category, description, application_scope,
                                version_number, active, note,
                                source_identification_id, source_inventory_item_id,
                                created_at, updated_at
                            )
                            VALUES (
                                :name, :category, :description, :scope,
                                :version, :active, :note,
                                :source_identification_id, :source_inventory_item_id,
                                :created_at, :updated_at
                            )
                            """
                        ),
                        {
                            "name": name,
                            "category": category,
                            "description": description or "",
                            "scope": orig[0],
                            "version": orig[1],
                            "active": active,
                            "note": orig[2] or "",
                            "source_identification_id": orig[3],
                            "source_inventory_item_id": orig[4],
                            "created_at": orig[5],
                            "updated_at": orig[6],
                        },
                    )
                    new_template_id = int(result.lastrowid)
                    item_to_template[item_id] = new_template_id

                    connection.execute(
                        text(
                            """
                            INSERT INTO hazard_library_template_operations (
                                template_id, operation_id
                            )
                            SELECT :new_template_id, operation_id
                            FROM hazard_library_template_operations
                            WHERE template_id = :template_id
                            """
                        ),
                        {
                            "new_template_id": new_template_id,
                            "template_id": template_id,
                        },
                    )

            connection.commit()

    _migrate_hazard_library_template_events_to_template_id(
        item_to_template,
        items_table_exists=items_table_exists,
    )

    if items_table_exists:
        with _db_engine().connect() as connection:
            connection.execute(text("DROP TABLE IF EXISTS hazard_library_template_items"))
            connection.commit()


def _migrate_hazard_library_template_events_to_template_id(
    item_to_template: dict[int, int],
    *,
    items_table_exists: bool,
) -> None:
    event_columns = _table_columns("hazard_library_template_events")
    if not event_columns:
        return

    if "template_id" in event_columns and "template_item_id" not in event_columns:
        return

    if "template_item_id" not in event_columns:
        return

    with _db_engine().connect() as connection:
        if "template_id" not in event_columns:
            connection.execute(
                text("ALTER TABLE hazard_library_template_events ADD COLUMN template_id INTEGER")
            )
            connection.commit()

        if item_to_template:
            for item_id, template_id in item_to_template.items():
                connection.execute(
                    text(
                        """
                        UPDATE hazard_library_template_events
                        SET template_id = :template_id
                        WHERE template_item_id = :item_id
                          AND template_id IS NULL
                        """
                    ),
                    {"template_id": template_id, "item_id": item_id},
                )
        elif items_table_exists:
            connection.execute(
                text(
                    """
                    UPDATE hazard_library_template_events
                    SET template_id = (
                        SELECT template_id
                        FROM hazard_library_template_items
                        WHERE hazard_library_template_items.id =
                            hazard_library_template_events.template_item_id
                    )
                    WHERE template_id IS NULL
                    """
                )
            )

        unresolved = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM hazard_library_template_events
                WHERE template_id IS NULL
                """
            )
        ).scalar()
        if unresolved:
            connection.commit()
            return

        connection.execute(
            text(
                """
                CREATE TABLE hazard_library_template_events_new (
                    id INTEGER PRIMARY KEY,
                    template_id INTEGER NOT NULL,
                    name VARCHAR(200) NOT NULL,
                    description TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    active BOOLEAN DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO hazard_library_template_events_new (
                    id, template_id, name, description, note, active,
                    sort_order, created_at, updated_at
                )
                SELECT
                    id, template_id, name, description, note, active,
                    sort_order, created_at, updated_at
                FROM hazard_library_template_events
                WHERE template_id IS NOT NULL
                """
            )
        )
        connection.execute(text("DROP TABLE hazard_library_template_events"))
        connection.execute(
            text(
                "ALTER TABLE hazard_library_template_events_new "
                "RENAME TO hazard_library_template_events"
            )
        )
        connection.commit()


def _ensure_hazard_library_template_events_table() -> None:
    columns = _table_columns("hazard_library_template_events")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_event import (
            HazardLibraryTemplateEvent,
        )

        HazardLibraryTemplateEvent.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_hazard_library_template_assessments_table() -> None:
    columns = _table_columns("hazard_library_template_assessments")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
            HazardLibraryTemplateAssessment,
        )

        HazardLibraryTemplateAssessment.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_hazard_library_template_assessment_exposed_groups_table() -> None:
    columns = _table_columns("hazard_library_template_assessment_exposed_groups")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
            HazardLibraryTemplateAssessmentExposedGroup,
        )

        HazardLibraryTemplateAssessmentExposedGroup.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )
    _ensure_index(
        "idx_hl_template_assessment_groups_assessment",
        """
        CREATE INDEX IF NOT EXISTS idx_hl_template_assessment_groups_assessment
        ON hazard_library_template_assessment_exposed_groups (assessment_id)
        """,
    )


def _migrate_hazard_library_template_assessment_groups_and_drop_consequence() -> None:
    """R20c: M:N skupiny katalogových posouzení + odstranění consequence."""
    columns = _table_columns("hazard_library_template_assessments")
    if not columns:
        return
    if not _table_exists("hazard_library_template_assessment_exposed_groups"):
        return

    with _db_engine().connect() as connection:
        if "exposed_group_id" in columns:
            connection.execute(
                text(
                    """
                    INSERT INTO hazard_library_template_assessment_exposed_groups (
                        assessment_id,
                        exposed_group_id,
                        sort_order
                    )
                    SELECT
                        a.id,
                        a.exposed_group_id,
                        1
                    FROM hazard_library_template_assessments AS a
                    WHERE a.exposed_group_id IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM hazard_library_template_assessment_exposed_groups AS g
                          WHERE g.assessment_id = a.id
                      )
                    """
                ),
            )
            connection.commit()

        if "consequence" not in columns:
            return

        # Nullable exposed_group_id
        create_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'hazard_library_template_assessments'"
            ),
        ).scalar()
        normalized = " ".join(str(create_sql or "").upper().split())
        needs_rebuild = (
            "CONSEQUENCE" in normalized
            or "EXPOSED_GROUP_ID INTEGER NOT NULL" in normalized
        )
        if not needs_rebuild:
            return

        connection.execute(
            text(
                """
                CREATE TABLE hazard_library_template_assessments_r20c (
                    id INTEGER NOT NULL PRIMARY KEY,
                    template_event_id INTEGER NOT NULL,
                    exposed_group_id INTEGER,
                    severity VARCHAR(32) NOT NULL DEFAULT '',
                    conclusion TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    active BOOLEAN DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO hazard_library_template_assessments_r20c (
                    id,
                    template_event_id,
                    exposed_group_id,
                    severity,
                    conclusion,
                    note,
                    active,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    template_event_id,
                    exposed_group_id,
                    COALESCE(severity, ''),
                    COALESCE(conclusion, ''),
                    COALESCE(note, ''),
                    COALESCE(active, 1),
                    COALESCE(sort_order, 0),
                    created_at,
                    updated_at
                FROM hazard_library_template_assessments
                """
            ),
        )
        connection.execute(text("DROP TABLE hazard_library_template_assessments"))
        connection.execute(
            text(
                "ALTER TABLE hazard_library_template_assessments_r20c "
                "RENAME TO hazard_library_template_assessments"
            ),
        )
        connection.commit()


def _ensure_hazard_library_template_measures_tables() -> None:
    existing_columns = _table_columns("hazard_library_template_existing_measures")
    if not existing_columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
            HazardLibraryTemplateExistingMeasure,
        )

        HazardLibraryTemplateExistingMeasure.__table__.create(bind=_db_engine(), checkfirst=True)

    required_columns = _table_columns("hazard_library_template_required_measures")
    if not required_columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
            HazardLibraryTemplateRequiredMeasure,
        )

        HazardLibraryTemplateRequiredMeasure.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_hazard_library_template_revisions_table() -> None:
    columns = _table_columns("hazard_library_template_revisions")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
            HazardLibraryTemplateRevision,
        )

        HazardLibraryTemplateRevision.__table__.create(bind=_db_engine(), checkfirst=True)
    _ensure_index(
        "idx_hazard_library_template_revisions_unique",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hazard_library_template_revisions_unique
        ON hazard_library_template_revisions (template_id, revision_number)
        """,
    )


def _ensure_hazard_library_template_legal_links_table() -> None:
    columns = _table_columns("hazard_library_template_legal_links")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
            HazardLibraryTemplateLegalLink,
        )

        HazardLibraryTemplateLegalLink.__table__.create(bind=_db_engine(), checkfirst=True)
    else:
        if "legal_document_id" not in columns:
            _add_column(
                "hazard_library_template_legal_links",
                "legal_document_id INTEGER",
            )
        _migrate_rebuild_hazard_library_template_legal_links_nullable()
        _migrate_hazard_library_template_legal_links_to_documents()
    _ensure_index(
        "idx_hazard_library_template_legal_links_template",
        """
        CREATE INDEX IF NOT EXISTS idx_hazard_library_template_legal_links_template
        ON hazard_library_template_legal_links (template_id)
        """,
    )
    _ensure_index(
        "idx_hazard_library_template_legal_links_document",
        """
        CREATE INDEX IF NOT EXISTS idx_hazard_library_template_legal_links_document
        ON hazard_library_template_legal_links (legal_document_id)
        """,
    )


def _migrate_rebuild_hazard_library_template_legal_links_nullable() -> None:
    """R19b: legal_requirement_id NULLABLE, legal_document_id jako hlavní vazba."""
    columns = _table_columns("hazard_library_template_legal_links")
    if not columns or "legal_document_id" not in columns:
        return
    with _db_engine().connect() as connection:
        create_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'hazard_library_template_legal_links'"
            ),
        ).scalar()
        if not create_sql:
            return
        normalized = " ".join(str(create_sql).upper().split())
        if "LEGAL_REQUIREMENT_ID INTEGER NOT NULL" not in normalized:
            return

        connection.execute(
            text(
                """
                CREATE TABLE hazard_library_template_legal_links_r19b (
                    id INTEGER NOT NULL PRIMARY KEY,
                    template_id INTEGER NOT NULL,
                    legal_document_id INTEGER,
                    legal_requirement_id INTEGER,
                    note TEXT DEFAULT '',
                    active BOOLEAN DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME,
                    updated_at DATETIME
                )
                """
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO hazard_library_template_legal_links_r19b (
                    id,
                    template_id,
                    legal_document_id,
                    legal_requirement_id,
                    note,
                    active,
                    sort_order,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    template_id,
                    legal_document_id,
                    legal_requirement_id,
                    COALESCE(note, ''),
                    COALESCE(active, 1),
                    COALESCE(sort_order, 0),
                    created_at,
                    updated_at
                FROM hazard_library_template_legal_links
                """
            ),
        )
        connection.execute(text("DROP TABLE hazard_library_template_legal_links"))
        connection.execute(
            text(
                "ALTER TABLE hazard_library_template_legal_links_r19b "
                "RENAME TO hazard_library_template_legal_links"
            ),
        )
        connection.commit()


def _migrate_hazard_library_template_legal_links_to_documents() -> None:
    """R19b: převod legal_requirement_id → legal_document_id, pokud je jednoznačný."""
    columns = _table_columns("hazard_library_template_legal_links")
    if "legal_document_id" not in columns:
        return
    if not _table_exists("legal_requirements"):
        return

    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                UPDATE hazard_library_template_legal_links
                SET legal_document_id = (
                    SELECT legal_requirements.legal_document_id
                    FROM legal_requirements
                    WHERE legal_requirements.id =
                        hazard_library_template_legal_links.legal_requirement_id
                      AND legal_requirements.legal_document_id IS NOT NULL
                )
                WHERE legal_document_id IS NULL
                  AND legal_requirement_id IS NOT NULL
                  AND EXISTS (
                      SELECT 1
                      FROM legal_requirements
                      WHERE legal_requirements.id =
                          hazard_library_template_legal_links.legal_requirement_id
                        AND legal_requirements.legal_document_id IS NOT NULL
                  )
                """
            ),
        )
        connection.commit()



def _ensure_ai_peer_reviews_table() -> None:
    columns = _table_columns("ai_peer_reviews")
    if not columns:
        from core.ai_oponentni.modely.ai_peer_review import AiPeerReview

        AiPeerReview.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "export_id_map_json" not in columns:
        _add_column("ai_peer_reviews", "export_id_map_json TEXT DEFAULT '{}' NOT NULL")
    if "unassigned_count" not in columns:
        _add_column("ai_peer_reviews", "unassigned_count INTEGER DEFAULT 0 NOT NULL")
    if "export_scope" not in columns:
        _add_column("ai_peer_reviews", "export_scope VARCHAR(32) DEFAULT 'full' NOT NULL")
    if "batch_count" not in columns:
        _add_column("ai_peer_reviews", "batch_count INTEGER DEFAULT 1 NOT NULL")
    if "selected_source_count" not in columns:
        _add_column("ai_peer_reviews", "selected_source_count INTEGER DEFAULT 0 NOT NULL")
    if "total_object_count" not in columns:
        _add_column("ai_peer_reviews", "total_object_count INTEGER DEFAULT 0 NOT NULL")
    if "response_loaded_at" not in columns:
        _add_column("ai_peer_reviews", "response_loaded_at DATETIME")
    if "loaded_proposals_count" not in columns:
        _add_column("ai_peer_reviews", "loaded_proposals_count INTEGER DEFAULT 0 NOT NULL")
    if "pending_proposals_count" not in columns:
        _add_column("ai_peer_reviews", "pending_proposals_count INTEGER DEFAULT 0 NOT NULL")


def _ensure_ai_peer_review_batches_table() -> None:
    columns = _table_columns("ai_peer_review_batches")
    if not columns:
        from core.ai_oponentni.modely.ai_peer_review import AiPeerReviewBatch

        AiPeerReviewBatch.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_ai_unassigned_proposals_table() -> None:
    columns = _table_columns("ai_unassigned_proposals")
    if not columns:
        from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal

        AiUnassignedProposal.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "proposal_id" not in columns:
        _add_column("ai_unassigned_proposals", "proposal_id VARCHAR(64) DEFAULT '' NOT NULL")
    if "exposed_group_id" not in columns:
        _add_column("ai_unassigned_proposals", "exposed_group_id INTEGER")
    if "payload_json" not in columns:
        _add_column("ai_unassigned_proposals", "payload_json TEXT DEFAULT '{}' NOT NULL")


def _ensure_ai_proposal_packages_table() -> None:
    columns = _table_columns("ai_proposal_packages")
    if not columns:
        from core.ai_oponentni.modely.ai_proposal_package import AiProposalPackageRecord

        AiProposalPackageRecord.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_responsibility_roles_table() -> None:
    columns = _table_columns("responsibility_roles")
    if not columns:
        from moduly.nastaveni.modely.responsibility_role import ResponsibilityRole

        ResponsibilityRole.__table__.create(bind=_db_engine(), checkfirst=True)
    _seed_responsibility_roles()


def _seed_responsibility_roles() -> None:
    default_roles = [
        ("Vedoucí provozu", ""),
        ("Vedoucí údržby", ""),
        ("Mistr", ""),
        ("OZO BOZP", ""),
        ("Personalista", ""),
    ]
    with _db_engine().connect() as connection:
        existing_count = connection.execute(
            text("SELECT COUNT(*) FROM responsibility_roles"),
        ).scalar_one()
        if existing_count:
            return

        for name, description in default_roles:
            connection.execute(
                text(
                    """
                    INSERT INTO responsibility_roles (name, description, active, created_at)
                    VALUES (:name, :description, 1, :created_at)
                    """,
                ),
                {
                    "name": name,
                    "description": description,
                    "created_at": datetime.now(),
                },
            )
        connection.commit()


def _ensure_legal_requirement_sources_table() -> None:
    columns = _table_columns("legal_requirement_sources")
    if not columns:
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        LegalRequirementSource.__table__.create(bind=_db_engine(), checkfirst=True)
        _migrate_legal_requirement_sources()


def _migrate_legal_requirement_sources() -> None:
    requirement_columns = _table_columns("legal_requirements")
    if not requirement_columns or "source_section_id" not in requirement_columns:
        return

    with _db_engine().connect() as connection:
        existing_count = connection.execute(
            text("SELECT COUNT(*) FROM legal_requirement_sources"),
        ).scalar_one()
        if existing_count:
            return

        connection.execute(
            text(
                """
                INSERT INTO legal_requirement_sources (requirement_id, legal_section_id, sort_order)
                SELECT id, source_section_id, 1
                FROM legal_requirements
                WHERE source_section_id IS NOT NULL
                """,
            ),
        )
        connection.commit()


def _ensure_legal_change_columns() -> None:
    columns = _table_columns("legal_changes")
    if not columns:
        return
    if "legal_check_run_id" not in columns:
        _add_column("legal_changes", "legal_check_run_id INTEGER")


def _ensure_legal_change_sections_table() -> None:
    columns = _table_columns("legal_change_sections")
    if not columns:
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection

        LegalChangeSection.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_legal_check_run_columns() -> None:
    columns = _table_columns("legal_check_runs")
    if not columns:
        return
    if "started_at" not in columns:
        _add_column("legal_check_runs", "started_at DATETIME")
    if "documents_checked_count" not in columns:
        _add_column("legal_check_runs", "documents_checked_count INTEGER")
    if "changes_found_count" not in columns:
        _add_column("legal_check_runs", "changes_found_count INTEGER")
    if "error_message" not in columns:
        _add_column("legal_check_runs", 'error_message TEXT DEFAULT ""')


def _ensure_legal_document_columns() -> None:
    columns = _table_columns("legal_documents")
    if not columns:
        return
    if "included_in_processes" not in columns:
        _add_column("legal_documents", "included_in_processes BOOLEAN DEFAULT 0")


def _migrate_legal_document_types() -> None:
    columns = _table_columns("legal_documents")
    if not columns or "document_type" not in columns:
        return

    from moduly.pravni_pozadavky.legal_document_type_utils import detect_document_type_from_text

    with _db_engine().connect() as connection:
        rows = connection.execute(
            text("SELECT id, title, document_type FROM legal_documents"),
        ).fetchall()
        for document_id, title, current_type in rows:
            detected_type = detect_document_type_from_text(title or "")
            if detected_type != (current_type or "").strip():
                connection.execute(
                    text("UPDATE legal_documents SET document_type = :document_type WHERE id = :id"),
                    {"document_type": detected_type, "id": document_id},
                )
        connection.commit()


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
