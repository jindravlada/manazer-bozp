from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from moduly.pravni_pozadavky.constants import (
    COMPLIANCE_STATUS_LABELS,
    DOCUMENT_TYPE_LABELS,
    PERIODICITY_LABELS,
    PROCESSING_STATUS_LABELS,
    SECTION_TYPE_LABELS,
)
from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_requirement_sanction_service import (
    legal_requirement_sanction_service,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from core.shared.constants import ENTITY_LEGAL_REQUIREMENT
from core.shared.sluzby.entity_link_service import entity_link_service


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


def _fmt_amount(value: Decimal | None, currency: str) -> str:
    if value is None:
        return ""
    amount = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    if currency:
        return f"{amount} {currency}"
    return amount


@dataclass(frozen=True)
class LegalRequirementLinkExportRow:
    target_type: str
    target_id: int
    link_type: str
    note: str


@dataclass(frozen=True)
class LegalRequirementSanctionExportRow:
    sanction_id: int
    authority: str
    legal_reference: str
    description: str
    max_amount: str
    currency: str
    note: str
    active_label: str


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
    legal_document_id: int | None
    legal_document_title: str
    legal_document_short_title: str
    legal_document_type: str
    legal_document_number: str
    legal_document_year: str
    legal_section_id: int | None
    legal_section_type: str
    legal_section_number: str
    legal_section_paragraph: str
    legal_section_item_letter: str
    legal_section_title: str
    legal_section_text: str
    source_section_id: int | None
    processing_status: str
    processing_status_label: str
    sanctions: list[LegalRequirementSanctionExportRow]
    links: list[LegalRequirementLinkExportRow]


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
        include_inactive_sanctions: bool = True,
    ) -> LegalRequirementExportContext:
        requirements = legal_requirement_service.get_all(active_only=active_only)
        rows = [
            self._build_row(requirement, include_inactive_sanctions=include_inactive_sanctions)
            for requirement in requirements
        ]
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
            rows=[self._build_row(requirement, include_inactive_sanctions=True)],
        )

    def _build_row(
        self,
        requirement: LegalRequirement,
        *,
        include_inactive_sanctions: bool,
        include_inactive_links: bool = True,
    ) -> LegalRequirementExportRow:
        sanctions = legal_requirement_sanction_service.list_by_requirement(
            requirement.id,
            include_inactive=include_inactive_sanctions,
        )
        links = entity_link_service.list_for_source(
            ENTITY_LEGAL_REQUIREMENT,
            requirement.id,
            include_inactive=include_inactive_links,
        )
        document = None
        if requirement.legal_document_id is not None:
            document = legal_document_service.get_by_id(requirement.legal_document_id)
        section = None
        if requirement.legal_section_id is not None:
            section = legal_section_service.get_by_id(requirement.legal_section_id)
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
            legal_document_id=requirement.legal_document_id,
            legal_document_title=_text(document.title if document else ""),
            legal_document_short_title=_text(document.short_title if document else ""),
            legal_document_type=(
                DOCUMENT_TYPE_LABELS.get(document.document_type, document.document_type)
                if document is not None
                else ""
            ),
            legal_document_number=_text(document.number if document else ""),
            legal_document_year=str(document.year) if document and document.year is not None else "",
            legal_section_id=requirement.legal_section_id,
            legal_section_type=(
                SECTION_TYPE_LABELS.get(section.section_type, section.section_type)
                if section is not None
                else ""
            ),
            legal_section_number=_text(section.section_number if section else ""),
            legal_section_paragraph=_text(section.paragraph if section else ""),
            legal_section_item_letter=_text(section.item_letter if section else ""),
            legal_section_title=_text(section.title if section else ""),
            legal_section_text=_text(section.text if section else ""),
            source_section_id=requirement.source_section_id,
            processing_status=_text(requirement.processing_status),
            processing_status_label=PROCESSING_STATUS_LABELS.get(
                requirement.processing_status,
                requirement.processing_status,
            ),
            sanctions=[self._build_sanction_row(sanction) for sanction in sanctions],
            links=[self._build_link_row(link) for link in links],
        )

    def _build_link_row(self, link) -> LegalRequirementLinkExportRow:
        return LegalRequirementLinkExportRow(
            target_type=_text(link.target_type),
            target_id=link.target_id,
            link_type=_text(link.link_type),
            note=_text(link.note),
        )

    def _build_sanction_row(self, sanction) -> LegalRequirementSanctionExportRow:
        return LegalRequirementSanctionExportRow(
            sanction_id=sanction.id,
            authority=_text(sanction.authority),
            legal_reference=_text(sanction.legal_reference),
            description=_text(sanction.description),
            max_amount=_fmt_amount(sanction.max_amount, ""),
            currency=_text(sanction.currency),
            note=_text(sanction.note),
            active_label="Aktivní" if sanction.active else "Neaktivní",
        )


legal_requirement_export_context_service = LegalRequirementExportContextService()
