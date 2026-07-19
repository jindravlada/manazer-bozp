"""Sestavení datového modelu koordinačního protokolu (COORD-011a).

Náhled je read-only: neukládá data a nevytváří PBP revize.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from moduly.koordinace_bozp.constants import (
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    ATTACHMENT_TYPE_LABELS,
    ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
    ATTACHMENT_TYPE_OTHER,
    BOZP_COORDINATION_STATUS_ARCHIVED,
    BOZP_COORDINATION_STATUS_LABELS,
    CONTACT_TYPE_LABELS,
    MEASURE_CATEGORIES,
    MEASURE_CATEGORY_LABELS,
    PBP_FRESHNESS_NEEDS_UPDATE,
    PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY,
    PROTOCOL_WARNING_EXPIRED_VALIDITY,
    PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED,
    PROTOCOL_WARNING_MISSING_COORDINATOR,
    PROTOCOL_WARNING_MISSING_MEASURES,
    PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT,
    PROTOCOL_WARNING_MISSING_WORKPLACE,
    PROTOCOL_WARNING_RISKS_NOT_SUBMITTED,
    PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
    PROTOCOL_WARNING_SEVERITY_CRITICAL,
    PROTOCOL_WARNING_SEVERITY_INFO,
    PROTOCOL_WARNING_SEVERITY_WARNING,
    PROTOCOL_WARNING_STALE_PBP_SNAPSHOT,
    RISK_HANDOVER_STATUS_LABELS,
    RISK_HANDOVER_STATUS_MAIN,
    RISK_HANDOVER_STATUS_NOT_SUBMITTED,
    RISK_HANDOVER_STATUS_WITHOUT_ATTACHMENT,
    VALIDITY_STATE_EXPIRED,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
    coordination_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
    coordination_contact_service,
)
from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
    coordination_coordinator_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
    coordination_employer_activity_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
    coordination_measure_service,
)
from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
    coordination_participant_service,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
    coordination_pbp_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import (
    evaluate_pbp_freshness,
)
from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
    coordination_risk_submission_service,
)
from moduly.koordinace_bozp.sluzby.coordination_validity import (
    coordination_validity_state,
)
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    coordination_workplace_service,
)


class CoordinationProtocolBuilderError(ValueError):
    pass


@dataclass(frozen=True)
class ProtocolWarning:
    code: str
    severity: str
    message: str
    related_entity_type: str | None = None
    related_entity_id: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProtocolSummary:
    active_employers: int = 0
    active_participants: int = 0
    active_workplaces: int = 0
    active_activities: int = 0
    active_measures: int = 0
    active_contacts: int = 0
    pbp_rules_count: int = 0
    active_attachments: int = 0
    warnings_info: int = 0
    warnings_warning: int = 0
    warnings_critical: int = 0

    @property
    def warnings_total(self) -> int:
        return self.warnings_info + self.warnings_warning + self.warnings_critical

    def to_dict(self) -> dict:
        data = asdict(self)
        data["warnings_total"] = self.warnings_total
        return data


@dataclass
class ProtocolBuildResult:
    protocol_data: dict = field(default_factory=dict)
    warnings: list[ProtocolWarning] = field(default_factory=list)
    summary: ProtocolSummary = field(default_factory=ProtocolSummary)

    def to_dict(self) -> dict:
        return {
            "protocol_data": self.protocol_data,
            "warnings": [item.to_dict() for item in self.warnings],
            "summary": self.summary.to_dict(),
        }


class CoordinationProtocolBuilder:
    """Sestaví protocol_data, warnings a summary pro náhled protokolu."""

    def build(
        self,
        coordination_id: int,
        *,
        today: date | None = None,
    ) -> ProtocolBuildResult:
        if not coordination_id:
            raise CoordinationProtocolBuilderError("Koordinace je povinná.")
        coordination = bozp_coordination_service.get_by_id(coordination_id)
        if coordination is None:
            raise CoordinationProtocolBuilderError("Koordinace nebyla nalezena.")

        current = today or date.today()
        employers_all = coordination_employer_service.list_for_coordination(
            coordination_id,
            include_inactive=True,
        )
        employers_active = [item for item in employers_all if item.active]
        employers_sorted = self._sort_employers(employers_active)

        participants_by_employer: list[dict] = []
        active_participants_count = 0
        for employer in employers_sorted:
            participants = [
                item
                for item in coordination_participant_service.list_for_employer(
                    employer.id,
                    include_inactive=False,
                )
            ]
            active_participants_count += len(participants)
            participants_by_employer.append(
                {
                    "employer": self._employer_dict(employer),
                    "participants": [
                        self._participant_dict(item) for item in participants
                    ],
                }
            )

        activities_by_employer: list[dict] = []
        active_activities_count = 0
        for employer in employers_sorted:
            activities = coordination_employer_activity_service.list_for_employer(
                employer.id,
                include_inactive=False,
            )
            active_activities_count += len(activities)
            activities_by_employer.append(
                {
                    "employer": self._employer_dict(employer),
                    "activities": [
                        self._activity_dict(item) for item in activities
                    ],
                }
            )

        workplaces = coordination_workplace_service.list_for_coordination(
            coordination_id,
            include_inactive=False,
        )
        measures = coordination_measure_service.list_for_coordination(
            coordination_id,
            include_inactive=False,
        )
        contacts = coordination_contact_service.list_for_coordination(
            coordination_id,
            include_inactive=False,
        )
        coordinator = coordination_coordinator_service.get_for_coordination(
            coordination_id,
            include_inactive=False,
        )
        pbp_revision = coordination_pbp_attachment_service.get_current(coordination_id)
        attachments = coordination_attachment_service.repository.list_for_coordination(
            coordination_id,
            include_inactive=False,
        )

        risk_rows = []
        for employer in employers_sorted:
            if employer.is_main:
                continue
            status = coordination_risk_submission_service.handover_status(employer.id)
            submission = coordination_risk_submission_service.get_for_employer(
                employer.id
            )
            risk_rows.append(
                {
                    "employer": self._employer_dict(employer),
                    "handover_status": status,
                    "handover_status_label": RISK_HANDOVER_STATUS_LABELS.get(
                        status,
                        status,
                    ),
                    "submission": self._submission_dict(submission),
                }
            )

        protocol_data = {
            "basics": self._basics_dict(coordination, today=current),
            "employers": [self._employer_dict(item) for item in employers_sorted],
            "participants_by_employer": participants_by_employer,
            "coordinator": self._coordinator_dict(coordinator),
            "workplaces": [self._workplace_dict(item) for item in workplaces],
            "activities_by_employer": activities_by_employer,
            "measures_by_category": self._group_measures(measures),
            "contacts": [self._contact_dict(item) for item in contacts],
            "emergency_procedures": {
                "emergency_reporting": coordination.emergency_reporting or "",
                "accident_reporting": coordination.accident_reporting or "",
                "fire_reporting": coordination.fire_reporting or "",
                "evacuation_instructions": coordination.evacuation_instructions or "",
            },
            "risk_handovers": risk_rows,
            "pbp_snapshot": self._pbp_dict(pbp_revision),
            "attachments_by_group": self._group_attachments(
                attachments,
                pbp_revision=pbp_revision,
            ),
        }

        warnings = self._build_warnings(
            coordination=coordination,
            activities_by_employer=activities_by_employer,
            workplaces=workplaces,
            measures=measures,
            coordinator=coordinator,
            pbp_revision=pbp_revision,
            risk_rows=risk_rows,
            today=current,
        )

        summary = ProtocolSummary(
            active_employers=len(employers_sorted),
            active_participants=active_participants_count,
            active_workplaces=len(workplaces),
            active_activities=active_activities_count,
            active_measures=len(measures),
            active_contacts=len(contacts),
            pbp_rules_count=(
                int(pbp_revision.rules_count) if pbp_revision is not None else 0
            ),
            active_attachments=len(attachments)
            + (1 if pbp_revision is not None else 0),
            warnings_info=sum(
                1
                for item in warnings
                if item.severity == PROTOCOL_WARNING_SEVERITY_INFO
            ),
            warnings_warning=sum(
                1
                for item in warnings
                if item.severity == PROTOCOL_WARNING_SEVERITY_WARNING
            ),
            warnings_critical=sum(
                1
                for item in warnings
                if item.severity == PROTOCOL_WARNING_SEVERITY_CRITICAL
            ),
        )
        return ProtocolBuildResult(
            protocol_data=protocol_data,
            warnings=warnings,
            summary=summary,
        )

    def _build_warnings(
        self,
        *,
        coordination,
        activities_by_employer,
        workplaces,
        measures,
        coordinator,
        pbp_revision,
        risk_rows,
        today: date,
    ) -> list[ProtocolWarning]:
        warnings: list[ProtocolWarning] = []

        if not coordination.active or coordination.status == BOZP_COORDINATION_STATUS_ARCHIVED:
            reason = []
            if not coordination.active:
                reason.append("neaktivní")
            if coordination.status == BOZP_COORDINATION_STATUS_ARCHIVED:
                reason.append("archivovaná")
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED,
                    severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                    message=(
                        "Koordinace je "
                        + " a ".join(reason)
                        + " – protokol může být pouze historický."
                    ),
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if (
            coordination_validity_state(coordination.valid_to, today=today)
            == VALIDITY_STATE_EXPIRED
        ):
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_EXPIRED_VALIDITY,
                    severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                    message="Koordinace je po platnosti.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if coordinator is None:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_COORDINATOR,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Není určen koordinátor BOZP.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if not workplaces:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_WORKPLACE,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Není evidováno žádné aktivní místo výkonu práce.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        for group in activities_by_employer:
            employer = group["employer"]
            if not group["activities"]:
                warnings.append(
                    ProtocolWarning(
                        code=PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY,
                        severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                        message=(
                            f"Zaměstnavatel „{employer['display_name']}“ "
                            "nemá evidovanou žádnou aktivní činnost."
                        ),
                        related_entity_type="coordination_employer",
                        related_entity_id=employer["id"],
                    )
                )

        if not measures:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_MEASURES,
                    severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                    message="Nejsou evidována žádná aktivní organizační opatření.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if pbp_revision is None:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT,
                    severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                    message="Příloha PBP (snapshot) dosud nebyla vytvořena.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )
        else:
            freshness = evaluate_pbp_freshness(coordination, today=today)
            if freshness.state == PBP_FRESHNESS_NEEDS_UPDATE:
                warnings.append(
                    ProtocolWarning(
                        code=PROTOCOL_WARNING_STALE_PBP_SNAPSHOT,
                        severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                        message=(
                            "Příloha PBP vyžaduje aktualizaci – neodpovídá "
                            "současným údajům v Registru rizik."
                        ),
                        related_entity_type="coordination_pbp_revision",
                        related_entity_id=pbp_revision.id,
                    )
                )

        for row in risk_rows:
            employer = row["employer"]
            status = row["handover_status"]
            if status == RISK_HANDOVER_STATUS_MAIN:
                continue
            if status == RISK_HANDOVER_STATUS_NOT_SUBMITTED:
                warnings.append(
                    ProtocolWarning(
                        code=PROTOCOL_WARNING_RISKS_NOT_SUBMITTED,
                        severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                        message=(
                            f"Dodavatel „{employer['display_name']}“ "
                            "nepředal informace o rizicích."
                        ),
                        related_entity_type="coordination_employer",
                        related_entity_id=employer["id"],
                    )
                )
            elif status == RISK_HANDOVER_STATUS_WITHOUT_ATTACHMENT:
                warnings.append(
                    ProtocolWarning(
                        code=PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
                        severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                        message=(
                            f"Dodavatel „{employer['display_name']}“ "
                            "předal rizika bez uložené přílohy."
                        ),
                        related_entity_type="coordination_employer",
                        related_entity_id=employer["id"],
                    )
                )

        return warnings

    @staticmethod
    def _sort_employers(employers):
        return sorted(
            employers,
            key=lambda item: (
                0 if item.is_main else 1,
                item.sort_order or 0,
                (item.company_name or "").casefold(),
                item.id,
            ),
        )

    @staticmethod
    def _employer_dict(employer) -> dict:
        name = employer.company_name or employer.abbreviation or f"#{employer.id}"
        display = name
        if employer.abbreviation and employer.abbreviation != name:
            display = f"{employer.abbreviation} – {name}"
        return {
            "id": employer.id,
            "abbreviation": employer.abbreviation or "",
            "company_name": employer.company_name or "",
            "display_name": display,
            "ico": employer.ico or "",
            "is_main": bool(employer.is_main),
            "sort_order": employer.sort_order or 0,
            "active": bool(employer.active),
        }

    @staticmethod
    def _participant_dict(participant) -> dict:
        return {
            "id": participant.id,
            "full_name": participant.full_name or "",
            "role": participant.role or "",
            "phone": participant.phone or "",
            "email": participant.email or "",
            "sort_order": participant.sort_order or 0,
        }

    @staticmethod
    def _activity_dict(activity) -> dict:
        return {
            "id": activity.id,
            "activity_name": activity.activity_name or "",
            "description": activity.description or "",
            "coordination_workplace_id": activity.coordination_workplace_id,
            "planned_from": (
                activity.planned_from.isoformat() if activity.planned_from else None
            ),
            "planned_to": (
                activity.planned_to.isoformat() if activity.planned_to else None
            ),
            "sort_order": activity.sort_order or 0,
            "workplace_label": coordination_employer_activity_service.workplace_label(
                activity.coordination_workplace_id
            ),
        }

    @staticmethod
    def _workplace_dict(workplace) -> dict:
        operation, place, part = coordination_workplace_service.workplace_display_names(
            workplace
        )
        parts = [item for item in (operation, place, part) if item]
        return {
            "id": workplace.id,
            "operation_name": operation,
            "workplace_name": place,
            "workplace_part_name": part,
            "label": " / ".join(parts),
            "note": workplace.note or "",
            "sort_order": workplace.sort_order or 0,
        }

    def _group_measures(self, measures) -> list[dict]:
        by_category: dict[str, list] = {key: [] for key in MEASURE_CATEGORIES}
        for measure in measures:
            category = measure.category if measure.category in by_category else "other"
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(
                {
                    "id": measure.id,
                    "title": measure.title or "",
                    "description": measure.description or "",
                    "category": measure.category,
                    "category_label": MEASURE_CATEGORY_LABELS.get(
                        measure.category,
                        measure.category,
                    ),
                    "sort_order": measure.sort_order or 0,
                }
            )
        result = []
        for category in MEASURE_CATEGORIES:
            items = by_category.get(category) or []
            if not items:
                continue
            items.sort(key=lambda item: (item["sort_order"], item["id"]))
            result.append(
                {
                    "category": category,
                    "category_label": MEASURE_CATEGORY_LABELS.get(category, category),
                    "measures": items,
                }
            )
        return result

    @staticmethod
    def _contact_dict(contact) -> dict:
        return {
            "id": contact.id,
            "contact_type": contact.contact_type,
            "contact_type_label": CONTACT_TYPE_LABELS.get(
                contact.contact_type,
                contact.contact_type,
            ),
            "custom_name": contact.custom_name or "",
            "role": contact.role or "",
            "phone": contact.phone or "",
            "email": contact.email or "",
            "sort_order": contact.sort_order or 0,
        }

    @staticmethod
    def _basics_dict(coordination, *, today: date) -> dict:
        return {
            "id": coordination.id,
            "coordination_number": coordination.coordination_number or "",
            "meeting_date": (
                coordination.meeting_date.isoformat()
                if coordination.meeting_date
                else None
            ),
            "place": coordination.place or "",
            "subject": coordination.subject or "",
            "status": coordination.status,
            "status_label": BOZP_COORDINATION_STATUS_LABELS.get(
                coordination.status,
                coordination.status,
            ),
            "note": coordination.note or "",
            "valid_from": (
                coordination.valid_from.isoformat() if coordination.valid_from else None
            ),
            "valid_to": (
                coordination.valid_to.isoformat() if coordination.valid_to else None
            ),
            "active": bool(coordination.active),
            "validity_state": coordination_validity_state(
                coordination.valid_to,
                today=today,
            ),
        }

    @staticmethod
    def _coordinator_dict(coordinator) -> dict | None:
        if coordinator is None:
            return None
        full_name = getattr(coordinator, "full_name", None) or ""
        role = getattr(coordinator, "role", None) or ""
        phone = getattr(coordinator, "phone", None) or ""
        email = getattr(coordinator, "email", None) or ""
        employer_name = getattr(coordinator, "employer_name", None) or ""

        # Legacy fallback – starší řádky bez snapshotu.
        if not full_name and coordinator.participant_id:
            participant = coordination_participant_service.get_by_id(
                coordinator.participant_id
            )
            if participant is not None:
                full_name = participant.full_name or ""
                role = role or (participant.role or "")
                phone = phone or (participant.phone or "")
                email = email or (participant.email or "")
        if not employer_name and coordinator.employer_id:
            employer = coordination_employer_service.get_by_id(coordinator.employer_id)
            if employer is not None:
                employer_name = employer.company_name or ""

        return {
            "id": coordinator.id,
            "participant_id": coordinator.participant_id,
            "employer_id": coordinator.employer_id,
            "full_name": full_name,
            "role": role,
            "phone": phone,
            "email": email,
            "employer_name": employer_name,
            "note": coordinator.note or "",
        }

    @staticmethod
    def _submission_dict(submission) -> dict | None:
        if submission is None:
            return None
        return {
            "id": submission.id,
            "submission_method": submission.submission_method or "",
            "submission_date": (
                submission.submission_date.isoformat()
                if submission.submission_date
                else None
            ),
            "document_reference": submission.document_reference or "",
            "note": submission.note or "",
        }

    @staticmethod
    def _pbp_dict(revision) -> dict | None:
        if revision is None:
            return None
        return {
            "id": revision.id,
            "revision_number": revision.revision_number,
            "title": revision.title or "",
            "content_hash": revision.content_hash or "",
            "rules_count": revision.rules_count or 0,
            "created_at": (
                revision.created_at.isoformat(sep=" ", timespec="minutes")
                if revision.created_at
                else None
            ),
            "created_by": revision.created_by or "",
            "stored_filename": revision.stored_filename or "",
        }

    def _group_attachments(self, attachments, *, pbp_revision) -> list[dict]:
        groups = {
            ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP: [],
            ATTACHMENT_TYPE_CONTRACTOR_RISKS: [],
            ATTACHMENT_TYPE_OTHER: [],
        }
        if pbp_revision is not None:
            groups[ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP].append(
                {
                    "id": pbp_revision.id,
                    "source": "pbp_revision",
                    "attachment_type": ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
                    "attachment_type_label": ATTACHMENT_TYPE_LABELS[
                        ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP
                    ],
                    "original_filename": pbp_revision.stored_filename or "",
                    "description": pbp_revision.title or "",
                    "rules_count": pbp_revision.rules_count or 0,
                }
            )
        for attachment in attachments:
            item = {
                "id": attachment.id,
                "source": "attachment",
                "attachment_type": attachment.attachment_type,
                "attachment_type_label": ATTACHMENT_TYPE_LABELS.get(
                    attachment.attachment_type,
                    attachment.attachment_type,
                ),
                "original_filename": attachment.original_filename or "",
                "description": attachment.description or "",
                "coordination_employer_id": attachment.coordination_employer_id,
            }
            if attachment.attachment_type == ATTACHMENT_TYPE_CONTRACTOR_RISKS:
                groups[ATTACHMENT_TYPE_CONTRACTOR_RISKS].append(item)
            elif attachment.attachment_type == ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP:
                groups[ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP].append(item)
            else:
                groups[ATTACHMENT_TYPE_OTHER].append(item)

        result = []
        for type_id in (
            ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
            ATTACHMENT_TYPE_CONTRACTOR_RISKS,
            ATTACHMENT_TYPE_OTHER,
        ):
            items = groups[type_id]
            if not items:
                continue
            result.append(
                {
                    "attachment_type": type_id,
                    "attachment_type_label": ATTACHMENT_TYPE_LABELS.get(
                        type_id,
                        type_id,
                    ),
                    "attachments": items,
                }
            )
        return result


coordination_protocol_builder = CoordinationProtocolBuilder()
