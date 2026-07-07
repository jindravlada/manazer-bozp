from collections.abc import Callable
from dataclasses import dataclass

from moduly.pravni_pozadavky.import_export.legal_document_bulk_internet_import_parser import (
    bulk_import_regulation_label,
    parse_bulk_import_line,
)
from moduly.pravni_pozadavky.import_export.legal_document_internet_import_service import (
    legal_document_internet_import_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service

BULK_IMPORT_STATUS_OK = "OK"
BULK_IMPORT_STATUS_ERROR = "Chyba"
BULK_IMPORT_STATUS_SKIPPED = "Přeskočeno"

DUPLICATE_SKIP_MESSAGE = "Předpis již existuje"

BulkProgressCallback = Callable[[int, int, str], None]


@dataclass(frozen=True)
class BulkInternetImportRowResult:
    regulation_label: str
    status: str
    title: str
    section_count: int | None
    error: str
    source_line: str


@dataclass(frozen=True)
class BulkInternetImportSummary:
    total: int
    ok_count: int
    error_count: int
    skipped_count: int
    rows: list[BulkInternetImportRowResult]


class LegalDocumentBulkInternetImportService:
    def import_lines(
        self,
        text: str,
        *,
        on_progress: BulkProgressCallback | None = None,
    ) -> BulkInternetImportSummary:
        lines = [line for line in (text or "").splitlines() if line.strip()]
        rows: list[BulkInternetImportRowResult] = []
        total = len(lines)

        for index, line in enumerate(lines, start=1):
            regulation_label = line.strip()
            try:
                parsed = parse_bulk_import_line(line)
            except ValueError as exc:
                rows.append(
                    BulkInternetImportRowResult(
                        regulation_label=regulation_label,
                        status=BULK_IMPORT_STATUS_ERROR,
                        title="",
                        section_count=None,
                        error=str(exc),
                        source_line=line.strip(),
                    ),
                )
                self._notify_progress(on_progress, index, total, line.strip())
                continue

            regulation_label = bulk_import_regulation_label(
                number=parsed.number,
                year=parsed.year,
            )
            existing = self._find_active_by_number_and_year(parsed.number, parsed.year)
            if existing is not None:
                rows.append(
                    BulkInternetImportRowResult(
                        regulation_label=regulation_label,
                        status=BULK_IMPORT_STATUS_SKIPPED,
                        title=existing.title,
                        section_count=None,
                        error=DUPLICATE_SKIP_MESSAGE,
                        source_line=parsed.source_line,
                    ),
                )
                self._notify_progress(on_progress, index, total, regulation_label)
                continue

            try:
                result = legal_document_internet_import_service.import_from_internet(
                    document_type=parsed.document_type,
                    number=parsed.number,
                    year=parsed.year,
                )
                document = legal_document_service.get_by_id(result.document_id)
                title = document.title if document is not None else ""
                rows.append(
                    BulkInternetImportRowResult(
                        regulation_label=regulation_label,
                        status=BULK_IMPORT_STATUS_OK,
                        title=title,
                        section_count=result.section_count,
                        error="",
                        source_line=parsed.source_line,
                    ),
                )
            except ValueError as exc:
                rows.append(
                    BulkInternetImportRowResult(
                        regulation_label=regulation_label,
                        status=BULK_IMPORT_STATUS_ERROR,
                        title="",
                        section_count=None,
                        error=str(exc),
                        source_line=parsed.source_line,
                    ),
                )

            self._notify_progress(on_progress, index, total, regulation_label)

        return BulkInternetImportSummary(
            total=total,
            ok_count=sum(1 for row in rows if row.status == BULK_IMPORT_STATUS_OK),
            error_count=sum(1 for row in rows if row.status == BULK_IMPORT_STATUS_ERROR),
            skipped_count=sum(1 for row in rows if row.status == BULK_IMPORT_STATUS_SKIPPED),
            rows=rows,
        )

    def _find_active_by_number_and_year(self, number: str, year: int):
        normalized_number = number.strip()
        for document in legal_document_service.list_all(include_inactive=True):
            if (
                document.active
                and document.number.strip() == normalized_number
                and document.year == year
            ):
                return document
        return None

    def _notify_progress(
        self,
        on_progress: BulkProgressCallback | None,
        current: int,
        total: int,
        label: str,
    ) -> None:
        if on_progress is not None:
            on_progress(current, total, label)


legal_document_bulk_internet_import_service = LegalDocumentBulkInternetImportService()
