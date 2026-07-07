from pathlib import Path

from moduly.pravni_pozadavky.import_export.legal_document_json_import_service import (
    LegalDocumentJsonImportResult,
    legal_document_json_import_service,
)
from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser


class LegalDocumentTxtImportService:
    def import_from_txt(
        self,
        path: str | Path,
        *,
        document_type: str,
        number: str = "",
        year: int | None = None,
        title: str,
        short_title: str = "",
    ) -> LegalDocumentJsonImportResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise ValueError("Soubor pro import nebyl nalezen.")

        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError("Soubor pro import nelze načíst.") from exc

        normalized_type = (document_type or "").strip()
        if not normalized_type:
            raise ValueError("Typ předpisu je povinný.")

        normalized_title = (title or "").strip()
        if not normalized_title:
            raise ValueError("Název předpisu je povinný.")

        parsed = legal_document_parser.parse_text(
            raw_text,
            document_type=normalized_type,
            number=(number or "").strip(),
            year=year,
            title=normalized_title,
            short_title=(short_title or "").strip(),
        )
        if not parsed.sections:
            raise ValueError("Text předpisu neobsahuje rozpoznatelná ustanovení.")

        return legal_document_json_import_service.import_data(parsed.to_dict())


legal_document_txt_import_service = LegalDocumentTxtImportService()
