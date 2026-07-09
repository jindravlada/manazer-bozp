import hashlib
import re

from moduly.pravni_pozadavky.constants import CHANGE_NOVELIZATION, NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
    ESbirkaVersionInfo,
    legal_document_esbirka_client,
)
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

_NUMBER_YEAR_RE = re.compile(r"^(\d+)/(\d{4})$")


class LegalCheckNovelizationService:
    def check_document(
        self,
        document: LegalDocument,
        *,
        check_run_id: int,
    ) -> LegalChange | None:
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return None

        remote_version = self._fetch_remote_version(document)
        if remote_version is None:
            return None

        if not self._has_newer_version(stored_version, remote_version):
            return None

        remote_checksum = self._build_remote_checksum(remote_version)

        from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

        if legal_change_service.find_unevaluated_novelization(
            document.id,
            remote_checksum=remote_checksum,
            note_prefix=NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        ) is not None:
            self._update_reference_checksum(stored_version, remote_version)
            return None

        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=stored_version.id,
            legal_check_run_id=check_run_id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            description=self._build_description(stored_version, remote_version.version_label),
            published_at=remote_version.publication_date,
            evaluated=False,
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{remote_checksum}",
        )
        self._update_reference_checksum(stored_version, remote_version)
        return change

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

    def _build_description(self, stored_version: LegalDocumentVersion, remote_label: str) -> str:
        return (
            f"Původní verze: {stored_version.version_name}\n"
            f"Nová verze: {remote_label}"
        )


legal_check_novelization_service = LegalCheckNovelizationService()
