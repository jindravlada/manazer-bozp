"""Hromadná analýza podobností kontrolních otázek (SIMILARITY-2 / SIMILARITY-3)."""

from __future__ import annotations

from dataclasses import dataclass

from core.services.text_similarity_service import (
    SimilarityCandidate,
    find_similar_pairs,
)
from core.shared.sluzby.similarity_checked_pair_service import (
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    normalize_similarity_pair_ids,
    similarity_checked_pair_service,
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
    checked: bool = False

    @property
    def score_percent(self) -> int:
        return int(round(self.score * 100))

    @property
    def normalized_ids(self) -> tuple[str, str]:
        return normalize_similarity_pair_ids(
            self.left.composite_id,
            self.right.composite_id,
        )


def analyze_control_point_similarities(
    *,
    include_inactive: bool = True,
    include_checked: bool = False,
    progress_callback=None,
    should_cancel=None,
) -> tuple[list[ControlPointSimilarityPair], bool]:
    """Porovná všechny kontrolní otázky prověrek a vrátí kandidátní dvojice.

    Zkontrolované dvojice se ve výchozím stavu do výsledků nezařazují
    (SIMILARITY-3). Při ``include_checked=True`` se vrátí i ony s ``checked=True``.
    """
    catalog = collect_control_point_candidates(include_inactive=include_inactive)
    by_id = {item.composite_id: item for item in catalog}
    checked_keys = similarity_checked_pair_service.list_checked_keys(
        SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT
    )
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
        try:
            key = normalize_similarity_pair_ids(pair.left_id, pair.right_id)
        except ValueError:
            continue
        is_checked = key in checked_keys
        if is_checked and not include_checked:
            continue
        results.append(
            ControlPointSimilarityPair(
                score=pair.score,
                match_type=pair.match_type,
                match_label=pair.match_label,
                left=left,
                right=right,
                checked=is_checked,
            )
        )
    return results, cancelled
