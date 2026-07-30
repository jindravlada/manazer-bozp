"""Sestavení datového modelu koordinačního protokolu (COORD-011a).

Náhled je read-only: neukládá data a nevytváří PBP revize.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Mapping

from moduly.koordinace_bozp.constants import (
    AGREEMENT_PART_CONTACTS,
    AGREEMENT_PART_COORDINATOR,
    AGREEMENT_PART_EMERGENCIES,
    AGREEMENT_PART_FINAL,
    AGREEMENT_PART_MUTUAL_RISKS,
    AGREEMENT_PART_PPE,
    AGREEMENT_PART_WORK_INTENT,
    AGREEMENT_PART_WORKPLACE_HANDOVER,
    ATTACHMENT_TYPE_CONTRACTOR_RISKS,
    ATTACHMENT_TYPE_LABELS,
    ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
    ATTACHMENT_TYPE_OTHER,
    CONTACT_TYPES,
    CONTACT_TYPE_LABELS,
    COORDINATION_PBP_INFO_TEXT,
    COORDINATION_PBP_INTRO_TEXT,
    MEASURE_CATEGORIES,
    MEASURE_CATEGORY_LABELS,
    PBP_FRESHNESS_NEEDS_UPDATE,
    PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY,
    PROTOCOL_WARNING_EXPIRED_VALIDITY,
    PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED,
    PROTOCOL_WARNING_MISSING_ACTIVE_EMPLOYER,
    PROTOCOL_WARNING_MISSING_COORDINATOR,
    PROTOCOL_WARNING_MISSING_MEASURES,
    PROTOCOL_WARNING_MISSING_MEETING_DATE,
    PROTOCOL_WARNING_MISSING_MEETING_PLACE,
    PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT,
    PROTOCOL_WARNING_MISSING_SUBJECT,
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
    RISK_HANDOVER_STATUS_UNSET,
    RISK_SUBMISSION_COMPLETED_STATUSES,
    RISK_SUBMISSION_PENDING_STATUSES,
    RISK_SUBMISSION_STATUS_LABELS,
    RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
    VALIDITY_STATE_EXPIRED,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
    coordination_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    default_abbreviation,
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
from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
    ProtocolDocumentBlock,
    build_protocol_document,
    document_blocks_from_dict,
    render_blocks_to_plain_lines,
)
from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
    CONTACT_EMPLOYER_UNSPECIFIED,
)


class CoordinationProtocolBuilderError(ValueError):
    pass


def protocol_measure_display_text(measure: Mapping[str, Any] | dict) -> str:
    """Text opatření pro náhled/ODT: Popis, jinak Název (UX-COORD-4a)."""
    description = (measure.get("description") or "").strip()
    if description:
        return description
    return (measure.get("title") or "").strip() or "—"


def flatten_protocol_measure_bullets(
    measures_by_category: list | None,
) -> list[str]:
    """Odrážky opatření v pořadí kategorií / sort_order – bez nadpisů kategorií."""
    lines: list[str] = []
    for group in measures_by_category or []:
        for measure in group.get("measures") or []:
            text = protocol_measure_display_text(measure)
            if text and text != "—":
                lines.append(f"• {text}")
    return lines


def _nonempty_text_lines(text: str | None) -> list[str]:
    value = (text or "").strip()
    if not value:
        return []
    return [value]


def _agreement_risk_lines(risk_rows: list | None) -> list[str]:
    lines: list[str] = []
    for row in risk_rows or []:
        employer = row.get("employer") or {}
        name = (employer.get("display_name") or "").strip()
        status = (
            row.get("handover_status_label") or row.get("handover_status") or ""
        ).strip()
        if not name and not status:
            continue
        if name and status:
            lines.append(f"• {name}: {status}")
        elif name:
            lines.append(f"• {name}")
        else:
            lines.append(f"• {status}")
    return lines


def _agreement_coordinator_lines(coordinator: Mapping[str, Any] | None) -> list[str]:
    if not coordinator:
        return []
    lines: list[str] = []
    name = (coordinator.get("full_name") or "").strip()
    if name:
        lines.append(f"Jméno: {name}")
    employer = (coordinator.get("employer_name") or "").strip()
    if employer:
        lines.append(f"Organizace: {employer}")
    role = (coordinator.get("role") or "").strip()
    if role:
        lines.append(f"Funkce: {role}")
    phone = (coordinator.get("phone") or "").strip()
    if phone:
        lines.append(f"Telefon: {phone}")
    email = (coordinator.get("email") or "").strip()
    if email:
        lines.append(f"E-mail: {email}")
    note = (coordinator.get("note") or "").strip()
    if note:
        if lines:
            lines.append("")
        lines.append("Další informace")
        lines.append(note)
    return lines


def _format_contact_detail(contact: Mapping[str, Any]) -> str:
    detail = (contact.get("custom_name") or "").strip()
    role = (contact.get("role") or "").strip()
    if role:
        detail = f"{detail}, {role}" if detail else role
    return detail


def _contact_block_lines(contact: Mapping[str, Any]) -> list[str]:
    """Jméno, role a spojení – bez řádku zaměstnavatele."""
    lines: list[str] = []
    detail = _format_contact_detail(contact)
    if detail:
        lines.append(detail)
    phone = (contact.get("phone") or "").strip()
    email = (contact.get("email") or "").strip()
    if phone:
        lines.append(f"Telefon: {phone}")
    if email:
        lines.append(f"E-mail: {email}")
    return lines


def format_contacts_section_lines(
    contacts_by_type: list | None,
    contacts: list | None = None,
) -> list[str]:
    """Řádky sekce důležitých kontaktů (typ → zaměstnavatel → kontakt)."""
    groups = list(contacts_by_type or [])
    if not groups and contacts:
        groups = [
            {
                "contact_type_label": "",
                "employer_groups": [
                    {
                        "employer_label": "",
                        "contacts": list(contacts),
                    }
                ],
            }
        ]
    lines: list[str] = []
    for group in groups:
        type_label = (group.get("contact_type_label") or "").strip()
        employer_groups = group.get("employer_groups")
        if not employer_groups:
            flat = group.get("contacts") or []
            if not flat:
                continue
            employer_groups = [{"employer_label": "", "contacts": flat}]
        if type_label:
            lines.append(type_label)
        for employer_group in employer_groups:
            items = employer_group.get("contacts") or []
            if not items:
                continue
            employer_label = (employer_group.get("employer_label") or "").strip()
            if (
                employer_label
                and employer_label != CONTACT_EMPLOYER_UNSPECIFIED
            ):
                lines.append(employer_label)
            for contact in items:
                lines.extend(_contact_block_lines(contact))
    return lines


def _agreement_contacts_lines(
    contacts: list | None,
    contacts_by_type: list | None = None,
) -> list[str]:
    return format_contacts_section_lines(contacts_by_type, contacts)


def _agreement_emergency_lines(procedures: Mapping[str, Any] | None) -> list[str]:
    procedures = procedures or {}
    rows = (
        ("Mimořádná událost", procedures.get("emergency_reporting")),
        ("Pracovní úraz", procedures.get("accident_reporting")),
        ("Požár", procedures.get("fire_reporting")),
        ("Evakuace", procedures.get("evacuation_instructions")),
    )
    lines: list[str] = []
    for label, value in rows:
        text = (value or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    return lines


def build_coordination_agreement_parts(
    protocol_data: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    """Osm částí dohody; prázdné body se vynechají (UX-COORD-9a)."""
    data = protocol_data or {}
    agreement = data.get("coordination_agreement") or {}
    parts_spec = (
        (
            AGREEMENT_PART_WORK_INTENT,
            _nonempty_text_lines(agreement.get("work_intent_information_text")),
        ),
        (
            AGREEMENT_PART_MUTUAL_RISKS,
            _agreement_risk_lines(data.get("risk_handovers")),
        ),
        (
            AGREEMENT_PART_PPE,
            _nonempty_text_lines(agreement.get("ppe_text")),
        ),
        (
            AGREEMENT_PART_COORDINATOR,
            _agreement_coordinator_lines(data.get("coordinator")),
        ),
        (
            AGREEMENT_PART_CONTACTS,
            _agreement_contacts_lines(
                data.get("contacts"),
                data.get("contacts_by_type"),
            ),
        ),
        (
            AGREEMENT_PART_WORKPLACE_HANDOVER,
            _nonempty_text_lines(agreement.get("workplace_handover_text")),
        ),
        (
            AGREEMENT_PART_EMERGENCIES,
            _agreement_emergency_lines(data.get("emergency_procedures")),
        ),
        (
            AGREEMENT_PART_FINAL,
            _nonempty_text_lines(agreement.get("final_provisions_text")),
        ),
    )
    return [
        {"title": title, "lines": lines}
        for title, lines in parts_spec
        if lines
    ]


def protocol_agreement_part_titles(
    protocol_data: Mapping[str, Any] | None = None,
) -> list[str]:
    """Pořadí nadpisů částí, které se skutečně vytisknou."""
    return [part["title"] for part in build_coordination_agreement_parts(protocol_data)]


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
            "coordination_agreement": {
                "work_intent_information_text": (
                    coordination.work_intent_information_text or ""
                ),
                "ppe_text": coordination.ppe_text or "",
                "workplace_handover_text": (
                    coordination.workplace_handover_text or ""
                ),
                "final_provisions_text": coordination.final_provisions_text or "",
            },
            "contacts": [self._contact_dict(item) for item in contacts],
            "contacts_by_type": self._group_contacts(contacts),
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
        protocol_data["document"] = build_protocol_document(protocol_data)

        warnings = self._build_warnings(
            coordination=coordination,
            employers=employers_sorted,
            activities_by_employer=activities_by_employer,
            workplaces=workplaces,
            measures=measures,
            coordinator=coordinator,
            pbp_revision=pbp_revision,
            risk_rows=risk_rows,
            today=current,
        )
        # Pro náhled UI – mimo tělo dokumentu / ODT.
        protocol_data["warnings"] = [item.to_dict() for item in warnings]

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
        employers,
        activities_by_employer,
        workplaces,
        measures,
        coordinator,
        pbp_revision,
        risk_rows,
        today: date,
    ) -> list[ProtocolWarning]:
        warnings: list[ProtocolWarning] = []

        if not (coordination.subject or "").strip():
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_SUBJECT,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Není vyplněn název akce.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if coordination.meeting_date is None:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_MEETING_DATE,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Není vyplněno datum schůzky.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if not (coordination.place or "").strip():
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_MEETING_PLACE,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Není vyplněno místo schůzky.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if not employers:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_MISSING_ACTIVE_EMPLOYER,
                    severity=PROTOCOL_WARNING_SEVERITY_CRITICAL,
                    message="Není evidován žádný aktivní zúčastněný zaměstnavatel.",
                    related_entity_type="bozp_coordination",
                    related_entity_id=coordination.id,
                )
            )

        if not coordination.active:
            warnings.append(
                ProtocolWarning(
                    code=PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED,
                    severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                    message=(
                        "Koordinace je neaktivní – protokol může být pouze historický."
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
            if status in (
                RISK_HANDOVER_STATUS_UNSET,
                RISK_HANDOVER_STATUS_NOT_SUBMITTED,
            ) or status in RISK_SUBMISSION_PENDING_STATUSES:
                warnings.append(
                    ProtocolWarning(
                        code=PROTOCOL_WARNING_RISKS_NOT_SUBMITTED,
                        severity=PROTOCOL_WARNING_SEVERITY_WARNING,
                        message=(
                            f"Dodavatel „{employer['display_name']}“ "
                            "dosud nepředal informace o rizicích "
                            "(nebo je předání teprve plánováno)."
                        ),
                        related_entity_type="coordination_employer",
                        related_entity_id=employer["id"],
                    )
                )
                continue
            if status in RISK_SUBMISSION_COMPLETED_STATUSES:
                attachments = coordination_attachment_service.list_for_employer(
                    employer["id"],
                    include_inactive=False,
                )
                if not attachments and status != RISK_SUBMISSION_STATUS_STATED_AT_MEETING:
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
        abbr = (employer.abbreviation or "").strip() or default_abbreviation(
            employer.company_name or ""
        )
        name = employer.company_name or abbr or f"#{employer.id}"
        display = name
        if abbr and abbr != name:
            display = f"{abbr} – {name}"
        return {
            "id": employer.id,
            "abbreviation": abbr,
            "company_name": employer.company_name or "",
            "display_name": display,
            "ico": employer.ico or "",
            "address": employer.address or "",
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

    def _group_contacts(self, contacts) -> list[dict]:
        by_type: dict[str, list] = {key: [] for key in CONTACT_TYPES}
        for contact in contacts:
            type_id = contact.contact_type if contact.contact_type in by_type else "other"
            if type_id not in by_type:
                by_type[type_id] = []
            by_type[type_id].append(self._contact_dict(contact))
        result = []
        for type_id in CONTACT_TYPES:
            items = by_type.get(type_id) or []
            if not items:
                continue
            items.sort(
                key=lambda item: (
                    (item.get("employer_label") or "").casefold(),
                    item["sort_order"],
                    (item.get("custom_name") or "").casefold(),
                    item["id"],
                )
            )
            result.append(
                {
                    "contact_type": type_id,
                    "contact_type_label": CONTACT_TYPE_LABELS.get(type_id, type_id),
                    "contacts": items,
                    "employer_groups": self._group_contacts_by_employer(items),
                }
            )
        return result

    @staticmethod
    def _group_contacts_by_employer(contact_dicts: list[dict]) -> list[dict]:
        groups: list[dict] = []
        current_key = object()
        current: dict | None = None
        for item in contact_dicts:
            key = (
                item.get("employer_id"),
                (item.get("employer_label") or "").casefold(),
            )
            if current is None or key != current_key:
                current_key = key
                current = {
                    "employer_id": item.get("employer_id"),
                    "employer_label": item.get("employer_label") or "",
                    "employer_name": item.get("employer_name") or "",
                    "contacts": [],
                }
                groups.append(current)
            current["contacts"].append(item)
        return groups

    @staticmethod
    def _contact_dict(contact) -> dict:
        employer_label = coordination_contact_service.employer_display_label(contact)
        employer_name = coordination_contact_service.employer_display_tooltip(contact)
        if not employer_name:
            employer_name = (getattr(contact, "employer_name", None) or "").strip()
        return {
            "id": contact.id,
            "contact_type": contact.contact_type,
            "contact_type_label": CONTACT_TYPE_LABELS.get(
                contact.contact_type,
                contact.contact_type,
            ),
            "employer_id": getattr(contact, "employer_id", None),
            "employer_label": employer_label,
            "employer_name": employer_name,
            "custom_name": contact.custom_name or "",
            "role": contact.role or "",
            "phone": contact.phone or "",
            "email": contact.email or "",
            "sort_order": contact.sort_order or 0,
        }

    @staticmethod
    def _basics_dict(coordination, *, today: date) -> dict:
        from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
            normalize_coordination_status,
            status_label,
        )

        normalized_status = normalize_coordination_status(coordination.status)
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
            "status": normalized_status,
            "status_label": status_label(normalized_status),
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
        status = submission.submission_method or ""
        return {
            "id": submission.id,
            "submission_method": status,
            "submission_status": status,
            "submission_status_label": RISK_SUBMISSION_STATUS_LABELS.get(
                status,
                status,
            ),
            "submission_date": (
                submission.submission_date.isoformat()
                if submission.submission_date
                else None
            ),
            "document_reference": submission.document_reference or "",
            "expected_email": getattr(submission, "expected_email", "") or "",
            "risks_text": getattr(submission, "risks_text", "") or "",
            "note": submission.note or "",
            # Interní vazba na úkol se do protokolu netiskne.
            "task_id": getattr(submission, "task_id", None),
        }

    @staticmethod
    def _pbp_content_lines(revision) -> list[str]:
        if revision is None:
            return []
        rules: list[str] = []
        raw = (revision.rules_json or "").strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    rules = [
                        str(item.get("text") or "").strip()
                        for item in parsed
                        if isinstance(item, dict) and (item.get("text") or "").strip()
                    ]
            except json.JSONDecodeError:
                rules = []
        lines: list[str] = []
        if COORDINATION_PBP_INTRO_TEXT:
            lines.extend([COORDINATION_PBP_INTRO_TEXT, ""])
        for index, text in enumerate(rules, start=1):
            lines.append(f"{index}. {text}")
        if rules and COORDINATION_PBP_INFO_TEXT:
            lines.extend(["", COORDINATION_PBP_INFO_TEXT])
        return lines

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
            "content_lines": CoordinationProtocolBuilder._pbp_content_lines(
                revision
            ),
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
