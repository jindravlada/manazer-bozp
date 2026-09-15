from dataclasses import dataclass
from datetime import date
import logging

from core.http_safe import SafeHttpsError
from moduly.pravni_pozadavky.constants import (
    CHANGE_NOVELIZATION,
    CHECK_RUN_COMPLETED,
    NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
    detected_version_name,
    legal_document_display_label,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
    ESbirkaOpenDataWording,
    format_opendata_fetch_error,
    legal_document_esbirka_opendata_client,
)
from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
    ESbirkaOpenDataParsedTree,
    legal_document_esbirka_opendata_tree_builder,
)
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_version_temporal import (
    is_identified_temporal_version,
)

logger = logging.getLogger(__name__)

NOVELIZATION_UNCHANGED = "unchanged"
NOVELIZATION_CHANGED = "changed"
NOVELIZATION_FAILED = "failed"


@dataclass(frozen=True)
class NovelizationCheckResult:
    status: str
    change: LegalChange | None = None
    error: str | None = None
    reference_checksum: str | None = None
    stored_version_id: int | None = None
    document_label: str = ""
    remote: ESbirkaOpenDataWording | None = None
    tree: ESbirkaOpenDataParsedTree | None = None
    source_eli: str | None = None
    effective_from: date | None = None
    source_url: str | None = None


