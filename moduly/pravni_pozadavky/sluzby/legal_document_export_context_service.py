from dataclasses import dataclass
from datetime import date, datetime

from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)


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
class LegalDocumentVersionExportRow:
    version_name: str
    valid_from: str
    valid_to: str
    effective_from: str
    effective_to: str
    publication_date: str
    source_url: str
    local_file_path: str


@dataclass(frozen=True)
class LegalDocumentExportRow:
    document_id: int
    document_type: str
    number: str
    year: str
    title: str
    short_title: str
    active_label: str
    versions: list[LegalDocumentVersionExportRow]


@dataclass(frozen=True)
class LegalDocumentExportContext:
    """Kontext pro budoucí export právních předpisů."""

    generated_at: datetime
    rows: list[LegalDocumentExportRow]

    @property
    def total_count(self) -> int:
        return len(self.rows)


class LegalDocumentExportContextService:
    def build(
        self,
        *,
        active_only: bool | None = True,
        include_inactive_versions: bool = True,
    ) -> LegalDocumentExportContext:
        if active_only is True:
            documents = legal_document_service.list_all(include_inactive=False)
        else:
            documents = legal_document_service.list_all(include_inactive=True)
        rows = [
            self._build_row(document, include_inactive_versions=include_inactive_versions)
            for document in documents
        ]
        return LegalDocumentExportContext(
            generated_at=datetime.now(),
            rows=rows,
        )

    def build_for_document(self, document_id: int) -> LegalDocumentExportContext | None:
        document = legal_document_service.get_by_id(document_id)
        if document is None:
            return None
        return LegalDocumentExportContext(
            generated_at=datetime.now(),
            rows=[self._build_row(document, include_inactive_versions=True)],
        )

    def _build_row(
        self,
        document: LegalDocument,
        *,
        include_inactive_versions: bool,
    ) -> LegalDocumentExportRow:
        versions = legal_document_version_service.list_by_document(
            document.id,
            include_inactive=include_inactive_versions,
        )
        return LegalDocumentExportRow(
            document_id=document.id,
            document_type=DOCUMENT_TYPE_LABELS.get(
                document.document_type,
                document.document_type,
            ),
            number=_text(document.number),
            year=str(document.year) if document.year is not None else "",
            title=_text(document.title),
            short_title=_text(document.short_title),
            active_label="Aktivní" if document.active else "Neaktivní",
            versions=[self._build_version_row(version) for version in versions],
        )

    def _build_version_row(self, version) -> LegalDocumentVersionExportRow:
        return LegalDocumentVersionExportRow(
            version_name=_text(version.version_name),
            valid_from=_fmt_date(version.valid_from),
            valid_to=_fmt_date(version.valid_to),
            effective_from=_fmt_date(version.effective_from),
            effective_to=_fmt_date(version.effective_to),
            publication_date=_fmt_date(version.publication_date),
            source_url=_text(version.source_url),
            local_file_path=_text(version.local_file_path),
        )


legal_document_export_context_service = LegalDocumentExportContextService()
