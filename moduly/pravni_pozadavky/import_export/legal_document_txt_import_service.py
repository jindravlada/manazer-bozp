from pathlib import Path

from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.legal_document_type_utils import resolve_document_type
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser


def _debug(message: str) -> None:
    print(f"[LegalDocumentTxtImport] {message}", flush=True)


class LegalDocumentTxtImportService:
    def import_from_txt(
        self,
        path: str | Path,
        *,
        document_type: str = "",
        number: str = "",
        year: int | None = None,
        title: str,
        short_title: str = "",
    ) -> LegalDocumentJsonImportResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise ValueError("Soubor pro import nebyl nalezen.")

        _debug(f"načítám TXT: {file_path}")
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("Soubor pro import nelze načíst.") from exc

        normalized_title = (title or "").strip()
        if not normalized_title:
            raise ValueError("Název předpisu je povinný.")

        resolved_type = resolve_document_type(
            explicit=document_type,
            title=normalized_title,
        )

        parsed = legal_document_parser.parse_text(
            raw_text,
            document_type=resolved_type,
            number=(number or "").strip(),
            year=year,
            title=normalized_title,
            short_title=(short_title or "").strip(),
        )
        _debug(f"parsování dokončeno, počet částí: {len(parsed.sections)}")
        if not parsed.sections:
            raise ValueError("Text předpisu neobsahuje rozpoznatelná ustanovení.")

        result = legal_document_json_import_service.import_data(parsed.to_dict())
        _debug(
            "import do databáze dokončen: "
            f"document_id={result.document_id}, "
            f"version_id={result.version_id}, "
            f"section_count={result.section_count}",
        )
        return result


legal_document_txt_import_service = LegalDocumentTxtImportService()
