"""Hromadná analýza podobností kontrolních otázek (SIMILARITY-2)."""

from __future__ import annotations

from dataclasses import dataclass

from core.services.text_similarity_service import (
    SimilarityCandidate,
    find_similar_pairs,
)
from moduly.proverky.sluzby.control_point_similarity_service import (
    ControlPointSimilarityCandidate,
    collect_control_point_candidates,
)


@dataclass(frozen=True)
class ControlPointSimilarityPair:
    """Kandidátní dvojice kontrolních otázek s umístěním."""

    score: float
    match_type: str
    match_label: str
    left: ControlPointSimilarityCandidate
    right: ControlPointSimilarityCandidate

    @property
    def score_percent(self) -> int:
        return int(round(self.score * 100))


def analyze_control_point_similarities(
    *,
    include_inactive: bool = True,
    progress_callback=None,
    should_cancel=None,
) -> tuple[list[ControlPointSimilarityPair], bool]:
    """Porovná všechny kontrolní otázky prověrek a vrátí kandidátní dvojice."""
    catalog = collect_control_point_candidates(include_inactive=include_inactive)
    by_id = {item.composite_id: item for item in catalog}
    pairs, cancelled = find_similar_pairs(
        [
            SimilarityCandidate(id=item.composite_id, text=item.text)
            for item in catalog
        ],
        progress_callback=progress_callback,
        should_cancel=should_cancel,
    )

    results: list[ControlPointSimilarityPair] = []
    for pair in pairs:
        left = by_id.get(pair.left_id)
        right = by_id.get(pair.right_id)
        if left is None or right is None:
            continue
        results.append(
            ControlPointSimilarityPair(
                score=pair.score,
                match_type=pair.match_type,
                match_label=pair.match_label,
                left=left,
                right=right,
            )
        )
    return results, cancelled
