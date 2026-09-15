"""Jednorázový přechod legacy RPP na Open Data baseline (PRE-4.0-BLOCKER-5R)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging

from core.http_safe import SafeHttpsError
from moduly.pravni_pozadavky.constants import (
    CHANGE_NOVELIZATION,
    NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
    detected_version_name,
    legal_document_display_label,
    legal_document_regulation_number,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
    format_opendata_fetch_error,
    legal_document_esbirka_opendata_client,
    open_data_http_session,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
    ESbirkaOpenDataParsedTree,
    legal_document_esbirka_opendata_tree_builder,
)
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
    legal_check_novelization_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_version_temporal import (
    is_identified_temporal_version,
)
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
from moduly.pravni_pozadavky.sluzby.legal_version_adoption_service import (
    legal_version_adoption_service,
)

logger = logging.getLogger(__name__)

BASELINE_ACTION_SKIPPED = "skipped"
BASELINE_ACTION_STAMP = "stamp"
BASELINE_ACTION_REPLACE = "replace"
BASELINE_ACTION_FAILED = "failed"

UNMAPPED_SOURCE_NOTE_PREFIX = "Open Data baseline: nepřemapovaný zdroj"


@dataclass(frozen=True)
class OpenDataBaselineDocumentResult:
    document_id: int
    action: str
    error: str | None = None
    remapped_count: int = 0
    unresolved_count: int = 0
    version_id: int | None = None


@dataclass(frozen=True)
class OpenDataBaselineRunResult:
    applied: bool
    results: tuple[OpenDataBaselineDocumentResult, ...] = ()

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.results if item.action == BASELINE_ACTION_FAILED)


class LegalOpenDataBaselineService:
    def documents_needing_baseline(self) -> list[LegalDocument]:
        needed: list[LegalDocument] = []
        for document in legal_document_service.list_all(include_inactive=False):
            if not self._can_fetch_document(document):
                continue
            current = legal_document_version_service.get_current_version(document.id)
            if current is None:
                continue
            if is_identified_temporal_version(current):
                continue
            needed.append(document)
        return needed

    def needs_baseline(self) -> bool:
        return bool(self.documents_needing_baseline())

    def apply_if_needed(self) -> OpenDataBaselineRunResult:
        documents = self.documents_needing_baseline()
        if not documents:
            return OpenDataBaselineRunResult(applied=False)

        if legal_document_esbirka_opendata_client.http_session is not None:
            results = tuple(self.apply_document(document) for document in documents)
            return OpenDataBaselineRunResult(applied=True, results=results)

        with open_data_http_session():
            results = tuple(self.apply_document(document) for document in documents)
            return OpenDataBaselineRunResult(applied=True, results=results)

    def apply_document(self, document: LegalDocument) -> OpenDataBaselineDocumentResult:
        label = legal_document_display_label(document)
        stored = legal_document_version_service.get_current_version(document.id)
        if stored is None:
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_FAILED,
                error="Chybí aktuální znění předpisu.",
            )
        if is_identified_temporal_version(stored):
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_SKIPPED,
                version_id=stored.id,
            )

        try:
            tree = legal_document_esbirka_opendata_tree_builder.fetch_in_force_tree(
                year=document.year if document.year is not None else "",
                number=document.number or "",
                on_date=date.today(),
            )
        except SafeHttpsError as exc:
            logger.info("Open Data baseline předpisu %s selhal: %s", label, exc)
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_FAILED,
                error=format_opendata_fetch_error(
                    kind=exc.kind,
                    endpoint="-",
                    status_code=exc.status_code,
                    detail=str(exc),
                ),
            )
        except ValueError as exc:
            logger.info("Open Data baseline předpisu %s selhal: %s", label, exc)
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_FAILED,
                error=str(exc) or "ověření se nezdařilo.",
            )
        except OSError as exc:
            logger.warning("Síťová chyba při Open Data baseline předpisu %s: %s", label, exc)
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_FAILED,
                error=format_opendata_fetch_error(
                    kind="network",
                    endpoint="-",
                    detail=str(exc) or "síťová chyba",
                ),
            )

        if tree.effective_from is None or not (tree.source_eli or "").strip():
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_FAILED,
                error="Open Data znění nemá ELI nebo datum účinnosti.",
            )

        checksum = legal_document_esbirka_opendata_client.build_version_checksum(
            tree.source_eli,
        )
        try:
            if legal_check_novelization_service._trees_match(stored, tree):
                stamped = self._stamp_matching_current(stored, tree, checksum)
                self._deactivate_unevaluated_novelizations(
                    document.id,
                    baseline_version_id=stamped.id,
                    checksum=checksum,
                    source_eli=tree.source_eli,
                )
                legal_check_novelization_service._sync_future_wordings(
                    document,
                    skip_eli=tree.source_eli,
                )
                return OpenDataBaselineDocumentResult(
                    document_id=document.id,
                    action=BASELINE_ACTION_STAMP,
                    version_id=stamped.id,
                )

            baseline = self._replace_with_open_data_tree(document, stored, tree, checksum)
            if baseline is None:
                return OpenDataBaselineDocumentResult(
                    document_id=document.id,
                    action=BASELINE_ACTION_FAILED,
                    error="Nové Open Data znění se nepodařilo uložit.",
                )
            mapping, unresolved_ids = legal_version_adoption_service._section_mapping(
                stored.id,
                baseline.id,
            )
            remapped_count = legal_version_adoption_service._remap_links(mapping)
            unresolved_count = self._annotate_unmapped_sources(document, unresolved_ids)
            self._deactivate_unevaluated_novelizations(
                document.id,
                baseline_version_id=baseline.id,
                checksum=checksum,
                source_eli=tree.source_eli,
            )
            legal_check_novelization_service._sync_future_wordings(
                document,
                skip_eli=tree.source_eli,
            )
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_REPLACE,
                remapped_count=remapped_count,
                unresolved_count=unresolved_count,
                version_id=baseline.id,
            )
        except (ValueError, OSError) as exc:
            logger.info("Open Data baseline předpisu %s selhal: %s", label, exc)
            return OpenDataBaselineDocumentResult(
                document_id=document.id,
                action=BASELINE_ACTION_FAILED,
                error=str(exc) or "Open Data baseline se nepodařil.",
            )

    def _can_fetch_document(self, document: LegalDocument) -> bool:
        return bool((document.number or "").strip()) and document.year is not None

    def _stamp_matching_current(
        self,
        stored: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        checksum: str,
    ) -> LegalDocumentVersion:
        existing = legal_document_version_service.find_by_source_eli(
            stored.legal_document_id,
            tree.source_eli,
        )
        if existing is not None and existing.id != stored.id:
            self._deactivate_unevaluated_novelizations(
                stored.legal_document_id,
                baseline_version_id=existing.id,
                checksum=checksum,
                source_eli=tree.source_eli,
            )
            legal_document_version_service.retire_source_eli(existing.id)
        stamped = legal_document_version_service.apply_official_wording_identifiers(
            stored.id,
            source_eli=tree.source_eli,
            checksum=checksum,
            effective_from=tree.effective_from,
            source_url=tree.source_url,
        )
        return stamped or stored

    def _replace_with_open_data_tree(
        self,
        document: LegalDocument,
        stored: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        checksum: str,
    ) -> LegalDocumentVersion | None:
        existing = legal_document_version_service.find_by_source_eli(
            document.id,
            tree.source_eli,
        )
        if existing is not None and existing.id != stored.id:
            if not legal_section_service.list_by_version(existing.id, include_inactive=False):
                created = legal_section_service.create_tree_from_parsed(
                    legal_document_id=document.id,
                    legal_document_version_id=existing.id,
                    parsed_sections=list(tree.sections),
                )
                if not created:
                    self._discard_incomplete(existing)
                    return None
            adopted = legal_document_version_service.set_pending_adoption(existing.id, False)
            return adopted or existing

        created_version: LegalDocumentVersion | None = None
        try:
            created_version = legal_document_version_service.create(
                legal_document_id=document.id,
                version_name=detected_version_name(tree.version_label),
                checksum=checksum,
                source_eli=tree.source_eli,
                source_url=tree.source_url,
                effective_from=tree.effective_from,
                publication_date=tree.effective_from,
                pending_adoption=False,
                future_wording=False,
            )
            sections = legal_section_service.create_tree_from_parsed(
                legal_document_id=document.id,
                legal_document_version_id=created_version.id,
                parsed_sections=list(tree.sections),
            )
            if not sections:
                raise ValueError("Nové znění se nepodařilo uložit.")
        except (ValueError, OSError):
            if created_version is not None:
                self._discard_incomplete(created_version)
            return None

        current_after = legal_document_version_service.get_current_version(document.id)
        if current_after is None or current_after.id != created_version.id:
            self._discard_incomplete(created_version)
            return None
        return created_version

    def _annotate_unmapped_sources(
        self,
        document: LegalDocument,
        unresolved_ids: set[int],
    ) -> int:
        links = legal_version_adoption_service._collect_unresolved_links(unresolved_ids)
        if not links:
            return 0
        doc_number = legal_document_regulation_number(document)
        annotated = 0
        for link in links:
            requirement = legal_requirement_service.get_by_id(link.requirement_id)
            if requirement is None:
                continue
            line = f"{UNMAPPED_SOURCE_NOTE_PREFIX} {doc_number} {link.section_label}."
            existing_note = (requirement.note or "").strip()
            if line in existing_note:
                continue
            if UNMAPPED_SOURCE_NOTE_PREFIX in existing_note and link.section_label in existing_note:
                continue
            requirement.note = f"{existing_note}\n{line}".strip() if existing_note else line
            legal_requirement_service.repository.update(requirement)
            annotated += 1
        return annotated

    def _deactivate_unevaluated_novelizations(
        self,
        document_id: int,
        *,
        baseline_version_id: int,
        checksum: str,
        source_eli: str,
    ) -> None:
        note_token = f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{checksum}"
        for change in legal_change_service.list_by_document(document_id, include_inactive=False):
            if change.evaluated:
                continue
            if change.change_type != CHANGE_NOVELIZATION:
                continue
            matches_version = change.new_legal_document_version_id == baseline_version_id
            matches_note = bool(checksum) and note_token in (change.note or "")
            matches_eli = False
            if change.new_legal_document_version_id is not None:
                new_version = legal_document_version_service.get_by_id(
                    change.new_legal_document_version_id,
                )
                matches_eli = (
                    new_version is not None
                    and (new_version.source_eli or "").strip() == source_eli
                )
            if matches_version or matches_note or matches_eli:
                legal_change_service.deactivate(change.id)

    def _discard_incomplete(self, version: LegalDocumentVersion) -> None:
        version.source_eli = None
        version.pending_adoption = False
        version.future_wording = False
        version.active = False
        legal_document_version_service.repository.update(version)


legal_opendata_baseline_service = LegalOpenDataBaselineService()
