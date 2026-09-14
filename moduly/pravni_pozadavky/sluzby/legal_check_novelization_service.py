from dataclasses import dataclass
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
    legal_document_esbirka_opendata_client,
)
from moduly.pravni_pozadavky.modely.legal_change import LegalChange
from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
    legal_document_version_service,
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


class LegalCheckNovelizationService:
    def initialize_reference_state(self, document: LegalDocument) -> NovelizationCheckResult:
        label = legal_document_display_label(document)
        stored_version = legal_document_version_service.get_current_version(document.id)
        if stored_version is None:
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                document_label=label,
            )

        fetched = self._fetch_remote_wording(document, label=label)
        if fetched.status != NOVELIZATION_UNCHANGED:
            return fetched

        return NovelizationCheckResult(
            status=NOVELIZATION_UNCHANGED,
            reference_checksum=fetched.reference_checksum,
            stored_version_id=stored_version.id,
            document_label=label,
            remote=fetched.remote,
        )

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

        fetched = self._fetch_remote_wording(document, label=label)
        if fetched.status == NOVELIZATION_FAILED:
            return fetched
        remote = fetched.remote
        remote_checksum = fetched.reference_checksum
        if remote is None or not remote_checksum:
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error="Neočekávaný formát odpovědi.",
                document_label=label,
            )

        from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service

        existing_change = legal_change_service.find_novelization_by_remote_checksum(
            document.id,
            remote_checksum=remote_checksum,
            note_prefix=NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        )
        comparable_eli = legal_document_esbirka_opendata_client.parse_version_checksum(
            stored_version.checksum,
        )
        if comparable_eli is None:
            self._update_reference_checksum(stored_version, remote_checksum)
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                reference_checksum=remote_checksum,
                stored_version_id=stored_version.id,
                document_label=label,
                remote=remote,
            )

        if comparable_eli == remote.last_wording_eli:
            if existing_change is not None and not self._is_confirmed_by_completed_check(
                existing_change,
            ):
                captured = self._capture_change_for_run(existing_change, check_run_id)
                return NovelizationCheckResult(
                    status=NOVELIZATION_CHANGED,
                    change=captured,
                    reference_checksum=remote_checksum,
                    stored_version_id=stored_version.id,
                    document_label=label,
                    remote=remote,
                )
            return NovelizationCheckResult(
                status=NOVELIZATION_UNCHANGED,
                reference_checksum=remote_checksum,
                stored_version_id=stored_version.id,
                document_label=label,
                remote=remote,
            )

        if existing_change is not None:
            if self._is_confirmed_by_completed_check(existing_change):
                return NovelizationCheckResult(
                    status=NOVELIZATION_UNCHANGED,
                    reference_checksum=remote_checksum,
                    stored_version_id=stored_version.id,
                    document_label=label,
                    remote=remote,
                )
            captured = self._capture_change_for_run(existing_change, check_run_id)
            return NovelizationCheckResult(
                status=NOVELIZATION_CHANGED,
                change=captured,
                reference_checksum=remote_checksum,
                stored_version_id=stored_version.id,
                document_label=label,
                remote=remote,
            )

        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=stored_version.id,
            new_legal_document_version_id=None,
            legal_check_run_id=check_run_id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            description=self._build_description_labels(
                stored_version.version_name,
                detected_version_name(remote.version_label),
            ),
            published_at=remote.effective_from,
            evaluated=False,
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{remote_checksum}",
        )
        return NovelizationCheckResult(
            status=NOVELIZATION_CHANGED,
            change=change,
            reference_checksum=remote_checksum,
            stored_version_id=stored_version.id,
            document_label=label,
            remote=remote,
        )

    def _fetch_remote_wording(
        self,
        document: LegalDocument,
        *,
        label: str,
    ) -> NovelizationCheckResult:
        try:
            wording = legal_document_esbirka_opendata_client.fetch_latest_wording(
                year=document.year if document.year is not None else "",
                number=document.number or "",
            )
        except SafeHttpsError as exc:
            logger.info("Kontrola předpisu %s selhala: %s", label, exc)
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error=str(exc) or "Předpis se nepodařilo ověřit.",
                document_label=label,
            )
        except ValueError as exc:
            logger.info("Kontrola předpisu %s selhala: %s", label, exc)
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error=str(exc) or "Předpis se nepodařilo ověřit.",
                document_label=label,
            )
        except OSError as exc:
            logger.warning("Síťová chyba při kontrole předpisu %s: %s", label, exc)
            return NovelizationCheckResult(
                status=NOVELIZATION_FAILED,
                error="Internet není dostupný.",
                document_label=label,
            )

        return NovelizationCheckResult(
            status=NOVELIZATION_UNCHANGED,
            reference_checksum=legal_document_esbirka_opendata_client.build_version_checksum(
                wording.last_wording_eli,
            ),
            document_label=label,
            remote=wording,
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

    def _update_reference_checksum(
        self,
        stored_version: LegalDocumentVersion,
        remote_checksum: str,
    ) -> None:
        legal_document_version_service.update_checksum(
            stored_version.id,
            remote_checksum,
        )

    def _build_description_labels(self, original_name: str, new_name: str) -> str:
        return (
            f"Původní verze: {original_name}\n"
            f"Nová verze: {new_name}"
        )


legal_check_novelization_service = LegalCheckNovelizationService()
