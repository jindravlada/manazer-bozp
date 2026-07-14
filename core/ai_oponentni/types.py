"""Sdílené typy pro poskytovatele oponentního posouzení."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class AiProposal:
    area: str
    name: str
    reasoning: str
    parent_export_id: str | None = None


@dataclass
class AiPeerReviewExportContent:
    """Obsah exportního balíčku sestavený doménovým poskytovatelem."""

    source_label: str
    prompt_text: str
    data_text: str
    overview_text: str
    summary_lines: list[str] = field(default_factory=list)
    zadani_json: dict | None = None
    schema_json: dict | None = None
    # export_id -> {"kind": "item"|"hazard"|"event"|"assessment", "id": <db_id>}
    export_id_map: dict[str, dict] = field(default_factory=dict)


@dataclass
class AiPeerReviewApplyResult:
    applied_count: int = 0
    unassigned_count: int = 0


@dataclass
class AiPeerReviewExportOptions:
    include_responsible_person: bool = False


class AiPeerReviewProvider(Protocol):
    """Doménový adaptér – každý modul dodá vlastní implementaci."""

    source_type: str

    def can_export(self, source_id: int | None) -> bool:
        ...

    def build_export_content(
        self,
        source_id: int,
        *,
        options: AiPeerReviewExportOptions,
    ) -> AiPeerReviewExportContent:
        ...

    def apply_proposals(
        self,
        source_id: int,
        proposals: list[AiProposal],
        *,
        review_id: int,
        export_id_map: dict[str, dict],
    ) -> AiPeerReviewApplyResult:
        """
        Zapsat převzaté návrhy výhradně podle exportních ID rodičů.
        Bez platného rodiče návrh nezařazovat (nepoužívat „připojit k prvnímu“).
        """
        ...
