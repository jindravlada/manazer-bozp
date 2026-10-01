from datetime import datetime

from sqlalchemy import text

from core.database.session import create_database


def _db_engine():
    from core.database.session import engine, reconfigure_database_engine

    reconfigure_database_engine()
    return engine


LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL = {
    "instance": 0,
    "catalog": 0,
}


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
    from moduly.schuzky.modely.meeting import Meeting  # noqa: F401
    from moduly.schuzky.modely.meeting_agenda_item import MeetingAgendaItem  # noqa: F401
    from moduly.schuzky.modely.meeting_event_type import MeetingEventType  # noqa: F401
    from moduly.schuzky.modely.meeting_template import MeetingTemplate  # noqa: F401
    from moduly.periodicke_cinnosti.modely.periodic_activity import (  # noqa: F401
        PeriodicActivity,
    )
    from moduly.periodicke_cinnosti.modely.periodic_activity_occurrence import (  # noqa: F401
        PeriodicActivityOccurrence,
    )
    from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem  # noqa: F401
    from moduly.rocni_plan.modely.yearly_plan_item_move import (  # noqa: F401
        YearlyPlanItemMove,
    )
    from moduly.rocni_plan.modely.yearly_plan_month_status import (  # noqa: F401
        YearlyPlanMonthStatus,
    )
    from moduly.rocni_plan.modely.yearly_plan_occurrence import (  # noqa: F401
        YearlyPlanOccurrence,
    )
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
    from moduly.proverky.modely.bozp_inspection_verification_override import (  # noqa: F401
        BozpInspectionVerificationOverride,
    )
    from moduly.audity.modely.audit_verification_override import (  # noqa: F401
        AuditVerificationOverride,
    )
    from moduly.audity.modely.audit_question_snapshot import (  # noqa: F401
        AuditQuestionSnapshot,
    )
    from moduly.audity.modely.audit_question_support_snapshot import (  # noqa: F401
        AuditQuestionSupportSnapshot,
    )
    from moduly.audity.modely.audit_scope_process import AuditScopeProcess  # noqa: F401
    from moduly.audity.modely.audit_section_summary import (  # noqa: F401
        AuditSectionSummary,
    )
    from moduly.proverky.modely.inspection_section_summary import (  # noqa: F401
        InspectionSectionSummary,
    )
    from moduly.audity.modely.audit_extraordinary_question import (  # noqa: F401
        AuditExtraordinaryQuestion,
        AuditExtraordinaryQuestionTarget,
    )
    from moduly.externi_audity.modely import (  # noqa: F401
        ExternalAudit,
        ExternalAuditFinding,
        ExternalAuditFindingTaskLink,
        ExternalAuditParticipant,
        ExternalAuditVisit,
        ExternalAuditVisitParticipant,
    )
    from moduly.statni_dozor.modely import (  # noqa: F401
        ControlAuthority,
        ControlAuthorityOffice,
        StateSupervision,
        StateSupervisionParticipant,
        StateSupervisionRequiredDocument,
        StateSupervisionTimelineItem,
    )
    from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract  # noqa: F401
    from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson  # noqa: F401
    from moduly.smlouvy_ozo.modely.ozo_person_period import OzoPersonPeriod  # noqa: F401
    from moduly.smlouvy_ozo.modely.qualification_certificate import (  # noqa: F401
        QualificationCertificate,
    )
    from moduly.smlouvy_ozo.modely.qualification_certificate_period import (  # noqa: F401
        QualificationCertificatePeriod,
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
    from core.shared.modely.similarity_checked_pair import SimilarityCheckedPair  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_existing_measure_exposed_group import (  # noqa: F401
        HazardExistingMeasureExposedGroup,
    )
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure  # noqa: F401
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview  # noqa: F401
    from moduly.rizeni_rizik.modely.risk_measure_review_item import (  # noqa: F401
        RiskMeasureReviewItem,
    )
    from moduly.rizeni_rizik.modely.hazard_identification_photo import (  # noqa: F401
        HazardIdentificationPhoto,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate  # noqa: F401
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (  # noqa: F401
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_existing_measure_exposed_group import (  # noqa: F401
        HazardLibraryTemplateExistingMeasureExposedGroup,
    )
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
    from moduly.rizeni_rizik.modely.pbp_validation_approval import (  # noqa: F401
        PbpValidationApproval,
    )
    from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (  # noqa: F401
        PravidlaBezpecnePraceEdition,
        PravidlaBezpecnePraceEditionRule,
    )
    from moduly.rizeni_rizik.modely.profession import Profession  # noqa: F401
    from moduly.rizeni_rizik.modely.profession_exposed_group import (  # noqa: F401
        ProfessionExposedGroup,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination  # noqa: F401
    from moduly.koordinace_bozp.modely.coordination_employer import (  # noqa: F401
        CoordinationEmployer,
    )
    from moduly.koordinace_bozp.modely.coordination_participant import (  # noqa: F401
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (  # noqa: F401
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (  # noqa: F401
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (  # noqa: F401
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import (  # noqa: F401
        CoordinationMeasure,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import (  # noqa: F401
        CoordinationContact,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (  # noqa: F401
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_attachment import (  # noqa: F401
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (  # noqa: F401
        CoordinationPbpRevision,
    )
    from core.ai_oponentni.modely.ai_peer_review import (  # noqa: F401
        AiPeerReview,
        AiPeerReviewBatch,
    )
    from core.ai_oponentni.modely.ai_unassigned_proposal import AiUnassignedProposal  # noqa: F401
    from core.ai_oponentni.modely.ai_proposal_package import AiProposalPackageRecord  # noqa: F401

    create_database()
    _ensure_thp_worker_title_columns()
    _ensure_ozo_person_title_columns()
    _ensure_ozo_person_period_notify_columns()
    _migrate_ozo_person_periods()
    _ensure_employer_columns()
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
    _ensure_bozp_inspection_verification_override_table()
    _ensure_audit_verification_override_table()
    _ensure_bozp_annual_report_table()
    _ensure_audit_annual_report_table()
    _ensure_audit_process_maturity_snapshot_table()
    _ensure_audit_program_final_report_table()
    _ensure_workplace_audit_columns()
    _ensure_workplace_hierarchy_columns()
    _ensure_responsibility_roles_table()
    _ensure_exposed_groups_table()
    _ensure_professions_tables()
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
    _ensure_legal_document_version_columns()
    _ensure_legal_check_run_columns()
    _ensure_hazard_identifications_table()
    _ensure_hazard_inventory_items_table()
    _migrate_drop_hazard_inventory_relations()
    _ensure_hazard_events_table()
    _migrate_hazard_events_drop_identified_hazards()
    _ensure_hazard_risk_assessments_table()
    _ensure_hazard_risk_assessment_exposed_groups_table()
    _migrate_hazard_risk_assessment_groups_and_drop_consequence()
    _migrate_exposed_target_source_type_columns()
    _ensure_hazard_existing_measures_table()
    _ensure_data_migration_flags_table()
    _ensure_hazard_existing_measure_exposed_groups_table()
    _ensure_hazard_required_measures_table()
    _ensure_risk_measure_reviews_table()
    _ensure_risk_measure_review_items_table()
    _ensure_hazard_identification_photos_table()
    _ensure_hazard_library_templates_table()
    _ensure_hazard_library_template_operations_table()
    _ensure_hazard_library_template_events_table()
    _migrate_hazard_library_template_master_catalog()
    _ensure_hazard_library_template_assessments_table()
    _ensure_hazard_library_template_assessment_exposed_groups_table()
    _migrate_hazard_library_template_assessment_groups_and_drop_consequence()
    _ensure_hazard_library_template_measures_tables()
    _ensure_hazard_library_template_existing_measure_exposed_groups_table()
    _run_existing_measure_relevance_backfill_once()
    _ensure_hazard_library_template_revisions_table()
    _ensure_hazard_library_template_legal_links_table()
    _ensure_pravidla_bezpecne_prace_editions_tables()
    _ensure_pbp_validation_approvals_table()
    _ensure_bozp_coordinations_table()
    _ensure_ai_peer_reviews_table()
    _ensure_ai_peer_review_batches_table()
    _ensure_ai_unassigned_proposals_table()
    _ensure_ai_proposal_packages_table()
    _migrate_legal_document_types()
    _ensure_meeting_minutes_columns()
    _ensure_meeting_event_type_column()
    _ensure_meeting_priority_column()
    _ensure_meeting_external_participants_column()
    _ensure_meeting_remind_from_column()
    _ensure_meeting_organizer_source_columns()
    _ensure_periodic_occurrence_columns()
    _ensure_meeting_event_types_table()
    _ensure_meeting_agenda_items_table()
    _ensure_meeting_templates_table()
    _ensure_meeting_template_organizer_source_columns()
    _ensure_yearly_plan_repeat_columns()
    _normalize_task_status_values()
    _normalize_meeting_status_values()
    _normalize_accident_legacy_values()
    _ensure_control_authority_catalog()


def _ensure_control_authority_catalog() -> None:
    from moduly.statni_dozor.sluzby.control_authority_catalog_seed_service import (
        ensure_control_authority_catalog,
    )

    if not _table_exists("control_authorities") or not _table_exists(
        "control_authority_offices"
    ):
        return
    ensure_control_authority_catalog()


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
    column_name = column_sql.split(None, 1)[0]
    if column_name in _table_columns(table_name):
        return
    with _db_engine().connect() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))
        connection.commit()


def _ensure_meeting_minutes_columns() -> None:
    columns = _table_columns("meetings")
    if not columns:
        return
    if "proceedings" not in columns:
        _add_column("meetings", "proceedings TEXT DEFAULT ''")
    if "conclusions" not in columns:
        _add_column("meetings", "conclusions TEXT DEFAULT ''")
    if "notes" not in columns:
        _add_column("meetings", "notes TEXT DEFAULT ''")


def _ensure_meeting_event_type_column() -> None:
    columns = _table_columns("meetings")
    if not columns:
        return
    if "event_type" not in columns:
        _add_column("meetings", "event_type VARCHAR(100) DEFAULT 'Schůzka' NOT NULL")


def _ensure_meeting_priority_column() -> None:
    columns = _table_columns("meetings")
    if not columns:
        return
    if "priority" not in columns:
        _add_column("meetings", "priority VARCHAR(30) DEFAULT 'Normální' NOT NULL")


def _ensure_periodic_occurrence_columns() -> None:
    columns = _table_columns("periodic_activity_occurrences")
    if not columns:
        return
    if "performed_by_kind" not in columns:
        _add_column("periodic_activity_occurrences", "performed_by_kind VARCHAR(20) DEFAULT ''")


def _ensure_yearly_plan_repeat_columns() -> None:
    columns = _table_columns("yearly_plan_items")
    if not columns:
        return
    if "repeat_every" not in columns:
        _add_column("yearly_plan_items", "repeat_every INTEGER DEFAULT 0 NOT NULL")
    if "repeat_unit" not in columns:
        _add_column("yearly_plan_items", "repeat_unit VARCHAR(20) DEFAULT 'none' NOT NULL")
    if "due_kind" not in columns:
        _add_column("yearly_plan_items", "due_kind VARCHAR(30) DEFAULT 'none' NOT NULL")
    if "due_day" not in columns:
        _add_column("yearly_plan_items", "due_day INTEGER")

    occurrence_columns = _table_columns("yearly_plan_occurrences")
    if not occurrence_columns:
        from moduly.rocni_plan.modely.yearly_plan_occurrence import YearlyPlanOccurrence

        YearlyPlanOccurrence.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_meeting_external_participants_column() -> None:
    columns = _table_columns("meetings")
    if not columns:
        return
    if "external_participants_json" not in columns:
        _add_column("meetings", "external_participants_json TEXT DEFAULT '[]'")


def _ensure_meeting_remind_from_column() -> None:
    columns = _table_columns("meetings")
    if not columns:
        return
    if "remind_from" not in columns:
        _add_column("meetings", "remind_from DATE")


def _ensure_meeting_organizer_source_columns() -> None:
    columns = _table_columns("meetings")
    if not columns:
        return
    if "organizer_source_type" not in columns:
        _add_column("meetings", "organizer_source_type VARCHAR(40)")
    if "organizer_source_id" not in columns:
        _add_column("meetings", "organizer_source_id INTEGER")


def _ensure_meeting_template_organizer_source_columns() -> None:
    columns = _table_columns("meeting_templates")
    if not columns:
        return
    if "organizer_source_type" not in columns:
        _add_column("meeting_templates", "organizer_source_type VARCHAR(40)")
    if "organizer_source_id" not in columns:
        _add_column("meeting_templates", "organizer_source_id INTEGER")


def _ensure_meeting_event_types_table() -> None:
    columns = _table_columns("meeting_event_types")
    if not columns:
        from moduly.schuzky.modely.meeting_event_type import MeetingEventType

        MeetingEventType.__table__.create(bind=_db_engine(), checkfirst=True)
    _seed_meeting_event_types()


DEFAULT_MEETING_EVENT_TYPES = (
    "Schůzka",
    "Školení",
    "Porada",
    "Jednání",
    "Meeting",
    "Konzultace",
    "Kontrolní pochůzka",
    "Telefonát",
    "Online schůzka",
    "Jiné",
)


def _seed_meeting_event_types() -> None:
    """Vloží výchozí typy pouze do prázdné tabulky."""
    if not _table_exists("meeting_event_types"):
        return
    with _db_engine().connect() as connection:
        existing_count = connection.execute(
            text("SELECT COUNT(*) FROM meeting_event_types"),
        ).scalar_one()
        if existing_count:
            return

        now = datetime.now()
        for index, name in enumerate(DEFAULT_MEETING_EVENT_TYPES, start=1):
            connection.execute(
                text(
                    """
                    INSERT INTO meeting_event_types
                        (name, active, sort_order, created_at, updated_at)
                    VALUES
                        (:name, 1, :sort_order, :created_at, :updated_at)
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


def _ensure_meeting_agenda_items_table() -> None:
    if not _table_exists("meeting_agenda_items"):
        from moduly.schuzky.modely.meeting_agenda_item import MeetingAgendaItem

        MeetingAgendaItem.__table__.create(bind=_db_engine(), checkfirst=True)

    columns = _table_columns("meeting_agenda_items")
    if not columns:
        return
    if "moje_sdeleni" not in columns:
        _add_column("meeting_agenda_items", "moje_sdeleni TEXT DEFAULT ''")
    if "prubeh_jednani" not in columns:
        _add_column("meeting_agenda_items", "prubeh_jednani TEXT DEFAULT ''")
    if "zaver" not in columns:
        _add_column("meeting_agenda_items", "zaver TEXT DEFAULT ''")
    if "status" not in columns:
        _add_column(
            "meeting_agenda_items",
            "status VARCHAR(30) DEFAULT 'Připraveno' NOT NULL",
        )


def _ensure_meeting_templates_table() -> None:
    if not _table_exists("meeting_templates"):
        from moduly.schuzky.modely.meeting_template import MeetingTemplate

        MeetingTemplate.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_thp_worker_title_columns() -> None:
    columns = _table_columns("thp_workers")
    if "title_before" not in columns:
        _add_column("thp_workers", "title_before VARCHAR(50) DEFAULT ''")
    if "title_after" not in columns:
        _add_column("thp_workers", "title_after VARCHAR(50) DEFAULT ''")
    if "performs_controls" not in columns:
        _add_column("thp_workers", "performs_controls BOOLEAN DEFAULT 0")


def _ensure_ozo_person_title_columns() -> None:
    columns = _table_columns("ozo_persons")
    if not columns:
        return
    if "title_before" not in columns:
        _add_column("ozo_persons", "title_before VARCHAR(50) DEFAULT ''")
    if "title_after" not in columns:
        _add_column("ozo_persons", "title_after VARCHAR(50) DEFAULT ''")


def _ensure_ozo_person_period_notify_columns() -> None:
    columns = _table_columns("ozo_person_periods")
    if not columns:
        return
    if "notify_before_value" not in columns:
        _add_column("ozo_person_periods", "notify_before_value INTEGER DEFAULT 0")
    if "notify_before_unit" not in columns:
        _add_column("ozo_person_periods", "notify_before_unit VARCHAR(20) DEFAULT 'days'")


def _migrate_ozo_person_periods() -> None:
    """Vytvoří první historické verze OZO a přesune přílohy ze singleton karty."""
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service

    person = ozo_person_service.repository.get()
    if person is None:
        return
    ozo_person_service.ensure_migrated(person)


def _ensure_employer_columns() -> None:
    columns = _table_columns("employers")
    if not columns:
        return
    if "abbreviation" not in columns:
        _add_column("employers", "abbreviation VARCHAR(32) DEFAULT ''")


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
        "remind_from": "remind_from DATE",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("tasks", column_sql)


def _ensure_accident_columns() -> None:
    columns = _table_columns("accidents")
    if not columns:
        return
    additions = {
        "number": "number VARCHAR(30) DEFAULT ''",
        "year": "year INTEGER",
        "employee_first_name": "employee_first_name VARCHAR(100) DEFAULT ''",
        "employee_last_name": "employee_last_name VARCHAR(100) DEFAULT ''",
        "employee_personal_number": "employee_personal_number VARCHAR(50) DEFAULT ''",
        "injury_type": "injury_type VARCHAR(250) DEFAULT ''",
        "injured_body_part": "injured_body_part VARCHAR(250) DEFAULT ''",
        "description": "description TEXT DEFAULT ''",
        "measures_summary": "measures_summary TEXT DEFAULT ''",
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
    if not columns:
        return
    additions = {
        "title_before": "title_before VARCHAR(50) DEFAULT ''",
        "title_after": "title_after VARCHAR(50) DEFAULT ''",
        "organization": "organization VARCHAR(200) DEFAULT ''",
        "job_title": "job_title VARCHAR(150) DEFAULT ''",
        "email": "email VARCHAR(150) DEFAULT ''",
        "phone": "phone VARCHAR(50) DEFAULT ''",
        "note": "note TEXT DEFAULT ''",
        "is_employee": "is_employee BOOLEAN DEFAULT 0",
        "created_at": "created_at DATETIME",
        "updated_at": "updated_at DATETIME",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("persons", column_sql)


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
    """
    Aditivně doplní chybějící sloupce control_results (nullable / DEFAULT).

    Potřeba pro AUDIT-SNAPSHOT-1a: ORM dotazy při backfillu vyžadují source_* a
    result i na neúplných legacy schématech (MIGRATION-0 test DB). Na běžné
    produkční DB jsou sloupce již přítomné — ADD je no-op. Existující hodnoty
    řádků se nemění; stará AppImage neznámé sloupce ignoruje.
    """
    columns = _table_columns("control_results")
    if not columns:
        return
    additions = {
        "source_area_id": "source_area_id VARCHAR(80) DEFAULT ''",
        "source_area_label": "source_area_label VARCHAR(150) DEFAULT ''",
        "source_section_id": "source_section_id VARCHAR(80) DEFAULT ''",
        "source_section_label": "source_section_label VARCHAR(150) DEFAULT ''",
        "source_control_point_id": "source_control_point_id VARCHAR(80) DEFAULT ''",
        "source_control_point_label": "source_control_point_label VARCHAR(200) DEFAULT ''",
        "result": "result VARCHAR(40) DEFAULT 'nekontrolovano' NOT NULL",
        "shared_experience": "shared_experience BOOLEAN DEFAULT 0 NOT NULL",
        "photo_path": "photo_path VARCHAR(500) DEFAULT ''",
        "note": "note TEXT DEFAULT ''",
        "recorded_by_name": "recorded_by_name VARCHAR(150) DEFAULT ''",
        "recorded_at": "recorded_at DATETIME",
        "created_at": "created_at DATETIME",
        "updated_at": "updated_at DATETIME",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("control_results", column_sql)

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
    additions = {
        "number": "number VARCHAR(30) DEFAULT ''",
        "year": "year INTEGER",
        "planned_month": "planned_month INTEGER",
        "inspection_date": "inspection_date DATE",
        "started_at": "started_at DATE",
        "finished_at": "finished_at DATE",
        "status": "status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL",
        "inspection_type": "inspection_type VARCHAR(30) DEFAULT 'Řádná' NOT NULL",
        "workplace_id": "workplace_id INTEGER",
        "workplace_name": "workplace_name VARCHAR(150) DEFAULT ''",
        "title": "title VARCHAR(250) DEFAULT ''",
        "silne_stranky": "silne_stranky TEXT DEFAULT '' NOT NULL",
        "doporuceni_vedouciho": "doporuceni_vedouciho TEXT DEFAULT '' NOT NULL",
        "created_at": "created_at DATETIME",
        "updated_at": "updated_at DATETIME",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("bozp_inspections", column_sql)


def _ensure_bozp_inspection_verification_override_table() -> None:
    columns = _table_columns("bozp_inspection_verification_overrides")
    if columns:
        return
    from moduly.proverky.modely.bozp_inspection_verification_override import (
        BozpInspectionVerificationOverride,
    )

    BozpInspectionVerificationOverride.__table__.create(
        bind=_db_engine(), checkfirst=True
    )


def _ensure_audit_verification_override_table() -> None:
    columns = _table_columns("audit_verification_overrides")
    if columns:
        return
    from moduly.audity.modely.audit_verification_override import AuditVerificationOverride

    AuditVerificationOverride.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_bozp_annual_report_table() -> None:
    columns = _table_columns("bozp_annual_reports")
    if not columns:
        from moduly.proverky.modely.bozp_annual_report import BozpAnnualReport

        BozpAnnualReport.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "zpracoval_worker_id" not in columns:
        _add_column("bozp_annual_reports", "zpracoval_worker_id INTEGER")


# Test hook: "before_drop" | "after_drop" | "after_rename". V produkci vždy None.
_AUDIT_ANNUAL_REPORTS_FAIL_AFTER: str | None = None

_AUDIT_ANNUAL_REPORTS_NEW_SQL = """
CREATE TABLE audit_annual_reports_new (
    id INTEGER NOT NULL PRIMARY KEY,
    year INTEGER NOT NULL,
    audit_program_id INTEGER NOT NULL,
    silne_stranky TEXT DEFAULT '' NOT NULL,
    top_priority TEXT DEFAULT '' NOT NULL,
    doporuceni_specialisty TEXT DEFAULT '' NOT NULL,
    zpracoval VARCHAR(150) DEFAULT '' NOT NULL,
    zpracoval_worker_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    CONSTRAINT uq_audit_annual_reports_year_program UNIQUE (year, audit_program_id)
)
"""


def _ensure_audit_annual_report_table() -> None:
    from moduly.audity.modely.audit_annual_report import AuditAnnualReport

    columns = _table_columns("audit_annual_reports")
    if not columns:
        if _table_exists("audit_annual_reports_new"):
            helper_count = _table_row_count("audit_annual_reports_new")
            if helper_count:
                raise RuntimeError(
                    "Nalezena pomocná tabulka audit_annual_reports_new s daty, "
                    "ale živá tabulka audit_annual_reports chybí. "
                    "Migrace se zastavila, aby nedošlo ke ztrátě dat."
                )
            with _db_engine().connect() as connection:
                connection.execute(text("DROP TABLE IF EXISTS audit_annual_reports_new"))
                connection.commit()
        AuditAnnualReport.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "audit_program_id" not in columns:
        _add_column("audit_annual_reports", "audit_program_id INTEGER")
    if _audit_annual_reports_has_year_only_unique():
        _migrate_audit_annual_reports_year_program_unique()


def _table_row_count(table_name: str) -> int:
    with _db_engine().connect() as connection:
        value = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
        return int(value or 0)


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
    """Přestaví unique(year) → unique(year, audit_program_id) v jedné SQLite transakci."""
    import sqlite3

    from core.database.session import dispose_database_engine, reconfigure_database_engine
    from core.services.storage_service import storage_service
    from moduly.audity.sluzby.audit_annual_program_service import audit_annual_program_service

    if not _audit_annual_reports_has_year_only_unique():
        return

    with _db_engine().connect() as connection:
        rows = connection.execute(
            text(
                "SELECT id, year, audit_program_id, silne_stranky, top_priority, "
                "doporuceni_specialisty, zpracoval, zpracoval_worker_id, created_at, updated_at "
                "FROM audit_annual_reports"
            )
        ).mappings().all()
        source_count = int(
            connection.execute(text("SELECT COUNT(*) FROM audit_annual_reports")).scalar() or 0
        )

    migrated_rows: list[dict] = []
    unresolved: list[int] = []
    for row in rows:
        payload = dict(row)
        program_id = payload.get("audit_program_id")
        if program_id is None:
            programs = audit_annual_program_service.list_programs_for_year(payload["year"])
            if len(programs) != 1:
                unresolved.append(int(payload["id"]))
                continue
            program_id = programs[0].id
        payload["audit_program_id"] = program_id
        migrated_rows.append(payload)

    if unresolved:
        raise RuntimeError(
            "Migrace ročních zpráv auditů nemůže doplnit audit_program_id "
            f"pro řádky id={unresolved}. Původní tabulka zůstane beze změny."
        )
    if len(migrated_rows) != source_count:
        raise RuntimeError(
            "Migrace ročních zpráv auditů: počet připravených řádků "
            f"({len(migrated_rows)}) neodpovídá zdroji ({source_count}). "
            "Původní tabulka zůstane beze změny."
        )

    db_path = storage_service.database_path
    dispose_database_engine()
    connection = sqlite3.connect(str(db_path.resolve()))
    try:
        connection.execute("BEGIN IMMEDIATE")
        tables = {
            str(item[0])
            for item in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "audit_annual_reports" not in tables:
            raise RuntimeError(
                "Migrace ročních zpráv auditů: živá tabulka audit_annual_reports chybí."
            )
        if "audit_annual_reports_new" in tables:
            helper_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM audit_annual_reports_new"
                ).fetchone()[0]
            )
            if helper_count:
                raise RuntimeError(
                    "Pomocná tabulka audit_annual_reports_new už obsahuje data. "
                    "Migrace se zastavila, aby nedošlo ke ztrátě dat."
                )
            connection.execute("DROP TABLE IF EXISTS audit_annual_reports_new")

        live_count = int(
            connection.execute("SELECT COUNT(*) FROM audit_annual_reports").fetchone()[0]
        )
        if live_count != source_count:
            raise RuntimeError(
                "Migrace ročních zpráv auditů: počet řádků se změnil před zápisem "
                f"(očekáváno {source_count}, nyní {live_count})."
            )

        connection.execute(_AUDIT_ANNUAL_REPORTS_NEW_SQL)
        for row in migrated_rows:
            connection.execute(
                """
                INSERT INTO audit_annual_reports_new (
                    id, year, audit_program_id, silne_stranky, top_priority,
                    doporuceni_specialisty, zpracoval, zpracoval_worker_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["year"],
                    row["audit_program_id"],
                    row["silne_stranky"] if row["silne_stranky"] is not None else "",
                    row["top_priority"] if row["top_priority"] is not None else "",
                    row["doporuceni_specialisty"]
                    if row["doporuceni_specialisty"] is not None
                    else "",
                    row["zpracoval"] if row["zpracoval"] is not None else "",
                    row["zpracoval_worker_id"],
                    row["created_at"],
                    row["updated_at"],
                ),
            )

        target_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM audit_annual_reports_new"
            ).fetchone()[0]
        )
        if target_count != source_count:
            raise RuntimeError(
                "Migrace ročních zpráv auditů: počet převedených řádků "
                f"({target_count}) neodpovídá zdroji ({source_count})."
            )

        if _AUDIT_ANNUAL_REPORTS_FAIL_AFTER == "before_drop":
            raise RuntimeError("simulated-fail:before_drop")
        connection.execute("DROP TABLE audit_annual_reports")
        if _AUDIT_ANNUAL_REPORTS_FAIL_AFTER == "after_drop":
            raise RuntimeError("simulated-fail:after_drop")
        connection.execute(
            "ALTER TABLE audit_annual_reports_new RENAME TO audit_annual_reports"
        )
        if _AUDIT_ANNUAL_REPORTS_FAIL_AFTER == "after_rename":
            raise RuntimeError("simulated-fail:after_rename")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
        reconfigure_database_engine(force=True)


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
    additions = {
        "number": "number VARCHAR(30) DEFAULT ''",
        "year": "year INTEGER",
        "planned_month": "planned_month INTEGER",
        "audit_date": "audit_date DATE",
        "started_at": "started_at DATE",
        "finished_at": "finished_at DATE",
        "expected_end_date": "expected_end_date DATE",
        "status": "status VARCHAR(30) DEFAULT 'Plánováno' NOT NULL",
        "audit_type": "audit_type VARCHAR(30) DEFAULT 'Řádný' NOT NULL",
        "workplace_id": "workplace_id INTEGER",
        "workplace_name": "workplace_name VARCHAR(150) DEFAULT ''",
        "title": "title VARCHAR(250) DEFAULT ''",
        "program_id": "program_id INTEGER",
        "program_visit_id": "program_visit_id INTEGER",
        "silne_stranky": "silne_stranky TEXT DEFAULT '' NOT NULL",
        "methodology_source": "methodology_source VARCHAR(30)",
        "questions_frozen_at": "questions_frozen_at DATETIME",
        "methodology_generation": "methodology_generation VARCHAR(80)",
        "changes_since_last": "changes_since_last TEXT",
        "conclusion_text": "conclusion_text TEXT",
        "lead_auditor_recommendation": "lead_auditor_recommendation TEXT",
        "lead_auditor_recommendation_results_signature": (
            "lead_auditor_recommendation_results_signature VARCHAR(64)"
        ),
        "support_snapshot_count": "support_snapshot_count INTEGER",
        "support_integrity_hash": "support_integrity_hash VARCHAR(64)",
        "created_at": "created_at DATETIME",
        "updated_at": "updated_at DATETIME",
    }
    for column_name, column_sql in additions.items():
        if column_name not in columns:
            _add_column("audits", column_sql)
    _ensure_index(
        "ix_audits_workplace_id",
        "CREATE INDEX IF NOT EXISTS ix_audits_workplace_id ON audits (workplace_id)",
    )


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
                        modified BOOLEAN DEFAULT 0,
                        active BOOLEAN DEFAULT 1,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                    """
                )
            )
            has_modified = "modified" in event_columns
            if has_modified:
                connection.execute(
                    text(
                        """
                        INSERT INTO hazard_events_new (
                            id,
                            inventory_item_id,
                            name,
                            description,
                            note,
                            modified,
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
                            COALESCE(modified, 0),
                            active,
                            sort_order,
                            created_at,
                            updated_at
                        FROM hazard_events
                        """
                    )
                )
            else:
                connection.execute(
                    text(
                        """
                        INSERT INTO hazard_events_new (
                            id,
                            inventory_item_id,
                            name,
                            description,
                            note,
                            modified,
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
                            0,
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

    # R12 rebuild historicky vynechával sloupec modified – doplnit vždy.
    event_columns = _table_columns("hazard_events")
    if event_columns and "modified" not in event_columns:
        _add_column("hazard_events", "modified BOOLEAN DEFAULT 0")

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


def _migrate_exposed_target_source_type_columns() -> None:
    """RISK-UX-6: source_type na vazebních tabulkách ohrožených skupin."""
    for table_name in (
        "hazard_risk_assessment_exposed_groups",
        "hazard_library_template_assessment_exposed_groups",
    ):
        columns = _table_columns(table_name)
        if not columns:
            continue
        if "source_type" not in columns:
            _add_column(
                table_name,
                "source_type VARCHAR(32) NOT NULL DEFAULT 'hazard_group'",
            )
        with _db_engine().connect() as connection:
            connection.execute(
                text(
                    f"""
                    UPDATE {table_name}
                    SET source_type = 'hazard_group'
                    WHERE source_type IS NULL OR TRIM(source_type) = ''
                    """
                ),
            )
            connection.commit()


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


def _ensure_hazard_existing_measure_exposed_groups_table() -> None:
    columns = _table_columns("hazard_existing_measure_exposed_groups")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_existing_measure_exposed_group import (
            HazardExistingMeasureExposedGroup,
        )

        HazardExistingMeasureExposedGroup.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )
    _ensure_index(
        "idx_hazard_existing_measure_groups_measure",
        """
        CREATE INDEX IF NOT EXISTS idx_hazard_existing_measure_groups_measure
        ON hazard_existing_measure_exposed_groups (measure_id)
        """,
    )
    _ensure_index(
        "idx_hazard_existing_measure_groups_unique",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hazard_existing_measure_groups_unique
        ON hazard_existing_measure_exposed_groups (
            measure_id, source_type, exposed_group_id
        )
        """,
    )


def _ensure_hazard_required_measures_table() -> None:
    columns = _table_columns("hazard_required_measures")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure

        HazardRequiredMeasure.__table__.create(bind=_db_engine(), checkfirst=True)
        return
    if "modified" not in columns:
        _add_column("hazard_required_measures", "modified BOOLEAN DEFAULT 0")
    if "title" not in columns:
        _add_column("hazard_required_measures", "title TEXT DEFAULT ''")
        with _db_engine().connect() as connection:
            # RISK-REVIEW-2: dřívější description = Název → title (description ponecháme)
            connection.execute(
                text(
                    "UPDATE hazard_required_measures "
                    "SET title = description "
                    "WHERE title IS NULL OR TRIM(title) = ''"
                )
            )
            connection.commit()


def _ensure_risk_measure_reviews_table() -> None:
    columns = _table_columns("risk_measure_reviews")
    if not columns:
        from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview

        RiskMeasureReview.__table__.create(bind=_db_engine(), checkfirst=True)


def _ensure_risk_measure_review_items_table() -> None:
    columns = _table_columns("risk_measure_review_items")
    if not columns:
        from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem

        RiskMeasureReviewItem.__table__.create(bind=_db_engine(), checkfirst=True)
        return

    if "compliant" not in columns:
        _add_column("risk_measure_review_items", "compliant BOOLEAN DEFAULT 0")
        with _db_engine().connect() as connection:
            connection.execute(
                text(
                    "UPDATE risk_measure_review_items "
                    "SET compliant = 1 WHERE result = 'compliant'"
                )
            )
            connection.commit()
    if "note_number" not in columns:
        _add_column("risk_measure_review_items", "note_number VARCHAR(16) DEFAULT ''")
    if "has_photo" not in columns:
        _add_column("risk_measure_review_items", "has_photo BOOLEAN DEFAULT 0")
    if "resolution" not in columns:
        _add_column(
            "risk_measure_review_items",
            "resolution VARCHAR(32) NOT NULL DEFAULT ''",
        )


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


def _ensure_hazard_library_template_existing_measure_exposed_groups_table() -> None:
    columns = _table_columns("hazard_library_template_existing_measure_exposed_groups")
    if not columns:
        from moduly.rizeni_rizik.modely.hazard_library_template_existing_measure_exposed_group import (
            HazardLibraryTemplateExistingMeasureExposedGroup,
        )

        HazardLibraryTemplateExistingMeasureExposedGroup.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )
    _ensure_index(
        "idx_hazard_library_existing_measure_groups_measure",
        """
        CREATE INDEX IF NOT EXISTS idx_hazard_library_existing_measure_groups_measure
        ON hazard_library_template_existing_measure_exposed_groups (measure_id)
        """,
    )
    _ensure_index(
        "idx_hazard_library_existing_measure_groups_unique",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_hazard_library_existing_measure_groups_unique
        ON hazard_library_template_existing_measure_exposed_groups (
            measure_id, source_type, exposed_group_id
        )
        """,
    )


EXISTING_MEASURE_RELEVANCE_MIGRATION = "existing_measure_relevance_v1"


def _ensure_data_migration_flags_table() -> None:
    if _table_exists("data_migration_flags"):
        return
    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS data_migration_flags (
                    name VARCHAR(100) NOT NULL PRIMARY KEY,
                    applied_at DATETIME NOT NULL
                )
                """
            )
        )
        connection.commit()


def _data_migration_applied(name: str) -> bool:
    _ensure_data_migration_flags_table()
    with _db_engine().connect() as connection:
        row = connection.execute(
            text("SELECT 1 FROM data_migration_flags WHERE name = :name"),
            {"name": name},
        ).fetchone()
    return row is not None


def _mark_data_migration_applied(name: str) -> None:
    _ensure_data_migration_flags_table()
    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                INSERT OR IGNORE INTO data_migration_flags (name, applied_at)
                VALUES (:name, :applied_at)
                """
            ),
            {"name": name, "applied_at": datetime.now()},
        )
        connection.commit()


def _run_existing_measure_relevance_backfill_once() -> dict[str, int]:
    """Jednorázová migrace – prázdná relevance po odebrání skupiny se znovu nedoplňuje."""
    if _data_migration_applied(EXISTING_MEASURE_RELEVANCE_MIGRATION):
        LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL["instance"] = 0
        LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL["catalog"] = 0
        return dict(LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL)
    counts = _backfill_existing_measure_relevance()
    _mark_data_migration_applied(EXISTING_MEASURE_RELEVANCE_MIGRATION)
    return counts


def _backfill_existing_measure_relevance() -> dict[str, int]:
    """Doplní relevanci zásad na všechny skupiny posouzení. Idempotentní.

    Zásada bez jakékoli vazby dostane všechny aktuální skupiny/role
    nadřazeného posouzení. Zásada, která už vazby má, se nemění.
    """
    instance_count = 0
    catalog_count = 0
    if _table_exists("hazard_existing_measures") and _table_exists(
        "hazard_existing_measure_exposed_groups"
    ):
        with _db_engine().connect() as connection:
            result = connection.execute(
                text(
                    """
                    INSERT INTO hazard_existing_measure_exposed_groups (
                        measure_id,
                        exposed_group_id,
                        source_type,
                        sort_order
                    )
                    SELECT
                        m.id,
                        g.exposed_group_id,
                        COALESCE(NULLIF(TRIM(g.source_type), ''), 'hazard_group'),
                        g.sort_order
                    FROM hazard_existing_measures AS m
                    JOIN hazard_risk_assessment_exposed_groups AS g
                      ON g.assessment_id = m.hazard_risk_assessment_id
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM hazard_existing_measure_exposed_groups AS r
                        WHERE r.measure_id = m.id
                    )
                    """
                )
            )
            instance_count = int(result.rowcount or 0)
            connection.commit()

    if _table_exists("hazard_library_template_existing_measures") and _table_exists(
        "hazard_library_template_existing_measure_exposed_groups"
    ):
        with _db_engine().connect() as connection:
            result = connection.execute(
                text(
                    """
                    INSERT INTO hazard_library_template_existing_measure_exposed_groups (
                        measure_id,
                        exposed_group_id,
                        source_type,
                        sort_order
                    )
                    SELECT
                        m.id,
                        g.exposed_group_id,
                        COALESCE(NULLIF(TRIM(g.source_type), ''), 'hazard_group'),
                        g.sort_order
                    FROM hazard_library_template_existing_measures AS m
                    JOIN hazard_library_template_assessment_exposed_groups AS g
                      ON g.assessment_id = m.template_assessment_id
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM hazard_library_template_existing_measure_exposed_groups AS r
                        WHERE r.measure_id = m.id
                    )
                    """
                )
            )
            catalog_count = int(result.rowcount or 0)
            connection.commit()

    LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL["instance"] = instance_count
    LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL["catalog"] = catalog_count
    return dict(LAST_EXISTING_MEASURE_RELEVANCE_BACKFILL)


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


def _ensure_professions_tables() -> None:
    profession_columns = _table_columns("professions")
    if not profession_columns:
        from moduly.rizeni_rizik.modely.profession import Profession

        Profession.__table__.create(bind=_db_engine(), checkfirst=True)

    link_columns = _table_columns("profession_exposed_groups")
    if not link_columns:
        from moduly.rizeni_rizik.modely.profession_exposed_group import (
            ProfessionExposedGroup,
        )

        ProfessionExposedGroup.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_profession_exposed_groups_profession",
        """
        CREATE INDEX IF NOT EXISTS idx_profession_exposed_groups_profession
        ON profession_exposed_groups (profession_id)
        """,
    )
    _ensure_index(
        "idx_profession_exposed_groups_group",
        """
        CREATE INDEX IF NOT EXISTS idx_profession_exposed_groups_group
        ON profession_exposed_groups (exposed_group_id)
        """,
    )


def _ensure_pravidla_bezpecne_prace_editions_tables() -> None:
    edition_columns = _table_columns("pravidla_bezpecne_prace_editions")
    if not edition_columns:
        from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
            PravidlaBezpecnePraceEdition,
            PravidlaBezpecnePraceEditionRule,
        )

        PravidlaBezpecnePraceEdition.__table__.create(bind=_db_engine(), checkfirst=True)
        PravidlaBezpecnePraceEditionRule.__table__.create(bind=_db_engine(), checkfirst=True)
    elif "profession_id" not in edition_columns:
        _add_column("pravidla_bezpecne_prace_editions", "profession_id INTEGER")

    rule_columns = _table_columns("pravidla_bezpecne_prace_edition_rules")
    if not rule_columns:
        from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
            PravidlaBezpecnePraceEditionRule,
        )

        PravidlaBezpecnePraceEditionRule.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_pbp_editions_scope_issued",
        """
        CREATE INDEX IF NOT EXISTS idx_pbp_editions_scope_issued
        ON pravidla_bezpecne_prace_editions (
            endangered_group_id,
            operation_id,
            workplace_id,
            workplace_part_id,
            issued_at
        )
        """,
    )
    _ensure_index(
        "idx_pbp_editions_profession_scope_issued",
        """
        CREATE INDEX IF NOT EXISTS idx_pbp_editions_profession_scope_issued
        ON pravidla_bezpecne_prace_editions (
            profession_id,
            operation_id,
            workplace_id,
            workplace_part_id,
            issued_at
        )
        """,
    )


def _ensure_pbp_validation_approvals_table() -> None:
    columns = _table_columns("pbp_validation_approvals")
    if not columns:
        from moduly.rizeni_rizik.modely.pbp_validation_approval import (
            PbpValidationApproval,
        )

        PbpValidationApproval.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_pbp_validation_approvals_measure",
        """
        CREATE INDEX IF NOT EXISTS idx_pbp_validation_approvals_measure
        ON pbp_validation_approvals (measure_id)
        """,
    )


def _ensure_bozp_coordinations_table() -> None:
    columns = _table_columns("bozp_coordinations")
    if not columns:
        from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination

        BozpCoordination.__table__.create(bind=_db_engine(), checkfirst=True)
        columns = _table_columns("bozp_coordinations")

    if "valid_from" not in columns:
        _add_column("bozp_coordinations", "valid_from DATE")
    if "valid_to" not in columns:
        _add_column("bozp_coordinations", "valid_to DATE")
    if "emergency_reporting" not in columns:
        _add_column("bozp_coordinations", "emergency_reporting TEXT DEFAULT ''")
    if "accident_reporting" not in columns:
        _add_column("bozp_coordinations", "accident_reporting TEXT DEFAULT ''")
    if "fire_reporting" not in columns:
        _add_column("bozp_coordinations", "fire_reporting TEXT DEFAULT ''")
    if "evacuation_instructions" not in columns:
        _add_column(
            "bozp_coordinations",
            "evacuation_instructions TEXT DEFAULT ''",
        )
    if "work_intent_information_text" not in columns:
        _add_column(
            "bozp_coordinations",
            "work_intent_information_text TEXT DEFAULT ''",
        )
    if "ppe_text" not in columns:
        _add_column("bozp_coordinations", "ppe_text TEXT DEFAULT ''")
    if "workplace_handover_text" not in columns:
        _add_column(
            "bozp_coordinations",
            "workplace_handover_text TEXT DEFAULT ''",
        )
    if "final_provisions_text" not in columns:
        _add_column(
            "bozp_coordinations",
            "final_provisions_text TEXT DEFAULT ''",
        )
    if "ready_at" not in columns:
        _add_column("bozp_coordinations", "ready_at DATETIME")
    if "issued_at" not in columns:
        _add_column("bozp_coordinations", "issued_at DATETIME")
    if "completed_at" not in columns:
        _add_column("bozp_coordinations", "completed_at DATETIME")
    if "archived_at" not in columns:
        _add_column("bozp_coordinations", "archived_at DATETIME")

    # COORDINATION-UX-1: mapování legacy stavů na Rozpracováno / Uzavřeno.
    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                UPDATE bozp_coordinations
                SET status = 'draft'
                WHERE lower(trim(coalesce(status, ''))) IN (
                    'draft', 'in_progress', ''
                )
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE bozp_coordinations
                SET status = 'closed'
                WHERE lower(trim(coalesce(status, ''))) IN (
                    'ready', 'prepared', 'active',
                    'issued', 'published',
                    'completed', 'done',
                    'archived', 'closed'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE bozp_coordinations
                SET status = 'draft'
                WHERE lower(trim(coalesce(status, ''))) NOT IN (
                    'draft', 'closed'
                )
                """
            )
        )
        connection.commit()

    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                UPDATE bozp_coordinations
                SET valid_from = meeting_date
                WHERE valid_from IS NULL
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE bozp_coordinations
                SET valid_to = date(meeting_date, '+1 year')
                WHERE valid_to IS NULL
                """
            )
        )
        connection.commit()

    _ensure_index(
        "idx_bozp_coordinations_number",
        """
        CREATE INDEX IF NOT EXISTS idx_bozp_coordinations_number
        ON bozp_coordinations (coordination_number)
        """,
    )
    _ensure_index(
        "idx_bozp_coordinations_meeting_date",
        """
        CREATE INDEX IF NOT EXISTS idx_bozp_coordinations_meeting_date
        ON bozp_coordinations (meeting_date)
        """,
    )
    _ensure_index(
        "idx_bozp_coordinations_valid_to",
        """
        CREATE INDEX IF NOT EXISTS idx_bozp_coordinations_valid_to
        ON bozp_coordinations (valid_to)
        """,
    )

    employer_columns = _table_columns("coordination_employers")
    if not employer_columns:
        from moduly.koordinace_bozp.modely.coordination_employer import (
            CoordinationEmployer,
        )

        CoordinationEmployer.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_coordination_employers_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_employers_coordination
        ON coordination_employers (coordination_id)
        """,
    )

    participant_columns = _table_columns("coordination_participants")
    if not participant_columns:
        from moduly.koordinace_bozp.modely.coordination_participant import (
            CoordinationParticipant,
        )

        CoordinationParticipant.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_coordination_participants_employer",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_participants_employer
        ON coordination_participants (coordination_employer_id)
        """,
    )

    coordinator_columns = _table_columns("coordination_coordinators")
    if not coordinator_columns:
        from moduly.koordinace_bozp.modely.coordination_coordinator import (
            CoordinationCoordinator,
        )

        CoordinationCoordinator.__table__.create(bind=_db_engine(), checkfirst=True)
    else:
        _migrate_coordination_coordinators_snapshot_ux_coord_2()

    _ensure_index(
        "idx_coordination_coordinators_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_coordinators_coordination
        ON coordination_coordinators (coordination_id)
        """,
    )

    workplace_link_columns = _table_columns("coordination_workplaces")
    if not workplace_link_columns:
        from moduly.koordinace_bozp.modely.coordination_workplace import (
            CoordinationWorkplace,
        )

        CoordinationWorkplace.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_coordination_workplaces_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_workplaces_coordination
        ON coordination_workplaces (coordination_id)
        """,
    )

    activity_columns = _table_columns("coordination_employer_activities")
    if not activity_columns:
        from moduly.koordinace_bozp.modely.coordination_employer_activity import (
            CoordinationEmployerActivity,
        )

        CoordinationEmployerActivity.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_coordination_employer_activities_employer",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_employer_activities_employer
        ON coordination_employer_activities (coordination_employer_id)
        """,
    )
    _ensure_index(
        "idx_coordination_employer_activities_workplace",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_employer_activities_workplace
        ON coordination_employer_activities (coordination_workplace_id)
        """,
    )

    measure_columns = _table_columns("coordination_measures")
    if not measure_columns:
        from moduly.koordinace_bozp.modely.coordination_measure import (
            CoordinationMeasure,
        )

        CoordinationMeasure.__table__.create(bind=_db_engine(), checkfirst=True)
        measure_columns = _table_columns("coordination_measures")
    if measure_columns and "template_code" not in measure_columns:
        _add_column("coordination_measures", "template_code VARCHAR(64)")

    _ensure_index(
        "idx_coordination_measures_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_measures_coordination
        ON coordination_measures (coordination_id)
        """,
    )
    _ensure_index(
        "idx_coordination_measures_template",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_coordination_measures_template
        ON coordination_measures (coordination_id, template_code)
        WHERE template_code IS NOT NULL AND template_code != ''
        """,
    )

    contact_columns = _table_columns("coordination_contacts")
    if not contact_columns:
        from moduly.koordinace_bozp.modely.coordination_contact import (
            CoordinationContact,
        )

        CoordinationContact.__table__.create(bind=_db_engine(), checkfirst=True)
    else:
        _migrate_coordination_contacts_employer_ux_coord_12d()

    _ensure_index(
        "idx_coordination_contacts_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_contacts_coordination
        ON coordination_contacts (coordination_id)
        """,
    )
    _ensure_index(
        "idx_coordination_contacts_participant",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_contacts_participant
        ON coordination_contacts (participant_id)
        """,
    )
    _ensure_index(
        "idx_coordination_contacts_employer",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_contacts_employer
        ON coordination_contacts (employer_id)
        """,
    )

    risk_submission_columns = _table_columns("coordination_employer_risk_submissions")
    if not risk_submission_columns:
        from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
            CoordinationEmployerRiskSubmission,
            CoordinationRiskSubmissionHistory,
        )

        CoordinationEmployerRiskSubmission.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )
        CoordinationRiskSubmissionHistory.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )
    else:
        _migrate_coordination_risk_submissions_ux_coord_13()

    history_columns = _table_columns("coordination_risk_submission_history")
    if not history_columns:
        from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
            CoordinationRiskSubmissionHistory,
        )

        CoordinationRiskSubmissionHistory.__table__.create(
            bind=_db_engine(),
            checkfirst=True,
        )

    _ensure_index(
        "idx_coordination_employer_risk_submissions_employer",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_employer_risk_submissions_employer
        ON coordination_employer_risk_submissions (coordination_employer_id)
        """,
    )
    _ensure_index(
        "idx_coordination_risk_submission_history_submission",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_risk_submission_history_submission
        ON coordination_risk_submission_history (submission_id)
        """,
    )

    attachment_columns = _table_columns("coordination_attachments")
    if not attachment_columns:
        from moduly.koordinace_bozp.modely.coordination_attachment import (
            CoordinationAttachment,
        )

        CoordinationAttachment.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_coordination_attachments_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_attachments_coordination
        ON coordination_attachments (coordination_id)
        """,
    )
    _ensure_index(
        "idx_coordination_attachments_employer",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_attachments_employer
        ON coordination_attachments (coordination_employer_id)
        """,
    )

    pbp_revision_columns = _table_columns("coordination_pbp_revisions")
    if not pbp_revision_columns:
        from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
            CoordinationPbpRevision,
        )

        CoordinationPbpRevision.__table__.create(bind=_db_engine(), checkfirst=True)

    _ensure_index(
        "idx_coordination_pbp_revisions_coordination",
        """
        CREATE INDEX IF NOT EXISTS idx_coordination_pbp_revisions_coordination
        ON coordination_pbp_revisions (coordination_id)
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


def _migrate_coordination_risk_submissions_ux_coord_13() -> None:
    """UX-COORD-13: stavy předání, nová pole a remap starých způsobů."""
    columns = _table_columns("coordination_employer_risk_submissions")
    if not columns:
        return
    if "expected_email" not in columns:
        _add_column(
            "coordination_employer_risk_submissions",
            "expected_email VARCHAR(150) DEFAULT ''",
        )
    if "risks_text" not in columns:
        _add_column(
            "coordination_employer_risk_submissions",
            "risks_text TEXT DEFAULT ''",
        )
    if "task_id" not in columns:
        _add_column(
            "coordination_employer_risk_submissions",
            "task_id INTEGER",
        )

    # Remap legacy technical methods → process statuses.
    remap = {
        "not_submitted": "will_send_email",
        "attachment": "stated_at_meeting",
        "email": "email_before_meeting",
        "paper": "will_submit_paper",
        "data_box": "submitted_earlier",
        "other": "submitted_earlier",
    }
    with _db_engine().connect() as connection:
        for old, new in remap.items():
            connection.execute(
                text(
                    """
                    UPDATE coordination_employer_risk_submissions
                    SET submission_method = :new
                    WHERE submission_method = :old
                    """
                ),
                {"old": old, "new": new},
            )
        connection.commit()


def _migrate_coordination_contacts_employer_ux_coord_12d() -> None:
    """UX-COORD-12d: vazba kontaktu na zaměstnavatele + snapshot názvu."""
    columns = _table_columns("coordination_contacts")
    if not columns:
        return
    if "employer_id" not in columns:
        _add_column(
            "coordination_contacts",
            "employer_id INTEGER",
        )
    if "employer_name" not in columns:
        _add_column(
            "coordination_contacts",
            "employer_name VARCHAR(250) DEFAULT ''",
        )


def _migrate_coordination_coordinators_snapshot_ux_coord_2() -> None:
    """UX-COORD-2: snapshot údajů koordinátora + nullable participant/employer."""
    columns = _table_columns("coordination_coordinators")
    if not columns:
        return

    if "full_name" not in columns:
        _add_column(
            "coordination_coordinators",
            "full_name VARCHAR(250) DEFAULT ''",
        )
    if "employer_name" not in columns:
        _add_column(
            "coordination_coordinators",
            "employer_name VARCHAR(250) DEFAULT ''",
        )
    if "role" not in columns:
        _add_column(
            "coordination_coordinators",
            "role VARCHAR(150) DEFAULT ''",
        )
    if "phone" not in columns:
        _add_column(
            "coordination_coordinators",
            "phone VARCHAR(50) DEFAULT ''",
        )
    if "email" not in columns:
        _add_column(
            "coordination_coordinators",
            "email VARCHAR(150) DEFAULT ''",
        )

    with _db_engine().connect() as connection:
        connection.execute(
            text(
                """
                UPDATE coordination_coordinators
                SET
                    full_name = COALESCE(
                        NULLIF(TRIM(full_name), ''),
                        (
                            SELECT COALESCE(p.full_name, '')
                            FROM coordination_participants p
                            WHERE p.id = coordination_coordinators.participant_id
                        ),
                        ''
                    ),
                    role = COALESCE(
                        NULLIF(TRIM(role), ''),
                        (
                            SELECT COALESCE(p.role, '')
                            FROM coordination_participants p
                            WHERE p.id = coordination_coordinators.participant_id
                        ),
                        ''
                    ),
                    phone = COALESCE(
                        NULLIF(TRIM(phone), ''),
                        (
                            SELECT COALESCE(p.phone, '')
                            FROM coordination_participants p
                            WHERE p.id = coordination_coordinators.participant_id
                        ),
                        ''
                    ),
                    email = COALESCE(
                        NULLIF(TRIM(email), ''),
                        (
                            SELECT COALESCE(p.email, '')
                            FROM coordination_participants p
                            WHERE p.id = coordination_coordinators.participant_id
                        ),
                        ''
                    ),
                    employer_name = COALESCE(
                        NULLIF(TRIM(employer_name), ''),
                        (
                            SELECT COALESCE(e.company_name, '')
                            FROM coordination_employers e
                            WHERE e.id = coordination_coordinators.employer_id
                        ),
                        ''
                    )
                WHERE
                    participant_id IS NOT NULL
                    OR employer_id IS NOT NULL
                """
            ),
        )
        connection.commit()

        create_sql = connection.execute(
            text(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'coordination_coordinators'"
            ),
        ).scalar()
        if not create_sql:
            return
        normalized = " ".join(str(create_sql).upper().split())
        needs_rebuild = (
            "PARTICIPANT_ID INTEGER NOT NULL" in normalized
            or "EMPLOYER_ID INTEGER NOT NULL" in normalized
        )
        if not needs_rebuild:
            return

        connection.execute(
            text(
                """
                CREATE TABLE coordination_coordinators_ux2 (
                    id INTEGER NOT NULL PRIMARY KEY,
                    coordination_id INTEGER NOT NULL,
                    employer_id INTEGER,
                    participant_id INTEGER,
                    full_name VARCHAR(250) NOT NULL DEFAULT '',
                    employer_name VARCHAR(250) DEFAULT '',
                    role VARCHAR(150) DEFAULT '',
                    phone VARCHAR(50) DEFAULT '',
                    email VARCHAR(150) DEFAULT '',
                    note TEXT DEFAULT '',
                    active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME,
                    FOREIGN KEY(coordination_id) REFERENCES bozp_coordinations (id)
                        ON DELETE CASCADE,
                    FOREIGN KEY(employer_id) REFERENCES coordination_employers (id)
                        ON DELETE SET NULL,
                    FOREIGN KEY(participant_id) REFERENCES coordination_participants (id)
                        ON DELETE SET NULL
                )
                """
            ),
        )
        connection.execute(
            text(
                """
                INSERT INTO coordination_coordinators_ux2 (
                    id,
                    coordination_id,
                    employer_id,
                    participant_id,
                    full_name,
                    employer_name,
                    role,
                    phone,
                    email,
                    note,
                    active,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    coordination_id,
                    employer_id,
                    participant_id,
                    COALESCE(full_name, ''),
                    COALESCE(employer_name, ''),
                    COALESCE(role, ''),
                    COALESCE(phone, ''),
                    COALESCE(email, ''),
                    COALESCE(note, ''),
                    COALESCE(active, 1),
                    created_at,
                    updated_at
                FROM coordination_coordinators
                """
            ),
        )
        connection.execute(text("DROP TABLE coordination_coordinators"))
        connection.execute(
            text(
                "ALTER TABLE coordination_coordinators_ux2 "
                "RENAME TO coordination_coordinators"
            ),
        )
        connection.commit()


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
    if "new_legal_document_version_id" not in columns:
        _add_column("legal_changes", "new_legal_document_version_id INTEGER")
    if "evaluation_note" not in columns:
        _add_column("legal_changes", 'evaluation_note TEXT DEFAULT ""')


LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX = (
    "uq_legal_document_versions_document_source_eli"
)


def _ensure_legal_document_version_columns() -> None:
    columns = _table_columns("legal_document_versions")
    if not columns:
        return
    if "pending_adoption" not in columns:
        _add_column("legal_document_versions", "pending_adoption BOOLEAN DEFAULT 0")
    if "source_eli" not in columns:
        _add_column("legal_document_versions", "source_eli VARCHAR(255)")
    if "future_wording" not in columns:
        _add_column("legal_document_versions", "future_wording BOOLEAN DEFAULT 0")
    _ensure_legal_document_version_source_eli_unique_index()


def _ensure_legal_document_version_source_eli_unique_index() -> None:
    columns = _table_columns("legal_document_versions")
    if not columns or "source_eli" not in columns:
        return
    if LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX in _table_indexes(
        "legal_document_versions"
    ):
        return
    _ensure_index(
        LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX,
        (
            f"CREATE UNIQUE INDEX {LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX} "
            "ON legal_document_versions (legal_document_id, source_eli)"
        ),
    )


def _ensure_legal_change_sections_table() -> None:
    columns = _table_columns("legal_change_sections")
    if not columns:
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection

        LegalChangeSection.__table__.create(bind=_db_engine(), checkfirst=True)
        columns = _table_columns("legal_change_sections")
    if not columns:
        return
    if "old_text" not in columns:
        _add_column("legal_change_sections", "old_text TEXT")
    if "new_text" not in columns:
        _add_column("legal_change_sections", "new_text TEXT")


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


def _normalize_meeting_status_values() -> None:
    """AGENDA-EVENT-UX-7: historické Proběhlo → Uzavřeno."""
    columns = _table_columns("meetings")
    if "status" not in columns:
        return
    with _db_engine().connect() as connection:
        connection.execute(
            text("UPDATE meetings SET status = :closed WHERE status = :held"),
            {"closed": "Uzavřeno", "held": "Proběhlo"},
        )
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
