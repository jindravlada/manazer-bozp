from dataclasses import dataclass
from datetime import date, datetime

from core.shared.constants import ENTITY_LEGAL_CHANGE
from core.shared.sluzby.entity_link_service import entity_link_service
from moduly.pravni_pozadavky.constants import (
    CHANGE_TYPE_LABELS,
    DOCUMENT_TYPE_LABELS,
    SECTION_TYPE_LABELS,
)
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


def _fmt_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value).strip()


def _fmt_datetime(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    return str(value).strip()


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


@dataclass(frozen=True)
class LegalChangeLinkExportRow:
    target_type: str
    target_id: int
    link_type: str
    note: str


@dataclass(frozen=True)
class LegalChangeExportRow:
    change_id: int
    change_type: str
    title: str
    description: str
    published_at: str
    effective_from: str
    evaluated_label: str
    evaluated_at: str
    evaluated_by: str
    note: str
    active_label: str
    legal_document_id: int
    legal_document_title: str
    legal_document_short_title: str
    legal_document_type: str
    legal_document_number: str
    legal_document_year: str
    legal_document_version_id: int | None
    legal_document_version_name: str
    legal_section_id: int | None
    legal_section_type: str
    legal_section_number: str
    legal_section_paragraph: str
    legal_section_item_letter: str
    legal_section_title: str
    legal_section_text: str
    links: list[LegalChangeLinkExportRow]


@dataclass(frozen=True)
class LegalChangeExportContext:
    """Kontext pro budoucí export změn legislativy."""

    generated_at: datetime
    rows: list[LegalChangeExportRow]

    @property
    def total_count(self) -> int:
        return len(self.rows)


class LegalChangeExportContextService:
    def build(
        self,
        *,
        active_only: bool | None = True,
        include_inactive_links: bool = True,
    ) -> LegalChangeExportContext:
        if active_only is True:
            changes = legal_change_service.list_all(include_inactive=False)
        else:
            changes = legal_change_service.list_all(include_inactive=True)
        rows = [
            self._build_row(change, include_inactive_links=include_inactive_links)
            for change in changes
        ]
        return LegalChangeExportContext(
            generated_at=datetime.now(),
            rows=rows,
        )

    def build_for_change(self, change_id: int) -> LegalChangeExportContext | None:
        change = legal_change_service.get_by_id(change_id)
        if change is None:
            return None
        return LegalChangeExportContext(
            generated_at=datetime.now(),
            rows=[self._build_row(change, include_inactive_links=True)],
        )

    def _build_row(
        self,
        change,
        *,
        include_inactive_links: bool,
    ) -> LegalChangeExportRow:
        document = legal_document_service.get_by_id(change.legal_document_id)
        version = None
        if change.legal_document_version_id is not None:
            version = legal_document_version_service.get_by_id(change.legal_document_version_id)
        section = None
        if change.legal_section_id is not None:
            section = legal_section_service.get_by_id(change.legal_section_id)
        links = entity_link_service.list_for_source(
            ENTITY_LEGAL_CHANGE,
            change.id,
            include_inactive=include_inactive_links,
        )
        return LegalChangeExportRow(
            change_id=change.id,
            change_type=CHANGE_TYPE_LABELS.get(change.change_type, change.change_type),
            title=_text(change.title),
            description=_text(change.description),
            published_at=_fmt_date(change.published_at),
            effective_from=_fmt_date(change.effective_from),
            evaluated_label="Ano" if change.evaluated else "Ne",
            evaluated_at=_fmt_datetime(change.evaluated_at),
            evaluated_by=_text(change.evaluated_by),
            note=_text(change.note),
            active_label="Aktivní" if change.active else "Neaktivní",
            legal_document_id=change.legal_document_id,
            legal_document_title=_text(document.title if document else ""),
            legal_document_short_title=_text(document.short_title if document else ""),
            legal_document_type=(
                DOCUMENT_TYPE_LABELS.get(document.document_type, document.document_type)
                if document is not None
                else ""
            ),
            legal_document_number=_text(document.number if document else ""),
            legal_document_year=str(document.year) if document and document.year is not None else "",
            legal_document_version_id=change.legal_document_version_id,
            legal_document_version_name=_text(version.version_name if version else ""),
            legal_section_id=change.legal_section_id,
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
            links=[self._build_link_row(link) for link in links],
        )

    def _build_link_row(self, link) -> LegalChangeLinkExportRow:
        return LegalChangeLinkExportRow(
            target_type=_text(link.target_type),
            target_id=link.target_id,
            link_type=_text(link.link_type),
            note=_text(link.note),
        )


legal_change_export_context_service = LegalChangeExportContextService()
