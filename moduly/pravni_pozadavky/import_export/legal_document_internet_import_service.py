from collections.abc import Callable

from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
    legal_document_esbirka_client,
)
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.legal_document_type_utils import resolve_document_type
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser

ImportStatusCallback = Callable[[str], None]
ImportCancelledCallback = Callable[[], bool]

_STATUS_SEARCHING = "Vyhledávám předpis..."
_STATUS_DOWNLOADING = "Stahuji..."
_STATUS_CONVERTING = "Parsuji..."
_STATUS_IMPORTING = "Ukládám..."
_STATUS_DONE = "Hotovo."


class ImportCancelledError(Exception):
    """Import byl uživatelem zrušen."""


def _debug(message: str) -> None:
    print(f"[LegalDocumentInternetImport] {message}", flush=True)


class LegalDocumentInternetImportService:
    def import_from_internet(
        self,
        *,
        document_type: str = "",
        number: str,
        year: int,
        on_status: ImportStatusCallback | None = None,
        is_cancelled: ImportCancelledCallback | None = None,
    ) -> LegalDocumentJsonImportResult:
        normalized_number = (number or "").strip()
        if not normalized_number:
            raise ValueError("Číslo předpisu je povinné.")

        if year is None:
            raise ValueError("Rok předpisu je povinný.")

        self._check_cancelled(is_cancelled)
        self._notify(on_status, _STATUS_SEARCHING)
        self._check_cancelled(is_cancelled)
        self._notify(on_status, _STATUS_DOWNLOADING)
        try:
            html = legal_document_esbirka_client.fetch_full_text_html(
                year=year,
                number=normalized_number,
            )
            self._check_cancelled(is_cancelled)
            title = legal_document_esbirka_client.extract_title(html)
            resolved_type = resolve_document_type(
                explicit=document_type,
                title=title,
            )
            self._notify(on_status, _STATUS_CONVERTING)
            raw_text = legal_document_esbirka_client.html_to_text(html)
            self._check_cancelled(is_cancelled)
            self._notify(on_status, _STATUS_IMPORTING)
            parsed = legal_document_parser.parse_text(
                raw_text,
                document_type=resolved_type,
                number=normalized_number,
                year=year,
                title=title,
                short_title="",
            )
            _debug(f"parsování dokončeno, počet částí: {len(parsed.sections)}")
            if not parsed.sections:
                raise ValueError("Neočekávaný formát stránky.")

            result = legal_document_json_import_service.import_data(parsed.to_dict())
            _debug(
                "import do databáze dokončen: "
                f"document_id={result.document_id}, "
                f"version_id={result.version_id}, "
                f"section_count={result.section_count}",
            )
            self._notify(on_status, _STATUS_DONE)
            return result
        except ImportCancelledError:
            raise
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Import se nezdařil.") from exc

    def _check_cancelled(self, is_cancelled: ImportCancelledCallback | None) -> None:
        if is_cancelled is not None and is_cancelled():
            raise ImportCancelledError()

    def _notify(
        self,
        on_status: ImportStatusCallback | None,
        message: str,
    ) -> None:
        if on_status is not None:
            on_status(message)


legal_document_internet_import_service = LegalDocumentInternetImportService()
