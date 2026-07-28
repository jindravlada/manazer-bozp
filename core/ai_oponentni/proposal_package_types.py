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


def _normalize_exposed_groups(
    *,
    exposed_group: str = "",
    exposed_groups: object = None,
) -> tuple[str, ...]:
    names: list[str] = []
    seen: set[str] = set()

    def _add(raw: object) -> None:
        name = str(raw or "").strip()
        if not name:
            return
        key = name.casefold()
        if key in seen:
            return
        seen.add(key)
        names.append(name)

    if isinstance(exposed_groups, (list, tuple)):
        for item in exposed_groups:
            _add(item)
    primary = str(exposed_group or "").strip()
    if primary:
        # Keep primary first when present.
        key = primary.casefold()
        if key in seen:
            names = [primary] + [n for n in names if n.casefold() != key]
        else:
            names.insert(0, primary)
    return tuple(names)


def _normalize_exposed_group_ids(raw: object, primary: int | None = None) -> tuple[int, ...]:
    ids: list[int] = []
    seen: set[int] = set()

    def _add(value: object) -> None:
        parsed = _optional_int(value)
        if parsed is None or parsed in seen:
            return
        seen.add(parsed)
        ids.append(parsed)

    if primary is not None:
        _add(primary)
    if isinstance(raw, (list, tuple)):
        for item in raw:
            _add(item)
    return tuple(ids)


@dataclass(frozen=True)
class AiProposalPackageMeasure:
    description: str
    note: str = ""


@dataclass(frozen=True)
class AiProposalPackageAssessment:
    exposed_group: str
    severity: str
    conclusion: str = ""
    existing_measures: tuple[AiProposalPackageMeasure, ...] = ()
    required_measures: tuple[AiProposalPackageMeasure, ...] = ()
    exposed_group_id: int | None = None
    exposed_groups: tuple[str, ...] = ()
    exposed_group_ids: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        groups = _normalize_exposed_groups(
            exposed_group=self.exposed_group,
            exposed_groups=self.exposed_groups,
        )
        ids = _normalize_exposed_group_ids(self.exposed_group_ids, self.exposed_group_id)
        object.__setattr__(self, "exposed_groups", groups)
        object.__setattr__(self, "exposed_group", groups[0] if groups else "")
        object.__setattr__(self, "exposed_group_ids", ids)
        object.__setattr__(self, "exposed_group_id", ids[0] if ids else self.exposed_group_id)


@dataclass(frozen=True)
class AiProposalPackageLegalLink:
    reference: str
    reasoning: str = ""
    legal_document_id: int | None = None
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
    # RISK-AI-12 – doporučení k opatřením (volitelné; starší balíky nemají)
    target_export_id: str | None = None
    proposed_text: str = ""

    @property
    def is_measure_recommendation(self) -> bool:
        from core.ai_oponentni.constants import AI_MEASURE_RECOMMENDATION_TYPES

        return self.package_type in AI_MEASURE_RECOMMENDATION_TYPES

    @property
    def requires_user_decision(self) -> bool:
        """True, pokud položka patří do fronty ke zpracování (RISK-AI-14)."""
        from core.ai_oponentni.constants import AI_MEASURE_REC_NO_CHANGE

        return self.package_type != AI_MEASURE_REC_NO_CHANGE

    @property
    def event_name(self) -> str:
        """Lidský název události pro UI (bez technického EVENT-XXX)."""
        if self.proposed_text.strip():
            return self.proposed_text.strip()
        if self.event is not None and self.event.name.strip():
            return self.event.name.strip()
        return "—"

    def display_event_label(self, *, resolved_target_name: str | None = None) -> str:
        """Text sloupce Událost: název nové události, cílové události nebo text opatření."""
        if self.is_measure_recommendation:
            text = self.proposed_text.strip()
            if text:
                return text
            if self.package_type == "beze_zmen":
                return "Beze změn opatření"
            return "—"
        if self.event is not None and self.event.name.strip():
            return self.event.name.strip()
        name = (resolved_target_name or "").strip()
        if name:
            return name
        if self.target_event_export_id:
            return "Doplnění události"
        return "—"

    @property
    def assessment_count(self) -> int:
        return len(self.assessments)

    @property
    def existing_measure_count(self) -> int:
        if self.package_type == "upravit_zasady_bezpecne_prace":
            return 1 if self.proposed_text.strip() else 0
        return sum(len(item.existing_measures) for item in self.assessments)

    @property
    def required_measure_count(self) -> int:
        if self.package_type in {
            "upravit_navazujici_opatreni",
            "nove_navazujici_opatreni",
        }:
            return 1 if self.proposed_text.strip() else 0
        return sum(len(item.required_measures) for item in self.assessments)

    @property
    def legal_link_count(self) -> int:
        return len(self.legal_links)

    def to_storage_dict(self) -> dict:
        return {
            "package_id": self.package_id,
            "package_type": self.package_type,
            "target_event_export_id": self.target_event_export_id,
            "target_export_id": self.target_export_id,
            "proposed_text": self.proposed_text,
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
                    "exposed_groups": list(assessment.exposed_groups),
                    "severity": assessment.severity,
                    "conclusion": assessment.conclusion,
                    "exposed_group_id": assessment.exposed_group_id,
                    "exposed_group_ids": list(assessment.exposed_group_ids),
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
                    "legal_document_id": link.legal_document_id,
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
                    exposed_groups=tuple(
                        str(name or "").strip()
                        for name in (item.get("exposed_groups") or [])
                        if str(name or "").strip()
                    ),
                    severity=str(item.get("severity") or "").strip(),
                    conclusion=str(item.get("conclusion") or "").strip(),
                    exposed_group_id=_optional_int(item.get("exposed_group_id")),
                    exposed_group_ids=tuple(
                        value
                        for value in (
                            _optional_int(raw)
                            for raw in (item.get("exposed_group_ids") or [])
                        )
                        if value is not None
                    ),
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
                legal_document_id=_optional_int(item.get("legal_document_id")),
                legal_requirement_id=_optional_int(item.get("legal_requirement_id")),
            )
            for item in (payload.get("legal_links") or [])
            if isinstance(item, dict)
        )
        target_event = payload.get("target_event_export_id")
        normalized_target = None
        if isinstance(target_event, str) and target_event.strip():
            normalized_target = target_event.strip()
        target_export = payload.get("target_export_id")
        normalized_target_export = None
        if isinstance(target_export, str) and target_export.strip():
            normalized_target_export = target_export.strip()
        return cls(
            package_id=str(payload.get("package_id") or "").strip(),
            package_type=str(payload.get("package_type") or "").strip(),
            target_event_export_id=normalized_target,
            event=event,
            assessments=tuple(assessments),
            legal_links=legal_links,
            reasoning=str(payload.get("reasoning") or "").strip(),
            target_export_id=normalized_target_export,
            proposed_text=str(payload.get("proposed_text") or "").strip(),
        )


@dataclass
class AiProposalPackageParseResult:
    packages: list[AiProposalPackage] = field(default_factory=list)
    format_label: str = ""
    schema_version: str = ""
    source_reference: str = ""
    skip_reasons: list[str] = field(default_factory=list)
