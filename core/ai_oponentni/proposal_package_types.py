"""Datové typy návrhových balíků AI oponentury (schema 2.0)."""

from __future__ import annotations

from dataclasses import dataclass, field


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class AiProposalPackageMeasure:
    description: str
    note: str = ""


@dataclass(frozen=True)
class AiProposalPackageAssessment:
    exposed_group: str
    consequence: str
    severity: str
    conclusion: str = ""
    existing_measures: tuple[AiProposalPackageMeasure, ...] = ()
    required_measures: tuple[AiProposalPackageMeasure, ...] = ()
    exposed_group_id: int | None = None


@dataclass(frozen=True)
class AiProposalPackageLegalLink:
    reference: str
    reasoning: str = ""
    legal_requirement_id: int | None = None


@dataclass(frozen=True)
class AiProposalPackageEvent:
    name: str
    description: str = ""
    note: str = ""


@dataclass(frozen=True)
class AiProposalPackage:
    package_id: str
    package_type: str
    target_event_export_id: str | None
    event: AiProposalPackageEvent | None
    assessments: tuple[AiProposalPackageAssessment, ...]
    legal_links: tuple[AiProposalPackageLegalLink, ...] = ()
    reasoning: str = ""

    @property
    def event_name(self) -> str:
        if self.event is not None and self.event.name.strip():
            return self.event.name.strip()
        if self.target_event_export_id:
            return self.target_event_export_id
        return "—"

    @property
    def assessment_count(self) -> int:
        return len(self.assessments)

    @property
    def existing_measure_count(self) -> int:
        return sum(len(item.existing_measures) for item in self.assessments)

    @property
    def required_measure_count(self) -> int:
        return sum(len(item.required_measures) for item in self.assessments)

    @property
    def legal_link_count(self) -> int:
        return len(self.legal_links)

    def to_storage_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "package_type": self.package_type,
            "target_event_export_id": self.target_event_export_id,
            "event": (
                {
                    "name": self.event.name,
                    "description": self.event.description,
                    "note": self.event.note,
                }
                if self.event is not None
                else None
            ),
            "assessments": [
                {
                    "exposed_group": assessment.exposed_group,
                    "consequence": assessment.consequence,
                    "severity": assessment.severity,
                    "conclusion": assessment.conclusion,
                    "exposed_group_id": assessment.exposed_group_id,
                    "existing_measures": [
                        {"description": measure.description, "note": measure.note}
                        for measure in assessment.existing_measures
                    ],
                    "required_measures": [
                        {"description": measure.description, "note": measure.note}
                        for measure in assessment.required_measures
                    ],
                }
                for assessment in self.assessments
            ],
            "legal_links": [
                {
                    "reference": link.reference,
                    "reasoning": link.reasoning,
                    "legal_requirement_id": link.legal_requirement_id,
                }
                for link in self.legal_links
            ],
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_storage_dict(cls, payload: dict) -> AiProposalPackage:
        event_payload = payload.get("event")
        event = None
        if isinstance(event_payload, dict):
            event = AiProposalPackageEvent(
                name=str(event_payload.get("name") or "").strip(),
                description=str(event_payload.get("description") or "").strip(),
                note=str(event_payload.get("note") or "").strip(),
            )
        assessments: list[AiProposalPackageAssessment] = []
        for item in payload.get("assessments") or []:
            if not isinstance(item, dict):
                continue
            assessments.append(
                AiProposalPackageAssessment(
                    exposed_group=str(item.get("exposed_group") or "").strip(),
                    consequence=str(item.get("consequence") or "").strip(),
                    severity=str(item.get("severity") or "").strip(),
                    conclusion=str(item.get("conclusion") or "").strip(),
                    exposed_group_id=_optional_int(item.get("exposed_group_id")),
                    existing_measures=tuple(
                        AiProposalPackageMeasure(
                            description=str(measure.get("description") or "").strip(),
                            note=str(measure.get("note") or "").strip(),
                        )
                        for measure in (item.get("existing_measures") or [])
                        if isinstance(measure, dict)
                    ),
                    required_measures=tuple(
                        AiProposalPackageMeasure(
                            description=str(measure.get("description") or "").strip(),
                            note=str(measure.get("note") or "").strip(),
                        )
                        for measure in (item.get("required_measures") or [])
                        if isinstance(measure, dict)
                    ),
                ),
            )
        legal_links = tuple(
            AiProposalPackageLegalLink(
                reference=str(item.get("reference") or "").strip(),
                reasoning=str(item.get("reasoning") or "").strip(),
                legal_requirement_id=_optional_int(item.get("legal_requirement_id")),
            )
            for item in (payload.get("legal_links") or [])
            if isinstance(item, dict)
        )
        target_event = payload.get("target_event_export_id")
        normalized_target = None
        if isinstance(target_event, str) and target_event.strip():
            normalized_target = target_event.strip()
        return cls(
            package_id=str(payload.get("package_id") or "").strip(),
            package_type=str(payload.get("package_type") or "").strip(),
            target_event_export_id=normalized_target,
            event=event,
            assessments=tuple(assessments),
            legal_links=legal_links,
            reasoning=str(payload.get("reasoning") or "").strip(),
        )


@dataclass
class AiProposalPackageParseResult:
    packages: list[AiProposalPackage] = field(default_factory=list)
    format_label: str = ""
    schema_version: str = ""
    source_reference: str = ""
    skip_reasons: list[str] = field(default_factory=list)
