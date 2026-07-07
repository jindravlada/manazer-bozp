from dataclasses import dataclass
from datetime import date, datetime

from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    PERIODICITY_LABELS,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value).strip()


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


@dataclass(frozen=True)
class LegalRequirementExportRow:
    requirement_id: int
    regulation_name: str
    regulation_number: str
    provision: str
    area: str
    requirement_summary: str
    organization_impact: str
    responsible_person_name: str
    verification_periodicity_label: str
    last_verification_date: str
    next_verification_date: str
    compliance_status_label: str
    note: str
    active_label: str


@dataclass(frozen=True)
class LegalRequirementExportContext:
    """Kontext pro budoucí export registru právních požadavků."""

    generated_at: datetime
    rows: list[LegalRequirementExportRow]

    @property
    def total_count(self) -> int:
        return len(self.rows)

    @property
    def active_count(self) -> int:
        return sum(1 for row in self.rows if row.active_label == "Aktivní")


class LegalRequirementExportContextService:
    def build(
        self,
        *,
        active_only: bool | None = True,
    ) -> LegalRequirementExportContext:
        requirements = legal_requirement_service.get_all(active_only=active_only)
        rows = [self._build_row(requirement) for requirement in requirements]
        return LegalRequirementExportContext(
            generated_at=datetime.now(),
            rows=rows,
        )

    def build_for_requirement(self, requirement_id: int) -> LegalRequirementExportContext | None:
        requirement = legal_requirement_service.get_by_id(requirement_id)
        if requirement is None:
            return None
        return LegalRequirementExportContext(
            generated_at=datetime.now(),
            rows=[self._build_row(requirement)],
        )

    def _build_row(self, requirement: LegalRequirement) -> LegalRequirementExportRow:
        return LegalRequirementExportRow(
            requirement_id=requirement.id,
            regulation_name=_text(requirement.regulation_name),
            regulation_number=_text(requirement.regulation_number),
            provision=_text(requirement.provision),
            area=_text(requirement.area),
            requirement_summary=_text(requirement.requirement_summary),
            organization_impact=_text(requirement.organization_impact),
            responsible_person_name=_text(requirement.responsible_person_name),
            verification_periodicity_label=PERIODICITY_LABELS.get(
                requirement.verification_periodicity,
                requirement.verification_periodicity,
            ),
            last_verification_date=_fmt_date(requirement.last_verification_date),
            next_verification_date=_fmt_date(requirement.next_verification_date),
            compliance_status_label=COMPLIANCE_STATUS_LABELS.get(
                requirement.compliance_status,
                requirement.compliance_status,
            ),
            note=_text(requirement.note),
            active_label="Aktivní" if requirement.active else "Archivní",
        )


legal_requirement_export_context_service = LegalRequirementExportContextService()
