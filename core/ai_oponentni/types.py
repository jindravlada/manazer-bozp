"""Sdílené typy pro poskytovatele oponentního posouzení."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from core.ai_oponentni.constants import AI_PEER_REVIEW_DEFAULT_ROLE


@dataclass
class AiProposal:
    area: str
    name: str
    reasoning: str
    parent_export_id: str | None = None


@dataclass
class AiExportSourceChoice:
    """Položka pro výběr zdroje dávkového exportu (např. položka analýzy)."""

    id: int
    label: str
    category_label: str = ""


@dataclass
class AiPeerReviewBatchContent:
    """Jedna dávka exportního balíčku."""

    batch_number: int
    source_count: int
    object_count: int
    recommended_limit_exceeded: bool
    source_names: list[str]
    prompt_text: str
    data_text: str
    overview_text: str
    summary_lines: list[str] = field(default_factory=list)
    zadani_json: dict = field(default_factory=dict)
    schema_json: dict = field(default_factory=dict)
    filename: str = ""


@dataclass
class AiPeerReviewExportContent:
    """Obsah exportu – jedna nebo více dávek se společnou mapou exportních ID."""

    source_label: str
    export_id_map: dict[str, dict] = field(default_factory=dict)
    export_scope: str = "full"
    batch_count: int = 1
    selected_source_count: int = 0
    total_object_count: int = 0
    batches: list[AiPeerReviewBatchContent] = field(default_factory=list)
    batches_overview_text: str = ""
    change_tracking: dict = field(
        default_factory=lambda: {
            "mode": "full",
            "base_export": None,
            "changed_objects": [],
        }
    )

    @property
    def prompt_text(self) -> str:
        return self.batches[0].prompt_text if self.batches else ""

    @property
    def data_text(self) -> str:
        return self.batches[0].data_text if self.batches else ""

    @property
    def overview_text(self) -> str:
        return self.batches[0].overview_text if self.batches else ""

    @property
    def summary_lines(self) -> list[str]:
        return list(self.batches[0].summary_lines) if self.batches else []

    @property
    def zadani_json(self) -> dict | None:
        return self.batches[0].zadani_json if self.batches else None

    @property
    def schema_json(self) -> dict | None:
        return self.batches[0].schema_json if self.batches else None

    @property
    def batch_number(self) -> int:
        return self.batches[0].batch_number if self.batches else 1


@dataclass
class AiPeerReviewApplyResult:
    applied_count: int = 0
    unassigned_count: int = 0


@dataclass
class AiPeerReviewExportOptions:
    export_scope: str = "full"
    selected_source_ids: list[int] | None = None
    opponent_role: str = AI_PEER_REVIEW_DEFAULT_ROLE
    objectives: list[str] | None = None
    focus_areas: list[str] | None = None
    workplace_characteristics: str = ""


class AiPeerReviewProvider(Protocol):
    """Doménový adaptér – každý modul dodá vlastní implementaci."""

    source_type: str

    def can_export(self, source_id: int | None) -> bool:
        ...

    def get_export_source_choices(self, source_id: int) -> list[AiExportSourceChoice]:
        """Aktivní zdroje pro ruční výběr do dávkového exportu."""
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
