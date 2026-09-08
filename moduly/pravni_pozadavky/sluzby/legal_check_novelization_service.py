import hashlib
import re

from moduly.pravni_pozadavky.constants import (
    CHANGE_NOVELIZATION,
    NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
    detected_version_name,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
    ESbirkaVersionInfo,
    legal_document_esbirka_client,
)
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.parser.legal_document_parser_models import LegalDocumentParseResult
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

_NUMBER_YEAR_RE = re.compile(r"^(\d+)/(\d{4})$")


class LegalCheckNovelizationService:
    def initialize_reference_state(self, document: LegalDocument) -> bool:
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return False

        remote_version = self._fetch_remote_version(document)
        if remote_version is None:
            return False

        self._update_reference_checksum(stored_version, remote_version)
        return True

    def check_document(
        self,
        document: LegalDocument,
        *,
        check_run_id: int,
    ) -> LegalChange | None:
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return None

        loaded = self._load_remote_document(document)
        if loaded is None:
            return None
        remote_version, parsed = loaded
        remote_checksum = self._build_remote_checksum(remote_version)

        if not self._has_reference_state(stored_version):
            self._update_reference_checksum(stored_version, remote_version)
            return None

        from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

        existing_version = self._existing_detected_version(
            document.id,
            remote_checksum,
            stored_version.id,
        )
        existing_change = legal_change_service.find_novelization_by_remote_checksum(
            document.id,
            remote_checksum=remote_checksum,
            note_prefix=NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        )
        newer = self._has_newer_version(stored_version, remote_version)

        if not newer:
            if existing_change is not None and existing_change.new_legal_document_version_id is None:
                new_version = existing_version or self._persist_pending_version(
                    document=document,
                    remote_version=remote_version,
                    parsed=parsed,
                    remote_checksum=remote_checksum,
                )
                if new_version is not None:
                    legal_change_service.attach_detected_version(
                        existing_change.id,
                        new_version.id,
                        description=self._build_description(stored_version, new_version),
                    )
                    existing_change = legal_change_service.get_by_id(existing_change.id)
            if existing_change is not None:
                self._sync_content_changes(existing_change)
            return None

        new_version = existing_version or self._persist_pending_version(
            document=document,
            remote_version=remote_version,
            parsed=parsed,
            remote_checksum=remote_checksum,
        )
        if existing_change is not None:
            if existing_change.new_legal_document_version_id is None and new_version is not None:
                legal_change_service.attach_detected_version(
                    existing_change.id,
                    new_version.id,
                    description=self._build_description(stored_version, new_version),
                )
                existing_change = legal_change_service.get_by_id(existing_change.id)
            if existing_change is not None:
                self._sync_content_changes(existing_change)
            return None

        new_version_label = (
            new_version.version_name if new_version is not None else remote_version.version_label
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=stored_version.id,
            new_legal_document_version_id=new_version.id if new_version is not None else None,
            legal_check_run_id=check_run_id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            description=self._build_description_labels(
                stored_version.version_name,
                new_version_label,
            ),
            published_at=remote_version.publication_date,
            evaluated=False,
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{remote_checksum}",
        )
        self._sync_content_changes(change, document=document, check_run_id=check_run_id)
        return change

    def _persist_pending_version(
        self,
        *,
        document: LegalDocument,
        remote_version: ESbirkaVersionInfo,
        parsed: LegalDocumentParseResult,
        remote_checksum: str,
    ) -> LegalDocumentVersion | None:
        if not parsed.sections:
            return None

        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name=detected_version_name(remote_version.version_label),
            publication_date=remote_version.publication_date,
            source_url=remote_version.source_url,
            checksum=remote_checksum,
            pending_adoption=True,
            active=True,
        )
        legal_section_service.create_tree_from_parsed(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            parsed_sections=parsed.sections,
        )
        return legal_document_version_service.get_by_id(version.id) or version

    def _sync_content_changes(
        self,
        change: LegalChange | None,
        *,
        document: LegalDocument | None = None,
        check_run_id: int | None = None,
    ) -> None:
        if change is None:
            return
        from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
            legal_change_section_service,
        )
        from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
            legal_section_structure_compare_service,
        )

        _saved, compare_result = legal_change_section_service.sync_version_content_changes(change)
        if document is None or check_run_id is None:
            return
        summary = legal_section_structure_compare_service.format_check_run_summary(
            document=document,
            result=compare_result,
        )
        if not summary:
            return
        from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
            legal_check_run_service,
        )

        legal_check_run_service.append_note(check_run_id, summary)

    def _existing_detected_version(
        self,
        document_id: int,
        remote_checksum: str,
        stored_version_id: int,
    ) -> LegalDocumentVersion | None:
        pending = legal_document_version_service.find_pending_by_checksum(
            document_id,
            remote_checksum,
        )
        if pending is not None:
            return pending
        same_checksum = legal_document_version_service.find_by_checksum(
            document_id,
            remote_checksum,
        )
        if same_checksum is None or same_checksum.id == stored_version_id:
            return None
        return same_checksum

    def _load_remote_document(
        self,
        document: LegalDocument,
    ) -> tuple[ESbirkaVersionInfo, LegalDocumentParseResult] | None:
        number, year = self._resolve_number_and_year(document)
        if number is None or year is None:
            return None
        try:
            html = legal_document_esbirka_client.fetch_full_text_html(
                year=year,
                number=number,
            )
            remote_version = legal_document_esbirka_client.extract_version_info(
                html,
                year=year,
                number=number,
            )
            title = legal_document_esbirka_client.extract_title(html)
            raw_text = legal_document_esbirka_client.html_to_text(html)
            from moduly.pravni_pozadavky.parser.legal_document_parser import legal_document_parser

            parsed = legal_document_parser.parse_text(
                raw_text,
                document_type=document.document_type,
                number=number,
                year=year,
                title=title,
                short_title=document.short_title or "",
            )
        except (ValueError, OSError):
            return None
        return remote_version, parsed

    def _fetch_remote_version(self, document: LegalDocument):
        number, year = self._resolve_number_and_year(document)
        if number is None or year is None:
            return None
        try:
            return legal_document_esbirka_client.fetch_version_info(
                year=year,
                number=number,
            )
        except ValueError:
            return None

    def _resolve_number_and_year(self, document: LegalDocument) -> tuple[str | None, int | None]:
        number = (document.number or "").strip()
        year = document.year
        if number and year is not None:
            normalized_number = number.replace(" Sb.", "").strip()
            return normalized_number, year

        match = _NUMBER_YEAR_RE.match(number)
        if match is not None:
            return match.group(1), int(match.group(2))

        return None, year

    def _has_reference_state(self, stored_version: LegalDocumentVersion) -> bool:
        stored_slice_id, stored_checksum = legal_document_esbirka_client.parse_version_checksum(
            stored_version.checksum,
        )
        return stored_slice_id is not None and stored_checksum is not None

    def _has_newer_version(
        self,
        stored_version: LegalDocumentVersion,
        remote_version: ESbirkaVersionInfo,
    ) -> bool:
        stored_slice_id, stored_checksum = legal_document_esbirka_client.parse_version_checksum(
            stored_version.checksum,
        )
        if stored_checksum is None:
            stored_checksum = self._compute_stored_text_checksum(stored_version.id)

        if stored_slice_id is not None and stored_slice_id != remote_version.slice_id:
            return True

        return stored_checksum != remote_version.text_checksum

    def _build_remote_checksum(self, remote_version: ESbirkaVersionInfo) -> str:
        return legal_document_esbirka_client.build_version_checksum(
            slice_id=remote_version.slice_id,
            text_checksum=remote_version.text_checksum,
        )

    def _update_reference_checksum(
        self,
        stored_version: LegalDocumentVersion,
        remote_version: ESbirkaVersionInfo,
    ) -> None:
        legal_document_version_service.update_checksum(
            stored_version.id,
            self._build_remote_checksum(remote_version),
        )

    def _compute_stored_text_checksum(self, version_id: int) -> str:
        sections = legal_section_service.list_by_version(version_id, include_inactive=False)
        parts: list[str] = []
        for section in sorted(sections, key=lambda item: (item.sort_order, item.id)):
            parts.append(
                "|".join(
                    [
                        section.section_type,
                        section.section_number,
                        section.paragraph,
                        section.item_letter,
                        section.title,
                        section.text,
                    ],
                ),
            )
        payload = "\n".join(parts)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_description(
        self,
        stored_version: LegalDocumentVersion,
        new_version: LegalDocumentVersion,
    ) -> str:
        return self._build_description_labels(stored_version.version_name, new_version.version_name)

    def _build_description_labels(self, original_name: str, new_name: str) -> str:
        return (
            f"Původní verze: {original_name}\n"
            f"Nová verze: {new_name}"
        )


legal_check_novelization_service = LegalCheckNovelizationService()
