"""Obecná hromadná analýza podobností mezi dvěma oblastmi (SIMILARITY-10)."""

from __future__ import annotations

from dataclasses import dataclass

from core.services.text_similarity_service import (
    SimilarityCandidate,
    find_similar_pairs,
    find_similar_pairs_between,
)
from core.shared.sluzby.similarity_checked_pair_service import (
    normalize_similarity_pair_ids,
    similarity_checked_pair_service,
)
from core.shared.sluzby.similarity_domain import pair_entity_type_for_scopes
from core.shared.sluzby.similarity_item_collectors import (
    SimilarityItem,
    collect_similarity_items,
)


@dataclass(frozen=True)
class SimilarityAnalysisPair:
    """Kandidátní dvojice podobných položek s umístěním."""

    score: float
    match_type: str
    match_label: str
    left: SimilarityItem
    right: SimilarityItem
    checked: bool = False
    pair_entity_type: str = ""

    @property
    def score_percent(self) -> int:
        return int(round(self.score * 100))

    @property
    def normalized_ids(self) -> tuple[str, str]:
        return normalize_similarity_pair_ids(
            self.left.composite_id,
            self.right.composite_id,
        )


def _storage_id(item: SimilarityItem, *, cross_domain: bool) -> str:
    if cross_domain:
        return f"{item.entity_type}::{item.composite_id}"
    return item.composite_id


def analyze_domain_similarities(
    scope_a: str,
    scope_b: str,
    *,
    include_inactive: bool = True,
    include_checked: bool = False,
    progress_callback=None,
    should_cancel=None,
) -> tuple[list[SimilarityAnalysisPair], bool]:
    """Porovná položky oblastí A a B (stejná = uvnitř, různá = mezi oblastmi)."""
    items_a = collect_similarity_items(scope_a, include_inactive=include_inactive)
    same_domain = scope_a == scope_b
    items_b = (
        items_a
        if same_domain
        else collect_similarity_items(scope_b, include_inactive=include_inactive)
    )
    pair_entity_type = pair_entity_type_for_scopes(scope_a, scope_b)
    checked_keys = similarity_checked_pair_service.list_checked_keys(pair_entity_type)
    cross_domain = not same_domain

    by_storage: dict[str, SimilarityItem] = {}
    for item in items_a:
        by_storage[_storage_id(item, cross_domain=cross_domain)] = item
    for item in items_b:
        by_storage[_storage_id(item, cross_domain=cross_domain)] = item

    left_candidates = [
        SimilarityCandidate(
            id=_storage_id(item, cross_domain=cross_domain),
            text=item.text,
        )
        for item in items_a
    ]

    if same_domain:
        raw_pairs, cancelled = find_similar_pairs(
            left_candidates,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )
    else:
        right_candidates = [
            SimilarityCandidate(
                id=_storage_id(item, cross_domain=True),
                text=item.text,
            )
            for item in items_b
        ]
        raw_pairs, cancelled = find_similar_pairs_between(
            left_candidates,
            right_candidates,
            progress_callback=progress_callback,
            should_cancel=should_cancel,
        )

    results: list[SimilarityAnalysisPair] = []
    for pair in raw_pairs:
        left = by_storage.get(pair.left_id)
        right = by_storage.get(pair.right_id)
        if left is None or right is None:
            continue
        try:
            key = normalize_similarity_pair_ids(pair.left_id, pair.right_id)
        except ValueError:
            continue
        is_checked = key in checked_keys
        if is_checked and not include_checked:
            continue
        # Pro evidenci a UI používáme storage ID (u cross-domain typované).
        left_item = SimilarityItem(
            entity_type=left.entity_type,
            composite_id=pair.left_id,
            text=left.text,
            location_label=left.location_label,
        )
        right_item = SimilarityItem(
            entity_type=right.entity_type,
            composite_id=pair.right_id,
            text=right.text,
            location_label=right.location_label,
        )
        results.append(
            SimilarityAnalysisPair(
                score=pair.score,
                match_type=pair.match_type,
                match_label=pair.match_label,
                left=left_item,
                right=right_item,
                checked=is_checked,
                pair_entity_type=pair_entity_type,
            )
        )
    return results, cancelled
