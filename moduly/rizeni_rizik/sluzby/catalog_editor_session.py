"""Editorová session Katalogu zdrojů rizik – obsah + AI balíky (UX-SAVE-1b.1).

Veškerá práce s AI balíky během otevřeného editoru probíhá pouze v paměti.
Do DB se zapíše až při finálním Uložit v jedné transakci.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.ai_oponentni.modely.ai_proposal_package import (
    PACKAGE_STATUS_INCORPORATED,
    PACKAGE_STATUS_PENDING,
    PACKAGE_STATUS_REJECTED,
    AiProposalPackageRecord,
)
from core.ai_oponentni.modely.ai_peer_review import AiPeerReview
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.ai_oponentni.repository.ai_peer_review_repository import AiPeerReviewRepository
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.database.session import get_session
from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS,
    HAZARD_LIBRARY_REVISION_REASON_MANUAL,
)
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
    HazardLibraryTemplateRevision,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
    SOURCE_TYPE_HAZARD_CATALOG_SOURCE,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
    HazardLibraryTemplateWorkingCopy,
)

SESSION_PACKAGE_PENDING = "pending"
SESSION_PACKAGE_STAGED = "staged_for_incorporation"
SESSION_PACKAGE_REJECTED = "rejected"


@dataclass
class CatalogSessionPackage:
    """Pracovní balík v editorové session."""

    local_id: int
    review_id: int
    source_type: str
    source_id: int
    package: AiProposalPackage
    session_status: str = SESSION_PACKAGE_PENDING
    db_id: int | None = None
    payload_dirty: bool = False
    is_new: bool = False
    original_status: str = PACKAGE_STATUS_PENDING

    @property
    def display_id(self) -> int:
        """ID pro UI (UserRole) – vždy local_id session."""
        return self.local_id


@dataclass
class _PendingReviewMeta:
    response_text: str = ""
    ai_model: str = ""
    loaded_packages_count: int = 0


@dataclass
class ImportPackagesResult:
    """Výsledek načtení balíků do editorové session."""

    created: list[CatalogSessionPackage]
    duplicate_package_ids: tuple[str, ...] = ()
    no_change_count: int = 0

    @property
    def loaded_count(self) -> int:
        return len(self.created)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicate_package_ids)


class CatalogEditorSession:
    """Jediný zdroj pravdy pro obsah katalogu a AI balíky během editace."""

    def __init__(self, template_id: int, content: HazardLibraryTemplateWorkingCopy):
        self.template_id = template_id
        self.content = content
        self.packages: dict[int, CatalogSessionPackage] = {}
        self._next_temp_id = -1
        self._packages_dirty = False
        self._pending_review_meta: dict[int, _PendingReviewMeta] = {}
        self._source_type = SOURCE_TYPE_HAZARD_CATALOG_SOURCE

    @classmethod
    def load(cls, template_id: int) -> CatalogEditorSession:
        content = HazardLibraryTemplateWorkingCopy.load(template_id)
        session = cls(template_id, content)
        session._load_pending_packages_from_db()
        return session

    def _alloc_temp_id(self) -> int:
        value = self._next_temp_id
        self._next_temp_id -= 1
        return value

    def _load_pending_packages_from_db(self) -> None:
        repo = AiProposalPackageRepository()
        review_repo = AiPeerReviewRepository()
        reviews = review_repo.get_for_source(self._source_type, self.template_id)
        for review in reviews:
            for record in repo.get_pending_for_review(review.id):
                package = repo.package_from_record(record)
                if not package.requires_user_decision:
                    continue
                self.packages[int(record.id)] = CatalogSessionPackage(
                    local_id=int(record.id),
                    review_id=int(record.ai_peer_review_id),
                    source_type=record.source_type,
                    source_id=int(record.source_id),
                    package=package,
                    session_status=SESSION_PACKAGE_PENDING,
                    db_id=int(record.id),
                    payload_dirty=False,
                    is_new=False,
                    original_status=record.status,
                )

    @property
    def is_dirty(self) -> bool:
        if self.content.is_dirty:
            return True
        if self._packages_dirty:
            return True
        if self._pending_review_meta:
            return True
        for item in self.packages.values():
            if item.is_new or item.payload_dirty:
                return True
            if item.session_status == SESSION_PACKAGE_STAGED:
                return True
            if item.session_status == SESSION_PACKAGE_REJECTED and item.db_id is not None:
                return True
        return False

    def list_pending_packages(
        self,
        review_id: int | None = None,
    ) -> list[CatalogSessionPackage]:
        """Balíky ke zobrazení v seznamu pending návrhů."""
        rows = [
            item
            for item in self.packages.values()
            if item.session_status == SESSION_PACKAGE_PENDING
            and item.package.requires_user_decision
            and (review_id is None or item.review_id == review_id)
        ]
        return sorted(
            rows,
            key=lambda item: (
                item.review_id,
                item.db_id if item.db_id is not None else item.local_id,
            ),
        )

    def get_package(self, local_id: int | None) -> CatalogSessionPackage | None:
        if not local_id:
            return None
        return self.packages.get(int(local_id))

    def import_packages(
        self,
        *,
        review_id: int,
        source_type: str,
        packages: list[AiProposalPackage],
        response_text: str = "",
        ai_model: str = "",
    ) -> ImportPackagesResult:
        known_ids = self._known_package_ids_for_review(review_id)
        created: list[CatalogSessionPackage] = []
        duplicates: list[str] = []
        no_change_count = 0
        for package in packages:
            if not package.requires_user_decision:
                # RISK-AI-14: beze_zmen zůstává v response_text, ne ve frontě.
                no_change_count += 1
                continue
            package_id = (package.package_id or "").strip()
            if package_id and package_id in known_ids:
                duplicates.append(package_id)
                continue
            if package_id:
                known_ids.add(package_id)
            local_id = self._alloc_temp_id()
            item = CatalogSessionPackage(
                local_id=local_id,
                review_id=review_id,
                source_type=source_type,
                source_id=self.template_id,
                package=deepcopy(package),
                session_status=SESSION_PACKAGE_PENDING,
                db_id=None,
                payload_dirty=True,
                is_new=True,
                original_status=PACKAGE_STATUS_PENDING,
            )
            self.packages[local_id] = item
            created.append(item)
        self._source_type = source_type
        meta = self._pending_review_meta.get(review_id) or _PendingReviewMeta()
        meta.response_text = response_text
        meta.ai_model = ai_model
        meta.loaded_packages_count = len(created)
        self._pending_review_meta[review_id] = meta
        self._packages_dirty = True
        return ImportPackagesResult(
            created=created,
            duplicate_package_ids=tuple(duplicates),
            no_change_count=no_change_count,
        )

    def _known_package_ids_for_review(self, review_id: int) -> set[str]:
        known: set[str] = set()
        for item in self.packages.values():
            if item.review_id != review_id:
                continue
            package_id = (item.package.package_id or "").strip()
            if package_id:
                known.add(package_id)
        for record in AiProposalPackageRepository().get_for_review(review_id):
            package_id = (record.package_id or "").strip()
            if package_id:
                known.add(package_id)
        return known

    def count_packages_by_status(self, review_id: int) -> tuple[int, int, int]:
        """Vrátí (pending, rejected, staged/accepted) pro konzultaci v session."""
        pending = 0
        rejected = 0
        staged = 0
        tracked_db_ids: set[int] = set()
        for item in self.packages.values():
            if item.review_id != review_id:
                continue
            if not item.package.requires_user_decision:
                continue
            if item.db_id is not None:
                tracked_db_ids.add(int(item.db_id))
            if item.session_status == SESSION_PACKAGE_PENDING:
                pending += 1
            elif item.session_status == SESSION_PACKAGE_REJECTED:
                rejected += 1
            elif item.session_status == SESSION_PACKAGE_STAGED:
                staged += 1
        for record in AiProposalPackageRepository().get_for_review(review_id):
            if int(record.id) in tracked_db_ids:
                continue
            package = AiProposalPackageRepository.package_from_record(record)
            if not package.requires_user_decision:
                continue
            if record.status == PACKAGE_STATUS_PENDING:
                pending += 1
            elif record.status == PACKAGE_STATUS_REJECTED:
                rejected += 1
            elif record.status == PACKAGE_STATUS_INCORPORATED:
                staged += 1
        return pending, rejected, staged

    def sync_review_stats(
        self,
        review_id: int,
        *,
        loaded_packages_count: int | None = None,
    ) -> AiPeerReview | None:
        """Zapíše počty konzultace podle aktuálního stavu session (+ DB)."""
        review = AiPeerReviewRepository().get_by_id(review_id)
        if review is None:
            return None
        pending, rejected, accepted = self.count_packages_by_status(review_id)
        meta = self._pending_review_meta.get(review_id)
        if loaded_packages_count is not None:
            review.loaded_proposals_count = int(loaded_packages_count)
        elif meta is not None and meta.loaded_packages_count:
            review.loaded_proposals_count = int(meta.loaded_packages_count)
        if meta is not None:
            if meta.response_text:
                review.response_text = meta.response_text.strip()
                review.response_loaded_at = datetime.now()
            if meta.ai_model:
                review.ai_model = meta.ai_model.strip()
        review.pending_proposals_count = pending
        review.rejected_count = rejected
        review.accepted_count = accepted
        review.unassigned_count = 0
        return AiPeerReviewRepository().update(review)

    def update_package(self, local_id: int, package: AiProposalPackage) -> CatalogSessionPackage:
        item = self.packages.get(local_id)
        if item is None:
            raise ValueError("Návrhový balík neexistuje v pracovní session.")
        if item.session_status != SESSION_PACKAGE_PENDING:
            raise ValueError("Upravovat lze pouze balík čekající na odborné posouzení.")
        item.package = deepcopy(package)
        item.payload_dirty = True
        self._packages_dirty = True
        return item

    def stage_for_incorporation(self, local_id: int) -> CatalogSessionPackage:
        item = self.packages.get(local_id)
        if item is None:
            raise ValueError("Návrhový balík neexistuje v pracovní session.")
        if not item.package.requires_user_decision:
            raise ValueError(
                "Doporučení „Beze změn“ nelze převzít – nevyžaduje rozhodnutí."
            )
        if item.session_status != SESSION_PACKAGE_PENDING:
            raise ValueError("Zapracovat lze pouze balík čekající na odborné posouzení.")
        item.session_status = SESSION_PACKAGE_STAGED
        self._packages_dirty = True
        self.content._touch(change_reason=HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS)
        return item

    def reject_package(self, local_id: int) -> bool:
        item = self.packages.get(local_id)
        if item is None:
            return False
        if not item.package.requires_user_decision:
            return False
        if item.session_status != SESSION_PACKAGE_PENDING:
            return False
        item.session_status = SESSION_PACKAGE_REJECTED
        self._packages_dirty = True
        return True

    def commit(
        self,
        *,
        basics: dict[str, Any] | None = None,
        bump_revision: bool = True,
    ) -> HazardLibraryTemplate:
        """Zapíše obsah katalogu i AI balíky v jedné transakci."""
        session = get_session()
        review_ids: set[int] = set()
        try:
            template = session.get(HazardLibraryTemplate, self.template_id)
            if template is None:
                raise ValueError("Zdroj rizika neexistuje.")

            if basics is not None:
                template.name = basics["name"]
                template.category = basics["category"]
                template.description = basics.get("description", "")
                template.note = basics.get("note", "")
                template.active = bool(basics.get("active", True))
                if "application_scope" in basics:
                    template.application_scope = basics["application_scope"]
                template.updated_at = datetime.now()

            id_map: dict[int, int] = {}
            self.content._commit_events(session, id_map)
            self.content._commit_legal_links(session)

            staged = [
                item
                for item in self.packages.values()
                if item.session_status == SESSION_PACKAGE_STAGED
            ]
            content_changed = self.content._dirty or bool(staged)

            for item in list(self.packages.values()):
                review_ids.add(item.review_id)
                if item.is_new and item.session_status == SESSION_PACKAGE_PENDING:
                    db_status = PACKAGE_STATUS_PENDING
                elif item.session_status == SESSION_PACKAGE_STAGED:
                    db_status = PACKAGE_STATUS_INCORPORATED
                elif item.session_status == SESSION_PACKAGE_REJECTED:
                    db_status = PACKAGE_STATUS_REJECTED
                else:
                    db_status = PACKAGE_STATUS_PENDING

                if item.is_new:
                    record = AiProposalPackageRepository.record_from_package(
                        review_id=item.review_id,
                        source_type=item.source_type,
                        source_id=item.source_id,
                        package=item.package,
                        status=db_status,
                    )
                    session.add(record)
                    session.flush()
                    item.db_id = int(record.id)
                    item.is_new = False
                else:
                    assert item.db_id is not None
                    record = session.get(AiProposalPackageRecord, item.db_id)
                    if record is None:
                        continue
                    if item.payload_dirty:
                        record.package_id = item.package.package_id
                        record.package_type = item.package.package_type
                        record.target_event_export_id = (
                            item.package.target_event_export_id or ""
                        )
                        record.payload_json = json.dumps(
                            item.package.to_storage_dict(),
                            ensure_ascii=False,
                        )
                    if item.session_status in (
                        SESSION_PACKAGE_STAGED,
                        SESSION_PACKAGE_REJECTED,
                    ):
                        record.status = db_status

            for review_id, meta in self._pending_review_meta.items():
                review_ids.add(review_id)
                review = session.get(AiPeerReview, review_id)
                if review is None:
                    continue
                if meta.response_text:
                    review.response_text = meta.response_text.strip()
                    review.response_loaded_at = datetime.now()
                if meta.ai_model:
                    review.ai_model = meta.ai_model.strip()
                if meta.loaded_packages_count:
                    review.loaded_proposals_count = meta.loaded_packages_count

            if bump_revision and content_changed:
                template.version_number += 1
                template.updated_at = datetime.now()
                if staged:
                    reason = (
                        self.content._pending_change_reason
                        or HAZARD_LIBRARY_REVISION_REASON_AI_PROPOSALS
                    )
                else:
                    reason = (
                        self.content._pending_change_reason
                        or HAZARD_LIBRARY_REVISION_REASON_MANUAL
                    )
                session.add(
                    HazardLibraryTemplateRevision(
                        template_id=template.id,
                        revision_number=template.version_number,
                        change_reason=reason,
                    ),
                )

            session.commit()
            session.refresh(template)
            template_id = int(template.id)
            version_number = int(template.version_number)
            name = template.name
            category = template.category
            description = template.description or ""
            note = template.note or ""
            active = bool(template.active)
            application_scope = template.application_scope
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        for review_id in review_ids:
            HazardLibraryTemplateWorkingCopy._refresh_review_counts(review_id)

        self.content.mark_clean()
        reloaded = HazardLibraryTemplateWorkingCopy.load(self.template_id)
        self.content.events = reloaded.events
        self.content.legal_links = reloaded.legal_links
        self.content._next_temp_id = reloaded._next_temp_id
        self._reload_packages_after_commit()
        return HazardLibraryTemplate(
            id=template_id,
            name=name,
            category=category,
            description=description,
            note=note,
            active=active,
            application_scope=application_scope,
            version_number=version_number,
        )

    def _reload_packages_after_commit(self) -> None:
        self.packages.clear()
        self._packages_dirty = False
        self._pending_review_meta.clear()
        self._next_temp_id = -1
        self._load_pending_packages_from_db()
