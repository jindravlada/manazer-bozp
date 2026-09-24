from collections.abc import Callable
from datetime import date

from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_LABELS
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
    legal_document_esbirka_opendata_tree_builder,
)
from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.legal_document_type_utils import resolve_document_type
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser
from moduly.pravni_pozadavky.parser.legal_document_parser_models import (
    LegalDocumentParseResult,
)

ImportStatusCallback = Callable[[str], None]
ImportCancelledCallback = Callable[[], bool]

_STATUS_SEARCHING = "Vyhledávám předpis..."
_STATUS_DOWNLOADING = "Stahuji..."
_STATUS_CONVERTING = "Parsuji..."
_STATUS_IMPORTING = "Ukládám..."
_STATUS_DONE = "Hotovo."
_NETWORK_ERROR = "Internet není dostupný."
_NOT_FOUND_ERROR = "Předpis nenalezen."


class ImportCancelledError(Exception):
    """Import byl uživatelem zrušen."""


def _debug(message: str) -> None:
    print(f"[LegalDocumentInternetImport] {message}", flush=True)


def public_import_error_message(exc: BaseException) -> str:
    """Uživatelská hláška. Síť a nenalezený předpis nemají technický obal."""
    text = str(exc or "").strip()
    if "kind=network" in text or "kind=timeout" in text:
        return _NETWORK_ERROR
    if text in {_NETWORK_ERROR, "Vypršel časový limit spojení.", "Služba není dostupná."}:
        return _NETWORK_ERROR
    if _NOT_FOUND_ERROR in text or "status=404" in text:
        return _NOT_FOUND_ERROR
    return text or "Import se nezdařil."


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
            tree = legal_document_esbirka_opendata_tree_builder.fetch_in_force_tree(
                year=year,
                number=normalized_number,
                on_date=date.today(),
            )
            self._check_cancelled(is_cancelled)
            title = (tree.document_title or "").strip()
            if not title:
                raise ValueError("Neočekávaný formát odpovědi.")
            if not tree.sections:
                raise ValueError("Neočekávaný formát stránky.")
            resolved_type = resolve_document_type(
                explicit=document_type,
                title=title,
            )
            self._notify(on_status, _STATUS_CONVERTING)
            self._check_cancelled(is_cancelled)
            self._notify(on_status, _STATUS_IMPORTING)
            parsed = LegalDocumentParseResult(
                document={
                    "document_type": DOCUMENT_TYPE_LABELS.get(resolved_type, resolved_type),
                    "number": normalized_number,
                    "year": year,
                    "title": title,
                    "short_title": "",
                    "valid_from": None,
                    "valid_to": None,
                    "effective_from": None,
                    "effective_to": None,
                    "source_url": tree.source_url,
                    "local_file_path": "",
                    "note": "",
                },
                version={
                    "version_name": legal_document_parser.DEFAULT_VERSION_NAME,
                    "valid_from": None,
                    "valid_to": None,
                    "effective_from": None,
                    "effective_to": None,
                    "publication_date": None,
                    "source_url": tree.source_url,
                    "local_file_path": "",
                    "checksum": "",
                    "note": "",
                },
                sections=list(tree.sections),
            )
            _debug(f"parsování dokončeno, počet částí: {len(parsed.sections)}")
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
        except ValueError as exc:
            raise ValueError(public_import_error_message(exc)) from exc
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
