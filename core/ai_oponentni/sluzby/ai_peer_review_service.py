"""Obecná služba exportu a evidence oponentního posouzení AI."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.ai_oponentni.constants import AI_PEER_REVIEW_ZIP_FILES
from core.ai_oponentni.modely.ai_peer_review import AiPeerReview
from core.ai_oponentni.repository.ai_peer_review_repository import AiPeerReviewRepository
from core.ai_oponentni.repository.ai_unassigned_proposal_repository import (
    AiUnassignedProposalRepository,
)
from core.ai_oponentni.sluzby.response_parser import parse_ai_peer_review_response
from core.ai_oponentni.types import (
    AiPeerReviewExportOptions,
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


class AiPeerReviewService:
    def __init__(self):
        self.repository = AiPeerReviewRepository()
        self.unassigned_repository = AiUnassignedProposalRepository()

    def get_for_source(self, source_type: str, source_id: int) -> list[AiPeerReview]:
        return self.repository.get_for_source(source_type, source_id)

    def get_by_id(self, review_id: int | None) -> AiPeerReview | None:
        if not review_id:
            return None
        return self.repository.get_by_id(review_id)

    def get_unassigned_for_review(self, review_id: int):
        return self.unassigned_repository.get_for_review(review_id)

    def default_export_filename(self, source_label: str, exported_at: datetime) -> str:
        stamp = exported_at.strftime("%Y-%m-%d_%H%M")
        safe = (
            (source_label or "posouzeni")
            .replace("/", "-")
            .replace(" ", "_")
            .replace(":", "-")
        )
        return f"AI_oponentni_{safe}_{stamp}.zip"

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
        if content.zadani_json is None or content.schema_json is None:
            raise AiPeerReviewError(
                "Doménový poskytovatel musí dodat zadani.json a schema_odpovedi.json."
            )

        exported_at = datetime.now()
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("pokyn_pro_AI.txt", content.prompt_text.rstrip() + "\n")
                zf.writestr("data.txt", content.data_text.rstrip() + "\n")
                zf.writestr("prehled.txt", content.overview_text.rstrip() + "\n")
                zf.writestr(
                    "zadani.json",
                    json.dumps(content.zadani_json, ensure_ascii=False, indent=2) + "\n",
                )
                zf.writestr(
                    "schema_odpovedi.json",
                    json.dumps(content.schema_json, ensure_ascii=False, indent=2) + "\n",
                )
        except OSError as error:
            target.unlink(missing_ok=True)
            raise AiPeerReviewError(
                f"Nepodařilo se vytvořit exportní soubor: {error}"
            ) from error

        try:
            with zipfile.ZipFile(target, "r") as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as error:
            target.unlink(missing_ok=True)
            raise AiPeerReviewError("Vytvořený exportní ZIP je neplatný.") from error

        if names != set(AI_PEER_REVIEW_ZIP_FILES):
            target.unlink(missing_ok=True)
            raise AiPeerReviewError("Exportní balíček neobsahuje očekávané soubory.")

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
                ai_model="",
                prompt_text=content.prompt_text,
                response_text="",
                accepted_count=0,
                rejected_count=0,
                unassigned_count=0,
            )
            saved = self.repository.add(review)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        return AiPeerReviewExportResult(
            review=saved,
            file_path=target,
            summary_lines=list(content.summary_lines),
        )

    def parse_response(self, response_text: str) -> list[AiProposal]:
        proposals = parse_ai_peer_review_response(response_text)
        if not proposals:
            raise AiPeerReviewError(
                "V odpovědi AI se nepodařilo najít žádný návrh "
                "ve formátu Oblast / Návrh / Zdůvodnění."
            )
        return proposals

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
        unassigned = 0
        if accepted:
            result = provider.apply_proposals(
                source_id,
                accepted,
                review_id=review_id,
                export_id_map=export_id_map,
            )
            applied = result.applied_count
            unassigned = result.unassigned_count

        review.ai_model = (ai_model or "").strip()
        review.response_text = response_text.strip()
        review.accepted_count = applied
        review.rejected_count = len(rejected)
        review.unassigned_count = unassigned
        return self.repository.update(review)


ai_peer_review_service = AiPeerReviewService()
