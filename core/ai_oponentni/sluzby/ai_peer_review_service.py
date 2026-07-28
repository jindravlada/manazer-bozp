"""Obecná služba exportu a evidence oponentního posouzení AI."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_CATALOG_REQUIRES_SCHEMA_2_0,
    AI_PEER_REVIEW_PARSE_NO_PACKAGES,
    AI_PEER_REVIEW_PARSE_NO_PROPOSALS,
    AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
    AI_PEER_REVIEW_ZIP_FILES,
)
from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
from core.ai_oponentni.modely.ai_proposal_package import (
    AiProposalPackageRecord,
    PACKAGE_STATUS_PENDING,
    PACKAGE_STATUS_REJECTED,
)
from core.ai_oponentni.modely.ai_unassigned_proposal import (
    AiUnassignedProposal,
    PROPOSAL_STATUS_REJECTED,
)
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.ai_oponentni.repository.ai_peer_review_batch_repository import (
    AiPeerReviewBatchRepository,
)
from core.ai_oponentni.repository.ai_peer_review_repository import AiPeerReviewRepository
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.ai_oponentni.repository.ai_unassigned_proposal_repository import (
    AiUnassignedProposalRepository,
)
from core.ai_oponentni.sluzby.response_parser import (
    AiPeerReviewParseError,
    parse_ai_peer_review_response,
)
from core.ai_oponentni.types import (
    AiPeerReviewBatchContent,
    AiPeerReviewExportContent,
    AiPeerReviewExportOptions,
    AiPeerReviewParseResult,
    AiPeerReviewProvider,
    AiProposal,
)


class AiPeerReviewError(ValueError):
    pass


@dataclass
class AiPeerReviewExportResult:
    review: AiPeerReview
    file_path: Path
    summary_lines: list[str]
    batch_count: int = 1


class AiPeerReviewService:
    def __init__(self):
        self.repository = AiPeerReviewRepository()
        self.batch_repository = AiPeerReviewBatchRepository()
        self.unassigned_repository = AiUnassignedProposalRepository()
        self.package_repository = AiProposalPackageRepository()

    def get_for_source(self, source_type: str, source_id: int) -> list[AiPeerReview]:
        return self.repository.get_for_source(source_type, source_id)

    def get_by_id(self, review_id: int | None) -> AiPeerReview | None:
        if not review_id:
            return None
        return self.repository.get_by_id(review_id)

    def get_batches_for_review(self, review_id: int) -> list[AiPeerReviewBatch]:
        return self.batch_repository.get_for_review(review_id)

    def get_unassigned_for_review(self, review_id: int):
        return self.unassigned_repository.get_for_review(review_id)

    def get_packages_for_review(self, review_id: int) -> list[AiProposalPackageRecord]:
        return self.package_repository.get_for_review(review_id)

    def get_package_models_for_review(self, review_id: int) -> list[AiProposalPackage]:
        return [
            self.package_repository.package_from_record(record)
            for record in self.get_packages_for_review(review_id)
        ]

    def delete_packages_for_review(self, review_id: int) -> None:
        self.package_repository.delete_for_review(review_id)

    def delete_import_data_for_review(self, review_id: int) -> None:
        self.delete_proposals_for_review(review_id)
        self.delete_packages_for_review(review_id)

    def get_proposal_by_id(self, proposal_id: int):
        return self.unassigned_repository.get_by_id(proposal_id)

    def update_proposal(self, proposal) -> None:
        self.unassigned_repository.update(proposal)

    def delete_proposals_for_review(self, review_id: int) -> None:
        self.unassigned_repository.delete_for_review(review_id)

    def clone_consultation_for_new_import(self, review_id: int) -> AiPeerReview:
        source = self.repository.get_by_id(review_id)
        if source is None:
            raise AiPeerReviewError("Záznam konzultace neexistuje.")

        clone = AiPeerReview(
            source_type=source.source_type,
            source_id=source.source_id,
            exported_at=source.exported_at,
            export_file_path=source.export_file_path,
            export_id_map_json=source.export_id_map_json,
            export_scope=source.export_scope,
            batch_count=source.batch_count,
            selected_source_count=source.selected_source_count,
            total_object_count=source.total_object_count,
            ai_model="",
            prompt_text=source.prompt_text,
            response_text="",
            response_loaded_at=None,
            loaded_proposals_count=0,
            pending_proposals_count=0,
            accepted_count=0,
            rejected_count=0,
            unassigned_count=0,
        )
        saved = self.repository.add(clone)
        batches = self.batch_repository.get_for_review(review_id)
        if batches:
            self.batch_repository.add_many(
                [
                    AiPeerReviewBatch(
                        ai_peer_review_id=saved.id,
                        batch_number=batch.batch_number,
                        source_count=batch.source_count,
                        object_count=batch.object_count,
                        filename=batch.filename,
                        recommended_limit_exceeded=batch.recommended_limit_exceeded,
                    )
                    for batch in batches
                ],
            )
        return saved

    @staticmethod
    def _proposal_model(
        *,
        review_id: int,
        source_type: str,
        source_id: int,
        proposal: AiProposal,
        status: str,
    ) -> AiUnassignedProposal:
        return AiUnassignedProposal(
            ai_peer_review_id=review_id,
            source_type=source_type,
            source_id=source_id,
            proposal_id=(proposal.proposal_id or "").strip(),
            area=proposal.area or "",
            name=proposal.name,
            reasoning=proposal.reasoning or "",
            parent_export_id=proposal.parent_export_id or "",
            exposed_group_id=proposal.exposed_group_id,
            status=status,
        )

    def store_rejected_proposals(
        self,
        *,
        review_id: int,
        source_type: str,
        source_id: int,
        proposals: list[AiProposal],
    ) -> None:
        if not proposals:
            return
        models = [
            self._proposal_model(
                review_id=review_id,
                source_type=source_type,
                source_id=source_id,
                proposal=proposal,
                status=PROPOSAL_STATUS_REJECTED,
            )
            for proposal in proposals
        ]
        self.unassigned_repository.add_many(models)

    def default_export_filename(self, source_label: str, exported_at: datetime) -> str:
        stamp = exported_at.strftime("%Y-%m-%d_%H%M")
        safe = (
            (source_label or "posouzeni")
            .replace("/", "-")
            .replace(" ", "_")
            .replace(":", "-")
        )
        return f"AI_oponentura_{safe}_{stamp}.zip"

    def export_package(
        self,
        provider: AiPeerReviewProvider,
        source_id: int | None,
        target_path: Path | str,
        *,
        options: AiPeerReviewExportOptions | None = None,
    ) -> AiPeerReviewExportResult:
        if not provider.can_export(source_id) or not source_id:
            raise AiPeerReviewError(
                "Export je možné provést až po uložení zdrojového záznamu."
            )

        export_options = options or AiPeerReviewExportOptions()
        content = provider.build_export_content(source_id, options=export_options)
        if not content.batches:
            raise AiPeerReviewError(
                "Identifikace neobsahuje žádný aktivní zdroj analýzy. Export nelze vytvořit."
            )
        for batch in content.batches:
            if not batch.zadani_json or not batch.schema_json:
                raise AiPeerReviewError(
                    "Doménový poskytovatel musí dodat zadani.json a schema_odpovedi.json."
                )

        exported_at = datetime.now()
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._write_export_archive(target, content)
        except OSError as error:
            target.unlink(missing_ok=True)
            raise AiPeerReviewError(
                f"Nepodařilo se vytvořit exportní soubor: {error}"
            ) from error

        try:
            self._validate_written_archive(target, content)
        except AiPeerReviewError:
            target.unlink(missing_ok=True)
            raise

        prompt_for_record = content.batches[0].prompt_text
        try:
            review = AiPeerReview(
                source_type=provider.source_type,
                source_id=source_id,
                exported_at=exported_at,
                export_file_path=str(target.resolve()),
                export_id_map_json=json.dumps(
                    content.export_id_map or {},
                    ensure_ascii=False,
                ),
                export_scope=content.export_scope,
                batch_count=content.batch_count,
                selected_source_count=content.selected_source_count,
                total_object_count=content.total_object_count,
                ai_model="",
                prompt_text=prompt_for_record,
                response_text="",
                accepted_count=0,
                rejected_count=0,
                unassigned_count=0,
            )
            saved = self.repository.add(review)
            batch_rows = [
                AiPeerReviewBatch(
                    ai_peer_review_id=saved.id,
                    batch_number=batch.batch_number,
                    source_count=batch.source_count,
                    object_count=batch.object_count,
                    filename=batch.filename
                    or self._batch_inner_filename(batch.batch_number, content.batch_count),
                    recommended_limit_exceeded=batch.recommended_limit_exceeded,
                )
                for batch in content.batches
            ]
            self.batch_repository.add_many(batch_rows)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        summary_lines = list(content.summary_lines)
        if content.batch_count > 1:
            summary_lines = [
                f"Počet dávek: {content.batch_count}",
                f"Celkem objektů: {content.total_object_count}",
                *summary_lines,
            ]

        return AiPeerReviewExportResult(
            review=saved,
            file_path=target,
            summary_lines=summary_lines,
            batch_count=content.batch_count,
        )

    def _batch_inner_filename(self, batch_number: int, batch_count: int) -> str:
        if batch_count <= 1:
            return ""
        return f"davka_{batch_number:03d}.zip"

    def _write_batch_bytes(self, batch: AiPeerReviewBatchContent) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("pokyn_pro_AI.txt", batch.prompt_text.rstrip() + "\n")
            zf.writestr("data.txt", batch.data_text.rstrip() + "\n")
            zf.writestr("prehled.txt", batch.overview_text.rstrip() + "\n")
            zf.writestr(
                "zadani.json",
                json.dumps(batch.zadani_json, ensure_ascii=False, indent=2) + "\n",
            )
            zf.writestr(
                "schema_odpovedi.json",
                json.dumps(batch.schema_json, ensure_ascii=False, indent=2) + "\n",
            )
        return buffer.getvalue()

    def _write_export_archive(
        self,
        target: Path,
        content: AiPeerReviewExportContent,
    ) -> None:
        if content.batch_count == 1:
            batch = content.batches[0]
            batch.filename = target.name
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("pokyn_pro_AI.txt", batch.prompt_text.rstrip() + "\n")
                zf.writestr("data.txt", batch.data_text.rstrip() + "\n")
                zf.writestr("prehled.txt", batch.overview_text.rstrip() + "\n")
                zf.writestr(
                    "zadani.json",
                    json.dumps(batch.zadani_json, ensure_ascii=False, indent=2) + "\n",
                )
                zf.writestr(
                    "schema_odpovedi.json",
                    json.dumps(batch.schema_json, ensure_ascii=False, indent=2) + "\n",
                )
            return

        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as outer:
            for batch in content.batches:
                filename = f"davka_{batch.batch_number:03d}.zip"
                batch.filename = filename
                outer.writestr(filename, self._write_batch_bytes(batch))
            overview = content.batches_overview_text or ""
            outer.writestr("prehled_davek.txt", overview.rstrip() + "\n")

    def _validate_written_archive(
        self,
        target: Path,
        content: AiPeerReviewExportContent,
    ) -> None:
        try:
            with zipfile.ZipFile(target, "r") as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as error:
            raise AiPeerReviewError("Vytvořený exportní ZIP je neplatný.") from error

        if content.batch_count == 1:
            if names != set(AI_PEER_REVIEW_ZIP_FILES):
                raise AiPeerReviewError(
                    "Exportní balíček neobsahuje očekávané soubory."
                )
            return

        expected = {f"davka_{n:03d}.zip" for n in range(1, content.batch_count + 1)}
        expected.add("prehled_davek.txt")
        if names != expected:
            raise AiPeerReviewError(
                "Exportní balíček s dávkami neobsahuje očekávané soubory."
            )
        with zipfile.ZipFile(target, "r") as outer:
            for batch_name in sorted(expected - {"prehled_davek.txt"}):
                try:
                    with zipfile.ZipFile(io.BytesIO(outer.read(batch_name)), "r") as inner:
                        inner_names = set(inner.namelist())
                except zipfile.BadZipFile as error:
                    raise AiPeerReviewError(
                        f"Vnitřní dávka {batch_name} je neplatný ZIP."
                    ) from error
                if inner_names != set(AI_PEER_REVIEW_ZIP_FILES):
                    raise AiPeerReviewError(
                        f"Dávka {batch_name} neobsahuje očekávané soubory."
                    )

    def parse_response(
        self,
        response_text: str,
        *,
        expected_source_identification_number: str | None = None,
        require_proposal_packages: bool = False,
    ) -> AiPeerReviewParseResult:
        try:
            result = parse_ai_peer_review_response(
                response_text,
                expected_source_identification_number=(
                    expected_source_identification_number
                ),
                require_proposal_packages=require_proposal_packages,
            )
        except AiPeerReviewParseError as error:
            raise AiPeerReviewError(str(error)) from error
        if require_proposal_packages:
            if result.schema_version and result.schema_version != AI_PEER_REVIEW_SCHEMA_VERSION_2_0:
                raise AiPeerReviewError(AI_PEER_REVIEW_CATALOG_REQUIRES_SCHEMA_2_0)
            if result.proposals:
                raise AiPeerReviewError(AI_PEER_REVIEW_CATALOG_REQUIRES_SCHEMA_2_0)
            if not result.packages:
                raise AiPeerReviewError(AI_PEER_REVIEW_PARSE_NO_PACKAGES)
            return result
        if not result.proposals:
            raise AiPeerReviewError(AI_PEER_REVIEW_PARSE_NO_PROPOSALS)
        return result

    @staticmethod
    def provider_uses_proposal_packages(provider: AiPeerReviewProvider) -> bool:
        return bool(getattr(provider, "uses_proposal_packages", False))

    def filter_new_packages_for_review(
        self,
        *,
        review_id: int,
        packages: list[AiProposalPackage],
    ) -> tuple[list[AiProposalPackage], list[str]]:
        """Oddělí nové balíky od duplicit podle package_id v rámci konzultace."""
        existing = {
            (record.package_id or "").strip()
            for record in self.package_repository.get_for_review(review_id)
            if (record.package_id or "").strip()
        }
        accepted: list[AiProposalPackage] = []
        duplicates: list[str] = []
        seen_in_batch: set[str] = set()
        for package in packages:
            package_id = (package.package_id or "").strip()
            if package_id and (package_id in existing or package_id in seen_in_batch):
                duplicates.append(package_id)
                continue
            if package_id:
                seen_in_batch.add(package_id)
            accepted.append(package)
        return accepted, duplicates

    def store_rejected_packages(
        self,
        *,
        review_id: int,
        source_type: str,
        source_id: int,
        packages: list[AiProposalPackage],
    ) -> None:
        if not packages:
            return
        records = [
            AiProposalPackageRepository.record_from_package(
                review_id=review_id,
                source_type=source_type,
                source_id=source_id,
                package=package,
                status=PACKAGE_STATUS_REJECTED,
            )
            for package in packages
        ]
        self.package_repository.add_many(records)

    def finalize_package_import(
        self,
        *,
        provider: AiPeerReviewProvider,
        source_id: int,
        review_id: int,
        response_text: str,
        ai_model: str,
        accepted: list[AiProposalPackage],
        rejected: list[AiProposalPackage],
        loaded_packages_count: int | None = None,
    ) -> AiPeerReview:
        review = self.repository.get_by_id(review_id)
        if review is None:
            raise AiPeerReviewError("Záznam konzultace neexistuje.")
        if review.source_type != provider.source_type or review.source_id != source_id:
            raise AiPeerReviewError("Konzultace nepatří k aktuálnímu záznamu.")

        pending = 0
        if accepted:
            result = provider.apply_proposal_packages(
                source_id,
                accepted,
                review_id=review_id,
            )
            pending = result.pending_count

        self.store_rejected_packages(
            review_id=review_id,
            source_type=provider.source_type,
            source_id=source_id,
            packages=rejected,
        )

        review.ai_model = (ai_model or "").strip()
        review.response_text = response_text.strip()
        review.response_loaded_at = datetime.now()
        review.loaded_proposals_count = (
            loaded_packages_count
            if loaded_packages_count is not None
            else len(accepted) + len(rejected)
        )
        review.pending_proposals_count = pending
        review.accepted_count = 0
        review.rejected_count = len(rejected)
        review.unassigned_count = 0
        return self.repository.update(review)

    def finalize_import(
        self,
        *,
        provider: AiPeerReviewProvider,
        source_id: int,
        review_id: int,
        response_text: str,
        ai_model: str,
        accepted: list[AiProposal],
        rejected: list[AiProposal],
        loaded_proposals_count: int | None = None,
    ) -> AiPeerReview:
        review = self.repository.get_by_id(review_id)
        if review is None:
            raise AiPeerReviewError("Záznam konzultace neexistuje.")
        if review.source_type != provider.source_type or review.source_id != source_id:
            raise AiPeerReviewError("Konzultace nepatří k aktuálnímu záznamu.")

        try:
            export_id_map = json.loads(review.export_id_map_json or "{}")
        except json.JSONDecodeError:
            export_id_map = {}
        if not isinstance(export_id_map, dict):
            export_id_map = {}

        applied = 0
        pending = 0
        unassigned = 0
        if accepted:
            result = provider.apply_proposals(
                source_id,
                accepted,
                review_id=review_id,
                export_id_map=export_id_map,
            )
            applied = result.applied_count
            pending = result.pending_count
            unassigned = result.unassigned_count

        self.store_rejected_proposals(
            review_id=review_id,
            source_type=provider.source_type,
            source_id=source_id,
            proposals=rejected,
        )

        review.ai_model = (ai_model or "").strip()
        review.response_text = response_text.strip()
        review.response_loaded_at = datetime.now()
        review.loaded_proposals_count = (
            loaded_proposals_count
            if loaded_proposals_count is not None
            else len(accepted) + len(rejected)
        )
        review.pending_proposals_count = pending
        review.accepted_count = applied
        review.rejected_count = len(rejected)
        review.unassigned_count = unassigned
        return self.repository.update(review)


ai_peer_review_service = AiPeerReviewService()
