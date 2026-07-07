from collections.abc import Callable

from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
    legal_document_esbirka_client,
)
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser

ImportStatusCallback = Callable[[str], None]

_STATUS_SEARCHING = "Vyhledávám předpis..."
_STATUS_DOWNLOADING = "Stahuji..."
_STATUS_CONVERTING = "Převádím..."
_STATUS_IMPORTING = "Importuji..."
_STATUS_DONE = "Hotovo."


def _debug(message: str) -> None:
    print(f"[LegalDocumentInternetImport] {message}", flush=True)


class LegalDocumentInternetImportService:
    def import_from_internet(
        self,
        *,
        document_type: str,
        number: str,
        year: int,
        on_status: ImportStatusCallback | None = None,
    ) -> LegalDocumentJsonImportResult:
        normalized_type = (document_type or "").strip()
        if not normalized_type:
            raise ValueError("Typ předpisu je povinný.")

        normalized_number = (number or "").strip()
        if not normalized_number:
            raise ValueError("Číslo předpisu je povinné.")

        if year is None:
            raise ValueError("Rok předpisu je povinný.")

        self._notify(on_status, _STATUS_SEARCHING)
        self._notify(on_status, _STATUS_DOWNLOADING)
        try:
            html = legal_document_esbirka_client.fetch_full_text_html(
                year=year,
                number=normalized_number,
            )
            title = legal_document_esbirka_client.extract_title(html)
            self._notify(on_status, _STATUS_CONVERTING)
            raw_text = legal_document_esbirka_client.html_to_text(html)
            self._notify(on_status, _STATUS_IMPORTING)
            parsed = legal_document_parser.parse_text(
                raw_text,
                document_type=normalized_type,
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
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("Import se nezdařil.") from exc

    def _notify(
        self,
        on_status: ImportStatusCallback | None,
        message: str,
    ) -> None:
        if on_status is not None:
            on_status(message)


legal_document_internet_import_service = LegalDocumentInternetImportService()