class LegalCheckNovelizationService:
    def initialize_reference_state(self, document: LegalDocument) -> NovelizationCheckResult:
        label = legal_document_display_label(document)
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                document_label=label,
            )

        fetched = self._fetch_in_force_tree(document, label=label)
        if fetched.status == NOVELIZATION_FAILED:
            return fetched
        tree = fetched.tree
        if tree is None:
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error="Neočekávaný formát odpovědi.",
                document_label=label,
            )

        if not self._trees_match(stored_version, tree):
            self._sync_future_wordings(document)
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                stored_version_id=stored_version.id,
                document_label=label,
                remote=fetched.remote,
                tree=tree,
            )

        result = NovelizationCheckResult(
            status=NOVELIZATION_UNCHANGED,
            reference_checksum=fetched.reference_checksum,
            stored_version_id=stored_version.id,
            document_label=label,
            remote=fetched.remote,
            tree=tree,
            source_eli=tree.source_eli,
            effective_from=tree.effective_from,
            source_url=tree.source_url,
        )
        self._sync_future_wordings(document)
        return result

    def check_document(
        self,
        document: LegalDocument,
        *,
        check_run_id: int,
    ) -> NovelizationCheckResult:
        label = legal_document_display_label(document)
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                document_label=label,
            )

        fetched = self._fetch_in_force_tree(document, label=label)
        if fetched.status == NOVELIZATION_FAILED:
            return fetched
        tree = fetched.tree
        remote_checksum = fetched.reference_checksum
        if tree is None or not remote_checksum:
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error="Neočekávaný formát odpovědi.",
                document_label=label,
            )

        existing_for_eli = legal_document_version_service.find_by_source_eli(
            document.id,
            tree.source_eli,
        )
        existing_change = self._find_recorded_change(
            document.id,
            remote_checksum=remote_checksum,
            pending=(
                existing_for_eli
                if existing_for_eli is not None
                and (existing_for_eli.pending_adoption or existing_for_eli.future_wording)
                else None
            ),
        )
        content_matches = self._trees_match(stored_version, tree)

        if (
            existing_for_eli is not None
            and existing_for_eli.id != stored_version.id
            and (existing_for_eli.future_wording or existing_for_eli.pending_adoption)
        ):
            pending = self._promote_existing_detected_version(
                document,
                existing_for_eli,
                tree,
                remote_checksum,
            )
            if pending is None:
                return self._finish_with_futures(
                    document,
                    NovelizationCheckResult(
                        status=NOVELIZATION_FAILED,
                        error="Nové znění se nepodařilo uložit.",
                        document_label=label,
                        remote=fetched.remote,
                        tree=tree,
                    ),
                    skip_eli=tree.source_eli,
                )
            return self._finish_with_futures(
                document,
                self._reuse_recorded_change(
                    document=document,
                    stored_version=stored_version,
                    tree=tree,
                    remote_checksum=remote_checksum,
                    check_run_id=check_run_id,
                    pending=pending,
                    existing_change=existing_change,
                    label=label,
                ),
                skip_eli=tree.source_eli,
            )

        if content_matches:
            self._stamp_identifiers_if_needed(stored_version, tree, remote_checksum)
            return self._finish_with_futures(
                document,
                NovelizationCheckResult(
                    status=NOVELIZATION_UNCHANGED,
                    reference_checksum=remote_checksum,
                    stored_version_id=stored_version.id,
                    document_label=label,
                    remote=fetched.remote,
                    tree=tree,
                    source_eli=tree.source_eli,
                    effective_from=tree.effective_from,
                    source_url=tree.source_url,
                ),
                skip_eli=tree.source_eli,
            )

        if (
            existing_for_eli is not None
            and not existing_for_eli.pending_adoption
            and existing_for_eli.id == stored_version.id
        ):
            return self._finish_with_futures(
                document,
                NovelizationCheckResult(
                    status=NOVELIZATION_FAILED,
                    error="Oficiální znění má stejné ELI, ale odlišný obsah.",
                    document_label=label,
                    remote=fetched.remote,
                    tree=tree,
                ),
                skip_eli=tree.source_eli,
            )

        if existing_change is not None and self._is_confirmed_by_completed_check(existing_change):
            pending = self._ensure_pending_version(
                document,
                stored_version,
                tree,
                remote_checksum,
                existing_pending=existing_for_eli if existing_for_eli and existing_for_eli.pending_adoption else None,
            )
            if pending is None:
                return self._finish_with_futures(
                    document,
                    NovelizationCheckResult(
                        status=NOVELIZATION_FAILED,
                        error="Nové znění se nepodařilo uložit.",
                        document_label=label,
                    ),
                    skip_eli=tree.source_eli,
                )
            if existing_change.new_legal_document_version_id != pending.id:
                from moduly.pravni_pozadavky.sluzby.legal_change_service import (
                    legal_change_service,
                )

                legal_change_service.attach_detected_version(existing_change.id, pending.id)
                existing_change = legal_change_service.get_by_id(existing_change.id) or existing_change
            self._sync_change_sections(existing_change)
            return self._finish_with_futures(
                document,
                NovelizationCheckResult(
                    status=NOVELIZATION_UNCHANGED,
                    reference_checksum=remote_checksum,
                    stored_version_id=stored_version.id,
                    document_label=label,
                    remote=fetched.remote,
                    tree=tree,
                ),
                skip_eli=tree.source_eli,
            )

        pending = self._ensure_pending_version(
            document,
            stored_version,
            tree,
            remote_checksum,
            existing_pending=existing_for_eli if existing_for_eli and existing_for_eli.pending_adoption else None,
        )
        if pending is None:
            return self._finish_with_futures(
                document,
                NovelizationCheckResult(
                    status=NOVELIZATION_FAILED,
                    error="Nové znění se nepodařilo uložit.",
                    document_label=label,
                ),
                skip_eli=tree.source_eli,
            )

        change = self._ensure_legal_change(
            document=document,
            stored_version=stored_version,
            pending=pending,
            tree=tree,
            remote_checksum=remote_checksum,
            check_run_id=check_run_id,
            existing_change=existing_change,
        )
        self._sync_change_sections(change)
        return self._finish_with_futures(
            document,
            NovelizationCheckResult(
                status=NOVELIZATION_CHANGED,
                change=change,
                reference_checksum=remote_checksum,
                stored_version_id=stored_version.id,
                document_label=label,
                remote=fetched.remote,
                tree=tree,
            ),
            skip_eli=tree.source_eli,
        )

    def _finish_with_futures(
        self,
        document: LegalDocument,
        result: NovelizationCheckResult,
        *,
        skip_eli: str | None = None,
    ) -> NovelizationCheckResult:
        self._sync_future_wordings(document, skip_eli=skip_eli)
        return result

    def _promote_existing_detected_version(
        self,
        document: LegalDocument,
        existing: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        remote_checksum: str,
    ) -> LegalDocumentVersion | None:
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return None
        if existing.pending_adoption:
            return self._ensure_pending_version(
                document,
                stored_version,
                tree,
                remote_checksum,
                existing_pending=existing,
            )
        if not existing.future_wording:
            return None
        if not self._trees_match(existing, tree):
            legal_document_version_service.retire_source_eli(existing.id)
            return self._ensure_pending_version(
                document,
                stored_version,
                tree,
                remote_checksum,
                existing_pending=None,
            )
        return legal_document_version_service.set_pending_adoption(existing.id, True)

    def _sync_future_wordings(
        self,
        document: LegalDocument,
        *,
        skip_eli: str | None = None,
    ) -> None:
        try:
            wordings = legal_document_esbirka_opendata_client.fetch_temporal_wordings(
                year=document.year if document.year is not None else "",
                number=document.number or "",
            )
        except (SafeHttpsError, ValueError, OSError) as exc:
            logger.info(
                "Budoucí znění předpisu %s se nepodařilo načíst: %s",
                legal_document_display_label(document),
                exc,
            )
            return

        futures = legal_document_esbirka_opendata_client.select_future_wordings(
            wordings,
            date.today(),
        )
        skipped = (skip_eli or "").strip()
        current = legal_document_version_service.get_current_version(document.id)
        for wording in futures:
            if not wording.source_eli or wording.source_eli == skipped:
                continue
            try:
                tree = legal_document_esbirka_opendata_tree_builder.fetch_tree_for_source_eli(
                    wording.source_eli,
                )
            except (SafeHttpsError, ValueError, OSError) as exc:
                logger.info(
                    "Budoucí znění %s předpisu %s se nepodařilo sestavit: %s",
                    wording.source_eli,
                    legal_document_display_label(document),
                    exc,
                )
                continue
            self._ensure_future_version(document, tree, current)

    def _ensure_future_version(
        self,
        document: LegalDocument,
        tree: ESbirkaOpenDataParsedTree,
        current: LegalDocumentVersion | None,
    ) -> LegalDocumentVersion | None:
        from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

        checksum = legal_document_esbirka_opendata_client.build_version_checksum(tree.source_eli)
        existing = legal_document_version_service.find_by_source_eli(document.id, tree.source_eli)
        if existing is not None:
            if current is not None and existing.id == current.id:
                return existing
            if existing.pending_adoption:
                return existing
            if existing.future_wording:
                if self._trees_match(existing, tree):
                    return existing
                legal_document_version_service.retire_source_eli(existing.id)
            else:
                return existing

        created = None
        try:
            created = legal_document_version_service.create(
                legal_document_id=document.id,
                version_name=detected_version_name(tree.version_label),
                checksum=checksum,
                source_eli=tree.source_eli,
                source_url=tree.source_url,
                effective_from=tree.effective_from,
                publication_date=tree.effective_from,
                pending_adoption=False,
                future_wording=True,
            )
            sections = legal_section_service.create_tree_from_parsed(
                legal_document_id=document.id,
                legal_document_version_id=created.id,
                parsed_sections=list(tree.sections),
            )
            if not sections:
                raise ValueError("Nové znění se nepodařilo uložit.")
        except (ValueError, OSError) as exc:
            if created is not None:
                self._discard_incomplete_pending(created)
            logger.info(
                "Uložení budoucího znění předpisu %s selhalo: %s",
                legal_document_display_label(document),
                exc,
            )
            return None

        current_after = legal_document_version_service.get_current_version(document.id)
        if current is not None and (current_after is None or current_after.id != current.id):
            self._discard_incomplete_pending(created)
            return None
        return created

    def _fetch_in_force_tree(
        self,
        document: LegalDocument,
        *,
        label: str,
    ) -> NovelizationCheckResult:
        try:
            tree = legal_document_esbirka_opendata_tree_builder.fetch_in_force_tree(
                year=document.year if document.year is not None else "",
                number=document.number or "",
                on_date=date.today(),
            )
        except SafeHttpsError as exc:
            logger.info("Kontrola předpisu %s selhala: %s", label, exc)
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error=format_opendata_fetch_error(
                    kind=exc.kind,
                    endpoint="-",
                    status_code=exc.status_code,
                    detail=str(exc),
                ),
                document_label=label,
            )
        except ValueError as exc:
            logger.info("Kontrola předpisu %s selhala: %s", label, exc)
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error=str(exc) or "ověření se nezdařilo.",
                document_label=label,
            )
        except OSError as exc:
            logger.warning("Síťová chyba při kontrole předpisu %s: %s", label, exc)
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error=format_opendata_fetch_error(
                    kind="network",
                    endpoint="-",
                    detail=str(exc) or "síťová chyba",
                ),
                document_label=label,
            )

        remote = ESbirkaOpenDataWording(
            last_wording_eli=tree.source_eli,
            source_url=tree.source_url,
            effective_from=tree.effective_from,
            version_label=tree.version_label,
        )
        return NovelizationCheckResult(
            status=NOVELIZATION_UNCHANGED,
            reference_checksum=legal_document_esbirka_opendata_client.build_version_checksum(
                tree.source_eli,
            ),
            document_label=label,
            remote=remote,
            tree=tree,
            source_eli=tree.source_eli,
            effective_from=tree.effective_from,
            source_url=tree.source_url,
        )

    def _trees_match(
        self,
        stored_version: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
    ) -> bool:
        from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
        from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
            legal_section_structure_compare_service,
        )

        stored_sections = legal_section_service.list_by_version(
            stored_version.id,
            include_inactive=False,
        )
        return legal_section_structure_compare_service.trees_content_equal(
            stored_sections=stored_sections,
            parsed_sections=list(tree.sections),
        )

    def _stamp_identifiers_if_needed(
        self,
        stored_version: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        remote_checksum: str,
    ) -> None:
        current_eli = (stored_version.source_eli or "").strip()
        identified = is_identified_temporal_version(stored_version)
        checksum_matches = (stored_version.checksum or "").strip() == remote_checksum
        if identified and current_eli == tree.source_eli and checksum_matches:
            return
        legal_document_version_service.apply_official_wording_identifiers(
            stored_version.id,
            source_eli=tree.source_eli,
            checksum=remote_checksum,
            effective_from=tree.effective_from,
            source_url=tree.source_url,
        )

    def _find_recorded_change(
        self,
        document_id: int,
        *,
        remote_checksum: str,
        pending: LegalDocumentVersion | None,
    ) -> LegalChange | None:
        from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

        change = legal_change_service.find_novelization_by_remote_checksum(
            document_id,
            remote_checksum=remote_checksum,
            note_prefix=NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        )
        if change is not None:
            return change
        if pending is None:
            return None
        for item in legal_change_service.list_by_document(document_id, include_inactive=False):
            if item.change_type != CHANGE_NOVELIZATION:
                continue
            if item.new_legal_document_version_id == pending.id:
                return item
        return None

    def _reuse_recorded_change(
        self,
        *,
        document: LegalDocument,
        stored_version: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        remote_checksum: str,
        check_run_id: int,
        pending: LegalDocumentVersion,
        existing_change: LegalChange | None,
        label: str,
    ) -> NovelizationCheckResult:
        if existing_change is not None and self._is_confirmed_by_completed_check(existing_change):
            if existing_change.new_legal_document_version_id != pending.id:
                from moduly.pravni_pozadavky.sluzby.legal_change_service import (
                    legal_change_service,
                )

                legal_change_service.attach_detected_version(existing_change.id, pending.id)
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                reference_checksum=remote_checksum,
                stored_version_id=stored_version.id,
                document_label=label,
                remote=self._remote_from_tree(tree),
                tree=tree,
            )

        change = self._ensure_legal_change(
            document=document,
            stored_version=stored_version,
            pending=pending,
            tree=tree,
            remote_checksum=remote_checksum,
            check_run_id=check_run_id,
            existing_change=existing_change,
        )
        self._sync_change_sections(change)
        return NovelizationCheckResult(
            status=NOVELIZATION_CHANGED,
            change=change,
            reference_checksum=remote_checksum,
            stored_version_id=stored_version.id,
            document_label=label,
            remote=self._remote_from_tree(tree),
            tree=tree,
        )

    def _ensure_pending_version(
        self,
        document: LegalDocument,
        stored_version: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        remote_checksum: str,
        *,
        existing_pending: LegalDocumentVersion | None,
    ) -> LegalDocumentVersion | None:
        from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service

        if existing_pending is not None and existing_pending.pending_adoption:
            existing_sections = legal_section_service.list_by_version(
                existing_pending.id,
                include_inactive=False,
            )
            if existing_sections:
                return existing_pending
            try:
                created = legal_section_service.create_tree_from_parsed(
                    legal_document_id=document.id,
                    legal_document_version_id=existing_pending.id,
                    parsed_sections=list(tree.sections),
                )
                if not created:
                    raise ValueError("Nové znění se nepodařilo uložit.")
            except (ValueError, OSError):
                self._discard_incomplete_pending(existing_pending)
                logger.info(
                    "Uložení pending znění předpisu %s selhalo.",
                    legal_document_display_label(document),
                )
                return None
            return existing_pending

        pending = None
        try:
            pending = legal_document_version_service.create(
                legal_document_id=document.id,
                version_name=detected_version_name(tree.version_label),
                checksum=remote_checksum,
                source_eli=tree.source_eli,
                source_url=tree.source_url,
                effective_from=tree.effective_from,
                publication_date=tree.effective_from,
                pending_adoption=True,
            )
            created = legal_section_service.create_tree_from_parsed(
                legal_document_id=document.id,
                legal_document_version_id=pending.id,
                parsed_sections=list(tree.sections),
            )
            if not created:
                raise ValueError("Nové znění se nepodařilo uložit.")
        except (ValueError, OSError):
            if pending is not None:
                self._discard_incomplete_pending(pending)
            logger.info(
                "Uložení pending znění předpisu %s selhalo.",
                legal_document_display_label(document),
            )
            return None

        current_after = legal_document_version_service.get_current_version(document.id)
        if current_after is None or current_after.id != stored_version.id:
            self._discard_incomplete_pending(pending)
            return None
        return pending

    def _discard_incomplete_pending(self, pending: LegalDocumentVersion) -> None:
        pending.source_eli = None
        pending.pending_adoption = True
        pending.future_wording = False
        pending.active = False
        legal_document_version_service.repository.update(pending)

    def _ensure_legal_change(
        self,
        *,
        document: LegalDocument,
        stored_version: LegalDocumentVersion,
        pending: LegalDocumentVersion,
        tree: ESbirkaOpenDataParsedTree,
        remote_checksum: str,
        check_run_id: int,
        existing_change: LegalChange | None,
    ) -> LegalChange:
        from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

        description = self._build_description_labels(
            stored_version.version_name,
            detected_version_name(tree.version_label),
        )
        if existing_change is None:
            return legal_change_service.create(
                legal_document_id=document.id,
                legal_document_version_id=stored_version.id,
                new_legal_document_version_id=pending.id,
                legal_check_run_id=check_run_id,
                change_type=CHANGE_NOVELIZATION,
                title="Předpis byl novelizován.",
                description=description,
                published_at=tree.effective_from,
                evaluated=False,
                note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{remote_checksum}",
            )

        if existing_change.new_legal_document_version_id != pending.id:
            legal_change_service.attach_detected_version(
                existing_change.id,
                pending.id,
                description=description,
            )
        captured = self._capture_change_for_run(existing_change, check_run_id)
        return legal_change_service.get_by_id(captured.id) or captured

    def _sync_change_sections(self, change: LegalChange) -> None:
        from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
            legal_change_section_service,
        )

        legal_change_section_service.sync_version_content_changes(change)

    def _remote_from_tree(self, tree: ESbirkaOpenDataParsedTree) -> ESbirkaOpenDataWording:
        return ESbirkaOpenDataWording(
            last_wording_eli=tree.source_eli,
            source_url=tree.source_url,
            effective_from=tree.effective_from,
            version_label=tree.version_label,
        )

    def _capture_change_for_run(self, change: LegalChange, check_run_id: int) -> LegalChange:
        from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

        if change.legal_check_run_id == check_run_id:
            return change
        updated = legal_change_service.attach_to_check_run(change.id, check_run_id)
        return updated or change

    def _is_confirmed_by_completed_check(self, change: LegalChange) -> bool:
        if change.legal_check_run_id is None:
            return True
        from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
            legal_check_run_service,
        )

        run = legal_check_run_service.get_by_id(change.legal_check_run_id)
        if run is None:
            return False
        return run.status == CHECK_RUN_COMPLETED

    def _build_description_labels(self, original_name: str, new_name: str) -> str:
        return (
            f"Původní verze: {original_name}\n"
            f"Nová verze: {new_name}"
        )


legal_check_novelization_service = LegalCheckNovelizationService()
